# -*- coding: utf-8 -*-
"""Stage 3 step 3 checks on the real screen.

A: on the copy output/cockpit_step3/ws_a (stage1 is never written): summary and difference-only supply table vs
   tool 2's outputs, the fixes F5-F12, no "which is better" words, screenshots.
B: a new workspace output/cockpit_step3/ws_b (base case only, made with tools.cockpit_cases), then ONLY the
   screen's operations (CompareScreen.do_*): run the base, copy + launch week + run, copy + planned output + run,
   compare, the raise-weeks helper, compare again (63,226 yen/week), a conflict, a cost-only change, and the
   responsiveness while a case runs. Screenshots on the way.
"""
import ctypes
import json
import os
import shutil
import subprocess
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
from wom.cockpit import case_actions as A  # noqa: E402
from wom.cockpit import cases as C  # noqa: E402
from wom.cockpit import compare_screen as S  # noqa: E402

D = os.path.join("output", "cockpit_step3")
APX = os.path.join("docs", "development", "WOM_Cockpit_Stage3_Step3_Operations_appendix")
os.makedirs(os.path.join(APX, "screens"), exist_ok=True)
IN = os.path.join("docs", "development", "WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix", "inputs")
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
rows, log = [], []


def check(part, what, got, want):
    rows.append({"part": part, "what": what, "screen": got, "expected": want, "match": got == want})


def note(msg):
    log.append(f"{time.strftime('%H:%M:%S')} {msg}")
    print(msg, flush=True)


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


def cases_cli(*args):
    p = subprocess.run([PY, "-m", "tools.cockpit_cases", *args], env=ENV, capture_output=True, text=True,
                       encoding="utf-8")
    note(f"$ python -m tools.cockpit_cases {' '.join(args)} -> {p.returncode}")
    if p.returncode != 0:
        raise RuntimeError(p.stdout + p.stderr)


# ══ A ═══════════════════════════════════════════════════════════════════
WSA = os.path.join(D, "ws_a")
for base, alt in (("C01", "C05"), ("C05", "C06"), ("C03", "C04")):
    pair = f"{base}__{alt}"
    cd = os.path.join(WSA, "compare", pair)
    root = new_root()
    scr = S.CompareScreen(root, WSA, base, alt)
    root.update()
    t = scr.displayed_tables()
    summ = "\n".join(t["summary"]["line"])
    notes = "\n".join(t["notes"]["note"])
    # difference-only supply table vs tool 2 (key totals)
    ak = os.path.join(cd, "supply_allocation_by_key.csv")
    if os.path.exists(ak):
        k = pd.read_csv(ak)
        m = {"需要": "q1_original", "当週": "on_time", "早出し": "early", "遅配": "late", "未配分": "q3_unallocated",
             "配分後の未充足": "q5_backlog_end"}
        diff = {(r.sku_id, r.region): {lab: getattr(r, f"{col}_alt") - getattr(r, f"{col}_base") for lab, col in m.items()}
                for r in k.itertuples()}
    else:
        k = pd.read_csv(os.path.join(cd, "supply_by_key.csv"))
        piv = k.pivot_table(index=["sku_id", "region"], columns="case",
                            values=["demand", "on_time", "early", "late", "backlog_end"])
        m = {"需要": "demand", "当週": "on_time", "早出し": "early", "遅配": "late", "配分後の未充足": "backlog_end"}
        diff = {}
        for idx in piv.index:
            dd = {lab: piv.loc[idx, (col, alt)] - piv.loc[idx, (col, base)] for lab, col in m.items()}
            dd["未配分"] = 0
            diff[idx] = dd
    nz = {kk: v for kk, v in diff.items() if any(v.values())}
    sd = t["supply_diff"]
    keys_screen = [x for x in sd["鍵"] if x != "供給の差なし"]
    check("A", f"{pair} 差の表の鍵（差のある鍵だけ）", sorted(keys_screen), sorted(f"{a}:{b}" for a, b in nz))
    for (sku, reg), v in nz.items():
        r = sd[sd["鍵"] == f"{sku}:{reg}"].iloc[0]
        for lab, val in v.items():
            check("A", f"{pair} 差 {sku}:{reg} {lab}", num(r[lab]), float(val))
    # summary numbers come from tool 2
    tot = pd.read_csv(os.path.join(cd, "money_totals.csv"))
    rep = tot[(tot["period"] == "report") & (tot["product"] == "*")].iloc[0]
    check("A", f"{pair} 要点：P0 の差", f"差 {rep.profit_r2_diff:,.0f} 円" in summ, True)
    fc = pd.read_csv(os.path.join(cd, "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
    for r in fc.itertuples():
        if r.f_star_per_week:
            f = float(r.f_star_per_week)
            txt = f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"
            check("A", f"{pair} 要点：境目 {r.display_name or r.cost_item}", f"{txt} 円／週" in summ, True)
    pw = pd.read_csv(os.path.join(cd, "planned_output_weeks.csv"), dtype=str, keep_default_na=False)
    for r in pw.itertuples():
        check("A", f"{pair} 要点：{r.case} {r.product} の期間", f"{r.first_week_at_cap}〜{r.last_week_at_cap}（{r.span_weeks} 週）" in summ, True)
    inv = pd.read_csv(os.path.join(cd, "inventory_by_week_sku.csv"))
    for p, g in inv.groupby("product"):
        check("A", f"{pair} ④ 在庫 {p}", f"{p} {int(g.lots_base.sum()):,} → {int(g.lots_alt.sum()):,}" in notes, True)
    for w in ("良い", "推奨", "有利"):
        check("A", f"{pair} 要点に「{w}」が無い", w in summ, False)
    check("A", f"{pair} ④ 在庫の保管費の但し書き", "在庫の保管費は金額に入っていない" in notes, True)
    check("A", f"{pair} ④ コード名を出さない", ("TH_cream_channel_fee" in notes or "planned_output_raise" in notes), False)
    check("A", f"{pair} ④ 計画の端の週の書き方", "計画の端の週（計画の最初の 1 週と最後の 4 週）" in notes, True)
    # F5 / F6 / F9 fixes
    fw = t["factory_weeks"]
    check("A", f"{pair} F5 下回った週の列が 2 つ", ["報告期間で上限を下回った週", "全計画で上限を下回った週（作らない週を含む）"]
          == [c for c in fw.columns if "下回った" in c], True)
    for r in pw[pw["product"] == scr.factory_sku.get()].itertuples():
        sr = fw[fw["案"].str.endswith(r.case)].iloc[0]
        check("A", f"{pair} F5 {r.case} 報告期間で下回った週", sr["報告期間で上限を下回った週"], r.weeks_below_cap_in_report)
        check("A", f"{pair} F5 {r.case} 全計画で下回った週", sr["全計画で上限を下回った週（作らない週を含む）"], r.weeks_below_cap)
    check("A", f"{pair} F6 在庫の表の見出しに案の ID", all((base in c or alt in c) for c in t["factory_inventory"].columns[1:]), True)
    mf = t["money_fixed_cost"]
    check("A", f"{pair} F8 合計の行が一番上", mf.iloc[0]["費目"], "合計")
    check("A", f"{pair} F8 判断の列が左", list(mf.columns[:6]), ["費目", "ΔP0", "ΔW", "境目（円／週）", "境目の置き方", "評価"])
    after_cols = [c for c in mf.columns if c.startswith("控除後 ")]
    check("A", f"{pair} F9 費目の行に控除後を出さない", all(mf.iloc[i][c] == "" for i in range(1, len(mf)) for c in after_cols), True)
    check("A", f"{pair} F10 表示名", all(n in list(mf["費目"]) for n in ["タイのクリームの販路費"]), True)
    if pair == "C05__C06":
        check("A", "C05__C06 F12 2 案に共通の不足", "COS_Serum:TH_Distributor の配分後の未充足 104 lot は 2 案に共通" in notes, True)
        check("A", "C05__C06 F11 クリームの在庫 +16.1%", "COS_Cream 26,989 → 31,340（+16.1%）" in notes, True)
        for i, name in enumerate(("summary", "supply", "factory", "money")):
            scr.nb.select(i)
            shot(root, f"A_{pair}_{i + 1}_{name}.png")
    root.destroy()

# F7: the case table's policy column is short; the file names are in ②
root = new_root()
scr = S.CompareScreen(root, WSA, "C03", "C04")
scr.select("C04")
root.update()
t = scr.displayed_tables()
pol = t["cases"].set_index("ID").loc["C04", "供給の方針"]
check("A", "F7 ① の供給の方針は短い名前", pol, "数量枠＋最低供給・削って最低")
check("A", "F7 ② にファイル名", any("allocation_qty_TH70_early.csv" in x for x in t["inputs"]["line"]), True)
shot(root, "A_C03__C04_cases_and_inputs.png")
root.destroy()

# ══ B ═══════════════════════════════════════════════════════════════════
WSB = os.path.join(D, "ws_b")
if os.path.exists(WSB):
    shutil.rmtree(WSB)
cases_cli("new", "--ws", WSB, "--model", os.path.join("data", "sample", "cosmetics-sg-th-2027-2029"),
          "--max-age-weeks", "52", "--name", "基準・後期")
cases_cli("set", "--ws", WSB, "--case", "C01", "entry-plan", "--file", os.path.join(IN, "market_entry_plan_A_late.csv"))
cases_cli("set", "--ws", WSB, "--case", "C01", "capacity", "--sku", "COS_Serum", "--max-supply", "17", "--cap-soft", "14")
cases_cli("set", "--ws", WSB, "--case", "C01", "capacity", "--sku", "COS_Cream", "--max-supply", "13", "--cap-soft", "11")

root = new_root()
scr = S.CompareScreen(root, WSB)
root.update()


def op(what, r):
    note(f"[画面] {what} -> {'OK' if r.ok else 'NG'}：{r.message}")
    return r


def result(cid):
    run = C.read_case(WSB, cid)["run"]
    return run["state"], run.get("summary") or {}


# 1 base: run from the screen; responsiveness while it runs
scr.select("C01")
op("C01 を実行", scr.do_run())
gaps, t0, switched = [], time.perf_counter(), 0
last = t0
shot_taken = False
while scr.worker.busy:
    scr.update()
    now = time.perf_counter()
    gaps.append(now - last)
    last = now
    if now - t0 > 2 and switched < 4:          # switch the tabs while the case runs
        scr.nb.select(switched % 4)
        switched += 1
    if now - t0 > 12 and not shot_taken:
        shot(root, "B_1_running_progress.png")
        shot_taken = True
    time.sleep(0.05)
scr.wait_idle()
check("B", "実行中に画面の更新が止まった最長（秒）", max(gaps) < 1.0, True)
note(f"実行中の更新の間隔：最長 {max(gaps):.2f} 秒（{len(gaps)} 回）、見出しを {switched} 回切り替えた")
st, s = result("C01")
check("B", "C01 状態", st, C.ST_DONE)
check("B", "C01 P0（段 1 の C01）", s.get("P0_report"), 606_871_080.0)
check("B", "C01 クリームの納品", (s.get("deliveries_by_sku") or {}).get("COS_Cream"), 1680)

# 2 copy + launch week + run
scr.select("C01")
op("C01 を複製（基準・早期）", scr.do_copy("基準・早期"))
op("C02 のタイのクリームの投入週を 2027-W27 に", scr.do_set_launch_week("COS_Cream", "TH_Distributor", "2027-W27"))
op("C02 の入力の検査（不正な週）", scr.do_set_launch_week("COS_Cream", "TH_Distributor", "2027-27"))
check("B", "不正な週は文で返す", "週のラベルではない" in scr.op_msg.cget("text"), True)
op("C02 を実行", scr.do_run())
scr.wait_idle()
st, s = result("C02")
check("B", "C02 P0（段 1 の C02）", s.get("P0_report"), 606_871_080.0)
check("B", "C02 クリームの納品", (s.get("deliveries_by_sku") or {}).get("COS_Cream"), 1680)

# 3 copy + planned output + run
scr.select("C01")
op("C01 を複製（生産量を上げる・後期）", scr.do_copy("生産量を上げる・後期"))
op("C03 のクリームの cap_soft を 14 に（max_supply 13 を超える）", scr.do_set_planned_output("COS_Cream", "Factory_JP", "14"))
check("B", "max_supply を超える値は段 1 の理由のまま", "max_supply を超える" in scr.op_msg.cget("text"), True)
op("C03 のクリームの cap_soft を 12 に", scr.do_set_planned_output("COS_Cream", "Factory_JP", "12"))
op("C03 を実行", scr.do_run())
scr.wait_idle()
st, s = result("C03")
check("B", "C03 P0（段 1 の C05）", s.get("P0_report"), 616_860_840.0)
check("B", "C03 クリームの納品", (s.get("deliveries_by_sku") or {}).get("COS_Cream"), 1768)

# 4 compare, raise weeks helper, compare again
scr.select("C01")
scr._set_role("base")
scr.select("C03")
scr._set_role("alt")
op("C01 → C03 を並べる", scr.do_compare())
scr.wait_idle()
cands = A.raise_week_candidates(WSB, "C03")
cream = [c for c in cands if c["sku"] == "COS_Cream"][0]
check("B", "増産の有償の週の候補", (cream["first"], cream["last"], cream["span"]), ("2026-W46", "2029-W46", 158))
scr.select("C03")
scr._dlg_raise()
root.update()
shot(root, "B_2_raise_weeks_dialog.png")
for w in scr.winfo_children():
    if isinstance(w, tk.Toplevel):
        w.destroy()
root.update()
op("C03 に増産の有償の週を入れる（確かめて「入れる」）", scr.do_apply_raise_weeks(cream, "E_JP", "JPY"))
t = scr.displayed_tables()
check("B", "費用の前提だけ変えた後の比較は「並べ直す」", "費用の前提が変わった" in t["message"]["message"][0], True)
check("B", "そのとき固定費の表を出さない", list(t["money_fixed_cost"].iloc[:, 0]), ["費用の前提が変わった：並べ直す"])
check("B", "そのとき要点の「判断に要るもの」を出さない",
      any("費用の前提が変わった：並べ直す（境目は出さない）" in x for x in t["summary"]["line"]), True)
op("C01 → C03 を並べ直す", scr.do_compare())
scr.wait_idle()
fc = pd.read_csv(os.path.join(WSB, "compare", "C01__C03", "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
f = float(fc[fc.cost_item == "planned_output_raise"].f_star_per_week.iloc[0])
check("B", "境目（段 1・段 2 と同じ 63,226 円／週）", round(f, 2), 63226.33)
t = scr.displayed_tables()
check("B", "並べ直すと「費用の前提が変わった」が消える", t["message"]["message"][0], "")
shot(root, "B_3_compare_summary.png")

# 5 cost-only change: weekly amount on the raise row
rows_now = [{"cost_item": "planned_output_raise", "display_name": "増産の確保費", "entity": "E_JP",
             "paid_start_week": "2026-W46", "paid_end_week": "2029-W46", "weekly_amount": "50000", "currency": "JPY",
             "count_outside_report": True, "note": ""}]
op("C03 の増産の確保費に週額 50,000 を入れる", scr.do_set_fixed_cost(rows_now))
st3 = C.status(WSB, "C03")["state"]
check("B", "費用の前提だけ変えても案は「済み」", st3, C.ST_DONE)
check("B", "比較は「並べ直す」", "費用の前提が変わった" in scr.displayed_tables()["message"]["message"][0], True)
op("C01 → C03 を並べ直す", scr.do_compare())
scr.wait_idle()
fc = pd.read_csv(os.path.join(WSB, "compare", "C01__C03", "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
tot = fc[fc.cost_item == "合計"]
r1 = fc[fc.cost_item == "planned_output_raise"].iloc[0]
check("B", "週額を入れると控除後の差が出る（P0 の差 − 50,000 × 158）", round(float(r1.delta_P_after)), round(9_989_760 - 50_000 * 158))
op("C03 の週額を空欄（未設定）に戻す", scr.do_set_fixed_cost([dict(rows_now[0], weekly_amount="")]))
op("C01 → C03 を並べ直す", scr.do_compare())
scr.wait_idle()

# 6 conflict
conf = os.path.join(D, "allocation_conflict.csv")
a = pd.read_csv(os.path.join(IN, "allocation_qty_TH70.csv"), dtype=str, keep_default_na=False)
a.loc[(a.sku_id == "COS_Cream") & (a.region == "TH_Distributor"), "alloc_lots"] = "100"
a.to_csv(conf, index=False, encoding="utf-8")
scr.select("C01")
op("C01 を複製（衝突する方針）", scr.do_copy("衝突する方針"))
cid = scr.selected
op(f"{cid} に方針（タイのクリームの数量枠 100 ＋ 最低 7 割）", scr.do_set_policy(
    allocation_file=conf, policy_file=os.path.join(IN, "udp_policy_MS50TH70.csv"), week_rule="trim_to_capacity_latest",
    knowledge_file=os.path.join(IN, "knowledge.json")))
op(f"{cid} を実行", scr.do_run())
scr.wait_idle()
st, _ = result(cid)
check("B", f"{cid} は「衝突」", st, C.ST_CONFLICT)
t = scr.displayed_tables()
check("B", "① の状態が「衝突」", t["cases"].set_index("ID").loc[cid, "状態"], C.ST_CONFLICT)
nt = "\n".join(t["notes"]["note"])
check("B", "④ に衝突の理由とログの場所", ("衝突" in nt and "置けない 199 lot" in nt and "logs" in nt), True)
scr.select(cid)
shot(root, "B_4_conflict.png")
root.destroy()

# reopen: a new window on ws_b shows the same tables
root = new_root()
scr2 = S.CompareScreen(root, WSB, "C01", "C03")
root.update()
t2 = scr2.displayed_tables()
check("B", "閉じて開き直して同じ案の表", len(t2["cases"]), 4)
root.destroy()
check("S7", "stage1 の 6 案は変わらない（case.json の実行の記録）",
      all(json.load(open(os.path.join("output", "cockpit_cases", "stage1", c, "case.json"), encoding="utf-8"))["run"]["state"] == "済み"
          for c in ("C01", "C02", "C03", "C04", "C05", "C06")), True)

out = pd.DataFrame(rows)
out.to_csv(os.path.join(APX, "step3_checks.csv"), index=False, encoding="utf-8-sig")
open(os.path.join(APX, "step3_procedure_log.txt"), "w", encoding="utf-8").write("\n".join(log) + "\n")
print(out.groupby("part")["match"].agg(["count", "sum"]).to_string())
bad = out[~out["match"]]
print("ALL MATCH" if bad.empty else bad.to_string())
