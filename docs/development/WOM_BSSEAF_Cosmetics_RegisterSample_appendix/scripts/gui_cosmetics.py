# -*- coding: utf-8 -*-
"""S7: load the registered model in the real window, plan, wait for PPC, screenshot each main tab."""
import json, os, sys, time, traceback
sys.path.insert(0, os.getcwd())
OUT = "output/bsseaf_cosmetics/register_work/gui"
os.makedirs(OUT, exist_ok=True)
FOLDER = os.path.abspath("data/sample/cosmetics-sg-th-2027-2029")
from tkinter import filedialog, ttk
import wom.gui.app as A
from wom.lovem.viewer import _print_window
filedialog.askdirectory = lambda **k: FOLDER
app = A.WOMApp(); app.geometry("1536x824+0+0")
st = {"ppc": None}; rec = {"errors": []}
o = app._on_ppc_done
def done(kpi, run_id=""):
    r = o(kpi, run_id); st["ppc"] = run_id or "done"; rec["kpi"] = kpi if isinstance(kpi, dict) else str(kpi); return r
app._on_ppc_done = done
def nbs(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, ttk.Notebook): out.append(c)
        out += nbs(c)
    return out
def shot(n):
    app.update(); app.update_idletasks(); _print_window(int(app.wm_frame(), 16)).save(f"{OUT}/{n}.png")
def plugins():
    r = {}
    for k in dir(app):
        v = getattr(app, k, None)
        if "plugin" in k.lower() and isinstance(v, dict):
            try: r[k] = {str(n): (x.get() if hasattr(x, "get") else str(x)) for n, x in v.items()}
            except Exception: pass
    return r
def load():
    app._load_model_folder(); app.update(); rec["plugins_after_load"] = plugins(); shot("0_loaded")
    t = time.time(); app._run_planning_engine(); poll(t)
def poll(t):
    if st["ppc"] is None and time.time() - t < 600:
        app.after(400, lambda: poll(t)); return
    rec["ppc_done"] = st["ppc"]; rec["seconds"] = round(time.time() - t, 1)
    app.after(4000, tabs)
def tabs():
    try:
        top = nbs(app)[0]; rec["tabs"] = []
        ids = list(top.tabs()); idx = {"i": 0}
        def nxt():
            if idx["i"] >= len(ids):
                json.dump(rec, open(f"{OUT}/steps.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str); app.destroy(); return
            t = ids[idx["i"]]; name = top.tab(t, "text"); rec["tabs"].append(name); top.select(t); app.update()
            def s():
                shot(f"{idx['i']+1}_" + "".join(c for c in name if c.isalnum())); idx["i"] += 1; nxt()
            app.after(1800, s)
        nxt()
    except Exception:
        rec["errors"].append(traceback.format_exc()); app.destroy()
app.after(1500, load); app.mainloop(); print(json.dumps({k: v for k, v in rec.items() if k != "kpi"}, ensure_ascii=False, default=str)[:1500])
