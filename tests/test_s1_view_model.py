# -*- coding: utf-8 -*-
"""
tests/test_s1_view_model.py — S1 Allocate 画面の view model（Phase 8-1）
================================================================================
正典: requests/Phase8-1_RequestLetter_to_CodeKun.md V4

**tkinter はテストしない。** `wom/gui/s1_view_model.py` の純関数だけを検証する
（`wom/gui/allocation_panel.py` は並べるだけなので、ここでは対象外）。
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import wom.gui.s1_view_model as s1vm
from wom.gui.s1_view_model import build_s1_view

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SAMPLE_DIR = os.path.join(REPO_ROOT, "data", "sample")

ALLOC_DIR = os.path.join(SAMPLE_DIR, "soysauce-jpy-2027-alloc")
OIL_DIR = os.path.join(SAMPLE_DIR, "oil-global-2027")

# oil-global-2027（uom="KL"）の実測済みノード構成（Phase 8-1 実測）。
# 木の形自体は Phase 6-3b で確定済み（10ノード・1,050点・line6/triangle4）。
OIL_NODE_PATHS = [
    (),
    ("JPY",),
    ("JPY", "SP_Oil_Local"),
    ("JPY", "SP_Oil_Import"),
    ("EUR",),
    ("EUR", "SP_Oil_EU_Local"),
    ("EUR", "SP_Oil_EU_Import"),
    ("USD",),
    ("USD", "SP_Oil_US_Local"),
    ("USD", "SP_Oil_US_Import"),
]


# ---------------------------------------------------------------------------
# V4.1
# ---------------------------------------------------------------------------

def test_view_triangle_mode_soysauce():
    v = build_s1_view(ALLOC_DIR, scenario_id="s1_base", cap_wk=800.0)
    assert v["mode"] == "triangle"
    assert v["breadcrumb"] == []
    assert v["headline"]["profit"] == pytest.approx(135_529_822.5, abs=1.0)
    assert v["headline"]["profit_source"] == "P_opt"


# ---------------------------------------------------------------------------
# V4.2
# ---------------------------------------------------------------------------

def test_levels_sorted_desc():
    v = build_s1_view(ALLOC_DIR, scenario_id="s1_base", cap_wk=800.0)
    values = [e["value"] for e in v["levels"]]
    assert values == sorted(values, reverse=True)
    by_name = {e["name"]: e for e in v["levels"]}
    assert by_name["P_opt"]["value"] >= by_name["P_greedy"]["value"]
    assert by_name["P_opt"]["value"] >= by_name["P_grid"]["value"]

    # s9_fta_cliff（cap_wk=500）: P_greedy が最下段に落ち highlight == True
    v2 = build_s1_view(ALLOC_DIR, scenario_id="s9_fta_cliff", cap_wk=500.0)
    values2 = [e["value"] for e in v2["levels"]]
    assert values2 == sorted(values2, reverse=True)
    greedy_entry = next(e for e in v2["levels"] if e["name"] == "P_greedy")
    assert greedy_entry is v2["levels"][-1] or greedy_entry == v2["levels"][-1]
    assert greedy_entry["highlight"] is True
    # highlight されるのは P_greedy だけ
    assert all(not e["highlight"] for e in v2["levels"] if e["name"] != "P_greedy")


# ---------------------------------------------------------------------------
# V4.3（最重要）
# ---------------------------------------------------------------------------

def test_headline_is_invariant_across_nodes():
    node_paths = [(), ("JPY",), ("JPY", "SP_Oil_Local")]
    views = [build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                           node_path=p) for p in node_paths]

    headlines = [v["headline"] for v in views]
    levels = [v["levels"] for v in views]
    assert all(h == headlines[0] for h in headlines)
    assert all(l == levels[0] for l in levels)

    # breadcrumb / node は変わる（降りたことが確認できないと、このテスト自体が無意味になる）
    assert views[0]["breadcrumb"] != views[1]["breadcrumb"]
    assert views[1]["breadcrumb"] != views[2]["breadcrumb"]
    assert views[0]["node"]["name"] != views[1]["node"]["name"]


# ---------------------------------------------------------------------------
# V4.4
# ---------------------------------------------------------------------------

def test_plot_kind_by_child_count():
    kinds = []
    for p in OIL_NODE_PATHS:
        v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                          node_path=p)
        n_children = len(v["node"]["children"])
        if n_children == 3:
            assert v["node"]["plot_kind"] == "triangle"
        elif n_children == 2:
            assert v["node"]["plot_kind"] == "line"
        kinds.append(v["node"]["plot_kind"])

    assert kinds.count("line") == 6
    assert kinds.count("triangle") == 4


# ---------------------------------------------------------------------------
# V4.5
# ---------------------------------------------------------------------------

def _walk_strings(obj):
    if isinstance(obj, dict):
        for k, val in obj.items():
            yield str(k)
            yield from _walk_strings(val)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk_strings(item)
    else:
        yield str(obj)


def test_no_flat_comparison_in_view():
    banned = ("hier_minus_flat", "平坦", "格子全数", "P_flat")
    for model_dir, scenario_id, cap_wk, kw in [
        (ALLOC_DIR, "s1_base", 800.0, {}),
        (OIL_DIR, "s1_base", 800.0, {"uom": "KL"}),
    ]:
        v = build_s1_view(model_dir, scenario_id=scenario_id, cap_wk=cap_wk, **kw)
        blob = "\n".join(_walk_strings(v))
        for word in banned:
            assert word not in blob, f"{word!r} leaked into view ({model_dir})"


# ---------------------------------------------------------------------------
# V4.6
# ---------------------------------------------------------------------------

def test_surface_is_not_recomputed():
    # triangle モード（N=3）: scan_surface が1回、scan_hierarchical は0回
    with mock.patch.object(s1vm, "scan_surface", wraps=s1vm.scan_surface) as m_surf:
        build_s1_view(ALLOC_DIR, scenario_id="s1_base", cap_wk=800.0)
        assert m_surf.call_count == 1

    # hierarchy モード（N>=4）: scan_hierarchical が1回、scan_surface は0回
    with mock.patch.object(s1vm, "scan_hierarchical", wraps=s1vm.scan_hierarchical) as m_hier, \
         mock.patch.object(s1vm, "scan_surface", wraps=s1vm.scan_surface) as m_surf2:
        build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                     node_path=("JPY", "SP_Oil_Local"))
        assert m_hier.call_count == 1
        assert m_surf2.call_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
