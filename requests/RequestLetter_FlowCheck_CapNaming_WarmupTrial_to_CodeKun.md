# Request Letter：流れの見える化（Flow Check）、cap_hard の名前の整理、warmup の試行

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`（着手時の SHA を報告書に記録する。起草時の先頭は `558d950`）
- 種別：GUI・記録の追加（Part 1・2）と、コピーしたモデルでの試行（Part 3）。計画の動きは変えない。
- 前提：
  - 決定記録 `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md`（v1.2）
  - `docs/development/WOM_LotIdentityFlow_Report.md`（§5.6 期末注文残の原因、§7 S4）
  - `docs/development/WOM_LOVEM_StageC_Report.md`（Astra君の独立照合。§5・§6）
  - `docs/design/planning_warmup_and_reporting_horizon.md`（§5・§13）、`wom/engine/warmup.py`

---

## 0. 背景と順番

LotIdentityFlow（既定 identity）で、上流の不足が市場と金額に届くようになりました。大杉さんが `python -m main` で確かめたところ、次の 2 つが分かりました。

- **画面から実出荷が読めない。** PSI の S は「そのノードへの要求（Demand Position）」なのに、凡例が「S: Sales/Fulfilled」になっていて、実出荷と誤読しやすい。実出荷は I と P から逆算するしかない。ネットワーク全体で流れが保存されているかも、人の目では確かめられない。
- **期末注文残の大半は「計画期間の端（開始）」である。** 期首在庫が無く、立ち上がり期の需要に供給が間に合わない（LotIdentityFlow 報告書 §5.6）。受け皿として、既存の warmup（`planning_config.csv` の `warmup_lt`）がある。identity で期末注文残が 0 だった soysauce-jpy-2027 は、`warmup_lt=26` を持っている。

本書は、次の順で進めます。identity の golden を作るのは、Part 3 の結果を見て、どのモデルに warmup を入れるかを大杉さんが決めてからにします（本書では作らない）。

1. Part 1：画面の見える化（S の名前、実出荷の列、Flow Check 表）
2. Part 2：cap_hard の名前の整理
3. Part 3：warmup の試行（モデルのコピーで）

## Part 1　画面の見える化

### V1　S の名前を「要求」に改める（誤読の落とし穴をまとめて潰す）

- PSI Chart の凡例 `S: Sales/Fulfilled`（`wom/gui/app.py` の 2 か所）を `S: Request (Demand Position)` に改める。
- `wom/model/plan_node.py` の S の説明コメント（`Sales / Fulfilled shipment`）も同じ意味に改める。
- ほかにも、S を「販売」「充足」「出荷」と説明している画面の文言・コメント・docstring・文書があれば、**まとめて**直す（`grep` で洗い出し、直した箇所を一覧にして報告する）。
- 意味の説明：S は、そのノードの週 w に置かれた要求の Lot_ID である（決定記録 §1.1）。実際に出荷した Lot_ID は `node._actual_ship[w]` にある。legacy の市場 leaf では両者が一致していたが、identity では一致しない。

### V2　PSI List に実出荷の列と合計行を加える

- PSI List の S の右に `Ship`（実出荷＝`len(node._actual_ship[w])`）の列を加える。`_actual_ship` が無いとき（旧い呼び出し）は `—` を表示する。
- 表の最下行に合計行（`Σ`）を加える。
  - S・Ship・P：期間の合計
  - I・CO：期間の最後の週の値（合計には意味がないので、列見出しに「期末」と分かるように書く）
- PSI Chart にも、実出荷を細い線（S の棒と区別できる色）で加える。
- Demand レイヤーの表示では Ship 列は出さない（実出荷は Supply 側の記録）。
- Export to CSV／Excel に Ship 列が含まれるようにする。

### V3　Flow Check 表（ネットワーク全体の流れの整合性）

**目的**：人が計算しなくても、「物が保存されているか」「親が出荷した物が子に届いているか」「市場の需要がどう終わったか」を、1 枚の表で確かめられるようにする。Astra君の段階 C の照合（Q02〜Q05）の要点を、どのモデルでも画面で見られるようにするもの。

**計算の置き場所**：Tk に依存しない関数として作る（例：`wom/engine/flow_check.py`。名前は任せる）。入力は計画後の SCTree と ForwardPlanResult。GUI・headless・テストから同じ関数を呼ぶ。計画の結果は変えない（読むだけ）。

**必要な記録**：親から子への到着を辺ごとに数えるため、`_propagate_to_child`・`_propagate_to_parent` で届けた件数を、辺（親・子・出荷週・到着週）ごとに ForwardPlanResult に**記録だけ**する（LotIdentityFlow の `ot_in_transit_at_end` と同じ扱い。legacy の計画は1ビットも変えない）。

**表 1：ノードごと**（製品ごと。単位は lot。cpu_size を掛けた数量の列も付ける）

| 列 | 内容 |
|---|---|
| product / node / node_type / plan_mode | |
| 期首 I | 計画開始時の在庫の件数 |
| 入庫 Σ | 期間中の P の合計 |
| 実出荷 Σ | 期間中の `_actual_ship` の合計 |
| 期末 I | 最終週の I |
| 保存差 | 期首 I ＋ 入庫 Σ − 実出荷 Σ − 期末 I（0 が正） |
| 上流からの出荷 Σ | 供給元（Outbound は親、Inbound は子）がこのノードに向けて出荷した件数 |
| 期末の輸送中 | そのうち、到着が計画期間の外になった件数 |
| 到着差 | 上流からの出荷 Σ − 期末の輸送中 − 入庫 Σ（0 が正） |
| 期末 CO | 最終週の CO |
| 判定 | OK／NG／対象外（理由） |

- **対象外**にするノードと理由の表示：
  - Kitting の組立ノード（部材から完成品への変換。到着差は1対1で比べられない）→「対象外（Kitting）」
  - P を需要 P のコピーで作るノード（Inbound のデカップリング点など、決定記録 §6。legacy では Outbound の下流も）→「対象外（P はコピー。出所なし）」と表示し、到着差の欄には差の値をそのまま出す（legacy の不整合が見えるように）
  - rice の収穫在庫のように、需要に紐づかない ID で作る供給 →「対象外（需要に無い ID）」
  - push_sub（要求なしで上流へ送る）→ 保存差だけを判定する
- 判定の NG は、赤などで目立たせる。

**表 2：市場（leaf_out）の需要の行き先**（製品ごと、最下段にモデル全体）

| 列 | 内容 |
|---|---|
| 需要 | 市場 leaf の S に置かれた Lot_ID の数 |
| 当週出荷 | 要求週に同じ ID を出荷した数 |
| 遅配 | 要求週より後に同じ ID を出荷した数 |
| 期末注文残 | 期末まで出荷されなかった数 |
| 検算 | 需要 −（当週出荷＋遅配＋期末注文残）（0 が正） |

**置き場所**：Network タブの PSI Chart／PSI List と並ぶサブタブ「Flow Check」を推奨（判断は任せる）。headless では `output/` の下に CSV を書き出す（ファイル名は任せる）。

**受入**：

- ev-thailand-2026 の identity で、表 2 が「需要 63,240 ＝ 当週出荷 58,220 ＋ 遅配 0 ＋ 期末注文残 5,020」になり、Astra君の段階 C（`docs/development/lovem/stageC/`）の数字と一致する。表 1 の判定はすべて OK か対象外。
- 同じモデルの legacy で、Outbound の下流（市場 leaf）が「対象外（P はコピー）」になり、到着差に値が出る（段階 C で見つかった 5,020 と整合するか確かめる）。
- 15 ケース（LotIdentityFlow と同じ）の identity で、表 1 に NG が 1 件も無い。NG があれば、原因を調べて報告する（直さずに報告でよい）。
- Cookie-jp-2026 の identity で、Cookie_Import の DC_Import_Buffer と DC_Import_Main の実出荷 Σ が、どちらも 67,274 になる（LotIdentityFlow 報告書 §5.3）。

## Part 2　cap_hard の名前の整理

identity では、cap_hard を超えた lot は封印（seal）されず、ID を保ったまま翌週へ**繰り延べ**られる（決定記録 D4）。今の `cap_hard_sealed` は、identity では「のべ lot 週」を数えており、legacy の「封印した lot の数」と意味が違う（LotIdentityFlow 報告書 §7 S4）。名前が同じだと誤読するので分ける。

- identity では、次の 2 つを記録する。
  - `cap_hard_deferred_lots`：繰り延べを受けた lot の数（重複なし）
  - `cap_hard_deferred_lot_weeks`：繰り延べの のべ lot 週（待ちの総量）
- `cap_hard_sealed` は legacy だけで使う。identity では 0 のままにする（加算しない）。
- headless のスナップショット：legacy のときは今のまま（既存 golden とバイト一致させる）。identity のときだけ、`forward` に上の 2 つを書き、`cap_hard_sealed` は書かない。
- 画面・ログ・`tools/sweep_flags.py`・`tools/probe_composite_baseline.py`・LOVEM の observer・`DATA_DICTIONARY.md` など、`cap_hard_sealed`／「封印」を表示・説明している箇所を**まとめて**洗い出し、identity のときは「繰り延べ」と表示する。直した箇所を一覧にして報告する。

## Part 3　warmup の試行（モデルのコピーで）

### 3.1 目的

期末注文残のうち、どれだけが warmup（計画の開始の前倒し）で解消するかを、モデルごと・原因ごとに測る。大杉さんが、どのモデルに `warmup_lt` を入れるかを決めるための材料にする。

### 3.2 やり方

- `data/sample/` の原本は**変更しない**。warmup は CSV に助走週の行を書き込むので、試行はモデルのフォルダのコピー（例：`output/warmup_trial/<model>__w<N>/`）で行う。
- 方式は identity。
- 対象と条件：

| モデル | 条件 | 見たいこと |
|---|---|---|
| Cookie-jp-2026 | `warmup_lt` を 3 通り（設計書 §13.1 の考え方で求めた必要週数、その半分、その 2 倍程度） | 期末注文残 14,172（開始端 12,784、能力 1,388）のうち、どれが消えるか |
| ev-thailand-2026 | 同上 | 期末注文残 5,020 のうち、どれが消えるか。とくに、段階 C で原因未確認とされた 200 件（Factory_Import_CN への要求週 W04・W05、部材の必要出荷週が期間内なのに供給が無い）が消えるか |
| soysauce-jpy-2027（対照） | `warmup_lt=0`（今の 26 を外す） | warmup を外すと期末注文残が現れるか。「warmup が効いている」ことの確認 |

- 必要週数の求め方（§13.1）：ノードの LT、安全在庫（`ss_days`）、初期在庫（`init_stock_days`）、push の lead time を、市場から上流へたどって合計する。モデルごとの計算の内訳を報告書に書く。

### 3.3 測るもの（条件ごと）

- 表 2（市場の需要の行き先）：需要・当週出荷・遅配・期末注文残
- 期末注文残の原因の分類（LotIdentityFlow 報告書 §5.6 と同じ方法）：能力・休業・計画期間の端（開始）・ID の照合不能・経路の未割当・計画期間の端（終わり）・未確認
- Flow Check 表 1 の NG の有無
- PPC の売上・粗利。warmup の助走週の扱い（助走週の生産・在庫の費用が PPC に入るか、売上の認識週が実需要の期間に入っているか）を、設計書 §9（Engine・Chart・PPC の責任分離）と照らして報告する。
- 実行時間

### 3.4 ev-thailand の 200 件

warmup で消えない場合は、原因を調べて報告する。**直さないでください。** 候補は、push_sub（Components_CN）の Mode 4 の生産計画が、立ち上がり期の ID を作らないこと（LotIdentityFlow 報告書 §7 S7）。どのコードのどの条件で、その ID が生成・配置されないのかを、証拠（ノード・週・ID）付きで示す。原因を断定できない場合は「未確認」と書く。

### 3.5 提案

測った結果から、モデルごとに `warmup_lt` の推奨値（入れない、を含む）と、その理由を表にする。**原本の `planning_config.csv` は書き換えない。** 決めるのは大杉さんです。

## 守ること

- legacy の計画は1ビットも変えない（Part 1・2 で加えるのは記録と表示だけ）。13 golden が legacy で完全一致すること。
- golden は再生成しない。`data/sample/` の原本を変更しない。commit・push はしない。
- 誤読を招く名前・説明は、関連する箇所をまとめて直し、一覧にして報告する。
- 副作用が出ても実装は止めずに最後まで行い、報告書に書く。
- 本書どおりにできないコードの事実を見つけた場合も、止めずに意図に最も近い形で実装し、変えた点と理由を報告する。

## 受入条件（まとめ）

1. 全テスト緑（今の件数＋新規）。13 golden が legacy で完全一致。
2. V3 の受入（ev-thailand・Cookie・15 ケース）。
3. Part 2：identity のスナップショットに `cap_hard_deferred_lots`・`cap_hard_deferred_lot_weeks` が載り、legacy のスナップショットは変わらない。
4. Part 3：3 モデルの条件ごとの結果表と、`warmup_lt` の推奨の表。

## 成果物

1. コードの変更（Part 1・2）とテスト（Flow Check の計算を小さな合成ツリーで確かめるもの、S・Ship の表示、cap_hard の記録）
2. 報告書 `docs/development/WOM_FlowCheck_WarmupTrial_Report.md`
   - Part 1・2 の変更点、直した文言の一覧
   - Flow Check の受入結果（ev-thailand の legacy と identity の表 1・表 2 を載せる）
   - Part 3 の結果表、原因の分類、ev-thailand の 200 件の調査、`warmup_lt` の推奨
   - 副作用、本書と変えた点
   - 大杉さんが `python -m main` で確かめる手順（Flow Check タブ、PSI List の Ship 列）
3. Flow Check 表の画面のスクリーンショット（ev-thailand の identity と legacy、Cookie の identity）
