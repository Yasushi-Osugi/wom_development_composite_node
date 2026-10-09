# WOM Start Here — 新しい人と新しい AI のための入口

- 版：2026-10-08（ブランチ `wom-v1r5m1_cap_trial`）
- 作成：Claude君（大杉さんの依頼）
- 位置づけ：**今有効な規則の索引と要約**。本文の正典は、各節で示す文書にある。この文書と正典が食い違ったら、正典が正しい（そしてこの文書を直す）。
- `CLAUDE.md` の大半は、日付順の**開発の経緯の記録**である。今有効な規則を探すときは、まずこの文書から辿ること。

---

## 0. 最初に読む順番

| 順 | 文書 | 何が分かるか |
|---|---|---|
| 1 | この文書 | 全体の地図、今有効な規則、新しいモデルの作り方 |
| 2 | `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md` | **計画の正典**：Lot_ID の基本ルール、状態の呼び方、例外と決定 D1〜D7a |
| 3 | `docs/design/wom_canonical_concepts.md`、`demand_anchored_lot.md` | WOM の考え方（設計の憲法）、Demand Anchored Lot |
| 4 | `AGENTS.md` | 保護対象のコアと 3 層のテスト（コードを変えるとき必須） |
| 5 | 扱うテーマの設計書・報告書（§5 の機能の地図） | 詳細 |

---

## 1. WOM とは

- **WOM（Weekly Operation Model）**：週次の PSI（Production・Sales・Inventory）を単位にした、E2E のサプライチェーン計画とシミュレーションのツール。Python ＋ tkinter ＋ matplotlib。
- 目的は、日・時間単位の実行系ではなく、**経営層のための事業モデルの定義と評価**（新規事業の事業性評価、生産配分、世代交代、為替・関税の影響など）。
- **機密情報を扱う前提**で、Stand Alone の Windows PC で動かす。画面は Tk ＋ matplotlib だけで作り、Web 系の GUI（plotly など）は使わない。World Map も手元のデータ（Natural Earth）だけで描き、実行時にネットワークへ出ない。
- 公開のときは、固有の企業名とクリティカルな数字を出さない（架空のケースとして定義する）。
- 起動：`python -m main`（GUI）。headless：`python -m tools.run_headless_from_folder --model-dir data\sample\<モデル> --plugins safe`。

---

## 2. 基本の考え方（正典：決定記録 §1、`demand_anchored_lot.md`）

### 2.1 二つの木とノードの種類（`sc_tree_master.csv` の `node_type`）

```
InBound（作る側）: leaf_in（部材・原料） → stockyard（組立の置場） → mom（工場）
                                           ↓ 供給点（supply_point、仮想）
OutBound（売る側）:                         dad（DC・倉庫） → leaf_out（市場・販売チャネル）
```

- **supply_point は仮想のノード**（グローバル需給センター、仮想の HQ 機能）。物理の輸送・在庫・運賃を持たない。物理の区間は supply point を飛ばして「MOM → 最初の DAD」と結ぶ。
- `node_master.csv` の `node_type`（procurement・mother_plant・sku_supplier・region_dc・marketing）は地図の色の分類で、上の木の用語とは別の体系。`node_id` は木の `node_name` と同じ名前にする。

### 2.2 Lot_ID は需要の単位

- **要求 X は、同じ ID の lot X が出荷された週に満たされる**（Lot_ID の同一性）。
- Lot_ID は**需要の単位**であり、物理の個体ではない（部材ノードの同じ ID は、その需要に対応する部材）。
- 状態の呼び方：当週出荷／遅配／期末注文残／早出し（基本ルールでは起きない）／I と CO に同じ ID（休業などで正常に起きる）。
- **売上の数量は実際に出荷された lot の数**（予定の S ではない）。

### 2.3 計画の方式（`planning_config.csv` の `lot_flow_mode`）

- **identity（既定）**：Lot_ID の基本ルールで計画する。
- **legacy**：前の方式。今は rice だけ。rice の legacy の結果は、下流で需要の P をコピーする経路のため、上流の不足が市場に見えない（`docs/development/WOM_RiceDAL_Trial_Report.md` §4）。**rice の数字を正解として扱わない。**

---

## 3. 今有効な業務ルール（索引）

| # | ルール | 正典・根拠 |
|---|---|---|
| R1 | Lot_ID の基本ルール、例外 1・2 の扱い（D1〜D7a） | 決定記録 |
| R2 | **計画期間**は、需要 CSV の最初の週から最後の週までの連続した ISO の週。CSV に無い週は需要 0 として埋め、埋めた週を報告する | `wom/engine/plan_period.py`、`docs/development/WOM_PeriodDetection_Fix_Report.md` |
| R3 | **warmup**（先行生産の助走）は 17 週（約 4 か月）。リードタイムの長いモデルは 26 週。`planning_config.csv` の `warmup_lt` | 決定記録 D7・D7a、`docs/design/planning_warmup_and_reporting_horizon.md` |
| R4 | **能力の値**：空欄 ＝ 未設定（上限なし）、`0` ＝ 能力ゼロ、正の数 ＝ 上限、負・数値でない ＝ 読み込みで止める。計画の木に無いノード名の行も止める | `CLAUDE.md`「能力の値の意味」、`WOM_CapacityZeroBlank_Report.md` |
| R5 | **能力の行が無い週は「上限なし」**。発売前・生産終了後など作れない週は、行を省かず `0` を書く（省くと Backward がそこへ作り溜める） | 同上 §4 |
| R6 | **休業と能力ゼロは別の状態**。設備・拠点が止まる週は休業（`holiday_calendar.csv` の supply_closure・操業カレンダー）、「その週は作れない」だけなら能力 0 | `CLAUDE.md`「能力の値の意味」、`docs/design/holiday_calendar_and_capacity_semantics.md` |
| R7 | **`cpu_size`** は 1 lot の物量（例：iphone_global は 1,000 台）。PPC のマスターの単価は**物量当たり**（PPC が lot 数 × cpu_size を掛ける） | `WOM_StageD_Phase1_Report.md` §2・§12 |
| R8 | **運賃は物理の区間だけに書く**（`ppc_edge_cost_rule.csv`）。ノード費用（`ppc_node_cost_rule.csv`）に運賃を書かない。同じ輸送を 2 か所に書くと二重計上になる。Cookie は対応済み。ev・oil などはノード費用に運賃が残っており、Value Chain の題材にするときに寄せる（Value Chain のローダは、ノードに運賃があると止まる） | 同上 §2、`data/sample/Cookie-jp-2026/README.md` |
| R9 | **関税は国境を越える区間**に置く（soysauce-jpy-2027-alloc は対応済み。ほかの soysauce と apparel-global は最後の区間に残っており、題材にするときに移す） | 段階 D の決定 c |
| R10 | **販売チャネル**は、各国・各地域の中に ①自社 ②外部 ③自社ネット の 3 種類が並ぶ（PySI の時代から変わらない定義）。自社か外部かを名前から推測しない（割当表で明示） | `docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md` §3 |
| R11 | **通貨の三つの役割**：① HQ の報告通貨（例 JPY）② 国際共通の評価通貨（USD）③ 現地通貨（例 EUR）。為替は `ppc_fx_rate.csv` だけを使い、黙って 1 にしない。表の最初の週より前は最初の週のレートを使って記録、表の後や無い通貨は未評価 | 同上 §5 |
| R12 | **設定が無い価格**は未評価（NaN）にして一覧に出す（0 にしない）。助走週の仕入価格は、表の最初の行の価格を使って記録 | `WOM_StageD_Phase1_Report.md` |
| R13 | **金額の三つの視点**：V1（ノード・区間の管理評価）、V2（法人別）、V3（連結。内部取引の消去と、内部の未実現利益の消去） | 段階 D 設計 v1.0、`WOM_StageD_Phase2_Report.md` |
| R14 | **能力を上位で扱う層**：市場の要求（週と Lot_ID）は変えず、内部の計画の位置だけを渡す。前倒しの窓（例 17 週）を設定する。プラグインで既定は OFF | `WOM_GenerationLine_UpperLayer_Report.md`、決定記録 §3（モデル 4） |
| R15 | **世代の切り替えのライン**：混流しない。空き期間（例 4 週）は両世代とも能力 0。切り替えの週は上位の層で候補を並べて選ぶ | 同上、`data/sample/smartx-2027-2029/README.md` |

---

## 4. 新しいサプライチェーン・モデルを作る

### 4.1 手本にするモデル

- **Cookie-jp-2026**：1 地域に 3 種類のチャネル、2 法人（中国の工場と日本）、運賃は物理の区間だけ、Value Chain のマスターあり。最初の手本に向く。
- **soysauce-jpy-2027-alloc**：3 法人・3 通貨、法人間の価格・卸価格、関税は国境の区間。
- **smartx-2027-2029**：能力のボトルネック、世代の切り替えのライン、上位の層。
- **ev-europe-2026**：組立と Stock Yard（Kitting）。
- rice は今、手本にしない（§2.3）。

### 4.2 フォルダの中身（`data/sample/<モデル>/`）

| 区分 | ファイル | 要否 |
|---|---|---|
| 計画 | `sc_tree_master.csv`（木）、`node_master.csv`（拠点と座標）、`demand_forecast.csv`（`sku_id, region, week, quantity`）、`capacity_plan.csv`、`planning_config.csv`（`warmup_lt`、`lot_flow_mode`、`cpu_size` など） | 必須 |
| 計画（任意） | `holiday_calendar.csv`、`push_config.csv`（push のバッファ）、`operating_calendar.csv`、`inventory_master.csv`、`lane_assignment.csv`、`route_master.csv`、`sku_master.csv` | モデルに応じて |
| 金額（PPC） | `ppc_market_price.csv`、`ppc_supplier_cost.csv`、`ppc_node_cost_rule.csv`、`ppc_edge_cost_rule.csv`、`ppc_tariff_rule.csv`、`ppc_transfer_price_rule.csv`、`ppc_fx_rate.csv`（無ければ `data/ppc` の見本） | PPC を見るなら |
| 金額（Value Chain） | `vc_config.csv`、`vc_entity.csv`、`vc_node_assignment.csv`、`vc_price_rule.csv` | 法人・連結を見るなら |
| 上位の層 | `capacity_layer_config.csv` | 上位の層を使うなら |
| 説明 | `README.md`（決めごと・仮の値・根拠） | 推奨 |

### 4.3 よくある落とし穴（実際に起きたもの）

1. 能力の CSV のノード名が木と違う → 今は読み込みで止まる（前は黙って捨てられていた）。
2. 作れない週の能力の行を省く → 「上限なし」になり、何年も前から作り溜める（R5）。
3. 需要 CSV の週を抜かす → 今は 0 で埋めて報告される（前は計画の終わりが切れていた）。
4. 同じ運賃を区間とノードの両方に書く → 二重計上（R8）。
5. supply point に運賃や在庫を持たせる → 仮想のノードなので持たない（§2.1）。
6. 単価の単位を lot と物量で取り違える → `cpu_size` と PPC のマスターの単位を揃える（R7。iphone の「1 万倍」の件）。
7. `node_master.csv` に座標が無い → World Map に描けない（一覧に出る）。Stock Yard は座標が無ければ親の組立工場の位置に描かれる。
8. 価格を 0 で埋める → 未評価として扱うべきもの（R12）。
9. 報告の開始週を二か所に書く → `vc_config.csv` の `report_start` だけに書く（`wom/engine/report_start.py`。World Map・Flow Check・Value Chain・Rice が読む）。無ければ最初の非ゼロ需要週。Rice の設定に残すと止まる。

### 4.4 確かめ方

| 道具 | 何を見るか |
|---|---|
| Network タブの Flow Check | ノードごとの数量の保存、市場の需要（当週・遅配・期末注文残）、Kitting |
| LOVEM（`python -m tools.lovem_observe` → `python -m wom.lovem.viewer`） | Lot を 1 本ずつ、ノード × 週で追う |
| World Map タブ | 実出荷の流れを地理の上で見る（出荷・輸送中） |
| Management → Value Chain | 法人別・連結の損益（消去前／消去後）、未評価・未設定価格の一覧 |
| `python -m tools.valuechain_run` | Value Chain の台帳を CSV で出す |
| headless（`tools.run_headless_from_folder`） | GUI 抜きで計画と PPC を回す |

---

## 5. 機能の地図

| 機能 | 中身 | 設計・報告 |
|---|---|---|
| 計画エンジン（PSI） | Backward・Forward、identity | 決定記録、`WOM_LotIdentityFlow_Report.md` |
| 能力・休業 | cap_hard・cap_soft、休業、能力ゼロ | `holiday_calendar_and_capacity_semantics.md`、`WOM_CapacityZeroBlank_Report.md` |
| warmup・計画期間 | 助走、期間の検出 | `planning_warmup_and_reporting_horizon.md`、`WOM_Warmup17_IdentityGolden_Report.md`、`WOM_PeriodDetection_Fix_Report.md` |
| Kitting・Stock Yard | 組立の部材の揃い | `kitting_list_assembly.md`、`WOM_iPhoneWarmup_EVUpdateKitting_S2_Report.md` |
| PPC（金額の旧方式） | 市場 leaf を起点にした価格・原価・利益 | `psi_ppc_separation.md`、`WOM_StageD_Survey_Report.md` |
| Value Chain（段階 D） | 実出荷の記録からの台帳、V1・V2・V3、連結、未実現利益の消去 | 設計 v1.0、`WOM_StageD_Phase1_Report.md`、`WOM_StageD_Phase2_Report.md` |
| LOVEM | Lot の観測と表示 | `docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`、`WOM_LOVEM_StageAB_EVThailand_Report.md`、`WOM_LOVEM_StageC_Report.md` |
| World Map | Natural Earth ＋ 実出荷 | `WOM_WorldMap_ActualFlows_Report.md` |
| 生産配分（`ask_global_allocation`） | 市場ごとの配分の利益地形 | `ask_global_allocation_spec.md`、`wom_model_typology.md`、`three_layer_production_allocation.md` |
| 上位の能力の層 | ボトルネック、世代の切り替え | `WOM_SmartxBottleneck_Report.md`、`WOM_GenerationLine_UpperLayer_Report.md` |

---

## 6. 開発の進め方

- **役割**：大杉さん（Owner：判断・実機確認・git）、Claude君（設計・依頼書・検証）、Code君（Claude Code：実装）、GPT-6 Astra君・GPT-6.1 Sol君（独立の調査・検証）。
- **流れ**：依頼書（`requests/`）→ 実装 → 報告書（`docs/development/`）→ 検証（「止める理由」と「申し送り」を分ける）→ commit。依頼書と実装は別の commit にする。
- **保護対象のコア**（`AGENTS.md` §10）：`backward_planner.py`、`forward_planner.py`、`plan_copy.py`、`plan_node.py`、`sc_tree.py`、`push_pull.py`。依頼書が無ければ変えない。変えるときは 3 層のテスト（単体・CSV からの結合・golden）を緑にし、大杉さんが diff を確かめる。
- **golden**：`tests/golden/*.json`（13 件）と `tests/golden/legacy/`（3 件）。意図した変化のときだけ、変わるモデルを報告してから作り直す。rice は HarvestBatch を含む 4 プラグインで作る（`CLAUDE.md`「禁足ルール」の節の手順）。
- **git**：Windows 側で行う。リモートは `composite_node`（`wom_development_composite_node`、default branch `wom-v1r5m1_cap_trial`）。commit メッセージの下書きは `commit_msg*.txt`（git の対象外）。
- **誤読を招く名前**は見つけ次第、関連する資料をまとめて直す。黙った既定値（0・1・前の週）を作らない。

---

## 7. 今開いている課題（2026-10-09）

| 課題 | 状態 |
|---|---|
| rice の再定義（HarvestBatch をやめ、Demand Anchored Lots に揃える） | 移行用コピー `data/trial/rice-japan-2027-2028-seasonal/` で実装済み（上位の層 `wom/capacity_layer/rice_seasonal.py`、プラグイン Rice Seasonal・既定 OFF。報告 `docs/development/WOM_RiceSeasonal_Implementation_Report.md`）。236,937 ID のうち当週 141,210、注文残 95,727（助走の2026年 67,169、報告期間のコシヒカリ 28,556＝収穫量不足）。精米の前倒しは1週まで、不足のときは比例配分を前倒しの少なさより優先する。元の `rice-japan-2027-2028`（legacy）と golden の置き換えは Owner の受入の後。そのとき §3 に季節供給の規則を足す。残り：年産上限の業務値、収穫年ごとの価格と古い在庫の評価損、ぬか等の金額、大きな run での LOVEM `verify_run` のメモリ |
| Backward の前倒しの上限 | 上位の層が OFF のとき上限が無い（`WOM_GenerationLine_UpperLayer_Report.md` §11.1） |
| 世代間の需要の移行 | 旧世代の残りの需要を新世代へ振り替える規則が無い |
| 在庫の保有費用・陳腐化の金額 | `vc_config.csv` の `holding_rate_weekly` を設定し、smartx などに Value Chain のマスターを用意してから |
| Cookie の CVS・soysauce の卸価格 | 仮の値（各モデルの README に根拠と損益分岐） |
| india-ghee-2026 の warmup | 12 週（R3 の 17・26 と揃っていない） |
