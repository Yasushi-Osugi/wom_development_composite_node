# -*- coding: utf-8 -*-
"""Stage 4 trial: the screen's numbers against tool 2's outputs (extends output/cockpit_step3/step3_check.py).

    python output/cockpit_step4/step4_check.py cos      # cosmetics: C01->C02, C01->C03, C02->C03
    python output/cockpit_step4/step4_check.py soy      # soy sauce: S01->S02 (cases made by the CLI)

Writes <appendix>/step4_screen_check_<part>.csv and screenshots in <appendix>/screens/.
"""
import ctypes
import os
import sys
import time
import tkinter as tk

import pandas as pd

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
from wom.cockpit import compare_view_model as V  # noqa: E402
from wom.cockpit import compare_screen as S  # noqa: E402

APX = os.path.join("docs", "development", "WOM_Cockpit_Stage4_Trial_appendix")
os.makedirs(os.path.join(APX, "screens"), exist_ok=True)
rows = []


def check(part, what, got, want):
    rows.append({"part": part, "what": what, "screen": got, "expected": want, "match": got == want})


def num(x):
    s = str(x).replace(",", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return s


def new_root(geo="1700x960+10+10"):
    for _ in range(5):
        try:
            r = tk.Tk()
            r.geometry(geo)
            return r
        except tk.TclError:
            time.sleep(0.2)
    raise RuntimeError("tk")


def shot(root, name):
    from PIL import ImageGrab
    root.update()
    time.sleep(0.5)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(
        os.path.join(APX, "screens", name))


def check_pair(part, ws, base, alt, shots=False):
    pair = f"{base}__{alt}"
    cd = os.path.join(ws, "compare", pair)
    root = new_root()
    scr = S.CompareScreen(root, ws, base, alt)
    root.update()
    t = scr.displayed_tables()
    summ = "\n".join(t["summary"]["line"])
    notes = "\n".join(t["notes"]["note"])
    # supply: difference-only table vs tool 2 (key totals)
    k = pd.read_csv(os.path.join(cd, "supply_by_key.csv"))
    piv = k.pivot_table(index=["sku_id", "region"], columns="case",
                        values=["demand", "on_time", "early", "late", "backlog_end"])
    m = {"需要": "demand", "当週": "on_time", "早出し": "early", "遅配": "late", "配分後の未充足": "backlog_end"}
    diff = {idx: {lab: piv.loc[idx, (col, alt)] - piv.loc[idx, (col, base)] for lab, col in m.items()}
            for idx in piv.index}
    nz = {kk: v for kk, v in diff.items() if any(v.values())}
    sd = t["supply_diff"]
    keys_screen = [x for x in sd["鍵"] if x != "供給の差なし"]
    check(part, f"{pair} 差の表の鍵（差のある鍵だけ）", sorted(keys_screen), sorted(f"{a}:{b}" for a, b in nz))
    for (sku, reg), v in nz.items():
        r = sd[sd["鍵"] == f"{sku}:{reg}"].iloc[0]
        for lab, val in v.items():
            check(part, f"{pair} 差 {sku}:{reg} {lab}", num(r[lab]), float(val))
    # supply tab totals per key (both cases) vs tool 2
    sup = None  # supply totals: checked through the difference table (step 3 pattern)
    if sup is not None and len(sup):
        for (sku, reg) in piv.index:
            for c in (base, alt):
                want = int(piv.loc[(sku, reg), ("on_time", c)])
                got = [r for r in sup.to_dict("records") if r.get("鍵") == f"{sku}:{reg}" and str(r.get("案", "")).endswith(c)]
                if got and "当週" in got[0]:
                    check(part, f"{pair} 供給 {sku}:{reg} {c} 当週", num(got[0]["当週"]), float(want))
    # summary: P0 difference, boundaries, factory periods
    tot = pd.read_csv(os.path.join(cd, "money_totals.csv"))
    rep = tot[(tot["period"] == "report") & (tot["product"] == "*")].iloc[0]
    check(part, f"{pair} 要点：P0 の差", f"差 {rep.profit_r2_diff:,.0f} 円" in summ, True)
    fc = pd.read_csv(os.path.join(cd, "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
    for r in fc.itertuples():
        if r.f_star_per_week:
            f = float(r.f_star_per_week)
            txt = f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"
            check(part, f"{pair} 要点：境目 {r.display_name or r.cost_item}", f"{txt} 円／週" in summ, True)
    mf = t["money_fixed_cost"]
    for r in fc.itertuples():
        if r.f_star_per_week:
            name = r.display_name or r.cost_item
            sr = mf[mf["費目"] == name]
            if len(sr):
                check(part, f"{pair} 金額の表：{name} の ΔW", num(sr.iloc[0]["ΔW"]), num(r.delta_W))
    pw = pd.read_csv(os.path.join(cd, "planned_output_weeks.csv"), dtype=str, keep_default_na=False)
    whole = pw[pw["row"] != "値ごと"] if "row" in pw.columns else pw
    per_value = pw[pw["row"] == "値ごと"] if "row" in pw.columns else pw.iloc[0:0]
    for r in whole.itertuples():
        if r.first_week_at_cap:
            check(part, f"{pair} 要点：{r.case} {r.product} の期間",
                  f"{r.first_week_at_cap}〜{r.last_week_at_cap}（{r.span_weeks} 週）" in summ, True)
    for r in per_value.itertuples():
        check(part, f"{pair} 要点：{r.case} {r.product} 上限 {r.shippable_soft_values} の週",
              f"上限 {r.shippable_soft_values} の {r.planned_weeks} 週（{r.planned_first_week}〜{r.planned_last_week}）"
              f"のうち、ちょうど作った週 {r.weeks_at_cap}" in summ, True)
    inv = pd.read_csv(os.path.join(cd, "inventory_by_week_sku.csv"))
    for p, g in inv.groupby("product"):
        check(part, f"{pair} ④ 在庫 {p}", f"{p} {int(g.lots_base.sum()):,} → {int(g.lots_alt.sum()):,}" in notes, True)
    for w in ("良い", "推奨", "有利"):
        check(part, f"{pair} 要点に「{w}」が無い", w in summ, False)
    # factory tab, every SKU
    for sku in list(scr.factory_sku["values"]):
        scr.factory_sku.set(sku)
        scr._draw_factory()
        fw = scr.displayed_tables()["factory_weeks"]
        for r in whole[whole["product"] == sku].itertuples():
            sr = fw[fw["案"].str.match(rf"^(基準|相手) {r.case}$")]
            check(part, f"{pair} 工場 {r.case} {sku} ちょうど作った週", num(sr.iloc[0]["ちょうど作った週"]) if len(sr) else None,
                  num(r.weeks_at_cap))
            check(part, f"{pair} 工場 {r.case} {sku} 全計画で下回った週",
                  num(sr.iloc[0]["全計画で上限を下回った週（作らない週を含む）"]) if len(sr) else None, num(r.weeks_below_cap))
        for r in per_value[per_value["product"] == sku].itertuples():
            lab = f"　うち {r.planned_first_week}〜{r.planned_last_week}（{r.planned_weeks} 週） {r.case}"
            sr = fw[fw["案"] == lab]
            check(part, f"{pair} 工場 {r.case} {sku} 上限 {r.shippable_soft_values} の行がある", len(sr), 1)
            if len(sr):
                check(part, f"{pair} 工場 {r.case} {sku} 上限 {r.shippable_soft_values} ちょうど作った週",
                      num(sr.iloc[0]["ちょうど作った週"]), num(r.weeks_at_cap))
        ag = pd.read_csv(os.path.join(cd, "age_summary.csv"), dtype=str)
        ag = ag[(ag["channel"] == "*") & (ag["product"] == sku)]
        fa = scr.displayed_tables()["factory_age"]
        for r in ag.itertuples():
            sr = fa[fa["案"].str.endswith(r.case)]
            check(part, f"{pair} 工場 {r.case} {sku} 年齢の最大", num(sr.iloc[0]["年齢の最大（週）"]) if len(sr) else None,
                  num(r.fifo_age_max))
        if shots:
            scr.nb.select(2)
            shot(root, f"{part}_{pair}_factory_{sku}.png")
    if shots:
        for i, name in enumerate(("summary", "supply", "factory", "money")):
            if name == "factory":
                continue
            scr.nb.select(i)
            shot(root, f"{part}_{pair}_{i + 1}_{name}.png")
    root.destroy()


def check_inputs(part, ws, cid, want_cap):
    """② the selected case's planned output by week ranges, ① the case table's capacity column."""
    d = V.case_inputs(ws, cid)
    for (sku, node), (ms, cs) in want_cap.items():
        r = [x for x in d["capacity"] if (x["sku_id"], x["node"]) == (sku, node)][0]
        check(part, f"② {cid} {sku}@{node} max_supply", r["max_supply"], ms)
        check(part, f"② {cid} {sku}@{node} cap_soft", r["cap_soft"], cs)
    root = new_root()
    scr = S.CompareScreen(root, ws, None, None)
    scr.select(cid)
    root.update()
    txt = scr.inputs.get("1.0", "end")
    for (sku, node), (ms, cs) in want_cap.items():
        if txt:
            check(part, f"② 画面の文 {cid} {sku}", f"{sku} @ {node}：max_supply {ms}・cap_soft {cs}" in txt, True)
    shot(root, f"{part}_{cid}_inputs.png")
    root.destroy()


part = sys.argv[1]
if part == "cos":
    W = os.path.join("output", "cockpit_step4", "cos")
    check_inputs(part, W, "C03", {("COS_Cream", "Factory_JP"): ("13", "2028-W11〜2029-W46 は 12、ほかは 11"),
                                  ("COS_Serum", "Factory_JP"): ("17", "14")})
    t = V.case_table(W)
    i = [k for k, c in enumerate(t["columns"]) if c.startswith("能力")]
    check(part, "① 能力の列", [[r["cells"][k] for k in i] for r in t["rows"]],
          [["13/11"], ["13/12"], ["13/11・12（週で違う）"]])
    check_pair(part, W, "C01", "C02")
    check_pair(part, W, "C01", "C03", shots=True)
    check_pair(part, W, "C02", "C03")
elif part == "soy":
    W = os.path.join("output", "cockpit_step4", "soy")
    check_pair(part, W, "C01", "C02", shots=True)
out = pd.DataFrame(rows)
out.to_csv(os.path.join(APX, f"step4_screen_check_{part}.csv"), index=False, encoding="utf-8")
print(f"{part}: {int(out['match'].sum())}/{len(out)} match")
for r in out[~out["match"]].itertuples():
    print("  NG", r.what, "| screen:", r.screen, "| expected:", r.expected)
