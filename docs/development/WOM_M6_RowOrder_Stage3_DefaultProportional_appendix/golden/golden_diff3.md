# 段 3：新しい既定（proportional_week）で golden を回した結果

| 種類 | モデル | golden と一致 | 違う欄 |
|---|---|---|---|
| default | Cookie-jp-2026 | 一致 | — |
| default | apparel-global-2028-2029 | 一致 | — |
| default | apparel-us-2026 | 一致 | — |
| default | bom-test-2026 | 一致 | — |
| default | cosmetics-sg-th-2027-2029 | 一致 | — |
| default | ev-europe-2026 | 一致 | — |
| default | ev-thailand-2026 | 一致 | — |
| default | ev-thailand-2026_update | 一致 | — |
| default | oil-global-2027 | **違う** | ppc, psi |
| default | rice-japan-2027-2028 | 一致 | — |
| default | smartphone-global-2026-2029 | **違う** | ppc, psi |
| default | smartx-2027-2029 | 一致 | — |
| default | soysauce-eu-2027 | 一致 | — |
| default | soysauce-jpy-2027-alloc | **違う** | ppc, psi |
| default | soysauce-jpy-2027 | 一致 | — |
| default | soysauce-us-2027 | 一致 | — |
| legacy | Cookie-jp-2026 | 一致 | — |
| legacy | ev-thailand-2026 | 一致 | — |
| legacy | soysauce-jpy-2027 | 一致 | — |

## oil-global-2027

- 違う欄：ppc, psi。段 2 の proportional_week と snapshot が同じ：True
- 合計（tail → 既定）：総納品 191,029 → 191,029、当週 191,029 → 191,029、遅配 0 → 0、期末の注文残 29 → 29（需要 191,058）
- 計画の前に落ちた lot（past_due）：29 → 29（うち工場の能力で 4 → 4）
- series_md5 などが変わったノード（3）：Gasoline_Local_RedSea/Retail_Local_R_KANTO, Gasoline_Local_RedSea/Retail_Local_R_KANSAI, Gasoline_Local_RedSea/Retail_Local_R_CHUBU

| PPC の項目 | tail | 既定 |
|---|---|---|
| total_lots | 1399 | 1408 |
| revenue_base | 1571097940180.0 | 1571457940180.0 |
| gross_profit_base | 552339674893.0 | 552699674893.0 |
| gross_margin_pct | 0.351563 | 0.351711 |
| trust_event_count | 733 | 742 |

| 製品 | 市場 | 需要 | 当週 tail → 既定 | 遅配 tail → 既定 | 期末の注文残 tail → 既定 |
|---|---|---|---|---|---|
| Gasoline_Local_RedSea | Retail_Local_R_KANTO | 246 | 246 → 232 | 0 → 0 | 0 → 14 |
| Gasoline_Local_RedSea | Retail_Local_R_KANSAI | 124 | 115 → 116 | 0 → 0 | 9 → 8 |
| Gasoline_Local_RedSea | Retail_Local_R_CHUBU | 124 | 104 → 117 | 0 → 0 | 20 → 7 |

## smartphone-global-2026-2029

- 違う欄：ppc, psi。段 2 の proportional_week と snapshot が同じ：True
- 合計（tail → 既定）：総納品 414,090 → 414,090、当週 414,090 → 414,090、遅配 0 → 0、期末の注文残 56,834 → 56,834（需要 470,924）
- 計画の前に落ちた lot（past_due）：56,834 → 56,834（うち工場の能力で 44,134 → 44,134）
- series_md5 などが変わったノード（12）：Phone16/SP_Phone16, Phone16/DC_EMEA, Phone16/Retail_EMEA, Phone16/DC_APAC, Phone16/Retail_APAC, Phone15/SP_Phone15, Phone15/DC_AMER_i15, Phone15/Retail_AMER_i15, Phone15/DC_EMEA_i15, Phone15/Retail_EMEA_i15, Phone15/DC_APAC_i15, Phone15/Retail_APAC_i15

| PPC の項目 | tail | 既定 |
|---|---|---|
| total_lots | 1127 | 1170 |
| revenue_base | 64101413473420.0 | 63634388846970.0 |
| cost_base | 37695124383917.75 | 37419216408499.32 |
| gross_profit_base | 26406289089502.25 | 26215172438470.68 |
| gross_margin_pct | 0.411946 | 0.411965 |
| tariff_base | 4720497327977.75 | 4462834176730.33 |

| 製品 | 市場 | 需要 | 当週 tail → 既定 | 遅配 tail → 既定 | 期末の注文残 tail → 既定 |
|---|---|---|---|---|---|
| Phone16 | Retail_EMEA | 70,736 | 70,736 → 55,626 | 0 → 0 | 0 → 15,110 |
| Phone16 | Retail_APAC | 80,184 | 48,397 → 63,507 | 0 → 0 | 31,787 → 16,677 |
| Phone15 | Retail_AMER_i15 | 34,580 | 34,580 → 24,644 | 0 → 0 | 0 → 9,936 |
| Phone15 | Retail_EMEA_i15 | 24,204 | 18,926 → 17,041 | 0 → 0 | 5,278 → 7,163 |
| Phone15 | Retail_APAC_i15 | 27,664 | 7,895 → 19,716 | 0 → 0 | 19,769 → 7,948 |

## soysauce-jpy-2027-alloc

- 違う欄：ppc, psi。段 2 の proportional_week と snapshot が同じ：True
- 合計（tail → 既定）：総納品 75,291 → 75,291、当週 75,291 → 75,291、遅配 0 → 0、期末の注文残 25,210 → 25,210（需要 100,501）
- 計画の前に落ちた lot（past_due）：24,524 → 24,524（うち工場の能力で 20,408 → 20,408）
- series_md5 などが変わったノード（12）：Soy_Sauce/SP_Soy, Soy_Sauce/FG_WH_Noda, Soy_Sauce/DC_US_SF, Soy_Sauce/Rest_US_West, Soy_Sauce/DC_US_NY, Soy_Sauce/Rest_US_East, Soy_Sauce/DC_JP, Soy_Sauce/Rest_JP, Soy_Sauce/DC_EU_RTM, Soy_Sauce/Rest_FR, Soy_Sauce/Rest_BE, Soy_Sauce/Rest_NL

| PPC の項目 | tail | 既定 |
|---|---|---|
| total_lots | 464 | 607 |
| revenue_base | 427957532.0 | 451673778.0 |
| cost_base | 316318290.04 | 326360886.13 |
| gross_profit_base | 111639241.96 | 125312891.87 |
| gross_margin_pct | 0.260865 | 0.277441 |
| tariff_base | 15670707.44 | 15921024.98 |

| 製品 | 市場 | 需要 | 当週 tail → 既定 | 遅配 tail → 既定 | 期末の注文残 tail → 既定 |
|---|---|---|---|---|---|
| Soy_Sauce | Rest_US_West | 17,588 | 17,063 → 12,981 | 0 → 0 | 525 → 4,607 |
| Soy_Sauce | Rest_US_East | 17,588 | 17,063 → 12,842 | 0 → 0 | 525 → 4,746 |
| Soy_Sauce | Rest_JP | 30,150 | 29,250 → 23,784 | 0 → 0 | 900 → 6,366 |
| Soy_Sauce | Rest_FR | 15,075 | 6,615 → 11,007 | 0 → 0 | 8,460 → 4,068 |
| Soy_Sauce | Rest_BE | 10,050 | 2,650 → 7,339 | 0 → 0 | 7,400 → 2,711 |
| Soy_Sauce | Rest_NL | 10,050 | 2,650 → 7,338 | 0 → 0 | 7,400 → 2,712 |
