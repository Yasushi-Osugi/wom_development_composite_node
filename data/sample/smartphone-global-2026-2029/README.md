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
