# Request Letter — 公開の前の小さな整理：プラグインの組・知らない名前・OI_ の例外

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-09
- 基準：`wom-v1r5m1_cap_trial` の最新（rice の置き換えのコミット、`commit_msg100.txt` の後）。着手時の SHA を報告する
- 前提：`docs/development/WOM_RiceLegacyRetire_Report.md` の「判断を仰ぎたいこと」3 点（Owner の回答：3 点とも推奨どおり）
- 種別：GUI・headless・照合の道具・データの設定・テスト。**保護対象のコアは変えない。golden は変えない。**

## 0. 目的

公開したサンプルを、だれが開いても golden と同じ値が出るようにする。利用者が気づけない「黙った動き」を無くす。

## 1. モデルごとの推奨のプラグインの組（決定 2）

**今の問題**：rice を GUI で読み込むと Rice Seasonal だけが自動で ON になり、Holiday Calendar は既定の OFF のまま。そのまま計画すると 139,554／93,975 になり、golden・報告書の 141,210／95,727 と違う。ほかのモデルも、GUI の既定のプラグインと golden のプラグインが同じとは限らない。

**作るもの**：

1. 各モデルの `planning_config.csv` に、キー `recommended_plugins`（値はプラグインのクラス名をカンマで区切る。例 `HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin`）を足す。**値は、そのモデルの golden（`tests/golden/<モデル>.json` の `config.plugins`）と同じにする。** golden の無いモデルは、今の GUI の既定の組を書き、一覧で報告する。
2. GUI：Load Model Folder のとき、`recommended_plugins` があれば、プラグインのチェックをその組に合わせる（組に無いものは OFF）。ステータスの行に「推奨のプラグインの組を適用：…」と出す。読み込んだ後に手で変えられる（比較のため）。キーが無いモデルは、今のまま（チェックを変えない）。
3. 前回の「`rice_seasonal_config.csv` があれば Rice Seasonal を ON」の専用の処理は、この仕組みに置き換えて外す。Rice Seasonal を ON にした実行で Rice の設定が無ければ止める動き（前回のメッセージ）は残す。
4. headless：`--plugins` を指定しないときは `recommended_plugins` を使う。キーが無いモデルは今の既定（`safe`）のまま。`--plugins` を指定したときは、指定のとおり（今のまま）。どちらを使ったかを出力の config に記録する。
5. 名前が知らないプラグインなら、読み込みで止める（3 と同じ規則）。

**確かめること**：全サンプルについて、GUI で読み込んで既定のまま計画した値＝headless で `--plugins` なしの値＝golden。少なくとも rice・Cookie・smartx（Capacity Layer は golden で OFF のはず）を GUI で確かめ、残りは headless で全モデルを比べる。

## 2. 知らないプラグイン名で止める（決定 3）

**今の問題**：headless の `--plugins` に知らない名前（例：削除した `HarvestBatchPlugin`）があっても、黙って無視して走る。

**変えること**：知らない名前があれば、実行の前に止める。メッセージに、知らない名前と、使える名前の一覧を出す。`tools/run_headless_from_folder.py` と、同じ経路を使う道具（`tools/warmup_trial.py` など）で同じ規則にする。テストを足す。

## 3. OI_ の例外を外す（決定 1）

**今の問題**：Flow Check（`wom/engine/flow_check.py`）は、需要の無い ID を持つノードを「対象外」にしている（旧 HarvestBatch の `OI_` のため）。`tools/lot_identity_checks.py` にも `OI_` を許す分岐がある。作るものが無くなったので、迷い込んだ ID が見えなくなるだけになっている。

**変えること**：両方の例外を外す。需要の無い ID は、どの名前でも NG として出る。テストを足す（需要に無い ID を入れた小さな木で NG になること）。全サンプルで NG が 0 のままであること（今のデータには `OI_` が無いので、変わらないはず）。

## 4. 受入条件

| ID | 検査 |
|---|---|
| P-1 | 全サンプルで、GUI の既定の値＝headless（`--plugins` なし）の値＝golden（golden のあるモデル）。表で示す |
| P-2 | rice を GUI で読み込んで既定のまま計画すると 141,210／95,727、World Map の帯 2027-W01 |
| P-3 | 知らないプラグイン名で headless・GUI の読み込みが止まり、メッセージに使える名前が出る |
| P-4 | 需要の無い ID が Flow Check・lot_identity_checks で NG になる（テスト）。全サンプルの NG は 0 |
| P-5 | golden（13＋legacy 3）は不変。全テストを単独で実行して緑 |

## 5. 範囲・文書

- 保護対象のコア・golden・モデルの値（需要・能力・価格）を変えない。`planning_config.csv` に足すのは `recommended_plugins` だけ。
- 文書：CLAUDE.md（プラグインの節・golden の作り方）、`tests/test_golden.py` と `tools/run_headless_from_folder.py` の説明、各モデルの README に「推奨のプラグインの組」があればその記述。`docs/WOM_Start_Here.md` は触らない（Claude 君が直す）。
- 報告：`docs/development/WOM_PublicReadiness_Plugins_Report.md`。最後に変更・追加・削除のファイルの一覧。
- commit・push はしない。
