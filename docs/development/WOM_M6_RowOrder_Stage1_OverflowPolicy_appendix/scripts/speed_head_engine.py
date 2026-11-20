# 変更前（着手時の HEAD）の backward_planner.py で smartphone の tail を測る（比較の基準）。
import os, sys, importlib.util, json
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
spec = importlib.util.spec_from_file_location("wom.engine.backward_planner", sys.argv[1])
mod = importlib.util.module_from_spec(spec); sys.modules["wom.engine.backward_planner"] = mod
spec.loader.exec_module(mod)
import wom.engine as we; we.backward_planner = mod
spec2 = importlib.util.spec_from_file_location("sp", os.path.join(os.path.dirname(__file__), "speed_smartphone.py"))
m = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m)
m.OUT = os.path.join(m.OUT, "head_engine"); os.makedirs(m.OUT, exist_ok=True)
m.one("tail")
