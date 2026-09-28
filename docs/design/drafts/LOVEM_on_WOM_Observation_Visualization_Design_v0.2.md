# LOVEM on WOM v0.2 観測・可視化設計書

- 文書ID：WOM-LOVEM-DESIGN-001
- 版：v0.2
- 作成日：2026-09-28
- オーナー：大杉（WOM Project Owner）
- 作成：GPT-6 Astra
- 改訂日：2026-09-28
- 改訂根拠：大杉さんが提示したClaude君の3提案（Windowsローカル描画・区間保存・EV Thailand先行）。v0.1を保存した上での改訂版。
- 状態：基本設計ドラフト。会話で合意した目的・業務原則と、今回提示する実装可能な設計案を区別する。
- 想定配置：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`
- 対象：`Yasushi-Osugi/wom_development_composite_node` / `wom-v1r5m1_cap_trial`。
- PPC入口の静的確認基準：`1b1f426792dff4fa8ddee1cbdfc78dc7154b7728`（2026-09-28取得時の同ブランチ先頭）。以降の実行は実際のSHAと差分を別途manifestへ記録する。
- 追補：2026-09-28、`requests/Feedback_LOVEM_v0.2_PPCEntry_to_Astra.md`を受けて段階Dの前提を追加。版名はv0.2を維持。A〜Cの対象・完了条件は変更しない。

## 0. v0.2の改訂判断

3提案を採用する。本版は設計の更新であり、描画性能や168 lotの原因を実測した報告ではない。

| 提案 | 採用内容 | 明確にする条件 |
|---|---|---|
| Windows Stand Alone、matplotlib/Tk | Tkinter＋matplotlibのTk埋込ビュー。線はLineCollectionを基本単位とする。Web画面・Webサーバーは使わない | 全件描画の性能は実測する。Linuxでは観測・照合・描画データのHeadless検証、最終GUIはWindows |
| 週次列挙から区間へ | PSI状態の保存正本をpsi_intervals.jsonlとする | 連続状態の圧縮とイベント保存を分け、週別のID・数量・多重度を復元できること |
| 最初はEV Thailand | 段階A＝観測、B＝描画、C＝独立照合をev-thailandで通す | SE2の168 lotを、元の集計条件から再現し、要求・出荷のID単位で説明する。遅配を結論として固定しない |

v0.1の全node価値・利益、Business Ownerへの帰着、Q01〜Q12は維持する。soysauceとCookieを含む金額検証は段階D、経営判断の比較往復は段階Eとし、初回A〜Cの必須範囲から外す。段階名は本版§12を正本とし、v0.1の段階名とは読み替える。

## 1. 目的

WOMの目的は、グローバル・サプライチェーンを対象に、市場消費の加速・減速を捉え、需要と供給を週次で同期させる意思決定を支援することである。

LOVEM on WOMは、Business Ownerの意思決定を、数量と金額の両面から検証して本人へ返す観測・可視化機能とする。

**経営の意思入れ → 市場への需要配分 → 能力を踏まえた週次計画 → Lotの供給・出荷 → 各nodeの売上・原価・利益 → 次の経営判断**

この循環を、同じシナリオ・実行・node・週・Lot_IDの対応で辿れるようにする。全Lotの正常な流れと想定外の流れを人間の目で確認できることを主目的とする。

## 2. 文書の権限と根拠

| 区分 | 本書での扱い |
|---|---|
| 合意済み業務原則 | 全nodeを対象とする価値・利益算定、全IDの可視化、node×週のLOVEM配置、Demand/Supplyの区別、Business Ownerへの帰着 |
| 設計案 | データ項目、表示記号、照合規則、構成、実装順序、受入条件。今回新たに定義する |
| 過去の観測・報告 | Trial-02およびExplicit Closure実装報告。各基準・状態を保持し、新ブランチの事実と混ぜない |
| 要確認 | 現行イベント記録の網羅性、PPCのnode別計上基準、API接続先、実行時SHA・差分、描画性能 |

本書は観測・可視化の設計であり、PlanningやPPCの業務挙動変更、golden更新、commit/pushを実施した記録ではない。実装時には対象リポジトリのAGENTS.mdと既存承認範囲に従う。

根拠資料：

- 大杉さんとの2026-09-28の会話：全nodeのS×Lot単価、全Lot可視化、Business Ownerへの帰着。
- 大杉さんのnote記事「PSI計画連携の仕組みをサプライチェーン全体に拡張していくための考慮点」（2022-02-28）：https://note.com/osuosu1123/n/n52d3b17848b3 。縦軸の事業単位・横軸の時間、物流・商流・計画情報という発想を参照。本書のDemand二段階やデータスキーマは記事の記述ではなく今回の設計案。
- `WOM_Capacity_Trial02_Report.md`：固定SHA `4ed2f145dfb30b95058c0d274665eca64e4fc4c4` の測定。
- `WOM_ExplicitClosure_v1r5m0_Report.md`：2026-09-27実装報告。報告時点で未commit・未push・golden未更新。掲載された結果は本書で再実行していない。

## 3. 範囲と最初の完成形

### 3.1 全体の到達範囲（段階A〜E）

1. 実行条件を固定した結果から、全node・全期間・全Lotの観測データを採取する。
2. Outbound Post-order、Inbound Pre-orderのnode配置と3〜5年の週次横軸に、Demand/Supplyの履歴を描く。
3. 全ID表示、拡大、スクロール、個別選択、原記録への参照を提供する。
4. 予定S、実出荷、I、CO、入庫、組立・移動の対応を照合する。
5. 全nodeの数量→金額の接続を調べ、Profit Zoneへ集計した根拠を示す。
6. Business Ownerの配分判断から各Lot・計上結果へ辿り、比較元との変化を説明する。

### 3.2 今回まとめて変更しないもの

観測と原因判定が済む前に、FIFO、CO、能力封印、Mode 4、PPC認識基準を同時変更しない。新しいLot ID体系、日次現場制御、正式な財務会計・連結会計エンジンもv0.2の実装範囲に含めない。

node別売上・利益を表示する要件は含むが、会計上の内部取引消去規則まで実装済みとは扱わない。

### 3.3 完了条件

**初回Trial（A〜C）**：ev-thailandの全対象製品・全node・全期間・全IDを観測・表示し、SE2の168 lotを生んだ週次数量差を再現した上で、その関係ID、元要求週、実出荷週、未達・未確認を全数で照合する。必要な対応が未取得なら「実装済み・原因未解決」とし、Trial完了とはしない。§13.3の終了条件を用いる。

**全体（A〜E）の完成条件**：

> 一つの配分判断について、生成・配分された全需要Lotが、どこで供給・出荷され、どこに在庫・未達として残り、その数量が各nodeの金額計算へどう反映されたかを、図と照合表で説明できること。

記録不足がある場合は、対象範囲と未確認件数を明示する。「未確認」を残した部分実装と、上記完成条件の達成を区別する。

## 4. 経営判断・Demand・Supplyの対応

| 段階 | 入力と判断 | 保存する出力 |
|---|---|---|
| Business Owner | 目的、優先市場、配分方針、能力変更などの意思入れ | decision_id、判断日時、適用期間、採用案、比較元 |
| DL-1 Demand Allocation | 経営目的と価格・原価等を用いた市場配分の選択 | 配分案、モデル前提、目的値、生成需要との対応 |
| DL-2 制約を反映した計画 | 能力・休業・LT等に基づく需要配置 | 制約適用前後の位置、移動理由、期間外・未達 |
| SL-1 Supply Simulation | 計画と物の利用可能性に基づく供給・出荷 | 入出庫、在庫、注文残、Kitting、実出荷 |
| 金額評価 | 各nodeの取引数量と価格・原価規則 | node別売上・原価・利益、Profit Zone、計上根拠 |
| Business Ownerへの帰着 | 採用案と比較元の結果 | 狙った成果、供給成立に対応する成果、差異、未確認 |

DL-2は実行可能な配置を求めるが、能力・期間が足りない場合に成立を保証したことにはしない。残った未達・期間外を可視化する。

「実出荷」はシミュレーション上で実現した出荷を意味する。現場システムから取得した実績との混同を防ぎ、画面に「Supply Simulation実出荷」と表示する。

## 5. 図の座標と構成

### 5.1 縦軸

- 最上部：Business Ownerの経営意思決定レーン。
- 続いてOutbound TreeをPost-orderで配置する。
- 接続部の対応を表示し、その下にInbound TreeをPre-orderで配置する。
- 子の表示順は入力定義または明示したnode順で固定し、比較するrun間で安定させる。
- 複数製品は製品ごとにnodeブロックを持つ。同名nodeだけを根拠に統合しない。
- node表示には正式ID、名前、製品、役割、Profit Zoneを併記する。

Post-orderは各枝の市場側を上へ置くが、すべての最終市場が他の全nodeより上になるとは限らない。v0.2では枝ごとのまとまりを保ち、背景・括りで経路を示す。

Outbound供給起点とInbound rootを接続する際は、業務上同じ拠点でも論理nodeの区別を保持する。接続線とphysical_site_id（根拠がある場合）で対応を示し、同じ在庫を二重集計しない。

### 5.2 横軸

- 表示はISO週ラベル `YYYY-Www`、内部参照はrunのweek_indexと週の開始日を併記する。
- 週番号の文字列だけから52週固定で時間差を算定しない。W53・年跨ぎを検査する。
- 元エンジンの週対応に不整合があれば診断し、観測側で黙って並び替えて修正しない。
- warmup、報告期間、期間前、期間後を区別する。期間外のLotを図から消さず、端の専用欄に件数とIDを残す。
- 全期間表示から週・node・IDへ拡大する。計画年数によって横軸の意味を変えない。

### 5.3 node内のレーン

| レーン | 内容 |
|---|---|
| Demand | S要求、計画上のI、P配置。必要に応じDemand COも独立表示 |
| Supply・物 | P入庫／生産完了、I滞留、実出荷 |
| Supply・要求 | 予定S、持越しCO、充足の対応 |
| 数量→金額 | 取引数量、適用単価・原価、売上・利益、PPCとの差 |

Demand/Supplyは隣接配置し、同じnode・週の差が見えるようにする。金額欄は折畳み可能だが、全nodeを対象としてデータを保持する。

### 5.4 画面領域

- 上部：対象run、比較run、期間、モデル、観測の完全性、表示件数。
- 本体：Business Ownerレーンとnode×週の全Lot図。
- 選択詳細：IDの全node履歴、予定と実出荷、部材結合、金額計上、出典。
- 照合一覧：違反・未確認・正常、件数、該当ID、対応する図の位置。

独立したWindowsローカル閲覧用ビューを先に作る。WOM本体GUIへの組込みは、観測データと照合の成立後に判断する。

### 5.5 実行・描画技術（v0.2採用）

- Windows Stand Aloneを対象とし、Tkinter/ttkをウィンドウ・操作部、matplotlib＋FigureCanvasTkAggを図の埋込みに使う。外部Webサーバー、ブラウザ画面、Web描画ライブラリは採用しない。
- PSIの水平線とnode間の接続線は、レーン・線種・状態ごとのLineCollectionでまとめて描く。1 Lotに1個のLine2DやTk widgetを作る構成は採らない。イベント点もまとめた描画を基本とする。
- 線分番号からinterval_id/event_id/relation_idへ戻る索引を保持する。選択時は該当IDの線を独立した強調用Collectionに描き、選択前の全件データを維持する。
- node行×週範囲の索引で表示範囲を切り出す。重なった線の選択候補は一覧に出し、先頭1件だけを無説明で選ばない。常時全IDの文字ラベルは付けず、選択・拡大時に表示する。
- 読込・線分生成は分割処理できる構成とし、進捗と中止を提供する。Tkと画面の更新はUIスレッドで行い、バックグラウンド処理から直接GUIを操作しない。
- 全体図では全対象IDを描画対象とする。全体図／範囲拡大／選択IDのモードと、描画済み・未描画件数を明示する。性能の都合で無断でIDを間引かない。
- 線分配列の生成と照合はGUIから分離する。適合確認済みLinuxでHeadless・pytestを実施できるが、Tk操作、拡大・選択、文字、終了動作の最終確認はWindowsで行う。
- matplotlib/Tk/Pythonの実際の版、バックエンド、画面解像度・倍率を検証報告に残す。LineCollectionの採用は性能保証ではなく、§13.5で測定する設計選択である。

## 6. 線と状態の意味

### 6.1 描画記号案

| 記号 | 意味 |
|---|---|
| Demandの破線 | 要求と計画配置の対応。現物移動を意味しない |
| Supplyの実線 | 根拠のある入出庫・node間移動 |
| Iの水平線 | 同じ物が当該nodeで待機する期間 |
| COの別レーン水平線 | 同じ出荷要求が未充足のまま持ち越される期間 |
| 充足の接続線 | 物の出荷イベントと、充足した要求の対応 |
| Kittingの結合点 | 必要部材の払出と組立完成の対応 |
| 灰色背景 | 休業週。物の有無とは別の状態 |
| 中断記号＋未確認表示 | 記録欠損または未解決の対応。推測で接続しない |

色だけで意味を伝えず、線種、ラベル、凡例を併用する。

### 6.2 誤読を防ぐ契約

- P→I→CO→Sという「物が必ず順番に通る経路」は描かない。COは要求であり物ではない。
- 同じ需要に対応する物がIにあり、要求がCOに残る状況は、そのまま二つの状態として表示し、原因を検査する。
- Demand Iは計画上の配置であり現物在庫と同一視しない。
- 予定Sを実出荷の線として描かない。
- 同週のP・Sに同じIDがあるだけでは処理順序を断定しない。イベント記録があれば順序を表示し、なければ週単位の対応に留める。
- 実出荷量と予定量の一致は、IDの一致を保証しない。
- 全node横断で同じIDが現れること自体は正常。重複の検査はnode・役割・イベント・数量の境界で行う。

## 7. 全IDを扱う方針

全IDを観測・保存・表示対象とし、無作為抽出や上位N件への置換を標準動作にしない。

全体縮尺では全IDの線分を描画対象にするが、ピクセルの重なりは起こる。画面には総ID数・表示対象数・フィルタ除外数・未読込数を示す。密度表現を補助表示しても、個々のIDの根拠を消さない。

拡大時はnode内の補助行を使って軌跡を分離する。補助行の位置は計画量・金額を意味しない。選択IDは全nodeで一貫して強調する。

性能上の必要から画面外を遅延描画する場合も、全件保存と表示範囲の完全性を維持する。全体図を一部だけ描いた状態を「全件表示完了」と表示しない。生データと全件照合表は画面から独立して出力する。

## 8. 観測データの定義

### 8.1 基本原則

既存Lot_IDを変更しない。観測用IDは原記録を識別するためのもので、新たな生産・出荷ID体系ではない。

同じ需要IDを部材ごとに共有する既存方式を想定し、`lot_id`だけを全世界で一意な物理個体キーとして使用しない。集合に変換して重複を消さず、数量・多重度を保持する。

### 8.2 保存ファイル案

表中のファイル名・フィールドは新規設計案。既存API名ではない。

| ファイル | 主なフィールド | 用途 |
|---|---|---|
| manifest.json | schema_version, run_id, code_sha, dirty_diff_hash, model_hashes, environment, plugins, observer_version, coverage | 再現条件と観測範囲 |
| decisions.jsonl | decision_id, decided_at, effective_from/to, objective, allocation_id, parameters, baseline_run_id, evidence_ref | 経営の意思入れ |
| nodes.csv | product_id, node_id, node_name, parent_id, tree_side, physical_site_id, display_order, profit_zone | node順序と集計境界 |
| weeks.csv | week_index, engine_week_label, iso_week_start, period_role | 時間軸 |
| demand_anchors.jsonl | demand_key, lot_id, product_id, market_node_id, required_week, quantity, unit, allocation_id | 変更前の要求正本 |
| psi_intervals.jsonl | interval_id, run_id, snapshot_id, phase, product_id, node_id, layer, bucket, lot_id, role_id, start_week_index, end_week_index, quantity, unit, multiplicity, evidence_level, evidence_ref | 連続するPSI状態。両端を含む週区間。quantityは1出現あたり、multiplicityはその週の出現数 |
| events.jsonl | event_id, event_type, product_id, node_id, week_index, sequence, lot_id, role_id, quantity, unit, origin, evidence_ref | 入庫・実出荷等の瞬時観測。区間に丸めない。sequenceが取得不能ならunknown |
| relations.jsonl | relation_id, relation_type, from_ref, to_ref, demand_key, quantity, evidence_level, evidence_ref | 要求・物・計画移動・組立の対応。区間参照はinterval_id＋week_index、イベント参照はevent_id |
| capacity.csv | node_id, week_index, raw_hard, raw_soft, effective_limit, planned_capacity, is_open, source_ref | 物理能力・操業状態・実効値 |
| financial_records.jsonl | financial_record_id, node_id, recognition_week, basis, quantity, unit, price/cost_rule_refs, currency, fx, revenue, cost, profit, profit_zone | 数量から金額への対応 |
| financial_links.jsonl | financial_record_id, source_ref, linked_quantity, mapping_method, evidence_ref | 金額とLotの接続。source_refはイベント、区間内の特定週、または定義された集約を指す |
| checks.csv | check_id, status, rule, scope, counts, quantities, evidence_refs, checker_version | 全数照合結果 |
| state_digests.jsonl | snapshot_id, phase, product_id, node_id, week_index, layer, bucket, entry_count, total_quantity, multiset_sha256, ordered_sha256 | 圧縮前に元PSIから採取した週別件数・数量・ハッシュ |
| source_evidence.jsonl | evidence_id, source_kind, source_locator, source_hash, payload | 引当・移動・観測境界の取得可能な原イベント。後から解釈を検証する根拠 |
| se2_weekly_reconciliation.csv | run_id, product_id, node_id, week_index, planned_s, actual_s, signed_gap, shortfall, excess, evidence_refs | 168 lotの元集計式と週別数量差 |
| se2_id_reconciliation.jsonl | demand_key, lot_id, role_id, required_week, shipped_week, quantity, classification, match_method, evidence_refs | 168 lotに関係する要求・出荷の全数対応と未確認 |

source_evidenceは既存ログの無差別な複製ではなく、判定に必要な原イベントを保全する。取得できない原記録を生成して補わない。state_digestsのordered_sha256は元リストの順序の監視用であり、区間だけから元リスト順序を復元できるとはしない。

共通してrun_idを保持する。空欄・None・0を区別する。取得不能値を0で補完しない。

証拠区分は `observed`（実行時記録）、`derived`（記録から再計算）、`reported`（他者報告）、`unknown` とする。derivedには計算方法と入力参照を必須にする。

### 8.3 採取する段階

1. DL-1採用案とLot生成直後：元需要を不変のアンカーとして保存。
2. Backward前／後、holiday等のpost-hook後：移動と消失に見える差を区別。
3. Demand→Supplyコピー直後。
4. Mode 4 setup等、供給P再配置の直後。
5. Forward：利用できる既存イベントを採取し、node処理・Kitting・実出荷の境界を記録。
6. Forward完了後のPSI。
7. PPC入力、計算結果、Profit Zone集計。

全段階の状態を単純に一つの図へ重ねず、採取段階を選択・比較する。最終状態と計画変更履歴は異なる表示である。

既存hookとイベント基盤の対応表を最初に作る。上記の名前のhookが現行コードに存在すると仮定しない。元需要はBackwardによる書換え前にコピーして保全する。

### 8.4 要求と物の識別

要求キーの基本はrun内の「製品・市場node・元要求週・Lot_ID・必要数量」。node別要求は、このアンカーへ関係付ける。

観測された物の識別には「製品・node・部材役割・Lot_ID・多重度」を用い、移動関係でnode間を接続する。Kittingでは部材側の複数記録と完成側の記録を結合する。BOM数量を使い、部材3個と完成品1個を単純な3→1の消失として扱わない。

FIFOで出荷したIDと充足した要求IDが異なる場合は、記録された引当関係を表示する。数量が合うだけで引当を発明しない。関係を取得できなければ、その要求の充足判定はunknownとする。

### 8.5 区間の意味と圧縮条件

保存正本を `psi_states.jsonl`（Lot・週ごとの行）から `psi_intervals.jsonl`（連続週区間）へ変更する。旧形式の全期間展開は必須成果物にしない。小さなテストや選択範囲の調査には一時的な週次展開を許す。

区間 `[start_week_index, end_week_index]` は両端を含む。週数は `end-start+1`。YYYY-Www文字列ではなくweeks.csvの連続indexで長さを算定する。

連結できるのは、同一run・snapshot・phase・product・node・layer・bucket・Lot_ID・部材役割・単位・quantity・multiplicity・証拠区分で、観測済みの週が隙間なく連続する状態だけである。quantity/multiplicityの変化、途中の欠測、採取段階、役割または由来の変更で区間を分ける。未知の週を在庫の継続とみなさない。

- **I／CO／Demand I等の状態**：上記条件で圧縮する。Iは在庫状態、COは要求状態の連続であり、COを物の滞留として描かない。
- **PSIのP／予定Sの出現**：初期実装ではstart=endの単週区間とする。各週の別々の入庫・要求を一本の滞留線にしない。
- **実出荷・受入・払出・Kitting等のイベント**：events.jsonlに単発記録として保存する。同じIDが複数週に出る場合もイベントを統合しない。PSI状態とイベントを同じ数量として二重加算しない。
- 同じLot_IDの複数出現はmultiplicityで保持する。部分数量はquantityで保持する。部材役割・原記録が異なれば分離し、元データにない物理個体の同一性を新設しない。
- 同一IDの連続存在は、引当・移動の証拠がなければ「同一物理個体が連続滞留した証明」にはしない。identity_basisをデータ辞書で定義し、同一性不明は詳細表示に残す。
- 区間の端は状態の観測範囲を意味する。IがW10〜W12に存在しただけで、入庫時点やW13の実出荷を推測しない。図の正確な入出庫接続はイベントを用いる。

例（各出現1 lot）：Iに同一キーがW10〜W12の各週1回存在すれば1区間、展開件数3、数量期間和3 lot-週となる。W11だけ2回ならmultiplicity=1,2,1の3区間とする。W11未取得ならW10とW12を結ばない。

`展開出現件数 = Σ((end-start+1) × multiplicity)`

`状態の数量期間和 = Σ((end-start+1) × quantity × multiplicity)`

これらの期間和は出荷数・ユニークID数とは別指標である。

### 8.6 可逆性・参照・独立照合の契約

可逆性の必須範囲は、各snapshot/node/week/layer/bucketの **Lot_ID・役割・単位・数量・多重度の多重集合** とする。元Pythonリスト順序や同週イベント順序まで区間から復元できるとはしない。FIFOの因果を調べる場合は、既存引当イベントまたは観測境界で採取した順序付き証拠を別途保存する。

1. 観測adapterは圧縮前のPSIを読み、週別件数・数量・正規化多重集合ハッシュをstate_digestsへ保存する。正規化・文字コード・数値表現・並び順をデータ辞書で固定し、元リスト自体は並び替えない。
2. 独立checkerは区間から1週またはnode単位に展開し、すべての対象週の件数・数量・ハッシュを照合する。原状態の誤読を圧縮とcheckerが共有しないよう、原PSIを直接読む非圧縮の参照処理も独立に用意する。
3. 小さな正解fixtureでは多重集合そのものを完全比較する。実モデルは全週の直接読取との照合を行い、差が出たキーは元明細と復元明細を残す。再実行を含む場合は同一入力・コードを固定する。
4. relationsから区間を参照する際は、参照週が区間内にあることを検査する。欠測区間、期間端で切れた区間、採取途中をmanifest.coverageに記録し、完成した区間と区別する。
5. 同じキーの重なった二重区間、start>end、未知node/週、負数量、不正multiplicityを検出する。別phaseや別snapshotの区間を一緒に集計しない。

区間化はストリーム／node単位で行い、610万行等の週次JSONを一度全生成してから圧縮する実装は避ける。元PSIに既に必要なメモリと、観測器・viewerが追加するメモリを分けて測る。区間形式は元エンジンのメモリ消費まで削減するものではない。

Claude君の「smartxのBuffer_Chip_TWのIだけで約610万 lot-週」は他者報告値であり、本版では再測定していない。圧縮後件数は継続性・IDの変化によるため、固定の削減率を約束しない。smartxは将来の負荷確認候補であり、初回A〜Cの対象に追加しない。

## 9. 全数照合の規則

判定はPASS／FAIL／UNKNOWN／NOT_APPLICABLE。記録不足をPASSにしない。意図した挙動変更は、変更理由を持つ別列で表し、保存違反を免除するラベルにはしない。

| ID | 規則 | 判定の要点 |
|---|---|---|
| Q01 | 観測範囲の完全性 | 全node・全週・全対象Lot、期間外・初期在庫・匿名供給を説明。§8.6の全週の区間復元一致、参照の有効性も検査 |
| Q02 | 元需要の保存 | 未変更アンカーの数量＝充足数量＋期末未充足＋明示的取消等。業務上定義されていない取消を使わない |
| Q03 | node内の物量保存 | 期首I＋入庫／生産完了＝期末I＋実出荷＋部材消費＋明示的廃棄等。採用する記録境界でPと生産完了を二重計上しない |
| Q04 | node間の移動 | 出荷と次nodeの到着をID・数量・LT・経路で対応付ける。輸送中と期間後到着を別管理 |
| Q05 | 出荷の根拠 | 実出荷に利用可能な物が存在するか。予定Sの複写だけで供給したことにしない |
| Q06 | 要求週と実出荷週 | 同一要求に対する早出し・当週・遅配・未達の数量を分解。部分出荷は分割して保持 |
| Q07 | COの連続性 | CO持越し・新規要求・充足の更新が整合するか。COを現物数量として物量保存式へ足さない |
| Q08 | Kitting | 必要部材の成立、消費、完成数量、重複消費、能力待ちを照合 |
| Q09 | 休業・能力 | 対象操作に対する実効制限と実出荷／Pを比較。pushの入庫を自動的に処理能力違反としない |
| Q10 | 数量→金額 | 計上数量と根拠数量、単位、取引node、認識週を照合 |
| Q11 | 金額→Profit Zone | node計上とゾーンの対象範囲、重複、未割当を照合 |
| Q12 | 観測の非干渉 | 観測ON/OFFでPSI、実出荷、既存診断、PPCが一致するか |

Code君（Claude Code）は観測adapter・区間encoder・viewerを担当し、Astra君はQ01〜Q12のcheckerと正解fixtureを独立に担当する構成を採用する。両者はスキーマと業務規則を共有するが、checkerが実装側の圧縮・引当・分類関数や「判定済み」結果をそのまま呼んで自己照合しない。原データと証拠まで戻って比較する。AIの担当を分けるだけで独立性を保証したことにはしない。

段階A〜CではQ01〜Q09・Q12を適用し、Q10・Q11は金額データ未採取としてNOT_APPLICABLE（段階Dで必須）にする。対象モデルにないKitting等も理由付きNOT_APPLICABLEとし、存在するのに観測できないものはUNKNOWNとする。checkerの独立作成は今後の実装分担であり、本設計改訂中に作成・実行したものではない。

週差だけの警告は「予定数量−実出荷数量」。Q06は要求IDと充足対応による別の判定とする。

受入用の最小例：同週に予定ID=A、実出荷ID=B、件数が双方1の場合、数量差は0だが、Aの充足をPASSにしない。Aが前週に出荷済みなら早出し、後週で対応が確認できれば遅配、そのどちらもなければ未達またはUNKNOWNとする。

## 10. 数量編から金額編への接続

### 10.1 全nodeを対象とする原則

素材、加工、組立、流通、最終市場の各nodeで、出荷数量と適用単価を結び付ける。

`node売上 = Σ(当該nodeの対象出荷数量 × 当該取引のLot単価)`

同一単価ならSのLot数×Lot単価。製品・時点・取引先で価格が異なる場合は明細単位で加算する。PPCがunit単位の場合はcpu_size等の換算を明示し、Lotとunitを混ぜない。

原価はruleのbasisを確認し、per_lot、per_unit、固定費、期間費等を分ける。すべての原価を無条件にSへ掛け直さない。粗利・営業利益等の名称は含む費用範囲を併記する。

### 10.2 表示する三つの金額基準

| basis | 意味 |
|---|---|
| plan | 予定出荷数量と採用した価格・原価規則に基づく計画額 |
| supplied | シミュレーション実出荷数量に対応する額。同一規則で再計算可能な範囲 |
| existing_ppc | 現行PPCが計上した額とその入力数量。確認基準のPSI bridgeはleaf_outのSupply S件数×cpu_sizeを入力とし、実出荷イベントを参照しない。製品・channel・週を名前に持つ集約レコードへ変換し、元Lot_ID明細を引き継がない。runnerのフィルタ・fallbackを含む実際の入力経路も併記する（§10.4） |

suppliedは観測用の照合計算であり、現行PPCを自動的に修正しない。規則・node別価格が取得できない部分は「計算不能」とする。plan/supplied/existing_ppcを加算しない。

価格・原価・為替・移転価格は、source file、行識別、適用週、通貨、単位、ruleの版を保存する。週別集約レコードしかない場合は、その単位での一致を示し、元IDへの配賦方法をderivedとして記録する。

PPCに上流nodeの費用が存在するだけでは、そのnodeの出荷売上が実装されている証拠にならない。node別の取引価格・出荷数量・計上週を個別に確かめる。

### 10.3 Profit Zoneと全体集計

node別売上と利益を可視化した上で、ゾーン所属・重複集計の扱いを定義する。同じ物の中間売上と最終売上を全体売上として無条件に足さない。

v0.2は「node別」「Profit Zone別」「現行PPC全体」の範囲を明示する。内部取引消去や連結範囲が未定なら、node売上の合計を「連結売上」と呼ばない。これは中間nodeの売上を算定しないという意味ではない。

### 10.4 現行PPC入口の静的確認（段階Dの前提追補）

根拠はClaude君のRequest Letterと、Astraによる上記固定SHAのコード読解。今回Headless・PPCの再実行はしていない。静的な入口の確認と、個別モデルの金額差の原因確定を分ける。

| 項目 | 固定SHAで確認した処理 | 段階Dで残す観測 |
|---|---|---|
| 起点node | `psi_to_sales_records()`は`NODE_TYPE_LEAF_OUT`以外を除外（bridge 134–139行） | source_node_id、product、channelへの対応、除外nodeの範囲 |
| 数量基準 | `node.qty_supply(w_idx, S_BUCKET)`。`PlanNode.qty_supply()`は`len(psi4supply[week][bucket])`。`_actual_s`を参照しない（bridge 150–160行、plan_node 264–266行） | 呼出時のSと実出荷を別採取。Sが実出荷と一致するかはnode・runごとに照合 |
| 単位換算 | `qty = lot_count * sc_tree.cpu_size`。leaf販売数量にBOM倍率を直接掛けていない | Lot数、cpu_size、unit数量、単価単位 |
| 行生成 | 実際のループは製品→leaf_out→週で、非ゼロSに対して1行を追加。合成IDは`PSI-{product}-{channel}-{week}`（bridge 161–169行） | 入力行番号とsource_nodeを保存。異なるleafが同一channelへ写像される場合のID衝突を確認 |
| 元ID | PPC出力用の入力行には元のLot_ID一覧がなく、合成IDのみ。元PSIから消去する処理ではない | 集約直前の元ID多重集合と集約行への対応を観測側で保全 |
| 入力選別 | runnerは既知product/channelで絞り込む。互換レコードがなければsample salesへfallback（runner 64–98行） | 呼出経路、採用・除外行数と数量、psi_mode、sample使用の有無 |

「channel×週で1行」は設計意図の要約であり、コードは複数leafを横断したgroupbyをしていない。対応表が一対一かを測定し、合成lot_idだけを観測用の一意キーにしない。

本書で「予定S」と呼ぶのは実出荷とは区別したSupply Sの系列である。このbridgeを読むだけで、全leaf・全runのSが常に未充足を含むとは断定しない。実際の呼出時点でどの値が入っているかを確認する。また、PPC全体のあらゆる入口がこのbridgeだけだとは断定せず、対象GUI/Headlessの呼出経路を記録する。

固定SHAの参照：

- [ppc_psi_bridge.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/1b1f426792dff4fa8ddee1cbdfc78dc7154b7728/wom/ppc/ppc_psi_bridge.py)
- [plan_node.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/1b1f426792dff4fa8ddee1cbdfc78dc7154b7728/wom/model/plan_node.py)
- [ppc_runner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/1b1f426792dff4fa8ddee1cbdfc78dc7154b7728/wom/ppc/ppc_runner.py)

### 10.5 ancestryと中間node金額の接続調査（段階D）

runnerのGENERIC分岐は、leaf_outからDAD祖先列、leaf_inからMOM祖先列を作り、`dad_nodes_chain`、`mom_nodes_chain`、`bom_qty_map`等としてPPC engineへ渡している。一方Cookie等には別のシナリオ分岐がある（runner 118–154、195–243、291–304行）。

**祖先経路を選ぶ処理の存在と、「各中間nodeの金額がleaf数量を配ったもの」という結論は別である。** 現時点では後者の実行時対応を未確認とする。段階Dで以下を調べる。

1. 対象モデルで実際に選ばれるscenario分岐と経路解決結果を採取する。CookieへGENERICの説明をそのまま適用しない。
2. PPC engine以下で、入力qty、BOM倍率、単価伝播、原価、移転価格、node別集計がどのレコードを使うかを追跡する。
3. 各中間nodeについて、計算数量が「自node実出荷」「leaf販売数量からの導出」「その他」「未確認」のどれかを根拠付きで示す。
4. node名が計算結果に出ることだけで、自nodeのSを読んでいると判断しない。集約の認識週と、当該nodeの実出荷週も照合する。
5. この調査で不足するnode別価格・原価規則は未設定として残す。差を埋めるための単価・引当・取引を発明しない。

### 10.6 suppliedとexisting_ppcの差の分類

まず同じrun・製品・node/取引範囲・週・通貨・単位・価格原価規則へ比較条件を揃える。全nodeのsupplied合計と市場起点のexisting_ppc全体を、そのまま差し引いて「供給差」と呼ばない。

| 分類 | 確かめること | 記録上の注意 |
|---|---|---|
| 起点・対象nodeの差 | 全node各自の出荷数量と、leaf起点から導出する数量の相違 | 比較できないnodeは対象範囲差／計算不能として残す |
| 数量・時点の差 | 同じ取引・規則で予定S基準と実出荷基準を比較 | 早出し・遅配による週差と、全期間未達を分ける |
| 集約・ID追跡の差 | 元Lot_IDとPPC集約行の対応がどこまで残るか | ID喪失だけでは金額誤差を証明しない。追跡不能件数・数量を報告 |
| その他・未説明 | 単価/原価、単位、為替、丸め、対象期間、フィルタ、fallback等 | 3分類へ無理に押し込まず残差と根拠を示す |

集約自体は、同一規則で線形に計算するなら金額を変えない場合がある。単価や適用条件の違いを集約で失っている場合には、その有無を実測する。Lotへの単純按分額はderivedであり、元Lotに対する実際の計上記録とは区別する。

各分類は関連し得るため、独立した加算可能な原因額とは仮定しない。金額分解を行う場合は固定条件・置換順序・中間結果を保存し、相互作用と未説明残差を示す。測れない分類に0円を入れない。

### 10.7 段階Dの追加証拠と終了条件

段階Dでのみ、以下を§8.2の観測契約へ追加する。A〜Cの保存・実装・受入条件に新しい必須項目を増やさない。

- `ppc_entry_records.jsonl`：run_id、entry_record_id、入口/呼出経路、入力行番号、source_node、product、channel、週、合成lot_id、S件数、cpu_size、qty/unit、採用/除外、fallback、evidence_ref。
- `ppc_entry_links.jsonl`：entry_record_idから集約直前の元PSI区間内の週・Lot_ID・多重度へ接続。後から合成IDを文字分割しただけの対応をobservedにしない。
- `ppc_node_basis.csv`：node別の数量起点、実行分岐、経路、倍率、価格原価規則、認識週と根拠。
- `ppc_basis_differences.csv`：比較scope、plan/supplied/existing_ppcの数量・金額、差の分類、確認状態、残差、evidence_ref。Q10で入口・数量対応、Q11でnode/Profit Zone集計を照合。

再実行で元ID一覧をbridge直前から採取できれば対応を保全する。過去の集約結果しか残っていない場合、そこから元IDを一意に復元できるとはしない。

Trial-02の9,293 lotとExplicit Closure SE1のCookie供給1,450 lot減・PPC不変は、この入口を原因候補とする。過去結果の基準と今回の実行を区別し、未出荷ID→leaf S→bridge行→採用入力→PPC明細・集計の経路を確認してから原因を確定する。上流の未出荷だけを理由に、末端初期在庫等による供給可能性を調べず全販売を未成立と扱わない。

段階Dの完了証拠は、対象nodeごとの数量起点と計上の対応、比較可能な範囲の金額差、ID追跡の可否、未設定・未説明の一覧である。PPCの修正方針は、この実測結果を大杉さんが確認してから決める。本追補はPPC修正、段階Dの測定開始、golden更新の依頼ではない。

## 11. Capacityに関する観測契約

- 合意方針：CapHardは物理設備能力。初期model building時に設定し、通常のPlanning処理で暗黙に変更しない。
- Ownerが設備変更を指示する場合、変更前後、適用開始週、decision_idを記録する。
- 休業状態、保存されたraw_soft、計画に適用するplanned_capacityを別列にする。
- None＝未設定、0＝有効なゼロ制限を区別する。画面の「—」と「0」を使い分ける。
- partial_capacityがraw_hardを書き換える現行移行措置は、そのまま観測・警告対象として示す。LOVEM追加と同時に書換えない。
- 0.3等を完全休業へ変更する検証は、指定された行に限定し、effectとvalueを一組で変更前後比較する。全小数値の一括変換は行わない。
- Bufferの1350等、対象操作の由来未確認値は、その状態を明記し、入庫上限・保管上限と推測で決めない。

## 12. 構成案と実装順序

### 12.1 構成

`既存WOM実行 → 観測adapter → 保存データ → 照合処理 → LOVEM viewer`

各境界でrun_idとschema_versionを持つ。viewerは保存結果を読むだけで、閲覧操作により再計画・入力変更を発生させない。

既存のイベント基盤が利用可能なら再利用する。ただし現在の実験ブランチで使えるかは、実装着手時に調べる。監視用処理でLotリストをsort/removeするなど、計画状態を変更しない。

### 12.2 作業段階（v0.2の段階名）

開始条件として基準SHA、未commit差分、入力ハッシュ、依存、既存API、現在のテスト結果を記録する。実験ブランチ名だけで基準を決めない。

| 段階 | 対象と内容 | 完了証拠 |
|---|---|---|
| A 観測 | ev-thailandの全Lot、元需要、予定S、実出荷、PSI区間、原イベントを取得 | manifest、取得可能項目表、原PSIとの区間復元照合、観測ON/OFF一致 |
| B 描画 | 同じrunをWindows Tk/matplotlibで全ID表示 | 全件描画数、ID選択と原記録参照、既知の正解図、Windows確認記録 |
| C 独立照合 | ev-thailand SE2の168 lotを週次数量差とID対応に分けて解く | Q01〜Q09・Q12、SE2全明細、数量集計への再照合、原因説明と残件 |
| D 全node金額接続 | soysauce-jpy-2027-allocとCookieを追加し数量→金額→Profit Zoneを追う | Q10・Q11、全node計上根拠、PPCとの差異、未確認範囲 |
| E 経営判断の往復 | 配分判断A/Bと観測・金額結果を関連付ける | decisionから図・金額への双方向参照 |

小さな合成fixtureは別モデル開発の拡大ではなく、A〜Cに組み込むテストとする。早出し・当週・遅配・未達・同数量別ID・重複・部分出荷・FIFO引当・Kitting・年跨ぎ・欠測を使い、既知の正解と照合する。区間encoder/decoderの正解を確かめてから実モデルの線を解釈する。

初回はC完了で一度区切り、結果を大杉さん・Claude君に返す。D/Eへ自動的に範囲を広げない。QのFAILやUNKNOWNを、原因特定済みのWOM不整合と観測器の不備に分ける。既存WOMの不整合を観測できたことは成果だが、観測器の欠損を完成扱いしない。

## 13. 試作モデルと受入条件

### 13.1 共通

- 全node、全対象週、全要求IDと観測供給IDの件数・数量を出力する。需要に紐付かない供給も別集合として残す。
- 同じ入力の観測ON/OFFで既存結果が変わらない。計測時間等の非業務項目は比較対象から明示的に除外する。
- UIで選択したIDからraw記録と照合結果へ移動でき、rawから同じ図位置へ戻れる。
- 100%保存された事実と、100%要求への充足対応が確認できた事実を区別する。
- 取得不能項目・未対応経路があれば、完成度と残件を示す。

### 13.2 soysauce-jpy-2027-alloc（段階D以降）

Business Ownerの採用配分、Lot生成、DL-2移動、Supply、node別金額を一巡して示す。比較元と配分変更案の2 runを同じnode順・週軸で比較する。

配分が変わるとLot_IDの生成数や意味が変わる可能性がある。同じ文字列という理由だけでrun間を同一個体として結ばず、元市場・製品・要求週・数量と生成規則を確認する。

Trial-02の9,293 IDと金額は4ed2f14での過去観測。新ブランチで再確認する値であり、期待値として機械的に固定しない。未出荷IDとPPC数量・金額の対応経路を再現できることを受入条件とする。

### 13.3 EV Thailand（初回A〜Cの唯一の実モデル）

全対象製品・全node・全週・全IDを描画し、2026-W38/W39の予定量と実出荷差168 lotが、どの要求集合に対応するかを調べる。

前週までに充足済み、当週充足、後週充足、期末未達、対応不明へ分解する。要求量が分割される場合は数量を分割して記録する。「168個のIDが遅配した」を前提にしない。総出荷9,370、総不足400という報告値も、同一コード・条件かを確認して扱う。

**SE2は今回の検査ケース名として使う。** 正式なモデルフォルダ名、製品、node、対象週、比較するrun、シナリオ、プラグインと168の集計式は、元の実装報告と実行条件を照合してmanifestに固定する。SE2を未確認のAPI名・データ列とみなさない。

初回完了に必要な出力：

1. 元の168 lotの定義を復元する。「予定S−実出荷の符号付き和」「各週の正の不足の和」「比較run間の差」を別列にし、どれが168なのか示す。同じ条件で再現できなければ、基準差分を報告して未解決とする。
2. 対象週だけでなく全観測期間の要求・出荷を追う。各週の要求と実出荷を多重集合で比較し、予定IDの不足と別IDの出荷超過を分ける。量の差168と未出荷ID件数が同じとは限らない。
3. 量差に関係する全要求を、元要求週に対する早出し・当週・後週・期末未達・対応不明へ分解する。同一Lot_IDが複数node・部材に現れるため、製品・node・役割・引当証拠を用いる。
4. 各要求について、要求量＝根拠付き充足量＋残要求量を照合する。未確認数量は残要求のうち判定不能な部分として別列にし、充足済みと二重加算しない。後日回復と呼ぶのは、当該要求への引当と後週実出荷が対応した部分だけである。
5. ID明細から元の週別予定S・実出荷・差を再集計して一致させる。予定外IDの出荷も別明細に保持し、都合のよい要求集合だけで168に合わせない。
6. 全ID図から該当明細へ、明細から図のnode・週へ移動できる。対応証拠がない経路は破断・UNKNOWNとして見える。
7. 独立checkerの結果、Windowsでの全件表示確認、原データ一式を添付する。「遅配だった」という仮説が否定されても、根拠付きで全量を説明できれば成功とする。

168に関係する数量にUNKNOWNが残れば原因解明は未完了とする。関係のない範囲の既知の未対応は明示して分離する。数量・IDの対応を説明するTrialと、発見したWOM不具合の修正完了は別の終了条件である。

### 13.4 Cookie（段階D）

Factory_GP_CNから下流へ、供給減少が伝わる範囲と、S・PPCへ伝わらなくなる境界を表示する。

報告された1,450 lot減少、past_due 1,388と残り62の説明は検査対象であり、ID対応で確定する。PPC不変という集計結果から、計上が正しいとも誤りとも即断しない。入力数量の出所と認識規則を示す。

### 13.5 描画性能

初回はev-thailandの固定runで、区間数・イベント数・ユニーク需要ID数・展開出現件数・lot-週を別々に記録する。圧縮前PSIの走査、保存、読込、線分生成、全体描画、拡大・選択応答の時間とピークメモリ、ファイル容量を計測する。圧縮率の分母・分子を明示する。画面への投入線分数と採用したinterval/eventの件数の対応も検査する。

3年・5年、smartx等への拡張負荷試験は後続の性能確認とし、EV Thailandの168 lot解明の必須対象を増やさない。未測定の秒数や削減率を達成済みとしない。Windows実機条件を付けて結果を提示し、操作性の受入判断を残す。

性能不足の場合は、保存件数を減らす前に描画方式・遅延読込を検討する。全件表示の完了状態と進捗を利用者に示す。

## 14. Business Ownerへの帰着

意思決定レーンには、判断時点と適用期間を別々に配置する。関係線は物流の線と区別し、対象配分・市場・計画期間へ接続する。

比較表示では以下を同時に辿れるようにする。

1. 何を狙って、どの市場へどれだけ配分したか。
2. そのために各nodeで何週前に何を用意する計画になったか。
3. どこで供給が成立し、在庫・未達・期間外が残ったか。
4. 全nodeの売上・原価・利益とProfit Zoneがどう変わったか。
5. 利益差のどこまでが数量差、単価差、費用差、期間差で説明でき、何が未確認か。

「狙った利益」「供給成立数量に対応する利益」「現在のPPC計上利益」の前提を併記し、差異を次の経営判断へ戻す。因果を比較で主張する場合は、変更した条件と固定した条件を明記する。

## 15. 成果物・保存・開発ゲート

初回A〜Cの実装成果物は、観測adapter、区間encoder、独立全数checker、Windows viewer、合成fixture、ev-thailand検証報告、SE2週別・ID別照合明細、データ辞書、再実行手順とする。soysauce・Cookieの金額検証報告はD以降に追加する。具体的なPython module名は既存構成の調査後に定める。

担当分担は、Claude君＝設計整合とRequest Letter整理、Code君（Claude Code）＝観測・保存・画面、Astra君＝独立checkerと差分レビュー、大杉さん＝業務判断と最終Windows確認を想定する。スキーマ変更は両実装へ同時に伝え、観測側だけでチェック基準を変更しない。

各実験を独立したrunフォルダへ保存し、入力・コード・観測器・出力のハッシュを付す。生データと報告書をZIPで渡し、消失した過去データに依存しない。

試作の作業を「観測」「描画」「数量と金額の対応」「業務ロジック修正」に分ける。観測で発見した不整合を、その場で原本CSVやgoldenを書き換えて隠さない。

開始時に必要な確認は、新ブランチの実在と基準SHA、休業実装の保存状態、未承認差分、観測可能な記録境界である。設計意図を再度一から議論するための停止条件にはしない。

現時点で未確定の実装事項は、既存hook/API接続、node別価格・利益の取得範囲、Profit Zoneの集計境界、全件描画方式の性能である。各段階の成果物で確認し、確認結果を本書へ戻す。

---

**v0.2の初回判断軸：EV Thailandの全Lotを、可逆な区間データとWindowsの全ID図で示し、SE2の168 lotを独立照合で説明する。全nodeの金額とBusiness Ownerへの帰着は、段階D/Eで接続する。**
