# Request Letter：BS-SEAF 化粧品の適用実験 — 第4段階（試行）：調査と基準ケースの写し

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-25）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `889e0cb`。着手時の SHA を報告書に記録する）
- 前提：`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.2.md`（以下「設計書」）、歩留まり Part A（`889e0cb`、`docs/development/WOM_YieldRate_PartA_Report.md`）
- 種別：**コードを変えない試行**。`wom/`・`tools/`・`tests/`・`data/sample/` は変えない。モデルと試行の道具は `output/bsseaf_cosmetics/` に置く（git の対象外）。コードを変えないと進めない所が見つかったら、そこで止めて報告する。
- テスト：コードを変えないので回さない。

---

## 0. この依頼の位置づけ

BS-SEAF（Self-Evolving Modeling Loop）の第4段階「試行」である。正式なモデル（`data/sample/`）は作らず、写しで動かして結果を比べる（お米の 2025 年産と同じ進め方）。採用するかどうか、`data/sample/` に入れるかは、結果を見て大杉さんが決める（第5・6段階）。

この実験の目的は化粧品のモデルを完成させることではなく、**BS-SEAF の手順が新しい業務に使えるかを確かめること**である。そのため、作ったモデルと同じくらい、**「設計書の Mapping のとおりに表せたか、どこで違ったか、どの既存知識を使ったか」の記録**を重く見る（§4）。設計書と違う結果が出たときは、設計書に合わせてモデルや値を調整せず、違いとして報告する。

## 1. Part 0：先に調べること（コードを読むだけ）

| # | 調べること | 設計書 |
|---|---|---|
| Q1 | identity の計画で、MOM の `_actual_ship`（Forward の実出荷）に、市場の Lot_ID と同じ ID が出荷週ごとに入っているか。pull の MOM と push の MOM の両方について | §3.3 Q1 |
| Q2 | Lot_ID ごとに「工場（MOM）の出荷週」と「市場（leaf_out）の出荷週」を対にして取り出す方法。段階 D の出荷の記録（`wom/valuechain/records.py`）、LOVEM（`tools.lovem_observe`）、headless の木から直接、のどれが向くか。どれを残存期間の判定（§3.3）の入力にするのがよいか、理由とともに | §3.3 Q2 |
| Q3 | Cookie-jp-2026 を雛形にして §2 のモデルを作るとき、追加・削除するファイル。Cookie の決めごと（leaf_out の `region` 列、`demand_forecast.csv` の `region` の値、MOM の `lt_wks`）が化粧品でもそのまま使えるか | §3.3 Q3 |
| Q5 | **supply point に作り置きの在庫が現れる理由**（歩留まりの試行 T2・T3 で `SP_Cookie_Local` の I が最大 6,900 lot）。どのコードの経路で supply point の I に lot が残るのか。作り置きの lot は、そのとき MOM の `_actual_ship` に記録済みか（＝工場を出た扱いか）、それとも MOM の I にいる扱いか | Start Here §7 |

**Q5 は調べるだけで、直さない。** 残存期間の判定は「工場の出荷週」を起点にするので（設計書 §3.2）、作り置きが supply point にいる間を「工場を出た後の滞留」として数えられるかどうかで、判定の意味が変わる。調べた結果を、§3.3 の判定に当てはめるとどうなるかまで書く。

## 2. Part 1：基準ケースの写しを作る

`output/bsseaf_cosmetics/B0/` に、設計書 v0.2 の基準ケース（§1・§2、§6 の決定 D2〜D5）のモデルを作る。Cookie-jp-2026 のフォルダを写して書き換えてよい。

### 2.1 木（2 SKU とも同じ形。Cookie と同じく SKU ごとにノードの行を持つ）

```
InBound : Materials_JP（leaf_in） → Factory_JP（mom、yield_rate 0.97）
OutBound: SP_<SKU>（supply_point）
            → WH_JP_Released（dad、判定済み倉庫・輸出前、lt_wks 1 ＝ 判定の期間）
              → DC_SG（dad、lt_wks 2 ＝ 海上）
                → SG_Store（leaf_out、直営店、lt_wks 1）
                → SG_EC（leaf_out、公式 EC、lt_wks 1）
                → SG_Distributor（leaf_out、代理店、lt_wks 1）
```

- SKU：`COS_Serum`（美容液）、`COS_Cream`（クリーム）。
- `Factory_JP` の行に `yield_rate`＝0.97（設計書 A10）。ほかの行は空欄。
- `parent_node` が空の MOM の `lt_wks` は使われないので置かない（`CLAUDE.md` 2026-08-20）。`Materials_JP` の `lt_wks` は 1。
- `ss_days`・`buffering_stock_flag`・`init_stock_days` は 0（基準ケースでは安全在庫を置かない。開店時在庫は warmup の先行生産で作る。設計書 COS-R06）。
- 名前は役割の分かる一般名（実在の企業・ブランドの名前は使わない。`tests/test_no_real_names.py` の規則）。

### 2.2 計画の設定

| ファイル | 中身 |
|---|---|
| `planning_config.csv` | `warmup_lt`＝17、`lot_flow_mode`＝identity、`cpu_size`＝24（1 lot＝24 個、A1）、`recommended_plugins`＝Cookie と同じ組 |
| `vc_config.csv` | `report_start`＝2027-W01 |
| `demand_forecast.csv` | 2027-W01〜2029-W52。§2.3 |
| `capacity_plan.csv` | `Factory_JP` だけ、計画の全週（warmup の週を含む）。§2.4 |
| `node_master.csv` | 座標は一般的な地点（日本の工場・日本の港の倉庫・シンガポールの DC・シンガポールの 3 チャネル）。`node_id` は木の名前と同じ |
| `vc_entity.csv` | 日本本社（group、JPY）、シンガポール販社（group、SGD）、外部の供給者（日本）、代理店（`external_channel`、SGD） |
| `vc_node_assignment.csv` | `SG_Store`＝own、`SG_EC`＝online、`SG_Distributor`＝external（代理店の法人）。日本のノードは日本本社、`DC_SG`・`SG_Store`・`SG_EC` はシンガポール販社 |

金額（価格・原価・為替・関税）は**置かない**（設計書 A11。この試行は数量の意味だけを見る）。PPC・Value Chain が見本の値で動く、未評価になる、止まる、のどれになるかを報告する（金額の数字そのものは評価しない）。Cookie から写した `ppc_*.csv`・`vc_price_rule.csv` は消すか空にし、どうしたかを書く。

### 2.3 需要（lot／週、設計書 A7・A8）

| SKU | チャネル | 販売開始 | 立ち上げ 13 週 | 定常 |
|---|---|---|---|---|
| COS_Serum | SG_Store | 2027-W14 | 2 | 4 |
| COS_Serum | SG_EC | 2027-W01 | 2 | 3 |
| COS_Serum | SG_Distributor | 2027-W01 | 3 | 6 |
| COS_Cream | SG_Store | 2027-W14 | 2 | 3 |
| COS_Cream | SG_EC | 2027-W01 | 1 | 2 |
| COS_Cream | SG_Distributor | 2027-W01 | 3 | 5 |

- 立ち上げは販売開始の週から 13 週（定常の 50% を切り上げた値）。季節変動は置かない。
- `SG_Store` の 2027-W01〜W13 は 0 の行を置く（行を抜かさない）。

### 2.4 工場の能力（設計書 A9、D2：SKU ごと、設備を共用しない）

| SKU | ピーク週の需要 | `max_supply`（cap_hard） | `cap_soft` |
|---|---|---|---|
| COS_Serum | 13 | 17（＝ceil（13 ÷ 0.97 × 1.2）） | 14（＝ceil（13 ÷ 0.97）） |
| COS_Cream | 10 | 13（＝ceil（10 ÷ 0.97 × 1.2）） | 11（＝ceil（10 ÷ 0.97）） |

- 能力は**物理の投入の能力**で書く。良品の上限は、エンジンが floor（能力 × 0.97）で作る（Serum：hard 16・soft 13、Cream：hard 12・soft 10）。
- `demand_envelope` は既定（hard）。cap_soft は記録だけになる（`cap_soft_violation` の件数を報告する）。

### 2.5 参考の写し

| 写し | 違い | 目的 |
|---|---|---|
| B0 | 上のとおり | 基準ケース |
| B1 | `Factory_JP` の `yield_rate` を空欄（1.0）にする。ほかは B0 と同じ | 歩留まりがこの基準ケースで効いているかを切り分ける |

## 3. Part 2：回して確かめる

headless（`python -m tools.run_headless_from_folder --model-dir output\bsseaf_cosmetics\B0`、推奨の組）と Flow Check で回し、設計書 §4 の検証条件を確かめる。V10 は Part A で確認済みなので不要。

| ID | 確かめること | 期待 |
|---|---|---|
| V01 | Flow Check の表 1：全ノードの数量の保存 | 全ノード OK |
| V02 | `SG_Store` の 2027-W14 より前の実出荷 | 0 |
| V03 | 開店時（2027-W14 の直前）の `DC_SG`・`WH_JP_Released` の在庫が、すべて需要の Lot_ID 付き | 出どころの無い lot が 0 |
| V04 | 残存期間の判定（下の §3.1） | 測った値を報告する（基準ケースでは判定の上限を入れないので、合否ではなく分布を見る） |
| V05 | 全 lot が `WH_JP_Released` を通り、工場からの区間が 1 週 | 全 lot |
| V06 | `Factory_JP` の週の P の最大 | Serum 16 以下、Cream 12 以下（floor（cap_hard × 0.97）） |
| V07 | チャネル別の当週出荷・遅配・期末注文残（Flow Check の表 2、報告期間） | 値を報告する |
| V08 | Value Chain の法人・チャネルの区分（own・online・external） | 意図どおり（Value Chain が金額の無いまま動かない場合は、マスターの読み込みで区分を確かめた結果でよい） |
| V09 | 実名が無い | `output/` も含めて、§2.1 の規則で名前を付けたことを書く |

あわせて、**直販比率（数量基準、設計書 D3）**を報告する：報告期間の実出荷 lot 数で、（`SG_Store`＋`SG_EC`）÷（3 チャネルの合計）。SKU 別と合計。

### 3.1 残存期間の判定（V04）

設計書 §3.2（大杉さんの決定 D4）のとおりに、写しの外の小さな道具（`output/bsseaf_cosmetics/shelf_life_check.py` など）で数える。**リポジトリには入れない**（入れるかは結果を見て大杉さんが決める）。

- Lot_ID ごとに、
  - `w_ship`：工場（`Factory_JP`）の実出荷週
  - `w_due`：`max`（Lot_ID の需要週〔`LotIDGenerator.parse()` で読む〕、市場の実出荷週）
  - 滞留 ＝ `w_due − w_ship`（週）。**週の差は計画の週の番号で数える**（ISO の週ラベルを引き算しない）
- 報告する値：滞留の最小・最大・分布（週ごとの lot 数）、52 週（設計書 A6 の許容滞留）を超える lot の数、SKU 別・チャネル別。
- Q5 の結果、作り置きが supply point にいる間を滞留に数えるかで値が変わる場合は、両方の数え方で出す。
- 遅配・期末注文残の lot の扱い（期末注文残の lot は市場の実出荷が無い）も書く。

## 4. Part 3：BS-SEAF の記録

報告書の中で、次の表を埋める。これがこの実験の主な成果物である。

### 4.1 Mapping の実際

設計書 §3.1 の各ルール（COS-R01〜R13）について：

| ID | 設計書の表し方 | 実際の表し方 | 設計書どおりか（違えば何が違ったか） | 使った既存の知識（設計書 §2.4 の行、または新たに見つけたもの） |
|---|---|---|---|---|

### 4.2 設計書に無かったこと

- 試行で初めて分かったこと（例：予想外の在庫・注文残、能力の効き方、ファイルの規則）。
- 設計書の仮定・Mapping のうち、直す必要があるもの。
- Data／Parameter で足りなかったところ（あれば）。Core の変更が要りそうな所は、変えずに報告する。

### 4.3 手間の記録

- モデルを作るのにかかった手間（ファイルの数、雛形から変えた行の数、迷った所）。後で変更課題①〜⑤（設計書 §5）を与えたときに、知識の再利用で手間がどれだけ減ったかを比べるための基準にする。

## 5. 報告書

`docs/development/WOM_BSSEAF_Cosmetics_Trial_Report.md` に次を書く：

1. 着手時の SHA。コードを変えていないこと（`git status` で `wom/`・`tools/`・`tests/`・`data/sample/` に変更が無い）。
2. Part 0 の Q1〜Q3・Q5 の結果。
3. 作った写し（B0・B1）のファイル一覧と、§2 から外れた所（あれば理由）。
4. Part 2 の V01〜V09 の結果、直販比率、§3.1 の残存期間の判定の結果。B0 と B1 の違い。
5. Part 3 の表。
6. 次の段階（第5段階：大杉さんの判断）で決めてほしいこと。

## 6. commit

- この依頼書（`docs(request): …`）と報告書を**別の commit** にする。`output/` は commit しない。git は大杉さんが Windows で行う。commit メッセージの下書きは `commit_msg*.txt`。
