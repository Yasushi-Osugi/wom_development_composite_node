# -*- coding: utf-8 -*-
"""
tools/lovem_handoff.py — package a LOVEM run folder for the independent checker (request §6).

    python -m tools.lovem_handoff --run output/lovem/ev-thailand-2026/run_A \
        --out output/lovem/handoff_ev-thailand-2026

Creates <out>/ with
  run/                 the run folder (all A1 files, incl. q12.json = Q12 evidence)
  DATA_DICTIONARY.md   docs/development/lovem/DATA_DICTIONARY.md
  REPRODUCE.md         commands, SHA and conditions that recreate the run folder
  SHA256SUMS.txt       SHA-256 of every file above (paths relative to <out>)
and <out>.zip next to it. Nothing in the run folder is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


REPRO = """# 再実行の手順（LOVEM 段階 A の run フォルダ）

- run_id：`{run_id}`
- code_sha：`{code_sha}`（dirty={dirty}、dirty_diff_hash=`{dirty_diff_hash}`、対象 `wom` `tools` `data`）
- モデル：`{model_dir}`（各ファイルの SHA-256 は run/manifest.json の `model_hashes`）
- プラグイン：{plugins}
- 環境：{env}

## コマンド（リポジトリ直下、Windows / PowerShell）

```powershell
git checkout {code_sha}
python -m tools.lovem_observe --model-dir {model_dir} --out <新しいフォルダ> --q12 --se2-compare-sha 4ed2f14
```

- 同じ code_sha・同じ未 commit 差分（dirty_diff_hash）・同じモデル（model_hashes）なら、`manifest.json` の
  `created_at`・`timing_s` を除き、全ファイルがバイト単位で同じになる（段階 A 報告書 §7 で2回実行して確認）。
- `q12.json`：観測 OFF／ON の指紋と一致判定（Q12 の証拠）。
- `se2_case.json` の `comparison_run` は、`git archive 4ed2f14` を一時フォルダへ展開して同じプラグインで実行した結果。

## 照合の拠り所

- `DATA_DICTIONARY.md`（全ファイルの列・None と 0・ハッシュ正規化・identity_basis・証拠区分）
- `SHA256SUMS.txt`（このフォルダの全ファイル）
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dictionary", default="docs/development/lovem/DATA_DICTIONARY.md")
    a = ap.parse_args(argv)
    if os.path.exists(a.out):
        print(f"[lovem] output exists: {a.out}", file=sys.stderr)
        return 2
    man = json.load(open(os.path.join(a.run, "manifest.json"), encoding="utf-8"))
    os.makedirs(a.out)
    shutil.copytree(a.run, os.path.join(a.out, "run"))
    shutil.copy2(a.dictionary, os.path.join(a.out, "DATA_DICTIONARY.md"))
    env = man["environment"]
    with open(os.path.join(a.out, "REPRODUCE.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(REPRO.format(run_id=man["run_id"], code_sha=man["code_sha"], dirty=man["dirty"],
                             dirty_diff_hash=man["dirty_diff_hash"], model_dir=man["model_dir"],
                             plugins=", ".join(man["plugins"]),
                             env=", ".join(f"{k} {v}" for k, v in env.items())))
    lines = []
    for root, _d, files in os.walk(a.out):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, a.out).replace("\\", "/")
            lines.append(f"{_sha(p)}  {rel}")
    lines.sort(key=lambda s: s.split("  ", 1)[1])
    with open(os.path.join(a.out, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    zpath = a.out.rstrip("/\\") + ".zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _d, files in os.walk(a.out):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, os.path.dirname(os.path.abspath(a.out))))
    print(f"[lovem] handoff: {a.out}  ({len(lines)} files)  zip: {zpath} ({os.path.getsize(zpath)/1e6:.1f} MB)"
          f"  sha256(zip)={_sha(zpath)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
