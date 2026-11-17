# -*- coding: utf-8 -*-
"""After-cost three cases (RequestLetter_Cockpit_AfterCost_ThreeCases §3): F3, the holding cost against the
sensitivity outputs, the screen against the CLI tables, the width of (2), earlier numbers unchanged.

    python output/cockpit_after/ac_check.py
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

WS = os.path.join("output", "cockpit_m5", "cos")
APX = os.path.join("docs", "development", "WOM_Cockpit_AfterCost_ThreeCases_appendix")
os.makedirs(os.path.join(APX, "screens"), exist_ok=True)
rows = []


def check(part, what, got, want):
    rows.append({"part": part, "what": what, "screen": got, "expected": want, "match": got == want})


T = {"now": pd.read_csv(os.path.join(WS, "after_cost", "current_demand", "after_cost_table.csv")),
     "strong": pd.read_csv(os.path.join(WS, "after_cost", "strong_ramp", "after_cost_table.csv"))}


def P(t, sc, rt, c):
    return float(T[t][(T[t]["scenario"] == sc) & (T[t]["holding_rate_text"] == rt) & (T[t]["case"] == c)]["P_after"].iloc[0])


# 1 F3
m = ("中・割増15%", "10%")
check("1 F3", "中・15%・10% C03 − C01", round(P("now", *m, "C03") - P("now", *m, "C01"), 2), 5686183.08)
check("1 F3", "中・15%・10% C03 − C02", round(P("now", *m, "C03") - P("now", *m, "C02"), 2), 2629530.77)
check("1 F3", "中・15%・10% C07 − C06", round(P("strong", *m, "C07") - P("strong", *m, "C06"), 2), 2105630.77)
h = 255576.92307692
for sc, base in (("低・割増15%", 8977760), ("高・割増15%", -3368640)):
    check("1 F3", f"{sc}・10% C03 − C01 ＝ {base:,} − 保有費", round(P("now", sc, "10%", "C03") - P("now", sc, "10%", "C01"), 2),
          round(base - h, 2))

# 2 the holding cost against holding_sensitivity.csv
for pair, t in (("C01__C02", "now"), ("C01__C03", "now"), ("C02__C03", "now"), ("C06__C07", "strong")):
    b, a = pair.split("__")
    hs = pd.read_csv(os.path.join(WS, "compare", pair, "holding_sensitivity.csv"))
    for _, r in hs.iterrows():
        rt = f"{r['annual_rate'] * 100:g}%"
        g = T[t][(T[t]["scenario"] == "中・割増0%") & (T[t]["holding_rate_text"] == rt)].set_index("case")
        for side, c in (("base", b), ("alt", a)):
            for p in ("report", "warmup", "total"):
                check("2 保有費", f"{pair} {rt} {c} {p}", round(float(g.loc[c, f"H_{p}"]), 6),
                      round(float(r[f"H_{side}_{p}"]), 6))


def new_root(geo):
    for _ in range(5):
        try:
            r = tk.Tk()
            r.geometry(geo)
            return r
        except tk.TclError:
            time.sleep(0.2)
    raise RuntimeError("tk")


def shot(root, name):
    """Only the cockpit window, rendered by the window itself (Win32 PrintWindow): nothing else on the desktop
    is captured even when another window covers it, and the keyboard focus is not taken."""
    from ctypes import wintypes
    from PIL import Image
    root.update()
    time.sleep(0.5)
    root.update()
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(hwnd)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mdc, bmp)
    ok = u.PrintWindow(hwnd, mdc, 2)                      # PW_RENDERFULLCONTENT
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(hwnd, hdc)
    if not ok:
        raise RuntimeError("PrintWindow failed")
    Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).save(os.path.join(APX, "screens", name))


# 3 the screen against the CLI tables
for pair, t in (("C02__C03", "now"), ("C06__C07", "strong"), ("C01__C02", "now"), ("C01__C03", "now")):
    b, a = pair.split("__")
    root = new_root("1700x1000+10+10")
    scr = S.CompareScreen(root, WS, b, a)
    root.update()
    tb = scr.displayed_tables()
    ac = tb["money_after_cost"]
    check("3 画面", f"{pair} 行数（6 シナリオ × 4 率）", len(ac), 24)
    for i, r in ac.iterrows():
        sc, rt = r.iloc[0], r.iloc[1]
        pb, pa = P(t, sc, rt, b), P(t, sc, rt, a)
        g = T[t][(T[t]["scenario"] == sc) & (T[t]["holding_rate_text"] == rt)].set_index("case")
        for col, want in ((2, pa - pb), (3, pb), (4, pa), (5, g.loc[b, "weekly_amount"]), (6, g.loc[a, "weekly_amount"]),
                          (7, g.loc[b, "raise_cost"]), (8, g.loc[a, "raise_cost"]), (9, g.loc[b, "H_total"]),
                          (10, g.loc[a, "H_total"])):
            check("3 画面", f"{pair} {sc} {rt} 列 {ac.columns[col]}", r.iloc[col], V.fmt_yen(float(want)))
    summ = "\n".join(tb["summary"]["line"])
    sent = V.after_cost_sentence(V.comparison(WS, b, a)["money"]["after_cost"])[0]
    check("3 画面", f"{pair} 要点の一文", sent in summ, True)
    ten = [P(t, sc, "10%", a) - P(t, sc, "10%", b) for sc in T[t]["scenario"].unique()]
    check("3 画面", f"{pair} 一文の幅（10%）", f"{V.fmt_yen(min(ten))}〜{V.fmt_yen(max(ten))} 円" in sent, True)
    notes = "\n".join(tb["notes"]["note"])
    check("3 画面", f"{pair} ④ の注記", "確保費の週額は仮置き（GPT-MC 見積もり、採用額ではない）" in notes, True)
    if pair in ("C02__C03", "C06__C07"):
        scr.nb.select(scr.nb.index(scr.tab_money))
        shot(root, f"ac_{pair}_money.png")
        scr.money_scroll.yview_moveto(1.0)
        shot(root, f"ac_{pair}_money_lower.png")
        scr.money_scroll.yview_moveto(0.0)
    if pair == "C02__C03":
        scr.nb.select(0)
        shot(root, f"ac_{pair}_summary.png")
    root.destroy()

# 4 the width of (2): narrow windows, before (minimum off) and after
for w in (1700, 1100, 900):
    for label, mn in (("前（最小なし）", 0), ("後", V.MIN_INPUTS_WIDTH)):
        V.MIN_INPUTS_WIDTH = mn
        root = new_root(f"{w}x900+10+10")
        scr = S.CompareScreen(root, WS, "C02", "C03")
        root.update()
        scr.nb.select(scr.nb.index(scr.tab_money))
        root.update()
        width = scr.inputs_width()
        if mn:
            check("4 ② の幅", f"窓 {w} px：② の幅 {width} px ≥ {mn}", width >= mn, True)
        rows.append({"part": "4 ② の幅（記録）", "what": f"窓 {w} px {label}", "screen": width, "expected": "",
                     "match": True})
        if w == 1100:
            shot(root, f"inputs_width_{w}_{'before' if mn == 0 else 'after'}.png")
        root.destroy()
V.MIN_INPUTS_WIDTH = 360

df = pd.DataFrame(rows)
df.to_csv(os.path.join(APX, "ac_check.csv"), index=False, encoding="utf-8-sig")
print(f"{int(df['match'].sum())}/{len(df)} match")
print(df[~df["match"]].to_string())
print(df[df["part"] == "4 ② の幅（記録）"].to_string())
