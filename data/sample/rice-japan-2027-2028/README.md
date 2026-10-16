# rice-japan-2027-2028（日本のコメ：季節供給・玄米保管・精米）

新潟のコシヒカリと北海道のゆめぴりかを、田 → 産地の集荷 → 玄米倉庫 → 精米センター（東・西）→ DC → 小売（関東・東北・関西・九州）へ供給するモデル。
計画期間は 2025-W33〜2028-W52（177 週。2026-W53 は需要 0 で埋まる）。lot_flow_mode = identity。

このフォルダの CSV が正本（2026-10-09、`requests/RequestLetter_RiceLegacyRetire_to_CodeKun.md` で legacy の rice を置き換えた）。
仕組みと検証：`docs/development/WOM_RiceSeasonal_Implementation_Report.md`、置き換え：`docs/development/WOM_RiceLegacyRetire_Report.md`。

## 季節供給の仕組み

収穫は年に 1 回（コシヒカリ W41〜W43、ゆめぴりか W37〜W43）。将来の市場の需要 ID（要求週・ID は変えない）を、過去の収穫に割り当て、玄米で保管し、要求に近い週に精米して届ける。
これを計画するのが上位の層 **Rice Seasonal（収穫・玄米保管・精米）**（`wom/plugins/rice_seasonal.py`）で、ID ごとに**収穫週と精米週の二つの日付**を選び、両品目を一度に解く（精米センターは品目共用）。
割り当てられない ID は、元の要求のまま市場の注文残として残る（匿名の期首在庫は作らない）。

- **推奨のプラグインの組**（`planning_config.csv` の `recommended_plugins`、golden と同じ組）：Holiday Calendar・Buffering Stock・Capacity Override・**Rice Seasonal**。
- **GUI**：このフォルダを読み込むと、チェックがこの組に合う（Rice Seasonal も ON）。そのまま Run Planning Engine すれば golden と同じ値になる。比較したいときは、読み込んだ後に手で変えられる（Rice Seasonal を OFF にすると過去の収穫に割り当てられず、ほとんどの需要が注文残になる）。
- **headless**：`--plugins` を省略すればこの組（明示するなら `--plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin`）。

## 値（Owner の決定、元の依頼書 §8.1・§8.2）

| 項目 | 値 |
|---|---|
| 1 lot | 精米 3 t（玄米 3,333.3 kg）、歩留まり 0.9。残り（ぬか等）は物量だけ記録し、金額は付けない |
| 玄米の保存 | 最長 52 週 |
| 収穫への遡及 | 52 週＋経路の LT |
| 精米の前倒し | 1 週まで（2026-10-09 に 0 週から変更） |
| 精米センター | 東 1,300・西 1,000 lot／週（**品目共用の一つの資源**） |
| 玄米倉庫・集荷・DC・市場 | 上限なしを明示 |
| 収穫 | 収穫週の能力はコシヒカリ 15,500 lot／週・ゆめぴりか 2,600 lot／週。年産上限はその合計（46,500・18,200）。**2025 年産だけ**コシヒカリ 18,595 lot／週・上限 55,785（仮定、下の「2025 年産」） |
| 報告の開始 | 2027-W01（`vc_config.csv` の `report_start`。報告の開始週の正典） |
| 価格 | 精米センターから先は、関東のコシヒカリの店頭 500 円／kg（150 万円／lot）から逆算した仮置き（§8.2） |

## 結果の読み方

- **2025 年産を計画に入れた**（2026-10-16、`requests/RequestLetter_RiceOpeningCrop2025_Apply_to_CodeKun.md`）。計画は北海道の収穫（2025-W37）の 4 週前、2025-W33 から始まる。2025-W33〜W52 の需要は 0。2025 年の秋に収穫した米が 2026 年の需要 ID に割り当てられて玄米倉庫に入り（2025-W52 の週末に新潟の玄米倉庫で 51,167 lot）、2026 年の需要は新米に切り替わるまで 2025 年産で届く。
  - **仮定**：新潟（コシヒカリ）の 2025 年産は 18,595 lot／週 × 3 週（W41〜W43）＝ **55,785 lot**（他の年 46,500 の 1.2 倍。前年産には余剰があった仮定）。2026 年の需要を届かない量 0 で届けるのに要る量（試行 `requests/RequestLetter_RiceOpeningCrop2025_Trial_to_CodeKun.md` の T3）。北海道（ゆめぴりか）の 2025 年産は他の年と同じ 18,200 lot（使うのは 15,008）。
  - 2025 年産は期首在庫ではなく普通の年産として持つ（決定記録 D7：期首在庫は計画の中で作る）。2025 年の週は報告の外（報告の開始 2027-W01 は変えない）。2026 年の休日はデータに無い。
- **報告期間（2027-W01〜）の不足は収穫量による**：コシヒカリは年産 46,500 lot が需要（約 59,903 lot／年）より少ない。不足は市場の注文残として見せる（データは直さない）。不足は要求週の早い順に配り、同じ週の中では市場の要求量に比例（最大剰余法）。
- 結果（Rice Seasonal ON）：当週出荷 212,003、注文残 24,934（すべて報告期間のコシヒカリ。助走〔2026 年〕の注文残 0）、遅配・早出し 0。報告期間のコシヒカリは当週出荷 97,496・注文残 24,934（2025 年産を入れる前は 93,874・28,556。2026 年産を 2026 年の需要に使う量が 3,622 lot 減り、その分が 2027 年へ回った）。Flow Check の表 2 に「うち報告期間」の列が出る。World Map の帯は「報告の開始週 2027-W01（vc_config.csv）」。

## ファイル

| ファイル | 内容 |
|---|---|
| sc_tree_master.csv など通常の CSV | 経路・需要・能力・休業（GW・お盆・年末年始）・価格 |
| capacity_plan.csv | 稲作田の非収穫週は 0（能力ゼロ）。精米センターのエンジンの上限は品目共用の値（品目の合計は Rice Seasonal が守る） |
| rice_seasonal_config.csv | 遡及の窓・玄米の保存の上限・精米の前倒し |
| rice_recipe.csv | 精米 kg／lot と歩留まり |
| rice_resources.csv・rice_resource_map.csv | 資源（単位つき）と、品目×ノード×役割 → 資源 |
| rice_resource_capacity.csv・rice_crop_limit.csv | 収穫週と週の収穫能力、作期ごとの年産上限 |
| vc_config.csv | `report_start` だけ（ほかの vc_* マスターは無いので Value Chain の台帳は作られない） |

`tools/rice_seasonal_check.py`（実出荷からの照合）、`tools/rice_seasonal_lovem_check.py`・`tools/lovem_interval_check.py`（LOVEM の照合）で確かめられる。
