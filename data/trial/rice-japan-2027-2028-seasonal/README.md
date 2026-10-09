# rice-japan-2027-2028-seasonal（通常 Rice の移行用コピー）

`tools/gen_rice_seasonal_migration.py` が `data/sample/rice-japan-2027-2028`（legacy、比較用、変えない）から作る。
手で直さず、道具を直して作り直すこと。依頼書：`requests/RequestLetter_RiceSeasonal_Implementation_to_CodeKun.md`
（§8.1・§8.2 の Owner の決定）。報告書：`docs/development/WOM_RiceSeasonal_Implementation_Report.md`。

## 計画の仕方

- lot_flow_mode = identity。HarvestBatch は使わない。
- プラグイン：Holiday Calendar（＋ Capacity Override・Buffering Stock は入力が無く何もしない）と
  **Rice Seasonal（収穫・玄米保管・精米）**。Rice Seasonal は既定 OFF なので、GUI の Plugins で ON にする。
  headless：`--plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin`
- Rice Seasonal は、市場の需要 ID（要求週・ID はそのまま）を、過去の収穫 → 玄米倉庫 → 要求に近い週の精米に割り当て、
  内部の計画の位置だけを渡す。割り当てられない ID は市場の注文残として残る（消さない）。

## 元の Rice から変えたもの

| ファイル | 変更 |
|---|---|
| planning_config.csv | lot_flow_mode = identity（元は legacy） |
| capacity_plan.csv | 稲作田の非収穫週 0.1 → **0**（能力ゼロを明示）。精米センターのエンジンの上限を品目共用の値（東 1,300・西 1,000）に。2028-W52 の行を追加 |
| node_cost_master.csv | 精米センターから先の 16 行（§8.2、1 lot＝精米 3 t、店頭 約500円/kg から逆算、仮置き） |
| sku_master.csv | unit_cost＝地域の DC の売価、selling_price＝小売の売価（§8.2）、note 列を追加 |

## 上位の層の入力（新規）

| ファイル | 内容 |
|---|---|
| rice_seasonal_config.csv | 収穫への遡及 52 週（＋経路の LT）、玄米の保存 最長 52 週、精米の前倒し 1 週まで（2026-10-09 変更） |
| vc_config.csv | `report_start` = 2027-W01 だけ。**報告の開始週の正典**（World Map・Value Chain・Flow Check・Rice の層が同じ値を読む）。ほかの vc_* マスターは無いので、Value Chain の台帳は作られない |
| rice_recipe.csv | 1 lot＝精米 3,000 kg、歩留まり 0.9（玄米 3,333.3 kg）。残りは「その他の産出」として物量だけ |
| rice_resources.csv | 資源と単位（玄米 kg／週・精米 kg／週・玄米の在庫 kg）。精米センター東 1,300・西 1,000 lot／週は**品目共用の一つの資源**。玄米倉庫・集荷・DC・市場は「上限なし」を明示 |
| rice_resource_map.csv | 品目×ノード×役割 → 資源 |
| rice_resource_capacity.csv | 収穫週と週の収穫能力（今の capacity_plan.csv の収穫週の値）、作期 |
| rice_crop_limit.csv | 作期ごとの年産上限＝収穫週の能力の合計（データは直さない。別の業務値は未定） |

## 結果の読み方（Owner の決定）

- 2026 年は助走の年。2025 年産の収穫は計画期間の外なので、2026 年の収穫が届くまでの需要は注文残になる（報告とは別に数える）。
- コシヒカリは年産の収穫能力（46,500 lot）が需要（約 59,903 lot）より少ない。不足は市場の注文残として見せる（データは直さない）。
- 不足は要求週の早い順に配り、同じ週の中では市場の要求量に比例（最大剰余法）。
