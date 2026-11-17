# -*- coding: utf-8 -*-
"""Milestone 5 (demand hypothesis): the screen against tool 2's outputs (extends step4b_check.py), the
需要の仮説… dialog, C01 -> C04 made with the screen only, and the text-only change.

    python output/cockpit_m5/m5_check.py
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

APX = os.path.join("docs", "development", "WOM_Cockpit_Milestone5_DemandHypothesis_appendix")
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


import json  # noqa: E402
import shutil  # noqa: E402
from wom.cockpit import cases as C  # noqa: E402
from wom.cockpit import case_actions as A  # noqa: E402
from wom.cockpit import case_runner as R  # noqa: E402

W = os.path.join("output", "cockpit_m5", "cos")
part = "m5"
NOTE = "発売直後の需要が想定より強い場合（立ち上がりの倍率 0.5→1.0）。到達点 5 の試行の仮説"

# 1. the four pairs (and the two known ones)
for b, a in (("C01", "C02"), ("C01", "C03"), ("C01", "C04"), ("C03", "C05"), ("C02", "C06"), ("C05", "C07")):
    check_pair(part, W, b, a, shots=(b, a) in (("C01", "C04"), ("C05", "C07")))

# 2. (2) the hypothesis with its basis text; the summary lists the change and the text
root = new_root()
scr = S.CompareScreen(root, W, "C01", "C04")
scr.select("C04")
root.update()
t = scr.displayed_tables()
txt = "\n".join(t["inputs"]["line"])
check(part, "② C04 タイのクリームの行",
      "COS_Cream:TH_Distributor  投入 2028-W01  定常 3 lot／週（立ち上がり 13 週 × 1.0）" in txt, True)
check(part, "② C04 根拠の文", f"根拠：{NOTE}" in txt, True)
summ = "\n".join(t["summary"]["line"])
check(part, "要点の違い：倍率", "COS_Cream:TH_Distributor の立ち上がりの割合（基準 0.5、相手 1.0）" in summ, True)
check(part, "要点の違い：根拠の文",
      f"COS_Cream:TH_Distributor の根拠（基準「docs/scenarios/cosmetics.md Demand assumptions」、相手「{NOTE}」）" in summ,
      True)
for w in ("良い", "推奨", "有利"):
    check(part, f"要点に「{w}」が無い", w in summ, False)
shot(root, "m5_C04_inputs_and_summary.png")

# 3. the dialog: product x market table, the preview (+13, and the rounding reason), nothing written
scr.select("C01")
root.update()
scr._dlg_hypothesis()
h = scr._hyp_dialog
m = h["matrix"]
check(part, "需要の仮説：表の製品", m["products"], ["COS_Serum", "COS_Cream"])
check(part, "需要の仮説：表の市場", m["markets"], ["SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor"])
check(part, "需要の仮説：セル", m["cells"][("COS_Cream", "TH_Distributor")]["text"], "2028-W01・定常 3・×0.5（13 週）")
check(part, "需要の仮説：表の行（画面）", list(h["tree"].item("COS_Cream", "values"))[-1], "2028-W01・定常 3・×0.5（13 週）")
before = open(os.path.join(W, "C01", "model", "market_entry_plan.csv"), "rb").read()


def pick(hd, key):
    hd["state"]["key"] = key
    for col, e in hd["entries"].items():
        e.delete(0, "end")
        e.insert(0, hd["matrix"]["cells"][key].get(col, ""))


def put(hd, col, v):
    hd["entries"][col].delete(0, "end")
    hd["entries"][col].insert(0, v)


pick(h, ("COS_Cream", "TH_Distributor"))
put(h, "ramp_ratio", "0.6")
r = h["preview_fn"]()
check(part, "需要の差の見込み 0.6：理由", ("需要の差 0 lot" in r.message and "3 × 0.6 ＝ 1.8 → 2" in r.message), True)
put(h, "ramp_ratio", "1.0")
r = h["preview_fn"]()
check(part, "需要の差の見込み 1.0", r.message,
      "需要の差 +13 lot（この鍵 299 → 312、全体 4,056 → 4,069、2028-W01〜2028-W13 の 13 週）。週ごと：各 2 → 3（+1）")
check(part, "需要の差の見込みでは何も書かない",
      open(os.path.join(W, "C01", "model", "market_entry_plan.csv"), "rb").read() == before, True)
h["dialog"].update()
shot(h["dialog"], "m5_dialog_preview.png")
h["dialog"].destroy()
root.destroy()

# 4. C01 -> C04 made with the screen's operations only (copy, the dialog, run, compare)
root = new_root()
scr = S.CompareScreen(root, W, None, None)
scr.select("C01")
r = scr.do_copy("画面で作った 強い立ち上がり")
cid = r.data["id"]
scr.select(cid)
root.update()
scr._dlg_hypothesis()
h = scr._hyp_dialog
pick(h, ("COS_Cream", "TH_Distributor"))
put(h, "ramp_ratio", "1.0")
put(h, "basis_note", NOTE)
h["ok"]()
check(part, f"画面で作った {cid}：投入の表が CLI の C04 と同じ",
      open(os.path.join(W, cid, "model", "market_entry_plan.csv"), "rb").read() ==
      open(os.path.join(W, "C04", "model", "market_entry_plan.csv"), "rb").read(), True)
check(part, f"画面で作った {cid}：需要が CLI の C04 と同じ",
      open(os.path.join(W, cid, "model", "demand_forecast.csv"), "rb").read() ==
      open(os.path.join(W, "C04", "model", "demand_forecast.csv"), "rb").read(), True)
scr.do_run()
scr.wait_idle(900)
sc = C.read_case(W, cid)["run"]["summary"]
s4 = C.read_case(W, "C04")["run"]["summary"]
for k in ("P0_report", "deliveries_by_sku", "backlog_end_by_key", "late_by_key"):
    check(part, f"画面で作った {cid} と CLI の C04：{k}", sc.get(k), s4.get(k))
scr.base, scr.alt = "C01", cid
scr.do_compare()
scr.wait_idle(600)
root.destroy()
a = pd.read_csv(os.path.join(W, "compare", f"C01__{cid}", "supply_by_key.csv"))
b = pd.read_csv(os.path.join(W, "compare", "C01__C04", "supply_by_key.csv"))
cols = ["sku_id", "region", "demand", "on_time", "early", "late", "backlog_end"]
check(part, f"C01 → {cid} の供給が C01 → C04 と同じ",
      a[a.case == cid][cols].reset_index(drop=True).equals(b[b.case == "C04"][cols].reset_index(drop=True)), True)
check_pair(part, W, "C01", cid)

# 5. text only: C04's basis text rewritten -> still 済み, the screen shows the new text and the note
NEW = NOTE + "（文だけ書き換えた：到達点 5 S4 の確かめ）"
r = A.set_demand_hypothesis(W, "C04", "COS_Cream", "TH_Distributor", {"basis_note": NEW})
check(part, "文だけの変更：メッセージ", "実行し直しは要らない" in r.message, True)
check(part, "文だけの変更：C04 は済みのまま", C.status(W, "C04")["state"], C.ST_DONE)
check(part, "文だけの変更：比較 C01 → C04 は済みのまま", R.compare_status(W, "C01", "C04"), C.ST_DONE)
root = new_root()
scr = S.CompareScreen(root, W, "C01", "C04")
scr.select("C04")
root.update()
t = scr.displayed_tables()
check(part, "文だけの変更：② に新しい文", f"根拠：{NEW}" in "\n".join(t["inputs"]["line"]), True)
summ = "\n".join(t["summary"]["line"])
check(part, "文だけの変更：要点に新しい文", f"相手「{NEW}」" in summ, True)
check(part, "文だけの変更：比べた後に変わった注記（要点）",
      "根拠の文は比べた後に変わった（数字は同じ）：C04 COS_Cream:TH_Distributor" in summ, True)
check(part, "文だけの変更：比べた後に変わった注記（④）",
      any("根拠の文は比べた後に変わった" in x for x in t["notes"]["note"]), True)
shot(root, "m5_C04_text_changed.png")
root.destroy()

# 6. a number on a scratch copy -> 入力が変わった
tmp = os.path.join("output", "cockpit_m5", "tmp_ws")
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(W, tmp)
A.set_demand_hypothesis(tmp, "C04", "COS_Cream", "TH_Distributor", {"ramp_ratio": "0.8"})
st = C.status(tmp, "C04")
check(part, "数の列の変更：入力が変わった", (st["state"], "model/market_entry_plan.csv" in st["changed_files"]),
      (C.ST_CHANGED, True))
shutil.rmtree(tmp, ignore_errors=True)

out = pd.DataFrame(rows)
out.to_csv(os.path.join(APX, "m5_screen_check.csv"), index=False, encoding="utf-8")
print(f"{part}: {int(out['match'].sum())}/{len(out)} match")
for r in out[~out["match"]].itertuples():
    print("  NG", r.what, "| screen:", r.screen, "| expected:", r.expected)
