# 付録：BS-SEAF 化粧品 U4 の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_Report.md`。

- `udp/<案>/`：選択の台帳、要求週ごとの結果、時間の可否の診断（参考値）、供給 0 の連続、`udp_plan.json`。
- `records/t2_all.csv`：要求週ごとの全期間の結果（T2）。`b_checks.json`：B1〜B4 の確かめ。`allocation_qty_P2a2.csv`：`quota_source` の列を足した数量枠。
- `scripts/`：`output/bsseaf_cosmetics/u4_work/` に置いて、リポジトリの根から実行する。順に `run_trial.py`、`measure.py`（P2-a の付録の `make_allocation.py` と `evaluation.json` を `p2a_work/` に要する）。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
