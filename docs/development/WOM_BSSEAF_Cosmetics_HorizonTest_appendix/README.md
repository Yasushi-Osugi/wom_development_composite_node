# 付録：BS-SEAF 化粧品 計画の期間を延ばす試験の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_HorizonTest_Report.md`。

- `udp/<案>/`：4 通りの選択の台帳、要求週ごとの結果、時間の可否の診断、供給 0 の連続、`udp_plan.json`。
- `quota/`：E13・E26 の数量枠。合計の内訳は `records/pre.json` の `quota`。
- `records/t2_all.csv`：E0・E13・E26 × A0e・A3 の要求週ごとの全期間の結果。
- `records/h2_diff.csv`：共通の期間で E0 と違う鍵・週の全件。
- `records/pre.json`：B1〜B3、試行の前の参考値。`records/measure.json`：確かめと集計。`records/knowledge.json`：実行に渡した知識の版。
- `scripts/`：`output/bsseaf_cosmetics/hz_work/` に置いて、リポジトリの根から `build.py`、`run_trial.py`、`measure.py` の順に実行する。`build.py` が写しの作り方。C3a の写し、前回の `U4_A0e_r2`・`U4_A3`（年齢の要約を含む）、P2-a の付録の `make_allocation.py`（`p2a_work/`）、M0 の `checks_ppc.json` を要する。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
