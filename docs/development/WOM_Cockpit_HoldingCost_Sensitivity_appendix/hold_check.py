# -*- coding: utf-8 -*-
"""Holding cost sensitivity (RequestLetter_Cockpit_HoldingCost_Sensitivity §4):
1 A1 recomputed from the raw inventory and inv_group_hq, 2 one week by hand, 3 the screen against tool 2's outputs,
5 the unused weeks, 6 the earlier comparison files unchanged.

    python output/cockpit_hold/hold_check.py
"""
import ctypes
import filecmp
import json
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

WS = os.path.join("output", "cockpit_m5", "cos")
BEFORE = os.path.join("output", "cockpit_hold", "compare_before")
APX = os.path.join("docs", "development", "WOM_Cockpit_HoldingCost_Sensitivity_appendix")
os.makedirs(os.path.join(APX, "screens"), exist_ok=True)
PAIRS = [("C02", "C03"), ("C06", "C07"), ("C01", "C02"), ("C01", "C03")]
rows = []


def check(part, what, got, want):
    rows.append({"part": part, "what": what, "screen": got, "expected": want, "match": got == want})


# 1 A1 from the raw files
for b, a in PAIRS:
    d = os.path.join(WS, "compare", f"{b}__{a}")
    hb = pd.read_csv(os.path.join(d, "holding_base.csv"))
    for cid in (b, a):
        run = os.path.join(WS, cid, "run", "vc")
        inv = pd.read_csv(os.path.join(run, "vc_inventory_weekly.csv"))
        ent = pd.read_csv(os.path.join(WS, cid, "model", "vc_entity.csv"), dtype=str)
        grp = set(ent.loc[ent["kind"] == "group", "entity_id"])
        own = inv[inv["owner"].isin(grp) & (inv["external"] == 0) & (inv["valued"] == 1)]
        v3 = pd.read_csv(os.path.join(run, "vc_v3_weekly.csv"))
        v3 = v3[v3["group_key"] == "GROUP"]
        rep = v3[v3["in_report"].astype(str) == "True"]
        wk = own.groupby("week_index")["group_hq"].sum()
        diff = (wk.reindex(rep["week_index"], fill_value=0).values - rep["inv_group_hq"].values)
        check("1 A1", f"{b}__{a} {cid} 報告期間の週ごとの差の最大", round(float(abs(diff).max()), 6), 0.0)
        for period, sel in (("report", v3["in_report"].astype(str) == "True"),
                            ("warmup", v3["in_report"].astype(str) != "True")):
            want = float(own[own["week_index"].isin(v3.loc[sel, "week_index"])]["group_hq"].sum())
            got = float(hb[(hb["case"] == cid) & (hb["period"] == period) & (hb["product"] == "*")
                           & (hb["location_kind"] == "*")]["B_group_hq"].iloc[0])
            check("1 A1", f"{b}__{a} {cid} {period} B_group_hq", round(got, 2), round(want, 2))
        lk = hb[(hb["case"] == cid) & (hb["product"] == "*") & (hb["location_kind"] != "*")]
        tot = hb[(hb["case"] == cid) & (hb["product"] == "*") & (hb["location_kind"] == "*")]
        check("1 A1", f"{b}__{a} {cid} node＋transit ＝ 計", round(float(lk["B_group_hq"].sum()), 2),
              round(float(tot["B_group_hq"].sum()), 2))
        check("1 A1", f"{b}__{a} {cid} 未評価の lot・週", int(tot["unvalued_lots_weeks"].sum()), 0)

# 2 one week by hand: C02, 2028-W20, COS_Cream, 10 %
inv = pd.read_csv(os.path.join(WS, "C02", "run", "vc", "vc_inventory_weekly.csv"))
x = inv[(inv["week"] == "2028-W20") & (inv["product"] == "COS_Cream") & inv["owner"].isin(["E_JP", "E_SG"])
        & (inv["external"] == 0) & (inv["valued"] == 1)]
hand = float(x["group_hq"].sum()) * 0.10 / 52
det = pd.read_csv(os.path.join(WS, "compare", "C02__C03", "holding_by_week_sku.csv"))
y = det[(det["case"] == "C02") & (det["week"] == "2028-W20") & (det["product"] == "COS_Cream")].iloc[0]
check("2 手計算", f"C02 2028-W20 COS_Cream group_hq {x['group_hq'].sum():,.0f} × 0.10 ÷ 52", round(float(y["holding_10pct"]), 6),
      round(hand, 6))
hand_rows = x[["owner", "location_kind", "location", "item", "lots", "group_hq"]]


def new_root(geo="1700x1000+10+10"):
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
    x0, y0 = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x0, y0, x0 + root.winfo_width(), y0 + root.winfo_height())).save(
        os.path.join(APX, "screens", name))


# 3・5 the screen
UNUSED = {("C02", "C03"): ((173, 158, 15), (88, 88, 0)), ("C06", "C07"): ((173, 160, 13), (101, 101, 0)),
          ("C01", "C02"): (None, (173, 158, 15)), ("C01", "C03"): (None, (88, 88, 0))}
for b, a in PAIRS:
    d = os.path.join(WS, "compare", f"{b}__{a}")
    hs = pd.read_csv(os.path.join(d, "holding_sensitivity.csv"), dtype=str, keep_default_na=False)
    root = new_root()
    scr = S.CompareScreen(root, WS, b, a)
    root.update()
    t = scr.displayed_tables()
    h = t["money_holding"]
    check("3 画面", f"{b}__{a} 保有費の表の行数", len(h), len(hs))
    for i, r in hs.iterrows():
        s = h.iloc[i]
        for col, src in ((2, "f_star_incl_warmup"), (3, "f_star_report_only"), (4, "dH_total"), (5, "dH_report"),
                         (6, "dH_warmup"), (7, "H_base_report"), (8, "H_base_warmup"), (9, "H_alt_report"),
                         (10, "H_alt_warmup")):
            check("3 画面", f"{b}__{a} {float(r['annual_rate']) * 100:g}% {src}", s.iloc[col],
                  V.fmt_yen(r[src]) if r[src] != "" else "")
        check("3 画面", f"{b}__{a} {float(r['annual_rate']) * 100:g}% 境目の読み方", s.iloc[11], r["boundary_incl_warmup"])
    fc = t["money_fixed_cost"]
    raise_row = fc[fc.iloc[:, 0] == "増産の確保費"].iloc[0]
    cols = list(fc.columns)
    wb, wa = UNUSED[(b, a)]
    for side, want, tag in (("基準", wb, b), ("相手", wa, a)):
        heads = [f"W 基準（{b}）" if side == "基準" else f"W 相手（{a}）",
                 f"上限で作った週 基準（{b}）" if side == "基準" else f"上限で作った週 相手（{a}）",
                 f"使わなかった週 基準（{b}）" if side == "基準" else f"使わなかった週 相手（{a}）"]
        got = tuple(str(raise_row.iloc[cols.index(hh)]) for hh in heads)
        exp = ("0", "", "") if want is None else tuple(str(v) for v in want)
        check("5 使わなかった週", f"{b}__{a} {tag} W・上限で作った週・使わなかった週", got, exp)
    summ = "\n".join(t["summary"]["line"])
    notes = "\n".join(t["notes"]["note"])
    sent = V.holding_sentence(V.comparison(WS, b, a)["money"]["holding"])[0]
    check("3 画面", f"{b}__{a} 要点の一文", sent in summ, True)
    check("3 画面", f"{b}__{a} ④ の注意", "在庫の保有費は P0 に入っていない。感度は金額と境目の見出しに（年率は仮置き、採用する率は未設定）" in notes,
          True)
    check("3 画面", f"{b}__{a} 「在庫の保管費は金額に入っていない」が無い", "在庫の保管費は金額に入っていない" in notes, False)
    if (b, a) in (("C02", "C03"), ("C06", "C07")):
        scr.nb.select(scr.nb.index(scr.tab_money))
        shot(root, f"hold_{b}__{a}_money.png")
        scr.nb.select(0)
        shot(root, f"hold_{b}__{a}_summary.png")
    root.destroy()

# 6 earlier files unchanged (the four comparisons made again; only compare.json and the summary text changed)
for p in ("C01__C02", "C01__C03"):
    for f in sorted(os.listdir(os.path.join(BEFORE, p))):
        if f in ("compare.json", "comparison_summary.md"):
            continue
        check("6 前の数字", f"{p}/{f} バイト単位で同じ",
              filecmp.cmp(os.path.join(BEFORE, p, f), os.path.join(WS, "compare", p, f), shallow=False), True)
    a = json.load(open(os.path.join(BEFORE, p, "compare.json"), encoding="utf-8"))
    n = json.load(open(os.path.join(WS, "compare", p, "compare.json"), encoding="utf-8"))
    check("6 前の数字", f"{p}/compare.json 違う鍵（時刻だけ）", sorted(k for k in set(a) | set(n) if a.get(k) != n.get(k)),
          ["at", "seconds"])
vc = os.path.join(WS, "C02", "model", "vc_config.csv")
cfg = pd.read_csv(vc, dtype=str, keep_default_na=False)
hr = cfg[cfg.iloc[:, 0] == "holding_rate_weekly"]
check("6 前の数字", "holding_rate_weekly は空欄のまま", "" if hr.empty else hr.iloc[0, 1], "")

df = pd.DataFrame(rows)
df.to_csv(os.path.join(APX, "hold_check.csv"), index=False, encoding="utf-8-sig")
hand_rows.to_csv(os.path.join(APX, "hand_check_C02_2028-W20_COS_Cream.csv"), index=False, encoding="utf-8-sig")
print(f"{int(df['match'].sum())}/{len(df)} match")
print(df[~df["match"]].to_string())
