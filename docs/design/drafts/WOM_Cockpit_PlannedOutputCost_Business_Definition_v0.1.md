# 化粧品のクリームの計画生産量を上げる費用｜業務定義案 v0.1

2026-11-13 ・ GPT-MC ・ **採用（大杉さん 2026-11-15）**

> **大杉さんの判断（2026-11-15）**
> 1. 費用の形は **§2 の推奨＝週・期間の確保費**（`E_JP` が追加シフト・要員を有償で確保した週に負担。作らなかった週も含む）。実績連動は対照案として残す。
> 2. 有償の期間は **助走の週を含める**（助走に作った分は報告期間の売上になるため、利益だけを数えて費用を外さない）。
> 3. 週額は **未設定のまま**。比較の表と画面では「未設定」と出し、採算の順位は保留する。境目だけを表示する。
>
> **確保の期間の数え方（Claude君が設計として置く。違えば大杉さんが直す）**：その案で週 11 良品 lot を作る**最初の週から最後の週まで連続**して有償とする（助走を含む）。§4 の表の「助走も有償で全計画の週を確保（感度）」＝ 173 週は、その上限にあたる値（境目 後期 約 57,744 円／週・早期 約 108,927 円／週）。案ごとの実際の週数は、比較の道具で実測して置き換える。
> **実績連動の 158／166 lot の行は、確保の形では使わない**（あちらは「週 11 を作った週だけ払う」契約の値）。

**読取基準**　`Yasushi-Osugi/wom_development_composite_node`、`wom-v1r6m0_BS-SEAF`、`3c3d67717228a9912eb12465f2a18c45d479072e`。指定ブランチの先端を確認し、そのコミットの依頼書と添付が一致することを確認した。先に読んだ `cec4eb3` からの差分は比較画面の設計案の追加1件で、依頼書・報告書・付録は一致する。[指定コミット][revision] ・ [依頼書 v0.1 §§1–4][request] ・ [コミット間の差分][diff]

日本工場のクリームの計画生産量を上げる採算と、上げた場合にタイの早期投入を組み合わせる採算を判断する。初回は販路の週固定費と同様、比較表の別欄で費用を控除する。ロードマップ案 v0.3 §0の到達点2で得た試行値を用いる。対象は `Factory_JP` の `COS_Cream` の計画値 `cap_soft` を週11から12へ上げる条件。物理上限 `max_supply` は13で、計画は大杉さんの方針どおり soft を使う。[ロードマップ案 v0.3 §0][roadmap] ・ [Code君の報告書 §0・§2][report0]

## 1. 比較条件と確認した結果

`P0` は報告期間 **2027-W01〜2029-W52（156 ISO週）**の Value Chain の消去後連結試算利益（JPY）。`vc_v3_weekly.csv` の `GROUP` のうち `in_report` の週について、`profit_r2_hq_wk` を合計する。以下は全SKUの連結値。比較は同じC3a、配分なしの4案で行う。早期・後期で供給方針を当てた `A_late`・`A_early` は別の試行。[Code君の報告書 §0–§2][report0] ・ [基準の観測報告 §3 O3][observe]

| 案 | タイ投入週 | `cap_soft`／良品計画上限（lot／週） | クリーム納品／タイ未充足（lot） | `P0`（円） | 販路の有償週数 `W` |
| --- | --- | ---: | ---: | ---: | ---: |
| 後期・上げない（基準後期） | 2028-W01 | 11／10 | 1,680／88 | 606,871,080 | 104 |
| 早期・上げない（基準早期） | 2027-W27 | 11／10 | 1,680／166 | 606,871,080 | 130 |
| 後期・上げる（`B_late`） | 2028-W01 | 12／11 | 1,768／0 | 616,860,840 | 104 |
| 早期・上げる（`B_early`） | 2027-W27 | 12／11 | 1,846／0 | 625,715,400 | 130 |

増産による `P0` の差は後期 **9,989,760円**（納品＋88 lot）、早期 **18,844,320円**（＋166 lot）。増産した2案の早期 − 後期は **8,854,560円**（＋78 lot）。この金額は販路の週固定費と増産の追加費用を控除する前の観測値。販路維持費の対象・有償週の条件は大杉さん採用済みで、週額 `f` は未設定。増産費用の条件・額は今回の判断対象。[Code君の報告書 §4 O3–O4][report4] ・ [販路の週固定費の業務定義 v0.1 §§2–4][channel] ・ [付録 C2の境目][cmp2] ・ [C3の比較値][cmp3]

## 2. 増産費用の発生条件（提案）

**推奨は、週11良品lotを計画できるようにする追加シフト・要員の確保費を、確保を約した有償週に負担する案。** `cap_soft` を変える計画上の事象は、必要な期間を特定する根拠に使う。費用の発生は、有償の要員配置やシフトの確保を約したことを根拠とする。

| 費用 | 負担・発生の根拠 | 単位と比較への入れ方 |
| --- | --- | --- |
| 週・期間の確保費（推奨） | 工場を持つ `E_JP` が、追加枠を確保する従業員・人員の手配先等に支払う想定。承認したシフト表、配置の合意、手配条件を根拠に、有償の開始週から終了週まで負担する。確保済みなら良品が10 lot以下または0の週も負担する。 | `g` 円／有償週 × 発生週数 `T`。追加枠ごとに各週1件を比較表で計上。期間契約が一括定額なら、契約額と報告期間に帰属する額を示す。 |
| 実績に応じる割増（対照案） | `E_JP` が実際に発生した追加残業の割増、増員の従量分、外注の追加対価を負担する想定。作業時間・受入・給与明細・請求明細で発生週と課金単位を確認する。 | 残業なら追加の有償時間 × 対象の増分単価。追加の良品lotで課金する例は `u` 円／対象lot × 工場の対象lot数 `Q`。 |

最初の感度比較は、同じ円建て週額で連続する期間の確保費を置く。上げる・戻す判断はシフト編成・人員の手配を見直せる期間の切れ目で行う。週単位で手配・解除できる契約が確認できる場合は、その週ごとの有償確保で `T` を数える。確保期間を変えて生産可能な週も変わるなら、その計画条件で数量・`P0` を取り直す。同じ手配の確保費は、案・負担法人・工場・SKU・有償週を照合して1回控除する。給与・外注代の支払週は、作業・確保の費用発生週と併記する。

**加工費との照合**。クリームの標準加工費は工場で600円／個（24個なら14,400円／良品lot）。原料と通常の数量比例加工費は既に試算利益に反映される。比較表の追加費用は、同じ増産分の標準加工費に含まれていない割増・確保費に限る。外注が既存の加工を置き換える場合は、重なる標準費用の範囲を照合して差額を用いる。週額と従量額を併用するなら、最低保証・割増・外注請求の内訳を突き合わせ、同じ手配・作業の負担を一度計上する。[工場の法人割当][assignment] ・ [標準加工費CSV][conversion] ・ [正式サンプルの数量単位・原価前提][sample] ・ [Code君の報告書 §7 D1][decision]

## 3. 費用発生週と工場の実績を数える

| 区分 | 週・数量の扱い |
| --- | --- |
| 主比較に算入する確保費 | 有償確保のISO週と報告期間の共通部分を両端含みで数える。初回の検算では上げる2案とも報告期間の全156週を有償と仮定し、上げない2案の追加枠は対象外。開始・終了の実際の条件は未設定。 |
| 助走 2026-W37〜W53（17週） | `P0` と同じ期間で比べる主表では期間外。有償の要員・シフトを現実の準備にも手配するなら、報告期間外の増産費を別欄で把握し、意思決定の感度に含める。モデルの助走をそのまま現実の契約期間とするには、準備活動と手配の根拠が要る。 |
| 工場の実績連動 | 同じ投入週の基準と増産の工場生産をISO週で照合する。今回の `u` の例は良品10 lotを超えた増産分を課金対象とし、上げる案の `Q` は `Σ max(工場の週別良品lot − 10, 0)`。実際の支払が残業時間・外注の受入数で決まる場合は、その記録を分母にする。 |

工場出荷相当の良品数（`handoff_to_sp`）を、報告書 §4 O3と付録の未使用週から照合した。通常計画で良品10 lotが基準。増産2案は報告期間内の2029-W47・W48に10 lot、W49〜W52に0 lotで、ほかの150週は11 lot。期末の少量・ゼロは報告書の計画境界の条件に留意する。[Code君の報告書 §4 O3・O7][report4] ・ [付録 C2の工場の未使用週][idle] ・ [工場の集計根拠][measure_script]

| 上げる案 | 助走の11 lot週／対象追加lot | 報告期間の11 lot週／対象追加lot | 全計画の11 lot週／対象追加lot | 全計画の良品総量（lot） |
| --- | ---: | ---: | ---: | ---: |
| 後期 | 8 | 150 | 158 | 1,768 |
| 早期 | 16 | 150 | 166 | 1,846 |

報告期間の工場良品総量は基準2案が各1,520 lot、増産2案が各1,670 lot（差は各150 lot）。助走に生産を寄せる量も案で変わるため、納品増88／166 lotと、週10 lotを超えた工場の課金対象量は別に記録する。検算では報告期間のW47・W48（10 lot）とW49〜W52（0 lot）は確保費が各週1件、実績連動の追加lot費は0件。助走の2026-W45は後期10 lot、早期11 lotで、実績連動の対象は後期0 lot、早期1 lot。[付録の計測値][measure] ・ [付録 C2の工場の未使用週][idle] ・ [基準の観測報告 §3 O6][observe_factory]

## 4. 4案の控除後利益と順位の境目

販路の週額を `f` 円、案別の増産費を `C_L`（後期）・`C_E`（早期）とする。確保費だけなら `C = g × T`、実績連動の追加lot費だけなら `C = u × Q`、別個の費用を併用する場合は `C = g × T + u × Q`。初回は円建て、対象週ごとに同額と置く。外貨の契約を使う場合は発生週の共通の為替規則でJPYに換算し、案別に積み上げる。

| 案 | 控除後利益（円） |
| --- | ---: |
| 後期・上げない | `606,871,080 − 104f` |
| 早期・上げない | `606,871,080 − 130f` |
| 後期・上げる | `616,860,840 − 104f − C_L` |
| 早期・上げる | `625,715,400 − 130f − C_E` |

| 判断する比較 | 控除後の差と境目 |
| --- | --- |
| 後期で上げるか | `9,989,760 − C_L`。同じ販路費が相殺される。追加費用が9,989,760円で同額。 |
| 早期で上げるか | `18,844,320 − C_E`。同じ販路費が相殺される。追加費用が18,844,320円で同額。 |
| 上げる場合に早期か | `8,854,560 − 26f − (C_E − C_L)`。同額となる販路週額は `(8,854,560 − (C_E − C_L)) ÷ 26`。増産費が両案同額なら **340,560円／週**。費用差が8,854,560円なら `f=0` で同額、それを超えるなら非負の `f` で後期が上。 |
| 上げない場合に早期か | `−26f`。`f=0` で同額、正の週額で後期が上。 |
| 早期と増産を組み合わせるか | 後期・上げない案に対し `18,844,320 − 26f − C_E`。早期・上げる案を選ぶには、後期・上げる案との上の差も確認する。 |

**増産費の単価の境目**。同じ投入週の基準と比較し、単独の費用なら `g* = ΔP0 ÷ T` または `u* = ΔP0 ÷ Q`。両方ある場合の同額条件は `g × T + u × Q = ΔP0`。例えば `u` が既知なら `g* = (ΔP0 − u × Q) ÷ T`。分母が0なら当該費用による順位変化はなし。分母が未設定、または連結利益が未評価なら「未算出」と理由を表示する。

| 費用を単独で課す仮定 | 分母（後期／早期） | 後期の境目 | 早期の境目 |
| --- | ---: | ---: | ---: |
| 報告期間に週定額で確保（主比較） | 156／156週 | 約64,036.92円／週 | 約120,796.92円／週 |
| 報告期間の追加良品lotだけに課金 | 150／150 lot | 66,598.40円／lot | 125,628.80円／lot |
| 助走も有償で全計画の週を確保（感度） | 173／173週 | 約57,744.28円／週 | 約108,926.71円／週 |
| 助走にも実績連動の追加lot費を負担（感度） | 158／166 lot | 約63,226.33円／lot | 113,520.00円／lot |

下2行は報告期間の利益増分で期間外の追加負担も回収できるかを見る感度。全計画期間の損益として比べる場合は、`P0` も全計画期間にそろえる。実績連動の助走費まで含めると、増産2案の早期の追加負担は後期より `8u` 円多く、販路の境目は `(8,854,560 − 8u) ÷ 26` 円／週になる。境目の判定は丸める前の値で行う。

**未設定と明示0円**。販路費・増産費はそれぞれ「未設定」「明示0円」「設定済み」を表示する。追加枠を持たない案の増産費は「対象外（控除0円）」。適用する費用額が未設定なら、その案の控除後利益は「未算出」。明示0円は金額0円で計算する。以下は連結利益・発生週数など、式に必要な条件がそろう場合の表示案。[Start Here R12–R13][start] ・ [Code君の報告書 §1][report0]

| 未設定の費用 | 比較表で示せるもの |
| --- | --- |
| 販路費のみ | 4案の控除後利益は未算出。同じ投入週で増産を比較する差は、販路費が相殺されるため算出できる。増産2案の販路費の境目は、既知の増産費差で調整する。 |
| 増産費のみ | 基準2案の控除後利益を表示。増産2案の控除後利益は未算出。同じ投入週の増産費の境目と、早期・後期の同額条件を表示する。 |
| 両方 | 4案の控除後利益は未算出。増産費の計算方式と分母を仮定した境目、増産費が同額の場合の販路費の境目を表示できる。双方の費用差が残る比較は同額条件の式を表示する。 |

## 5. 手計算の検算例

販路 `f = 200,000円／週`、増産の有償確保 `g = 80,000円／週`、上げる2案は報告期間156週、従量費は対象外と仮定する。金額は検算用で採用額は未設定。

| 案 | `P0`（円） | 販路費（円） | 増産確保費（円） | 控除後利益（円） |
| --- | ---: | ---: | ---: | ---: |
| 後期・上げない | 606,871,080 | 20,800,000 | 0 | 586,071,080 |
| 早期・上げない | 606,871,080 | 26,000,000 | 0 | 580,871,080 |
| 後期・上げる | 616,860,840 | 20,800,000 | 12,480,000 | 583,580,840 |
| 早期・上げる | 625,715,400 | 26,000,000 | 12,480,000 | **587,235,400** |

この例は早期・上げる案が最高で、後期・上げない案より1,164,320円上。さらに助走17週の確保費1,360,000円を増産2案に負担させると、早期・上げる案は585,875,400円になり、後期・上げない案が195,680円上になる。販路費の条件が同じでも、増産費の対象期間で4案の順位が変わる例。

## 6. 大杉さんの採用判断と受け渡し

| 判断 | 推奨と、選択で変わるもの |
| --- | --- |
| 費用の種類と負担 | **`E_JP` の追加シフト・人員の有償確保費**から試す。稼働量が下がった週にも負担が残る条件を表せる。割増が実績だけで発生するなら時間・追加lot課金へ切り替え、確保と実績の両方があれば内訳を照合する。 |
| 有償の開始・終了と助走 | **シフト・要員を有償で確保した期間**を費用の根拠とする。初回主表は報告期間との共通部分を数え、実際に負担する準備費があれば別掲して回収可否も示す。確保の期間と解除の条件は手配の根拠から決める。 |
| 金額と採算の判定 | 増産費と販路費の実額は未設定として、まず境目を表示する。確保費・割増の見積りが得られた段階で、4案の控除後利益、供給、在庫・製品年齢を並べ、増産の採否と早期投入との組合せを判断する。 |

採用後、Claude君に、期間と単価の根拠、4案の式、未設定の表示と検算値を渡す。後続の試行では、工場の週別生産と有償週・対象lotを照合し、販路費・増産費・`P0` を別欄で再計算する。比較画面の設計案では、増産費が未設定の間は該当する採算順位を保留し、採用後に比較の道具へ反映する。[ロードマップ案 v0.3 §0][roadmap] ・ [Code君の報告書 §7 D1・D4][decision] ・ [比較画面設計案 §§2・6–7][screen]

## 読取・確認の範囲

指定コミットで依頼書 §§1–4、ロードマップ案 v0.3 §0、採用記録付きの週固定費の業務定義 v0.1 §§2–4、Code君の報告書 §§0–2・§4 O3–O7・§7、基準の観測報告 §3、付録のC2/C3比較・工場の集計と計測、正式サンプルの法人割当・加工費、Start Here R12–R13を読んだ。付録から週数・数量を集計し、報告書と付録の `P0` から差を再計算した。賃金・シフト・外注の契約原票、割増額、`output/cockpit_cmp2/` の実行時原票は未確認。今回の検証は原本読取と再計算まで。美容液の増産、物理上限を上げる設備投資、WOMへの実装は依頼書 §4の範囲外。[指定コミット][revision] ・ [Code君の報告書 冒頭・§0][report0]

[revision]: https://github.com/Yasushi-Osugi/wom_development_composite_node/commit/3c3d67717228a9912eb12465f2a18c45d479072e
[diff]: https://github.com/Yasushi-Osugi/wom_development_composite_node/compare/cec4eb3666fa6e4b022bff2f55b18f40a35d3cd9...3c3d67717228a9912eb12465f2a18c45d479072e
[request]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/requests/RequestLetter_WOM_Cockpit_PlannedOutputCost_to_GPT_MC_v0.1.md
[screen]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/requests/Cockpit_Stage3_DesignMD_PlanCompareScreen_v0.1.md
[roadmap]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/design/drafts/Roadmap_WOM_Management_Cockpit_Product_Market_v0.3.md#L7-L36
[report0]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_Report.md#L22-L75
[report4]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_Report.md#L118-L168
[decision]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_Report.md#L203-L222
[channel]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/design/drafts/WOM_Cockpit_TH_WeeklyFixedCost_Business_Definition_v0.1.md#L1-L72
[observe]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_Observe_Report.md#L118-L132
[observe_factory]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_Observe_Report.md#L165-L170
[cmp2]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/compare_C2/fixed_cost_breakeven.csv
[cmp3]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/compare_C3/fixed_cost_breakeven.csv
[idle]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/compare_C2/factory_idle_weeks.csv
[measure]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/measure/cmp2_measure.json#L43-L204
[measure_script]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/scripts/cmp2_measure.py#L86-L112
[assignment]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L13
[conversion]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/data/sample/cosmetics-sg-th-2027-2029/ppc_node_cost_rule.csv#L5
[sample]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/data/sample/cosmetics-sg-th-2027-2029/README.md#L26-L71
[start]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/3c3d67717228a9912eb12465f2a18c45d479072e/docs/WOM_Start_Here.md#L92-L93
