# 付録：BS-SEAF 化粧品 U4 能力に合わせて減らす週を選ぶ規則の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_CapacityAwareWeekRule_U4_Report.md`。

- `udp/<案>/`：選択の台帳、要求週ごとの結果、時間の可否の診断、供給 0 の連続、`udp_plan.json`。
- `records/t2_all.csv`：A0e・A3 の要求週ごとの全期間の結果。A0・A1 は `WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/t2_all.csv`。
- `records/pre_checks.json`：B1・B2 と試行の前の参考値。`records/measure.json`：B3・T8 の確かめと集計。
- `scripts/`：`output/bsseaf_cosmetics/cap_work/` に置いて、リポジトリの根から `pre_checks.py`、`run_trial.py`、`measure.py` の順に実行する。C3a の写し、U4 の作業フォルダ（`U4_A0` など、年齢の要約）、P2-a の付録の `make_allocation.py` と `evaluation.json` を `p2a_work/` に要する。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
