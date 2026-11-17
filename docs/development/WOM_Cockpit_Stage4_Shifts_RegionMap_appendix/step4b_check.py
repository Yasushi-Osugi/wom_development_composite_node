# -*- coding: utf-8 -*-
"""Stage 4 (shifts / region map): the screen's numbers against tool 2's outputs (extends
output/cockpit_step4/step4_check.py: market labels, one row per factory, the engine's capacity).

    python output/cockpit_step4b/step4b_check.py soy    # soy sauce: S01 (C01) -> S02 (C02), made by the CLI
    python output/cockpit_step4b/step4b_check.py cos    # cosmetics regression: the 88-week workspace re-run

Writes <appendix>/step4b_screen_check_<part>.csv and screenshots in <appendix>/screens/.
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

APX = os.path.join("docs", "development", "WOM_Cockpit_Stage4_Shifts_RegionMap_appendix")
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
    mm = pd.read_csv(os.path.join(cd, "market_map.csv"), dtype=str)
    mk = {(r.sku_id, r.region): r.market for r in mm.itertuples()}

    def lab(sku, reg):
        return f"{sku}:{mk[(sku, reg)]}（{reg}）" if mk.get((sku, reg), reg) != reg else f"{sku}:{reg}"

    # supply: difference-only table and the per-key totals vs tool 2
    k = pd.read_csv(os.path.join(cd, "supply_by_key.csv"))
    piv = k.pivot_table(index=["sku_id", "region"], columns="case",
                        values=["demand", "on_time", "early", "late", "backlog_end"])
    m = {"需要": "demand", "当週": "on_time", "早出し": "early", "遅配": "late", "配分後の未充足": "backlog_end"}
    diff = {idx: {lb: piv.loc[idx, (col, alt)] - piv.loc[idx, (col, base)] for lb, col in m.items()}
            for idx in piv.index}
    nz = {kk: v for kk, v in diff.items() if any(v.values())}
    sd = t["supply_diff"]
    keys_screen = [x for x in sd["鍵"] if x != "供給の差なし"]
    check(part, f"{pair} 差の表の鍵（市場の名前と地域、差のある鍵だけ）", sorted(keys_screen),
          sorted(lab(a, b) for a, b in nz))
    for (sku, reg), v in nz.items():
        r = sd[sd["鍵"] == lab(sku, reg)].iloc[0]
        for lb, val in v.items():
            check(part, f"{pair} 差 {lab(sku, reg)} {lb}", num(r[lb]), float(val))
    st = t["supply_totals"]
    for (sku, reg) in piv.index:
        for c in (base, alt):
            rr = st[(st["鍵"] == lab(sku, reg)) & st["案"].str.endswith(c)]
            for lb, col in (("当週", "on_time"), ("遅配", "late"), ("配分後の未充足（⑤）", "backlog_end")):
                check(part, f"{pair} 供給の合計 {lab(sku, reg)} {c} {lb}", num(rr.iloc[0][lb]) if len(rr) else None,
                      float(piv.loc[(sku, reg), (col, c)]))
    # summary: P0 difference, boundaries
    tot = pd.read_csv(os.path.join(cd, "money_totals.csv"))
    rep = tot[(tot["period"] == "report") & (tot["product"] == "*")].iloc[0]
    check(part, f"{pair} 要点：P0 の差", f"差 {V.fmt_yen(rep.profit_r2_diff)} 円" in summ, True)
    fc = pd.read_csv(os.path.join(cd, "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
    mf = t["money_fixed_cost"]
    for r in fc.itertuples():
        if r.f_star_per_week:
            f = float(r.f_star_per_week)
            txt = f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"
            name = r.display_name or r.cost_item
            check(part, f"{pair} 要点：境目 {name}", f"{txt} 円／週" in summ, True)
            sr = mf[mf["費目"] == name]
            check(part, f"{pair} 金額の表：{name} の ΔW", num(sr.iloc[0]["ΔW"]) if len(sr) else None, num(r.delta_W))
    p0 = t["money_p0"]
    for r in tot[tot["product"] == "*"].itertuples():
        per = "報告期間" if r.period == "report" else "全計画期間（参考）"
        sr = p0[(p0.iloc[:, 0] == per) & (p0.iloc[:, 1] == "合計")]
        check(part, f"{pair} 金額の表：P0 の差（{per}）", str(sr.iloc[0, 4]) if len(sr) else None,
              V.fmt_yen(r.profit_r2_diff))
    # factory: periods in the summary, the table for every factory, the source of the capacity
    pw = pd.read_csv(os.path.join(cd, "planned_output_weeks.csv"), dtype=str, keep_default_na=False)
    whole = pw[pw["row"] != "値ごと"] if "row" in pw.columns else pw
    per_value = pw[pw["row"] == "値ごと"] if "row" in pw.columns else pw.iloc[0:0]
    for r in whole.itertuples():
        if r.first_week_at_cap:
            check(part, f"{pair} 要点：{r.case} {r.product} {r.factory} の期間",
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
    choices = {c["label"]: c for c in scr.cmp["factory"]["choices"]}
    check(part, f"{pair} 工場の選択肢", sorted(scr.factory_sku["values"]),
          sorted(c["label"] for c in V.factory_view(cd, base, alt)["choices"]))
    fwk = pd.read_csv(os.path.join(cd, "factory_weekly.csv"), dtype={"week": str})
    ag = pd.read_csv(os.path.join(cd, "age_summary.csv"), dtype=str)
    for label in list(scr.factory_sku["values"]):
        scr.factory_sku.set(label)
        scr._draw_factory()
        sku, fac = choices[label]["sku"], choices[label]["factory"]
        tb = scr.displayed_tables()
        fw = tb["factory_weeks"]
        wf = whole[(whole["product"] == sku) & (whole["factory"] == fac)]
        pv = per_value[(per_value["product"] == sku) & (per_value["factory"] == fac)]
        check(part, f"{pair} 工場 {label} の行の数", len(fw), len(wf) + len(pv))
        for r in wf.itertuples():
            sr = fw[fw["案"].str.match(rf"^(基準|相手) {r.case}$")]
            check(part, f"{pair} 工場 {r.case} {label} 計画の上限（良品）",
                  str(sr.iloc[0]["計画の上限（良品）"]) if len(sr) else None, str(r.shippable_soft_values))
            check(part, f"{pair} 工場 {r.case} {label} ちょうど作った週",
                  num(sr.iloc[0]["ちょうど作った週"]) if len(sr) else None, num(r.weeks_at_cap))
            check(part, f"{pair} 工場 {r.case} {label} 全計画で下回った週",
                  num(sr.iloc[0]["全計画で上限を下回った週（作らない週を含む）"]) if len(sr) else None,
                  num(r.weeks_below_cap))
        for r in pv.itertuples():
            lb = f"　うち {r.planned_first_week}〜{r.planned_last_week}（{r.planned_weeks} 週） {r.case}"
            sr = fw[fw["案"] == lb]
            check(part, f"{pair} 工場 {r.case} {label} 上限 {r.shippable_soft_values} の行がある", len(sr), 1)
            if len(sr):
                check(part, f"{pair} 工場 {r.case} {label} 上限 {r.shippable_soft_values} ちょうど作った週",
                      num(sr.iloc[0]["ちょうど作った週"]), num(r.weeks_at_cap))
        src = "エンジンの値" if (fwk["capacity_source"] == "engine").all() else "capacity_plan.csv の値"
        check(part, f"{pair} 工場 {label} の図の題に能力の出どころ（{src}）",
              src in scr.factory_fig.axes[0].get_title(loc="left"), True)
        a = ag[(ag["channel"] == "*") & (ag["product"].isin([sku, "*"]))]
        a = a.assign(_o=(a["product"] != sku).astype(int)).sort_values(["case", "_o"]).drop_duplicates("case")
        fa = tb["factory_age"]
        for r in a.itertuples():
            sr = fa[fa["案"].str.endswith(r.case)]
            if len(sr):
                check(part, f"{pair} 工場 {r.case} {label} 年齢の最大", num(sr.iloc[0]["年齢の最大（週）"]),
                      num(r.fifo_age_max))
        if shots:
            scr.nb.select(2)
            shot(root, f"{part}_{pair}_factory_{label.replace(' @ ', '_')}.png")
    if shots:
        for i, name in ((0, "summary"), (1, "supply"), (3, "money")):
            scr.nb.select(i)
            shot(root, f"{part}_{pair}_{i + 1}_{name}.png")
    root.destroy()


def check_inputs(part, ws, cid, want_text):
    """② the selected case's planned output (the engine's values when the case has run)."""
    d = V.case_inputs(ws, cid)
    root = new_root()
    scr = S.CompareScreen(root, ws, None, None)
    scr.select(cid)
    root.update()
    txt = scr.inputs.get("1.0", "end")
    for (sku, node), want in want_text.items():
        r = [x for x in d["capacity"] if (x["sku_id"], x["node"]) == (sku, node)][0]
        check(part, f"② {cid} {sku}@{node} の計画の生産量", r["text"], want)
        check(part, f"② 画面の文 {cid} {sku}@{node}", f"{sku} @ {node}：{want}" in txt, True)
    shot(root, f"{part}_{cid}_inputs.png")
    root.destroy()


part = sys.argv[1]
if part == "soy":
    W = os.path.join("output", "cockpit_step4b", "soy")
    tail = "、休業 3 週（2027-W18, 2028-W18, 2028-W33）（エンジンの値）"
    check_inputs(part, W, "C01", {("Soy_Sauce", "Bottling_Noda"): "18 シフト → 686 lot／週（設備 800 × 18 ÷ 21）" + tail})
    check_inputs(part, W, "C02", {("Soy_Sauce", "Bottling_Noda"): "21 シフト → 800 lot／週（設備 800 × 21 ÷ 21）" + tail})
    t = V.case_table(W)
    i = [k for k, c in enumerate(t["columns"]) if c.startswith("能力")]
    check(part, "① 能力の列（エンジンの値）", [t["columns"][k] for k in i] + [[r["cells"][k] for k in i] for r in t["rows"]],
          ["能力 Soy_Sauce@Bottling_Noda（hard/soft）", ["800/686"], ["800/800"]])
    check_pair(part, W, "C01", "C02", shots=True)
elif part == "cos":
    W = os.path.join("output", "cockpit_step4b", "cos88")
    check_inputs(part, W, "C03", {("COS_Cream", "Factory_JP"):
                                  "max_supply 13・cap_soft 2028-W11〜2029-W46 は 12、ほかは 11（エンジンの値）"})
    check_pair(part, W, "C01", "C02")
    check_pair(part, W, "C01", "C03", shots=True)
    check_pair(part, W, "C02", "C03")
out = pd.DataFrame(rows)
out.to_csv(os.path.join(APX, f"step4b_screen_check_{part}.csv"), index=False, encoding="utf-8")
print(f"{part}: {int(out['match'].sum())}/{len(out)} match")
for r in out[~out["match"]].itertuples():
    print("  NG", r.what, "| screen:", r.screen, "| expected:", r.expected)
