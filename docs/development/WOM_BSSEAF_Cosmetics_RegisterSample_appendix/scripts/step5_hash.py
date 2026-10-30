# -*- coding: utf-8 -*-
"""S5: snapshot / compare the registered folder (file list + sha256). usage: step5_hash.py save|cmp <tag>"""
import json, os, sys
sys.path.insert(0, os.getcwd())
from wom.lovem.observer import model_hashes
M = "data/sample/cosmetics-sg-th-2027-2029"
P = "output/bsseaf_cosmetics/register_work/hashes_s5.json"
h = model_hashes(M)
if sys.argv[1] == "save":
    json.dump(h, open(P, "w"), indent=1); print("saved", len(h))
else:
    a = json.load(open(P))
    print(sys.argv[2], "same" if a == h else "DIFF", len(h))
