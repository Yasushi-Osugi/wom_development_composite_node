# -*- coding: utf-8 -*-
"""
tests/test_allocation_hierarchical.py — 階層化単体格子（Phase 6-3）のテスト
================================================================================
`test_allocation_nmarket.py`（Phase 6-2a・平坦 N 市場の end-to-end）とは別ファイル。
本ファイルは階層化（`hierarchical_simplex.py`）専用——Phase 6-3 の階層化テストも
今後ここに追記していく。

正典: requests/Phase6_DesignMD_NMarketHierarchy.md §5（rev.6）
依頼: requests/Phase6-3_RequestLetter_to_CodeKun.md §V7
      requests/Phase6-3b_Addendum_to_CodeKun.md §A7（A1/A4 追加分）
      requests/Phase6-3c_Addendum_A9_to_CodeKun.md（A9-6 経路再構成 + A9-1〜A9-3）

**`cap_wk=800`（既定値）でテストを書かないこと**——限界市場が単独グループの JP に
落ち、内部比率解放の効果が 0 に退化する帯域である。本ファイルの主要な回帰テストは
`cap_wk=500` を使う（(2) 実測での期待値）。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import scan_surface, best_point
from wom.allocation.hierarchical_simplex import (
    aggregate_block, build_hierarchy, scan_hierarchical, hierarchy_gap,
)
from wom.allocation.merit_order import build_allocation_merit_order
from wom.allocation.transmission import CostBlock, Scenario

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")
OIL_DIR = os.path.join(os.path.dirname(__file__), "..",
                       "data", "sample", "oil-global-2027")

SC = Scenario(fx_usd=150.0, material_usd=6.0)


@pytest.fixture(scope="module")
def market_blocks():
    """既存の3市場ブロック（level="market"、既定・従来どおり）。"""
    return derive_cost_blocks(ALLOC_DIR)


@pytest.fixture(scope="module")
def region_blocks():
    """6地域ブロック（level="region"）。build_hierarchy() の検証にはこちらを使う。"""
    return derive_cost_blocks(ALLOC_DIR, level="region")


# ---------------------------------------------------------------------------
# V7.1 aggregate_block() が既存3市場ブロックを再現する（最重要）
# ---------------------------------------------------------------------------

def test_aggregate_block_reproduces_market_blocks(market_blocks, region_blocks):
    blocks3, tp3 = market_blocks
    blocks6, tp6 = region_blocks
    assert tp3 == pytest.approx(tp6, abs=1e-9)

    groups = {"JP": ["JP"], "US": ["US_W", "US_E"], "EU": ["FR", "BE", "NL"]}
    for market, regions in groups.items():
        agg = aggregate_block([blocks6[r] for r in regions])
        orig = blocks3[market]
        assert agg.usd == pytest.approx(orig.usd, abs=1e-9)
        assert agg.eur == pytest.approx(orig.eur, abs=1e-9)
        assert agg.jpy == pytest.approx(orig.jpy, abs=1e-9)
        assert agg.tariff_rate == pytest.approx(orig.tariff_rate, abs=1e-12)
        assert agg.demand_qty == orig.demand_qty
        assert agg.ccy == orig.ccy
        assert agg.price_local == orig.price_local


# ---------------------------------------------------------------------------
# V7.2 build_hierarchy() が market_group を再現する
# ---------------------------------------------------------------------------

def test_build_hierarchy_reproduces_market_group(region_blocks):
    blocks6, _tp = region_blocks
    tree = build_hierarchy(blocks6, ALLOC_DIR, max_children=3)

    def scan_needing_nodes(node):
        n = 1 if len(node["children"]) >= 2 else 0
        for c in node["children"]:
            n += scan_needing_nodes(c)
        return n

    # market_group（JP / US{US_W,US_E} / EU{FR,BE,NL}）と一致する分割
    groups = {frozenset(c["markets"]) for c in tree["children"]}
    assert groups == {frozenset(["JP"]), frozenset(["US_W", "US_E"]),
                      frozenset(["FR", "BE", "NL"])}
    assert tree["markets"] == ("JP", "US_W", "US_E", "FR", "BE", "NL")
    assert scan_needing_nodes(tree) == 3   # 実測での期待値（Request Letter 表）


# ---------------------------------------------------------------------------
# V7.3 双子分割の不変性（階層経由・最重要）
# ---------------------------------------------------------------------------

def test_hierarchy_split_invariance(market_blocks):
    """3市場を双子分割した6市場で、階層化の結果が3市場と一致すること。

    双子は経済条件が完全に同一（需要のみ折半）なので、分割は情報を増やして
    いない——木は build_hierarchy() ではなく手組みする（双子の市場名は
    sc_tree_master.csv / ga_market_aggregation.csv に存在しないため）。
    """
    from dataclasses import replace

    blocks3, tp = market_blocks
    cap_wk = 800.0

    surf3 = scan_surface(blocks3, tp, SC, cap_wk)
    flat3_best, _plateau = best_point(surf3)

    def _twin_leaf(name):
        return {"name": name, "children": [], "markets": (name,)}

    def _twin_group(name, a, b):
        return {"name": name, "children": [_twin_leaf(a), _twin_leaf(b)],
               "markets": (a, b)}

    blocks6 = {}
    for m in ("JP", "US", "EU"):
        src = blocks3[m]
        half = src.demand_qty / 2
        blocks6[f"{m}_a"] = replace(src, demand_qty=half)
        blocks6[f"{m}_b"] = replace(src, demand_qty=half)

    tree = {
        "name": "ALL",
        "children": [_twin_group("JP", "JP_a", "JP_b"),
                    _twin_group("US", "US_a", "US_b"),
                    _twin_group("EU", "EU_a", "EU_b")],
        "markets": ("JP_a", "JP_b", "US_a", "US_b", "EU_a", "EU_b"),
    }

    hier = scan_hierarchical(blocks6, tree, tp, SC, cap_wk)
    assert hier["profit"] == pytest.approx(flat3_best, abs=1.0)
    assert hier["nodes"] == 4          # ALL + JP + US + EU
    assert hier["points"] == 231 + 21 + 21 + 21


# ---------------------------------------------------------------------------
# V7.4 hierarchy_gap() は全シナリオで 0 以上
# ---------------------------------------------------------------------------

def test_hierarchy_gap_is_nonnegative(region_blocks):
    blocks6, tp = region_blocks
    tree = build_hierarchy(blocks6, ALLOC_DIR, max_children=3)
    for cap_wk in (400.0, 500.0, 650.0, 800.0, 1200.0):
        gap = hierarchy_gap(blocks6, tree, tp, SC, cap_wk)
        assert gap["hierarchy_gap"] >= -1e-6, f"cap_wk={cap_wk}"


# ---------------------------------------------------------------------------
# V7.5 cap_wk=500 の回帰値（実測固定）
# ---------------------------------------------------------------------------

def test_hierarchy_gap_regression_cap500(region_blocks):
    blocks6, tp = region_blocks
    tree = build_hierarchy(blocks6, ALLOC_DIR, max_children=3)
    gap = hierarchy_gap(blocks6, tree, tp, SC, cap_wk=500.0)

    assert gap["P_opt"] == pytest.approx(94_455_637.5, abs=1.0)
    assert gap["P_flat"] == pytest.approx(93_564_900.0, abs=1.0)
    assert gap["P_hier"] == pytest.approx(93_993_780.0, abs=1.0)
    assert gap["hierarchy_gap"] == pytest.approx(461_857.5, abs=1.0)
    assert gap["flat_grid_gap"] == pytest.approx(890_737.5, abs=1.0)
    assert gap["hier_minus_flat"] == pytest.approx(428_880.0, abs=1.0)
    assert gap["points_hier"] == 483
    assert gap["points_flat"] == 53_130


# ---------------------------------------------------------------------------
# V7.6 hier_minus_flat の符号は固定されない
# ---------------------------------------------------------------------------

def test_hier_minus_flat_has_no_fixed_sign(region_blocks):
    """階層化が平坦格子に勝つケースと負けるケースが両方あることを固定する
    （`gap_amt` のときと同じ落とし穴に対する杭）。"""
    blocks6, tp = region_blocks
    tree = build_hierarchy(blocks6, ALLOC_DIR, max_children=3)

    gap500 = hierarchy_gap(blocks6, tree, tp, SC, cap_wk=500.0)
    gap1200 = hierarchy_gap(blocks6, tree, tp, SC, cap_wk=1200.0)

    assert gap500["hier_minus_flat"] == pytest.approx(428_880.0, abs=1.0)
    assert gap500["hier_minus_flat"] > 0        # 階層化が勝つ

    assert gap1200["hier_minus_flat"] == pytest.approx(-1_840_657.5, abs=1.0)
    assert gap1200["hier_minus_flat"] < 0       # 階層化が負ける


# ---------------------------------------------------------------------------
# V7.7 内部比率解放の効果は限界市場の位置で決まる
# ---------------------------------------------------------------------------

def test_internal_ratio_freedom_only_when_cut_is_inside_group(market_blocks, region_blocks):
    blocks3, tp3 = market_blocks
    blocks6, tp6 = region_blocks

    mo3_500 = build_allocation_merit_order(blocks3, SC, cap_wk=500.0, transfer_price_usd=tp3)
    mo6_500 = build_allocation_merit_order(blocks6, SC, cap_wk=500.0, transfer_price_usd=tp6)
    assert mo6_500["profit"] - mo3_500["profit"] == pytest.approx(630_937.5, abs=1.0)
    assert mo6_500["marginal_market"] == "US_W"

    mo3_800 = build_allocation_merit_order(blocks3, SC, cap_wk=800.0, transfer_price_usd=tp3)
    mo6_800 = build_allocation_merit_order(blocks6, SC, cap_wk=800.0, transfer_price_usd=tp6)
    assert mo6_800["profit"] - mo3_800["profit"] == pytest.approx(0.0, abs=1.0)
    assert mo3_800["marginal_market"] == "JP"   # 単独グループ＝内部比率解放の余地なし


# ---------------------------------------------------------------------------
# V7.8 エラー系（4パターン）
# ---------------------------------------------------------------------------

def test_hierarchy_errors(region_blocks):
    blocks6, _tp = region_blocks

    # (a) 通貨が混在するグループを aggregate_block() に渡すと ValueError（C10）
    jpy_cb = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                       price_local=200, ccy="JPY", demand_qty=100)
    usd_cb = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                       price_local=200, ccy="USD", demand_qty=100)
    with pytest.raises(ValueError, match="currenc"):
        aggregate_block([jpy_cb, usd_cb])

    # (b) cliff を持つブロックが混ざるグループで ValueError
    cliff_cb = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.125,
                         price_local=200, ccy="JPY", demand_qty=100,
                         tariff_rate_preferential=0.0, preferential_threshold_lot=50)
    plain_cb = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                         price_local=200, ccy="JPY", demand_qty=100)
    with pytest.raises(ValueError, match="cliff"):
        aggregate_block([cliff_cb, plain_cb])

    # (c) max_children に収まらない木を要求すると ValueError（黙って割らない）
    with pytest.raises(ValueError):
        build_hierarchy(blocks6, ALLOC_DIR, max_children=1)

    # (d) 子1のノードで scan_surface() を呼んでいないこと（n_dim>=2 制約）。
    #     ルートの子が1つ（WRAP）でも例外なく通り、WRAP の2市場だけが
    #     走査ノードとしてカウントされることを確認する。
    single_child_tree = {
        "name": "ALL",
        "children": [{
            "name": "WRAP",
            "children": [{"name": "A", "children": [], "markets": ("A",)},
                        {"name": "B", "children": [], "markets": ("B",)}],
            "markets": ("A", "B"),
        }],
        "markets": ("A", "B"),
    }
    blocks2 = {
        "A": CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                       price_local=200, ccy="JPY", demand_qty=100),
        "B": CostBlock(usd=0, eur=0, jpy=120, tariff_rate=0.0,
                       price_local=220, ccy="JPY", demand_qty=100),
    }
    hier = scan_hierarchical(blocks2, single_child_tree, 0.0,
                             Scenario(fx_usd=150.0, material_usd=6.0), cap_wk=100.0)
    assert hier["nodes"] == 1                 # ALL（子1つ）は数えない。WRAP のみ
    assert set(hier["surfaces"].keys()) == {"WRAP"}


# ---------------------------------------------------------------------------
# A7.1 aggregate_block() は price_local を加重平均する（Addendum A1）
# ---------------------------------------------------------------------------

def test_aggregate_block_averages_price():
    """demand 3:1・price 100:200 -> 加重平均 125（例外にならない）。
    通貨混在は引き続き ValueError（維持）。"""
    cb_a = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                     price_local=100.0, ccy="JPY", demand_qty=300)
    cb_b = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                     price_local=200.0, ccy="JPY", demand_qty=100)
    agg = aggregate_block([cb_a, cb_b])
    assert agg.price_local == pytest.approx(125.0, abs=1e-9)
    assert agg.ccy == "JPY"
    assert agg.demand_qty == 400

    jpy_block = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                          price_local=200.0, ccy="JPY", demand_qty=100)
    usd_block = CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                          price_local=200.0, ccy="USD", demand_qty=100)
    with pytest.raises(ValueError, match="currenc"):
        aggregate_block([jpy_block, usd_block])


# ---------------------------------------------------------------------------
# A7.2 oil-global-2027: uom 絞り込み + 階層化の完走（Addendum A3/A4/A6）
# ---------------------------------------------------------------------------

def test_oil_uom_split_and_hierarchy():
    """uom を指定しないと2種類あることを理由に落ちる（A8: ga_market_aggregation.csv
    は21行すべてを持つので、tmp_path の合成 CSV は不要——実データに対して直接効く）。

    利益・誤差の回帰値は A9-6（経路の再構成 + 経路上の関税探索）実装後に実測した
    値である。A6/A8 時点の値（原価ゼロのモデルの上の数字）は破棄した。
    """
    with pytest.raises(ValueError, match="KL100KBBL"):
        derive_cost_blocks(OIL_DIR)

    blocks, tp = derive_cost_blocks(OIL_DIR, uom="KL")
    assert len(blocks) == 15

    tree = build_hierarchy(blocks, OIL_DIR)
    r = scan_hierarchical(blocks, tree, tp, SC, cap_wk=800.0)
    assert r["nodes"] == 10
    assert r["points"] == 1_050
    assert r["profit"] == pytest.approx(18_166_679_186.0, abs=1.0)   # A9-6後の実測値（新正典）

    g = hierarchy_gap(blocks, tree, tp, SC, cap_wk=800.0)
    assert g["P_flat"] is None                    # 13.9億点なので走らせない
    assert g["hierarchy_gap"] == pytest.approx(499_524_694.0, abs=1.0)   # A9-6後の実測値（新正典）


def test_oil_structure_only():
    """uom="KL100KBBL"（タンカー単位、Hormuz/RedSea）側は構造のみ確認する。
    `sc.material_usd`（kL スケールの量）をタンカーロットに適用することになる
    ため、利益・感度分析は意味を持たない（A9-3）——profit は assert しない。
    """
    b6, tp6 = derive_cost_blocks(OIL_DIR, uom="KL100KBBL")
    assert len(b6) == 6

    tree6 = build_hierarchy(b6, OIL_DIR)
    r6 = scan_hierarchical(b6, tree6, tp6, SC, cap_wk=8.0)
    assert r6["nodes"] == 3


# ---------------------------------------------------------------------------
# A9: 原価経路の再構成（A9-6）
# ---------------------------------------------------------------------------

def test_path_supplement_does_not_change_soysauce(market_blocks, region_blocks):
    """最重要: A9-6（経路の補完 + 経路上の関税探索）を適用しても、soysauce の
    原価ブロックは3市場・6地域とも全フィールド完全一致で1円も動かないこと。
    soysauce はコスト行が全区間に存在するため、outbound sc_tree からの補完は
    0本のはず（実測済み）。
    """
    blocks3, tp3 = market_blocks
    blocks6, tp6 = region_blocks

    expected3 = {
        "JP": (9.1, 0.0, 1725.0, 0.0, 3840.0, "JPY", 30150),
        "US": (15.65, 0.0, 1575.0, 0.125, 40.0, "USD", 35176),
        "EU": (14.6, 2.15, 1575.0, 0.08, 38.0, "EUR", 35175),
    }
    expected6 = {
        "JP": (9.1, 0.0, 1725.0, 0.0, 3840.0, "JPY", 30150),
        "US_W": (15.4, 0.0, 1575.0, 0.125, 40.0, "USD", 17588),
        "US_E": (15.9, 0.0, 1575.0, 0.125, 40.0, "USD", 17588),
        "FR": (14.6, 2.15, 1575.0, 0.08, 38.0, "EUR", 15075),
        "BE": (14.6, 2.15, 1575.0, 0.08, 38.0, "EUR", 10050),
        "NL": (14.6, 2.15, 1575.0, 0.08, 38.0, "EUR", 10050),
    }

    assert tp3 == pytest.approx(17.6, abs=1e-9)
    assert tp3 == tp6

    for m, exp in expected3.items():
        cb = blocks3[m]
        got = (cb.usd, cb.eur, cb.jpy, cb.tariff_rate, cb.price_local, cb.ccy, cb.demand_qty)
        assert got == exp, f"market {m}: {got} != {exp}"

    for m, exp in expected6.items():
        cb = blocks6[m]
        got = (cb.usd, cb.eur, cb.jpy, cb.tariff_rate, cb.price_local, cb.ccy, cb.demand_qty)
        assert got == exp, f"region {m}: {got} != {exp}"


def test_tariff_found_on_path_not_only_final_edge(market_blocks):
    """soysauce で、経路上探索（A9-6.2）でも従来と同じ関税率が引けること
    （JP=0.0 / US=0.125 / EU=0.08）。soysauce では課税点がもともと
    `DC_*->Rest_*`（leaf 直前の1本）なので、経路上探索に広げても
    ヒットは1件のまま・値も同じであることが最重要（Request Letter 実測どおり）。
    """
    blocks3, _tp = market_blocks
    assert blocks3["JP"].tariff_rate == pytest.approx(0.0, abs=1e-12)
    assert blocks3["US"].tariff_rate == pytest.approx(0.125, abs=1e-12)
    assert blocks3["EU"].tariff_rate == pytest.approx(0.08, abs=1e-12)


def _write_unreachable_model(model_dir) -> None:
    """derive_cost_blocks() が要求する9 CSV を持つ最小合成モデルを書く。
    leaf_out "Leaf_Broken" は上流エッジも outbound 親も持たない
    （ppc_edge_cost_rule.csv・sc_tree_master.csv のいずれにも上流情報が無い）。
    """
    def w(name, header, rows):
        with open(os.path.join(model_dir, name), "w", encoding="utf-8", newline="") as f:
            f.write(",".join(header) + "\n")
            for row in rows:
                f.write(",".join(str(v) for v in row) + "\n")

    w("sc_tree_master.csv",
      ["node_name", "parent_node", "product_name", "node_type", "side", "region"],
      [["Leaf_Broken", "", "Prod1", "leaf_out", "outbound", "R1"]])
    w("ga_market_aggregation.csv",
      ["market_group", "region", "market_node", "internal_ratio", "base_qty_lot", "note"],
      [["Leaf_Broken", "R1", "Leaf_Broken", "1.0000", "10", ""]])
    w("ppc_node_cost_rule.csv", ["node_id", "currency", "fixed_amount"], [])
    w("ppc_edge_cost_rule.csv", ["edge_id", "currency", "fixed_amount"], [])
    w("ppc_supplier_cost.csv", ["product_id", "week", "purchase_price"],
      [["Prod1", "2027-W01", "5"]])
    w("ppc_tariff_rule.csv", ["edge_id", "tariff_rate"], [])
    w("ppc_market_price.csv", ["market_node", "market_price", "currency"],
      [["Leaf_Broken", "100", "JPY"]])
    w("sku_master.csv", ["sku_id", "unit_cost", "uom"], [["Prod1", "1000", "EA"]])
    w("ppc_transfer_price_rule.csv", ["margin_rate"], [["0.1"]])


def test_unreachable_leaf_raises(tmp_path):
    """経路が無い leaf は既定（require_full_path=True）で ValueError。
    require_full_path=False なら通り、到達できなかった leaf が
    incomplete_paths（渡した out-list）に載ること（A9-6.3）。
    """
    model_dir = tmp_path / "unreachable"
    model_dir.mkdir()
    _write_unreachable_model(str(model_dir))

    with pytest.raises(ValueError, match="Leaf_Broken"):
        derive_cost_blocks(str(model_dir))

    incomplete: list = []
    blocks, _tp = derive_cost_blocks(str(model_dir), require_full_path=False,
                                     incomplete_paths=incomplete)
    assert incomplete == ["Leaf_Broken"]
    assert "Leaf_Broken" in blocks   # 続行はする（原価は mat_usd のみ）


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
