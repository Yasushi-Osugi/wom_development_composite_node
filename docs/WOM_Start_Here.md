# WOM Start Here — 新しい人と新しい AI のための入口

- 版：2026-10-31（ブランチ `wom-v1r5m1_cap_trial`）
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
| — | [BS-SEAF の進め方の知識](bsseaf/WOM_BSSEAF_Process_Knowledge.md)（WOM-KB-BSSEAF-001） | WOM を BS-SEAF の 8 段階で改良する進め方：段階と担当、誤りの型と打ち手、標準にするもの（知識 × 適用条件 × 根拠）、一巡ごとの記録、中心仮説。**事例を始める前に読む** |
| — | `docs/semantics/`（業務の意味体系、[読み方](semantics/README.md)） | 業務の用語の定義と、判断に要る業務の情報。**機能の名前を探す前に**、扱う業務の問いの意味をここで確かめる（§0.1） |

### 0.1 生産配分と優先供給を調べる入口

**業務の問いから入る**：

| 業務の問い | 1. 意味を確かめる | 2. WOM での表し方 | 3. 事例 |
|---|---|---|---|
| 供給が足りない。どの市場・チャネルに、どれだけ供給するか／外した需要はどうなるか／計画の注文残は何か | [供給配分の意味体系](semantics/supply_allocation.md)（配分・未配分・受渡点・納期延期・注文残、追跡する 5 つの数量と成立条件、例題。採否：定義と数量の関係は採用〔2026-10-26〕、未決事項は保留。根拠は文書の §0） | [三層設計MD](design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md)（既存の機能・入力・経路、適用の前の確認 ALC-Q） | 化粧品：`docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md`（C3a）、`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` |

**配分（供給の対象にする数量を決めること）と納期延期（後の時期に届けること）は別の判断である。** 計画の結果の注文残は「配分したが届かなかった量」であり、「配分で外した量（未配分）」とは別に数える。期末の注文残は、要求の Lot_ID と実出荷の Lot_ID を照合して数える（Flow Check 表2 の backlog_end）。最終週の CO や、毎週の CO の合計では数えない。

市場優先・チャネル優先・Global HQの需給調整（親心）・Demand Allocation・Supply Allocation・Capacity Envelopeを扱うときは、[生産配分と優先供給の三層設計MD](design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md)を先に読む。**Managementの配分判断、Backwardの需要・生産配置、Forwardの制約下の供給計算は、WOMの既存機能群である。** 配分を需要CSVへ渡す`wom/allocation/handoff.py`、三層を一巡する`tools/run_planning_loop.py`、計画案を残す`wom/planning_state/`にも辿る。

機能の存在、対象モデルでの有効化、層間の接続、結果の検証を分けて確かめる。通常のBackwardが常に利益順で配分するとは仮定しない。「WOMに機能が無い」「Coreの新規実装が必要」と判断する前に、既存経路と適用条件を調べる。

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
  - ただし、Backward が MOM の能力で lot を前倒しすると、MOM はその週に実出荷として記録し、作り置きは **supply point の I に現れる**（supply point の要求週は前倒しされないため）。これは**物理的には工場の完成品在庫**であり、エンジンの誤りではない。在庫の所在を読むときは「supply point の I ＝ 工場の完成品倉庫」と読み替える。使用期限・滞留を数えるときは、工場の出荷週を起点にする（`docs/development/WOM_BSSEAF_Cosmetics_Trial_Report.md` Q5）。
- `node_master.csv` の `node_type`（procurement・mother_plant・sku_supplier・region_dc・marketing）は地図の色の分類で、上の木の用語とは別の体系。`node_id` は木の `node_name` と同じ名前にする。

### 2.2 Lot_ID は需要の単位

- **要求 X は、同じ ID の lot X が出荷された週に満たされる**（Lot_ID の同一性）。
- Lot_ID は**需要の単位**であり、物理の個体ではない（部材ノードの同じ ID は、その需要に対応する部材）。
- 状態の呼び方：当週出荷／遅配／期末注文残／早出し（基本ルールでは起きない）／I と CO に同じ ID（休業などで正常に起きる）。
- **売上の数量は実際に出荷された lot の数**（予定の S ではない）。

### 2.3 計画の方式（`planning_config.csv` の `lot_flow_mode`）

- **identity（既定）**：Lot_ID の基本ルールで計画する。
- **legacy**：前の方式。**`data/sample/` に legacy で動くモデルは無い**（2026-10-09、rice が identity に移った。`tests/test_rice_retire.py` が全サンプルの identity を確かめる）。方式のコードは決定記録 D3 のとおり残し、`tests/golden/legacy/`（3 件）が守る。
- 前の rice（legacy＋HarvestBatch）は 236,937 ID の全部が当週出荷に見えたが、それは HarvestBatch の匿名の期首在庫（`OI_`）が助走の年の不足と収穫量の不足を隠していたため。identity では当週 141,210・注文残 95,727（`docs/development/WOM_RiceLegacyRetire_Report.md`）。**出どころの無い在庫は、不足を見えなくする。** 2026-10-16 からは、2025 年産を計画の中の普通の年産として持つ（計画は 2025-W33 から。`WOM_RiceOpeningCrop2025_Report.md`）。

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
| R7 | **`cpu_size`** は 1 lot の物量（例：smartphone-global-2026-2029 は 1,000 台）。PPC のマスターの単価は**物量当たり**（PPC が lot 数 × cpu_size を掛ける） | `WOM_StageD_Phase1_Report.md` §2・§12 |
| R8 | **運賃は物理の区間だけに書く**（`ppc_edge_cost_rule.csv`）。ノード費用（`ppc_node_cost_rule.csv`）に運賃を書かない。同じ輸送を 2 か所に書くと二重計上になる。Cookie は対応済み。ev・oil などはノード費用に運賃が残っており、Value Chain の題材にするときに寄せる（Value Chain のローダは、ノードに運賃があると止まる） | 同上 §2、`data/sample/Cookie-jp-2026/README.md` |
| R9 | **関税は国境を越える区間**に置く（soysauce-jpy-2027-alloc は対応済み。ほかの soysauce と apparel-global は最後の区間に残っており、題材にするときに移す） | 段階 D の決定 c |
| R10 | **販売チャネル**は、各国・各地域の中に ①自社 ②外部 ③自社ネット の 3 種類が並ぶ（PySI の時代から変わらない定義）。自社か外部かを名前から推測しない（割当表で明示） | `docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md` §3 |
| R11 | **通貨の三つの役割**：① HQ の報告通貨（例 JPY）② 国際共通の評価通貨（USD）③ 現地通貨（例 EUR）。為替は `ppc_fx_rate.csv` だけを使い、黙って 1 にしない。表の最初の週より前は最初の週のレートを使って記録、表の後や無い通貨は未評価 | 同上 §5 |
| R12 | **設定が無い価格**は未評価（NaN）にして一覧に出す（0 にしない）。助走週の仕入価格は、表の最初の行の価格を使って記録。**PPC も同じ（D8）**：結果に `valuation_status`（評価済み／一部未評価／未評価）を持つ。価格・仕入れの原価の行が無い製品 × 市場は 0 円で評価せず除き、除いた量を記録の件数・WOM の lot 数・物量で `excluded` に出す。未評価は金額のキーを持たない。一部未評価の金額は全計画の金額と比べない。規則の最初の週より前の週は最初の行の値を使い、件数を記録（`price_before_first_rule_week`）。費用の規則（ノード・区間・関税）の「行が無い」は費用なしとして扱い、件数だけを数える（未設定と区別するかは未決） | `WOM_StageD_Phase1_Report.md`、`docs/development/WOM_PPC_NoSilentFallback_Report.md` |
| R13 | **金額の三つの視点**：V1（ノード・区間の管理評価）、V2（法人別）、V3（連結。内部取引の消去と、内部の未実現利益の消去） | 段階 D 設計 v1.0、`WOM_StageD_Phase2_Report.md` |
| R14 | **能力を上位で扱う層**：市場の要求（週と Lot_ID）は変えず、内部の計画の位置だけを渡す。前倒しの窓（例 17 週）を設定する。プラグインで既定は OFF | `WOM_GenerationLine_UpperLayer_Report.md`、決定記録 §3（モデル 4） |
| R15 | **世代の切り替えのライン**：混流しない。空き期間（例 4 週）は両世代とも能力 0。切り替えの週は上位の層で候補を並べて選ぶ | 同上、`data/sample/smartx-2027-2029/README.md` |
| R16 | **季節の供給（rice）**：市場の要求（週と Lot_ID）は変えず、上位の層が ID ごとに収穫週と精米週を別々に選ぶ。週の設備の上限・収穫の週・年産の上限・保管の上限・歩留まりは別々の入力。匿名の期首在庫を作らず、報告の期首在庫は計画の中の先の収穫から作る。助走の年の不足は報告期間と分けて数える。**前年産は、計画の始まりを前年の収穫の前に延ばし、普通の年産としてデータで持つ**（rice は 2025-W33 から、2025 年産は仮定の量。期首在庫を外から置く機能は作らない。決定記録 D7 と同じ考え、`WOM_RiceOpeningCrop2025_Report.md`）。不足のときは要求週の早い順、同じ週は市場の要求量に比例して配る（精米の前倒しの少なさより優先） | `docs/development/WOM_RiceSeasonal_Implementation_Report.md`、`data/sample/rice-japan-2027-2028/README.md`、依頼書 §8 |
| R17 | **歩留まり**（`sc_tree_master.csv` の `yield_rate`、工場＝MOM の行だけ）：完成品の出荷時点に一本化した歩留まり。工程別の不良は見ない。`cap_hard`（Sealing_Qty）・`cap_soft`（Production_Qty）は物理の投入の能力のまま、エンジンは **floor（能力 × yield_rate）＝引当て可能な良品の lot 数**で lot を置き・封じる（`PlanNode.shippable_*`）。不良の分の Lot_ID は作らない。空欄・列なし＝1.0。不正な値、MOM 以外、push の MOM、legacy、Rice Seasonal ON では止まる。投入の物量（1／y）と金額は Part B（未実装） | `docs/development/WOM_YieldRate_PartA_Report.md`、`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.2.md` §7 |
| R18 | **製品の年齢（残存期間）は先入れ先出しで数える**。物の在る所（工場の完成品倉庫＝supply point の I、DAD、店頭）ごと・SKU ごとに製造週（工場の実出荷週）の札を並べ、古い札から出す。年齢＝納品週 − 製造週（計画の週の番号で数える）。**Lot_ID は需要の単位なので、物の年齢を Lot_ID で数えない**（作り置きのとき需要の単位と物が離れ、年齢を大きく数える。化粧品の B3：Lot_ID で最大 165 週、先入れ先出しで最大 21 週）。道具 `python -m tools.shelf_life_check --model-dir <モデル> --max-age-weeks <週>`（許容は必須） | `docs/development/WOM_WarmupSoft_BlankAttrs_ShelfLifeFIFO_Report.md`、`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.4.md` §8.3 |
| R19 | **木の属性の空欄**（`sc_tree_master.csv`）：`ss_days`・`init_stock_days` の空欄は N/A（未設定。計画は 0 と同じ）、0 は明示の 0、0 以上の整数以外は止まる。`demand_envelope` の空欄は hard、hard・soft 以外は止まる（綴りの誤りを推測で直さない。直すのはモデルの CSV）。warmup の行には、能力の値の列（`max_supply`・`cap_soft`）を最初の実週から写す | 同上（`wom/engine/tree_attrs.py`、`wom/engine/warmup.py` の `_CAPACITY_COPY_COLS`） |
| R20 | **生産配分と優先供給は三層で扱う**：Managementが採用配分を決め、BackwardがLT・需要集約・能力を考慮して配置し、Forwardが制約下の実出荷・未充足を計算する。既存のCSVハンドオフと三層連携CLIがある。元需要・配分済み需要・実納品を分け、対象ケースでの有効化・接続・検証を確認してから差分を判断する | [三層設計MD](design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md)（WOM-KB-ALLOCATION-001）、`wom/allocation/handoff.py`、`tools/run_planning_loop.py` |
| R22 | **PPC・Value Chain の規則の出どころ**：モデルのフォルダのファイルを先に使う。共有の規則（`data/ppc`）は、`planning_config.csv` の `ppc_shared_rules_dir` で宣言したモデルだけが、モデルに無いファイルについて読む（Cookie・rice・smartphone が宣言）。宣言が無ければ `data/ppc` は読まず未評価。見本の販売データで計算することは無い（`python -m wom.ppc` の実演だけ）。チャネルの対応方式（`use_node_name`）は規則の出どころとは別に決まる | `wom/ppc/ppc_rules.py` `resolve_ppc_rules()`、`docs/development/WOM_PPC_NoSilentFallback_Report.md` |
| R21 | **金額なしで配分を試すときは数量配分モード**：`tools/run_quantity_allocation.py`（SKU × チャネルの lot 数で配分を渡す。価格・原価・`ga_*` を読まず、PPC を呼ばず財務は「未評価」）。元の需要で計画期間・warmup・能力を固定し、①〜⑤ を Flow Check 表2 の明細で数える。不整合なら結果を保存せず `diagnostics/` に書く。配分後の未充足（⑤ > 0）は計画の結果として保存する。期末の注文残を最終週の CO や毎週の CO の合計で数えない（`backlog_lot_weeks` は lot × 週） | [意味体系](semantics/supply_allocation.md) §3、[三層設計MD](design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md) §3.1、`docs/development/WOM_QuantityAllocationMode_Report.md` |

---

## 4. 新しいサプライチェーン・モデルを作る

### 4.1 手本にするモデル

- **Cookie-jp-2026**：1 地域に 3 種類のチャネル、2 法人（中国の工場と日本）、運賃は物理の区間だけ、Value Chain のマスターあり。最初の手本に向く。
- **soysauce-jpy-2027-alloc**：3 法人・3 通貨、法人間の価格・卸価格、関税は国境の区間。
- **smartx-2027-2029**：能力のボトルネック、世代の切り替えのライン、上位の層。
- **ev-europe-2026**：組立と Stock Yard（Kitting）。
- **rice-japan-2027-2028**：季節の供給（収穫・玄米保管・精米）、品目共用の設備、不足の配分。Rice Seasonal のプラグインが要る（GUI はモデルを読むと自動で ON。Holiday Calendar は手で ON）。
- **cosmetics-sg-th-2027-2029**：1 工場から 2 か国・4 チャネル（直営店・EC・代理店 2 つ）へ、販売開始のずれ、店頭在庫（`ss_days`）、能力の平準化（`demand_envelope`＝soft）と歩留まり、製品の年齢（先入れ先出し、`tools/shelf_life_check.py`）、金額の規則を全部モデルの中に持つ PPC。BS-SEAF の検証の事例で、比べる案（能力の不足・数量配分・関税）の作り方は `docs/scenarios/cosmetics.md`、業務の意味は [供給配分の意味体系](semantics/supply_allocation.md)。

### 4.2 フォルダの中身（`data/sample/<モデル>/`）

| 区分 | ファイル | 要否 |
|---|---|---|
| 計画 | `sc_tree_master.csv`（木）、`node_master.csv`（拠点と座標）、`demand_forecast.csv`（`sku_id, region, week, quantity`）、`capacity_plan.csv`、`planning_config.csv`（`warmup_lt`、`lot_flow_mode`、`cpu_size`、`recommended_plugins` など） | 必須 |
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
5. supply point に運賃や在庫を持たせる → 仮想のノードなので持たない（§2.1）。計画の結果として supply point の I に現れる作り置きは、工場の完成品在庫と読む（§2.1）。
6. 単価の単位を lot と物量で取り違える → `cpu_size` と PPC のマスターの単位を揃える（R7。smartphone の「1 万倍」の件）。
7. `node_master.csv` に座標が無い → World Map に描けない（一覧に出る）。Stock Yard は座標が無ければ親の組立工場の位置に描かれる。
8. 価格を 0 で埋める → 未評価として扱うべきもの（R12）。PPC の規則のファイルを見出しの行だけ置いたり、消したりしても、見本の金額にはならず未評価になる（R22。2026-10-26 より前は、見本の販売・見本の規則で、もっともらしい粗利率が出た）。
9. 報告の開始週を二か所に書く → `vc_config.csv` の `report_start` だけに書く（`wom/engine/report_start.py`。World Map・Flow Check・Value Chain・Rice が読む）。無ければ最初の非ゼロ需要週。Rice の設定に残すと止まる。
10. プラグインの組を GUI と headless で別々に選ぶ → 同じモデルで値が変わる（2026-10-09 の版の rice では、Holiday Calendar を忘れると当週出荷 139,554、正しくは 141,210）。モデルの `planning_config.csv` の `recommended_plugins` に golden と同じ組を書く。GUI は読み込みでチェックを合わせ、headless は `--plugins` を省けばこの組を使う。知らないプラグイン名は止まる。
11. 実在の企業・団体・製品の名前をサンプルや文書に書く → 公開のリポジトリなので一般名（`EMS_A`、`Retailer_A` など）にする。`tests/test_no_real_names.py` が止める。元の名前との対応表はリポジトリに入れない。
12. **計画の両端で能力が使えない**（化粧品の配分の試行 P1、`docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md` §4）→ 需要の合計を能力の合計にそろえても、期末の注文残が残ることがある。(a) **最初の週**：Backward は計画の最初の週にも能力があるとして押し戻しの最後尾を置くが、原料の区間（InBound のリードタイム）があると Forward はその週に作れず、注文残になる。Backward・Forward・Flow Check のどの記録にも「置いたが作れない」とは出ない（lot を追跡して初めて分かった）。(b) **最後の週**：店頭在庫（`ss_days`）などで早く作る分があると、最後の数週の工場の余裕を埋める需要が無い（押し戻しは前の週にしか動かない）。実際に使える能力は合計より少し小さい（P1：美容液 2,184 → 2,182）。この量は計画の境界の効果で、業務の欠品と読まない（Owner、2026-10-26）。Backward の扱いは保護対象コアの話で、今は記録だけ

### 4.4 確かめ方

| 道具 | 何を見るか |
|---|---|
| Network タブの Flow Check | ノードごとの数量の保存、市場の需要（当週・遅配・期末注文残）、Kitting |
| LOVEM（`python -m tools.lovem_observe` → `python -m wom.lovem.viewer`） | Lot を 1 本ずつ、ノード × 週で追う |
| World Map タブ | 実出荷の流れを地理の上で見る（出荷・輸送中） |
| Management → Value Chain | 法人別・連結の損益（消去前／消去後）、未評価・未設定価格の一覧 |
| `python -m tools.valuechain_run` | Value Chain の台帳を CSV で出す |
| headless（`tools.run_headless_from_folder`） | GUI 抜きで計画と PPC を回す |
| `python -m tools.quick_check` | テストの段（smoke・領域・全テスト）。§6 |

---

## 5. 機能の地図

| 機能 | 中身 | 設計・報告 |
|---|---|---|
| 計画エンジン（PSI） | Backward・Forward、identity | 決定記録、`WOM_LotIdentityFlow_Report.md` |
| 能力・休業 | cap_hard・cap_soft、休業、能力ゼロ | `holiday_calendar_and_capacity_semantics.md`、`WOM_CapacityZeroBlank_Report.md` |
| warmup・計画期間 | 助走、期間の検出 | `planning_warmup_and_reporting_horizon.md`、`WOM_Warmup17_IdentityGolden_Report.md`、`WOM_PeriodDetection_Fix_Report.md` |
| Kitting・Stock Yard | 組立の部材の揃い | `kitting_list_assembly.md`、`WOM_SmartphoneWarmup_EVUpdateKitting_S2_Report.md` |
| PPC（金額の旧方式） | 市場 leaf を起点にした価格・原価・利益 | `psi_ppc_separation.md`、`WOM_StageD_Survey_Report.md` |
| Value Chain（段階 D） | 実出荷の記録からの台帳、V1・V2・V3、連結、未実現利益の消去 | 設計 v1.0、`WOM_StageD_Phase1_Report.md`、`WOM_StageD_Phase2_Report.md` |
| LOVEM | Lot の観測と表示 | `docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`、`WOM_LOVEM_StageAB_EVThailand_Report.md`、`WOM_LOVEM_StageC_Report.md` |
| World Map | Natural Earth ＋ 実出荷 | `WOM_WorldMap_ActualFlows_Report.md` |
| 生産配分と優先供給（三層） | 配分の利益評価・採用、需要CSVへのハンドオフ、Backward配置、Forward供給、計画案記録。用語の意味は[供給配分の意味体系](semantics/supply_allocation.md) | [三層設計MD](design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md)、[配分仕様](design/ask_global_allocation_spec.md)、[計画案CLI](../tools/run_planning_loop.py)、[数量配分モード（金額なし）](../tools/run_quantity_allocation.py) |
| 上位の能力の層 | ボトルネック、世代の切り替え | `WOM_SmartxBottleneck_Report.md`、`WOM_GenerationLine_UpperLayer_Report.md` |
| 授業の教材 | Lesson 000「お米が足りない」：台本と、rice から比較モデル（収穫・精米 +30%）を作る道具 `tools/lesson000_variants.py` | `docs/lessons/lesson000/`、`WOM_Lesson000_Public_Report.md` |

---

## 6. 開発の進め方

- **役割**：大杉さん（Owner：判断・実機確認・git）、Claude君（設計・依頼書・検証）、Code君（Claude Code：実装）、GPT-6 Astra君・GPT-6.1 Sol君（独立の調査・検証）。
- **流れ**：依頼書（`requests/`）→ 実装 → 報告書（`docs/development/`）→ 検証（「止める理由」と「申し送り」を分ける）→ commit。依頼書と実装は別の commit にする。
- **BS-SEAF の一巡**：8 段階・誤りの型・標準の作法・報告書に残す記録は [BS-SEAF の進め方の知識](bsseaf/WOM_BSSEAF_Process_Knowledge.md)。最初の基準事例は化粧品（[検証報告](development/WOM_BSSEAF_Verification_Cosmetics_Report.md)）。
- **保護対象のコア**（`AGENTS.md` §10）：`backward_planner.py`、`forward_planner.py`、`plan_copy.py`、`plan_node.py`、`sc_tree.py`、`push_pull.py`。依頼書が無ければ変えない。変えるときは 3 層のテスト（単体・CSV からの結合・golden）を緑にし、大杉さんが diff を確かめる。
- **golden**：`tests/golden/*.json`（15 件）と `tests/golden/legacy/`（3 件）。意図した変化のときだけ、変わるモデルを報告してから作り直す。プラグインの組はモデルの `recommended_plugins` と同じ（rice 以外は Holiday Calendar・Buffering Stock・Capacity Override、rice はこれに Rice Seasonal）。作るときは `--plugins` を明示する（`CLAUDE.md`、`tests/test_golden.py` の説明）。
- **テストの段**（`tests/README.md`、2026-10-15）：途中は `python -m tools.quick_check --smoke`（約 1 分）と、直した所の領域（`--area rice` など、`--changed` は変えたファイルから選ぶ）。全テスト（`--full`、約 15〜18 分）は依頼書ごとに最後に 1 回。保護対象のコアを直したときは全テストと 3 層のテストが必須。依頼書には回す段を書く。新しいテストのファイルは `tests/conftest.py` の対応表に 1 行足す。golden を含む pytest は並行させない。
- **git**：Windows 側で行う。リモートは `composite_node`（`wom_development_composite_node`、default branch `wom-v1r5m1_cap_trial`）。commit メッセージの下書きは `commit_msg*.txt`（git の対象外）。
- **誤読を招く名前**は見つけ次第、関連する資料をまとめて直す。黙った既定値（0・1・前の週）を作らない。

---

## 7. 今開いている課題（2026-10-15）

| 課題 | 状態 |
|---|---|
| rice の残り | rice は identity に移った（`WOM_RiceLegacyRetire_Report.md`）。2025 年産を計画に入れた（2026-10-16、`WOM_RiceOpeningCrop2025_Report.md`）。残り：年産上限の業務値（2025 年産 55,785 は仮定）、2026 年の休日がデータに無い、届かない需要が注文残として最後まで残る扱い（小売の米では失われる需要に近い）、収穫年ごとの価格と古い在庫の評価損、ぬか等の金額、rice の PPC の価格表（今は `data/ppc` の見本の規則）、大きな run での LOVEM `verify_run` のメモリ（`tools/lovem_interval_check.py` で照合） |
| 公開の前のサンプルの見直し | 済み（2026-10-09、`docs/development/WOM_SampleNames_PublicReview_Report.md`）。実在の企業・団体・製品の名前を一般名にした（値は不変）。スマートフォンのモデルは `smartphone-global-2026-2029`、古い方は削除。全モデルに golden。`tests/test_no_real_names.py`（公開の一覧＋手元だけの `private/real_name_denylist.txt`）。画像も確認済み（実名の写った画面 9 枚を削除、`docs/images/` の 12 枚は問題なし）。サンプルの 1 モデルは Owner の判断で削除。git の履歴は書き換えない（Owner の判断） |
| 需要の出どころ（4P） | 需要は `demand_forecast.csv` として外から与えられている。製品・価格・チャネル・販促（コトラーの 4P）から需要の ID を作り、出どころを ID の属性として持つ「需要の層」を、上位の層と同じくエンジンの外に置く構想（Owner、2026-10-09）。rice では「不足のとき、配分・価格・品目の誘導のどれで対応するか」を比べる題材になる |
| Backward の前倒しの上限 | 上位の層が OFF のとき上限が無い（`WOM_GenerationLine_UpperLayer_Report.md` §11.1） |
| 世代間の需要の移行 | 旧世代の残りの需要を新世代へ振り替える規則が無い |
| 歩留まり Part B | 投入の物量（良品 1 lot の裏に投入 1／y）、良品 1 lot 当たりの原価、画面の良品の上限の線（`WOM_YieldRate_PartA_Report.md` §6） |
| supply point の作り置きの在庫の表示 | 理由は分かった（§2.1、化粧品の試行 Q5）：工場の完成品在庫が supply point の I に表示される。表示（所在の名前）を工場に寄せるかは未決 |
| 在庫の保有費用・陳腐化の金額 | `vc_config.csv` の `holding_rate_weekly` を設定し、smartx などに Value Chain のマスターを用意してから |
| 画面の表示の誤読（化粧品のサンプルの登録で分かった、`WOM_BSSEAF_Cosmetics_RegisterSample_Report.md` §5） | Management の Tariff & FX パネルが空のとき「設定して」と出るが、原因は `edge_cost_master.csv` が見出しだけであること（メッセージと原因がずれる）。Inv Value・CCC・AR・AP が 0 と並ぶのは単価・回転日数が無いためで、「在庫が無い」と誤読しうる（未設定と 0 を分けていない。R12 と同じ問題）。PPC の Waterfall の GM（1 lot 当たりの平均）と KPI の GM（全体）が違う値で、同じ名前で並ぶ |
| Value Chain の金額の層（G1〜G5） | 化粧品の金額の試行（`docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md` §6）で分かった、Value Chain が表せないもの：売上の率のノード費用を計上しない（G1。同じ行の 1 個当たりの金額も一緒に落ちる）、外部の代理店のノードに置いた自社負担の費用（MDF）を計上せず issues にも出ない（G2）、sell-in の代理店の売上が PPC より 1 週早い（G3）、関税の課税価格が振替価格だけ（G4、PPC も同じ）、CIF の運賃の負担（G5）。PPC は表せる。拡張するかは未決 |
| 費用の規則の「行が無い」 | ノード・区間・関税の規則の行が無い組合せは、全 golden のモデルにある（`WOM_PPC_NoSilentFallback_Report.md` §6.1）。今は「費用なし」として扱い、件数だけを数える（Owner、2026-10-26）。明示の 0 の行を求めるかは、化粧品の費用を置く段階で、費用の種類ごとに決める |
| 計画の最初の週に置かれて作れない lot | Backward は計画の最初の週の能力を使うが、原料の区間があると Forward は作れない（§4.3 の 12）。記録を足すか、InBound のリードタイムの分の週を能力 0 とするかは未決（保護対象コア。Owner は今は記録だけ、2026-10-26） |
| Cookie の CVS・soysauce の卸価格 | 仮の値（各モデルの README に根拠と損益分岐） |
