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
from wom.gui.s1_view_model import build_s1_view, format_market_name

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


# ---------------------------------------------------------------------------
# Phase 8-2: C1〜C6（大杉さんが実機で見つけた4件＋Claude君が測って見つけた2件）
# 正典: requests/Phase8-2_RequestLetter_to_CodeKun.md
# ---------------------------------------------------------------------------

def test_format_market_name_strips_retail_prefix():
    assert format_market_name("Retail_EU_DE") == "EU_DE"
    assert format_market_name("SP_Oil_Local") == "SP_Oil_Local"   # 前置き無しは無変更
    assert format_market_name("ALL") == "ALL"


# --- C1/C3: 結論行のラベル・要約・文字数 ------------------------------------

def test_headline_line1_is_labeled_and_collapsed():
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    line1 = v["headline"]["lines_ja"][0]

    assert line1.startswith("推奨配分（連続最適）")
    assert "（真の最適）" not in line1          # C1: ラベルは配分に付く。二重に付けない
    assert "Retail_" not in line1               # C3: 前置きは落とす
    # C3: 15市場を1行に収める。旧実装は365文字で右端が画面から溢れていた
    assert len(line1) < 150
    # C3: 配分ゼロの市場数を必ず出す（黙って落とさない）
    assert "配分ゼロ" in line1
    assert "6市場" in line1                     # oil の s1_base/cap800 で実測済み
    # 上位4市場 + 残りの要約が入っている
    assert "他5市場" in line1


def test_headline_full_allocation_ja_has_every_market():
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    full = v["headline"]["full_allocation_ja"]
    for m in markets_of_oil():
        assert format_market_name(m) in full


def markets_of_oil():
    from wom.gui.s1_view_model import _scenario_blocks
    from wom.allocation.grid import markets_of
    blocks, _tp, _sc = _scenario_blocks(OIL_DIR, "s1_base", "KL")
    return markets_of(blocks)


def test_headline_summary_never_drops_zero_markets_silently():
    """C3 の事故の再発防止: 配分ゼロの市場がいても『配分ゼロ なし』と誤魔化さない。"""
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    line1 = v["headline"]["lines_ja"][0]
    assert "配分ゼロ なし" not in line1

    # soysauce（3市場、全市場に配分あり）では「配分ゼロ なし」になる
    v2 = build_s1_view(ALLOC_DIR, scenario_id="s1_base", cap_wk=800.0)
    line1_2 = v2["headline"]["lines_ja"][0]
    assert "配分ゼロ なし" in line1_2


# --- C6: 整形の粗2件 ---------------------------------------------------------

def test_reversal_line_has_space_after_to():
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    lines = v["headline"]["lines_ja"]
    reversal_line = next((l for l in lines if l.startswith("ただし")), None)
    assert reversal_line is not None
    # 「〜を上回ると」のあとに半角スペースが入り、市場名が直後にくっつかない
    assert "と " in reversal_line
    assert "とRetail_" not in reversal_line
    assert "とEU_NL" not in reversal_line
    assert "Retail_" not in reversal_line       # C3 の整形もここに効いていること


def test_structural_gap_zero_has_no_numeric_suffix():
    """soysauce s1_base（cliff無し）は structural_optimality_gap == 0。
    修正前は『構造由来の取りこぼし +0万』と出ていた。"""
    v = build_s1_view(ALLOC_DIR, scenario_id="s1_base", cap_wk=800.0)
    assert v["profit_levels"]["structural_optimality_gap"] == pytest.approx(0.0, abs=1e-6)
    blob = "\n".join(v["level_notes_ja"]) + "\n" + v["headline"]["lines_ja"][1]
    assert "+0万" not in blob
    assert "構造由来の取りこぼしなし" in blob


# --- C2: 配分ゼロの枝は「意味の無い比率」を出さない --------------------------

def test_zero_branch_is_marked_unallocated():
    v_root = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    assert v_root["node"]["is_unallocated"] is False
    assert v_root["node"]["unallocated_message"] is None

    v_jpy_local = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                                node_path=("JPY", "SP_Oil_Local"))
    assert v_jpy_local["node"]["is_unallocated"] is False

    v_usd = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                          node_path=("USD",))
    assert v_usd["node"]["cap_lots"] == pytest.approx(0.0, abs=1e-6)
    assert v_usd["node"]["is_unallocated"] is True
    assert v_usd["node"]["unallocated_message"] is not None
    assert "0 lot" in v_usd["node"]["unallocated_message"]
    assert "ALL" in v_usd["node"]["unallocated_message"]     # 上位ノード = root
    assert "USD" in v_usd["node"]["unallocated_message"]     # ゼロなのはこのノード自身

    v_usd_local = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                                node_path=("USD", "SP_Oil_US_Local"))
    assert v_usd_local["node"]["is_unallocated"] is True
    assert "SP_Oil_US_Local" in v_usd_local["node"]["unallocated_message"]  # ゼロなのはこのノード
    assert "USD" in v_usd_local["node"]["unallocated_message"]   # 直近の親


def test_unallocated_message_ja_exact_text_and_naming():
    """検証フィードバック（大杉さん経由）: 名指しが1つずれていた——旧実装は
    『上位ノードで ALL の比率が0』のように書いており ALL 自身がゼロであるかの
    ように読めたが、実際に0なのは USD への配分。『上位ノード {parent} において
    {current} の配分が 0 のため』の形で current（このノード自身）を明示し、
    英数字の前後にスペースを入れる（C6 と同じ欠陥の再発防止）。文面を固定する。
    """
    v_usd = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                          node_path=("USD",))
    assert v_usd["node"]["unallocated_message"] == (
        "この枝には配分されていません（0 lot）。上位ノード ALL において "
        "USD の配分が 0 のため、ここから下の比率に意味はありません。"
    )

    v_usd_local = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                                node_path=("USD", "SP_Oil_US_Local"))
    assert v_usd_local["node"]["unallocated_message"] == (
        "この枝には配分されていません（0 lot）。上位ノード USD において "
        "SP_Oil_US_Local の配分が 0 のため、ここから下の比率に意味はありません。"
    )

    # 英数字（ノード名・数値）の前後に半角スペースがあること
    msg = v_usd["node"]["unallocated_message"]
    assert "ノードALL" not in msg and "ALLにおいて" not in msg
    assert "が0のため" not in msg


def test_unallocated_branch_does_not_apply_to_leaves():
    """葉自身が cap_lots==0 でも、is_unallocated 扱いにはしない（C4 の単位経済が優先）。"""
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                      node_path=("USD", "SP_Oil_US_Local", "Retail_US_TX"))
    assert v["node"]["children"] == []
    assert v["node"]["is_unallocated"] is False
    assert v["node"]["leaf_economics"] is not None


# ---------------------------------------------------------------------------
# Phase 8-2a: D1〜D3（大杉さんが実機で見つけた3件）
# 正典: requests/Phase8-2a_Addendum_to_CodeKun.md
# ---------------------------------------------------------------------------

# --- D1: 配分ゼロの枝を経由しても view model は葉まで到達できる ----------------

def test_d1_path_through_zero_branch_reaches_leaf_economics():
    """配分ゼロの枝を経由する node_path で build_s1_view() を呼ぶと、
    葉の leaf_economics が返る（rank==15 / shipped==0）——view model 側の
    経路は Phase 8-2 の時点で既に生きていた。塞いでいたのはパネルの
    `_render_children()` が `is_unallocated` のとき早期 return して子ノードの
    クリックリンクごと消していたことだけである（D1 の根本原因）。
    これが落ちたら「降りられない」が再発したということになる。
    """
    # 中間ノード（USD, SP_Oil_US_Local）は is_unallocated=True だが、
    # children は空ではない——降りる経路そのものは view model 上は生きている
    v_mid = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                          node_path=("USD", "SP_Oil_US_Local"))
    assert v_mid["node"]["is_unallocated"] is True
    assert v_mid["node"]["children"] != []

    v_leaf = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                           node_path=("USD", "SP_Oil_US_Local", "Retail_US_TX"))
    le = v_leaf["node"]["leaf_economics"]
    assert le is not None
    assert le["rank"] == 15
    assert le["shipped"] == pytest.approx(0.0, abs=1e-6)


# --- D2: 市場名と数字の間はノーブレークスペース -------------------------------

def test_market_share_uses_nbsp_between_name_and_number():
    """名前と数字の間が通常の半角スペースだと、wraplength 制約下の折返しで
    市場名と数字が分離しうる（実機で US_NY と 0 が分離して確認された）。
    区切りの ' / ' でしか折れないよう、ノーブレークスペース（\\u00a0）を使う。
    """
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    full = v["headline"]["full_allocation_ja"]
    line1 = v["headline"]["lines_ja"][0]

    assert " " in full
    assert " " in line1

    # 市場名（英数字・アンダースコア）の直後に半角スペース+数字が続く箇所が
    # 無いこと（あればそこが折返しで分離しうる）
    import re
    assert re.search(r"[A-Za-z_]+ \d", full) is None
    assert re.search(r"[A-Za-z_]+ \d", line1) is None


# --- C4: 葉ノードの単位経済 ---------------------------------------------------

def test_leaf_economics_kanto():
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                      node_path=("JPY", "SP_Oil_Local", "Retail_Local_KANTO"))
    le = v["node"]["leaf_economics"]
    assert le is not None
    assert le["ccy"] == "JPY"
    assert le["price_local"] == pytest.approx(170_000.0)
    assert le["rev"] == pytest.approx(170_000.0)
    assert le["cost"] == pytest.approx(111_000.0)
    assert le["margin"] == pytest.approx(59_000.0)
    assert le["margin_pct"] == pytest.approx(59_000.0 / 170_000.0, abs=1e-6)
    assert le["rank"] == 9
    assert le["n_markets"] == 15
    assert le["cap_lots"] == pytest.approx(5148.0, abs=1.0)
    assert le["shipped"] == pytest.approx(le["cap_lots"])   # 需要が能力を上回るので出荷=能力


def test_leaf_economics_us_tx_zero_shipped():
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                      node_path=("USD", "SP_Oil_US_Local", "Retail_US_TX"))
    le = v["node"]["leaf_economics"]
    assert le is not None
    assert le["ccy"] == "USD"
    assert le["price_local"] == pytest.approx(900.0)
    assert le["rev"] == pytest.approx(135_000.0)
    assert le["cost"] == pytest.approx(115_500.0)
    assert le["margin"] == pytest.approx(19_500.0)
    assert le["margin_pct"] == pytest.approx(19_500.0 / 135_000.0, abs=1e-6)
    assert le["rank"] == 15
    assert le["n_markets"] == 15
    assert le["shipped"] == pytest.approx(0.0, abs=1e-6)
    assert le["marginal_market"] == "Local_KANTO"     # Retail_ 前置き無し
    assert le["marginal_rank"] == 9


def test_leaf_economics_does_not_mix_local_and_jpy_currency():
    """マージン・売上は JPY 建て、price_local は現地通貨。混ぜると 14,191% のような
    非現実的な値になる（Request Letter §C4 の実例）。"""
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL",
                      node_path=("USD", "SP_Oil_US_Local", "Retail_US_TX"))
    le = v["node"]["leaf_economics"]
    wrong_pct = le["margin"] / le["price_local"]        # margin(JPY) / price_local(USD) を混ぜた誤り
    assert wrong_pct > 10.0                             # 明らかに非現実的（現実は14.4%程度）
    assert le["margin_pct"] < 1.0                       # 正しい方は妥当な範囲


# --- C5: 階層化の誤差の2項分解（恒等式2本） ----------------------------------

def test_hierarchy_gap_decomposes_into_mix_and_vol():
    v = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    pl = v["profit_levels"]

    assert pl["hierarchy_gap"] == pytest.approx(pl["hierarchy_mix"] + pl["hierarchy_vol"],
                                                abs=1.0)

    lam = v["merit_order"]["lambda"]
    assert pl["hierarchy_vol"] == pytest.approx(pl["hierarchy_unshipped"] * lam, abs=1.0)

    assert pl["hierarchy_marginal_market"] == v["merit_order"]["marginal_market"]


def test_hierarchy_unshipped_is_independent_of_material_price():
    """未出荷ロット数は原料単価を変えても変わらない（Phase 8-1b で原料単価を
    6.00→500.00 に直した前後で、物理的な取りこぼしは1ロットも変わっていない
    ことを確認する回帰）。"""
    v6 = build_s1_view(OIL_DIR, scenario_id="s1_base", cap_wk=800.0, uom="KL")
    # s1_base は既に mat=500（Phase 8-1b 適用済み）。ga_scenario_master.csv を
    # 経由せず Scenario を直接差し替えて mat=6 を再現する。
    import wom.gui.s1_view_model as _s1vm
    from dataclasses import replace
    from wom.allocation.grid import WEEKS
    from wom.allocation.hierarchical_simplex import build_hierarchy, scan_hierarchical
    from wom.allocation.merit_order import true_continuous_optimum

    blocks, tp, sc = _s1vm._scenario_blocks(OIL_DIR, "s1_base", "KL")
    sc6 = replace(sc, material_usd=6.0)
    tree = build_hierarchy(blocks, OIL_DIR, max_children=3)
    hier500 = scan_hierarchical(blocks, tree, tp, sc, 800.0)
    hier6 = scan_hierarchical(blocks, tree, tp, sc6, 800.0)
    to500 = true_continuous_optimum(blocks, sc, 800.0, transfer_price_usd=tp)
    to6 = true_continuous_optimum(blocks, sc6, 800.0, transfer_price_usd=tp)

    unshipped500 = sum(to500["q"].values()) - sum(hier500["q"].values())
    unshipped6 = sum(to6["q"].values()) - sum(hier6["q"].values())
    assert unshipped500 == pytest.approx(unshipped6, abs=1e-6)
    assert v6["profit_levels"]["hierarchy_unshipped"] == pytest.approx(unshipped500, abs=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
