# LOVEM on WOM 段階 A・B 報告（ev-thailand-2026）

- 依頼書：`requests/RequestLetter_LOVEM_StageAB_EVThailand_to_CodeKun.md`
- 設計の正本：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`
- 実装：Code君（Claude Code, Windows）、2026-09-28
- 状態：**段階 A・B 完了**（段階 A は commit `81dc234`。段階 B は未 commit、§8 以降）
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

# 段階 B（描画）— 2026-09-29

## 8. 要約

1. Windows 単体の viewer（`python -m wom.lovem.viewer <run フォルダ>`）を、Tkinter と matplotlib（FigureCanvasTkAgg）だけで作った。Web 系は使っていない。`wom/gui/app.py` には組み込んでいない。
2. **B4 の受入条件 1〜5 はすべて満たした。**
   - ev-thailand-2026 の **全 63,240 ID・全 1,703,049 本の線分を描画**した。保存データの件数と一致する。
   - ID を選ぶと全ノードで強調され、元の記録へ移動でき、元の記録から図の位置へ戻れる。
   - 休業週は灰色で表示される。
   - 性能とメモリを測った。
   - スクリーンショットと起動手順を用意した。
3. viewer は保存データを読むだけ。再計画もファイルの書き込みもしない（テストで run フォルダのハッシュが前後で同じことを確認）。
4. テスト：**566 passed / 3 skipped / 0 failed**（段階 A の 562 件＋ viewer の 4 件）。golden・core・サンプル CSV は変わっていない。
   - その後、final 以外の段階の表示だけを直した（§17-3）。この変更の後は、viewer の4件だけを再実行して緑。
5. 引き渡し一式：`output/lovem/handoff_ev-thailand-2026.zip`（5.2MB、32 ファイル）。SHA-256 は `00badb50f6506823a13e2d8a3ca2e7507b0bc61fb9a5868c98a16a76b206689d`。

## 9. 作ったもの

| ファイル | 役割 |
|---|---|
| `wom/lovem/viewdata.py` | 描画モデル（Tk なし）：run フォルダを読み、区間・イベント・関係を描画区分ごとの線分配列（numpy）にする。表示範囲の切り出し、候補の検索、ID の履歴、SE2 の ID 一覧 |
| `wom/lovem/viewer.py` | Tk viewer 本体と、計測・スクリーンショット用の `--bench` モード |
| `tools/lovem_handoff.py` | Astra君への引き渡し一式（run フォルダ、辞書、再実行手順、SHA256SUMS、ZIP） |
| `tests/test_lovem_viewer.py` | 描画件数の一致、候補の検索、選択と履歴、Tk での全件描画・選択・元の記録・図へ戻る・拡大時の切り出し・run フォルダ不変（4件） |

段階 A のコードに入れた変更は1点だけで、観測の結果には影響しない。

- `observer.py` の manifest の文言：Stockyard がある場合の Kitting の記述を、実態（`node.kitting` は採取していない）に合わせた。ev-thailand は Stockyard が無いので、出力は変わらない。
- データ辞書の該当行も直した。

## 10. 画面の構成（設計書 §5・§6）

| 要素 | 実装 |
|---|---|
| 縦軸 | 最上部に Business Owner レーン（空欄、「段階 E で接続」と表示）。製品ごとにブロックを分け、nodes.csv の `display_order`（Outbound は post-order、続いて Inbound は pre-order）で並べる |
| ノードの帯 | 3 レーン：Demand／Supply・物（入庫・I・実出荷）／Supply・要求（予定 S・CO）。数量→金額のレーンは作っていない（段階 D） |
| 横軸 | 週（`YYYY-Www`、拡大に合わせてラベルを間引く）。左右の余白に、ノードごとの期間前・期間後の件数を表示し、クリックすると ID の一覧が出る |
| 記号 | Demand は破線・点線、Supply は実線、I は物レーンの水平線、CO は要求レーンの水平線、入庫と実出荷は縦の短い線（入庫は週の 1/4、実出荷は 3/4 の位置）、予定 S は要求レーンの一点鎖線の短い棒、出荷→到着の関係は細い灰色の実線、休業週は灰色の背景 |
| 未確認 | 入庫のうち、伝播の記録が無いもの（需要のコピー）は灰色の点線で描き、凡例と詳細欄で「出所の記録なし＝未確認」と表示する。記録の無い関係線は引かない |
| 誤読を防ぐ契約（§6.2） | P・I・CO・S を1本の線にしない（入庫と実出荷は縦線、I と CO はレーンを分けた水平線）。予定 S は要求レーンの棒で、実出荷の線としては描かない |
| 1 ID の位置 | 各レーンの中で、ID ごとに決まった高さ（Lot_ID の CRC32 から決める）に置く。ノードをまたいでも同じ高さになるので、選んだ ID を追いやすい。高さは数量・金額を意味しない |
| 線の描き方 | 描画区分ごとに1つの LineCollection（12個）。1 Lot ごとに Line2D や widget は作らない。表示範囲は numpy のマスクで切り出す |
| 上部の表示 | 総 ID・描画済み ID・未描画 ID（表示範囲外）・フィルタで除外した ID・線分数（描画中／全体）・状態（「全件描画 完了」は、全区分を全範囲で描いたときだけ出る） |

## 11. 操作（B2・B3）

| 操作 | 実装 |
|---|---|
| 拡大・スクロール | matplotlib のツールバー（拡大・移動・戻る）。マウスホイールで上下に移動。「全体表示」ボタン |
| ID の選択 | 図の線をクリックする。4px 以内の線を**全部**候補の一覧に出し、ID が1つだけならそのまま選ぶ（ダブルクリックで選び直せる）。Lot_ID を入力して選ぶこともできる |
| 選択の表示 | その ID の全ノードの線を黄色で強調する。詳細欄に、ノードごとの履歴（Demand・入庫・I・実出荷・予定 S・CO・関係、期間前・期間後）と、元の記録（events → `source_evidence`）の一覧を出す |
| 元の記録 ⇄ 図 | 元の記録の行をクリックすると、下の欄に `source_evidence` の中身（種類・場所・ハッシュ・payload）が出る。「この記録の図の位置へ戻る」で、そのノード・週へ拡大する |
| 区分のフィルタ | 12 区分それぞれのチェック。除外した ID の数を上部に出す |
| 読み込み | 別スレッドで読み、進捗バーと「中止」ボタンがある。Tk の更新は UI スレッドだけで行う（キュー経由） |
| SE2 | 「SE2 へ移動」で Factory_Import_CN の 2026-W34〜W44 へ拡大する。詳細欄に、対象週の予定 S・実出荷・入庫・I・CO の Lot_ID をそのまま並べる（分類はしない） |
| checks.csv | 「checks.csv を読む」で、段階 C の checker の出力を一覧表示する（読み込む口だけ） |

## 12. B4 受入結果

| # | 条件 | 結果 |
|---|---|---|
| 1 | 全 ID を描画し、描画件数が保存データと一致 | **一致**。線分 1,703,049 本（final の区間 1,232,269＋実出荷 296,120＋関係 174,660）をすべて描画。ID 63,240（anchors の数と同じ）をすべて描画。入庫 296,120＝伝播の記録あり 174,660＋未確認 63,240＋leaf_in の外部供給 58,220 |
| 2 | ID 選択で全ノード強調、元の記録へ移動、元の記録から図へ戻る | **動作**。スクリプト化した操作と Tk のテストで確認（§13・テスト）。手でのクリック操作は、大杉さんの実機確認をお願いしたい |
| 3 | 休業週が灰色 | **表示**。Factory_Local_TH の 2026-W32・2027-W32、Factory_Import_CN の 2026-W40・W41・2027-W40・W41（capacity.csv の is_open=0 の6週） |
| 4 | 性能 | §13 |
| 5 | スクリーンショットと起動手順 | §14・§15 |

## 13. 性能（ev-thailand-2026、Windows 実機）

| 項目 | 値 |
|---|---|
| 区間数 | final 1,232,269（全 snapshot では 3,042,731） |
| イベント数 | 476,134（うち描画する実出荷 296,120） |
| 関係数 | 174,660 |
| ユニーク ID | 63,240 |
| 展開出現件数（final） | 2,099,810（全 snapshot では 3,912,268） |
| lot-週（final の supply） | I 88,770、CO 856,452 |
| 保存容量 | run フォルダ 46.8MB、引き渡し ZIP 5.2MB |
| 読み込み（viewer 内、別スレッド） | 41.8 秒（events 9.7、relations 3.3、区間 27.3、配列化 1.0）。Tk を動かさずに読むと 23.4 秒 |
| 線分の生成（LineCollection の用意） | 0.13 秒 |
| 全体描画（全 170万本） | 8.5 秒 |
| SE2 への拡大（切り出し＋描画） | 1.25 秒（描画する線分 8,905 本） |
| ID の選択（強調＋詳細） | 0.46 秒 |
| 元の記録から図へ戻る | 0.52 秒 |
| メモリ | 起動時 113MB → 読み込み・描画後 1,250MB、ピーク（working set）1,341MB |
| 画面の条件 | 1920×1080、Tk scaling 1.67（Windows の表示倍率による）、ウィンドウ 1600×960、matplotlib 3.9.2（TkAgg）、Tk 8.6.14、Python 3.12.3 |

目標値は置いていない。計測は `python -m wom.lovem.viewer <run> --bench <json> --shots <dir>` で再現できる（`docs/development/lovem/stageB_bench.json` に同じ値）。

## 14. スクリーンショット（`docs/development/lovem/stageB_shots/`）

Win32 の PrintWindow で、viewer のウィンドウ自身を描き出したもの（他のウィンドウは写らない）。

| ファイル | 内容 |
|---|---|
| `01_overall.png` | 全体図。「総 ID 63,240｜描画済み ID 63,240｜未描画 0｜フィルタ 0｜線分 1,703,049 / 1,703,049｜全件描画 完了」 |
| `02_se2_zoom.png` | SE2 の拡大（Factory_Import_CN、2026-W34〜W44）。W40・W41 の灰色背景、右に対象週の ID 一覧 |
| `03_id_selected.png` | SE2 の拡大の上で ID（`EVmaker_Import:BKK:2026-W46:00001`）を選んだところ。全ノードの履歴と元の記録 |
| `05_evidence_back.png` | 元の記録（Components_CN の実出荷）から、図の位置へ戻ったところ |
| `04_id_selected_overall.png` | 全体図で同じ ID を選んだところ（Sales → DC → SP → Factory → Components が黄色） |

## 15. 大杉さんが起動する手順

```powershell
cd C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial
# run フォルダが無ければ作る（約 2.5 分。Q12 と比較 run を含む）
python -m tools.lovem_observe --model-dir data/sample/ev-thailand-2026 --out output/lovem/ev-thailand-2026/run_A --q12 --se2-compare-sha 4ed2f14
# viewer（読み込みに約 40 秒。進捗バーが出る）
python -m wom.lovem.viewer output/lovem/ev-thailand-2026/run_A
```

確認していただきたい操作：

1. 上部の件数表示（全件描画 完了）
2. 「SE2 へ移動」
3. 図の線のクリック（候補の一覧・ダブルクリックでの選択）
4. 詳細欄の元の記録をクリック →「この記録の図の位置へ戻る」
5. ツールバーでの拡大・移動
6. 区分のチェックを外したときの件数

## 16. Astra君への引き渡し（§6）

`output/lovem/handoff_ev-thailand-2026/` と同じ中身の ZIP：

| 中身 | 内容 |
|---|---|
| `run/` | run フォルダ一式（A1 の全ファイル、`q12.json`＝Q12 の証拠、`se2_case.json`、`verify.json`、PPC 出力） |
| `DATA_DICTIONARY.md` | データ辞書 |
| `REPRODUCE.md` | 再実行の手順（コマンド・SHA・条件） |
| `SHA256SUMS.txt` | 全ファイルの SHA-256 |

run フォルダは、段階 B のコードが未 commit の状態（HEAD `17915af` ＋ dirty）で作り直したもの。

- `manifest.json` の `code_sha`・`dirty_diff_hash` はその状態を記録している。
- 段階 A の出力（区間・digests・events・relations・anchors・SE2）は、段階 A 報告時と同じ件数・同じ検査結果。
- 段階 B の commit の後に作り直すと、manifest の `code_sha`・`dirty` 系の値だけが変わる見込み（コード上、他の出力には影響しない）。

## 17. 設計書と変えた点・残った未確認

1. **期間外の欄**：左右の余白に件数を出し、クリックで ID の一覧を出す。期間外の lot を線としては描いていない（位置が無いため）。
2. **「未確認」の表し方**：記録の無い入庫は、灰色の点線と「未確認」の文言で示した。線を途中で切る記号（破断マーク）は作っていない。関係の線そのものが無いので、切る対象が無い。
3. **採取段階の切り替え**：`--snapshot` で final 以外の段階も表示できる（例 `--snapshot post_copy`）。
   - 実出荷・到着・関係は Forward の記録なので、final 以外の段階では描かない。上部にもその旨を出す。
   - 最初の実装では Forward 前の図にも重ねて描いていたので、報告前に直した。
   - 2つの段階を同じ図で比べる機能は作っていない。
4. **手での操作**：クリック・ダブルクリック・ツールバーの操作は、関数を呼ぶテストとスクリプト化した操作では確認したが、人がマウスで操作しての確認はしていない。
5. **HiDPI**：Windows の表示倍率が 100% でないと、matplotlib が図の大きさを倍率の分だけ大きく取り、下端が切れる。viewer 側で、キャンバスの実寸に図を合わせ直している。
6. **読み込み時間**：viewer 内では、Tk のイベント処理と GIL を分け合うため 42 秒かかる（単独なら 23 秒）。全件を保存どおりに読む方針のまま、間引きはしていない。
7. **SE2 の対象週の ID 一覧**：予定 S と実出荷に異なる Lot_ID が並んでいることは画面から読み取れる。しかし、それが早出し・遅配などのどれに当たるかは判定していない（段階 C）。
