# -*- coding: utf-8 -*-
"""B checks on the real screen: S2 (screen numbers == tool 2 outputs), S3/S4 marks and words, S5 (changed inputs,
reopen), and screenshots. Reads only (the changed-input check uses the case command and reverts it)."""
import json
import os
import subprocess
import sys
import time
import tkinter as tk
import ctypes
try:                      # screenshots: Tk and the screen grab must use the same (physical) pixels
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
from wom.cockpit import compare_screen as S  # noqa: E402

WS = os.path.join("output", "cockpit_cases", "stage1")
APX = os.path.join("docs", "development", "WOM_Cockpit_Stage3_Step2_CompareScreen_appendix")
os.makedirs(os.path.join(APX, "screens"), exist_ok=True)
PAIRS = [("C01", "C02"), ("C03", "C04"), ("C05", "C06"), ("C01", "C05"), ("C02", "C04"), ("C02", "C06")]


def num(x):
    s = str(x).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return s


def new_root():
    for _ in range(5):
        try:
            r = tk.Tk()
            r.geometry("1700x960+10+10")
            return r
        except tk.TclError:
            time.sleep(0.2)
    raise RuntimeError("tk")


def open_screen(base, alt):
    root = new_root()
    scr = S.CompareScreen(root, WS, base, alt)
    root.update()
    return root, scr


rows = []


def check(pair, what, got, want):
    ok = got == want
    rows.append({"pair": pair, "what": what, "screen": got, "tool2": want, "match": ok})


for base, alt in PAIRS:
    pair = f"{base}__{alt}"
    d = os.path.join(WS, "compare", pair)
    root, scr = open_screen(base, alt)
    t = scr.displayed_tables()
    rec = json.load(open(os.path.join(d, "compare.json"), encoding="utf-8"))
    # ① P0 of both cases
    cases = t["cases"].set_index(t["cases"].columns[1])
    p0col = [c for c in cases.columns if c.startswith("P0")][0]
    check(pair, "① P0 基準", num(cases.loc[base, p0col]), round(rec["P0_base"]))
    check(pair, "① P0 相手", num(cases.loc[alt, p0col]), round(rec["P0_alt"]))
    check(pair, "① 基準の印", cases.loc[base, "role"], "◎")
    check(pair, "① 相手の印", cases.loc[alt, "role"], "○")
    # ③ supply totals == supply_allocation_by_key / supply_by_key (all SKUs: switch the combobox is not needed,
    #    the totals table holds every key)
    st = t["supply_totals"]
    ak = os.path.join(d, "supply_allocation_by_key.csv")
    if os.path.exists(ak):
        k = pd.read_csv(ak)
        cols = {"需要": "q1_original", "供給の対象": "q2_in_scope", "未配分（③）": "q3_unallocated", "当週": "on_time",
                "早出し": "early", "遅配": "late", "配分後の未充足（⑤）": "q5_backlog_end"}
    else:
        k = pd.read_csv(os.path.join(d, "supply_by_key.csv"))
        k = k.pivot_table(index=["sku_id", "region"], columns="case",
                          values=["demand", "on_time", "early", "late", "backlog_end"]).reset_index()
        k.columns = ["sku_id", "region"] + [f"{a}_{'base' if b == base else 'alt'}" for a, b in k.columns[2:]]
        cols = {"需要": "demand", "当週": "on_time", "早出し": "early", "遅配": "late", "配分後の未充足（⑤）": "backlog_end"}
    for r in k.itertuples():
        key = f"{r.sku_id}:{r.region}"
        for side, cid in (("base", base), ("alt", alt)):
            sr = st[(st["案"] == cid) & (st["鍵"] == key)].iloc[0]
            for label, col in cols.items():
                check(pair, f"③ 供給 {cid} {key} {label}", num(sr[label]), float(getattr(r, f"{col}_{side}")))
    # ③ money: report P0 by product
    mt = pd.read_csv(os.path.join(d, "money_totals.csv"))
    mp = t["money_p0"]
    for r in mt[mt["period"] == "report"].itertuples():
        prod = "合計" if r.product == "*" else r.product
        sr = mp[(mp["期間"] == "報告期間") & (mp["SKU"] == prod)].iloc[0]
        check(pair, f"③ P0 報告期間 {prod} 基準", num(sr["P0 基準"]), round(r.profit_r2_base))
        check(pair, f"③ P0 報告期間 {prod} 相手", num(sr["P0 相手"]), round(r.profit_r2_alt))
        check(pair, f"③ P0 報告期間 {prod} 差", num(sr["差"]), round(r.profit_r2_diff))
    # ③ fixed cost table
    fc = pd.read_csv(os.path.join(d, "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
    mf = t["money_fixed_cost"]
    for i, r in fc.iterrows():
        sr = mf.iloc[i]
        check(pair, f"③ 固定費 {r['cost_item']} 費目", sr["費目"], r["cost_item"] or "（固定費の表なし）")
        for label, col in (("W 基準", "W_base"), ("W 相手", "W_alt"), ("ΔW", "delta_W")):
            check(pair, f"③ 固定費 {r['cost_item']} {label}", num(sr[label]), num(r[col]))
        check(pair, f"③ 固定費 {r['cost_item']} ΔP0", num(sr["ΔP0"]), round(num(r["delta_P0"])))
        fs = r["f_star_per_week"]
        check(pair, f"③ 固定費 {r['cost_item']} 境目（小数 2 桁）",
              round(num(sr["境目（円／週）"]), 2) if sr["境目（円／週）"] else "", round(num(fs), 2) if fs else "")
        if r["cost_item"] not in ("", "合計") and r["weekly_amount_base"] == "" and r["paid_start_base"]:
            check(pair, f"③ 固定費 {r['cost_item']} 週額は「未設定」", sr["週額 基準"], "未設定")
            check(pair, f"③ 固定費 {r['cost_item']} 控除後は「未算出」", sr["控除後 基準"], "未算出")
    # ③ factory: planned output weeks
    pw = pd.read_csv(os.path.join(d, "planned_output_weeks.csv"), dtype=str, keep_default_na=False)
    fwt = t["factory_weeks"]
    sku = scr.factory_sku.get()
    for r in pw[pw["product"] == sku].itertuples():
        sr = fwt[fwt["案"] == r.case].iloc[0]
        check(pair, f"③ 工場 {r.case} {sku} その間の週数", sr["その間の週数"], r.span_weeks)
        check(pair, f"③ 工場 {r.case} {sku} 最初の週", sr["ちょうど作った最初の週"], r.first_week_at_cap)
    # ④ words (S4) and the min-supply marks (S3)
    notes = "\n".join(t["notes"]["note"])
    if any(r["weekly_amount_base"] == "" and r["paid_start_base"] for _, r in fc.iterrows()):
        check(pair, "④ 未設定と保留", ("未設定" in notes and "保留" in notes), True)
    if pair == "C03__C04":
        sr = st[(st["案"] == "C04") & (st["鍵"] == "COS_Cream:SG_Distributor")].iloc[0]
        check(pair, "S3 C04 SG 代理店のクリームの最低ちょうどの週", num(sr["最低ちょうどの週"]), 83.0)
        check(pair, "S3 未配分と未充足の列が分かれている", "未配分（③）" in st.columns and "配分後の未充足（⑤）" in st.columns, True)
    # screenshots of the C05 -> C06 / C03 -> C04 pairs
    if pair in ("C03__C04", "C05__C06"):
        from PIL import ImageGrab
        for i, name in enumerate(("supply", "factory", "money")):
            scr.nb.select(i)
            root.update()
            time.sleep(0.6)
            root.update()
            x, y = root.winfo_rootx(), root.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(
                os.path.join(APX, "screens", f"{pair}_{i + 1}_{name}.png"))
    root.destroy()

# S5: reopen gives the same tables; a changed case shows no result and "実行し直す"
root, scr = open_screen("C05", "C06")
a = {k: v.to_csv(index=False) for k, v in scr.displayed_tables().items()}
scr.reopen()
root.update()
b = {k: v.to_csv(index=False) for k, v in scr.displayed_tables().items()}
check("C05__C06", "S5 開き直して同じ表（同じ窓）", a == b, True)
root.destroy()
root, scr = open_screen("C05", "C06")
c = {k: v.to_csv(index=False) for k, v in scr.displayed_tables().items()}
check("C05__C06", "S5 閉じて開き直して同じ表（新しい窓）", a == c, True)
root.destroy()
py = sys.executable
env = dict(os.environ, PYTHONIOENCODING="utf-8")
subprocess.run([py, "-m", "tools.cockpit_cases", "set", "--ws", WS, "--case", "C05", "planned-output", "--sku",
                "COS_Cream", "--cap-soft", "11"], check=True, env=env, capture_output=True)
try:
    root, scr = open_screen("C05", "C06")
    t = scr.displayed_tables()
    cases = t["cases"].set_index(t["cases"].columns[1])
    p0col = [c for c in cases.columns if c.startswith("P0")][0]
    check("C05 changed", "S5 入力が変わった案の P0 は出さない", cases.loc["C05", p0col], "")
    check("C05 changed", "S5 状態は「実行し直す」", cases.loc["C05", "状態"], "実行し直す")
    check("C05 changed", "S5 比較の数字を出さない（表が空）", len(t["money_fixed_cost"]) + len(t["supply_totals"]), 0)
    check("C05 changed", "S5 比較の理由を出す", "入力が変わった" in t["message"]["message"][0], True)
    notes = "\n".join(t["notes"]["note"])
    check("C05 changed", "S5 ④ に変わったファイルの名前", "model/capacity_plan.csv" in notes, True)
    from PIL import ImageGrab
    scr.nb.select(2)
    root.update()
    time.sleep(0.6)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(
        os.path.join(APX, "screens", "C05_changed_rerun.png"))
    root.destroy()
finally:
    subprocess.run([py, "-m", "tools.cockpit_cases", "set", "--ws", WS, "--case", "C05", "planned-output", "--sku",
                    "COS_Cream", "--cap-soft", "12"], check=True, env=env, capture_output=True)
root, scr = open_screen("C05", "C06")
d2 = {k: v.to_csv(index=False) for k, v in scr.displayed_tables().items()}
check("C05 reverted", "S5 戻すと元の表", a == d2, True)
root.destroy()

out = pd.DataFrame(rows)
out.to_csv(os.path.join(APX, "s2_screen_vs_tool2.csv"), index=False, encoding="utf-8-sig")
print(out.groupby("pair")["match"].agg(["count", "sum"]).to_string())
bad = out[~out["match"]]
print("ALL MATCH" if bad.empty else bad.to_string())
