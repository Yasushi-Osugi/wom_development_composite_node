# 化粧品 G2 代理店向け販促協賛金の業務定義依頼 v0.1

- 宛先：GPT-MC君（業務定義担当）
- 依頼者：大杉
- 日付：2026-11-08
- 状態：依頼書ドラフト
- 参照基準：`wom-v1r6m0_BS-SEAF`、コミット `fea28db46c09f2bf20245b740a7fbbdc051ae922`

## 1. 依頼する成果物

**G2（代理店向けの販促協賛金、MDF）の業務定義案 v0.1**を、`WOM_G2_Distributor_MDF_Business_Definition_v0.1.md` として作成してください。最初の照合例は、G3で確認したシンガポール代理店向けのクリーム1ロットです。**誰が、誰への、何に基づく負担を、どの週に、いくら計上するか**を、手計算と件数で確かめられる形にしてください。

G1は正式な化粧品サンプルのシンガポール直販で検証済みです。G2は外部代理店との取引であり、販促の対象拠点と、費用を負担する自社法人を分けて扱います。今回の成果物は経営シミュレーションの業務定義と期待結果です。WOMへの対応付けは、業務条件の採用後にClaude君が行います。

## 2. 根拠と試行の前提

| 確認すること | 根拠 |
| --- | --- |
| G2の現在地 | [Start HereのG2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/WOM_Start_Here.md#L203)・[M0報告書 §6・T12](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L454)。M0ではPPCが代理店向けMDFを集計し、Value Chainでは計上も問題の一覧への記録もされなかった。 |
| 現行サンプルの費用・取引主体 | [金額仮定書 §§2.2・4.2・5.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md)・[費用CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/ppc_node_cost_rule.csv#L18-L21)・[法人割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv)。SG・THとも試行料率は5%。自社側の負担者はSG向けがシンガポール販社 `E_SG`、TH向けが日本本社 `E_JP`。代理店は外部法人。 |
| どの売上を参照するか | [卸価格CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv#L4-L7)・[G3検証報告 §§4.1–4.4](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L80-L123)。G3の代表ロットは、DC出荷週の外部卸売に対応する。代理店受入、代理店側の出荷の観測、PPC集計は照合に使う。 |
| G1反映後の利益差と検証の作法 | [G1検証報告 §11](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md#L207-L233)・[プロセス知識 §3.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/bsseaf/WOM_BSSEAF_Process_Knowledge.md#L75-L76)。正式サンプルの利益合計の差は22,196,148円。業務定義では、明細の種類・件数と元の事象の照合方法を示す。 |

現行サンプルの料率・価格・法人割当、報告書にある観測結果、今回提案する計上条件を分けて記してください。**G3で決めたのは卸売の売上週です。MDFの負担がその週に確定するかは、今回の業務判断です。**

## 3. 業務定義で決めたいこと

1. **対象と負担者**：対象となる外部卸売、費用を負担する自社法人、協賛金の受取先を特定してください。代理店自身が負担する販促費、G1の直販費用、グループ内の取引、代理店の消費者向け販売の観測は、対象取引と区別してください。
2. **算定基準と費用の意味**：税抜の外部卸売額に試行料率5%を掛ける案を出発点に、対象額、数量、通貨、丸めを示してください。M0は自社負担の販促費として試算しています。売上値引き・割戻しとして扱う条件があり得るなら、何が違うと判断が変わるかを示してください。契約条件を確認できない場合は、モデルの仮定として記載してください。
3. **負担の確定と計上週**：卸売の成立で負担が確定する案と、販促実施・承認など別の事象で確定する案を比較し、化粧品サンプルで採る案を提案してください。算定に使う売上の週、費用計上の週、支払の週を区別し、根拠となる事象を示してください。
4. **0件と保留の区別**：対象外・負担なしが確認できる場合と、対象取引なのに価格・料率・負担法人・承認など必要な根拠が足りない場合を分けてください。後者は何が不明かを記録し、確定額0と区別します。

## 4. 手計算の照合例

代表は `COS_Cream:SG_Distributor:2028-W29:00002`。シンガポール販社 `E_SG` から外部代理店 `EXT_CH_SG_DIST` への卸売です。

| 入力の事実 | 値 |
| --- | --- |
| 区間と卸売の根拠事象 | `DC_SG → SG_Distributor` の実出荷、2028-W28 |
| 卸売額 | 24個 × 62 SGD/個 ＝ 税抜1,488.00 SGD |
| 後続の事象 | W29の代理店受入・代理店側の出荷。PPCのW29集計は複数ロットを含む。 |
| 5%を適用した金額 | 1,488.00 SGD × 5% ＝ **74.40 SGD** |

次の表は条件を比較するための例です。どちらを採るかと、実際に必要な記録を業務定義案で示してください。

| 条件 | 週別の期待結果 |
| --- | --- |
| A：対象の外部卸売で負担が確定する | W28に `E_SG` のMDF **1件・74.40 SGD**。W29の受入・代理店側の出荷に伴う追加計上は0件。 |
| B：販促実施・承認で負担が確定する | W30に承認される試験例では、W28・W29に確定費用の計上はなく、W30に**1件・74.40 SGD**（算定基準・料率はAと同じと仮定）。承認の記録が無く、確定の有無が不明なら保留。 |

- **重複防止**：Aでは、同じ卸売の出荷ID・費目・負担法人を照合し、同じ負担の有効な費用明細は1件。Bでは、承認等の負担確定記録を元の卸売とどう結び付けるかを示してください。受入・代理店側の出荷・PPC集計は照合用です。
- **タイへの適用確認**：[M0報告書 T13](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/fea28db46c09f2bf20245b740a7fbbdc051ae922/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L460-L467)のタイ向けクリーム1ロットでは、`DC_TH` から外部代理店への卸売が2029-W02です。5%を適用するなら24個 × 1,600 THB × 5% ＝ **1,920 THB**。負担法人は `E_JP`。AとBの違いが、タイ向けでも同じように説明できるかを短く示してください。
- **全期間の参考照合**：G3の外部卸売443,922,960円相当に、同じ対象範囲・同じ為替前提で5%を適用すると**22,196,148円**。G1後の比較表の利益差と一致します。週別の合否は、採用した負担確定事象と費用明細で判定してください。PPCの集計週との一致を条件にしません。

## 5. 提出時に明記すること

業務定義案に、**①採用を勧める条件と理由、②代表ロットの法人・相手先・根拠事象・計上週・費目・件数・金額、③追加計上0件／対象外／保留の例、④大杉が決める点**を入れてください。実際に読んだ版・箇所と確認できなかった原本を記し、手計算の期待結果とWOMでの観測を区別します。案Bなど、計画データに負担確定の記録が無い場合は、追加で必要な事実を挙げてください。

まずはこの1ロットから定義を作り、タイ向けの短い確認を添えてください。大杉が条件を採用したら、定義書・判断記録・期待結果をClaude君に渡し、既存機能と設定で表せる部分と、追加が必要な部分を分けます。
