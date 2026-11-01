---
knowledge_id: WOM-DESIGN-UPPER-DEMAND-PLAN-001
title: 上位 Demand Plan — 詳細設計と実装の進め方
version: "0.3"
updated: "2026-11-02"
adoption: 提案
evidence: "コード確認（2ac9598）：handoff.py、flow_check.py、run_quantity_allocation.py、sc_tree.py、backward_planner.py。実装・実行は未実施"
basis:
  - docs/design/drafts/WOM_Upper_Demand_Plan_U4_Design_Draft_v0.1.md      # GPT君の設計ドラフト（入力・選択・出力）
  - docs/design/drafts/WOM_Demand_Priority_Allocation_Concept_Design_v0.1.md  # 構想
  - requests/BSSEAF_Cosmetics_AllocationWeekRule_U4_v0.1.md               # U4 の判断資料（v0.2）
---

# 上位 Demand Plan — 詳細設計と実装の進め方 v0.3

- 作成：Claude君（設計）。GPT君の設計ドラフト（2026-11-01）の §3〜§7 を、WOM の既存のコードに対応させて詳細にしたもの
- 位置づけ：**従来の Demand Plan（需要 CSV）の上位にある計画の機能**。元の需要 ① の全体に経営の方針を与え、供給の条件を見て供給の対象 ② を選び、外した ③ の理由を残し、実行の後に ④⑤ を元の需要へ戻して照合する。三層の **Management の層**に当たり、PSI エンジン（Backward／Forward）の前と後に置く。保護対象のコアは変えない
- 採否：全体が提案。段階 1（§8）だけを、U4 の判断（大杉さん）の後に依頼書にする

---

## 0. 従来の Demand Plan との違い

| | 従来の Demand Plan | 上位 Demand Plan |
|---|---|---|
| 持つもの | `demand_forecast.csv`（SKU × region × 週の数量） | 元の需要の台帳、方針、選択の台帳、実行の結果の照合 |
| 不足のとき | 需要 CSV をそのまま渡し、エンジンが押し戻し、届かない分が ⑤ になる。どれが ⑤ になるかは押し戻しの順 | 渡す前に、方針と供給の条件から ②③ を選ぶ。③ は理由付きで台帳に残る |
| 説明できること | 何が届かなかったか（⑤） | 何を外したか（③）とその理由、何が届かなかったか（⑤）とその原因、両者の違い |
| 元の需要 | 需要 CSV を書き換えると消える | 台帳に残る（実行用の需要 CSV は台帳から作る派生物） |

## 1. 全体の流れ（一巡）

```
元の需要（demand_forecast.csv）
   │  (1) 台帳にする                       udp_demand_ledger.csv
   ▼
方針・数量枠・供給の条件                   udp_policy.csv（任意）、udp_quota.csv、モデル
   │  (2) 選ぶ（モード 1：数量枠を固定）    udp_selection_ledger.csv
   │  (3) 時間の可否を診断する              udp_capacity_check.csv
   ▼
実行用の需要 CSV（既存の形）               demand_forecast_<plan_id>.csv
   │  (4) 既存の経路で計画（数量配分モード、ppc=False）
   ▼
Backward／Forward／Flow Check
   │  (5) 元の需要へ戻して照合する           udp_result_by_request.csv、udp_supply_runs.csv
   ▼
(6) 比べる・Owner が判断する               udp_plan.json（版・判断の番号）
```

(2)(3)(5) が新しい部分。(4) は既存の `tools/run_quantity_allocation.py` の経路をそのまま使う。

## 2. データの設計

置き場所：`<out-dir>/udp/<plan_id>/`（試行の写しの外。`output/` の下）。CSV は UTF-8・見出しあり。

### 2.1 元の需要の鍵

**`source_demand_ref` ＝ `sku_id|region|request_week[|segment]`**。CSV の行の番号は使わない。

- `region` は需要 CSV の列で、化粧品では leaf_out のノードの名前と同じ（`SG_Store` など。確かめた）。
- `segment`（需要区分）は、同じ週・同じチャネルの中で優先の違う需要があるときだけ。化粧品の U4 では使わない（空）。
- 同じ `source_demand_ref` の中の lot は、業務上同じものとして扱う（数量で対応させる）。

### 2.2 ファイル

| ファイル | 向き | 列（必須） | 備考 |
|---|---|---|---|
| `udp_demand_ledger.csv` | 出力（(1)） | `source_demand_ref, sku_id, region, request_week, segment, q1, demand_nature` | `demand_nature`：`forecast`／`firm`。化粧品は `forecast`。需要 0 の週も行を持つ |
| `udp_quota.csv` | 入力（モード 1） | `sku_id, region, alloc_lots, quota_source` | 今の `allocation_qty_*.csv` に出どころの列を足したもの。`quota_source` の例：`P2-a2（U3 の基準による配分）`。今の形のファイルもそのまま読めるようにする |
| `udp_policy.csv` | 入力（任意。段階 3 から） | `policy_id, policy_version, sku_id, region, week_from, week_to, segment, priority_class, reason, window_from, window_to, min_supply_lots, min_supply_kind` | `priority_class` 1〜5（1 が最優先、順序だけ）。`min_supply_kind`：`required`／`target`。空欄の項目は「指定なし」で、既定値を黙って置かない |
| `udp_selection_ledger.csv` | 出力（(2)） | `source_demand_ref, q1, q2, q3, week_rule, tie_key, reason_code, quota_ref, policy_ref` | `reason_code` の例：`quota_cut_proportional`、`quota_cut_even`、`quota_cut_latest_first`、`kept_full`。鍵ごとに Σq2 ＝ `alloc_lots` |
| `udp_capacity_check.csv` | 出力（(3)、診断） | `sku_id, week, need_good_lots, cap_good_lots, cum_need, cum_cap, cum_excess` と、SKU ごとの `ontime_short_ref`・適用条件 | §4。要求時期までに満たせない量の参考値で、期末の未充足の予測値ではない |
| `udp_result_by_request.csv` | 出力（(5)） | `source_demand_ref, q2, on_time, early, late, q5, first_ship_weeks` | §5。q2 ＝ on_time＋early＋late＋q5 |
| `udp_supply_runs.csv` | 出力（(5)） | `sku_id, region, zero_supply_weeks, longest_zero_run, longest_zero_run_from, excluded_weeks_rule` | 実際の出荷の週で数える。§5.3 |
| `udp_plan.json` | 出力 | `plan_id, scenario_id, mode, horizon, judgement_week, report_start, week_rule, tie_key, input_hashes{}, target_commit, knowledge_used[], owner_decisions[], calc_status, consistency_status, target_status, owner_status` | 再現と引き継ぎ。**`input_hashes` は計算に使う入力のファイルだけ**（元の需要 CSV、数量枠、方針、モデルの入力 CSV）。生成した需要 CSV と実行の結果は混ぜない（それらは出力として別に記録）。**状態は 4 つを別々に持つ**：計算（未計算／計算済み）、数量の整合（未確認／整合／不整合）、業務の目標（未判定／達成／未達）、Owner の採否（未判断／採用／不採用）。一つの `status` にまとめない（GPT君） |

## 3. 選び方（モード 1：数量枠を固定）

鍵 k（SKU × region）ごとに、元の需要 d(w)、数量枠 a（＝ alloc_lots）、減らす量 r ＝ Σd − a。出力 s(w) は 0 ≤ s(w) ≤ d(w)、Σs ＝ a。直営店・EC のように a ＝ Σd の鍵は、s ＝ d（`kept_full`）。

| 規則（`week_rule`） | 定義 | 化粧品の案 |
|---|---|---|
| `proportional_early_tie` | 最大剰余法。raw(w) ＝ a·d(w)/Σd、floor の後の残り R を、端数の大きい順、**同じ端数は request_week の早い順**に +1 | **A0**。今の `handoff.py` と同じ結果になる（鍵の中の行が週の順のため）。結果として、減らす 1 lot は遅い週に並ぶ |
| `proportional_even` | まず floor(raw) を置く。残り R を、**端数の大きい集団から順に**、集団の全週へ +1 する（端数が同じ週の集まりを一つの集団とする）。残りが集団の大きさ n より少なくなった**最後の集団だけ**、その R' 個の +1 を、集団を request_week の順に並べた番号の**等間隔の位置** i_j ＝ floor((j＋0.5)·n／R')（j ＝ 0…R'−1）に置く | **A0e** |
| `earliest_first` | request_week の早い順に s(w) ＝ min(d(w), 残り) | **A1**（遅い週から丸ごと減る） |
| `priority_then_<rule>` | 段階 3。`udp_policy.csv` の priority_class の順に枠を埋め、同じ優先の中は上のどれかの規則 | A2・構想の段階 A |

**同順位の鍵は request_week（と segment）**。行の番号に頼らない。テスト：行の順を入れ替えても選択の台帳が同じ。

**A0 が今の結果と同じになることの確認**：`proportional_early_tie` で P2-a2 の配分を選び、今の `write_demand_for_quantity_allocation()` が書く需要 CSV と、全行一致することをテストにする（P2-a・P0P1 の結果を変えないため）。

### 3.1 能力に合わせて減らす週を選ぶ規則（`trim_to_capacity_latest`、v0.3 で追加。提案）

**業務の意味**：能力が足りなくなる区間に合わせて、**期間の後ろの週から、各週の需要を能力の高さまで削る**。能力を余らせない範囲で、できるだけ遅い週で減らす。近い週の需要は全部残し、遠い週は「能力に入りきる分」だけ残す（代理店への供給は止めない）。

**背景**：A1（早い週を優先）は遠い週を丸ごと外したため、その週の能力が余り（後ろの週の能力は前の週の需要に使えない）、能力の足りない区間で押し戻された lot が届かなかった（U4 の報告書 §5）。この規則は、外す量を「その週の能力を超える分」に限ることで、能力を余らせない。

**手順**（SKU ごと。鍵ごとの数量枠 a_k はモード 1 のまま固定、減らす量 r_k ＝ Σd_k − a_k）：

1. 元の需要（全部の鍵）から、工場の週ごとの必要 need(p) を作る（§4 と同じ換算。§4 の条件の選択肢 `first_week_unusable`・`ss_lead` を使う）。
2. 工場の週を**後ろから前へ**たどる。週 p で、超える分 e(p) ＝ max(0, need(p) − cap_good(p))。
3. e(p) を、その週 p に対応する要求週の、**減らす量の残っている鍵**（r_k > 0。化粧品では代理店）の需要から減らす。鍵の間の分け方は、残りの r_k に比例（最大剰余法、同順位は region の名前の順）。各鍵の減らす量は、その週の需要と残りの r_k を超えない。
4. すべての r_k を使い切ったら終わる。後ろから全部たどっても残る r_k があれば、残りは `proportional_even` で配り、その量を診断に書く（化粧品では起きない見込み：2028〜2029 年の超える分の合計が、減らす量より大きい）。
5. 減らした後の need で §4 の診断をもう一度計算し、参考値を記録する。

**見込みの性質**：e(p) を後ろから削るので、削った週の need は能力と同じになり、能力を余らせない。超える分が後ろの区間で単調に増える形（化粧品の 2028〜2029 年）なら、減らした後の累計の超過の最大は、モード 1 で外せない分（境界の分）だけになる。**これは近似の条件の下での見込みで、未充足はエンジンの後の照合で確定する**（§4）。

## 4. 時間の可否の診断（`udp_capacity_check.csv`）— 要求時期までに満たせない量の参考値

GPT君のドラフト §7 の「期間の合計の能力を ② にそろえることと、要求の時期に間に合う需要を選ぶことは違う」を、計画の前に数で示す診断。

**計算**（SKU ごと、工場を一つの資源とみなす）：

1. need_good(w) ＝ Σ_leaf s_leaf(w ＋ L_leaf)。L_leaf は leaf から工場の出荷までの週数（木の `lt_wks` の和。化粧品は判定 1＋海上 2＋DC→チャネル 1 ＝ 4）。
2. cap_good(w) ＝ floor(cap_soft(w) × yield_rate)（`demand_envelope`＝soft のとき。hard なら max_supply）。`PlanNode.shippable_*` と同じ換算にする（C3a の開放の週：美容液 13、クリーム 10）。
3. cum_excess(t) ＝ Σ_{w≤t} need_good(w) − Σ_{w≤t} cap_good(w)（w は計画の最初の週から）。
4. **要求時期までに満たせない量の参考値**：ontime_short_ref ＝ max(0, max_t cum_excess(t))。作り置きは前の週にしかできないので、ある時点までの必要が、その時点までの能力を超えた分は、その要求時期には間に合わない。

**意味（v0.2 で直した。GPT君の指摘）**：

**時間の可否の診断は、指定した近似の条件の下で、要求時期までに満たせない数量を示す参考値とする。期末の未充足（⑤）の予測値とは区別する。期末の未充足は、Forward の後の Lot の照合（§5）で確定し、診断との差と適用の条件を記録する。**

- 要求時期に間に合わない量と、期末まで届かない量は違いうる。例：第 1 週の需要 10・能力 5、第 2 週の需要 0・能力 5。第 1 週に 5 不足する（参考値 5）が、翌週の生産と遅配を認める計画なら、期末までに 10 全部を届けられる（期末の未充足 0）。
- 近似の条件：単一の資源（SKU ごとの工場）、固定の LT、作り置きに上限なし、遅れての生産をしない、店頭在庫（`ss_days`）・原料の区間（最初の週）・休業は入れない。この条件を `udp_capacity_check.csv` に一緒に書く。
- **v0.3 で選択肢を足す**：`first_week_unusable`（工場の計画の最初の週の能力を 0 とする。原料の区間の LT のため）と `ss_lead`（leaf の `ss_days` の分、その leaf の要求を ceil(ss_days／7) 週早める）。U4 の試行では、この 2 つを入れると 6 通りすべてで未充足と一致した（報告書 §5.1）。一般の式としては採用せず、既定は今と同じ（入れない）。使った条件を出力に書く。
- 今の WOM の Backward は、能力を超えた分を前の週へだけ押し戻し、計画の最初より前に出た分を `past_due` にする。Forward がそれを後の週で作って遅配にするかどうかで、参考値と期末の未充足の関係が変わる。**化粧品の試行で、遅配（Flow Check の表2 の `late`）が出るかを確かめ、参考値・期末の未充足・遅配の三つを並べて記録する。**
- 合計が等しい（Σneed ＝ Σcap）とき、cum_excess(t) ＝ t より後の能力の余り − t より後の必要。期間の終わりで能力が余る選び方ほど、参考値が大きい。
- A0・P1 で期末の未充足と数が近くても、それだけで一般の予測の式としては採用しない。今の Backward の配置に限った診断として使う場合も、その条件を書く。モード 2 の選択に使うかは、試行の後に決める。

## 5. 実行の後の照合（元の需要へ戻す）

### 5.1 Lot と元の需要の対応

既存の Flow Check の表2は、leaf ごとに、要求の Lot_ID の S の週（`s_week`）と、最初の実出荷の週（`first_ship`）を照合して数えている（`wom/engine/flow_check.py` の表2 の部分）。ただし出力は leaf・製品・モデルの集計で、**要求週ごとの明細は出していない**（GPT君の指摘どおり。確かめた）。

新しい照合は同じ方法を使う：leaf の lot ごとに (product, leaf, s_week) を取り、`source_demand_ref ＝ product|leaf|s_week` に戻す。同じ鍵の中の lot は同じものとして数える。Lot_ID の文字列は書き換えない。

### 5.2 `udp_result_by_request.csv`

- 鍵ごとに q2（その週の要求 lot の数）、on_time（w ＝ s_week）、early（w < s_week）、late（w > s_week）、q5（出荷なし）。
- **照合**：leaf ごとの合計が、Flow Check の表2 の demand・on_time・early・late・backlog_end と一致する。選択の台帳の q2 と、要求 lot の数が一致する。合わなければ止める（不整合）。
- ①③ は選択の台帳から足す（③ は Lot が作られないので、エンジンの側には無い）。

### 5.3 `udp_supply_runs.csv`

実際の出荷の週（leaf の出荷）で、供給が 0 の週の数と、最長の連続を数える。数えない週を明示する：その leaf の最初の需要の週より前（開店前・タイの 2028 年前）、元の需要が 0 の週、休業の週。要求週ごとの未充足（§5.2）とは別の集計。

## 6. 比べ方（M1〜M7 との対応）

| 測ること（U4 資料 §5） | 出どころ |
|---|---|
| M1 鍵ごとの ①〜⑤ | 選択の台帳＋`udp_result_by_request.csv`（Q json とも照合） |
| 要求週ごとの当週の充足率 | `udp_result_by_request.csv` の on_time ÷ **元の需要 ①**（その週の）。「近い週を守れたか」を直接見る（GPT君）。分母が 0 の週は「対象なし」と書き、100% にしない |
| M2 要求週ごとの ②〜⑤ | `udp_result_by_request.csv` |
| M3 供給が 0 の週・連続 | `udp_supply_runs.csv` |
| M4 能力の余り | `udp_capacity_check.csv` と工場の PSI |
| M5 年齢 | `tools/shelf_life_check.py --demand-file` |
| M6 評価の額 | P2-a の `evaluate.py`（同じ単価・固定費の相当額） |
| M7 固定の確認 | 既存の数量配分モードの検査 |

## 7. 既存の機能との対応と、足りない部分

| 仕事 | 既存 | 足すもの | 置き場所 |
|---|---|---|---|
| 元の需要の台帳 | なし（需要 CSV だけ） | `udp_demand_ledger.csv` を作る | 新しい `wom/allocation/upper_demand_plan.py` |
| 数量枠の読み込み | `read_quantity_allocation()` | `quota_source` の列（任意） | `handoff.py` |
| 週への当て方 | `write_demand_for_quantity_allocation()`（比例＋行の番号の同順位） | `week_rule` と `tie_key`。既定は `proportional_early_tie`（今と同じ結果） | `handoff.py`（`_largest_remainder` の同順位の鍵を引数にする） |
| 選択の台帳 | なし（keys の合計だけ返す） | 週ごとの q1・q2・q3 と reason_code | `upper_demand_plan.py` |
| 時間の可否の診断 | なし | §4 | `upper_demand_plan.py`（木と capacity_plan を読むだけ） |
| 計画の実行 | `tools/run_quantity_allocation.py` | `--week-rule`、`--udp-out` の引数 | `tools/run_quantity_allocation.py` |
| 要求週ごとの照合 | Flow Check の表2 の内部の照合（集計だけ出力） | §5 の明細と、表2 との照合 | `upper_demand_plan.py`（`flow_check.py` は変えずに、同じ照合を木から行う） |
| 優先度の方針 | なし（`bridge_backward()` の `market_priority` は使われていない置き場） | 段階 3 で `udp_policy.csv` | `upper_demand_plan.py` |
| ⑤ の振り分けに優先を効かせる | なし（押し戻しは lot の並びの順） | **段階 1・2 では扱わない**。段階 2 の結果を見て、上位での選び直し・既存の上位配置（Capacity Layer）・コアの変更を比べる（GPT君 §8.2） | — |

保護対象のコア（`backward_planner.py`、`forward_planner.py`、`plan_copy.py`、`plan_node.py`、`sc_tree.py`、`push_pull.py`）は、段階 1〜3 で変えない。

## 8. 実装の進め方

| 段階 | 中身 | 担当 | コード | 終わりの条件 |
|---|---|---|---|---|
| **0** | U4 の判断（U4 資料 §7） | 大杉さん | なし | 判断の番号が付く |
| **1** | 上位 Demand Plan のモード 1 の最小の実装：台帳、`week_rule`（3 つ）、選択の台帳、時間の可否の診断、要求週ごとの照合、供給 0 の連続 | Code君 | 道具（`wom/allocation/`、`tools/`）。コアなし | §9 の UP-V01〜V07・V10 |
| **2** | 化粧品の試行：A0（P2-a2 の再現）、A0e、A1。診断とエンジンの ⑤ の比べ合わせ | Code君 | なし（写し） | ①〜⑤・M1〜M7 の表、診断の当たり方 |
| **3** | 優先度の方針（`udp_policy.csv`、`priority_then_<rule>`）、仮の Window の小実験（A2） | Code君 | 道具 | UP-V08・V09 |
| **4** | モード 2（チャネルの間の数量も方針と時間の可否から選ぶ）。⑤ の振り分けに優先を効かせる方法の比較 | 設計から | 比較の後に決める | 構想の段階 B |

段階 1 と 2 は一つの依頼書にしてよい（実装 → 試行）。段階 3 以降は、段階 2 の結果と大杉さんの判断の後に別の依頼書にする。

## 9. 受入の条件（GPT君の UP-V を段階に割り当てた）

| ID | 確認すること | 段階 |
|---|---|---|
| UP-V01 | 元の需要の台帳が全部の ① を持ち、選択の台帳の全行に規則と理由がある | 1 |
| UP-V02 | 鍵・元の需要ごとに ①＝②＋③、実行の後に ②＝④＋⑤ | 1・2 |
| UP-V03 | `proportional_early_tie` が今の `handoff.py` と全行一致し、A0 が P2-a2（①4,056・②3,864・③192・④3,856・⑤8）を再現する | 1・2 |
| UP-V04 | 小さな例で選択と時間の可否の診断を手計算と照合する（GPT君の §7 の例：能力 5・5、需要 W1 8・W2 2 → 要求週どおりに選ぶと ② 7） | 1 |
| UP-V05 | 需要 CSV の行の順を入れ替えても、選択の台帳が同じ | 1 |
| UP-V06 | 生成後の Lot の重複・消失なし。案の比較は `source_demand_ref` で行う | 1 |
| UP-V07 | 要求週ごとの ④⑤ の合計が、Flow Check の表2 と leaf ごとに一致する | 1 |
| UP-V08 | 優先度ごとの ④⑤ を観測し、高優先の未充足と低優先の納品の組を、原因の候補（GPT君 §5.3）と一緒に出す | 3 |
| UP-V09 | 満たせない必須の最低供給を検出し、達成と表示しない | 3 |
| UP-V10 | `udp_plan.json` に入力・規則・知識の版・commit・ハッシュが残り、同じ入力の再実行で同じ結果 | 1 |

既存の golden は変わらないこと。新しい選択を指定しない経路は、今と同じ結果。

## 10. 未決（大杉さんの判断）

U4 資料 v0.2 §7 に、GPT君の UP-J01〜J06 と合わせて並べる。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-01 | 初版（提案）。GPT君の上位 Demand Plan の設計ドラフトを、既存のコードに対応させて詳細にした |
| v0.3 | 2026-11-02 | §3.1 に能力に合わせて減らす週を選ぶ規則（`trim_to_capacity_latest`）、§4 に診断の条件の選択肢（`first_week_unusable`・`ss_lead`）を足した。U4 の試行の結果から |
| v0.2 | 2026-11-01 | GPT君の確認（`c9a1d16`）：時間の可否の診断を「要求時期までに満たせない量の参考値」とし、期末の未充足の予測値と区別（§4）。均等の規則の定義を「端数の大きい集団から、最後の集団だけ等間隔」に（§3）。ハッシュは入力のファイルだけ、状態は 4 つを別々に（§2.2）。要求週ごとの当週の充足率（元の需要が分母）を足した（§6） |
