# G5 シンガポール向けCIFの海上運賃と在庫原価｜業務定義案 v0.1

2026-11-12 ・ GPT-MC ・ 採否待ち

日本本社の `WH_JP_Released` からシンガポール販社の `DC_SG` へ売るクリーム24個（`COS_Cream`、1ロット）を対象とする。`E_JP` が負担する外部運賃と、`E_SG` が運賃込みの価格で取得する在庫を照合し、グループ連結で外部運賃が残る場所を確認する。G4との比較は[共通照合表](WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md)を参照。

## 1. 現行サンプルの前提とM0の観測

| 区分 | 確認した内容 |
| --- | --- |
| 現行サンプルの前提 | `E_JP → E_SG` の法人間取引。金額仮定書はCIFシンガポールとし、日本本社が海上運賃を負担して価格に含める。クリームの法人間価格は5,000円／個、区間費用は60円／個。金額仮定書の60円は輸出通関を含む海上費用。 |
| M0の報告結果（T15） | Value Chainは区間費用60円／個を法人間価格に上乗せし、`E_SG` の取得原価に3,367行、80,808個 × 60円＝4,848,480円を計上。報告開始前週末にはそのうち4,320円が3ロットの在庫に残り、報告最終週末の残額は0円。 |
| 観測結果の照合範囲 | M0報告はPPCとValue Chainの運賃合計が一致したとしている。提案の受入には、`E_JP` の外部負担、`E_SG` の取得額、週末の連結在庫をロットごとに照合する。 |

[金額仮定書（本文 v0.2） §§2.3・4.1・4.3・5.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md) ・ [M0報告書 §6・T15](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L491)

## 2. 負担法人、支払先、支配移転（提案）

| 判断 | 代表例の前提 |
| --- | --- |
| 契約上の負担 | `E_JP` が運送を手配し、外部運賃60円／個を負担する。船積み時に当該ロットへの費用帰属と支払義務が確定する契約を置く。 |
| 実際の支払の確認 | `E_JP` から外部の運送業者への支払と置く。費用の根拠は運送契約・船積記録・外部請求明細。支払週は決済記録から追い、今回の例では未指定。`E_SG` から `E_JP` への法人間代金は別の債務。 |
| 価格への包含 | 5,000円／個に対象の海上運賃を含む。`E_SG` の法人間取得額は120,000円、同じ運賃の別建て加算は0円。1,440円は内包分を照合するために使う。 |
| 支配の移転 | WOMのD-2を適用し、この取引の出荷を船積みと定め、その時点で `E_SG` に支配が移る契約を試行条件とする。輸送中の在庫原価も `E_SG` に帰属する。DC受入で所在を振り替える。 |

ICCのCIFの解説では、売り手は指定仕向港までの運送・保険を手配して費用を負担し、危険は船積み時に移転する。在庫と売上の認識に用いる支配移転は、上記のD-2の採用条件と契約証拠で判断する。今回の金額照合は法人間価格と海上運賃に限る。保険の額・包含、60円の実際の費目内訳、指定港や契約書の条件は未確認。追加の取得費用は対象範囲と包含が確認できた時点で反映する。[ICCのCIF解説](https://academy.iccwbo.org/incoterms/article/incoterms-2020-cip-or-cif/) ・ [Value Chain設計 v1.0 §0.1 D-2・D-3、§2.3](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L11-L67)

## 3. 法人別と連結の原価（提案）

`C` はこのロットの `E_JP` が保有する船積み前の原価（対象運賃を加える前、JPY）。この例ではグループも同じ原価を持つと置く。`C` の金額は未指定。

| 視点 | 計上方法 |
| --- | --- |
| `E_JP` の法人別（V2） | 船積み週に外部運賃1,440円を把握し、同じ週の法人間売上120,000円に対応する直接原価に一度反映。ロットの売上原価は `C + 1,440円`。運賃部分は1件として元の外部請求へ遡れるようにする。 |
| `E_SG` の法人別（V2） | 船積み週に輸送中在庫120,000円を取得。受入は所在の振替で、追加の取得額は0円。外部販売時に売上原価120,000円へ振り替える。 |
| グループ連結（V3） | 法人間の売買と、在庫に含まれる内部利益 `120,000円 − (C + 1,440円)` を消去する。未販売中の在庫は `C + 1,440円`、外部販売時の売上原価も `C + 1,440円`。外部運賃部分は在庫から売上原価へ一度移り、この例の独立した期間費用は0円。 |

直接帰属する運賃を在庫原価に含め、販売時に売上原価へ振り替える判断はWOMのD-3に従う。連結で内部取引を消去した後の金額は、検証で照合する期待値とする。[Value Chain設計 v1.0 §§0.1・1・2.3](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L11-L67) ・ [IAS 2 §§11・34（EU公表版）](https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX%3A02023R1803-20260308) ・ [IFRS 10 B86(c)](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2023/issued/part-a/ifrs-10-consolidated-financial-statements.pdf?bypass=on)

## 4. 代表1ロットの週別期待結果

24個 × 5,000円＝**120,000円**、24個 × 60円＝**1,440円**。依頼書の例に沿って、2028-W28船積み・負担確定、W29受入、W31外部販売（24個すべて）と置く。件数は表で指定した業務上の明細の数とする。

| ISO週・事象 | `E_JP`（V2） | `E_SG`（V2） | グループ（V3） |
| --- | --- | --- | --- |
| 2028-W28 船積み・支配移転 | 法人間売上120,000円・1件。売上原価 `C + 1,440円`・1件（外部運賃部分1,440円・1件）。 | 輸送中在庫の取得120,000円・1件。別建て運賃0件。 | 輸送中在庫 `C + 1,440円`。外部売上原価0件。 |
| 2028-W29 DC受入 | この取引の追加運賃・原価0件。 | DC在庫120,000円へ所在を振替。新規取得・運賃の追加は各0件。 | DC在庫 `C + 1,440円`。追加運賃0件。 |
| 2028-W30末 未販売 | この取引の追加計上0件。 | 在庫120,000円。外部売上原価0件。 | 在庫 `C + 1,440円`。外部売上原価0件。 |
| 2028-W31 外部販売 | この取引の追加計上0件。 | 売上原価120,000円・1件。在庫0円。 | 売上原価 `C + 1,440円`・1件（運賃分1,440円を含む）。在庫0円。 |

受入時に支配が移る契約を採用する場合は、W28末の輸送中在庫を `E_JP` が `C + 1,440円` で保有し、法人間売上・対応する売上原価と `E_SG` の取得をW29に計上する。外部運賃の負担はW28の船積みを根拠に確定する。連結ではW30末の在庫とW31売上原価がともに `C + 1,440円` になる。

## 5. 価格が運賃別の場合との照合

| 条件 | 外部運賃1,440円の負担 | `E_SG` の取得額 | 連結原価 |
| --- | --- | ---: | ---: |
| 採用候補のCIF。運賃込み5,000円／個 | `E_JP` が運送業者へ。`E_SG` の追加0円。 | **120,000円** | `C + 1,440円` |
| 対照例。運賃別の品代5,000円／個と、買い手が負担する別契約 | `E_SG` が運送業者へ。取得に直接帰属する1,440円を一度算入。`E_JP` の外部運賃0件。 | **121,440円** | `C + 1,440円` |
| 照合で検出するケース。運賃込み5,000円／個に同じ1,440円を重ねる | 外部費用と同じ費用を `E_SG` へ重ねている。 | 121,440円（CIF条件で1,440円過大） | 外部費用1件と照合して原因を特定。 |

対照例で負担確定・支配移転が同じW28なら、`E_SG` はその週に121,440円の輸送中在庫を認識し、W31に同額を売上原価へ振り替える。追加の請求明細があれば、法人間価格への包含と最終負担を契約・請求明細で確認する。包含や金額が不明な費用の追加は判定保留とし、確認済みの法人間価格は保持する。

区間・`Lot_ID`・元の出荷記録を起点に、法人間請求と運送業者の請求明細を結び付ける。費目と対象区間、配賦した数量・金額、負担法人、包含の根拠を照合する。外部請求明細の当該ロット配賦分が1,440円・1件であることを、再取込、受入、外部販売、連結の各段階で元明細に遡って確認する。

## 6. 読取基準と設計への引継ぎ

入力とM0報告の参照版は依頼書指定の `9eefff8fee8d3807f6f5adffb254fd53b6f92e2d`。開発台帳 §4、M0報告書 §6・T15、金額仮定書（本文 v0.2） §§2.3・4.1・4.3・5.1、Value Chain設計 v1.0 §§0.1・1・2、下記サンプル入力を読んだ。G2反映後の `ccf2b40` では Start Here §7・G2報告の完了記録を確認した。採用後の設計ではG2反映後の版を基準とする。下記のサンプル入力は指定版と一致する。

[開発台帳 §4](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/requests/BSSEAF_Roadmap_Loop_Ledger_v0.1.md#L67-L81) ・ [法人割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L15-L20) ・ [数量設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/planning_config.csv#L4) ・ [Value Chain価格](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv#L2-L3) ・ [区間費用](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_edge_cost_rule.csv#L6-L9) ・ [関税設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_tariff_rule.csv#L6-L9) ・ [G2反映後のStart Here §7](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/ccf2b40c3dddbbaa60312b8ad2b80d2a064bca35/docs/WOM_Start_Here.md#L203) ・ [指定版との比較](https://github.com/Yasushi-Osugi/wom_development_composite_node/compare/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d...ccf2b40c3dddbbaa60312b8ad2b80d2a064bca35)

## 7. 大杉さんの採用判断と受入値

| 採用する条件 | 選択肢と推奨理由 |
| --- | --- |
| 運賃負担と価格の範囲 | **`E_JP` が負担し、法人間価格5,000円／個に含めるCIFを採用**。金額仮定書と一致する。運賃別・買い手負担は、同じ金額の取得原価加算が正当になる対照例として使う。 |
| 認識週 | **船積み時に支配が移るD-2を採用**。出荷・輸送中・受入の原価を一続きで追える。契約で受入時に移る場合は、受入週で法人間売買を認識する。外部運賃の負担確定と支払は各事象の記録で判定する。 |
| 原価の扱い | **`E_JP` の法人間売上に対応する直接原価、`E_SG` の価格に含まれる取得原価、連結の在庫・売上原価として追う**。元の外部費用を一度だけ帰属させ、未販売期と販売期の連結値を照合できる。 |

**受入値**は、2028-W28に `E_JP` の外部運賃1,440円・1件と `E_SG` の取得120,000円・1件、W29の `E_SG` の運賃追加0件、W30末の連結在庫 `C + 1,440円`、W31の `E_SG` の売上原価120,000円・1件と連結の売上原価 `C + 1,440円`・1件。連結で残る外部運賃はこのロットで1,440円。

実際の契約・船積み・請求・保険・決済の原票、M0実行時の `output/` のロット明細は未確認。週別の受入値は仮定に基づく手計算で、WOM実行による検証はこれから行う。大杉さんの採用後、Claude君へこの定義と[共通照合表](WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md)を渡す。
