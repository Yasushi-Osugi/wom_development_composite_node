# WOM 化粧品 G1 業務定義案 v0.1

- 作成日　2026-11-08
- 担当　GPT-MC（業務定義）
- 引継先　Claude君（設計担当）
- 状態　提案。計上条件は大杉さんの採用判断前
- 参照基準　`wom-v1r6m0_BS-SEAF`、コミット `d91846819e05b074013975917cbd6c219a558505`

## 1. 問いと適用範囲

シンガポール販社（`E_SG`）の直販で、どの売上に料率を掛け、どの配送に個数単価を掛けて、どの週の販売費にするかを定義する。対象はWOMの週次経営シミュレーション。費用を負担する法人は `E_SG` とし、消費者への商品売上、販売費の計上、費用の支払は別の記録として扱う。

| 項目 | 今回の範囲 |
| --- | --- |
| 販売取引 | `E_SG` から外部の消費者への直販。公式EC `SG_EC` と直営店 `SG_Store` |
| 配送・梱包 | `SG_EC` の消費者向け発送に伴う、`E_SG` 負担の配送・梱包 |
| 対象SKU・単位 | クリーム `COS_Cream` と美容液 `COS_Serum`。期待例はクリーム1ロット＝1ケース＝24個 |
| 期間・通貨 | ISO週・SGD。M0の報告対象は2027-W01〜2029-W52。期待例の週は試験用に設定 |
| 別の論点 | 代理店MDF（G2）、輸入関税（G4）、日本からSGへの海上運賃と在庫原価（G5）、週固定費・配分に使う変動費、実績取込時の返品・訂正の設計 |

`DC_SG → SG_EC` の市内運賃0.30 SGD/個はEC拠点までの区間費用。G1の3 SGD/個はその先の消費者向け配送・梱包なので、同じ費用の根拠として扱わない。 [金額仮定書 §4.1–4.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L68-L95) · [M0 区間費用CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_edge_cost_rule.csv#L12-L13) · [法人・チャネル割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L16-L19)

## 2. 採用済みの前提とM0の観測

| 状態 | 内容 |
| --- | --- |
| 採用済みの試行前提 | 税抜の価格と費用の水準（M1）、直営店の店舗運営費を売上の35%で近似（M5）、費用が無いと確定した対象には明示の0（M7）。公式ECのクリームは平均値引き反映済みの **131 SGD/個** |
| 費用CSVの事実 | M0のECでは、販社販管費10%と決済・EC基盤手数料5%、配送・梱包3 SGD/個が一つの `sga_cost` 行（`basis=revenue`、`rate=0.15`、`fixed_amount=3`）。デジタル広告15%は別の `marketing_cost` 行 |
| M0での観測 | Value Chainは売上比率の費用行を計上せず、同じ行の配送・梱包費も一緒に落ちた。issuesには `revenue_based_node_cost_not_supported` が出た。M0のG1未計上額は全期間・両チャネルで **281,015,748 JPY**、うちECの配送・梱包は **6,243,120 JPY** |
| 今回の提案 | 費目ごとに算定基準と計上事象を定義し、以下の期待値を入力から手計算する。提案の適用結果は設計・検証工程で照合する |

M0の `fixed_amount=3` は1個当たりの設定値。価格・料率の採用と、費目別の計上週の採用を区別する。 [金額仮定書 §2.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L39-L48) · [同 §5.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L121-L132) · [M0 費用CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_node_cost_rule.csv#L12-L17) · [M0報告書 §6 G1・T12](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L454)

## 3. 業務ルール案

**売上比率の基準**は、同じ取引・ロットについて `E_SG` が認識した、モデル上の値引き反映後かつ税抜の消費者向け商品売上。クリーム1個の基準は公式ECの131 SGDをそのまま使う。前段の法人間売上と、代理店の卸売・観測売上は別の取引として識別する。直販では `SG_EC` または `SG_Store` の消費者向け外部売上が対応する。 [金額仮定書 §2.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L39-L48) · [段階D設計 v1.0 §3](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L76-L109)

| 対象 | 費用明細の種類 | 算定基準 | 計上の根拠と週 |
| --- | --- | --- | --- |
| EC・直営店 | 販社販管費 | 税抜売上 × 10% | 対象の外部売上を認識した週。販社の宣伝・管理費を配賦する試行上の費用 |
| EC | 決済・EC基盤手数料 | 税抜売上 × 5% | 対象の外部売上を認識した週。決済・基盤提供者への負担を近似 |
| EC | デジタル広告費 | 税抜売上 × 15% | 対象の外部売上を認識した週。デジタル広告の販社負担を近似 |
| EC | 消費者向け配送・梱包費 | 対象発送の個数 × 3 SGD/個 | 対象ロットの消費者向け発送と販社負担が確定したことを根拠に、対象発送が行われた週。売上より先の週でも費用が発生する案 |
| 直営店 | 店舗運営費（M5の近似） | 税抜売上 × 35% | 対象の外部売上を認識した週。家賃・人件費などの店舗運営費を試行上の料率で近似 |

各明細は `E_SG` の販売費として費目別に1件。直営店では **店舗運営費35%と販社販管費10%の2件（合計45%）** を区別する。店舗運営費35%はM5の試行上の近似。週固定費の計算や、配分判断で使う変動費の定義は別途扱う。販社販管費、個別の決済・基盤手数料、デジタル広告にはそれぞれの費用範囲を割り当てる。 [金額仮定書 §4.2・§5.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L83-L132)

発送週と売上週が異なる例では、配送・梱包の負担を示す記録と外部売上の記録を個別に確認する。通常のサンプルで最終販売を表すECの実出荷と、試験上の配送・梱包の負担確定を、区別できることが先行例の適用条件となる。

## 4. ECのクリーム1ロットの手計算

**試験入力**　`SG_EC` で `E_SG` が消費者にクリーム24個を一括販売。2028-W28にEC拠点への入荷、2028-W29に対象外部売上の成立と消費者向け発送（販社負担確定）があると置く。週と事象の並びは手計算・照合用の仮定。数量はサンプルの1ロット24個、価格は税抜131 SGD/個で、売上基準額は **3,144.00 SGD（24 × 131）**。 [サンプルの計画設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/data/sample/cosmetics-sg-th-2027-2029/planning_config.csv#L1-L5) · [M0 市場価格CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_market_price.csv#L5)

| 週 | 負担法人 | 費用明細の種類 | 計算 | 件数 | 金額（SGD） |
| --- | --- | --- | --- | ---: | ---: |
| 2028-W29 | E_SG | 販社販管費 | 3,144.00 × 10% | 1 | 314.40 |
| 2028-W29 | E_SG | 決済・EC基盤手数料 | 3,144.00 × 5% | 1 | 157.20 |
| 2028-W29 | E_SG | デジタル広告費 | 3,144.00 × 15% | 1 | 471.60 |
| 2028-W29 | E_SG | 消費者向け配送・梱包費 | 24個 × 3.00 | 1 | 72.00 |
| **2028-W29 計** | **E_SG** | **G1の販売費** | **比率分943.20 ＋ 個数分72.00** | **4** | **1,015.20** |

W28のEC拠点への入荷だけでは、G1の販売費は **0件・0.00 SGD**。W29の外部売上1件・3,144.00 SGDは費用4件の件数と別に照合する。金額はSGDの小数2桁表示で、本例の計算に丸め差は生じない。

### 4.1 事象が分かれる場合の判定例

下表は上記と同じ単価・数量を使う条件別の期待値。括弧内はG1の販売費明細の件数。

| 試験条件 | 2028-W28 | 2028-W29 | 判定 |
| --- | ---: | ---: | --- |
| 対象配送だけ先行。販社負担はW28に確定し、対象売上はW29に成立 | 72.00（1） | 943.20（3） | 配送分は発送週。売上週での配送分の追加は0件。合計1,015.20（4） |
| 対象売上はW29に成立。販社負担の対象配送は無いと確定 | 0.00（0） | 943.20（3） | 配送・梱包は0件 |
| 販社負担の対象配送はW28に確定。対象売上は成立しないと確認済み | 72.00（1） | 0.00（0） | 確定した配送分のみ。売上比率の3費目は0件 |
| 対象外部売上も対象配送も無いと確定 | 0.00（0） | 0.00（0） | G1の発生なし |
| 対象配送と負担はW28に確定。売上の記録不足で成立・金額を判定できない | 72.00（1） | 比率分は保留 | 確定分は72.00。G1の総額は一部未評価 |

対象外の取引はG1の集計から外す。対象内で費用の発生が無いと確定したときは0件・0 SGDとし、規則として費用なしが確定したノード・区間はM7に沿って明示の0を根拠にする。適格事象・数量・基準額・料率・単価・負担法人のいずれかを確かめられない費目は判定を保留し、確定できた費目を別に示す。

## 5. 照合と重複防止

1. **取引と費目を特定する。** 売上比率分は、売り手・買い手・チャネル（または区間）・SKU／Lot_IDで対象の消費者向け売上を特定し、売上の根拠記録を照合する。配送分は、負担法人・消費者向けの配送区間・SKU／Lot_IDで対象発送を特定し、発送・負担の根拠記録を照合する。両方とも費目を添えて数える。
2. **根拠事象ごとに対象の費目を一度計上する。** 1件の外部売上に対し売上比率分は該当費目ごとに1件。1件の対象発送に対し配送・梱包はまとめて1件。入荷の記録は追跡用とし、配送費を計上した後の売上成立は売上比率分だけの根拠にする。同週の基本例は販売費4件、先行例はW28に1件・W29に3件が合格条件。
3. **同じ試算の再計算でも件数と金額を照合する。** 同一入力を再計算した結果は上表と一致すること。実績取込での同じ記録の再受信と、訂正で発生週・金額が変わる場合の差替えは、別の設計・検証項目として扱う。

M0のPPCはSKU・チャネルのleaf・週で集計した照合用の値。基本例で対象1ロットの数量相当だけを計算すると、PPCのまとめ方では `sga_cost` が543.60 SGD、`marketing_cost` が471.60 SGD。集計行に複数ロットがあれば対象数量相当で比較する。配送先行例の週別の合否は、採用した根拠事象と費目別の期待表で判定する。 [M0試行依頼書 v0.2 §3.3](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun.md#L108-L138) · [G3検証報告 §6](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L135-L145)

## 6. 読取記録と確認範囲

| 実際に読んだ原本 | 版・箇所 |
| --- | --- |
| 添付の金額編の業務定義依頼 | v0.1（2026-11-08）§§1–5。G1の初回提出範囲 |
| [AGENTS.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/AGENTS.md#L27) と [Start Here](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/WOM_Start_Here.md#L190) | 指定コミット。§2の記録方針と§7のG3解決・G1未解決 |
| [GPT-MCの役割定義](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/design/drafts/WOM_GPT_MC_Role_Definition_v0.1.md#L18)、[G3業務定義](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/design/drafts/WOM_G3_SellIn_Business_Definition_v0.1.md#L39)、[G3検証報告](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md#L135) | 指定コミット。役割v0.1 §§2–5、G3定義v0.1 §§4–5、検証報告§6 |
| [金額仮定書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md) と [M0報告書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L360) | 指定コミット。仮定書の本文v0.2（ファイル名はv0.1）§§0・2・4・5.1・7、報告書の§§1.1・4（T4・T9）・6（T12–T15）・7 |
| M0の入力CSVとサンプル設定 | 指定コミット。[費用](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_node_cost_rule.csv#L12-L17)、[市場価格](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_market_price.csv#L2-L5)、[VCの法人間・卸価格](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/vc_price_rule.csv)、[区間費用](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_edge_cost_rule.csv#L6-L13)、[ノード割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L16-L19)、[計画設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/data/sample/cosmetics-sg-th-2027-2029/planning_config.csv#L1-L5)。公式ECの131 SGDの出典は市場価格CSV |
| [段階D設計](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L76) と [M0試行依頼書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun.md#L108) | 指定コミット。段階D設計v1.0 §3、M0試行依頼書v0.2 §3.3 |

確認範囲は指定版の文書・入力CSVと手計算。M0の元の実行台帳はGit管理外のため未取得で、観測は報告書の記録に基づく。期待表の週は試験入力であり、M0の実行週の転記ではない。 [M0報告書 §7](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L494-L516)

G2のMDFは外部代理店向けの別取引。G4の関税とG5の海上運賃は上流の区間・原価の論点として分ける。G1との接点は配送範囲の区別で、`WH_JP_Released → DC_SG` の海上運賃、`DC_SG → SG_EC` の市内運賃、`SG_EC` から消費者への配送・梱包をそれぞれの区間・事象で照合する。 [金額仮定書 §4.1–4.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md#L68-L95) · [M0報告書 §6 G2・G4・G5](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/d91846819e05b074013975917cbd6c219a558505/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L435)

## 7. 推奨案と大杉さんの判断事項

| 決めること | 推奨する前提 | 別の前提を置いた場合の影響 |
| --- | --- | --- |
| 売上比率に使う金額 | **値引き反映後・税抜の対象外部売上**。試行の費用と販売を同じ取引の金額で照合でき、平均値引き反映済みの131 SGD/個を使える | 費目の契約で別の基準を定める場合はその費目だけ変わる。比較として全3費目を値引き前の138 SGD/個に置くなら、同週例の比率分は993.60、G1計は1,065.60 SGD。ECの売上そのものは131 SGD/個 |
| 売上比率分を計上する週 | **対象外部売上の認識週**。採用済みの試行料率を、売上との対応が追える週に置く | 特定の費目で、決済・役務完了など独立の負担確定事象を使うなら、その費目の週を別にする。例として5%の費目だけがW30確定なら、157.20 SGDがW29からW30へ移る |
| 配送・梱包費の計上事象 | **販社負担が確定した消費者向け発送の週**。配送だけが先行した週にも、その週に発生した販社負担を示せる | 配送費の負担確定も対象売上の成立を条件とする場合、先行例のW28は0件、W29は4件・1,015.20 SGD。同じ売上が成立しない場合の負担条件もこの選択に合わせて定義する |

採用判断に合わせて、売上と対象発送の根拠として使う記録を確定する。Claude君への引継ぎでは、採用判断、基本例・先行例の週別金額と件数、同一取引・費目の照合条件、参照コミットを渡す。
