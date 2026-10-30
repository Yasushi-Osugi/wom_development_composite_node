# -*- coding: utf-8 -*-
"""Copy the planning inputs of M0 to data/sample and record hashes (no README / _result)."""
import json, os, shutil, sys
sys.path.insert(0, os.getcwd())
from wom.lovem.observer import model_hashes
SRC = "output/bsseaf_cosmetics/M0"
DST = "data/sample/cosmetics-sg-th-2027-2029"
W = "output/bsseaf_cosmetics/register_work"
os.makedirs(DST, exist_ok=True)
names = [f for f in sorted(os.listdir(SRC)) if f.endswith(".csv")]
for f in names:
    shutil.copyfile(os.path.join(SRC, f), os.path.join(DST, f))
h = model_hashes(DST)
assert h == {f: v for f, v in model_hashes(SRC).items() if f.endswith(".csv")}
json.dump(h, open(os.path.join(W, "hashes_copied.json"), "w"), indent=1)
print(len(h), "files")
