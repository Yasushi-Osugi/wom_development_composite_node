# 付録：BS-SEAF 化粧品 タイ向けクリームの最低 7 割（TH70）の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Report.md`。作業計画：`requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md`。

- `inputs/`：TH70 の数量枠（`allocation_qty_TH70.csv`）と方針（`udp_policy_MS50TH70.csv`）、実行に渡した知識の版（`knowledge.json`）、T0 で記録した入力のハッシュ（`t0_hashes.json`）。
- `udp/TH70/`：選択の台帳、要求週ごとの結果、最低供給量の二段階の確認、時間の可否の診断、供給 0 の連続、`udp_plan.json`。
- `udp/MS50_reproduced/udp_plan.json`：基準 MS50 を今の commit で再現したときの計画の記録。台帳 5 つは `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/udp/MS50/` とバイト単位で同じなので、写していない（`records/t1_compare.json`）。
- `shelf/`：先入れ先出しの年齢の要約（許容 52 週）。
- `records/`：比べる表（`report_tables.md`、`th70_measure.py` が出力）、確かめと集計（`measure.json`）、要求週ごとの全期間の結果（`th70_all.csv`）、クリームの工場の週の生産と作り置きの週ごとの値（`cream_factory_stock_by_week.csv`）、T1 の照合（`t1_compare.json`）、試行の前の参考値・衝突・終了コード（`*_pre.json`）、道具の出力（`*_stdout.txt`）。
- `scripts/`：`th70_trial.py`（T0〜T2）、`th70_measure.py`（T3）。`output/bsseaf_cosmetics_th70/work/` に置いて、リポジトリの根から `th70_trial.py T0`、`T1`、`T2`、`th70_measure.py` の順に実行する。Python 3.12（Anaconda）。評価の額は P2-a の付録の `make_allocation.py`（git の対象）の単位の貢献を使う。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
