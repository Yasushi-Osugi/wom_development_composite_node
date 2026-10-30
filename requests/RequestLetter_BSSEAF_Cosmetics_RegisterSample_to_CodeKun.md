# Request Letter：BS-SEAF 化粧品 — 採用モデルを正式なサンプルとして登録する（段階 6）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-30）。進め方：GPT君の確認（2026-10-30）に従う
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `e9741a6`。この依頼書は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：BS-SEAF の図の段階 6「Model Application and Execution」、検証報告の骨組み `requests/BSSEAF_Verification_Cosmetics_Report_Outline_v0.1.md`、金額の試行 M0 の報告書と付録（`docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md`・`..._appendix/`）、`AGENTS.md` §5（Scenario rules）、`docs/scenarios/README.md`
- 種別：**サンプルのモデル・golden・文書の追加**。エンジン・道具のコードは変えない。既存の golden は変わらないこと

---

## 0. 段階 6 の意味と、採用するモデル

**段階 6 をこう捉える**：人間が採用したモデルを、通常の利用の経路に引き渡し、適用・実行する。WOM では、**採用した化粧品のモデルを `data/sample/` に登録し、リポジトリを取得した利用者が、通常の CLI・GUI から実行できる状態にする**。検証の範囲は「教育・実証用のモデルの正式な登録と実行」。実企業での運用は範囲の外。

**採用するモデル（基準）＝ M0**：C3b の数量のモデル（タイの代理店を含み、能力を A9 で計算し直したもの）に、金額の仮定（M1〜M8）を置いたもの。供給能力が足りた状態で、数量と PPC の金額を確かめ済み（M0 の報告書）。

- P2-a1 などの配分の案を「最良のモデル」として採用するのではない（P2-a1 は P1 より良いが、配分しない P0 には届かなかった）。
- 能力の足りない C3a、配分を変える P1・P2-a は、**基準から再現できる手順と配分のファイル**として残す（§2.4）。サンプルのモデルとしては登録しない。

## 1. 決めてほしいこと（大杉さん、この依頼書を Code君に渡す前に）

| # | 事項 | Claude君の推奨 |
|---|---|---|
| R1 | モデルのフォルダの名前 | **`cosmetics-sg-th-2027-2029`**（題材・市場・販売の年。既存の `smartx-2027-2029` などに合わせる。シンガポールとタイの両方を含むことを名前に出す） |
| R2 | 比べる案（C3a・P1・P2-a）の残し方 | 手順と配分のファイルとして、シナリオの文書と既存の付録に残す（モデルのフォルダは 1 つ） |

以下は推奨どおりに決まったものとして書く。

## 2. 作業

### 2.1 モデルのフォルダを作る

- 元：`output/bsseaf_cosmetics/M0`（計画の入力のファイル。`README.md`・`_result/` などの試行の出力は持ち込まない）。M0 の金額の 10 ファイルは、付録の `money_csv/M0/` と同じであることを確かめる。
- 先：`data/sample/cosmetics-sg-th-2027-2029/`。ファイルの組は既存のサンプル（Cookie-jp-2026）と同じ形。`planning_config.csv` は M0 のまま（`warmup_lt 17`、`lot_flow_mode identity`、`cpu_size 24`、`recommended_plugins`）。共有の規則の宣言（`ppc_shared_rules_dir`）は置かない（金額の規則は全部モデルの中にある）。
- **warmup の行は、置いた状態で一定になること**（冪等）：登録したモデルを CLI・GUI で実行しても、追跡しているファイルが書き換わらないことを `git status` で確かめる。書き換わるなら、実行後の状態で登録し直し、もう一度確かめる。
- 名前の検査（`tests/test_no_real_names.py`）を通す。ノードの名前は役割名のまま。

### 2.2 文書

1. **モデルの README**（`data/sample/cosmetics-sg-th-2027-2029/README.md`、日本語。Cookie-jp-2026 の README の形）：
   - 業務の問い、架空のブランドであること、物理のネットワーク（2 SKU、シンガポールの直営店・EC・代理店、タイの代理店、日本の工場）
   - 単位（1 lot ＝ 1 ケース ＝ 24 個。価格・費用は 1 個当たり、税抜き）
   - 仮定（設計書 §1.4 の A1〜A13、金額の仮定 M1〜M8 の要点）と出どころ
   - 実行の方法（CLI・GUI）と期待する結果（M0 の数：期間、Flow Check の全量の充足、PPC の売上・試算利益）
   - 既知の限界：歩留まりの損は原価に入っていない（約 3%、M3）、店舗の運営費は売上の 35% の近似（M5）、日本本社の固定費なし（M6）、Value Chain の G1〜G5、U4（配分の週の粒度）、計画の境界の効果、タイの関税は 0%（EPA の仮定）
2. **シナリオの文書**（`docs/scenarios/cosmetics.md`、英語。`docs/scenarios/README.md` の推奨の構成）と、`docs/scenarios/README.md` の一覧への 1 行。
3. **比べる案の再現**（§2.4）をシナリオの文書に書く。

### 2.3 golden

- `tests/golden/cosmetics-sg-th-2027-2029.json` を、既存の golden と同じ作り方（`python -m tools.run_headless_from_folder --model-dir data/sample/cosmetics-sg-th-2027-2029 --plugins <recommended_plugins> --out tests/golden/... --quiet`）で作る。legacy の golden は作らない（identity のモデル）。
- `tests/test_public_readiness.py`（`recommended_plugins` ＝ golden の組）が通ること。

### 2.4 比べる案の再現の手順（シナリオの文書に書く。ファイルは既存の付録を参照）

| 案 | 基準からの作り方 |
|---|---|
| C3a（能力の不足） | `capacity_plan.csv` を A9 で計算し直す前の値に戻す（変更課題①②③の報告書 §2 の C3b の行の逆） |
| P1・P2-a1・P2-a2 | C3a の写しに、配分のファイル（P0P1 の報告書の付録 A、`docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/`）を `tools/run_quantity_allocation.py` で渡す |
| M0t（タイの関税 30%） | `ppc_tariff_rule.csv` の `WH_JP_Released->DC_TH` を 0.30 に（M0 の付録 `money_csv/M0t/`） |

手順は、実際に 1 回たどって、数が各報告書と合うことを確かめる（C3a の Flow Check 表2 の ⑤ 192、M0t の利益 −27,612,000 円）。

## 3. 受入条件

| # | 条件 |
|---|---|
| S1 | **モデルの保存**：計画・金額の入力と設定が全部 git の管理下にあり、`output/` や登録していないスクリプトに依存しない |
| S2 | **通常の CLI の実行**：`run_headless_from_folder` で計画と PPC が動く。期間・プラグインの組が M0 と同じ。PPC は `評価済み` |
| S3 | **結果の再現**：数量（Flow Check 表1・表2 の明細）と PPC（全体の売上 1,156,284,480 円・試算利益 631,849,608 円、チャネル × SKU の 8 通りの 1 個当たりの値）が M0 と一致する。差があれば理由を書く |
| S4 | **Value Chain**：`tools.valuechain_run`（golden ができたので `--plugins` の既定が golden の組になる）が最後まで動く。G1〜G5 は既知の限界として README に書いてあり、Value Chain の利益が PPC より G1＋G2 の分多いことを確かめる |
| S5 | **冪等**：CLI・GUI の実行の後、`git status` で追跡しているファイルが変わっていない |
| S6 | **回帰**：既存の golden（通常 15・legacy 3）が変わらない。新しい golden が通る。`test_public_readiness`・`test_no_real_names` が通る。最後に `python -m tools.quick_check --full` を 1 回（サンプルと golden をリポジトリに足す変更のため） |
| S7 | **GUI**：Windows の GUI でモデルを読み込み、計画と PPC を実行できる。GUI の確認の道具（`tools/gui_*_check.py` のうち、読み込み・計画・PPC を確かめるもの）があれば回し、画面の画像を報告書に付ける。**最後の確認は大杉さんが GUI で行う**（§4） |
| S8 | **説明と限界**：README とシナリオの文書に、業務の意味・仮定・単位・実行の方法・期待する結果・既知の限界が書いてある |
| S9 | **知識への接続**：Start Here の「手本にするモデル」（§4.1）の表に 1 行を足す案を報告書に書く（Start Here の本文は Claude君が直す） |

## 4. 大杉さんの GUI での確認（Code君の作業の後）

1. GUI でモデルのフォルダ `data/sample/cosmetics-sg-th-2027-2029` を読み込む。プラグインのチェックが `recommended_plugins` に合っている。
2. 計画を実行し、PSI の画面で、直営店の開店（2027-W14）・店頭在庫・工場の平準化が見える。
3. PPC が「評価済み」で完了し、PPC のタブに金額が出る。
4. World Map で、日本 → シンガポール・タイの流れが描ける。

## 5. 止める理由と申し送り

報告では、**止める理由**（動き・数字・誤読に関わる。先に直す）と**申し送り**（記録して進む）を分ける。些細なものは往復させずに直して報告だけにする。

止める理由に当たるもの：S3 の数が M0 と合わない（理由が分からない）、既存の golden が変わる、冪等にならない、エンジンや道具のコードを変えないと登録できない。

## 6. 報告書と commit

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_RegisterSample_Report.md`。着手時の SHA、§2 で作ったもの、§3 の S1〜S9 の結果（実行した後の数）、GUI の画像、止める理由と申し送り、Start Here への追記の案。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に書く。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-10-30 | 初版 |
