# 実装依頼：設定変化点スイープ・ツール `tools/sweep_flags.py`

**依頼日**：2026-08-27
**依頼者**：大杉
**種別**：**新規ツールの実装**（`tools/` 配下）
**対象ブランチ**：`wom-v1r3m0_DEMO`
**先行調査**：`requests/request_investigation_s1_push_pull_default.md`、`requests/request_investigation_s2_inbound_decoupling.md`

---

## 0. この依頼で守ってほしいこと

- **新規ファイルの追加のみ。既存コードは一切変更しないこと。**
  - 保護対象コア6ファイル（`backward_planner.py` / `forward_planner.py` / `plan_copy.py` / `plan_node.py` / `sc_tree.py` / `push_pull.py`）は変更禁止
  - `tools/run_headless_from_folder.py` も**変更せず、import または subprocess で呼ぶ**こと
  - `wom/gui/` 配下も変更禁止
- **サンプルデータ（`data/sample/`）を恒久的に書き換えないこと。**
  実行中に一時的に変更する場合は、必ず元に戻す（§4 参照）
- 実装後、`git status` が clean（新規ツールと出力先を除く）であることを確認して報告すること

---

## 1. 背景と目的

### 1.1 なぜ必要か

WOM の挙動を切り分ける際、GUI 経由では以下の操作要因が混入し、何が原因で結果が変わったのか特定できなくなる。

- `Apply Filters` の押し忘れ（SKU=All の集計値を単一 SKU の値と誤認する事故が実際に発生）
- Planning Config（Start Week / #Weeks）の再入力漏れ
- プラグインの ON/OFF の記録漏れ
- 複数の設定を同時に変えてしまい、寄与を分離できない

**変化点を一つずつ振って、結果を機械的に比較する道具**があれば、この問題は構造的に解消する。

### 1.2 直近の具体的な検証課題

`data/sample/apparel-us-2026` の `Apparel_Outsourced_S1`（leaf_in は `Fabric_CN` 1つのみ）について、
以下3つの設定が結果にどう影響するかを分離したい。

| 設定 | 内容 |
|---|---|
| `buffering_stock_flag` | `sc_tree_master.csv` の `Factory_Import_CN` 行、0 / 1 |
| `push_config.csv` | ファイルの有無（`push_lead_time_weeks=4` の1行） |
| `holiday_calendar.csv` | ファイルの有無（プラグイン相当の ON/OFF） |

**既知の観測（GUI 経由、要 headless での再確認）**
- `buffering_stock_flag=1` かつ `push_config.csv` 無 → MOM に I が立たず CO が単調増加（S2 調査で機構を特定済み）
- `buffering_stock_flag=1` かつ `push_config.csv` 有（LT=4）→ MOM に I が立つ
- Holiday Calendar の ON/OFF が PPC の関税額に影響している可能性があるが**未確認**

---

## 2. 作ってほしいもの

`tools/sweep_flags.py`

### 2.1 基本動作

1. 設定の組み合わせ（ケース）を定義ファイルまたはコマンドライン引数で受け取る
2. 各ケースについて、
   - 対象 CSV を一時的に書き換える
   - `run_headless_from_folder.py` 相当の計画実行を行う
   - 結果を収集する
   - **CSV を元に戻す**
3. 全ケースの結果を1本の CSV に横並びで出力する

### 2.2 呼び出しイメージ

```
python -m tools.sweep_flags --model data/sample/apparel-us-2026 --spec tools/sweep_specs/apparel_s1.yaml
```

引数の設計は任せる。YAML でも JSON でも、スクリプト内の dict でもよい。
**ただし「ケース定義を外に出せる」ことは必須**（次の検証で別の組み合わせを試すため）。

### 2.3 ケース定義に必要な表現力

最低限、以下が指定できること。

- **CSV のセル書き換え**
  例：`sc_tree_master.csv` の `node_name=Factory_Import_CN` かつ `product_name=Apparel_Outsourced_S1` の行の `buffering_stock_flag` を `1` にする
- **ファイルの有無の切り替え**
  例：`push_config.csv` を存在させる／退避する（内容も指定できること）
  例：`holiday_calendar.csv` を退避する
- **ケースに名前をつける**（`base` / `A_no_holiday` / `B_flag1` / `C_flag1_push4` 等）

### 2.4 直近の検証で使うケース（初期スペックとして同梱してほしい）

| ケース名 | buffering_stock_flag | push_config.csv | holiday_calendar.csv |
|---|---|---|---|
| `base` | 0 | 無 | 有 |
| `A_no_holiday` | 0 | 無 | **無** |
| `B_flag1` | **1** | 無 | 有 |
| `C_flag1_push4` | **1** | **有（LT=4）** | 有 |

`push_config.csv` の内容（`C_flag1_push4` で使用）：
```
sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week
Apparel_Outsourced_S1,Factory_Import_CN,0,0,False,,0,,4,
```

---

## 3. 収集・出力してほしい項目

対象 SKU は `Apparel_Outsourced_S1`（スペックで指定可能にすること）。

### 3.1 PSI 側（ノードごと）

対象ノード：`Fabric_CN`(leaf_in) / `Factory_Import_CN`(mom) / `SP_Apparel_Outsourced`(supply_point) / `DC_Import_Buffer`(dad)
（これもスペックで指定可能にすること）

| 項目 | 内容 |
|---|---|
| `series_md5` | `run_headless_from_folder.py` の `_psi_signature` と同じ算出方法 |
| `P_nonzero_weeks` | P が非ゼロの週の一覧（多い場合は先頭/末尾＋件数） |
| `S_nonzero_weeks` | 同上 |
| `I_nonzero_weeks` | 同上 |
| `CO_nonzero_weeks` | 同上 |
| `I_max` / `I_sum` | 在庫の最大値と総和 |
| `CO_max` / `CO_last` | CO の最大値と最終週の値 |
| `plan_mode` | 実行時に確定した値（`pull` / `push` / `push_sub`） |
| `is_decoupling` | 実行時に確定した bool |

**`plan_mode` と `is_decoupling` の実測値を出すこと**が重要。CSV の設定がエンジン内でどう解決されたかを確認したい。

### 3.2 PPC 側

`ppc_kpi_summary.json` と `ppc_event_ledger.csv` から、

| 項目 | 内容 |
|---|---|
| `lots` | ロット数（全体および対象 SKU 単体） |
| `revenue` / `total_cost` / `gross_profit` / `gross_margin` | 全体および対象 SKU 単体 |
| `tariff_cost` | 同上 |
| `trust_events` | 件数と種別ごとの内訳 |
| `tariff_event_count` / `tariff_event_sum` | 台帳から対象 SKU 単体で集計 |

**「全体」と「SKU 単体」の両方を必ず出すこと。**
GUI で両者を取り違える事故が起きたため、この区別を明示的に記録したい。

### 3.3 起動時ログ

各ケースについて、以下を記録すること。

- `[warmup]` 行（`effective_start` と `warmup_lt`）
- `[AutoDetect] period` 行
- `[PushPull]` 行（`Applying push config` か `no rows matched` か）
- `[HolidayCalendar]` 行（件数。出なければ「無効」と記録）

**`planning_config.csv` の `warmup_lt` が headless で有効になっているかを確認したい。**
GUI では反映されないことが判明している（CLAUDE.md 記録済み）。

### 3.4 出力形式

`output/sweep/<timestamp>/` 配下に、

- `summary.csv` — ケースを列、項目を行にした横並びの表（**目視比較しやすい向き**）
- `detail_<case>.json` — ケースごとの詳細（週次系列を含む）
- `console_<case>.log` — 各ケースの標準出力

`summary.csv` は、**差分が出た項目が一目で分かる**ことを優先してほしい。
可能なら「全ケースで同一の項目」と「差分のある項目」を分けて出力するとよい。

---

## 4. 安全要件【重要】

### 4.1 CSV の復元

- 各ケースの実行前に、書き換える対象ファイルを**必ず退避**すること
- 実行後に**必ず復元**すること
- **例外が発生した場合も復元されること**（`try/finally` を使う）
- 全ケース終了後、`git status` で `data/sample/` に変更が無いことを確認できる状態にすること

### 4.2 出力の混入防止

- 各ケースの実行前に `output/ppc/` を退避またはクリアすること
- **前回のケースの出力が残ったまま読まれる事故を防ぐこと**
  （実際にこの取り違えが発生し、同一の台帳を別条件のものとして比較してしまった）

### 4.3 冪等性

- 同じスペックで2回実行したら、同じ結果になること
- 中断しても `data/sample/` が壊れないこと

---

## 5. 実装上の注意

- `run_headless_from_folder.py` は**変更せず**、import して関数を呼ぶか `subprocess` で起動すること
- Windows 環境で動くこと（`_DEMO` は Windows 上にある）。パス区切りに注意
- 依存ライブラリは既存のもの（`pandas` 等）に留めること。新規の依存は避ける
- 1ケースあたりの実行時間を計測し、`summary.csv` に含めること
- Holiday Calendar が headless でプラグインとして有効かどうかは**未確認**。
  もし headless では常に無効なら、`base` と `A_no_holiday` が同一結果になるはず。
  **その場合はそう報告すること**（ツールの不具合ではなく、仕様の発見として）

---

## 6. 報告してほしいこと

1. ツールの使い方（コマンド例、スペックの書き方）
2. §2.4 の4ケースを実行した結果の `summary.csv`
3. **差分が出た項目と、出なかった項目の整理**
4. 実行後の `git status`（`data/sample/` が clean であること）
5. 実装中に気づいた点（依頼範囲外でも）

---

## 7. この依頼の後の流れ（参考）

- 結果をもとに、大杉が「どの設定が何に効いたか」を判定する
- 判定に応じて、エンジン修正・lint 追加・仕様文書化のいずれかへ進む
- **このツール自体は恒久的に `tools/` に残す。**
  今後の切り分けはすべてこれを使う
