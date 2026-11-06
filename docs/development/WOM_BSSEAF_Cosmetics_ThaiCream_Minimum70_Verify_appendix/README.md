# 付録：BS-SEAF 化粧品 TH70 の独立の確認（段階 7）

本報告：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_Report.md`。

- `scripts/v2_run.py`：写しと入力を自分のコードで作り、`tools.run_quantity_allocation`・`tools.shelf_life_check` を直接実行する（出力 `output/bsseaf_cosmetics_th70_verify/v2/`）。
- `scripts/v2_check.py`：V2 の 3〜8 を自分の集計で確かめ、`v2_check.json` を書く。
- `records/v2_check.json`：V2 の結果。`records/v1_t1_compare.json`：V1 の T1 の照合（付録のスクリプトの写しの出力）。

リポジトリの根から `v2_run.py`、`v2_check.py` の順に実行する（Python 3.12、Anaconda）。
