# warmup_lt を暦の区切りでそろえ、identity の golden を作る　報告

- 依頼書：`requests/RequestLetter_Warmup17_IdentityGolden_to_CodeKun.md`
- 前提：決定記録 `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md` v1.3 の D5・D7、`docs/development/WOM_FlowCheck_WarmupTrial_Report.md` §5
- 実装：Code君（Claude Code, Windows）、2026-09-30
- 作業フォルダ／ブランチ：`wom-v1r5m1_cap_trial`
- **着手時の SHA：`988f935`**（Flow Check の commit は `7604f64`）
- **commit・push はしていない。** golden は作り直した（大杉さんの差分の確認待ち）。
- **改訂（同日）**：初版の報告への大杉さんの判断（oil は 26、落ちた 3 件のテストは直す、iphone と alloc はそのまま）を反映した。反映した箇所は §0・§2.2・§3.2・§5 S4・S8・§6。
- **エンジン・GUI のコードは変えていない。** 変えたのは、サンプルの入力（`planning_config.csv` と warmup の生成行）、golden、`tests/test_golden.py`（legacy のフォルダを読む部分）と、大杉さんの判断を受けて直した既存のテスト 2 本（`tests/test_lovem_observer.py`・`tests/test_stage3a1_stockyard.py`。§5 S8）だけ。

---

## 0. 要約

1. **warmup_lt を決めて、原本の `planning_config.csv` に書いた**（依頼書 2 の手順：17・26・52 のうち、期末注文残がいちばん少なくなる値の最小のもの）。

   | 値 | モデル |
   |---|---|
   | 17 | ev-thailand-2026、Cookie-jp-2026、apparel-global-2028-2029、ev-europe-2026、smartx-2027-2029、apparel-us-2026（52 から）、bom-test-2026（12 から）、ev-thailand-2026_update（16 から） |
   | 26 | soysauce-eu-2027、soysauce-us-2027、**oil-global-2027**（新規）、soysauce-jpy-2027・soysauce-jpy-2027-alloc（今のまま）。oil は、手順では 52 になる（26 では 29 件が残る）が、**大杉さんの判断で 26 にした**（§2.2） |
   | **決められない** | **iphone_global**（`capacity_plan.csv` に `node_name` 列が無く、warmup の助走行の生成がエラーで止まる。コードを変えない約束なので、warmup なしのまま。§2.3） |
   | 対象外 | rice-japan-2027-2028（legacy のまま、入力は変えていない）、india-ghee-2026（試行だけ。原本は変えていない） |

2. **golden を作り直した**：13 件（rice は legacy、ほかの 12 件は identity）と、legacy の golden 3 件（`tests/golden/legacy/`：Cookie・ev-thailand・soysauce-jpy）。rice の golden は 1 バイトも変わっていない。
3. **warmup を入れた identity の 11 モデルのうち 10 モデルは、期末注文残が 0 になり、PPC の売上・粗利が、これまでの legacy の golden と同じ値になった**（§3.2）。残るのは 2 モデル：oil は 29 件（すべて Gasoline_Local_RedSea。§2.2）、iphone は 97,834 件（能力 65,274、計画期間の端（開始）32,560）。
4. **Flow Check**：13 モデルの表 1 の NG は 0 件、表 2 の検算もすべて 0。ev-thailand-2026_update（golden の対象外）は、既知の NG が 1 件（Factory_Local_TH の保存差 52,400）のまま。
5. テスト：**593 passed／3 skipped（失敗 0）**（全 596 件、8 分 59 秒）。golden の 13 件、legacy の golden の 3 件、直した 3 件のテストを含む。初版で落ちていた 3 件は、大杉さんの判断どおりに直した（§5 S8）。

---

## 1. 変更したもの

| 種類 | 内容 |
|---|---|
| 入力（新規） | `planning_config.csv` を 8 モデルに新しく作った：Cookie-jp-2026・ev-thailand-2026・apparel-global-2028-2029・ev-europe-2026・smartx-2027-2029（`warmup_lt,17`）、soysauce-eu-2027・soysauce-us-2027・oil-global-2027（`26`）。書式は `key,value` と LF |
| 入力（値の変更） | apparel-us-2026（52 → 17）、bom-test-2026（12 → 17）、ev-thailand-2026_update（16 → 17）。ほかのキー（`cpu_size`・`planning_start`）と改行の書式はそのまま |
| 入力（生成行） | 上の 11 モデルの `demand_forecast.csv`・`capacity_plan.csv` に、`materialize_warmup` が助走週の行を書いた（§1.1） |
| golden | `tests/golden/*.json` の 12 件（rice 以外）を作り直した。`tests/golden/legacy/*.json` を 3 件、新しく作った |
| テスト（判断を受けて直した分） | `tests/test_stage3a1_stockyard.py`：ev-europe の 2 件の期待値を書き換えた。`tests/test_lovem_observer.py`：`test_se2_168_is_reproduced` を、warmup を入れない入力のコピーで実行する形に変えた（§5 S8） |
| テスト | `tests/test_golden.py`：比べ方を関数 `_check_golden` にまとめ、`test_legacy_golden_matches` を加えた。`tests/golden/legacy/` の golden は、`planning_config.csv` の指定によらず、必ず legacy で実行して比べる |
| 変えていないもの | エンジン・GUI のコード。rice・soysauce-jpy-2027・soysauce-jpy-2027-alloc・iphone_global・india-ghee-2026 の入力 |

### 1.1 生成行の範囲（どのファイルのどの範囲が生成行か）

生成行＝「最初の需要のある週」より前の週の行（`wom/engine/warmup.py` の規則）。需要は 0、能力は最初の実週の値のコピーで、`source` 欄が `warmup`。

| モデル | warmup_lt | ファイル | 全行数 | 生成行 | 生成行の週の範囲 | 週数 | 最初の需要のある週 |
|---|---:|---|---:|---:|---|---:|---|
| Cookie-jp-2026 | 17 | demand_forecast.csv | 726 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| Cookie-jp-2026 | 17 | capacity_plan.csv | 847 | 119 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| apparel-global-2028-2029 | 17 | demand_forecast.csv | 468 | 68 | 2027-W40〜2028-W04 | 17 | 2028-W05 |
| apparel-global-2028-2029 | 17 | capacity_plan.csv | 1638 | 238 | 2027-W40〜2028-W04 | 17 | 2028-W05 |
| apparel-us-2026 | 17 | demand_forecast.csv | 546 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| apparel-us-2026 | 17 | capacity_plan.csv | 636 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| bom-test-2026 | 17 | demand_forecast.csv | 37 | 17 | 2025-W36〜2025-W52 | 17 | 2026-W01 |
| bom-test-2026 | 17 | capacity_plan.csv | 36 | 34 | 2025-W36〜2025-W52 | 17 | 2026-W01 |
| ev-europe-2026 | 17 | demand_forecast.csv | 628 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| ev-europe-2026 | 17 | capacity_plan.csv | 1140 | 170 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| ev-thailand-2026 | 17 | demand_forecast.csv | 726 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| ev-thailand-2026 | 17 | capacity_plan.csv | 726 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| ev-thailand-2026_update | 17 | demand_forecast.csv | 726 | 102 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| ev-thailand-2026_update | 17 | capacity_plan.csv | 847 | 119 | 2025-W37〜2026-W01 | 17 | 2026-W02 |
| oil-global-2027 | 26 | demand_forecast.csv | 1798 | 390 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| oil-global-2027 | 26 | capacity_plan.csv | 1664 | 416 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| smartx-2027-2029 | 17 | demand_forecast.csv | 2268 | 153 | 2025-W36〜2025-W52 | 17 | 2026-W01 |
| smartx-2027-2029 | 17 | capacity_plan.csv | 2076 | 119 | 2025-W36〜2025-W52 | 17 | 2026-W01 |
| soysauce-eu-2027 | 26 | demand_forecast.csv | 780 | 156 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| soysauce-eu-2027 | 26 | capacity_plan.csv | 390 | 78 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| soysauce-us-2027 | 26 | demand_forecast.csv | 780 | 156 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| soysauce-us-2027 | 26 | capacity_plan.csv | 390 | 78 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| soysauce-jpy-2027（変更なし） | 26 | demand／capacity／operating_calendar | 780／390／130 | 156／78／26 | 2026-W28〜2026-W53 | 26 | 2027-W01 |
| soysauce-jpy-2027-alloc（変更なし） | 26 | 同上 | 780／390／130 | 156／78／26 | 2026-W28〜2026-W53 | 26 | 2027-W01 |

差分の読み方（`git diff --stat -- data/sample`：25 ファイル、2,572 行の追加、488 行の削除）：

- **追加だけのモデル**：Cookie・ev-thailand・smartx・soysauce-eu/us・oil・bom-test・ev_update（週数が増えた分）。
- **apparel-us（削除 420 行）**：warmup が 52 → 17 になり、助走行が 35 週分減った。
- **apparel-global（能力 56 行・需要 8 行の置き換え）**：§5 S2。
- **ev-europe（能力 1 行の削除）**：§5 S3。

---

## 2. warmup_lt の試行（モデル × 17・26・52、identity、コピーで実施）

`output/warmup_trial/<モデル>__w<N>/` のコピーで測った。期末注文残（件）と、残った分の原因を示す。

### 2.1 結果

| モデル | warmup なし | 17 | 26 | 52 | 選んだ値 |
|---|---:|---:|---:|---:|---|
| ev-thailand-2026 | 5,020 | **0** | 0 | 0 | 17 |
| Cookie-jp-2026 | 14,172 | **0** | 0 | 0 | 17 |
| apparel-global-2028-2029 | 7,244 | **0** | 0 | 0 | 17 |
| ev-europe-2026 | 3,720 | **0** | 0 | 0 | 17 |
| apparel-us-2026 | 33,076 | **0** | 0 | 0（今の値） | 17 |
| bom-test-2026 | 20 | **0** | 0 | 0 | 17（今は 12） |
| ev-thailand-2026_update | 3,581 | **0** | 0 | 0 | 17（今は 16） |
| smartx-2027-2029 | 16,888（遅配 16,073） | **0**（遅配 16,073） | 0（同） | 0（同） | 17 |
| soysauce-eu-2027 | 14,926 | 790 | **0** | 0 | 26 |
| soysauce-us-2027 | 14,750 | 701 | **0** | 0 | 26 |
| soysauce-jpy-2027 | 14,926 | 790 | **0**（今の値） | 0 | 26 のまま |
| oil-global-2027 | 14,042 | 74 | **29** | 0 | **26**（大杉さんの判断。手順では 52） |
| soysauce-jpy-2027-alloc（元の需要） | 43,046 | 31,384 | 25,210（今の値） | 7,374 | 26 のまま（依頼書の指定） |
| soysauce-jpy-2027-alloc（P_opt/800） | 27,129 | 15,467 | **9,293**（今の値） | **0** | — |
| india-ghee-2026（試行だけ） | 4,810 | 0 | 0 | 0 | 原本は 12 のまま |
| iphone_global | 97,834 | エラー | エラー | エラー | 決められない |

残った分の原因（件数の多い順）：

| モデル・条件 | 期末注文残 | 原因 |
|---|---:|---|
| soysauce-jpy-2027 w17 | 790 | 計画期間の端（開始）461／ID の照合不能 329（push の Mode 4 の立ち上がり。FlowCheck 報告書 §5.4 と同じ仕組み） |
| soysauce-eu-2027 w17 | 790 | 同上（461／329） |
| soysauce-us-2027 w17 | 701 | 計画期間の端（開始）395／ID の照合不能 306 |
| oil-global-2027 w17 | 74 | 能力 49／計画期間の端（開始）25 |
| oil-global-2027 w26 | 29 | 計画期間の端（開始）25／能力 4 |
| alloc（元の需要）w17 | 31,384 | 能力 26,582／開始端 4,116／ID の照合不能 686 |
| alloc（元の需要）w26 | 25,210 | 能力 20,408／開始端 4,116／ID の照合不能 686 |
| alloc（元の需要）w52 | 7,374 | 開始端 4,116／能力 2,572／ID の照合不能 686 |
| alloc（P_opt/800）w17 | 15,467 | 能力 10,665／開始端 4,116／ID の照合不能 686 |
| alloc（P_opt/800）w26 | 9,293 | 能力 4,491／開始端 4,116／ID の照合不能 686 |
| iphone_global（warmup なし） | 97,834 | 能力 65,274（SP_iPhone16 38,007・SP_iPhone15 27,267。Backward が MOM の能力で押し戻して第 0 週を越えた分）／計画期間の端（開始）32,560 |
| ev_update（warmup なし） | 3,581 | 開始端 3,330／ID の照合不能 210／能力 41 |

- 経路の未割当・終わりの端・休業・未確認は、どの条件でも 0 件。
- Flow Check の NG は、ev_update の既知の 1 件を除き、どの条件でも 0 件。
- 助走週の日付の PPC イベントは、どの条件でも 0 件。

### 2.2 oil-global-2027 は 26 にした（大杉さんの判断）と、残る 29 件の内訳

- 17 週では 74 件、26 週では 29 件が残り、52 週で 0 になる。手順（期末注文残がいちばん少ない値の最小）では 52 になるが、D7 の標準（17 週、足りなければ 26 週）に合わせて、**大杉さんの判断で 26 にした**。原本の `planning_config.csv` は `warmup_lt,26`、golden は 26 週の入力で作り直した。
- **残る 29 件は、すべて Gasoline_Local_RedSea（紅海の代替ルート）**。ほかの 7 製品は 0 件。

  | 市場 leaf | 需要 | 当週出荷 | 期末注文残 |
  |---|---:|---:|---:|
  | Retail_Local_R_KANTO | 246 | 246 | 0 |
  | Retail_Local_R_KANSAI | 124 | 115 | 9 |
  | Retail_Local_R_CHUBU | 124 | 104 | 20 |
  | 製品の合計 | 494 | 465 | **29** |

- 原因の内訳：

  | 原因 | 件数 | 止まった場所 | 例 |
  |---|---:|---|---|
  | 計画期間の端（開始） | 25 | Refinery_Local_R（mom） | `Gasoline_Local_RedSea:KANSAI:2028-W18:00002`（要求週 2028-W18。Backward が能力で前へ押し戻し、計画の開始より前に出た） |
  | 能力 | 4 | SP_Oil_Local_R（supply_point） | `Gasoline_Local_RedSea:CHUBU:2028-W25:00001`（要求週 2028-W25。計画の終わりの近くで、能力の順番が回ってこない） |

- なぜ残るか：この製品は、製油所の能力（Refinery_Local_R、5 lot／週）が、2027-W19 以降の需要（8 lot／週）を恒常的に下回るように作ってある（CLAUDE.md「Hormuz 海峡封鎖 vs Red Sea 代替ルート比較」：紅海ルートは正規ルートの約 6 割しか代替できない、という設定）。Backward は、能力を超えた分を前の週へ押し戻すので、助走が長いほど、助走週の能力で作り溜めできる。26 週の助走では、市場への当週出荷が 465 件、期末注文残が 29 件になった。52 週にすると 0 になる。（465 は市場の当週出荷の数であり、助走週の先行生産量や、実需要の開始時点の在庫量とは別の数である。）
- 3 つを分けて記録する（段階 C の Astra君の指摘による補足、2026-09-30）：
  - **観測結果**：warmup 26 週で、当週出荷 465、期末注文残 29。原因の分類は、計画期間の端（開始）25、能力 4。
  - **モデルの設定**：製油所の能力 5 lot／週に対して、需要 8 lot／週となる条件。
  - **業務上の解釈**：「モデルが意図した供給不足」が見えている、という説明。29 件すべてを、恒常的な能力不足だけに帰属させる意味ではない（25 件は分類上「開始端」）。52 週にして 0 にすると、この製品の物語（能力の制約で未充足が積み上がる）が画面から消える。
- 金額の注意：この製品の 1 lot はタンカー 1 隻分（約 27.1 億円）なので、**件数では 0.015% だが、売上では 786 億円（全体の 4.8%）**にあたる。新しい golden の売上は 1 兆 5,711 億円（これまでの legacy の golden は 1 兆 6,497 億円）、粗利は 5,523 億円（同 5,795 億円）、粗利率 35.16%（同 35.13%）。
- legacy は、この 29 件も出荷したことにしていた（warmup なしの legacy では、製油所の P は 335 しかないのに、市場では 494 を出荷）。identity では、作れた分だけを出荷する。

### 2.3 iphone_global は決められなかった

- `materialize_warmup` が、`capacity_plan.csv` の助走行を作るところで止まる。

  ```
  wom/engine/warmup.py, _build_warm_lines:
      si, ni, mi = _col(hf, "sku_id"), _col(hf, "node_name"), _col(hf, "max_supply")
  ValueError: 'node_name' is not in list
  ```

- iphone の `capacity_plan.csv` の見出しは `sku_id,region,week,max_supply,cap_pieces,source`（SKU 単位の古い書式）で、`node_name` 列が無い。ほかのモデルはすべて `node_name` 列を持つ。
- エンジンのコード（`warmup.py`）も、`planning_config.csv` と生成行以外の入力も変えない約束なので、iphone には warmup を入れていない。
- identity の golden は、warmup なしで作った。期末注文残 97,834 件（能力 65,274、開始端 32,560）が残った状態を固定している。
- 直すなら、(a) `warmup.py` を `node_name` 列の無い書式に対応させる、(b) iphone の `capacity_plan.csv` に `node_name` 列を加える、のどちらか。どちらも今回の範囲の外。
- なお、iphone の「能力」の 65,274 件は、warmup を入れても消えない見込み（Backward の MOM の能力の押し戻しによるもので、LotIdentityFlow 報告書 §5.6）。

### 2.4 soysauce-jpy-2027-alloc と 9,293 件

- alloc は能力を 800／週に絞ったモデルで、元の需要（100,501）に対して能力が足りない。warmup を延ばすほど、助走週に作り溜めできる分だけ期末注文残が減る（0 週 43,046 → 26 週 25,210 → 52 週 7,374）が、0 にはならない。依頼書の指定どおり 26 のままにした。
- **P_opt/800 の条件（能力に合わせた配分の需要 83,200）**
  - 26 週（今の値）：期末注文残 **9,293** 件（能力 4,491、開始端 4,116、ID の照合不能 686）。LotIdentityFlow 報告書 §5.2 と同じ値。
  - 17 週：15,467 件。
  - **52 週：0 件**。PPC の売上 5.486 億、粗利 1.650 億、粗利率 30.08%（legacy の値と同じ）。
  - つまり、9,293 件は「能力そのものが足りない」のではなく、「助走が 26 週では足りない」分である。52 週分を前倒しで作り溜めれば、配分どおりの需要をすべて満たせる。ただし、1 年分の先行生産が現実的かどうかは別の問題である。

---

## 3. golden の作り直し

### 3.1 作り方

- CLAUDE.md の手順どおり、headless の CLI（`python -m tools.run_headless_from_folder --model-dir data/sample/<モデル> --plugins <今の golden に記録されているプラグイン> --out tests/golden/<モデル>.json --quiet`）で作った。
- 方式は、各モデルの `planning_config.csv` のとおり（rice は legacy、ほかは identity）。identity の golden の `config` には `"lot_flow_mode": "identity"` が載り、`forward` は `cap_hard_deferred_lots`・`cap_hard_deferred_lot_weeks`・`cap_soft_violation_count` になる。
- legacy の golden 3 件は、**同じ入力（warmup を入れた後）**に `--lot-flow-mode legacy` を付けて作り、`tests/golden/legacy/` に置いた。

### 3.2 差分の確認資料（モデルごと）

市場＝需要＝当週出荷＋遅配＋期末注文残。列は「legacy（これまでの golden の入力）／identity で warmup なし／identity で warmup あり（新しい golden）」。

| モデル | warmup_lt 前→後 | 計画の開始・週数 前→後 | 市場（legacy）当週／残 | 市場（identity・warmup なし）当週／遅配／残 | 市場（新 golden）当週／遅配／残 |
|---|---|---|---|---|---|
| Cookie-jp-2026 | なし→17 | 2026-W02・104 → 2025-W37・121 | 141,990／0 | 127,818／0／14,172 | 141,990／0／0 |
| apparel-global-2028-2029 | なし→17 | 2028-W01・104 → 2027-W40・117 | 181,526／0 | 174,282／0／7,244 | 181,526／0／0 |
| apparel-us-2026 | 52→17 | 2025-W02・126 → 2025-W37・91 | 249,172／0 | 216,096／0／33,076 | 249,172／0／0 |
| bom-test-2026 | 12→17 | 2025-W41・32 → 2025-W36・37 | 100／0 | 80／0／20 | 100／0／0 |
| ev-europe-2026 | なし→17 | 2026-W02・88 → 2025-W37・105 | 53,140／0 | 49,420／0／3,720 | 53,140／0／0 |
| ev-thailand-2026 | なし→17 | 2026-W02・104 → 2025-W37・121 | 63,240／0 | 58,220／0／5,020 | 63,240／0／0 |
| iphone_global | なし→なし | 2027-W01・156（同じ） | 470,924／0 | 373,090／0／97,834 | 373,090／0／**97,834** |
| oil-global-2027 | なし→26 | 2027-W01・78 → 2026-W28・104 | 191,058／0 | 177,016／0／14,042 | 191,029／0／**29** |
| rice-japan-2027-2028 | なし（legacy） | 2026-W01・156（同じ） | 235,316／0 | （参考）0／142,914／92,402 | 235,316／0／0（legacy のまま） |
| smartx-2027-2029 | なし→17 | 2026-W01・261 → 2025-W36・278 | 709,811／0 | 676,850／16,073／16,888 | 693,738／**16,073**／0 |
| soysauce-eu-2027 | なし→26 | 2027-W01・104 → 2026-W28・130 | 100,501／0 | 85,575／0／14,926 | 100,501／0／0 |
| soysauce-jpy-2027 | 26→26 | 2026-W28・130（同じ） | 100,501／0 | 85,575／0／14,926 | 100,501／0／0 |
| soysauce-us-2027 | なし→26 | 2027-W01・104 → 2026-W28・130 | 100,500／0 | 85,750／0／14,750 | 100,500／0／0 |

PPC（売上／粗利／粗利率。通貨は各モデルの基準通貨）：

| モデル | これまでの golden（legacy） | identity・warmup なし | 新しい golden |
|---|---|---|---|
| Cookie-jp-2026 | 4,259,700,000／686,229,000／16.11% | 3,834,540,000／622,270,200／16.23% | 4,259,700,000／686,229,000／16.11% |
| apparel-global-2028-2029 | 10,387,986／3,994,720／38.46% | 9,989,391／3,836,841／38.41% | 10,387,986／3,994,720／38.46% |
| apparel-us-2026 | 12,209,428／5,182,155／42.44% | 10,588,704／4,499,182／42.49% | 12,209,428／5,182,155／42.44% |
| bom-test-2026 | 3,200,000／2,393,000／74.78% | 2,560,000／1,914,400／74.78% | 3,200,000／2,393,000／74.78% |
| ev-europe-2026 | 3,665.1 億／1,923.3 億／52.48% | 3,408.4 億／1,788.0 億／52.46% | 3,665.1 億／1,923.3 億／52.48% |
| ev-thailand-2026 | 3,191.2 億／1,802.9 億／56.50% | 2,929.9 億／1,657.4 億／56.57% | 3,191.2 億／1,802.9 億／56.50% |
| iphone_global | 713.3 兆／296.2 兆／41.53% | 583.3 兆／239.7 兆／41.09% | **583.3 兆／239.7 兆／41.09%** |
| oil-global-2027 | 1.650 兆／5,795 億／35.13% | 1.100 兆／3,847 億／34.99% | **1.571 兆／5,523 億／35.16%** |
| rice-japan-2027-2028 | 1,829,200,000／705,096,313／38.55% | （参考）1,122,629,300／425,038,777／37.86% | 1,829,200,000／705,096,313／38.55% |
| smartx-2027-2029 | 702,250,439／634,628,760／90.37% | 690,212,627／623,762,050／90.37% | 702,250,439／634,628,760／90.37% |
| soysauce-eu-2027 | 3,622,501／985,297／27.20% | 3,060,127／827,787／27.05% | 3,622,501／985,297／27.20% |
| soysauce-jpy-2027 | 614,988,400／172,459,616／28.04% | 530,632,900／148,853,881／28.05% | 614,988,400／172,459,616／28.04% |
| soysauce-us-2027 | 3,585,879／963,595／26.87% | 3,036,915／811,939／26.74% | 3,585,879／963,595／26.87% |

- **warmup を入れた identity の 10 モデルと rice は、新しい golden の PPC（売上・原価・粗利・粗利率・lot 数・trust event の件数）が、これまでの golden と一致する。** 違うのは oil（lot 数 1,408 → 1,399、trust event 742 → 733。§2.2）と iphone（lot 数 1,170 → 1,047、trust event 390 → 366）。
- これは、「legacy が例外 1・2 で覆い隠していた立ち上がり期の不足」を、identity では warmup で実際に作って埋めた、と読める。

`forward`・`backward`：

| モデル | forward（前 → 後） | backward |
|---|---|---|
| iphone_global | `cap_hard_sealed` 1,230 → `cap_hard_deferred_lots` 55,413・`lot_weeks` 55,413 | 変化なし（0） |
| smartx-2027-2029 | `cap_hard_sealed` 1,647 → `cap_hard_deferred_lots` 19,887・`lot_weeks` 19,887 | 変化なし（0） |
| rice-japan-2027-2028 | `cap_hard_sealed` 8,572（変化なし、legacy） | 変化なし（0） |
| ほかの 10 モデル | `cap_hard_sealed` 0 → `cap_hard_deferred_lots` 0・`lot_weeks` 0（項目名だけが変わる） | 変化なし（0） |

- `cap_soft_violation_count` と `cap_soft_envelope_count` は、どのモデルも 0 のまま。

psi（変わったノードの数／全ノードの数）と代表例：

| モデル | 変わった数 | 代表例（前 → 後） |
|---|---|---|
| Cookie-jp-2026 | 15／15 | DC_Import_Main：P 78,142・S 78,142・I_max 0 → P 78,930・S 78,930・I_max 788。DC_Import_Buffer：P 67,274・CO（のべ）905,258 → P 78,930・CO 0・I_max 2,364 |
| apparel-global-2028-2029 | 20／20 | DC_JP_Offshore：P・S 31,188 は同じ。週の並び（series_md5）だけが変わる（計画の開始が 13 週前へ出たため） |
| apparel-us-2026 | 112／112 | DC_Local_US（S1）：P・S 23,884、I_max 3,200 は同じ。週の並びだけが変わる（開始が 35 週後ろへ） |
| bom-test-2026 | 8／8 | Battery_Supply：P・S 100 は同じ。週の並びだけが変わる |
| ev-europe-2026 | 24／24 | Battery_HU：P・S 7,945 → 8,815。Battery_HU_Yard：I_sum 15,890 → 17,630 |
| ev-thailand-2026 | 14／14 | Components_CN：P・S 9,370 → 10,540。DC_EV_Import：P 9,370・S 10,386・CO（のべ）100,142 → P 10,540・S 10,540・CO 0 |
| iphone_global | 14／32 | Retail_AMER_i15：P 34,580・CO 0 → P 28,180・CO（のべ）944,000・I_max 400 |
| oil-global-2027 | 53／53 | Import_Hub_EU：P 11,320・S 11,757・CO（のべ）33,176 → P 12,093・S 12,093・CO 0。Refinery_Local_R：P 335・S 360 → P 465・S 490（29 件が残る） |
| rice-japan-2027-2028 | 0／24 | 変化なし |
| smartx-2027-2029 | 34／34 | AssemblyCN_g1：P 132,257・S 144,881・CO（のべ）3,225,909 → P 149,145・S 149,145・CO 0 |
| soysauce-eu-2027 | 15／15 | Bottling_Noda：P 85,575・S 92,537 → P 100,501・S 100,501。Brewing_Noda：P・S 85,575 → 100,501 |
| soysauce-jpy-2027 | 3／15 | DC_EU_RTM：I_max 0 → 1,050。DC_US_NY：I_max 0 → 525（デカップリング点の下流に安全在庫が見えるようになった。LotIdentityFlow 報告書 §7 S8） |
| soysauce-us-2027 | 15／15 | Bottling_Noda：P 85,750・S 92,712 → P 100,500・S 100,500 |

- 「前」は、これまでの golden（legacy・warmup なし）の値。warmup を入れると助走週が加わるので、合計が同じノードでも、週の並び（`series_md5`）が変わる。

Flow Check（新しい入力・各モデルの方式）：

| モデル | 表 1 の NG | 表 1 の対象外 | 表 2 の検算の不一致 |
|---|---:|---:|---:|
| Cookie・apparel-global・apparel-us・ev-thailand・iphone・oil・smartx・soysauce-eu／jpy／us | 0 | 0 | 0 |
| bom-test-2026 | 0 | 1（Kitting） | 0 |
| ev-europe-2026 | 0 | 2（Kitting） | 0 |
| rice-japan-2027-2028（legacy） | 0 | 18（P はコピー、需要に無い ID） | 0 |
| ev-thailand-2026_update（golden の対象外） | **1**（Factory_Local_TH の保存差 52,400。既知） | 0 | 0（需要 63,240 ＝ 当週出荷 63,240） |

### 3.3 legacy の golden（旧方式を守る網）

| モデル | 置き場所 | 入力 | 市場・PPC |
|---|---|---|---|
| Cookie-jp-2026 | `tests/golden/legacy/Cookie-jp-2026.json` | warmup_lt=17 を入れた後 | 粗利率 16.1%、`cap_hard_sealed` 0 |
| ev-thailand-2026 | `tests/golden/legacy/ev-thailand-2026.json` | 同上（17） | 粗利率 56.5%、`cap_hard_sealed` 0 |
| soysauce-jpy-2027 | `tests/golden/legacy/soysauce-jpy-2027.json` | 26（変更なし） | 粗利率 28.0%、trust event 32 |

- `config` に `lot_flow_mode` は載らない（legacy のため）。`forward` は `cap_hard_sealed`・`cap_soft_violation_count`。
- `test_legacy_golden_matches` が、同じ入力を legacy で実行した結果と比べる（受入条件 4）。
- 注意：soysauce-jpy の legacy の golden は、これまでの golden（legacy・同じ入力）と同じ内容になる。Cookie と ev-thailand は、warmup を入れた後の入力での legacy なので、これまでの golden とは計画の開始週が違う。

---

## 4. 受入条件

| 条件 | 結果 |
|---|---|
| 1. 全テスト緑（新しい golden 13 件＋legacy の golden 3 件） | **達成**：593 passed／3 skipped、失敗 0（初版では 3 件が落ちていた。§5 S8 のとおりに直した） |
| 2. identity の 12 モデルの期末注文残と原因の内訳 | 10 モデルは 0。oil は 29（計画期間の端（開始）25、能力 4。§2.2）。iphone は 97,834（能力 65,274、計画期間の端（開始）32,560）。§2.1・§3.2 |
| 3. Flow Check の NG は ev-thailand-2026_update の既知の 1 件だけ | そのとおり（§3.2） |
| 4. legacy の golden 3 件が、同じ入力の legacy の実行と一致 | 一致（`test_legacy_golden_matches` の 3 件が緑） |

---

## 5. 副作用（どこで／何が／なぜ／実機での見方／期待との差）

### S1　iphone_global に warmup を入れられない

- どこで：`wom/engine/warmup.py` の `_build_warm_lines`、`data/sample/iphone_global/capacity_plan.csv`。
- 何が：`planning_config.csv` に `warmup_lt` を書くと、計画の実行が `ValueError: 'node_name' is not in list` で止まる（§2.3）。
- なぜ：`capacity_plan.csv` が `node_name` 列の無い古い書式のため。
- 実機での見方：iphone のフォルダに `planning_config.csv`（`warmup_lt,17`）を置いて `python -m main` で読み込むと、期間の自動検出のところでエラーになるはず（GUI では確かめていない）。
- 期待との差：依頼書 2.1 は iphone を「手順 1〜3 で決める」としていたが、決められなかった。identity の golden は、期末注文残 97,834 件が残った状態を固定している。

### S2　apparel-global の原本の 4 週分の行が、生成行に置き換わった

- どこで：`data/sample/apparel-global-2028-2029/` の `demand_forecast.csv`（8 行）と `capacity_plan.csv`（56 行）。
- 何が：原本にあった 2028-W01〜W04 の行（需要 0 の、手作りの 4 週の助走）が消え、同じ週の生成行（`source=warmup`）に置き換わった。
- なぜ：`warmup.py` は「最初の需要のある週（2028-W05）より前の行はすべて生成行」と見なし、いったん取り除いてから作り直すため。
- 確かめたこと：置き換わった行の値（需要 0、能力の値）は、原本と全く同じ（能力 1,456 行・需要 416 行のすべてで差は 0）。変わったのは `source` 欄の文言だけ。
- 期待との差：warmup の 17 週は、2028-W05 から数える。元の計画の開始（2028-W01）から見ると、前へ 13 週出たことになる。

### S3　ev-europe の `capacity_plan.csv` の壊れた末尾行が消えた

- どこで：`data/sample/ev-europe-2026/capacity_plan.csv` の最終行。
- 何が：原本の末尾にあった `EVm,,,,,`（途中で切れた行）が、作り直しのときに落ちた。
- なぜ（推定）：過去に、ファイルの末尾が切り捨てられたときの残り（CLAUDE.md にある、Linux の bash での切り捨ての痕跡かもしれない）。`warmup.py` は、週の欄が空の行を「最初の需要のある週より前」と見なして取り除いた。
- 期待との差：計画には影響しない（もともと、ノードも週も無い行で、読み込み時に使われていなかった）。入力がきれいになった、という変化。

### S4　oil-global-2027 は 26 にし、期末注文残 29 件を残した

- §2.2。大杉さんの判断による。golden は、29 件（売上で 786 億円）が残った状態を固定している。

### S5　apparel-us-2026 の計画の開始が後ろへ動いた

- どこで：apparel-us-2026。
- 何が：warmup が 52 → 17 になり、計画の開始が 2025-W02 → 2025-W37、計画の週数が 126 → 91 になった。結果（市場の出荷・PPC）は変わらない。
- 実機での見方：CLAUDE.md には「apparel-us は GUI の Planning Config に Start Week=2025-W02／#Weeks=126 を直接入力」という運用の記録がある。今は `planning_config.csv` から自動で 2025-W37・91 週になるはずである。GUI での確認はしていない。
- 期待との差：依頼書の手順どおり（17 で足りたので、小さい方にそろえた）。

### S6　smartx-2027-2029 は、warmup を入れても遅配 16,073 件が残る

- どこで：smartx の市場 leaf。
- 何が：期末注文残は 0 になるが、要求週より後に出荷する lot が 16,073 件ある（17・26・52 のどれでも同じ）。
- なぜ（推定）：cap_hard を超えた lot の繰り延べ（`cap_hard_deferred_lots` 19,887）によるもので、warmup では変わらない。
- 期待との差：遅配は期末注文残ではないので、手順では 17 になる。

### S7　headless の CLI は、golden を作るときに Flow Check の CSV も書く

- 今回は `output/golden_regen/main/flow_check/<モデル>/` に書かせ、§3.2 の Flow Check の確認に使った（git の対象外）。

### S8　既存のテスト 3 件が落ちた（入力に warmup を入れたため）→ 大杉さんの判断で直した

- どこで：`tests/test_lovem_observer.py` の 1 件、`tests/test_stage3a1_stockyard.py` の 2 件。どれも、サンプルの実データ（ev-thailand-2026、ev-europe-2026）を実行し、**warmup の無い入力で出ていた「立ち上がり期の不足」の数**を期待値にしていた。
- 何が：

  | テスト | 期待値（warmup なしの入力） | warmup 17 の入力での値 |
  |---|---|---|
  | `test_lovem_observer.py::test_se2_168_is_reproduced`（ev-thailand、legacy） | 2026-W38 の要求／実出荷 150／132、W39 150／0、不足の合計 168、期間の実出荷 9,370、push の不足 400 | W38 150／150、W39 150／150、不足の合計 0、期間の実出荷 10,540、push の不足 0 |
  | `test_stage3a1_stockyard.py::test_ev_europe_2026_import_chain_matches_post_gate_baseline`（legacy） | Factory_Import_HU の P 7,945、S 8,345、I 0 | P 8,815、S 8,815、I 0（売上 3,665.1 億・粗利率 52.48% は一致） |
  | `test_stage3a1_stockyard.py::test_ev_europe_2026_local_chain_matches_pre_yard_baseline` | Kitting の完成／全体 41,475／41,975（不足 500） | 44,325／44,325（不足 0） |

- なぜ：3 件とも、計画の始まりで作れなかった分（push の Mode 4 の立ち上がり、開始端の Kitting の不足）を数えている。warmup がその不足を無くしたので、数が変わった。エンジンの解き方は変わっていない。
- **直した内容（大杉さんの判断）**：
  - ev-europe の 2 件：期待値を上の「warmup 17 の入力での値」に書き換えた。前の値と、変わった理由を、テストの説明文とコメントに残した。
  - `test_se2_168_is_reproduced`：**warmup を入れない入力のコピーで実行する形に変えた。** 新しい fixture `se2_run` が、ev-thailand-2026 のフォルダを一時フォルダへコピーし、コピーの `planning_config.csv` を `warmup_lt,0` にして `materialize_warmup` で生成行を取り除き（需要の最初の週が 2026-W02 に戻ることを確かめる）、legacy で 1 回、観測つきで実行する。期待値（168 など）は前のまま。原本は変えない。このモジュールのほかのテスト（Q12 など）は、今までどおり原本（warmup 17）で実行する。
- 残る注意：LOVEM の SE2 の説明資料（`se2_case.json`）は、今の ev-thailand-2026 の原本からは 168 を再現しない（不足 0 になる）。168 を見せるには、warmup の無いコピーで観測する必要がある。

---

## 6. 本書と変えた点

1. **iphone_global の値を決めなかった**（§2.3、S1）。エンジンのコードを変えない約束を優先した。
2. **oil-global-2027 を 26 にした**（§2.2）。手順では 52 になるが、大杉さんの判断で、29 件の期末注文残を残して 26 にした。
3. **legacy の golden の入力は「変わった後」にした**（依頼書は「前でも後でもよい」）。warmup を入れた後の入力でも、legacy の解き方が壊れていないことを守れるため。
4. **golden の作り直しのプラグイン指定**：CLAUDE.md の手順は「rice 以外は `safe`」だが、今回は、各 golden に記録されているプラグインの一覧をそのまま渡した（`config` の変化を、方式の記録だけにするため）。
5. **既存のテスト 2 本（3 件）を直した**（§5 S8）。依頼書 4 の範囲の外だが、大杉さんの判断による。
6. **ev-thailand-2026_update の生成行**：golden の対象外なので、`materialize_warmup` を直接呼んで作り直した（16 → 17 週）。

---

## 7. `python -m main` で確かめる手順

`python -m main` を起動し直してから、モデルのフォルダを読み込む（フォルダを切り替えただけだと、前のモデルの出力が残ることがある）。

1. **ev-thailand-2026**
   - 読み込むと、計画の開始が 2025-W37（121 週）になる。
   - Planning Engine を実行し、Network タブ → 「✔ Flow Check」を開く。
   - 要約行に「表 2：需要 63240 ＝ 当週出荷 63240 ＋ 早出し 0 ＋ 遅配 0 ＋ 期末注文残 **0**」、表 1 は「NG 0・対象外 0」と出る。
   - 「📋 PSI List」で `IN:mom:Factory_Import_CN:EVmaker_Import` を選ぶと、2025 年の助走週に P と I が立ち、2026-W02 以降の CO が 0 になる（warmup なしでは CO が 400 のまま残っていた）。
2. **Cookie-jp-2026**
   - 同じ手順で、Flow Check の要約行が「需要 141990 ＝ 当週出荷 141990 ＋ … ＋ 期末注文残 **0**」になる。
   - PSI List で `OUT:dad:DC_Import_Main:Cookie_Import` を選ぶと、Σ 行の S（要求）と Ship（実出荷）が、どちらも 78,930 になる（warmup なしでは 78,142 と 67,274）。
3. **iphone_global**：Flow Check の要約行に、期末注文残 97,834 が出る（warmup なしのため）。
   **oil-global-2027**：計画の開始が 2026-W28（104 週）になり、Flow Check の要約行に、期末注文残 29 が出る。表 2 で、残りが Gasoline_Local_RedSea の Retail_Local_R_KANSAI（9）と Retail_Local_R_CHUBU（20）にあることを確かめられる。
4. **legacy と見比べる**：モデルのフォルダをコピーし、コピーの `planning_config.csv` に `lot_flow_mode,legacy` を 1 行足して読み込む（原本は変えない）。
5. **golden の差分の確認**：`git diff --stat`、`git diff tests/golden/<モデル>.json`。入力の生成行は `git diff --stat -- data/sample`。
