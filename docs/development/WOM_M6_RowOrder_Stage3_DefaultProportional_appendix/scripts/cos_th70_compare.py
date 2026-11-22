# -*- coding: utf-8 -*-
"""段 3 §5：化粧品の採用した配分の案（TH70）の配分済みの需要で、tail と新しい既定の計画を比べる。"""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "roworder_stage2", "scripts"))
import common as CM  # noqa
from golden_sweep3 import write_policy  # noqa
from tools import run_headless_from_folder as H  # noqa
B = os.path.join(CM.REPO, "output", "roworder_stage3", "cos_alloc")
res = {}
for tag, pol in (("tail", "tail"), ("default", None)):
    m = os.path.join(B, f"th70_{tag}")
    if not os.path.exists(m):
        shutil.copytree(os.path.join(B, "model_TH70"), m)
    write_policy(m, pol)
    snap = H.run(m, plugins_spec="HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin",
                 output_ppc_dir=os.path.join(m, "_ppc"), verbose=False, demand_file="demand_forecast_Q01.csv",
                 warmup_real_start="2027-W01")
    res[tag] = snap
keys = ("period", "products", "forward", "backward", "ppc", "psi")
diff = [k for k in keys if res["tail"].get(k) != res["default"].get(k)]
out = {"diff_keys": diff, "ppc_tail": res["tail"]["ppc"], "ppc_default": res["default"]["ppc"]}
json.dump(out, open(os.path.join(B, "th70_compare.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("diff keys:", diff)
