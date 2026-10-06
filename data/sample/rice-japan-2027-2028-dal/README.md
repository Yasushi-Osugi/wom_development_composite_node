# Rice DAL Trial — 試行用・golden対象外

`requests/RequestLetter_RiceDAL_Trial_to_CodeKun.md` に基づく調査用モデルです。
基準は `d848c5fa0565d70f6817c1a0257341067712deca`。既存riceの置換や本実装を意味しません。

原本 `rice-japan-2027-2028` を複写し、identityで、HarvestBatchPluginを使わずに測定しました。
変更した入力は `demand_forecast.csv`、`capacity_plan.csv`、`planning_config.csv` だけです。
原本のその他CSVは、そのまま残しています。`inventory_master.csv` があることと、
Planning EngineのLot単位の期首在庫に読み込まれることは別です。本試行の `opening_inv` は0です。

| 項目 | 試行条件 |
|---|---|
| 計画期間 | 2025-W37〜2028-W52、連続するISO週173週 |
| 評価対象の需要週 | 2027-W01〜2028-W52 |
| 2025需要 | 2026の同じ週番号のW37〜W52を写した試行仮定 |
| 2026〜2028需要 | 原本の週形。HolidayCalendarを有効にするため、計画後のLot数はCSVの合計と異なる |
| 2026-W53 | 原本に需要予測が無いため、明示的な0を追加。実績や新しい予測ではない |
| 2028-W52能力 | 原本がW51までのため、2026-W52を写して末尾を補完 |
| 田んぼの能力 | 原本どおり。収穫週の数値と、その他の週の0.1を維持。0.1の本番仕様化を承認するものではない |
| 助走 | `warmup_lt` と `planning_start` の自動生成を使わない |
| プラグイン | HolidayCalendarPlugin、BufferingStockOptimizerPlugin、CapacityOverridePlugin |

報告開始週は、今回の測定道具が明示的にフィルターします。
`planning_start` は計画の開始週の指定で、報告開始週の指定ではありません。
通常のGUI集計が自動で2025・2026の需要を報告対象から外す、という設定はしていません。

## Headlessでの単独起動

リポジトリのルートで、モデルを一時フォルダへ複写して実行することを推奨します。

```sh
python -m tools.run_headless_from_folder --model-dir data/sample/rice-japan-2027-2028-dal --plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin --out output/rice_dal_trial/snapshot.json --ppc-out output/rice_dal_trial/ppc
```

GUIで確認する場合は `python -m main` からこのフォルダを読み込み、
**HarvestBatchを無効、Holiday Calendarを有効**にしてPlanning Engineを実行してください。
この試行はRun Simulationの数量モデル・moneyの測定ではありません。
Windows GUIの操作・描画性能は今回未確認です。

## 再測定

基準SHAの新しいcheckoutに `tools/probe_rice_dal_trial.py` と
`tools/analyze_rice_dal_trial.py` だけを先に置き、配布物の `RERUN.md` に従ってください。
`prepare` はこのフォルダが既に存在すると、上書きせずに停止します。
能力を増やした条件は測定先の `models/dal_increased/` にだけ作り、この試行用マスターも変更しません。

## 今回確認できたこと

報告期間の需要159,094 lotに対し、現行能力では当週出荷0、遅配して出荷62,082、期末注文残97,012。
年間需要に足りる田んぼの能力にした条件でも、当週出荷0、遅配89,839、期末注文残69,255でした。
プラグインを外すと、田のPは直近の過去の収穫週へ戻らず、Forwardで次の収穫週以降へ繰り延べられます。
全ノード・全週の期末Iは0で、玄米保管拠点への先行在庫は形成されません。
未処理Pの繰り延べはIとは別なので、I=0を物理的な待ち在庫が無い証拠とは解釈できません。

詳細は `docs/development/WOM_RiceDAL_Trial_Report.md` を参照してください。
