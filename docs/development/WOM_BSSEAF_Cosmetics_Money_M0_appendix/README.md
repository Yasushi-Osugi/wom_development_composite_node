# 付録：BS-SEAF 化粧品の金額試行 M0-PPC の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md`（§7 に手順）。

- `scripts/`：生成・実行・集計のスクリプト。`output/bsseaf_cosmetics/money_m0_work/` に置いて、リポジトリの根から実行する（`m0_common.py` がこの位置を前提にしている）。
- `money_csv/M0/`：M0 の金額の 10 ファイル。M0a も同じ内容。`money_csv/M0t/` は M0t で違う `ppc_tariff_rule.csv` だけ。
- `records/`：基準と写しの記録（期間・プラグイン・数量入力の sha256）、SKU とノードの対応表、A4 の合成入力と結果。

値は架空のブランドの仮定（`requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md` §5.1）。実在の企業の値ではない。
