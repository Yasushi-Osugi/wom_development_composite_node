---
handoff:
  case_id: BSSEAF-COS-LOOP4
  task_id: NEWAGENT-MINIMUM-SUPPLY-PLAN-001
  role_from: research_design   # 新しいセッションの Claude Code
  role_to: owner
  target_commit: c7972de4d3c70e2101086b65bb1d59d8c75a9dea
  knowledge_used:
    - id: WOM-SEM-SUPPLY-ALLOCATION-001
      version: "0.6"
      applicability: "①〜⑤ の関係（§3）、最低供給量の二段階の確認と衝突（§6.1）、U4 の化粧品の規則（§5）"
    - id: WOM-KB-BSSEAF-001
      version: "v0.5"           # 依頼書の指定は v0.4。読んだ版は v0.5（§3.2 に 1 行が加わった版）
      applicability: "8 段階（§1）、知識が見つからないときの扱い（§3.2）、段階 7 の独立性（§3.3）、一巡の記録（§4）"
    - id: WOM-DESIGN-UPPER-DEMAND-PLAN-001
      version: "0.3"
      applicability: "§3.1 trim_to_capacity_latest、§3.2 最低供給量、§4 時間の可否の診断（参考値）"
  acceptance:
    ref: "requests/RequestLetter_BSSEAF_Cosmetics_MinimumSupply_Reallocation_to_NewAgent.md §7"
  evidence:
    - "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md"
  status: "Owner 判断待ち（H2）"
  decisions:
    - "H1（2026-11-06、大杉さん）：タイのクリームの 7 割・切り上げは、全量（元の需要 299 を減らさない）の意味のまま進める"
  open_items:
    - "H2：後の試行（T0〜T3）を誰が・どの範囲で実行するか"
  stop_reasons: []
  handover_notes:
    - "数量枠の候補は一つに決まる（タイ 299・シンガポール 666）。数え直しは git の対象の CSV だけ。WOM の再実行は未実施"
    - "シンガポールのクリームの減らす区間が前へ広がる見込み（近似：2029-W19 → 2029-W07）。実際の選び方と実納品は未確認"
  next: owner
---

# 作業計画：化粧品のタイ向けクリームを最低 7 割にする配分の見直し（v0.1）

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_MinimumSupply_Reallocation_to_NewAgent.md` v1.0
- 作成：新しいセッションの Claude Code（Claude Opus 5.5）、2026-11-06
- 範囲：調査と計画まで。WOM の実行、コードの変更、正式なモデルへの適用はしていない

## 0. 結論（短く）

1. **新しい条件を満たす数量枠は一つしかない**：タイの代理店のクリーム 274 → **299**、シンガポールの代理店のクリーム 691 → **666**（合計 965 は同じ）。（再集計）
   - タイのクリームの週の需要は 2 lot（13 週）と 3 lot（91 週）だけ。7 割を切り上げると 2 → 2、3 → 3 になる。最低数量の合計は 299 で、元の需要 299 と同じ。つまりこの条件は、**タイのクリームを一つも減らさない**ことと同じ（基準の報告書 §0 の「実質 10 割」と一致）。
   - 数量枠は元の需要を超えられない（`wom/allocation/handoff.py` の `check_quantity_quota`）。だからタイは 299 ちょうどで、残りの 666 がシンガポールに決まる。
   - シンガポールの最低 5 割の合計は 455。666 はこれを上回るので、数量では両立する。
2. **CSV の変更は 2 つ**：数量枠の 2 行と、方針のファイルの 1 行（タイのクリームの比率を 0.7 に）。既存の道具の経路（R23 の `--policy-file`）でそのまま表せる。**コード・保護対象のコアの変更は要らない見込み**。根拠は、比率を鍵ごとに読むこと（`read_policy`）と、元の需要と同じ数量枠の鍵は減らさないこと（`select_mode1_capacity`）。ここまではコード確認で、実行はしていない。
3. **数量だけでは、届くかは決まらない**。基準の週ごとの選択を数え直して近似した。基準でタイが減らしていた 25 lot（2029-W26〜W50 に週 1 lot）は、シンガポールでは同じ週に置けない（その週は既に最低 5 割まで減っている）。前の週へ繰り越すと、シンガポールの減らす区間は **2029-W19 → 2029-W07 に約 12 週前へ広がる**。減らす週はすべて 5 lot 中 3 lot（60％）になる（近似。道具そのものではない）。届くか、在庫と年齢がどう変わるかは、後の試行で確かめる。

## 1. 業務の要求と、固定する条件

- 要求（依頼書 §0.1）：採用済みの「代理店への最低供給量 5 割」の化粧品の計画を基準にする。タイの代理店へ届けるクリームだけは、各要求週の元の需要の 7 割以上（lot 単位で切り上げ）を、その週に届ける。工場の能力は増やさない。変えてよいのは、シンガポールとタイのクリームの配分の数量だけ。
- 固定するもの（依頼書 §2）：元の需要、計画の期間・warmup、工場の能力・歩留まり・リードタイム・在庫の方針・操業、SKU ごとの供給の対象の合計、直営店・EC の配分、美容液の配分と最低供給量、シンガポールのクリームの最低供給量（5 割・切り上げ・必ず守る）、製品の年齢の条件。
- 年齢の条件の根拠：`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.5.md` の A6（残存期間 24 か月＝許容の滞留 12 か月＝52 週）と COS-R05（納品時の先入れ先出しの年齢 ≦ 52 週）。道具は `python -m tools.shelf_life_check --max-age-weeks 52`。（文書確認）
- 需要を減らす・端数を切り捨てる・比率を下げる、という変更は、この計画では使わない（業務の要求を変えることになるため）。

## 2. 調べた版・資料・作業の環境

| 項目 | 中身 |
|---|---|
| commit | `c7972de4d3c70e2101086b65bb1d59d8c75a9dea`（ブランチ `wom-v1r6m0_BS-SEAF`、作業ツリーは clean） |
| 版の差 | 依頼書は WOM-KB-BSSEAF-001 を v0.4 と書いているが、読んだ版は v0.5（2026-11-06。§3.2 に「新しい担当を迎える前の確かめ」が加わった） |
| 環境 | Windows 11、Claude Code（デスクトップ）。資料・コードの読み、CSV の読み書き、Python の実行（Anaconda 3.12.3、pandas 2.2.2）、リポジトリへの書き込みができる。Git Bash の `python` は Windows ストアの起動用のファイルで動かないので、`%USERPROFILE%\anaconda3\python.exe` を使った |
| していないこと | WOM のモデルの実行（`run_quantity_allocation`・headless・`shelf_life_check` を含む）、道具の関数の呼び出し、コードの変更、commit。読まないでほしいと指定された 3 ファイルと、`output/` の下は開いていない |
| 再集計の道具 | 手で書いた CSV の数え直し（スクラッチの領域、リポジトリの外）。読んだのは git の対象の CSV だけ（§8 の 13〜16） |

確かめ方の表記：**文書**＝文書確認、**コード**＝コード確認（上の commit）、**再集計**＝git の対象のファイルを自分で数え直した、**再実行**＝WOM を自分で実行した（今回は無し）。

## 3. 基準の案と、再現の手順

### 3.1 基準の構成（すべて文書確認＋コード確認）

| 要素 | 中身 | 根拠 |
|---|---|---|
| モデル | `data/sample/cosmetics-sg-th-2027-2029` の写し。`capacity_plan.csv` の全行（warmup の行も）を、美容液 `max_supply` 17・`cap_soft` 14、クリーム 13・11 にする（**C3a**＝能力が足りない状態） | `docs/scenarios/cosmetics.md`「C3a」、付録 `scripts/run_trial.py` の `copy_c3a()` と `CAP` |
| 能力（良品） | クリームの工場は `demand_envelope=soft`、`yield_rate=0.97`。良品の能力は週 10 lot（int(11×0.97)）。最初の週は 0 | `sc_tree_master.csv`、`upper_demand_plan._sku_resources`、再集計（MS50 の `udp_capacity_check.csv`：10 が 172 週、0 が 1 週） |
| 期間 | 2026-W37 から 173 週。warmup 17 週。報告の開始は 2027-W01 | `docs/scenarios/cosmetics.md`、`planning_config.csv` |
| 数量枠 | P2-a2：クリーム SG 691・TH 274・直営店 416・EC 299。美容液 SG 825・TH 358・直営店 546・EC 455 | `docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv` |
| 方針 | MS50（代理店 4 鍵、0.5、ceil、required） | `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv` |
| 週への当て方 | `trim_to_capacity_latest`（能力を超える工場の週を後ろからたどって削る。最低供給量で止まった分だけ前の週へ繰り越す） | Start Here R23、詳細設計 §3.1・§3.2、`select_mode1_capacity()` |
| プラグイン | 推奨の組：`HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin`（`--plugins` を省けばこの組） | `planning_config.csv`、Start Here §4.3 の 10 |
| 既存の結果 | ③ 192、④ 3,864、⑤ 0。下回った週は計画の時・実行の結果とも 0。比べるための評価の額 607,741,740 円。年齢の最大 28 週、52 週超 0 | `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_Report.md` §0・§5、付録 `udp/MS50/` |

**数量枠のファイルの注意**：同じ名前の `allocation_qty_P2a2.csv` が 2 つある。P2-a の付録（`AllocationP2a_appendix/allocation/`、3 列）と U4 の付録（`UpperDemandPlan_U4_appendix/records/`、`quota_source` 列が多い 4 列）。数は同じだが、ハッシュが違う（再集計）。最低供給量の試行は U4 の付録の方を使った（`run_trial.py` の `AF`）。`docs/scenarios/cosmetics.md` の「採用した配分の計画」は P2-a の方を指している。**`udp_plan.json` の `input_hashes` まで照合するなら U4 の方を使う**。

### 3.2 再現の手順（後の試行の T1。今回は実行していない）

1. 写しを作る：`output/bsseaf_cosmetics_th70/MS50_ref/` に、サンプルをコピーして C3a の能力を書く（`run_trial.py` の `copy_c3a()` と同じ）。
2. 実行する：
   ```
   python -m tools.run_quantity_allocation --model-dir <写し> --allocation-file docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv --week-rule trim_to_capacity_latest --policy-file docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv --udp-out <場所>/udp --out-dir <場所>/_planning_state --unallocated-note "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
   ```
3. 照らし合わせる：`udp_selection_ledger.csv`・`udp_result_by_request.csv`・`udp_min_supply_check.csv`・`udp_capacity_check.csv`・`udp_supply_runs.csv` を、付録の `udp/MS50/` とバイト単位で比べる。終了コード 0、③ 192・④ 3,864・⑤ 0。年齢は `python -m tools.shelf_life_check --model-dir <写し> --max-age-weeks 52 --demand-file demand_forecast_Q01.csv --warmup-real-start 2027-W01`（引数は `run_trial.py` と同じ）で、最大 28 週・52 週超 0。
4. 一致しなければ、先へ進まず、差を記録して戻す（コードは基準のときの `6e4a534…` から変わっている。`code_dirty` も違う）。

## 4. 業務の意味と、既存の機能への対応（依頼書 §3.1）

1. **8 段階と今回の位置**（文書：進め方の知識 §1）。今回は段階 2（意味と既存の知識を探す）と段階 3（差を Data／Parameter／Core に分ける）。後の試行が段階 4、採否が段階 5（大杉さん）、別の担当の確認が段階 7、知識の更新が段階 8。
2. **三層の分担**（文書：三層設計 MD §1）。Management（上位 Demand Plan）が、どの需要を供給の対象にするか（②）を選ぶ。Backward が、配分済みの需要を工場の週へ置く（能力を超える分は前の週へ）。Forward が、時間を遡らずに実出荷・未充足（④⑤）を計算する。今回の変更は Management の層の入力（数量枠・方針）だけ。
3. **5 つの数量**（文書：意味体系 §2・§3）。① 元の需要 ＝ ② 供給の対象 ＋ ③ 未配分。② ＝ ④ 実納品 ＋ ⑤ 配分後の未充足。④ は、需要の一件ごとに引渡しの完了で数える。③（経営が外した）と ⑤（届けると決めて届かなかった）を混ぜない。
4. **二段階の確認の理由**（文書：意味体系 §6.1、Start Here R23・§4.3 の 13）。選んだ週に届くとは限らない。押し戻される lot は、選んだ規則ではなく lot の並びで決まる。だから「選んだ ② ≧ 最低」と「その要求週の当週の ④ ≧ 最低」を別に確かめる。コード：`min_supply_check()` が `plan_ok` と `delivered_ok` を別に出す。
5. **三つの結果の違い**（文書：R23、意味体系 §6.1。コード：`run_quantity_allocation.main()`）：
   - 衝突（終了コード 3）は、最低数量の合計が数量枠を超えて両立しないこと。計画の前に止まり、エンジンに渡さない。
   - 未達（実納品不足、終了コード 4）は、選んだが当週に届かなかったこと。試行は完了し、採用だけを止める。
   - 不整合（終了コード 1）は、入力・記録の数が合わないこと。結果は保存せず `diagnostics/` に書く。

**既存の機能との対応**（コード確認。新しい機能は要らない見込み）：

| 要ること | 既存の機能 | 今回の適用の条件 |
|---|---|---|
| 鍵ごとに違う比率 | `read_policy()`：1 ファイルに `policy_id`・`policy_version` は 1 組。比率は行（鍵）ごと | 1 つのファイルに 0.5 と 0.7 を混ぜてよい。`policy_id` は新しい名前にする |
| タイを減らさない | `select_mode1_capacity()`：鍵の減らす量 `left` は q1 − 数量枠。0 なら `room` が 0 で、その鍵は削られない | 数量枠 299 ＝ q1 なので、自動的に減らさない |
| 衝突の検出 | `min_supply_conflicts()`：減らす量 ＞ q1 − 最低数量の合計 | タイは 0 ＞ 0 ではないので衝突しない。シンガポールは 88 ≦ 299 |
| 繰越 | 最低で止まった分だけ前の週へ送る。`blocked` は減らす量の残る鍵の最低だけを数える | タイの分は、シンガポールの前の週へ回る（§5.2） |
| 実納品の確認 | `min_supply_check()`、終了コード 4 | そのまま |
| 年齢 | `tools/shelf_life_check.py`（先入れ先出し） | 許容 52 週を明示する |

**探し方の記録**：Start Here §0.1 → 意味体系 → 三層設計 MD → R23 → 詳細設計 → 最低供給量の報告書と付録 → `docs/scenarios/cosmetics.md`。どの知識にも索引から辿れた。索引の外を探したのは 2 か所だけ。(a) 基準の能力の値（Start Here に無く、`docs/scenarios/cosmetics.md` の C3a で見つけた）。(b) 年齢の許容 52 週の業務の根拠（Start Here R18 には道具の引数としてしか出てこない。化粧品設計書 v0.5 の A6・COS-R05 を grep で見つけた）。

## 5. 提案する CSV の変更と、数量の確認

### 5.1 変更（写しの中だけ。正式なファイルは変えない）

数量枠（新しいファイル。U4 の付録の P2-a2 を写して 2 行を変える）：

```
COS_Cream,SG_Distributor,666,P2-a2 から TH 最低 7 割のために 25 lot を TH へ（試行 TH70）
COS_Cream,TH_Distributor,299,P2-a2 から TH 最低 7 割のために 25 lot を TH へ（試行 TH70）
```

ほかの 6 行（直営店・EC・美容液）は P2-a2 のまま。

方針（新しいファイル。MS50 を写して、1 行の比率と全行の `policy_id` を変える）：

```
policy_id,policy_version,sku_id,region,min_supply_ratio,min_supply_rounding,min_supply_kind,reason
MS50TH70,1,COS_Serum,SG_Distributor,0.5,ceil,required,代理店への最低供給量（MS50 のまま）
MS50TH70,1,COS_Serum,TH_Distributor,0.5,ceil,required,代理店への最低供給量（MS50 のまま）
MS50TH70,1,COS_Cream,SG_Distributor,0.5,ceil,required,代理店への最低供給量（MS50 のまま）
MS50TH70,1,COS_Cream,TH_Distributor,0.7,ceil,required,タイのクリームの最低供給量 7 割（依頼書 BSSEAF-COS-LOOP4）
```

`reason` の文は案。大杉さんの判断の参照先が決まったら、それに合わせる。

### 5.2 数量の確認（再集計。git の対象の CSV だけ）

| 鍵 | 週の需要 → 最低（週の数） | ① | 最低の合計 | 基準の数量枠 | 新しい数量枠 | ③ |
|---|---|---:|---:|---:|---:|---:|
| クリーム TH（7 割） | 2 → 2（13）、3 → 3（91） | 299 | 299 | 274 | **299** | 0 |
| クリーム SG（5 割） | 3 → 2（13）、5 → 3（143） | 754 | 455 | 691 | **666** | 88 |
| 合計（SG＋TH） | | 1,053 | 754 | 965 | 965 | 88 |

- 数量枠の候補：タイは 299 以上（最低）で、299 以下（元の需要）。だから 299 しかない。シンガポールは 965 − 299 ＝ 666 ≧ 455 で成り立つ。
- **過去の案は使わない**。数量枠は条件から一つに決まる。参考として、P1（`docs/scenarios/cosmetics.md`）はタイ 211 で、この条件を満たさない。
- SKU のクリームの供給の対象の合計（直営店 416・EC 299・SG＋TH 965）は変わらない。美容液も変わらない。

**週の選び方の近似**（再集計。道具の `select_mode1_capacity` ではなく、付録 MS50 の選択の台帳から手で数えた）：

- 前提：SG と TH の代理店は、工場までの週が同じ（DC→代理店 1 ＋ 海上 2 ＋ 判定済み倉庫 1 ＝ 4 週、`ss_days` 0。`sc_tree_master.csv`）。だから、同じ要求週で TH の削りを SG に移しても、工場の週の必要量は同じ。
- 基準（MS50）：減らす区間は SG が 2029-W19〜W50、TH が 2029-W26〜W50（週 1 lot、計 25）。SG は 2029-W20 以降、毎週 2 lot 減って最低（5 → 3）に達しているので、同じ週に余地は無い（W19 の余地 1 lot だけ）。
- 近似：TH の 25 lot を、後ろから SG の余地のある週へ繰り越す（道具の繰越と同じ向き）。結果は次のとおり。
  - SG の ③ ＝ 88。減らす区間は **2029-W07〜W50（44 週）**。繰越が入る週は 13 週（W07〜W19）。
  - 減らす週の SG の選んだ量は、すべて 5 lot 中 3 lot（60％）。週の最低は MS50 と同じ 60％。
  - 置けずに残った量は 0（衝突なし）。
- 時間の可否：削りを前の週へ移すので、累計の必要量はどの週でも MS50 以下になる。だから MS50 の参考値（0）は悪くならない見込み。ただし、前の週を減らして空いた能力で後の週の分を作り置きする形になる。在庫と年齢は増える方向。
- **この近似は道具の結果ではない**。道具は、各工場の週の超過 e と繰越を、鍵の残りに比例して配る（`_largest_remainder`）。T2 で道具の台帳を出し、この近似と照らす。

## 6. 比べる試行の手順と、受入の条件（後の試行。担当は計画のレビューの後に決める）

| 段 | 中身 | 出力 | 止める条件 |
|---|---|---|---|
| T0 | 写しと入力を作る（§3.2 の 1、§5.1 の 2 ファイル）。入力のハッシュを記録 | 写し、数量枠と方針のファイル | — |
| T1 | 基準 MS50 を再現（§3.2） | `udp/` 一式、年齢 | 付録とバイト一致しない |
| T2 | 新しい案（TH70）を同じ手順で実行。`--policy-file` は MS50TH70、`--allocation-file` は新しい数量枠 | `udp/` 一式、終了コード | 終了コード 1（不整合）。3 が出たら、§5.2 の数え直しの誤りとして原因を調べる |
| T3 | 比べる（下の表）。年齢は `shelf_life_check`（許容 52） | 比べる表 | — |

T2 の終了コード 4（未達）、⑤ ＞ 0、年齢の 52 週超は、**有効な結果**として残す。そのうえで、原因（どの要求週・どの lot が押し戻されたか）を `udp_result_by_request.csv` と LOVEM で追う。この一つの案が未達でも、「すべての配分に解が無い」とは書かない。この条件では数量枠の候補が一つしかないので、残る打ち手は週の選び方の規則か、業務の条件の側になる。その場合は大杉さんへ戻す。

**比べる項目と受入の条件**（依頼書 §5）：

| 観点 | 確かめること | 受入の条件 |
|---|---|---|
| 固定する条件 | 需要・期間（173 週）・能力・プラグイン・判定の時点（計画の終わり）・単位（lot）・受渡点（代理店への引渡し）が両案で同じ | 入力のハッシュの差が、数量枠と方針のファイルだけ |
| 数量 | SKU × チャネル × 要求週で、①＝②＋③、②＝④＋⑤。Flow Check 表2 と照合（道具の `rc 0`） | 全行で成立 |
| 最低供給量 | `udp_min_supply_check.csv` で 4 鍵の `plan_ok`・`delivered_ok` | タイのクリームは 104 週すべて当週 ④ ＝ ①（7 割切り上げ）。ほかの 3 鍵は 5 割を下回る週 0 |
| 時間の制約 | 参考値（`ontime_short_ref`）は試行の前に記録し、実納品・⑤ と照らす | 参考値を予測として使わない。⑤ は実行の結果で判断 |
| ほかの市場 | SG クリーム：③・減らす区間の始まりと長さ・週の最低の率・前半と後半の率。直営店・EC・美容液：①〜⑤ が MS50 と同じか | 変化を表に出す（採否は大杉さん） |
| 在庫・年齢 | 作り置きの最大（supply point の I ＝ 工場の完成品倉庫）、先入れ先出しの年齢の最大と 52 週超。Lot_ID の滞留は参考の列として分けて出す | 52 週超 0（COS-R05）。超えたら未達として記録 |
| 金額 | 評価するなら、付録の `measure.py` と同じ比べ方（P2-a の `make_allocation.py` の単位の貢献 − 固定の 213,719,220 円）。数量配分の経路は「財務は未評価」で、これを 0 円と読まない | 名前は「比べるための評価の額」。営業利益と呼ばない |
| 根拠 | 入力・方針・数量枠のファイルとハッシュ、commit、`code_dirty`、プラグイン、実行した担当、出力の場所、`--knowledge-file`・`--decision-ref` | `udp_plan.json` と報告書に書く |

## 7. 未確認の事項、人の判断が要る事項、知識の更新の候補

**大杉さんに決めてほしいこと**：

| 一言の決定 | 中身 | 推奨と理由 |
|---|---|---|
| **タイのクリームは全量を守る、として進める**（**決定済み**：2026-11-06、大杉さん「Proceed as full」） | 7 割・切り上げは、このモデルの需要（週 2・3 lot）では元の需要と同じ量になる。業務の言葉では「タイのクリームは減らさない」と同じ意味で、数量枠も 299 しかない | 推奨。要求の文のまま実行できる。「7 割」という比率に余地を持たせたい意図なら、需要を lot より細かく持つか比率・端数を変えることになり、どちらも業務の要求の変更なので別の判断になる |
| **後の試行 T0〜T3 を写しで行う** | §6 の手順で、MS50 と TH70 を比べる | 推奨。数量では両立し、コードの変更も要らない見込み。届くか・年齢は実行でしか分からない |

**未確認の事項**：

- 道具の実際の選び方（§5.2 は近似）。実納品・⑤・年齢・評価の額。基準の再現（コードが `6e4a534` から変わっていることを含む）。いずれも再実行は未実施。
- 比べるための評価の額の計算（`measure.py`・`make_allocation.py`）は、所在と式の形だけを見た。単価の中身は読んでいない。
- 試行の補足文の `--unallocated-note` は、MS50 の試行の文をそのまま使う案。今回の判断の参照先（`--decision-ref`）は未定。

**知識の更新の候補**（段階 8、Claude君へ）：

1. Start Here R18（または化粧品の行）に、年齢の許容 52 週の業務の根拠（化粧品設計書 v0.5 の A6・COS-R05）への導線を足す。今は道具の引数としてしか出てこない。
2. 意味体系 §6.1 に、「lot が小さいと、比率と切り上げで最低が元の需要と同じになり、比率の差が業務の意味を持たない」ことを適用条件として足す（化粧品のタイのクリーム：7 割＝10 割）。
3. 同じ名前で中身の違う `allocation_qty_P2a2.csv` が 2 つある（§3.1）。どちらを正とするかを `docs/scenarios/cosmetics.md` に書く。
4. 依頼書の `knowledge_used` の版（v0.4）と正本の版（v0.5）の差。

## 8. 読んだファイル（読んだ順）

| # | ファイル | 確かめ方 |
|---|---|---|
| 1 | `requests/RequestLetter_BSSEAF_Cosmetics_MinimumSupply_Reallocation_to_NewAgent.md` | 文書 |
| 2 | `AGENTS.md`（冒頭、のち全体） | 文書 |
| 3 | `docs/WOM_Start_Here.md`（R23 の行、のち全体） | 文書 |
| 4 | `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv` | 文書・再集計（行数） |
| 5 | `CLAUDE.md`（R23・最低供給量の記述の有無を grep で） | 文書（記述は無かった） |
| 6 | `docs/bsseaf/WOM_BSSEAF_Process_Knowledge.md` | 文書 |
| 7 | `docs/semantics/supply_allocation.md` | 文書 |
| 8 | `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_Report.md` | 文書 |
| 9 | 同付録 `README.md`、`policy/udp_policy_MS70.csv`、`scripts/run_trial.py` | 文書・コード |
| 10 | `docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv`（と付録の一覧） | 文書 |
| 11 | 付録 `udp/MS50/` の 6 ファイルの見出し | 文書 |
| 12 | `wom/allocation/upper_demand_plan.py` の 93〜512 行 | コード |
| 13 | `data/sample/cosmetics-sg-th-2027-2029/` の `planning_config.csv`・`sc_tree_master.csv`（クリーム）・`capacity_plan.csv`（冒頭） | 文書 |
| 14 | `docs/scenarios/cosmetics.md` の 60〜236 行 | 文書 |
| 15 | `docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/allocation_qty_P2a2.csv`（ハッシュの比較） | 再集計 |
| 16 | `requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.5.md`（年齢・残存期間を grep で） | 文書 |
| 17 | 再集計：`demand_forecast.csv`、10、MS50 の `udp_selection_ledger.csv`・`udp_result_by_request.csv`・`udp_min_supply_check.csv`・`udp_capacity_check.csv` | 再集計 |
| 18 | `tools/run_quantity_allocation.py` の 405〜465 行、`tools/shelf_life_check.py` の引数、`wom/allocation/handoff.py` の `check_quantity_quota` | コード |
| 19 | `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md` §1・§4.1・§4.2、`docs/design/WOM_BSSEAF_MultiAI_Loop_Design_v0.1.md` §2、`docs/design/drafts/WOM_Upper_Demand_Plan_DetailDesign_v0.1.md` §3.2（と見出し） | 文書 |
| 20 | 付録 `scripts/measure.py`（評価の額の式の所在）、P2-a の付録の一覧 | コード（所在のみ） |

## 9. BS-SEAF の記録

| 項目 | 中身 |
|---|---|
| 読む前に受け取っていたもの | 依頼書と、セッションに自動で読み込まれた文脈（`CLAUDE.md`、直近の commit の件名を含む git の状態）。直近の commit の件名に「minimum supply adopted for cosmetics (50%)」があった |
| 辿った経路 | §4 の「探し方の記録」 |
| 時間 | 始め 2026-11-06 02:55（最初の確認の三問）。合図の後に再開し、本書を書き終えたのは 03:04（端末の時計。待ち時間を含む。合図を待った時間は分けて測っていない） |
| 質問と手戻り | 最初の確認の後、大杉さんから質問が 1 つあった（下の誤り）。計画の中身の手戻りは無し |
| 誤り | 最初の確認の報告で「`CLAUDE.md` に R23 や最低供給量 5 割の採用の記述がある」と書いた。実際には `CLAUDE.md` に該当の記述は無い。R23 は自分で読んだ Start Here の 103 行目、「最低供給量 5 割の採用」は自動で渡された git の状態の commit の件名にあった。出どころを確かめずに書いた（進め方の知識 §2 の「確かめる前に前提にした」型）。大杉さんの確認で分かった |
| 人の橋渡し | 転記・連絡 0。git の操作 0（commit は大杉さん）。業務の判断：§7 の 2 件（うち H1 は決定済み、H2 は待ち）。レビューへの対応：質問 1 件 |
| 変えたもの | リポジトリには本書と commit メッセージの下書きだけ。Data・Parameter・Core・道具は変えていない |

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-06 | 初版 |
| v0.1（追記） | 2026-11-06 | 大杉さんの決定 H1（タイのクリームは全量を守る）を記録。中身の数量・手順は変えていない |
