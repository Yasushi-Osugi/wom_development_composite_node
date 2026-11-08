# WOM 化粧品 G3 業務定義 v0.1

- 作成日　2026-11-08
- 担当　GPT-MC（WOM金額編の業務定義）
- 状態　大杉さんの採用判断を反映（2026-11-08）。設計への引き渡し用
- 参照基準　`wom-v1r6m0_BS-SEAF`、コミット `7777b2a006421655baa9ad4e8891006512da9ca2`

## 1. 問いと適用範囲

WOMの週次管理シミュレーションで、シンガポール販社から外部代理店へのクリームの卸売（sell-in）を、どの事象に基づいて、どの週に計上するかを定義する。

| 項目 | 今回の対象 |
| --- | --- |
| 売り手と買い手 | シンガポール販社（`E_SG`）→ シンガポールの外部代理店 |
| 物流区間 | `DC_SG → SG_Distributor` |
| 対象ロット | `COS_Cream:SG_Distributor:2028-W29:00002` |
| 数量と単価 | 1ロット＝1ケース＝24個。クリームの卸単価は税抜62 SGD/個 |
| 計上額 | 24個 × 62 SGD/個 ＝ **税抜1,488 SGD**。売上の帰属先はシンガポール販社 |
| 取引の範囲 | 全量を一括で引き渡す1件の卸売。部分受入、返品、独立した検収が必要な取引は範囲外 |

## 2. M0で観測された結果

M0報告書 §6 T13 の代表ロット行に記録された週を示す。表中の売上週は各方式の観測結果。

| 観測項目 | 週 | M0での扱い |
| --- | --- | --- |
| `DC_SG` の実出荷 | 2028-W28 | Value Chainはこの週に外部卸売を計上 |
| 代理店の受入（P） | 2028-W29 | モデル上の受入週 |
| 代理店leafの実出荷（S） | 2028-W29 | PPCはこの週に売上を計上。Value Chainは別の観測明細 `observation_sale` として記録 |

T13では両方式に税抜卸単価62 SGD/個が使われている。Value Chainの `observation_sale` も同じ卸単価による観測であり、グループの売上集計から除かれている。 [M0報告書 §6 G3・T13](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L473)

## 3. 採用した計上ルール

**大杉さんの判断（2026-11-08）**　「出荷時に支配が移る」ことを基本とする。今回の卸売には、段階DのD-2（案Aの出荷時認識）を適用する。 [段階D設計 v1.0 §0.1 D-2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L10-L19)

この試行では、対象取引・ロットの `DC_SG → SG_Distributor` の実出荷を、モデル上の引渡し完了の根拠とする。実出荷の事実を確かめ、実際に出荷したISO週にシンガポール販社が税抜卸売額を計上する。代理店の受入（P）とleafの実出荷（S）は、出荷に続く別々の物流事象として扱う。

## 4. 採用したルールの期待結果

この1件の卸売にD-2を適用した場合の期待値。数量24個と税抜卸単価62 SGD/個から計算する。

| ISO週 | 入力となる事象 | 卸売明細の件数 | 週別売上（税抜SGD） |
| --- | --- | ---: | ---: |
| 2028-W28 | DC実出荷 | 1 | 1,488 |
| 2028-W29 | 代理店受入・代理店leaf実出荷 | 0 | 0 |
| **2週合計** | **1ロット・24個** | **1** | **1,488** |

DCからの実出荷が未発生の間は計上0件。記録の欠落で出荷を確かめられない場合は未確認として計上を保留する。

## 5. 重複計上を防ぐ業務条件

1. **同じ卸売を一つの取引として照合する。** この例では、売り手・買い手・卸売区間・Lot_IDの組で出荷、受入、leaf実出荷を突き合わせる。計上週や事象が異なっても、この組で対応するものは同一の卸売として扱う。
2. **一つの試算で採用する計上事象は一つ。** その事象だけを根拠に、同じ卸売の有効な売上明細を最大1件とする。ほかの事象やPPC・Value Chainの並行集計は照合に使い、売上に加算するのは採用した明細1件に限る。代理店leafの実出荷は物流上の観測に使う。
3. **同じ記録の再取込・再計算でも1件。** 根拠記録の訂正で計上週が変わった場合は、同じ取引の計上結果を差し替え、訂正後の週に1件だけが有効になるようにする。

同じ実出荷記録を再入力した場合も、上表の件数と金額を期待する。代理店の受入やleafの実出荷が後続週になった場合も、同じ卸売の計上はDC実出荷週に1件とする。

## 6. 根拠と確認範囲

- **採用済みのモデル前提**　1ロット24個、外部代理店へのsell-in、販社から代理店への税抜卸単価。価格は金額仮定書の本文v0.2 §0・§2.2・§5.1 M1と、M0付録の価格CSVを照合した。 [金額仮定書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md) · [Value Chain価格CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/vc_price_rule.csv#L5) · [PPC価格CSV](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_market_price.csv#L7) · [化粧品設計 v0.5 §6 D3](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.5.md#L288)
- **今回の確認**　指定コミットの文書と価格CSVを確認し、期待金額を手計算した。M0の元の出荷明細とPPC台帳はGit管理外のため、観測週の確認は報告書T13まで。WOMの再実行による検証は後続工程。 [M0報告書 §7](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L494-L516)

## 7. 受入時認識との比較

比較した案Bは、代理店の受入までシンガポール販社に支配があり、全量の受入が引渡し完了を示す取引に適用する。この前提で同じ事象を評価した場合、W28は0 SGD、W29は1,488 SGDとなる。M0のPPCもW29に計上したが、M0で使った事象はleaf実出荷（S）で、案Bの根拠は受入（P）である。 [M0試行依頼書 v0.2 §1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7777b2a006421655baa9ad4e8891006512da9ca2/requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun.md#L40-L55)

## 8. 設計・検証への引き渡し

- **設計担当**　採用した実出荷事象、卸売取引の照合条件、単価をWOMの既存データと外部売上明細に対応付け、§4・§5をどこまで既存の仕組みで表せるか確認する。
- **検証担当**　入力の原本と採用した業務ルールから売上週・金額・明細件数を独立に導き、§4・§5の期待値と試行出力を照合する。
