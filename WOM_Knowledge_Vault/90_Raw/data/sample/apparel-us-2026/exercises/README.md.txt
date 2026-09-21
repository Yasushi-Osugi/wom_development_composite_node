# apparel-us-2026 — 演習問題 模範解答

note記事 第6回「オフショア vs 垂直統合」で出題した4つの演習問題の模範解答です。
課題①〜③はWOMを実際に再実行して数値検証したもの、課題④はコードを伴わない設計討議です。

再現には `wom-v1r1m8` ルートで以下を実行してください（PSI→PPCの全パイプラインを
コードから直接呼び出す standalone script が必要です。GUIの `python -m main` からは
`data/sample/apparel-us-2026` を選んで `Run Planning Engine` → `PPC Financial KPI`
タブでも同じ結果を再現できますが、本ディレクトリのscriptは複数パラメータを一括で
振るための headless 版です）。

| 課題 | 検証結果 | 詳細 |
|---|---|---|
| ① margin_rate感応度分析 | margin_rateはPPC(広義)GM%だけを動かし、Management(狭義)GM%は65.3%で完全に不変 | [ex1_margin_rate_sensitivity/](ex1_margin_rate_sensitivity/README.md) |
| ② 関税ショック損益分岐点分析 | 小売価格を**+3.2%**引き上げればBase水準(35.9%)を維持できる。ただし`ppc_market_price.csv`を変更しても効果はゼロ(要`sku_master.csv`のselling_price変更) | [ex2_tariff_breakeven_price/](ex2_tariff_breakeven_price/README.md) |
| ③ 季節重複時のキャパシティ競合検証 | S4/S5の需要期を重ねると、同じ物理工場(Factory_Import_CN, 実キャパ15,000/週)に対して**合計30,000/週**まで生産計画が成立してしまう(SKU単位で独立判定、合算されない) | [ex3_capacity_overlap/](ex3_capacity_overlap/README.md) |
| ④ 店舗共有パターンの設計 | 設計討議(コードなし) | [ex4_shared_store_design/](ex4_shared_store_design/README.md) |

各サブディレクトリに、実行ログの要点・グラフ・再現用のPythonスクリプトを格納しています。
すべて `data/sample/apparel-us-2026/` の実データ・実コード(`wom/engine/*`, `wom/ppc/*`)を
直接呼び出して検証したものです（読み手の手元でも同じ結果を再現できます）。
