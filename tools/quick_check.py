# -*- coding: utf-8 -*-
"""
tools/quick_check.py — run the test tiers (RequestLetter_QuickCheckTests)

    python -m tools.quick_check --smoke                      # ~3 min, any time during work
    python -m tools.quick_check --area rice,capacity         # the areas you touched
    python -m tools.quick_check --golden rice-japan-2027-2028
    python -m tools.quick_check --changed                    # pick areas from the changed files
    python -m tools.quick_check --changed wom/ppc/ppc_kpi.py data/sample/bom-test-2026/sku_master.csv
    python -m tools.quick_check --full                       # once per request letter, at the end
    python -m tools.quick_check --area rice --dry-run        # print the pytest commands only

pytest runs one command at a time (never in parallel: golden warm-up writes
CSVs and parallel runs collide), with PYTHONDONTWRITEBYTECODE=1 and
-p no:cacheprovider. The last line says tier, areas, passed/failed/skipped, time.

Which test file belongs to which area is in tests/conftest.py (AREAS).
Which changed path selects which area is PATH_RULES below; tests/README.md
shows the same table.
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import os
import re
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN_DIR = os.path.join(REPO, "tests", "golden")

# Protected core (CLAUDE.md "禁足ルール").
PROTECTED_CORE = (
    "wom/engine/backward_planner.py",
    "wom/engine/forward_planner.py",
    "wom/engine/plan_copy.py",
    "wom/model/plan_node.py",
    "wom/model/sc_tree.py",
    "wom/engine/push_pull.py",
)

# Changed path -> areas. First matching rule wins (order matters).
# "smoke" in the areas means: run the smoke tier as well.
PATH_RULES = (
    # (glob,                                   areas)
    ("wom/capacity_layer/rice_*",              ("rice", "capacity")),
    ("wom/plugins/rice_*",                     ("rice", "capacity")),
    ("tools/rice_*",                           ("rice",)),
    ("wom/capacity_layer/*",                   ("capacity",)),
    ("wom/plugins/capacity_layer.py",          ("capacity", "plugins")),
    ("wom/plugins/*",                          ("plugins",)),
    ("wom/engine/holiday_calendar_plugin.py",  ("plugins", "core")),
    ("wom/engine/decouple_optimizer.py",       ("plugins",)),
    ("wom/engine/money.py",                    ("ppc",)),
    ("wom/engine/landed_cost.py",              ("ppc",)),
    ("wom/ppc/*",                              ("ppc",)),
    ("wom/valuechain/*",                       ("ppc",)),
    ("tools/valuechain_*",                     ("ppc",)),
    ("wom/allocation/*",                       ("allocation",)),
    ("wom/visualization/*",                    ("allocation",)),
    ("tools/*allocation*",                     ("allocation",)),
    ("tools/plot_merit_order_suite.py",        ("allocation",)),
    ("wom/lovem/*",                            ("lovem",)),
    ("tools/lovem_*",                          ("lovem",)),
    ("wom/gui/*",                              ("gui",)),
    ("wom/cockpit/*",                          ("gui", "allocation")),
    ("wom/worldmap_ne/*",                      ("worldmap",)),
    ("tools/*worldmap*",                       ("worldmap",)),
    ("wom/engine/*",                           ("smoke", "core")),
    ("wom/model/*",                            ("smoke", "core")),
    ("wom/planning_state/*",                   ("core",)),
    ("wom/data/*",                             ("smoke", "core")),
    ("tools/run_headless_from_folder.py",      ("smoke", "core", "golden")),
    ("tools/quick_check.py",                   ("public",)),
    ("tests/conftest.py",                      ("public",)),
    ("pytest.ini",                             ("public",)),
    ("tests/golden/*",                         ("golden",)),
    ("docs/*",                                 ("public",)),
    ("requests/*",                             ("public",)),
    ("*.md",                                   ("public",)),
)
# data/sample/<model>/... -> that model's golden, plus these areas for some models.
MODEL_AREAS = {"rice-japan-2027-2028": ("rice",)}


def _areas_table():
    spec = importlib.util.spec_from_file_location("_wom_tests_conftest", os.path.join(REPO, "tests", "conftest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.AREA_NAMES, mod.AREAS


def golden_models():
    return sorted(f[:-5] for f in os.listdir(GOLDEN_DIR) if f.endswith(".json"))


def golden_ids(models):
    ids = []
    legacy = os.path.join(GOLDEN_DIR, "legacy")
    for m in models:
        if not os.path.exists(os.path.join(GOLDEN_DIR, m + ".json")):
            raise SystemExit(f"[quick_check] no golden for model '{m}'. Known: {', '.join(golden_models())}")
        ids.append(f"tests/test_golden.py::test_golden_matches[{m}]")
        if os.path.exists(os.path.join(legacy, m + ".json")):
            ids.append(f"tests/test_golden.py::test_legacy_golden_matches[{m}]")
    return ids


def changed_paths():
    out = set()
    for cmd in (["git", "--no-optional-locks", "status", "--porcelain"],
                ["git", "--no-optional-locks", "diff", "--name-only", "HEAD"]):
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        for line in r.stdout.splitlines():
            if not line.strip():
                continue
            p = line[3:] if cmd[2] == "status" else line
            p = p.split(" -> ")[-1].strip().strip('"')
            out.add(p)
    return sorted(out)


def plan_from_paths(paths):
    """Return (areas, golden models, notes) chosen by PATH_RULES for the given paths."""
    _names, table = _areas_table()
    areas, models, notes = set(), set(), []
    protected = False
    for raw in paths:
        p = raw.replace("\\", "/").lstrip("./")
        if p in PROTECTED_CORE:
            protected = True
            areas |= {"smoke", "core", "golden"}
            continue
        m = re.match(r"data/sample/([^/]+)/", p)
        if m:
            models.add(m.group(1))
            areas |= set(MODEL_AREAS.get(m.group(1), ()))
            continue
        m = re.match(r"tests/(test_[^/]+\.py)$", p)
        if m:
            got = table.get(m.group(1))
            if got:
                areas |= set(got)
            else:
                areas |= {"smoke", "public"}
                notes.append(f"{p}: not in tests/conftest.py AREAS (add one line)")
            continue
        for pat, ar in PATH_RULES:
            if fnmatch.fnmatch(p, pat):
                areas |= set(ar)
                break
        else:
            areas.add("smoke")
            notes.append(f"{p}: no rule in PATH_RULES -> smoke only")
    known = set(golden_models())
    for mdl in sorted(models):
        if mdl not in known:
            notes.append(f"data/sample/{mdl}: no golden for this model -> smoke")
            areas.add("smoke")
    models &= known
    if models:
        areas.add("smoke")
    if protected:
        notes.insert(0, "PROTECTED CORE changed: run --full and the 3-layer tests "
                        "(Unit / Integration / E2E golden) before review (CLAUDE.md 禁足ルール)")
    return areas, models, notes


def _base():
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def commands(areas, models, full=False):
    """pytest argument lists, run one after another."""
    base = _base()
    if full:
        return [base + ["tests/"]]
    cmds = []
    if areas:
        expr = " or ".join(sorted(areas))
        cmds.append(base + ["tests/", "-m", expr])
    if models and "golden" not in areas:
        cmds.append(base + golden_ids(sorted(models)))
    return cmds


_COUNT = re.compile(r"(\d+) (passed|failed|skipped|error|errors|deselected|xfailed|xpassed)")


def run(cmds, label, dry):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    total = {}
    t0 = time.time()
    rc = 0
    for c in cmds:
        print("[quick_check] " + " ".join(f'"{a}"' if " " in a else a for a in c), flush=True)
        if dry:
            continue
        p = subprocess.Popen(c, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        last = ""
        for line in p.stdout:
            sys.stdout.write(line)
            if _COUNT.search(line):
                last = line
        p.wait()
        rc = rc or (p.returncode if p.returncode not in (5,) else 0)
        for n, k in _COUNT.findall(last):
            k = "error" if k == "errors" else k
            total[k] = total.get(k, 0) + int(n)
    if dry:
        print(f"[quick_check] DRY RUN | {label}")
        return 0
    s = " ".join(f"{k}={total.get(k, 0)}" for k in ("passed", "failed", "skipped", "error"))
    print(f"[quick_check] {label} | {s} | {time.time() - t0:.0f} s | {'OK' if rc == 0 else 'FAILED'}")
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the test tiers (smoke / area / golden / changed / full).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true")
    g.add_argument("--area", help="comma-separated areas")
    g.add_argument("--golden", help="comma-separated model names (tests/golden/<model>.json)")
    g.add_argument("--changed", nargs="*", metavar="PATH",
                   help="pick areas from changed files (git status + git diff HEAD), or from the PATHs given")
    g.add_argument("--full", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the pytest commands only")
    a = ap.parse_args(argv)
    names, _table = _areas_table()

    if a.full:
        return run(commands(set(), set(), full=True), "tier=full", a.dry_run)
    if a.smoke:
        return run(commands({"smoke"}, set()), "tier=smoke", a.dry_run)
    if a.area:
        areas = {x.strip() for x in a.area.split(",") if x.strip()}
        bad = areas - set(names) - {"smoke", "slow"}
        if bad:
            raise SystemExit(f"[quick_check] unknown area(s): {', '.join(sorted(bad))}. Known: {', '.join(names)}")
        return run(commands(areas, set()), "tier=area areas=" + ",".join(sorted(areas)), a.dry_run)
    if a.golden:
        models = [x.strip() for x in a.golden.split(",") if x.strip()]
        return run([_base() + golden_ids(models)], "tier=golden models=" + ",".join(models), a.dry_run)
    paths = a.changed if a.changed else changed_paths()
    if not paths:
        print("[quick_check] no changed files -> smoke")
        return run(commands({"smoke"}, set()), "tier=changed(none)->smoke", a.dry_run)
    areas, models, notes = plan_from_paths(paths)
    print("[quick_check] changed: " + ", ".join(paths))
    for n in notes:
        print("[quick_check] NOTE: " + n)
    label = ("tier=changed areas=" + ",".join(sorted(areas))
             + (" golden=" + ",".join(sorted(models)) if models else ""))
    return run(commands(areas, models), label, a.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
