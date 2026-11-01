---
handoff:
  case_id: BSSEAF-COS-U4
  task_id: U4-T2-capacity-aware-week-rule
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: c1be01f       # この依頼書の commit の前の先頭。着手時の SHA を報告書に
  knowledge_used:
    - id: WOM-SEM-SUPPLY-ALLOCATION-001
      version: v0.4
      applicability: "U4（化粧品で採用：均等）、選ぶ週と届く週は別"
    - id: WOM-DESIGN-UPPER-DEMAND-PLAN-001
      version: "0.3"
      applicability: "§3.1 trim_to_capacity_latest、§4 診断の条件の選択肢"
    - id: WOM-KB-BSSEAF-001
      version: v0.3
      applicability: "止める理由と申し送り、記録 §4"
  acceptance:
    ref: "この依頼書 §6"
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_Report.md
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes: []
  next: implement
---

# Request Letter：BS-SEAF 化粧品 U4 — 能力に合わせて減らす週を選ぶ規則（上位 Demand Plan、モード 1）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-02）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（この依頼書は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：
  - 判断：`requests/BSSEAF_Cosmetics_AllocationWeekRule_U4_v0.1.md`（v0.4）§7.1（大杉さん、2026-11-02：化粧品の規則は A0e、次の段階はこの規則）
  - 設計：`docs/design/drafts/WOM_Upper_Demand_Plan_DetailDesign_v0.1.md`（ファイル内の版 v0.3）§3.1・§4
  - 前回の結果：`docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_Report.md`（`c1be01f`）
- 種別：**Part A は道具のコードの追加**（`wom/allocation/upper_demand_plan.py`、`tools/run_quantity_allocation.py`）。保護対象のコアと `flow_check.py` は変えない。既存の golden（通常 16・legacy 3）は変わらないこと。**Part B は試行**（写しは `output/bsseaf_cosmetics/`）

---

## 0. 目的

前回の試行で、「早い週を残し遠い週を外す」規則（A1）は、外した週の能力が余り、能力の足りない区間で押し戻された lot（タイの代理店）が、残したはずの週で届かなかった（未充足 119）。**どの週を選ぶか**と**どの週に届くか**は別だった。

今回は、**能力が足りなくなる区間に合わせて、期間の後ろの週から、各週の需要を能力の高さまで削る**規則（`trim_to_capacity_latest`）を作り、化粧品で試す。近い週の需要を全部残しながら、能力を余らせないことで、**選んだ週に実際に届くか**を確かめる。

## 1. 決まっていること

- モード 1 のまま：SKU × チャネルの数量枠は P2-a2 で固定。減らせるのは代理店の鍵だけ（直営店・EC は全量）。
- 化粧品の事例で今使う規則は A0e（`proportional_even`）。今回の規則は、それと比べる候補（採用は結果を見て大杉さんが決める）。
- 時間の可否の診断は参考値。未充足は Forward の後の Lot の照合で確定する。
- 差し戻し・修正の往復は 3 回まで。

## 2. 先に確かめること

| # | 確かめること |
|---|---|
| B1 | 前回の `time_phased_check()` で、`first_week_unusable` と `ss_lead`（詳細設計 §4）を入れた計算が、前回の 6 通りの未充足（報告書 T3 の右の列）を再現すること。前回の計算は試行のスクリプトか、モジュールか（モジュールに入っていなければ、今回モジュールに入れる） |
| B2 | 工場の週 p と、代理店の要求週の対応（化粧品は LT 4 週。直営店は `ss_days` 14 日で 2 週早い）。SG・TH とも 4 週であること |
| B3 | 前回の A0e の結果（未充足 4、評価の額 607,240,500 円）が、今の commit で再現すること（比べる基準） |

## 3. Part A：規則と診断の条件

### 3.1 `time_phased_check()` に条件の選択肢

- 引数 `first_week_unusable: bool = False`、`ss_lead: bool = False`（詳細設計 §4）。既定は今と同じ結果。
- 出力の近似の条件の文字列に、使った条件を書く。

### 3.2 規則 `trim_to_capacity_latest`（詳細設計 §3.1）

- 今の `select_mode1()` は鍵ごとに独立して選ぶが、この規則は**SKU ごとに全部の鍵の需要と、モデルの能力・LT を見て**選ぶ。関数を分けてよい（例：`select_mode1_capacity(ledger, quota_file, model_dir, first_week_unusable=True, ss_lead=True)`）。選択の台帳の形は同じ。`reason_code` は `quota_cut_trim_to_capacity`。
- 手順：工場の週を後ろから前へたどり、その週の必要が良品の能力を超える分 e(p) を、対応する要求週の、減らす量の残っている鍵から減らす。鍵の間は残りの減らす量に比例（最大剰余法、同順位は region の名前の順）。使い切ったら終わる。残れば `proportional_even` で配り、その量を記録する。
- 診断の条件は、規則の中では `first_week_unusable=True`・`ss_lead=True` を使い、`udp_plan.json` と選択の台帳に記録する。
- `tools/run_quantity_allocation.py` の `--week-rule` に `trim_to_capacity_latest` を足す。他の規則と既定の動きは変えない。

### 3.3 テスト

| テスト | 中身 |
|---|---|
| 規則の手計算 | 小さな合成の例（工場 1・代理店 2・直営店 1、能力と需要を手で置く）で、減らす週と量を手計算と照合。減らした後に、削った週の必要が能力と同じになること |
| 数量の保存 | 鍵ごとに Σ減らす量 ＝ r_k、q1 ＝ q2 ＋ q3、どの週も 0 ≤ q2 ≤ q1 |
| 余りの扱い | 超える分の合計が減らす量より少ない例で、残りが均等に配られ、その量が記録される |
| 行の順 | 需要 CSV の行の順を入れ替えても選択の台帳が同じ |
| 既定の不変 | 既存の 3 規則と診断の既定の結果が前回と同じ |

回す段：途中は `--smoke` と `--area allocation`、最後に `--full` を 1 回。

## 4. Part B：化粧品の試行

### 4.1 案

| 案 | 規則 | 写し |
|---|---|---|
| A0e（基準） | `proportional_even` | `output/bsseaf_cosmetics/U4_A0e_r2`（前回と同じ作り方：C3a、P2-a2 の数量枠） |
| **A3** | `trim_to_capacity_latest` | `output/bsseaf_cosmetics/U4_A3` |

前回の A0・A1 の結果は、報告書から引用して並べる（再実行は要らない）。

### 4.2 見込み

| | A0e | A3 |
|---|---|---|
| ①②③ | 4,056・3,864・192（鍵ごとも P2-a2 と同じ） | 同じ |
| 減らす週 | 期間に均等 | 期間の後ろの約 26 週（美容液）・約 29 週（クリーム）で、毎週 4・3 lot 程度（良品の不足の分）。近い週は全部残す |
| 代理店への供給 0 の週 | 0 | 0（毎週の削る量が代理店の需要より小さい） |
| 時間の可否の参考値（条件 2 つを入れて） | 前回の値 | **境界の分だけになる見込み**（数は Part A の診断で、試行の前に出して報告書に書く） |
| 未充足 | 4 | 方向：A0e と同じ程度か少ない。届かない lot が近い週に出ないか |

### 4.3 測ること（前回の T1〜T9 と同じ形）

- T1 鍵ごとの ①〜⑤、T2 要求週ごと（代理店 4 鍵、期間の終わりの 30 週）と当週の充足率（元の需要が分母）、T3 参考値（条件 2 つを入れた値と入れない値）・未充足・遅配、T4 供給 0 の週、T5 工場の能力の余り（期間の終わりの 30 週）、T6 年齢、T7 評価の額、T8 固定の確認、T9 未充足の鍵・要求週。
- **T10（今回の中心）**：**「選んだ週に届いたか」**。A3 で残した週（要求週ごとの ②）のうち、当週に届いた割合と、届かなかった lot の要求週の分布。前回の A1（残した週の TH 2029-W21〜W40 で未充足）と並べる。
- まとめの表：案（A0・A0e・A1・A3）× {②③④⑤、当週の充足率（全体・代理店）、参考値、未充足、供給 0 の最長、年齢の最大、評価の額}。A0・A1 は前回の値の引用と明記。

## 5. 止める理由と申し送り

止める理由：B1 で前回の 6 通りを再現できない、B3 で A0e が再現しない、既存の規則・診断の既定の結果が変わる、既存の golden が変わる、数量の保存が破れる、照合が表2 と合わない、保護対象のコアか `flow_check.py` を変えないと実装できない、往復が 3 回を超える。

**未充足が見込みより多い・A3 が A0e より悪いことは、止める理由ではない**（結果として残し、原因を T9・T10 で調べる）。

## 6. 受入条件

| # | 条件 |
|---|---|
| S1 | §2 の B1〜B3 の結果 |
| S2 | 規則の手計算・数量の保存・余りの扱い・行の順・既定の不変のテストが通る |
| S3 | A0e が前回を再現。A3 の ①②③ が見込みどおり |
| S4 | 要求週ごとの照合が表2 と一致、②＝④＋⑤ |
| S5 | 試行の前に出した A3 の参考値と、試行の後の未充足を並べた表 |
| S6 | §4.3 の T1〜T10 とまとめの表 |
| S7 | 回帰：既存の golden が変わらない。`--full` が通る |

## 7. 報告書と記録

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_CapacityAwareWeekRule_U4_Report.md`（付録 `..._appendix/`）。冒頭に引き継ぎの欄（YAML。`next: owner`）。
- 中身：着手時の SHA、§2 の結果、作ったもの、S1〜S7、§4.3 の表、止める理由と申し送り、大杉さんに決めてほしいこと（化粧品で使う規則を A0e から A3 に変えるか）。
- **BS-SEAF の記録**：前回と同じ項目に加えて、**実作業の時間を、着手・各 Part の完了・報告の時刻で記録する**（前回は計測できなかった）。テストの実行の待ち時間は別に書く。人の橋渡し（転記・連絡／git の操作／業務の判断／レビューへの対応）も数える。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-02 | 初版 |
