# 週別の差（C09 − C04、2028-W04〜2028-W30 と ⑤ が出た週）

- 対象 COS_Cream × SG_EC。①〜⑤ の列（target_*・other_*）は要求週、費用・生産・在庫・試算利益は起きた週。
- cost_add は案の外の追加費用（円、P0 に入っていない）。profit_r2 は P0 の週の値（試算）。保有費は未設定。
- 「その他の週」と「計」まで足すと、どの列も計画全体の差になる。
- ⑤ が出た週のうち、どの列にも差の無い週はここでは省いた（CSV には全部ある。省いた週は「その他の週」に入れていない）。

| week | in_range | q5_week | cost_add | target_on_time | target_q5 | other_on_time | other_q5 | production_all | production_target_sku | inventory_lots | profit_r2 | profit_r2_target_market | profit_r2_other_markets | cost_planned_output_raise | cost_promo_campaign_add |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2028-W04 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W05 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W06 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W07 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W08 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W09 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W10 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W11 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W12 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W13 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W14 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W15 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W16 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W17 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W18 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W19 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W20 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W21 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W22 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 720 | 720 | 0 | 0 | 0 |
| 2028-W23 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2028-W24 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 720 | 720 | 0 | 0 | 0 |
| 2028-W25 | True | False | 0 | -1 | 0 | 0 | 0 | 0 | 0 | 1 | -195,084 | -195,084 | 0 | 0 | 0 |
| 2028-W26 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 2028-W27 | True | False | 0 | -1 | 0 | 0 | 0 | 0 | 0 | 2 | -195,084 | -195,084 | 0 | 0 | 0 |
| 2028-W28 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2028-W29 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2028-W30 | True | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| 2029-W13 | False | True | 0 | 0 | 0 | 1 | -1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 2029-W14 | False | True | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 2029-W15 | False | True | 0 | 1 | -1 | 0 | 0 | 0 | 0 | 0 | 195,084 | 195,084 | 0 | 0 | 0 |
| その他の週 | False | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 67 | 111,396 | -720 | 112,116 | 0 | 0 |
| 計 | False | False | 0 | -1 | -1 | 1 | -1 | 0 | 0 | 79 | -82,248 | -194,364 | 112,116 | 0 | 0 |

## 市場別の金額の差（報告期間 2027-W01〜2029-W52、円）

| sku_id | region | market | external_revenue_diff | external_cogs_group_diff | expense_diff | profit_r2_diff |
|---|---|---|---|---|---|---|
| COS_Cream | SG_Distributor | SG_Distributor | 171,120 | 48,900 | 10,104 | 112,116 |
| COS_Cream | SG_EC | SG_EC | -361,560 | -49,728 | -117,468 | -194,364 |
| COS_Cream | SG_Store | SG_Store | 0 | 0 | 0 | 0 |
| COS_Cream | TH_Distributor | TH_Distributor | 0 | 0 | 0 | 0 |
| COS_Serum | SG_Distributor | SG_Distributor | 0 | 0 | 0 | 0 |
| COS_Serum | SG_EC | SG_EC | 0 | 0 | 0 | 0 |
| COS_Serum | SG_Store | SG_Store | 0 | 0 | 0 | 0 |
| COS_Serum | TH_Distributor | TH_Distributor | 0 | 0 | 0 | 0 |
| * | * | 計 | -190,440 | -828 | -107,364 | -82,248 |

## 市場 × 要求年の差（差のある行だけ）

| sku_id | region | year | q1_base | on_time_base | delivered_base | q5_base | q1_alt | on_time_alt | delivered_alt | q5_alt | q1_diff | on_time_diff | delivered_diff | q5_diff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COS_Cream | SG_Distributor | 2029 | 260 | 216 | 216 | 44 | 260 | 217 | 217 | 43 | 0 | 1 | 1 | -1 |
| COS_Cream | SG_EC | 2028 | 110 | 110 | 110 | 0 | 108 | 108 | 108 | 0 | -2 | -2 | -2 | 0 |
| COS_Cream | SG_EC | 2029 | 104 | 87 | 87 | 17 | 104 | 88 | 88 | 16 | 0 | 1 | 1 | -1 |
