import sys, time
sys.path.insert(0, r"C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF")
from wom.cockpit import case_runner as R
WS = r"C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF\output\cockpit_m5\cos"
pairs = [p.split("__") for p in sys.argv[1:]]
for b, a in pairs:
    t = time.perf_counter()
    rec = R.compare_cases(WS, b, a)
    print(b, a, rec["state"], rec["P0_base"], rec["P0_alt"], round(time.perf_counter() - t, 1), "s")
