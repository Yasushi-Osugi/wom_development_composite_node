# LOVEM run folder — データ辞書（schema `lovem-a1`、observer 0.1.0）

- 対象：LOVEM on WOM 段階 A（観測）の run フォルダ
- 設計の正本：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`（以下「設計書」）
- 依頼書：`requests/RequestLetter_LOVEM_StageAB_EVThailand_to_CodeKun.md`
- 生成：`python -m tools.lovem_observe --model-dir <model> --out <run folder> [--q12] [--se2-compare-sha <sha>]`
- **この辞書が、独立 checker（段階 C）の唯一の拠り所。** 実装コード（`wom/lovem/*`）を読まなくても照合できるように書いている。

---

## 0. 設計書 §8.2 との違い（変更点と理由）

| # | 設計書 §8.2 | この run フォルダ | 理由 |
|---|---|---|---|
| 1 | `psi_intervals.jsonl`（1ファイル） | `psi_intervals/<product>__<phase>.jsonl.gz`（snapshot ごとに1ファイル）。ファイル一覧は `manifest.json` の `snapshots[].intervals_file` | ev-thailand で 1 ファイルにすると 1.5GB（304万区間）。snapshot ごとに分けて gzip にすると計 22MB。viewer は final だけを読める。列は §8.2 のまま |
| 2 | `events.jsonl` / `relations.jsonl` / `source_evidence.jsonl` / `demand_anchors.jsonl` | 同名に `.gz` を付けた gzip JSONL | 容量（events だけで 200MB → 4.6MB）。中身の列は変えていない |
| 3 | nodes.csv の `physical_site_id`、`profit_zone` | **無い** | 段階 A では取得していない（profit_zone は段階 D）。空欄で出すと「取得済みの空」と誤読されるので列ごと置かない |
| 4 | — | nodes.csv に `display_group`・`node_type`・`plan_mode`・`is_decoupling`・`lt_wks`・`transit_lt_wks`・`supply_role` を追加 | 縦軸の配置と、push／pull の区別に必要 |
| 5 | — | events に `evidence_level`・`detail` を追加 | 瞬時イベントにも証拠区分が要る。`detail` は種別ごとの補足（§2.7） |
| 6 | — | relations に `method` を追加 | derived の関係は計算方法が必須（設計書 §8.2） |
| 7 | capacity.csv の列 | `product_id`・`op_shifts` を追加 | node_id は製品をまたいで一意だが、読みやすさのため。休業の元になる週の状態 |
| 8 | demand_anchors の列 | `run_id`・`required_week_label`・`occurrence`・`evidence_level`・`evidence_ref` を追加 | 同じ lot_id が同じ週・同じ市場に2回以上現れた場合を区別するため（`occurrence`） |
| 9 | — | 追加ファイル：`headless_snapshot.json`、`verify.json`、`q12.json`、`se2_case.json`、`ppc/` | 再現・自己検査の記録。`ppc/` は現行 PPC の出力をそのまま置いただけで、段階 D の観測ではない |

---

## 1. 共通の約束

### 1.1 文字コード・形式

- すべて UTF-8。CSV は BOM なし、改行 `\n`、1 行目がヘッダ。
- JSONL は 1 行 1 JSON オブジェクト。`.gz` は gzip 圧縮した JSONL（Python なら `gzip.open(path, "rt", encoding="utf-8")`）。
- JSON の `null` は「値が無い（取得していない／該当しない）」。数値の `0` は「0 と観測した」。**両者を混同しない。** CSV では `null` を空欄で表す。

### 1.2 ID と週

- `run_id`：`<case>@<code_sha 先頭7桁>[+dirty]:<label>`。1 つの run フォルダの全ファイルで同じ値（`q12.json` の ON 側だけは `label=q12`）。
- `product_id`：製品名（sc_tree_master の `product_name`）。
- `node_id`：エンジンの `PlanNode.node_id`（例 `IN:mom:Factory_Import_CN:EVmaker_Import`）。製品を含むので run 内で一意。表示名は nodes.csv の `node_name`。
- `lot_id`：エンジンの Lot_ID 文字列（例 `EVmaker_Import:BKK:2026-W09:00001`）。**変更も新設もしていない。** 同じ lot_id は複数のノード・週・区分に現れる（設計書 §6.2 最終行）。
- `week_index`：weeks.csv の連続番号（0 始まり）。**週の長さ・差は必ず week_index で計算する**（`YYYY-Www` 文字列から計算しない。2026 年は W53 がある）。

### 1.3 数量

- 1 つの lot_id が PSI リストに 1 回現れること＝1 lot。`quantity` はその 1 出現あたりの量で、段階 A では常に `1`、`unit` は常に `"lot"`。
- 件数だけの記録（lot_id を持たない記録）は `lot_id=null`、`quantity=件数`。

### 1.4 証拠区分 `evidence_level`

| 値 | 意味 |
|---|---|
| `observed` | 実行中にエンジンのデータ構造からコピーした値 |
| `derived` | observed の値から、`method` に書いた規則で計算した値 |
| `reported` | 他者の報告値（段階 A では使っていない） |
| `unknown` | 取得できない。段階 A では該当する行を**作らない**（manifest の `coverage.known_gaps` に書く） |

### 1.5 `identity_basis`（何を同一とみなすか）

- PSI の状態は `(run_id, snapshot_id, product_id, node_id, layer, bucket, lot_id, role_id)` を単位とする。
- 同じ lot_id が別のノード・別の週にあっても、それだけで「同じ物理的な個体が移動した」とはしない。物の移動は `relations.jsonl` の関係がある場合に限る。
- 同じ lot_id が区間として続いていても、同一個体の連続滞留の証明ではない（設計書 §8.5）。
- `role_id` は段階 A では常に `"-"`（ノード単位のリストで、部材役割を区別していない）。

---

## 2. ファイル別

### 2.1 `manifest.json`

| キー | 意味 |
|---|---|
| `schema_version` / `observer_version` | `lovem-a1` / `0.1.0` |
| `run_id`, `case`, `created_at` | §1.2。`created_at` は再現性の比較対象外 |
| `code_sha` | 実行時の `git rev-parse HEAD` |
| `dirty` / `dirty_diff_hash` / `dirty_scope` / `untracked_in_scope` | `wom`・`tools`・`data` の未 commit 差分（`git diff HEAD --binary`）と未追跡ファイル（パス＋内容 SHA-256）を合わせた SHA-256。scope 外（Vault 等）は含めない |
| `model_dir`, `model_hashes` | モデルフォルダの各ファイルの SHA-256（実行前） |
| `model_unchanged_by_run` | 実行後にもう一度ハッシュを取り、同じなら true。実行はモデルの**複写**に対して行う |
| `environment` | Python・OS・numpy・pandas・matplotlib の版 |
| `plugins` | 使ったプラグイン（golden の config と同じ3つ） |
| `products` | 製品の順（縦軸の製品ブロックの順） |
| `weeks` | 週数、最初と最後の週、W53 の週、7日刻みでない箇所、需要が最初に正になる週 |
| `snapshots[]` | 採取した snapshot の一覧：`snapshot_id`、`phase`、`product_id`、`layers`、`weeks`（[最初, 最後]の index）、`complete`、`intervals_file`、`n_intervals` |
| `counts` | anchors・digests・intervals・events・relations の件数。`expanded_occurrences_by_snapshot` は `"<snapshot_id>|<layer>|<bucket>"` ごとの Σ((end−start+1)×multiplicity) |
| `timing_s` | 実行時間（非業務項目。比較対象外） |
| `coverage` | 採取段階ごとの状態（`stages`）、Kitting（`not_applicable` ＝ Stockyard が無い／`present` ＝ Stockyard の PSI は区間として採取済みだが、`node.kitting` の記録は lovem-a1 では採取していない）、`known_gaps`（取得できない対応の一覧）、`arrival_unlinked`（出荷と結べなかった到着の件数）、期間端の扱い |

### 2.2 `nodes.csv`

| 列 | 意味 |
|---|---|
| `product_id`, `node_id`, `node_name` | §1.2 |
| `parent_id` | 親の node_id。root は空欄 |
| `tree_side` | `outbound` / `inbound` |
| `display_order` | 縦軸の順（run 全体で 0 からの通し番号）。製品ごとに、Outbound を post-order、続いて各 Inbound root を pre-order |
| `display_group` | `outbound_postorder` / `inbound_preorder` |
| `node_type` | `leaf_out` / `dad` / `supply_point` / `mom` / `leaf_in` / `stockyard` |
| `plan_mode` | 実行後の値：`pull` / `push`（push のデカップリング点）/ `push_sub` |
| `is_decoupling` | 1 / 0（実行後の値） |
| `lt_wks`, `transit_lt_wks` | エンジンの属性値（週） |
| `supply_role` | エンジンの属性値 |

### 2.3 `weeks.csv`

| 列 | 意味 |
|---|---|
| `week_index` | 0 からの連続番号 |
| `engine_week_label` | エンジンの週ラベル `YYYY-Www` |
| `iso_week_start` | その ISO 週の月曜日（`YYYY-MM-DD`） |
| `period_role` | `warmup`（需要が最初に正になる週より前）／`plan`。ev-thailand-2026 は warmup が無く、全週 `plan` |

計画期間の外（期間前・期間後）の週は行を持たない。期間外に関わる lot は events（`backward_past_due`、`arrival_beyond_horizon`）で表す。

### 2.4 `demand_anchors.jsonl.gz`

Lot 生成（`assign_demand_lots_from_dict`）の直後、どのプラグイン・Backward よりも前の、leaf_out の `psi4demand[w][S]`。Holiday の demand_multiplier で後から足された lot（`HOL:` で始まる ID）はここには無い。

| キー | 意味 |
|---|---|
| `demand_key` | `"<product_id>|<market_node_id>|<required_week>|<lot_id>|<occurrence>"` |
| `lot_id`, `product_id` | §1.2 |
| `market_node_id` | leaf_out の node_id |
| `required_week` / `required_week_label` | 元の要求週（index／ラベル） |
| `occurrence` | 同じ (市場, 週, lot_id) の何回目の出現か（1 始まり） |
| `quantity`, `unit` | 1, `"lot"` |
| `allocation_id` | 常に null（段階 E で接続） |

### 2.5 `psi_intervals/<product>__<phase>.jsonl.gz`

PSI リストの状態を区間に圧縮したもの（設計書 §8.5）。

| キー | 意味 |
|---|---|
| `interval_id` | run 内で一意（`iv` ＋ 8 桁、全ファイル通し） |
| `run_id`, `snapshot_id`, `phase`, `product_id`, `node_id` | `snapshot_id = "<product_id>/<phase>"` |
| `layer` | `demand`（`psi4demand`）/ `supply`（`psi4supply`） |
| `bucket` | `S`（予定 S）/ `CO` / `I` / `P` |
| `lot_id`, `role_id` | §1.2・§1.5 |
| `start_week_index`, `end_week_index` | **両端を含む**。週数＝end−start+1 |
| `quantity`, `unit` | 1 出現あたりの量（1, `"lot"`） |
| `multiplicity` | その各週に、その lot_id がリストに現れた回数（1 以上の整数） |
| `evidence_level`, `evidence_ref` | `observed`, `"snapshot:<snapshot_id>"` |

**phase（採取段階）**

| phase | 採った時点 | layer |
|---|---|---|
| `pre_backward` | `BackwardPlanner.run(product)` の直前（HOOK_PRE_PLAN の後） | demand |
| `post_backward` | `BackwardPlanner.run(product)` の直後 | demand |
| `post_backward_hooks` | HOOK_POST_BACKWARD の全リスナーの後 | demand |
| `post_copy` | `copy_demand_to_supply` の直後 | supply |
| `post_push_setup` | `PushProductionPlanner.setup_all` の直後（push_config のある製品だけ） | supply |
| `final` | 全製品の計画と PPC の後（headless の `_psi_signature` の直前） | demand と supply |

**圧縮規則**

- `I`・`CO`（両 layer）：同じ lot_id が、同じ multiplicity で、連続する週に現れる間を 1 区間にする。multiplicity が変われば区間を分ける。
- `P`・`S`：常に単週区間（start = end）。連続する週の入庫・要求を 1 本の線にしない。
- どの snapshot も全週（0〜n−1）を採取しており、欠測週は無い（`manifest.snapshots[].complete=true`）。

**週ごとの多重集合への戻し方（checker 用）**

区間ごとに start..end の各週へ `(lot_id, role_id, quantity) → multiplicity` を加える。これで得られる多重集合が、`state_digests` の同じ週の値と一致する。

`展開出現件数 = Σ((end−start+1) × multiplicity)`、`数量期間和 = Σ((end−start+1) × quantity × multiplicity)`。

### 2.6 `state_digests.jsonl`

圧縮**前**に、エンジンのリストから直接取った値。phase ごと・layer ごとに、**全ノード × 全週 × 4 区分**の行がある（空リストも行を持つ）。

| キー | 意味 |
|---|---|
| `run_id`, `snapshot_id`, `phase`, `product_id`, `node_id`, `week_index`, `layer`, `bucket` | 対象のセル |
| `entry_count` | リストの長さ（出現件数） |
| `total_quantity` | Σ quantity（段階 A では entry_count と同じ） |
| `multiset_sha256` | §3 の正規化による多重集合ハッシュ |
| `ordered_sha256` | 元リストの順序のハッシュ（§3）。区間からは復元できない（順序の監視用） |

### 2.7 `events.jsonl.gz`

瞬時の記録。区間に丸めない。

| キー | 意味 |
|---|---|
| `event_id` | run 内で一意。`actual_ship` だけは `"ship:<product>:<node_id>:<week_index>:<sequence>"`、それ以外は `ev` ＋ 8 桁 |
| `event_type` | 下表 |
| `product_id`, `node_id`, `week_index` | その記録のノードと週 |
| `sequence` | 同じノード・週のリスト内での位置（0 始まりの整数）。位置が無い記録は文字列 `"unknown"` |
| `lot_id` | 件数だけの記録は null |
| `role_id`, `quantity`, `unit` | §1.3・§1.5 |
| `origin` | 取得元のエンジンの記録名 |
| `evidence_level`, `evidence_ref` | §1.4。`evidence_ref` は `source_evidence` の `evidence_id` |
| `detail` | 種別ごとの補足（無い種別ではキー自体が無い） |

| event_type | 意味 | lot_id | evidence_level |
|---|---|---|---|
| `actual_ship` | Supply Simulation の実出荷。`ForwardPlanner._actual_s[node][w]` の各要素（sequence＝リスト内の位置）。予定 S とは別 | あり | observed |
| `arrival` | node 間の伝播で、受け手ノードの `psi4supply[w][P]` に追加された lot。`detail.from_node_id`（送り手）、`detail.ship_week_index` | あり | observed |
| `bridge_arrival` | MOM から supply_point へのブリッジ（Forward Phase 2）で、supply_point の P に入った lot（OutBound 処理の直前の値） | あり | observed |
| `arrival_beyond_horizon` | 送り手は出荷したが、到着週が計画期間の外で、どの P にも入らなかった lot。`week_index` は出荷週、`detail.arrival_week_index` | あり | derived |
| `backward_past_due` | Backward が期間の前へ置こうとして置けなかった需要（`BackwardPlanResult.past_due_lots`） | あり | observed |
| `push_shortfall` | push ノードで予定 S に対して物が無く出荷できなかった件数（`PlanNode._push_shortfall`） | null（件数） | observed |
| `forward_shortfall_weeks` | Forward の不足件数（`ForwardPlanResult.shortfall_weeks`） | null（件数） | observed |
| `forward_cap_hard_events` / `forward_cap_soft_violations` / `forward_closure_p_deferred` / `forward_closure_s_planned` / `forward_kitting_capacity_deferred` | 同名の `ForwardPlanResult` の記録（件数） | null | observed |
| `forward_closure_p_unplaced` | 休業で期間内に置けなかった P（lot ごと） | あり | observed |
| `mode4_closure_shifted` | Mode 4 が休業週から移した件数。`detail.to_week_index` | null | observed |

ev-thailand-2026 に実際に現れるのは、`actual_ship`・`arrival`・`bridge_arrival`・`backward_past_due`・`forward_shortfall_weeks`・`push_shortfall` の6種。

**書かないもの**：どの出荷がどの要求（S／CO）を満たしたか。エンジンに記録が無いため、作らない（manifest `coverage.known_gaps`）。

### 2.8 `relations.jsonl.gz`

記録から裏付けのある対応だけ。推測した引当は入れない。

| キー | 意味 |
|---|---|
| `relation_id` | `rel` ＋ 8 桁 |
| `relation_type` | `ship_to_arrival`（送り手の `actual_ship` → 受け手の `arrival`）／`ship_to_bridge`（MOM の `actual_ship` → supply_point の `bridge_arrival`） |
| `from_ref`, `to_ref` | event_id |
| `demand_key` | 常に null（要求との対応は取得していない） |
| `quantity` | 1 |
| `evidence_level`, `method`, `evidence_ref` | `derived`、計算規則、`source_evidence` の id |

**method の規則**

- `ship_to_arrival`：伝播の1回の呼び出しで、受け手の週 w の P の末尾に追加された lot 列を、送り手の週 (w − LT) の `_actual_s` の列に対して、順序を保った部分列として先頭から対応付けた（LT は、InBound が `transit_lt_wks`（0 なら `lt_wks`）、OutBound が子の `lt_wks`）。
- `ship_to_bridge`：supply_point の P[w] ＝ 各 MOM root の `_actual_s[w]` を `in_roots` の順に連結したもの、として位置で対応付けた。

### 2.9 `capacity.csv`（最終状態）

| 列 | 意味 |
|---|---|
| `product_id`, `node_id`, `week_index` | 対象 |
| `raw_hard`, `raw_soft` | エンジンの生の値。`0.0` はエンジンの約束で「未設定」 |
| `effective_limit` | `PlanNode.processing_limit(w)`：休業=`0.0`、未設定=空欄、それ以外=raw_hard |
| `planned_capacity` | `PlanNode.planned_capacity(w)`：休業=`0.0`、未設定=空欄、それ以外=raw_soft |
| `is_open` | 1 / 0 |
| `op_shifts` | 週の操業直数。空欄＝未設定（常に稼働）、0＝休業 |
| `source_ref` | `final_state` |

### 2.10 `source_evidence.jsonl.gz`

判定に必要な原記録。存在しない記録は作らない。

| キー | 意味 |
|---|---|
| `evidence_id` | `src` ＋ 8 桁 |
| `source_kind` | 下表 |
| `source_locator` | 対象（`<product>/<node_id>/<week_index>` 等） |
| `source_hash` | `payload` の SHA-256（§3 の JSON 正規化） |
| `payload` | 元記録のコピー |

| source_kind | payload |
|---|---|
| `forward_actual_s` | そのノード・週の `_actual_s` リスト（元の順序） |
| `forward_propagation_append` | `{from_node_id, to_node_id, arrival_week_index, ship_week_index, lots, via}` |
| `forward_bridge_p` | `{lots, sources: [[mom_node_id, その週の _actual_s], ...]}` |
| `forward_ship_beyond_horizon` | `{lots, arrival_week_index, via}` |
| `forward_result` | `ForwardPlanResult` の記録リスト一式（週はラベル） |
| `backward_result` | `{past_due_lots: [[node_id, lot_id, week_index], ...]}` |
| `push_setup_result` | `{mode, push_lots_total, push_events, mode4_closure_shifted}` |
| `push_shortfall` | `{"<week_index>": 件数}`（0 の週は省略） |

### 2.11 `se2_case.json`

SE2 の**定義と週別の件数**。lot の分類（早出し・当週・後週・未達）はしていない。

| キー | 意味 |
|---|---|
| `model_dir`, `plugins`, `product_id`, `node_name`, `node_id`, `target_weeks`, `closure_weeks` | 対象 |
| `run_id`, `code_sha` | この run |
| `formulas` | 各数値の式（下表） |
| `target_week_rows` | 対象週の `planned_s`・`actual_s`・`signed_gap`・`shortfall`・`excess`・`push_shortfall` |
| `sum_*` | 対象週の合計 |
| `horizon_totals` | 全期間の `actual_s`・`planned_s`・`push_shortfall`、不足のある週 |
| `comparison_run` | 比較 run（Explicit Closure 実装前のコード `4ed2f14`、同じプラグイン）の同じ週の値 |
| `candidates`, `which_is_168` | 168 になるのはどの式か |

| 項目 | 式 |
|---|---|
| `planned_s` | `state_digests`（snapshot `<product>/final`、layer `supply`、bucket `S`）の `entry_count` |
| `actual_s` | そのノード・週の `actual_ship` イベントの件数 |
| `signed_gap` | planned_s − actual_s |
| `shortfall` / `excess` | max(0, planned_s − actual_s) / max(0, actual_s − planned_s) |
| `push_shortfall` | `push_shortfall` イベントの quantity |
| 168 | 対象週の shortfall の和（＝ push_shortfall の和） |

### 2.12 そのほか

| ファイル | 内容 |
|---|---|
| `headless_snapshot.json` | `tools/run_headless_from_folder.run()` の返り値（golden と同じ形） |
| `verify.json` | 生成側の自己検査（区間を戻して state_digests と比較）。独立 checker の代わりにはならない |
| `q12.json` | 観測 OFF と ON の指紋（全リスト・`_actual_s`・Forward/Backward の結果・push_shortfall・snapshot・PPC 出力ファイル）と一致判定 |
| `ppc/` | 現行 PPC の出力ファイル（そのまま） |

---

## 3. ハッシュの正規化規則

- **multiset_sha256**
  1. セルの各 lot_id について、`multiplicity`＝リスト内の出現回数を数える。
  2. 各エントリを1行 `f"{lot_id}\t{role_id}\t{quantity}\t{multiplicity}"` にする。
     - `quantity` が整数値なら小数点なしの10進（`1`）、そうでなければ Python の `repr(float)`。
     - `role_id` は `"-"`。
  3. 行を `(lot_id, role_id)` の Python 文字列順（Unicode コードポイント順）に並べる。
  4. `"\n"` で連結し（末尾に改行なし）、UTF-8 にして SHA-256 の16進小文字。
  5. 空のセルは空文字列の SHA-256（`e3b0c442…b855`）。
- **ordered_sha256**：元リストの lot_id をそのままの順に `"\n"` で連結し、UTF-8 → SHA-256。
- **source_hash**：`json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` を UTF-8 → SHA-256。

---

## 4. 既知の未取得（manifest `coverage.known_gaps` と同じ）

| 項目 | 状態 | 内容 |
|---|---|---|
| 需要の充足対応 | unknown | どの出荷がどの要求（S／CO）を満たしたかは、エンジンに記録が無い |
| pull モードの入庫 | 物の関係なし | デカップリング点より下流（と InBound の pull／decoupling コピー）は、P＝psi4demand の P のコピーで、伝播した出荷ではない。これらの入庫に `arrival` は無い |
| cap_hard の封印 lot | unknown | 件数だけで、封印された lot_id は記録されない |
| push_shortfall の lot | unknown | 件数だけで、出荷できなかった予定 S の lot_id は記録されない |
| push デカップリングの inline 伝播 | 観測なし | 親を持つ push デカップリング点は `ForwardPlanner.run` 内で直接伝播する。ev-thailand-2026 には該当なし（Factory_Import_CN は root） |
| 週内の順序 | 一部 | `sequence` はエンジンのリスト内の位置。ノードをまたいだ週内の処理順は記録していない |
