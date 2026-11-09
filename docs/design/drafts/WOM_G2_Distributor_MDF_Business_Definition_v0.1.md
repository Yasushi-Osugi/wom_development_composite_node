# WOM 化粧品 G2 業務定義案 v0.1

- 作成日　2026-11-08
- 担当　GPT-MC（業務定義）
- 引継先　Claude君（設計担当）
- 状態　提案。MDFの負担確定条件は大杉さんの採用判断前
- 参照基準　`wom-v1r6m0_BS-SEAF`、コミット `fea28db46c09f2bf20245b740a7fbbdc051ae922`

## 1. 適用範囲と負担者

化粧品の週次経営シミュレーションで、自社が負担し、外部代理店に支払う販促協賛金（MDF）を、対象の外部卸売に結び付けて計上する。費用の帰属は負担する自社法人、販促の対象は代理店チャネル、協賛金の受取先は外部代理店とする。1件の卸売ロットに対し、同じ協賛負担が1件成立する試行を対象とする。

| 市場 | 対象の外部卸売区間 | 売り手・費用負担者 | 買い手・協賛金の受取先 | 通貨 |
| --- | --- | --- | --- | --- |
| シンガポール | `DC_SG → SG_Distributor` | `E_SG`（シンガポール販社） | `EXT_CH_SG_DIST`（外部代理店） | SGD |
| タイ | `DC_TH → TH_Distributor` | `E_JP`（日本本社） | `EXT_CH_TH_DIST`（外部代理店） | THB |

対象SKUはクリームと美容液。最初の照合はSG向けクリーム24個・1ロットとする。代理店自身が負担する販促、G1の直販費用、グループ内の売上、代理店の消費者向け出荷の観測は、取引の区分に従ってG2の対象外とする。販促案件を複数ロットに配分する契約や、実績の取消・訂正は別の検証条件を持つ。 [金額仮定書 §2.2・§4.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L39-L48) · [法人割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L16-L21) · [MDFの費用設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/ppc_node_cost_rule.csv#L18-L21)

## 2. 確認した入力とWOMの観測

| 区分 | 確認した内容 |
| --- | --- |
| 現行サンプルの試行設定 | SG・THとも代理店向けの料率は5%。費用CSVの注記はSG向けを `E_SG`、TH向けを `E_JP` の負担とする。1ロットは24個 |
| 確認済みのG3 | 代表ロット `COS_Cream:SG_Distributor:2028-W29:00002` の `DC_SG` 実出荷と外部卸売の認識は2028-W28。税抜1,488.00 SGDの売上明細1件。受入と代理店側の出荷はW29 |
| M0の観測 | PPCはMDFを `marketing_cost` として集計した。Value ChainのG2は、外部代理店ノードに設定した費用の明細もissuesも出なかった。T12の全期間差は22,196,148円 |
| G1反映後の観測 | 正式サンプルの利益比較（Value Chain − PPC）の差は22,196,148円。G2の比較値であり、今回のMDF計上週は§3で条件として提案する |

G3の出荷原本の `ship_id` と売上原本の `src_id` は、ともに `ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6`。売上行は `revenue / external / wholesale`、相手先は `EXT_CH_SG_DIST`。同じロットにある本社から販社への法人間売上やW29の観測明細は、別の取引・事象として照合する。 [サンプル計画設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/planning_config.csv#L1-L5) · [G3検証報告 §4.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L82-L100) · [G3出荷明細](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_shipments.csv#L6) · [G3売上明細](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_money_lines.csv#L19) · [M0報告書 G2・T12](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L454) · [G1検証報告 §11](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md#L225-L233)

## 3. MDFの算定と計上週の判断案

### 3.1 算定基準と費用区分

対象の外部卸売について、認識した税抜卸売額（MDF控除前）に試行料率5%を掛ける。代表例の卸売額は、実出荷24個 × 卸単価62 SGD/個 ＝ **1,488.00 SGD**。協賛費は **1,488.00 × 5% ＝ 74.40 SGD**。額は取引通貨で計算し、負担1件の合計の小数第3位を四捨五入する案とする。代表例とタイの例には丸め差が生じない。円での参考照合にはM2の固定為替（1 SGD＝115 JPY、1 THB＝4.5 JPY）を使う。 [卸価格CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv#L4-L7) · [金額仮定書 §1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L18-L26) · [M1・M2の判断](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L121-L132)

本試行では、M0に沿って「代理店向け販促協賛費（MDF、販売費）」として負担法人に費目別明細を1件立てる。卸売の売上、協賛の負担と費用、協賛金の支払はそれぞれの根拠事象で記録する。

実取引を評価する場合は、代理店が提供する別個の販促役務とその対価を契約・実施記録で特定できるか、支払が卸売の値引き・割戻しに該当するかを確認する。IFRS 15を適用する場合、顧客への支払は原則として売上の減額。別個の財・サービスの対価は購入として扱い、その公正価値を超える分は売上の減額となる。公正価値を合理的に見積もれない場合は全額を売上から減額する。例えば74.40 SGD全額を卸売の割戻しとする条件では、調整後の売上は1,413.60 SGDとなる。同じ74.40 SGDの処理は該当する区分で一度行う。A・Bは販促費モデルの負担確定週の比較で、実契約の区分・認識には契約と適用基準を別途確認する。 [IFRS Foundation、IFRS 15（2024年版）¶70–72](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2024/issued/part-a/ifrs-15-revenue-from-contracts-with-customers.pdf)

### 3.2 負担確定事象と三つの週

| 項目 | A　対象卸売の成立で確定 | B　販促実施・承認などで確定 |
| --- | --- | --- |
| 適用条件 | 対象の外部卸売が成立した時点で、その卸売に対する5%の販促協賛負担も確定する、と化粧品サンプルの前提に置く | 対象卸売を算定に使い、販促の実施や承認が負担を確定させる条件とする。ここでは承認が最後の条件 |
| 算定に使う売上の週 | **2028-W28**（G3のDC実出荷で認識） | **2028-W28**（同じ卸売を参照） |
| 費用計上の週 | **2028-W28**。対象卸売の成立と同時に確定するMDFを費用にする | **2028-W30**に承認で確定する試験例。販促実施と承認の両方が条件なら、最後の条件を満たした週に費用にする |
| 確定の根拠 | G3の外部卸売・出荷の記録と、当該法人・相手先・SKUに適用する協賛条件 | 元の外部卸売の記録と、その取引に対応する販促案件・実施・承認等の記録 |
| 支払の週 | 未設定。送金・相殺などの決済条件で別に決まる | 同左。W30は承認による費用の確定週 |

**初回試行はAを推奨する。** G3で売上と出荷を1件ずつ照合できるので、負担もそこで確定するモデル条件を採用すれば、費目・週・件数を同じ原本から検証できる。計上週を決める根拠は「対象卸売が成立すると協賛負担が確定する」という今回の仮定。Bは、承認等が実質的な確定条件である契約を表す。後日の書類が既に確定した負担の確認にとどまるときは、負担が成立した元の週を使う。

Bに必要な追加の事実は、協賛条件・販促案件の識別、負担法人と受取先、対象卸売の出荷IDまたは対応を確定できる取引明細、実施・承認の有無と日付、確定した金額または料率・対象額と通貨。複数の卸売にまたがる承認なら、各卸売へ配分する根拠も必要になる。実施・承認・決済の実績原本は確認できていないため、W30は条件比較用に置いた週である。

## 4. 代表1ロットの期待結果

対象は `COS_Cream:SG_Distributor:2028-W29:00002` の外部卸売。負担法人は `E_SG`、受取先は `EXT_CH_SG_DIST`。いずれも算定基準1,488.00 SGD、料率5%、費目「代理店向け販促協賛費（MDF）」。表の0件は当週に確定費用の追加が無いという意味。

| ISO週 | 事象 | AのMDF（件数・金額） | BのMDF（件数・金額） |
| --- | --- | --- | --- |
| 2028-W28 | `DC_SG` 実出荷・外部卸売の成立 | **1件・74.40 SGD** | 0件（承認前） |
| 2028-W29 | 代理店受入・代理店側の出荷 | **追加0件** | 0件（承認前） |
| 2028-W30 | Bの負担を確定させる承認（試験入力） | 追加0件 | **1件・74.40 SGD** |
| **期間計** | **1ロットの協賛負担** | **1件・74.40 SGD** | **1件・74.40 SGD** |

| 判定 | 具体例 | 期待結果 |
| --- | --- | --- |
| 対象外 | G1の公式EC売上、グループ内売上、代理店の消費者向け出荷の観測、代理店自身の費用 | G2の集計対象から除外 |
| 負担なしと確認 | 対象の卸売について負担なしと確認、または適用する規則が明示的に0% | **0件・0.00**。負担なしの根拠を記録 |
| Bで承認前と確認 | 承認の状態が取得でき、W28・W29は未承認と判明 | 当週の確定明細は0件。承認待ちとして区別 |
| 判定保留 | 対象取引の卸売額・料率・負担法人・受取先の根拠や、Bでの確定を示す承認記録が不足し、確定の有無または額が不明 | 確定額を保留し、不足した情報を記録。確定額0とは区別 |

### 4.1 タイ向けの短い確認

M0のタイ向けクリーム `COS_Cream:TH_Distributor:2029-W03:00003` は、`DC_TH → TH_Distributor` の外部卸売が2029-W02。負担者は日本本社 `E_JP`、受取先は外部代理店 `EXT_CH_TH_DIST`。24個 × 1,600 THB/個 ＝ 38,400 THB、5%は **1,920.00 THB**。Aなら **2029-W02に1件**。Bで例えば2029-W04の承認が負担を確定させるなら、W02の売上を基準に **W04に1件**。代理店受入・代理店側出荷のW03は照合に使う。 [M0報告書 T13](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L460-L467) · [卸価格CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv#L6-L7) · [費用設定・負担者](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/ppc_node_cost_rule.csv#L20-L21)

## 5. 照合、重複防止、全期間の参考値

1. **元の卸売を特定する。** 売り手・買い手・卸売区間・Lot_IDで取引を選び、DCの出荷IDと外部卸売明細の元記録IDを照合する。MDFは負担法人・受取先・費目を添えて照合する。
2. **同じ協賛負担を1件として数える。** 今回の範囲では、元の卸売出荷ID・負担法人・MDF費目の組につき、有効な費用明細は1件。Aは卸売の記録を確定の根拠とする。Bは元の卸売出荷IDに、確定を示す承認等のID・週をひもづける。同じ承認の再提示を照合し、週・請求・支払の記録だけで同じ負担を増やさない。
3. **後続事象と再計算を照合する。** 受入、代理店側の出荷、PPC集計、支払は元の負担との照合用。同じ計画入力で再計算しても、費用の週・件数・金額が期待表と一致することを確かめる。実績データの再取込や訂正による差替えは、その段階での別の検証項目とする。

G3のPPCのW29行は `COS_Cream × SG_Distributor × 2028-W29` の5ロット（120個）、卸売相当7,440 SGDの集計。5%の金額相当は5ロットで372.00 SGD、代表1ロットで74.40 SGD。これは算定額の照合に使う。週別の合否は、採用した負担確定事象とG2の費用明細の週・件数・金額で判定する。 [G3検証報告 §4.4](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L119-L123)

全期間の参考値は、G3で確認した対象外部卸売 **443,922,960円 × 5% ＝ 22,196,148円**。2,340件すべてで同じ料率の負担が1回確定し、同じ報告期間・為替前提で集計する場合の比較値で、M0 T12のG2とG1反映後の利益差に一致する。Bで承認が報告期間外にずれる、または負担が確定しない取引がある場合は、承認範囲と計上期間に応じて比較する。 [G3検証報告 §4.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L102-L110) · [M0報告書 T12](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L439-L454) · [G1検証報告 §11](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md#L225-L233)

## 6. 読取記録と確認範囲

| 読んだ資料 | 版・箇所と用途 |
| --- | --- |
| 添付のG2業務定義依頼 | v0.1（2026-11-08）§§1–5。成果物、候補、比較範囲 |
| [Start Here](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/WOM_Start_Here.md#L203)、[M0報告書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L473) | 指定コミットの§7、M0の§6 G2・T12・T13と[§7](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L494-L516)。現行の観測、タイの週と実行出力の所在 |
| [金額仮定書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md) | 指定コミットの本文v0.2（ファイル名はv0.1）、§§0・1・2.2・4.2・5.1。数量・通貨、価格、MDF率、M1・M2・M7・M8 |
| 正式サンプルの設定 | 指定コミットの [MDF費用行](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/ppc_node_cost_rule.csv#L18-L21)、[法人割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L16-L21)、[卸価格](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv#L4-L7)、[計画設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/planning_config.csv#L1-L5) |
| [G3検証報告](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L80-L123)と付録 | 指定コミットの§§4.1–4.4。[出荷](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_shipments.csv)、[金額明細](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_money_lines.csv)、[照合結果](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/verify_g3_result.json)。代表の出荷ID、外部卸売明細、全体の比較値 |
| [G1検証報告](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md#L207-L233)、[プロセス知識](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/bsseaf/WOM_BSSEAF_Process_Knowledge.md#L75-L78) | 指定コミットのG1報告§11とプロセス知識v0.8 §3.2。利益の差と、事象・費目・件数による検証の作法 |
| [IFRS 15](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2024/issued/part-a/ifrs-15-revenue-from-contracts-with-customers.pdf) | IFRS Foundation公表の2024年版¶70–72。実取引で顧客への支払を区分するときの参考 |

確認範囲は、指定版の文書・入力CSV、G3の付録明細との照合と、G2の手計算。M0およびG1の全件の実行台帳原本はGit管理外のため未取得で、観測値は各報告書による。MDFの契約・販促実施・承認・決済の実績原本は提示資料から確認できていない。§4は業務上の期待結果で、G2の実行による確認は後続工程。 [M0報告書 §7](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L494-L516) · [G1検証報告 §10–11](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md#L192-L233)

## 7. 大杉さんの判断と引継ぎ

| 一言の判断案 | 採用する前提と影響 |
| --- | --- |
| **初回は、対象卸売の成立でMDFの負担も確定すると置く** | 案Aを推奨。SG代表はW28に1件・74.40 SGD、THの確認例はW02に1件・1,920.00 THB。販促実施・承認が確定条件となるケースには案Bを用い、事実を示す記録と週を指定する |
| **M0に沿って、税抜の外部卸売額の5%を販促協賛費として試算する** | 試行料率・負担法人・取引通貨を明記し、同じ負担1件の金額を小数第3位で四捨五入し、小数第2位まで記録する。売上の割戻しとして評価する契約では、売上調整の条件を別に定義する |

採用後に、判断記録、本書の週別期待値、元の卸売出荷IDと費目の照合条件、参照コミットをClaude君に渡せる形とする。設計では、既存のG3卸売明細を利用できる範囲と、負担法人別の費用明細を表すために必要な差分を確認する。
