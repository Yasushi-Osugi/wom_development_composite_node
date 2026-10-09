# A：`capacity_plan.csv` の書式と、助走行の作り方の対応表

## 1. 2 つの書式と、実ローダの読み方

実ローダは `wom/engine/capacity_sealer.load_capacity_dataframe`（GUI と headless が共用）。

| | 新書式 | 旧書式 |
|---|---|---|
| 見分け方 | `node_name` 列がある | `node_name` 列が無い |
| 例 | `sku_id,node_name,week,max_supply,cap_soft,source` | `sku_id,region,week,max_supply,cap_pieces,source` |
| 使っているモデル | smartphone-global-2026-2029 以外のすべて | smartphone-global-2026-2029 だけ |
| ローダが読む列 | `sku_id`・`node_name`・`week`・`max_supply`（＋あれば `cap_soft`） | `sku_id`・`week`・`max_supply`（＋あれば `cap_soft`） |
| 能力の単位 | (製品, ノード, 週) | (製品, 週)。同じ製品・週の行は**合計**する |
| 能力を付けるノード | その名前のノード | その製品の InBound root（`sc_tree.get_in_root(製品)`＝最初の MOM） |
| ローダが読まない列 | `source` | `region`・`cap_pieces`・`source`（記録としての列） |

smartphone-global-2026-2029 の実データ：

| 製品 | `region` | `source` | 週 | `max_supply` | 能力が付くノード |
|---|---|---|---|---|---|
| Phone16 | CN | EMS_A_CN | 2027-W01〜2029-W52（156 行） | 800 → …（後半に下がる） | EMS_A_CN |
| Phone15 | CN | EMS_A_CN | 2027-W01〜2029-W52（156 行） | 500 → … | EMS_A_CN_i15 |
| Phone17 | CN | EMS_A_CN | 2028-W27〜2029-W52（78 行） | 26 → 52 → 78 → …（立ち上げ） | EMS_A_CN_i17 |

- `region=CN`・`source=EMS_A_CN` は、3 製品に共通の値で、ローダは読まない。「どこの能力か」を人が読むための記録である。
- Phone16 には MOM が 2 つある（EMS_A_CN と EMS_A_IN）。旧書式の能力は、最初の MOM（EMS_A_CN）だけに付く。EMS_A_IN には能力の行が無い（能力は未設定＝制限なし）。これは今回の変更の前からで、変えていない。

## 2. 助走行の作り方（`wom/engine/warmup._build_warm_lines`）

| | 新書式（変えていない） | 旧書式（今回加えた） |
|---|---|---|
| 元にする週 | 最初の需要のある週（real_start） | 同じ |
| 能力のキー | (`sku_id`, `node_name`) | 行そのもの（最初の実週の各行） |
| 作る行 | キーごとに 1 行。`max_supply` は最初の実週の値、`source` は `warmup`、ほかの列は空 | 最初の実週の各行を、`week` だけ替えて**そのまま**コピー（`region`・`cap_pieces`・`source` を保つ） |
| 並び | 週ごとに、キーの昇順 | 週ごとに、最初の実週の行の順 |
| 最初の実週に行が無い製品 | 助走行を作らない | 同じ（Phone17 は助走行なし） |
| 生成行の見分け方 | `week` が real_start より前（＋`source=warmup`） | `week` が real_start より前 |
| 必須の列が無いとき | — | `sku_id`・`week`・`max_supply` のどれかが無ければ、列名を示して `ValueError` |

旧書式で「行をそのままコピーする」理由：

- ローダが見る能力は (製品, 週) の合計なので、最初の実週の行をすべてコピーすれば、助走週の能力は最初の実週と同じになる。
- 同じ製品に複数の行（地域別・拠点別）があっても、混ざらず、合計も変わらない。
- `node_name` を足したり、`region` をノード名に読み替えたりしない（依頼書 A1 の禁止事項）。見出しは変えない。

smartphone-global-2026-2029 に入った助走行（`warmup_lt=26`）：

| ファイル | 助走行 | 週の範囲 | 中身 |
|---|---:|---|---|
| `capacity_plan.csv` | 52 | 2026-W28〜2026-W53 | 週ごとに 2 行：`Phone16,CN,<週>,800,,EMS_A_CN` と `Phone15,CN,<週>,500,,EMS_A_CN` |
| `demand_forecast.csv` | 156 | 2026-W28〜2026-W53 | 週ごとに 6 行：Phone16・Phone15 × AMER・EMEA・APAC、数量 0 |

実需要期間（2027-W01 以降）の行は、1 バイトも変えていない（差分は追加だけ）。

## 3. 対応していないもの（変えていない）

- `holiday_calendar.csv`・`push_config.csv`・`ppc_*.csv` は、warmup の対象外（設計どおり）。smartphone の休業（春節など）は、2027 年以降の週だけに定義されている。
- 新書式の助走行は、`cap_soft` 列を空にする（今回の変更の前から）。
