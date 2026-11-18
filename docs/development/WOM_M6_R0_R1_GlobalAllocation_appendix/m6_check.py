# -*- coding: utf-8 -*-
"""到達点 6 §3.4: the screen's supply table (②÷①, ④÷①, ④÷②) and the rule / result sentence against
tools/period_fulfillment.py; screenshots of the cockpit window only (Win32 PrintWindow).

    python output/cockpit_m6/m6_check.py
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

WS = os.path.join("output", "cockpit_m6", "soy")
APX = os.path.join("docs", "development", "WOM_M6_R0_R1_GlobalAllocation_appendix")
os.makedirs(os.path.join(APX, "screens"), exist_ok=True)
F = pd.concat([pd.read_csv(os.path.join(WS, "fulfillment", d, "period_fulfillment.csv")) for d in ("C01", "C02_C05")])
F = F[F["region"] != "*"].drop_duplicates(["case", "region"]).set_index(["case", "region"])
rows = []


def check(part, what, got, want):
    rows.append({"part": part, "what": what, "screen": got, "expected": want, "match": got == want})


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


for b, a in (("C01", "C02"), ("C02", "C03"), ("C03", "C04"), ("C03", "C05")):
    root = new_root("1700x1000+10+10")
    scr = S.CompareScreen(root, WS, b, a)
    root.update()
    t = scr.displayed_tables()["supply_totals"]
    sv = scr.cmp["supply"]
    tot = sv["totals"].reset_index(drop=True)
    check("画面", f"{b}__{a} 行数", len(t), len(tot))
    for i, r in tot.iterrows():
        s = t.iloc[i]
        f = F.loc[(r["case"], r["region"])]
        tag = f"{b}__{a} {r['case']} {r['region']}"
        for head, col in (("需要", "q1"), ("供給の対象", "q2"), ("当週", "on_time"), ("早出し", "early"), ("遅配", "late"),
                          ("配分後の未充足（⑤）", "q5")):
            check("画面", f"{tag} {head}", str(s[head]), str(int(f[col])))
        un = str(s["未配分（③）"])
        check("画面", f"{tag} 未配分（③）", un, str(int(f["q3"])) if un != "—" else "—")
        for head, col in (("②÷①（配分の規則）", "r21"), ("④÷①（納品の結果）", "r41"), ("④÷②", "r42")):
            check("画面", f"{tag} {head}", s[head], V.fmt_pct(float(f[col])))
    summ = "\n".join(scr.displayed_tables()["summary"]["line"])
    sent = V.rule_and_result(sv, b, a)
    check("画面", f"{b}__{a} 要点の一文", sent in summ, True)
    for side, cid in (("基準", b), ("相手", a)):
        g = F.loc[cid]
        lo, hi = g["r41"].idxmin(), g["r41"].idxmax()
        mlo = f"Soy_Sauce:{g.loc[lo, 'market']}（{lo}）"
        check("画面", f"{b}__{a} {cid} 結果の幅（道具の最小・最大の値、最小の市場）",
              f"{side} {cid} は {V.fmt_pct(g.loc[lo, 'r41'])}（{mlo}）〜{V.fmt_pct(g.loc[hi, 'r41'])}（" in sent, True)
    scr.nb.select(scr.nb.index(scr.tab_supply))
    shot(root, f"m6_{b}__{a}_supply.png")
    scr.supply_scroll.yview_moveto(1.0)
    shot(root, f"m6_{b}__{a}_supply_lower.png")
    scr.supply_scroll.yview_moveto(0.0)
    scr.nb.select(0)
    shot(root, f"m6_{b}__{a}_summary.png")
    root.destroy()

df = pd.DataFrame(rows)
df.to_csv(os.path.join(APX, "m6_screen_check.csv"), index=False, encoding="utf-8-sig")
print(f"{int(df['match'].sum())}/{len(df)} match")
print(df[~df["match"]].head(20).to_string())
