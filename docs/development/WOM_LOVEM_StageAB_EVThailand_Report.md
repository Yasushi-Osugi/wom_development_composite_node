# LOVEM on WOM 段階 A・B 報告（ev-thailand-2026）— 段階 A 中間報告

- 依頼書：`requests/RequestLetter_LOVEM_StageAB_EVThailand_to_CodeKun.md`
- 設計の正本：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`
- 実装：Code君（Claude Code, Windows）、2026-09-28
- 状態：**段階 A 完了（中間報告）**。段階 B（viewer）は、大杉さんの commit の後に着手する。
- commit・push はしていない。golden は変えていない。

---

## 0. 要約

1. 観測 adapter・区間 encoder／decoder・保存・データ辞書を作った。**保護対象の core は1行も変えていない。** 観測は、計画の呼び出し境界に読み取り専用のラッパーをその run の間だけ差し込む方式で、終了時に必ず外す。
2. A4 の受入条件（1〜5）はすべて満たした。
   - Q12：観測 ON／OFF で、全ノードの全リスト、実出荷、診断、PPC 出力が完全一致。
   - 区間の復元：state_digests の 37,856 行すべてと一致。
   - SE2：168 が再現した。
3. 設計書 §8.2 からは、保存の形だけを変えた（列は同じ）。`psi_intervals` を snapshot ごとのファイルに分け、大きい JSONL を gzip にした。1ファイルにすると 1.5GB あったためで、分けた後の run フォルダは約 50MB。
4. SE2 の 168 は、次の4つの式のどれでも 168 になる。**lot 単位の分類はしていない**（段階 C で Astra君が行う）。
   - 対象週（2026-W38・W39）の「予定 S − 実出荷」の和（150−132＋150−0）
   - 同じ週の正の不足の和
   - 同じ週の `_push_shortfall` の和
   - 比較 run（Explicit Closure 前のコード 4ed2f14、同じ週の不足 0）との差

---

## 1. A0：基準と実行条件

| 項目 | 値 |
|---|---|
| 基準 SHA | `d5e16f763cb50112603fb6ce6a99af4f61669f4b`（依頼書を commit した後の HEAD。依頼書に書かれた `5344816` の次の commit） |
| 未 commit の差分 | 新規ファイルのみ：`wom/lovem/`（7ファイル）、`tools/lovem_observe.py`、`tests/test_lovem_intervals.py`、`tests/test_lovem_observer.py`、`docs/development/lovem/`、本報告書。既存ファイルの変更なし（Obsidian Vault の変更は作業前からあり、対象外） |
| 依存 | Python 3.12.3（conda-forge）、numpy 1.26.4、pandas 2.2.2、matplotlib 3.9.2、Tk 8.6。OS：Windows 11 |
| テスト（基準時点） | 544 passed / 3 skipped（作業2の後に確認済み） |
| テスト（段階 A の後） | **562 passed / 3 skipped / 0 failed**（新規18件）。その後 gzip の書き出しを時刻固定に変えたため、LOVEM の18件だけ再実行して緑 |
| モデル | `data/sample/ev-thailand-2026`（実行はフォルダの複写に対して。原本のハッシュは前後で同じ） |
| プラグイン | HolidayCalendarPlugin・BufferingStockOptimizerPlugin・CapacityOverridePlugin（golden の config と同じ） |
| 計画期間 | 2026-W02〜2027-W52、104週（2026-W53 を含む。週の開始日はすべて7日刻み）。warmup なし（需要は 2026-W02 から） |
| 製品 | EVmaker_Local、EVmaker_Import |
| ノード（14） | EVmaker_Local：Sales_TH_BKK・PRO・ONL（leaf_out）、DC_EV_Local（dad）、SP_EV_Local（supply_point）、Factory_Local_TH（mom）、Battery_CN（leaf_in）<br>EVmaker_Import：Sales_TH_BKK_i・PRO_i・ONL_i（leaf_out）、DC_EV_Import（dad、デカップリング点）、SP_EV_Import（supply_point）、Factory_Import_CN（mom、push、Mode 4 LT=4）、Components_CN（leaf_in、push_sub） |
| Stockyard | 無し → Kitting は対象外（manifest に記載） |

### 1.1 採取可能項目の調査（設計書 §8.3 の段階ごと）

既存の基盤は次のとおり。

- `hook_bus.py`：5つの hook（PRE_PLAN・POST_BACKWARD・POST_COPY・POST_FORWARD・POST_PLAN）がある。
- `event_timeline.py`・`planning_debugger.py`：どちらも **lot 件数だけ**のスナップショットで、Lot_ID を持たない。planning_debugger は node_name をキーにしているため、製品をまたぐと衝突する。ID 単位の観測には使えない。

| 段階 | 項目 | 既存で採れる | 観測用の記録が要る（今回実装） | 採れない |
|---|---|---|---|---|
| 1 アンカー | Backward 前の元需要 | — | ✓ `assign_demand_lots_from_dict` の直後（HOOK_PRE_PLAN は Holiday の demand_multiplier と同じ hook で、登録順によっては書き換え後になる） | — |
| 2 Backward | Backward 直前の demand | — | ✓ `BackwardPlanner.run` の入口（製品ごとの pre hook が無い） | — |
|  | Backward 直後の demand | — | ✓ `BackwardPlanner.run` の出口（POST_BACKWARD は他のリスナーの後になりうる） | — |
|  | post-hook 後 | ✓ HOOK_POST_BACKWARD（全リスナーの後に採るため `HookBus.fire` の出口で採取） | — | — |
|  | 期間前へ置けなかった需要 | ✓ `BackwardPlanResult.past_due_lots`（lot_id つき） | — | — |
| 3 copy | copy 直後の supply | ✓ HOOK_POST_COPY（今回は `copy_demand_to_supply` の出口で採取。同じ時点） | — | — |
| 4 Mode 4 | setup 直後の supply P | — | ✓ `PushProductionPlanner.setup_all` の出口（hook が無い） | — |
|  | Mode 4 の予定・休業移動 | ✓ `PushSetupResult.push_events`・`mode4_closure_shifted`（件数） | — | — |
| 5 Forward | 実出荷の Lot_ID | ✓ `ForwardPlanner._actual_s`（private。run の後に読む） | — | — |
|  | node 間の到着（誰の出荷が、どの週に、どこへ） | — | ✓ `_propagate_to_parent`／`_propagate_to_child` の前後で受け手 P の末尾差分を採取 | — |
|  | MOM → supply_point のブリッジ | — | ✓ `_run_ot_push_pull` の入口で supply_point の P を採取 | — |
|  | 不足・封印・休業の診断 | ✓ `ForwardPlanResult` の各 record、`closure_*`（件数。`closure_p_unplaced` のみ lot_id つき） | — | — |
|  | push の不足 | ✓ `PlanNode._push_shortfall`（件数） | — | 不足した lot_id |
|  | cap_hard で封印された lot | 件数のみ | — | 封印された lot_id |
|  | どの出荷がどの要求を満たしたか | — | — | ✗（エンジンに記録が無い） |
|  | pull モードの入庫の出所 | — | — | ✗（P は需要のコピーで、物の伝播ではない） |
|  | 親を持つ push デカップリング点の伝播 | — | — | ✗（`ForwardPlanner.run` 内の直接処理。ev-thailand には該当なし） |
|  | Kitting | ✓ `node.kitting`、`kitting_*`（ev-thailand では対象外） | — | — |
| 6 完了後 | 最終 PSI（demand・supply） | ✓ HOOK_POST_FORWARD／POST_PLAN（今回は PPC の後の `_psi_signature` の入口で採取＝golden と同じ時点） | — | — |
|  | 能力・操業状態 | ✓ `cap_hard`／`cap_soft`／`processing_limit`／`planned_capacity`／`is_open`／`op_shifts` | — | — |
| 7 PPC | — | 段階 D（対象外） | — | — |

### 1.2 置き場所

- **`wom/lovem/`（新規パッケージ）**：観測・区間・保存・検査のコード。`wom/gui/app.py` には組み込んでいない（設計書 §5.4）。テストから import でき、段階 B の viewer も同じパッケージに置く予定。
- **`tools/lovem_observe.py`**：実行用 CLI。既存の `tools/run_headless_from_folder.py` と同じ層に置き、その `run()` をそのまま呼ぶ。計画の順序を二重に持たないため。

| ファイル | 役割 |
|---|---|
| `wom/lovem/observer.py` | 観測 adapter（ラッパーの設置と解除、run フォルダの書き出し） |
| `wom/lovem/intervals.py` | 区間 encoder／decoder、構造検査 |
| `wom/lovem/digest.py` | 多重集合・順序のハッシュ（正規化規則の実装。辞書 §3） |
| `wom/lovem/io.py` | run フォルダの読み出し |
| `wom/lovem/verify.py` | 生成側の自己検査（区間 → 週 → digests） |
| `wom/lovem/q12.py` | 観測 ON／OFF の指紋比較 |
| `wom/lovem/se2.py` | SE2 の定義と週別件数（分類なし） |

## 2. 保存した run フォルダ

`output/lovem/ev-thailand-2026/run_A/`（`.gitignore` の対象。段階 B の後に ZIP にして引き渡す）

| ファイル | 件数 | 容量 |
|---|---:|---:|
| `manifest.json` | — | 13 KB |
| `nodes.csv` / `weeks.csv` / `capacity.csv` | 14 / 104 / 2,912 | 2 KB / 3 KB / 120 KB |
| `demand_anchors.jsonl.gz` | 63,240 | 0.5 MB |
| `psi_intervals/`（11 snapshot） | 3,042,731 区間 | 22 MB |
| `state_digests.jsonl` | 37,856 | 17.6 MB |
| `events.jsonl.gz` | 476,134 | 4.6 MB |
| `relations.jsonl.gz` | 174,660 | 1.6 MB |
| `source_evidence.jsonl.gz` | 1,938 | 1.5 MB |
| `se2_case.json`、`q12.json`、`verify.json`、`headless_snapshot.json`、`ppc/` | — | — |

snapshot は、製品ごとに pre_backward・post_backward・post_backward_hooks・post_copy・final の5つです。push_config がある EVmaker_Import だけ post_push_setup が加わり、計11になります。

events の内訳：

| event_type | EVmaker_Local | EVmaker_Import |
|---|---:|---:|
| actual_ship | 248,100 | 48,020 |
| arrival | 97,700 | 18,740 |
| bridge_arrival | 48,850 | 9,370 |
| backward_past_due | 3,850 | 970 |
| forward_shortfall_weeks | 312 | 215 |
| push_shortfall | — | 7 |

relations は ship_to_arrival 116,440 件、ship_to_bridge 58,220 件です。出荷と結べなかった到着（arrival_unlinked）は 0 件でした。

## 3. A4 受入結果

| # | 条件 | 結果 |
|---|---|---|
| 1 | 観測 ON／OFF で PSI・実出荷・診断・PPC が完全一致（Q12） | **一致**（下記） |
| 2 | 全週の区間の復元が `state_digests` と一致 | **一致**：37,856 / 37,856 行（件数・数量・多重集合ハッシュ）。構造エラー 0、interval_id の重複 0、digest の無い区間 0 |
| 3 | 合成 PSI の往復テスト | **緑**（`tests/test_lovem_intervals.py` 12件：早出し・当週・遅れ・未達・同数量で別 ID・同じ ID の多重出現・欠測週・年跨ぎ・入力を変えないこと・構造検査） |
| 4 | 全テストが緑、golden 不変 | **562 passed / 3 skipped / 0 failed**。golden・core・サンプル CSV の変更なし |
| 5 | `se2_case.json` の 168 が再現 | **再現**（§4） |

**Q12 の比べ方**（`q12.json`、テスト `test_q12_observation_does_not_change_the_plan`）

同じ計測用フック（読み取りのみ）で、観測 OFF の run と、`observe_run` そのものを使った観測 ON の run を比べた。比べたものは次のとおり。

- 全14ノード × demand／supply の全週・全区分のリスト（**元の順序のまま**）
- `_push_shortfall`、plan_mode
- `ForwardPlanner._actual_s`
- ForwardPlanResult・BackwardPlanResult の全フィールド
- headless snapshot（forward・backward・ppc・psi）
- PPC の出力6ファイル

すべて一致した。

## 4. SE2 の定義（`se2_case.json`）

| 週 | 予定 S | 実出荷 | 符号付き差 | 正の不足 | `_push_shortfall` |
|---|---:|---:|---:|---:|---:|
| 2026-W38 | 150 | 132 | 18 | 18 | 18 |
| 2026-W39 | 150 | 0 | 150 | 150 | 150 |
| 計 | 300 | 132 | **168** | **168** | **168** |

- 比較 run（コード `4ed2f14`＝Explicit Closure 前）：同じ2週は 予定 S 100・実出荷 100、不足 0。差は 168。
  - 比較 run は `git archive 4ed2f14` を一時フォルダに展開して実行した。リポジトリは変えていない。
- 期間全体：実出荷 9,370、予定 S 9,770、`_push_shortfall` 400（2026-W02〜W06 の 232 と W38・W39 の 168）。比較 run でも 9,370／9,770／400 で、前回報告書の「総出荷 9,370・総不足 400 は前後で同じ」と一致する。
- **168 がどの lot か（早出し・当週・後週・未達）は判定していない。** push ノードの不足は件数でしか記録されないので、段階 C では予定 S と実出荷の lot_id の多重集合、要求週、送り手の出荷から照合することになる（辞書 §4）。

## 5. 性能（段階 A）

| 項目 | 値 |
|---|---|
| 観測つき実行（計画＋PPC＋採取） | 73.9 秒・75.6 秒（2回。うち採取・区間化 約59 秒、Forward のイベント化 約10 秒） |
| 観測なしの同じ実行 | 単独では計っていない（Q12 の OFF＋ON が合計 78 秒なので、10 秒台と見込む） |
| 自己検査（区間 → 週 → digests） | 65.8 秒・66.1 秒 |
| 区間数・展開出現件数 | 3,042,731 区間。final の supply：I 38,920＋49,850 lot-週、CO 140,742＋715,710 lot-週（Import＋Local） |
| ユニーク需要 ID（anchors） | 63,240 |

ピークメモリ、読み込み・線分生成・描画・選択の時間は、段階 B で計る。

## 6. 設計書と変えた点・未確認

1. 保存の形（辞書 §0）：`psi_intervals` を snapshot ごとのファイルに分け、大きい JSONL を gzip にした。列は設計書 §8.2 のまま。nodes.csv の `physical_site_id`・`profit_zone` は取得していないので、列ごと置いていない。
2. 採取の時点：アンカーを HOOK_PRE_PLAN ではなく Lot 生成の直後で採った（Holiday の demand_multiplier より前にするため）。final は PPC の後（golden の psi signature と同じ時点）。
3. 取得できない対応は作っていない（辞書 §4）：
   - 需要の充足の対応（どの出荷がどの要求を満たしたか）
   - pull モードの入庫の出所
   - 封印・push 不足の lot_id
4. 「予定 S」は Supply layer の S（`psi4supply[w][S]`）、「実出荷」は `_actual_s`。push ノードでは予定 S が需要の階段のまま、実出荷だけが減る。
5. 自己検査（`verify.py`）は生成側の確認であり、段階 C の独立 checker の代わりではない。

## 7. 再実行の手順

```powershell
cd C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial
python -m tools.lovem_observe --model-dir data/sample/ev-thailand-2026 `
    --out output/lovem/ev-thailand-2026/run_A --q12 --se2-compare-sha 4ed2f14
python -m pytest tests/test_lovem_intervals.py tests/test_lovem_observer.py -v
```

**再現性（実測）**：同じ条件で2回実行し、run フォルダの全ファイルを SHA-256 で比べた。違ったのは次だけで、他はすべてバイト単位で一致した（gzip はヘッダの時刻を 0 に固定している）。

- `manifest.json` の `created_at`・`timing_s`
- `se2_case.json` の比較列：2回目は `--se2-compare-sha` を付けずに実行したため、比較列が無い

---

（段階 B の結果は、この報告書に追記する）
