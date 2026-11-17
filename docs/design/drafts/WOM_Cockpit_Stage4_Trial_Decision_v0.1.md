# WOM経営コックピット 到達点4｜試行判断票 v0.1

2026-11-16｜設計ドラフト・未採用｜参照：`wom-v1r6m0_BS-SEAF` `64372f0`

> **大杉さんの判断（2026-11-17）**：GPT君のこの判断票（v0.1）を土台に、次のとおり採用・変更した。依頼書は `requests/RequestLetter_Cockpit_Stage4_Trial_to_CodeKun.md`。
> 1. **醤油（A）は「設備の上限を 800→900 にする案」ではなく「瓶詰の計画の生産量（`cap_soft`）を 800→900 にする案」で比べる**。醤油の計画の木では瓶詰（`Bottling_Noda`）が `demand_envelope=soft`（平準化生産）と定義されているのに、`capacity_plan.csv` に `cap_soft` の列が無く、設備の上限で動いていた。写しに `cap_soft` の列を置き（瓶詰の行だけ）、醸造（`hard`）・瓶詰の設備の上限は週 1,000 lot と置く（README の「1,000 なら全需要を満たす」値）。正式なサンプルは変えない。
> 2. 化粧品（B）はこの票の 88 週（2028-W11〜2029-W46）で試し、届かなければ最大 2 回まで開始を早めて試し直す。有償の週は「生産量を引き上げた週」（入力の事実）とし、工場が実際に作ったかは別に測る。
> 3. 依頼書は 1 通、化粧品を先、醤油を後。smartx の金額の直しが commit されてから着手。

**推奨：醤油で現行の比較手順が通るかを確かめる。化粧品では、増産の期間を絞っても納品を維持できるかを並行して試す。** 下の設定値は試行案。新しい案の結果は未検証。

### A｜醤油：供給能力を変えた2案を別サンプルで比較する

**共通設定**：`soysauce-jpy-2027-alloc` の写しを使用。国内・米国・欧州の既存週別需要をそのまま使い、経営配分は両案とも適用しない。計画は `2026-W28〜2028-W52`（助走26週を含む）。空欄の `vc_config.csv` の `report_start` に `2027-W01` を設定し、報告は `2028-W52` まで。既存の価格・原価・為替・法人設定と推奨プラグインを共通にし、連結試算利益はJPYで比較する。作業作成時の在庫年齢の上限は観測用に `130週`（計画全体）とし、賞味期限の判断には用いない。

| 案 | `capacity_plan.csv` の `Soy_Sauce`、`Brewing_Noda`・`Bottling_Noda` |
|---|---|
| A0 基準 | 両工程の `max_supply=800` lot／週（既存値） |
| A1 能力を追加 | 両工程の `max_supply=900` lot／週（同じ期間の該当行のみ、助走を含む） |

**合格条件**：元需要の一致を確認し、CLIとGUIで同じ案の市場別納品・期末未充足・連結試算利益 `P0`（固定費控除前）が一致する。差が出た理由を代表週と `Lot_ID` で説明する。既存の法人間・卸価格は試算用の仮定。評価できない明細があれば、対象と理由を記録して金額の優劣は保留する。

### B｜化粧品：増産の期間を絞り、納品と確保費を比較する

**共通設定**：能力不足の後期案 C01 を起点とする。タイのクリーム投入は `2028-W01`、設備上限 `max_supply=13`、配分なし、報告期間は `2027-W01〜2029-W52`。写しの `capacity_plan.csv` で `Factory_JP × COS_Cream` の週別 `cap_soft` だけを変える（歩留まり0.97、良品上限は週10→11 lot）。

| 案 | クリームの `cap_soft` | 有償週／確認済みの納品 |
|---|---|---|
| C01 基準 | 全週 `11` | 追加の確保費なし／1,680 lot |
| C03 現行の増産案 | 全週 `12` | 158週（助走8週を含む）／1,768 lot |
| B1 期間限定案 | `2028-W11〜2029-W46` の88週は `12`、他は `11` | 同じ88週だけ有償と仮定／納品は未検証 |

**判定**：まずC01・C03の `P0`（606,871,080円・616,860,840円）を再現する。B1はC03で上限まで作った最後の週から88週を取った案。クリーム1,768 lot・タイの期末未充足0を維持し、市場別の納期と他SKUを悪化させないか、在庫量・在庫年齢（上限52週）・`P0` も照合する。届かなければ、不足の要求週からリードタイムを引き、開始を早めるか期間を延ばす。

**金額の読み方**：工場の増産可能週と、契約上の有償週を別々に記録する。同じ週額で88週だけ確保できれば、C03より70週分（約44%）の確保費が減る。これは費用の感度であり、採算は納品結果と確保条件を見て判断する。週額が未設定の間は、控除後の順位を保留する。

**次の判断**：大杉さんはAの800／900 lotとBの88週の試行条件を選ぶ。Claude君が条件を確定してCode君へ渡し、元サンプルの写しをCLIで実行してから画面で照合する。Bの結果を見て、期間指定をGUIに加えるかを決める。

根拠：[ロードマップ §3–4][roadmap] · [醤油サンプルの能力と価格の仮定][soy] · [化粧品の既知結果 §0][cosmetics] · [確保費の業務定義][cost]

[roadmap]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/64372f0f457fc5cfbe47380100ccff92248d24eb/docs/design/drafts/Roadmap_WOM_Management_Cockpit_Product_Market_v0.3.md#L91
[soy]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/64372f0f457fc5cfbe47380100ccff92248d24eb/data/sample/soysauce-jpy-2027-alloc/README.md
[cosmetics]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/64372f0f457fc5cfbe47380100ccff92248d24eb/docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_Report.md#L36
[cost]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/64372f0f457fc5cfbe47380100ccff92248d24eb/docs/design/drafts/WOM_Cockpit_PlannedOutputCost_Business_Definition_v0.1.md
