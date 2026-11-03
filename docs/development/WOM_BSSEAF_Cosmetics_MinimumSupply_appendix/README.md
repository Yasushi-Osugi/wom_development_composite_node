# 付録：BS-SEAF 化粧品 代理店への最低供給量の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_Report.md`。

- `policy/`：方針のファイル（MS50・MS70）。
- `udp/MS_base`・`udp/MS50`：選択の台帳、要求週ごとの結果、時間の可否の診断、供給 0 の連続、`udp_plan.json`。MS50 は `udp_min_supply_check.csv`（二段階の確認）も。
- `udp/MS70`：`udp_conflicts.csv`（衝突の記録）、`udp_selection_reference.csv`（衝突の無い鍵の参考。採用できる台帳ではない）、`udp_plan.json`。
- `records/t2_all.csv`：基準・MS50 の要求週ごとの全期間の結果。`records/pre.json`：B2、試行の前の参考値、終了コード。`records/measure.json`：確かめと集計。`records/knowledge.json`：実行に渡した知識の版。
- `scripts/`：`output/bsseaf_cosmetics/ms_work/` に置いて、リポジトリの根から `run_trial.py`、`measure.py` の順に実行する。C3a の写し、P2-a の付録の `make_allocation.py`（`p2a_work/`）を要する。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
