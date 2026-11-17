# 在庫の保管費・保有費｜業務定義案 v0.1

2026-11-17 ・ GPT-MC ・ **採用（大杉さん 2026-11-17、下の判断の欄の変更を含む）**

> **大杉さんの判断（2026-11-17）**（Claude君がリポジトリの実物と照合した上で）
> 1. 最初は**在庫に資金を寝かせる費用（資本拘束分）**から試す。倉庫への追加の支払いは、契約の額が分かってから別に扱う（§6 の推奨どおり）。
> 2. 原価は**内部の利益を除いた連結原価**（`vc_inventory_weekly.csv` の `group_hq`）を使い、週末の所有法人の負担とする。
> 3. **移送中の在庫を含める**。助走（2026-W37〜W53）の在庫の費用は別欄に出し、回収できるかの判断に含める。
> 4. **年率 5%・10%・15% で感度を試す**。採用する率は未設定のまま。
> 5. **比べる週数を直す**：この定義は依頼の時点（`584af05`）の数え方で、全期間の増産を 158 週としている。大杉さんが 2026-11-17 に増産の有償の週を「計画の生産量を引き上げた週の範囲」で数えると決めた（`a48eb57`）ので、**全期間の増産は 173 週、88 週の案との差は 85 週**。§4 の式の `70` は `85` に読み替える：確保費の節約 `85 × f`、同額になる週額 `f* ＝（r × ΔB ＋ ΔS）÷ 85`、同額になる週率 `r* ＝（85 × f − ΔS）÷ ΔB`。到達点 5 の組（101 週の案 C07 と全期間の増産 C06）では差は 72 週。§1 の表の「158 週」と §5 の検算例の「70」も同じ読み替え（検算例の式の形と率の計算は正しい）。
> 6. **計算は比較の道具の側で行い、Value Chain の `holding_rate_weekly` は空欄のままにする**。今の Value Chain の欄は法人の帳簿原価で計上するので、使うと 2 と違う額になり、比較の別欄との二重引きの元にもなる。依頼書：`requests/RequestLetter_Cockpit_HoldingCost_Sensitivity_to_CodeKun.md`。

**読取基準**　`Yasushi-Osugi/wom_development_composite_node` の `wom-v1r6m0_BS-SEAF`、`584af05dd6bd811e6118b09e3bbe6ca8f88adf69`。依頼書を追加したコミットを参照した。[参照コミット][revision] ・ [依頼書 v0.1 §§1–4][letter]

まず、**連結原価で評価した週末在庫に資本拘束の週率を掛ける**。増産の確保を158週から88週へ短くしたとき、節約する70週分の確保費で、増えた在庫を持つ費用を賄えるかを比べる。倉庫への追加支払いは、契約で把握できたサービスを別費目として追加する。到達点5の需要・数量・画面の受入と並行して行う。[ロードマップ v0.4 §3.2][roadmap] ・ [到達点5の判断票][decision]

## 1. 比較条件と確認した現行前提

| 化粧品・後期投入の比較 | C02 全期間増産 | C03 88週増産 |
| --- | ---: | ---: |
| クリーム納品／タイのクリーム期末未充足 | 1,768 lot／0 lot | 1,768 lot／0 lot |
| 控除前の連結試算利益 `P0`、報告期間 | 616,860,840円 | 616,860,840円 |
| 増産の確保費が発生する週（助走の対象週を含む） | 158週 | 88週 |
| クリームの週末在庫の合計（全計画期間） | 26,989 lot・週 | 29,754 lot・週 |
| クリームの最大年齢（先入れ先出し） | 24週 | 27週 |

C03のクリーム在庫は2,765 lot・週多い（約10.2%）。製品・所在・週によって原価が異なり得るため、境目の計算には両案それぞれの**週末の連結在庫原価**を使う。到達点5の予備試行では、強い需要の立ち上がりで在庫が減る案もあった。醤油の瓶詰18→21シフト試行の在庫＋23.7%も、同じ方法で原価の週別差を測る候補になる。[段4の試行報告 §§1.2–1.3][trial] ・ [C02・C03の比較出力][c23] ・ [醤油の比較報告 §§2.2–2.5][soy]

| 現行の扱い | 確認した内容 |
| --- | --- |
| Value Chainの保有費 | `vc_config.csv` の `holding_rate_weekly` は化粧品・Cookie・醤油（配分版）で空欄。設定すると、毎週末、評価済みのグループ所有在庫（輸送中を含む）の**所有法人の帳簿原価**に週率を掛けて、その週の期間費用 `holding` に計上する。 |
| 連結とPPC | 現行の保有費は連結範囲の法人の費用として `profit_r2_hq_wk` に入る。PPCに週末在庫に対する保有費はない。比較に使う `P0` は報告期間のValue Chainの消去後連結試算利益。 |
| 既存の倉庫費 | `WH_JP_Released` の `warehouse_cost` は30円／個。「保管・出荷」の数量比例費用で、Value Chainでは当該ノードでの受入時に期間費用として計上する。24個の受入なら720円。 |

[化粧品設定][cfg] ・ [Cookie設定][cookie] ・ [醤油設定][soycfg] ・ [設定の読込][masters] ・ [Value Chain週末処理][ledger] ・ [連結の費用集計][views] ・ [倉庫費の規則][nodecost] ・ [倉庫費の計上][receipt] ・ [比較の利益集計][compare]

## 2. 費用の範囲・算定基礎・負担（提案）

| 費目 | 適用・負担と算定 |
| --- | --- |
| **在庫保有費（資本拘束分）** | 初回の推奨。各週末に連結範囲の法人が保有する評価済み在庫の、**内部利益消去後の連結原価**（報告通貨JPY）に、共通の週率を掛ける。計画比較の管理上の費用とし、週末の所有法人ごとに帰属を示す。 |
| **保管費（倉庫の実費）** | 追加の倉庫料を把握できた段階の選択肢。倉庫・費目ごとの契約上の課金量（例：ケースまたはパレット）×課金週×単価。課金単位や端数・最低保証は契約に従う。費用は倉庫サービスの支払義務を負う法人に、サービスの週で帰属させる。支払日は決済記録で別に追う。 |
| **両方を入れる条件** | 機会費用の率に含めた費目と、倉庫契約等で別計上する費目を照合し、個々の負担を一度だけ反映する。倉庫の固定契約は増床・外部委託など案で負担が変わる範囲を捉え、両案共通の額は差額で相殺する。 |

初回の週率は資本拘束分に限る。陳腐化・減耗・保険料は、廃棄・評価減、保険契約、既存の費用との対応が分かれば個別に評価する。資本拘束分は比較利益の調整額として扱う。実際の仕入・加工・運賃等が同額なら、連結原価方式の保有費は法人間価格の変更で動かない。所有法人の帳簿で負担を見る場合は、現行の帳簿原価方式を対照に使える。[MIT CTL「Inventory Holding Cost」][mit] ・ [Value Chain設計 D-3・D-5][design]

| 在庫の所在・状態 | 初回の保有費での扱い |
| --- | --- |
| 工場側・倉庫・DC・自社チャネル手前 | 評価済みのグループ所有在庫を含める。日本の工場・倉庫とタイDCは `E_JP`、シンガポールDC・直営店等は `E_SG`。原材料・仕掛品は在庫出力に原価付きで表れる範囲で含める。 |
| 輸送中 | 週末の在庫所有法人に帰属。出荷・受入の両地点で同じ在庫を加算せず、週末の所在1か所で数える。倉庫料の課金対象は契約で指定された保管場所。 |
| 外部の代理店・顧客 | 支配移転後は対象外。G3の卸売はDC出荷で支配が移るので、代理店の受入やその後の販売まで保有週を延長しない。 |
| 所有中だが価額未評価 | 評価できた分に金額を付け、残りの所在・SKU・週・lot数を表示する。費用全体は「一部未評価」とし、影響する採算の順位を保留する。 |

[法人とノードの割当][assign] ・ [連結範囲][entities] ・ [WOMのD-2・輸送中在庫の定義][design] ・ [Start Here R12・R13][rules] ・ [Start Here G3・G5][g3]

## 3. 期間、率、二重控除の防止

**週末スナップショット**は、その週の出荷・受入を反映した後の残高を、在庫所有法人・所在・SKUごとに数える。持ち越した在庫は、在庫が残る週末ごとに1回。週内に全量を払い出して週末に残らない分は、その週の保有費の対象外。週中の日数に応じた倉庫料は、実費の課金記録で評価する。

| 集計欄 | 対象期間 |
| --- | --- |
| 報告期間の `P0` と保有費 | **2027-W01〜2029-W52（156週）**。`P0` は `vc_v3_weekly.csv` の `GROUP`・`in_report` の `profit_r2_hq_wk` を合計する。 |
| 助走の保有費 | **2026-W37〜2026-W53（17週）**の所有在庫を、報告期間と別欄に出す。報告期間の供給に向けた実運用の作り置きを表すと採用した場合、採算比較では助走分も加える。 |
| 採算比較の費用 | 両案の費用に同じ期間・範囲を指定する。推奨は、報告期間の `P0` に対し、**報告期間の保有費と助走の保有費の両方**で回収可否を確かめ、助走分を内訳で示す方式。増産確保費は採用済みの有償週（助走対象週を含む）で数える。全計画期間の損益を比較する場合は、`P0` も同じ173週にそろえる。 |

[化粧品サンプルの計画期間][sample] ・ [増産確保費の採用記録][raise] ・ [C02・C03の有償週の出力][c23fixed]

**感度の仮置き**は年率5%／10%／15%。年率は資本が拘束されることの負担を表す評価用の仮定で、実際に適用する率は大杉さんの設定待ち。週率は年率（比率）÷52で単利換算し、2026-W53を含む対象ISO週を1週ずつ数える。異なる長さの期間を年率に換算し直す処理は要らない。

| 感度 | 年率 | 週率（%） | `holding_rate_weekly` の入力例（比率） |
| --- | ---: | ---: | ---: |
| 低 | 5% | 約0.096154% | 0.000961538461538 |
| 中 | 10% | 約0.192308% | 0.001923076923077 |
| 高 | 15% | 約0.288462% | 0.002884615384615 |

**同じ支払い・費用の照合**。倉庫契約または請求の明細を、費目・サービス・対象所在・負担法人・週で既存費用と照合する。`warehouse_cost` 30円／個、DCの取扱費、既計上の運賃・保険に含まれる費用は追加控除0件。たとえば倉庫料のうち既存の30円に含まれる部分はそのまま引き継ぎ、別建ての保管料は内訳を確認できた増分だけを足す。G4・G5で適格な運賃や関税が在庫原価に入っている場合、その残高を資本拘束分の基礎に使う。外貨の別建て保管料はサービス週の共通の為替規則でJPYに換算する。[ノード費用入力][nodecost] ・ [WOMのD-3][design] ・ [Start Here R11][fx]

- **推奨の連結原価方式**では、保有費を含める前の `P0` を使い、比較の別欄で一度だけ控除する。
- **現行設定の感度試行**では、`holding_rate_weekly` で生じる期間費用が既に連結利益に含まれる。費用明細 `kind=expense`、`scope=period`、`family=holding` を照合し、同じ週・費目分の外側の控除を0件にする。報告期間外の助走分を採算の別欄に加える場合は、その助走分だけを使う。[週末の保有費明細][ledger] ・ [連結の費用集計][views]

## 4. 88週案と158週案の境目

案別に、対象期間の評価済み連結在庫原価を全週分合計した額を `B`（円・週）、週率を `r`、増産の共通週額を `f`（円／週）、追加の倉庫実費を `S`（円）とする。資本拘束分の保有費は `r × B` 円。販路費は同じ後期投入で同一条件なので差額では相殺する。

| 照合欄 | C03（88週） − C02（158週） |
| --- | --- |
| 控除前利益の差 | `ΔP0 = 0円`（報告期間の観測） |
| 増産確保費の節約 | `(158 − 88) × f = 70 × f` |
| 保有費と保管実費の追加 | `r × ΔB + ΔS`。各差はC03 − C02。 |
| 控除後利益の差 | **`ΔP0 + 70 × f − r × ΔB − ΔS`** |
| 両案が同額になる増産の週額 | **`f* = (r × ΔB + ΔS) ÷ 70`**（この比較は `ΔP0 = 0`）。正の境目がある場合、これを上回る週額ではC03が上。 |
| 両案が同額になる在庫保有費の週率 | **`r* = (70 × f − ΔS) ÷ ΔB`**（`ΔB > 0`、`ΔP0 = 0`）。正の境目がある場合、これを上回る率ではC02が上。年率表示は `52 × r*`。 |

`ΔB = 0` なら保有率による差は0円。 `ΔB < 0` なら率が高いほどC03の差額は増える。非負の実用範囲で同額にならない場合は「正の境目なし」などの理由を示す。算定に必要な率・週額が未設定でも、他方の値を明示した感度ごとの境目、または同額条件の式を出せる。原価の週別差が未評価なら数値の境目は「未算出」。両案の実額の採算順位は保留とする。

**表示**は「未設定」（率・契約条件の入力待ち）、「明示0」（0と設定）、「未評価／一部未評価」（原価等の不足）、「対象外」（選んだ費用範囲の外）を区別する。0設定では、週別の基礎と明示0を表示して費用0円で計算する。比較画面は `P0`、報告期間・助走別の対象原価と費用、未評価の数量、確保費の差、控除後の差と境目を表示する。最終的な採否は大杉さんが判断する。[Start Here R12–R13][rules] ・ [報告期間の未評価判定][p0]

## 5. 検算値と既存機能での試行

**代表週**。G5報告のシンガポール向けクリーム1 lot（24個、出荷記録 `ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:93:0`）は、2028-W25・W26の週末に `E_SG` の輸送中在庫。連結原価47,520円（46,080円＋運賃1,440円）、法人帳簿原価120,000円。年率10%を仮定して比較する。G5報告で観測したのは原価・所在であり、以下の費用は手計算の期待値。[G5報告 §1 B1・§3.1 V1〜V5][g5]

| 比較方法 | 2028-W25末の1 lot分 | W25・W26の2週分 |
| --- | ---: | ---: |
| 推奨の連結原価方式 | 47,520 × 0.10 ÷ 52 ≒ **91.38円** | **182.77円** |
| 現行の法人帳簿原価方式 | 120,000 × 0.10 ÷ 52 ≒ **230.77円** | **461.54円** |
| この在庫の倉庫料 | 輸送中なので対象外 | 対象外 |

丸めは同じ期間の明細を合計してから表示に適用する。W30の外部販売後、このlotの週末保有費は0円。倉庫側の検算では、日本の倉庫でクリーム24個を1回受け入れる場合、既存の720円を受入週に1件計上する。翌週まで保管しても同じ受入に対する既存規則での追加額は0円。別建て保管料は契約待ちの間「未設定」と表示する。[倉庫費の規則][nodecost] ・ [受入時の費用処理][receipt]

**全体比較の検算例**。例として両案の有効な原価・週の差を **1億3,000万円・週**、増産費を **5,000円／週**と置く。倉庫の追加実費はこの例の対象外。原価・週の差と週額は計算を確かめるための仮定で、2,765 lot・週を金額換算した観測値ではない。

| 仮の年率 | C03が節約する増産確保費 | C03の追加保有費 | 控除後の利益差（C03 − C02） |
| ---: | ---: | ---: | ---: |
| 5% | 350,000円 | 125,000円 | ＋225,000円 |
| 10% | 350,000円 | 250,000円 | ＋100,000円 |
| 15% | 350,000円 | 375,000円 | −25,000円 |

この例では年率 **14%**で同額（350,000円 ÷ 130,000,000円・週 × 52）。年率10%に固定すると増産確保費の境目は **約3,571.43円／週**（250,000円 ÷ 70）。境目の判定は丸め前の額を使う。

### Claude君・Code君への受け渡し

1. **報告の再現**。C02・C03の同じ写し・同じ計画で、週率が空欄の連結利益、158／88週、納品・在庫の数量を照合する。現行設定の感度は、写しで空欄、明示0、低・中・高を個別に指定し、`vc_checks.json` の設定と `vc_money_lines.csv.gz` の `holding` を照合する。空欄は明細0件、明示0は金額0円。各案の空欄からの連結利益減少額は、同じ期間・連結範囲の保有費明細の合計と一致する。期末在庫、数量、既存費用の額、出荷結果も照合する。
2. **原価基礎を変えた場合の感度**。`vc_inventory_weekly.csv` を、連結対象の所有法人、`external=0`、`valued=1`、対象週で絞る。各案の `group_hq` を週・SKU・所有者・所在別に集計し、全対象の合計は `vc_v3_weekly.csv` の `inv_group_hq` と照合する。未評価数量は別に集計する。集約済みの在庫CSVはlot別の行を持たないため、代表lotは出荷・入出庫の明細で追い、週末残高と照らす。外部の表で差と境目を手計算できる。
3. **反映先の判断**。連結原価での計算をValue Chain内に持つ場合は、現行の法人帳簿原価固定の算定基礎を選べるようにする変更が必要。既存の週末出力から比較表に載せる場合は、比較の道具への反映で足りる。倉庫料を自動計算する場合は、所在別の契約・課金単位・期間を結び付ける設計が要る。[週末在庫の列定義][ledger] ・ [連結在庫の集計][stock] ・ [出力ファイルと確認欄][run]

## 6. 大杉さんに決めていただくこと

| 判断すること | 推奨 |
| --- | --- |
| 初回はどの費用を入れますか。 | **在庫に資金を置く費用から試し、倉庫への追加支払いは契約額が分かってから別に扱う。** |
| どの原価を使い、誰の負担にしますか。 | **内部利益を除いた連結原価を使い、週末の所有法人に帰属させる。** 倉庫料の負担は契約で決める。 |
| 輸送中や助走の在庫も含めますか。 | **グループ所有の輸送中在庫を含め、助走の在庫費用も別掲して回収可否に含める。** 実運用の準備として扱う範囲を採用時に確認する。 |
| どの率で試行し、いつ採算を判断しますか。 | **5%・10%・15%の年率で感度を試し、採用する実額は未設定とする。** 原価の差と増産の有償週を照合した後に、順位が変わる条件を判断する。 |

## 読取・確認の範囲

指定版で依頼書、ロードマップ v0.4 §3.2、判断票、採用済みの増産確保費の定義、段4・G5の報告、C02・C03の公開比較出力、現行設定と関連コードを読んだ。公開比較出力で利益・週数・lot・週を照合し、代表週と感度例を検算した。C02・C03の週別の原価残高の原票、倉庫契約、実際の資本コストは未確認。現行WOMでの感度試行と、両案の実際の境目は、週別原価の取得後に確認する。[公開比較出力][c23] ・ [計画出力の所在][trial]

[revision]: https://github.com/Yasushi-Osugi/wom_development_composite_node/commit/584af05dd6bd811e6118b09e3bbe6ca8f88adf69
[letter]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/requests/RequestLetter_WOM_Cockpit_HoldingCost_to_GPT_MC_v0.1.md
[roadmap]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/design/drafts/Roadmap_WOM_Management_Cockpit_Product_Market_v0.4.md#L115-L121
[decision]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/design/drafts/WOM_Cockpit_Milestone5_Decision_v0.1.md#L6-L21
[trial]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/development/WOM_Cockpit_Stage4_Trial_Report.md
[c23]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/development/WOM_Cockpit_Stage4_Trial_appendix/cos/C02__C03/comparison_summary.md#L37-L62
[c23fixed]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/development/WOM_Cockpit_Stage4_Trial_appendix/cos/C02__C03/fixed_cost_breakeven.csv
[soy]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/development/WOM_Cockpit_Stage4_Shifts_RegionMap_Report.md#L58-L117
[cfg]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/cosmetics-sg-th-2027-2029/vc_config.csv#L1-L5
[cookie]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/Cookie-jp-2026/vc_config.csv#L1-L5
[soycfg]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/soysauce-jpy-2027-alloc/vc_config.csv#L1-L5
[masters]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/wom/valuechain/masters.py#L184-L193
[ledger]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/wom/valuechain/ledger.py#L767-L805
[receipt]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/wom/valuechain/ledger.py#L729-L765
[views]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/wom/valuechain/views.py#L120-L154
[nodecost]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/cosmetics-sg-th-2027-2029/ppc_node_cost_rule.csv#L6-L13
[compare]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/tools/compare_scenarios.py#L296-L346
[mit]: https://ctl.mit.edu/sites/ctl.mit.edu/files/attachments/S2%20-%20Aug%204%20-%20W2%20-%20SCx_KeyConcepts.pdf
[design]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L11-L67
[assign]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L12-L21
[entities]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/cosmetics-sg-th-2027-2029/vc_entity.csv#L1-L6
[fx]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/WOM_Start_Here.md#L91
[rules]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/WOM_Start_Here.md#L92-L93
[g3]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/WOM_Start_Here.md#L205
[sample]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/data/sample/cosmetics-sg-th-2027-2029/README.md#L25-L39
[raise]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/design/drafts/WOM_Cockpit_PlannedOutputCost_Business_Definition_v0.1.md#L3-L13
[p0]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/tools/compare_scenarios.py#L720-L728
[g5]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_Report.md#L38-L105
[stock]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/wom/valuechain/views.py#L178-L237
[run]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/584af05dd6bd811e6118b09e3bbe6ca8f88adf69/wom/valuechain/run.py#L150-L212
