import os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
from tools import run_headless_from_folder as H
from wom.plugins.selection import read_recommended_plugins
D = "output/cockpit_m6/r0_order_test"
for tag, m in (("order_changed", D + "/model"), ("original_C02", "output/cockpit_m6/soy/C02/model")):
    H.run(m, plugins_spec=",".join(read_recommended_plugins(m)), output_ppc_dir=f"{D}/{tag}/ppc", verbose=False,
          ppc=False, flow_check_dir=f"{D}/{tag}/flow_check")
