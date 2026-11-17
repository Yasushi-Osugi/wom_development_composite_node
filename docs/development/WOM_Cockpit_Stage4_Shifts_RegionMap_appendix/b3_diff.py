# 段 4（シフト・地域）B3：比較の出力を、前の出力と共通の列で照らし合わせる
import glob, os, sys
import pandas as pd
pairs = [("output/cockpit_cases/stage1", "output/cockpit_step4b/cos_stage1"),
         ("output/cockpit_step4/cos", "output/cockpit_step4b/cos88")]
rows = []
for old, new in pairs:
    for d in sorted(os.listdir(os.path.join(old, "compare"))):
        for f in sorted(glob.glob(os.path.join(old, "compare", d, "*.csv"))):
            fn = os.path.basename(f)
            g = os.path.join(new, "compare", d, fn)
            if not os.path.exists(g):
                rows.append((old, d, fn, "missing in new", "")); continue
            a = pd.read_csv(f, dtype=str, keep_default_na=False)
            b = pd.read_csv(g, dtype=str, keep_default_na=False)
            common = [c for c in a.columns if c in b.columns]
            added = [c for c in b.columns if c not in a.columns]
            same = len(a) == len(b) and a[common].reset_index(drop=True).equals(b[common].reset_index(drop=True))
            rows.append((old, d, fn, "same" if same else f"DIFFERENT ({len(a)} vs {len(b)} rows)", ",".join(added)))
t = pd.DataFrame(rows, columns=["workspace", "pair", "file", "result", "added_columns"])
t.to_csv("output/cockpit_step4b/b3_diff.csv", index=False)
print(t["result"].value_counts().to_string())
print(t[t["result"] != "same"].to_string(index=False))
print(t[t["added_columns"] != ""][["pair", "file", "added_columns"]].drop_duplicates(["file", "added_columns"]).to_string(index=False))
