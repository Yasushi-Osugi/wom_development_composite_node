# smartphone-global-2026-2029

Smartphone の世界のサプライチェーン（Phone15・16・17）。台湾のウェーハ・SoC → 中国／インドの組立
（EMS_A）→ 地域の DC（ロサンゼルス・アムステルダム・シンガポール）→ 地域の販売。

## 販売の拠点の地点（代表の地点（仮）、RequestLetter_WorldMap_ActualFlows §1.1、2026-10-01）

`Retail_*` の 9 拠点は、地域全体の販売をまとめたノードで、1 つの場所を持たない。World Map に描くため、
各地域の**代表の都市**を `node_master.csv` の緯度・経度に入れた。**代表の地点（仮）**であり、
販売の場所を表すものではない。

| 拠点 | 地域 | 代表の地点（仮） | 緯度 | 経度 |
|---|---|---|---:|---:|
| `Retail_AMER`・`Retail_AMER_i15`・`Retail_AMER_i17` | AMER | New York | 40.7128 | −74.0060 |
| `Retail_EMEA`・`Retail_EMEA_i15`・`Retail_EMEA_i17` | EMEA | London | 51.5074 | −0.1278 |
| `Retail_APAC`・`Retail_APAC_i15`・`Retail_APAC_i17` | APAC | Tokyo | 35.6762 | 139.6503 |

- 地域の DC（ロサンゼルス・アムステルダム・シンガポール）とは別の都市にして、DC → 販売の区間が
  地図で線として見えるようにした。
- 変更前の 9 行は、列が 1 つずれていた（`sku_id` の列に地域、`region` の列に説明が入っていた）。
  緯度・経度を入れるのと同時に、`sku_id`（Phone16／15／17）・`region`・`description` を正しい列に直した。
- `node_type` は `retail` のまま（World Map の色の表に無いので、計画の木の役割 leaf_out の色＝市場の赤で描く）。
- `node_master.csv` を読むのは World Map だけで、計画・PPC には影響しない。

## Phone15・17 の DC と工場（2026-10、設計担当の提案どおり）

`sc_tree_master.csv` にあって `node_master.csv` に行の無かった `DC_AMER_i15`・`DC_EMEA_i15`・`DC_APAC_i15`・
`DC_AMER_i17`・`DC_EMEA_i17`・`DC_APAC_i17`・`EMS_A_CN_i15`・`EMS_A_CN_i17` の 8 行を足した。座標は
Phone16 の同じ名前の拠点（`DC_AMER`・`DC_EMEA`・`DC_APAC`・`EMS_A_CN`）と同じ（説明に「… と同じ地点」）。
名前から推測する規則にはせず、行として書いた。

## PPC（粗利の試算）の限界（RequestLetter_MoneyBase_Smartx_CostFix E、2026-11-17）

- このモデルの PPC は、計画の木ではなく**固定の経路**で計算する（`wom/ppc/ppc_engine.py` の
  `build_smartphone_global_vs_paths`：EMS_A_CN → SP_Phone16 → 市場。Phone15・17 も同じ形）。supply point を DC として扱う。
- そのため計画の木の DC（DC_AMER など）・台湾の工場（Foundry_A_TW）・インドの工場（EMS_A_IN）を通らない。
  - DC の作業費（`ppc_node_cost_rule.csv` の DC の conversion_cost。費用の約 0.86%）が計上されない。
  - 計画では米州の Phone16 をインド組立から出すが、PPC は中国組立（EMS_A_CN）の仕入値・組立費と、中国発の関税で計上する。
  - これらの規則の行（38 行）は一度も引かれず、PPC の警告（`ppc_warnings.csv` の `unused_rule_row`）に出る。
- 直さない（大杉さんの判断、2026-11-15）。計画の木の経路で金額を見るなら、後継の **smartx-2027-2029** を使う。
  調査：`docs/development/WOM_MoneyBase_UnappliedRules_Survey_Report.md`。
