# -*- coding: utf-8 -*-
"""
tests/test_allocation_material_invariant.py — 原料単価の不変条件（Phase 8-1b）
================================================================================
正典: requests/Phase8-1b_Addendum_MaterialPrice_to_CodeKun.md §4 B4。

`data/sample/*/ga_scenario_master.csv` の base シナリオ（scenario_id 最初の行）が
宣言する `material_price_usd` と、`derive_cost_blocks()` が実データ
（`ppc_supplier_cost.csv` 経由）から導出する `material_usd_base` は、
**現状コード上どこにも照合されていない**（letter §3.1）。ga_scenario_master.csv 側の
`Scenario.material_usd` は regime_map の原料軸を掃くための独立値であり、
`unit_pnl()` の `usd_eff = cb.usd − cb.material_usd_base + sc.material_usd` で
両者が完全に相殺するため、base シナリオの値が実データと食い違っていても
A系統の結果には一切影響しない。

本テストは、この2ファイルを繋ぐ唯一の橋である。新しいサンプルケースを
足した人が原料単価を書き忘れたら（他モデルの既定値がそのまま複写されたら）、
ここで落ちる。

uom が複数あるモデル（oil-global-2027）は、主 uom（"KL"）だけを検査する。
"KL100KBBL"（タンカー単位、Hormuz/RedSea）は sc.material_usd をタンカーロットに
適用することになるため利益・感度分析には意味を持たない（Phase 6-3c Addendum
A9-3 で申し送り済み）——これを**無言で素通りさせない**ため、既知の不一致として
明示的に検証する（§5.1 参照。もし将来 uom 列が追加され値が一致するようになれば、
このテストが失敗して更新を促す）。
"""
import csv
import glob
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.cost_block import derive_cost_blocks

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample")

# モデルが複数 uom を持つ場合、不変条件を検証する「主 uom」を明示する
# （derive_cost_blocks(uom=None) が単一 uom で通るモデルはここに載せない）。
PRIMARY_UOM = {
    "oil-global-2027": "KL",
}

# 主 uom 以外に存在する uom で、材料単価の一致検証が構造的に意味を持たない
# ことが既に申し送り済みのもの（黙って skip するのではなく、既知の不一致として
# 明示的に assert する。CLAUDE.md Phase 8-1b §5.1 / Phase 6-3c Addendum A9-3）。
KNOWN_OUT_OF_SCOPE_UOM = {
    "oil-global-2027": "KL100KBBL",
}


def _model_dirs_with_ga_scenario_master():
    pattern = os.path.join(SAMPLE_DIR, "*", "ga_scenario_master.csv")
    dirs = sorted(os.path.dirname(p) for p in glob.glob(pattern))
    return dirs


def _base_material_price_usd(model_dir: str) -> float:
    path = os.path.join(model_dir, "ga_scenario_master.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, f"{path}: no rows"
    return float(rows[0]["material_price_usd"])


MODEL_DIRS = _model_dirs_with_ga_scenario_master()


def test_at_least_soysauce_and_oil_present():
    """掃き出し範囲の固定（letter §3.6）: サンプルケースが増減したら気づけるように。"""
    names = sorted(os.path.basename(d) for d in MODEL_DIRS)
    assert "soysauce-jpy-2027-alloc" in names
    assert "oil-global-2027" in names


@pytest.mark.parametrize("model_dir", MODEL_DIRS, ids=[os.path.basename(d) for d in MODEL_DIRS])
def test_base_material_price_matches_derived_cost_block(model_dir):
    """base シナリオ（行0）の material_price_usd == derive_cost_blocks() の material_usd_base。

    oil-global-2027 を 500.00 から元の 6.00（soysauce の値）に戻すと、
    このテストは 500.00 != 6.00 で確実に落ちる（Phase 8-1b 完了条件）。
    """
    declared = _base_material_price_usd(model_dir)

    name = os.path.basename(model_dir)
    uom = PRIMARY_UOM.get(name)
    blocks, _tp = derive_cost_blocks(model_dir, uom=uom)

    bases = {round(cb.material_usd_base, 6) for cb in blocks.values()}
    assert len(bases) == 1, (
        f"{name}: material_usd_base is not uniform across markets: {bases}"
    )
    derived = next(iter(bases))

    assert declared == pytest.approx(derived, abs=1e-6), (
        f"{name}: ga_scenario_master.csv base material_price_usd={declared} "
        f"!= derive_cost_blocks(uom={uom!r}).material_usd_base={derived}"
    )


def test_oil_kl100kbbl_is_a_known_unverified_mismatch():
    """§5.1: KL100KBBL を無言で通さない。

    真値はタンカー1隻あたり 7,800,000 USD 相当（Phase 6-3c Addendum A9-3）だが、
    ga_scenario_master.csv は uom 列を持たず1モデル1値しか表現できないため、
    現状は必ず主 uom（KL, 500.00）の値と比較され不一致になる。これは既知の
    スコープ外事項であり、バグではない——ただし「気づかれずに一致してしまう」
    ことがあれば、それは仕様前提が変わった合図なので、このテストを更新すること。
    """
    name = "oil-global-2027"
    model_dir = os.path.join(SAMPLE_DIR, name)
    uom = KNOWN_OUT_OF_SCOPE_UOM[name]

    declared = _base_material_price_usd(model_dir)   # 500.00（主 uom=KL の値）
    blocks, _tp = derive_cost_blocks(model_dir, uom=uom)
    bases = {round(cb.material_usd_base, 6) for cb in blocks.values()}
    assert len(bases) == 1
    derived = next(iter(bases))

    # 既知の不一致（500.00 の KL 単価 vs タンカーロットの実原価）であることを
    # 明示的に確認する。一致したら仕様前提が変わっているのでこのテストを見直すこと。
    assert declared != pytest.approx(derived, abs=1e-6), (
        f"{name}: uom={uom!r} の material_usd_base が主 uom の宣言値と一致した。"
        f"KL100KBBL の単位変換が実装された可能性がある——本テストと "
        f"PRIMARY_UOM/KNOWN_OUT_OF_SCOPE_UOM の扱いを見直すこと。"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
