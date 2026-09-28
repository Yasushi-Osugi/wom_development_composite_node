# Request Letter：LOVEM on WOM 段階 A（観測）・B（描画）— ev-thailand-2026

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`（remote：`composite_node`）
- 基準：`5344816`（本依頼書を commit した後は、その SHA を報告書に記録する）
- 設計の正本：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`（以下「設計書」）
  - 本書は、設計書の段階 A・B を Code君の作業として切り出したもの。設計書と本書が食い違う場合は、設計書を正とし、食い違いを報告する。

---

## 1. 目的

ev-thailand-2026 の**全 Lot_ID が、全ノード・全週で、どの状態にあったか**を採取・保存し（段階 A）、Windows の画面に全件描く（段階 B）。

これは WOM の計画ロジックを直す依頼ではありません。今ある計画結果を、**変えずに**観測し、見えるようにする依頼です。

最初に解きたい問いは、Explicit Closure 実装報告の SE2 です。
ev-thailand-2026 の Factory_Import_CN（EVmaker_Import、push）で、2026-W38・W39 に予定 S 150・150 に対して実出荷が 132・0 となり、168 lot が不足しました。この 168 lot が、ID 単位で早出し・当週・後週・未達のどれなのかを、段階 C で Astra君が独立に照合します。本依頼は、その照合に必要なデータと画面を用意するものです。

## 2. 分担と独立性（設計書 §9・§15）

| 担当 | 作業 |
|---|---|
| Code君 | 段階 A：観測 adapter、区間 encoder／decoder、保存。段階 B：Windows viewer |
| Astra君 | 段階 C：独立 checker（Q01〜Q09・Q12）と正解 fixture、SE2 の週別・ID 別照合 |
| 大杉さん | 業務判断、Windows での最終確認、commit |
| Claude君 | 依頼書と設計の整合 |

**独立性のために守ってほしいこと**

- SE2 の 168 lot を ID 単位で分類する処理（早出し・遅配などの判定）は、Code君の側では**作らない**。分類は Astra君の checker が行う。viewer は、保存されたデータをそのまま見せるだけにする。
- Astra君の checker は、Code君の encoder や分類関数を呼ばず、保存データと原 PSI から独立に照合する。そのため、保存形式とデータ辞書を正確に残すことが最重要です。

## 3. 守ること

1. **計画結果を変えない。** 観測 ON／OFF で、PSI・実出荷・既存診断・PPC が完全に一致すること（Q12）。観測処理の中で Lot のリストを sort・remove・再代入しない。コピーを取ってから読む。
2. **core を変える場合は最小限にする。** 保護対象（`plan_node.py`・`forward_planner.py`・`backward_planner.py`・`push_pull.py`・`plan_copy.py`・`sc_tree.py`）への変更は、既存の結果・hook・record だけでは採取できない情報に限る。変更する場合は、既定 OFF・読み取り専用の記録だけとし、報告書にその理由と差分を明記する。
3. **推測で線を結ばない。** 記録の無い対応（どの出荷がどの要求を満たしたか、等）は作らない。取得できないものは `unknown` として保存し、画面では破断・未確認として見せる。
4. **0・空欄・None を区別する。** 取得できない値を 0 で埋めない。
5. **画面は Windows の Tkinter／matplotlib（FigureCanvasTkAgg）だけで作る。** Web サーバー、ブラウザ画面、Web 系の描画ライブラリは使わない。線は LineCollection でまとめて描き、1 Lot ごとに Line2D や widget を作らない（設計書 §5.5）。
6. **全 ID を描く。** 性能の都合で ID を間引かない。描画済み・未描画の件数を画面に出す（設計書 §7）。
7. core・サンプル CSV・golden を、観測のために書き換えない。commit・push はしない。
8. 副作用や、設計書どおりにできない事実が見つかっても、止めずに最後まで実装し、報告書に書く（これまでと同じ）。

## 4. 段階 A：観測

### A0　基準の記録と採取可能項目の調査（最初に行う）

実装に入る前に、次を報告書に表で残してください。

- 基準 SHA、未 commit の差分、依存パッケージの版、現在のテスト結果
- ev-thailand-2026 の実行条件：plugin セット（golden の config と同じ3つ）、計画期間、製品（EVmaker_Import・EVmaker_Local）、ノード一覧
- **既存の記録で何が採れるかの一覧**：`hook_bus.py`、`event_timeline.py`、`planning_debugger.py`、`ForwardPlanResult` の各 record、`_actual_s`、`_push_shortfall`、`_propagate_to_parent` の到着、休業の診断（`closure_*`・`mode4_closure_shifted`）など。
  - 設計書 §8.3 の7段階（アンカー、Backward 前後、post-hook 後、copy 後、Mode 4 setup 後、Forward 中のイベント、Forward 完了後）ごとに、「既存で採れる／採るには観測用の記録が要る／採れない」を分ける。
  - 段階 7（PPC）は段階 D なので対象外。

### A1　保存するファイル（設計書 §8.2 のうち段階 A〜C の分）

run ごとにフォルダを分け、次を保存してください。

| ファイル | 内容 | 補足 |
|---|---|---|
| `manifest.json` | schema_version、run_id、code_sha、dirty_diff_hash、model_hashes、environment、plugins、observer_version、coverage | coverage に欠測・期間端・未採取の段階を書く |
| `nodes.csv` | product_id、node_id、node_name、parent_id、tree_side、display_order、node_type、plan_mode | display_order は §5 の縦軸の順 |
| `weeks.csv` | week_index、engine_week_label、iso_week_start、period_role | warmup・報告期間を区別。W53・年跨ぎを検査 |
| `demand_anchors.jsonl` | Backward が書き換える前の元需要 | 段階 1 で採取 |
| `psi_intervals.jsonl` | 設計書 §8.5 の区間形式 | I・CO・Demand I は区間に圧縮、P・予定 S は単週区間 |
| `events.jsonl` | 入庫・実出荷などの瞬時の記録 | 区間に丸めない。順序が採れなければ sequence は unknown |
| `relations.jsonl` | 記録から裏付けのある対応だけ | 例：子の出荷と親の到着。推測した引当は入れない |
| `capacity.csv` | raw_hard、raw_soft、effective_limit（`processing_limit`）、planned_capacity、is_open | 休業週を区別 |
| `state_digests.jsonl` | 圧縮前の原 PSI から採った、週・ノード・区分ごとの件数・数量・多重集合ハッシュ | Astra君の checker が区間の復元を検証する基準 |
| `source_evidence.jsonl` | 判定に必要な原イベント（実出荷の ID 列、到着、shortfall など） | 取得できないものは作らない |
| `se2_case.json` | SE2 の定義：モデル、製品、ノード、対象週、比較する run（前後）、プラグイン、168 の集計式 | 分類はしない。Code君が前回測った定義を固定するだけ |

`decisions.jsonl`・`financial_*` は段階 D・E なので作らない。ev-thailand に Stockyard が無ければ、Kitting の記録は「対象なし」と manifest に書く。

### A2　区間 encoder／decoder

- 設計書 §8.5 の連結条件（同一 run・snapshot・phase・product・node・layer・bucket・lot_id・役割・単位・quantity・multiplicity・証拠区分で、週が隙間なく続く場合だけ）を守る。
- **ユニットテストで往復を確かめる**：小さな合成 PSI（早出し、当週、遅れ、未達、同数量で別 ID、同じ ID の多重出現、欠測週、年跨ぎを含む）を encode → decode して、多重集合が完全一致すること。
- 実モデルでは、decode した全週の件数・数量・ハッシュが `state_digests` と一致すること。
- 区間化はノード単位で逐次行い、全週を一度に展開してから圧縮しない（設計書 §8.6）。

### A3　データ辞書

`docs/development/lovem/DATA_DICTIONARY.md` に、全ファイルの列の意味、単位、None と 0 の区別、多重集合ハッシュの正規化規則（文字コード・数値表現・並び順）、identity_basis、証拠区分（observed／derived／reported／unknown）を書く。**Astra君はこの辞書だけを頼りに checker を作ります。** 設計書 §8.2 と違う列にした場合は、変更点と理由を辞書の冒頭に書く。

### A4　段階 A の受入条件

1. 観測 ON／OFF で ev-thailand-2026 の PSI・実出荷・診断・PPC が完全一致（Q12）。
2. 全週の区間の復元が `state_digests` と一致。
3. 合成 PSI の往復テストが緑。
4. 全テスト（既存 544 件＋新規）が緑。golden は変わらない。
5. `se2_case.json` の 168 が、同じ条件の再実行で再現する（`予定 S − 実出荷` の週別の正の不足の和など、どの式で 168 になるかを明記）。再現しなければ、差と原因を報告する。

## 5. 段階 B：描画（Windows viewer）

### B1　画面の構成（設計書 §5）

- **縦軸**：最上部に Business Owner レーン（段階 A〜C では空欄とし、「段階 E で接続」と表示）。その下に Outbound Tree を Post-order、接続部、Inbound Tree を Pre-order で並べる。製品ごとにノードのまとまりを分ける。
- **横軸**：週（`YYYY-Www`）。warmup・期間外を区別し、期間外の Lot は端の欄に件数と ID を残す。
- **ノード内のレーン**：Demand／Supply・物（P・I・実出荷）／Supply・要求（予定 S・CO）。数量→金額のレーンは段階 D なので作らない。
- **記号**（設計書 §6.1）：Demand は破線、Supply は実線、I と CO は別レーンの水平線、休業週は灰色の背景、記録の無い対応は破断と「未確認」表示。色だけで意味を伝えず、線種・凡例を併用する。
- **誤読を防ぐ契約**（設計書 §6.2）：P→I→CO→S を1本の線で描かない。予定 S を実出荷の線として描かない。

### B2　操作

- 全体表示から、週・ノードの範囲へ拡大・スクロールできる。
- Lot_ID を選ぶと、全ノードでその ID の線が強調され、詳細欄に、全ノードでの履歴、予定と実出荷、元の記録（`source_evidence` の該当行）が出る。
- 重なった線を選んだときは、候補を一覧で出す（先頭の1件だけを黙って選ばない）。
- 画面上部に、総 ID 数・描画済み数・未描画数・フィルタで除外した数を表示する。
- 読み込みと線分の生成は分割して進め、進捗表示と中止ができる。Tk の更新は UI スレッドだけで行う。
- viewer は保存データを読むだけで、再計画や入力の変更をしない。

### B3　SE2 への導線

- `se2_case.json` の対象（Factory_Import_CN、2026-W38・W39）へ一発で移動できる操作を用意する。
- そこで、予定 S・実出荷・I・CO と、それぞれの ID を画面から確認できること。分類（早出し・遅配など）は表示しない。段階 C の checker の結果を後で重ねられるよう、`checks.csv` を読み込む口だけ用意しておく。

### B4　段階 B の受入条件

1. ev-thailand-2026 の全 ID を描画し、描画件数が保存データの件数と一致する。
2. ID を選ぶと、全ノードで強調され、元の記録へ移動でき、元の記録から図の位置へ戻れる。
3. 休業週（2026-W40・W41 ほか）が灰色で表示される。
4. 性能（設計書 §13.5）：区間数・イベント数・ユニーク ID 数・展開出現件数・lot-週、保存容量、読み込み・線分生成・全体描画・拡大・選択の時間とピークメモリを測って記録する。目標値は置かない。
5. Windows での画面確認用に、スクリーンショット（全体、SE2 の拡大、ID 選択時）と、大杉さんが `python` で起動する手順を報告書に書く。

## 6. Astra君への引き渡し

段階 B が終わったら、次を1つのフォルダと ZIP にまとめてください。大杉さんが Astra君へ渡します。

- ev-thailand-2026 の run フォルダ一式（A1 の全ファイル）
- 同じ run を ON／OFF で比べた結果（Q12 の証拠）
- `DATA_DICTIONARY.md`
- 再実行の手順（どのコマンドで、どの SHA・条件なら同じ run フォルダが作れるか）
- 各ファイルの SHA-256 の一覧

## 7. 成果物

1. 観測 adapter・区間 encoder／decoder・viewer のコード。置き場所（パッケージ名）は A0 の調査後に決め、報告書に理由を書く。WOM 本体の GUI（`wom/gui/app.py`）には組み込まない（設計書 §5.4）。
2. テスト（合成 PSI の往復、観測 ON／OFF の一致、描画件数の一致）
3. `docs/development/lovem/DATA_DICTIONARY.md`
4. 報告書 `docs/development/WOM_LOVEM_StageAB_EVThailand_Report.md`
   - A0 の採取可能項目の表、A4・B4 の受入結果、性能の数値、core を変えた場合はその理由と差分、設計書と変えた点、残った未確認
5. §6 の引き渡し一式

## 8. 対象外

- 段階 C の照合・分類（Astra君）
- 段階 D（数量→金額、PPC）、段階 E（経営判断の往復）
- ev-thailand-2026 以外のモデル（smartx などの負荷試験も含む）
- 計画ロジックの修正（SE2 の原因が分かっても、ここでは直さない）

## 9. 手続き

- 段階 A が終わった時点で、一度中間報告をしてください（A0 の表と A4 の結果）。大杉さんが commit してから段階 B に進みます。
- commit・push は大杉さんが行います。golden は変えないでください。
