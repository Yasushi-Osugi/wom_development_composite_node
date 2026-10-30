# 報告書：BS-SEAF 化粧品の金額試行 M0-PPC（金額の仮定を規則のファイルに置く）

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun.md` v0.2（2026-10-30）
- 業務の仮定：`requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md`（本文 v0.2、§5.1 の M1〜M8）
- 実施：Code君（Claude Code）、2026-10-30
- 付録（再現用、git の追跡対象）：`docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/`

結果の名称は、依頼書 §1 のとおり「**今回対象にした費用を控除した PPC 試算利益**」とする（出力のキーは既存の `gross_profit_base` 等のまま）。数値は、採用済みの架空の仮定を WOM が意図どおり評価するかを確かめるための値で、「一般的な水準として妥当」と検証したものではない。

## 0. 結論

| 判定 | 結果 |
|---|---|
| **M0-PPC** | **完了**。M0・M0t・M0a の 3 ケースとも A1〜A8 をすべて満たした（§3）。A9 の明記と再現用データの保存は本報告と付録で行った |
| **M0-VC 観測** | **完了**。3 ケースとも実行は成功し、issues・未評価・保存の検査を記録した。G1〜G5 を金額と代表 Lot で示した（§6） |
| **M0-VC 業務要求** | **未完了**。Value Chain は売上の率の販売費（G1）と、外部の代理店に置いた自社負担の MDF（G2）を計上しない。代理店の売上は sell-in の業務定義と違う週に立つ（G3）。関税の課税価格・CIF の運賃の負担（G4・G5）も業務の定義と違う。Value Chain の利益は PPC の試算利益と一致しない（全期間で G1＋G2 の額だけ多い） |

結論と結果の表に必ず添えること（A9）：

- **M3**：原価に歩留まりの損（0.97）を入れていない。**原価は約 3% 低い**（原料・加工の 1 個当たりの単価を 1/0.97 倍していない。歩留まり Part B で入れる）。
- **M5**：直営店の店舗運営費は**売上の 35% での近似**。固定費として実装したものではない（売上が下がると費用も下がり、損益を良く見せる）。
- **M6**：日本本社の研究開発・グローバルなブランドの費用は**入れていない**。試算利益はグループの営業利益ではない。
- **関税の課税価格の仕様差（G4）**：現行 PPC は振替価格だけに課税する（1,800／1,500 円/個）。業務の定義（CIF）では 1,821／1,521 円/個になり、M0t で計 347,256 円の差がある。入力の単価は変えていない。
- **Value Chain は未完了**：上の M0-VC 業務要求の行のとおり。conservation 等が通っていても、除かれた費用を含む業務上の損益が正しいことの証明にはならない。

## 1. 着手時の記録

- **着手時の SHA**：`0b59da7`（依頼書 v0.2 の commit）。読み取り基準 `4824673` との間で `wom/`・`tools/`・`tests/`・`data/sample/` に差分は無い（`git diff --stat 4824673 0b59da7 -- wom tools tests data/sample` が空）。よって依頼書の指定はそのまま適用できると判断した。
- **作業ツリー**：着手時の未追跡は、この作業の前からある `docs/design/drafts/Cosmetic_model/` と `requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun_v0.2_GPT_Sample.md` だけ。
- **環境**：Windows 11、Python 3.12.3（Anaconda）、pandas 2.2.2、numpy 1.26.4。実行はリポジトリの根から。
- **読んだもの**：依頼書 v0.2、金額仮定書 §5.1、PPC の計算（`ppc_runner.py`・`ppc_forward.py`・`ppc_tariff.py`・`ppc_profit_zone.py`・`ppc_transfer.py`・`ppc_rules.py`・`ppc_psi_bridge.py`・`ppc_kpi.py`）、Value Chain の読み込みと台帳（`wom/valuechain/masters.py`・`ledger.py`・`policy.py`・`run.py`）、C3a・C3b の作成手順（`output/bsseaf_cosmetics/gen_models.py`）と変更課題①②③の報告書。

### 1.1 元モデルの由来と基準の固定

- 元モデル：`output/bsseaf_cosmetics/C3b`・`C3a`。`gen_models.py` が Cookie-jp-2026 から作った試行用のモデル（README）。C3a と C3b の違いは `capacity_plan.csv` だけ（C3b は A9 で能力を計算し直した版）。元は編集していない。
- 基準の取り直し：元を直接実行せず、入力だけを `money_m0_work/base/C3a`・`C3b` に写して、同じコード・同じプラグインで数量の計画を回した（`step1_base.py`）。写しは元と sha256 が一致し、実行で入力は 1 ファイルも変わらなかった。Flow Check 表1・表2 は、元の `C3a/_result`・`C3b/_result` の CSV とバイト単位で一致した。
- warmup の補完：元のフォルダには助走の行（`source=warmup`、2026-W37 から）が既に入っている。実行時の補完（`materialize_warmup`）は、元の写しでも M0・M0t・M0a でも入力のハッシュを変えなかった（＝補完は何もしなかった）。補完の前と後は同じ。

| 条件 | 値（C3a・C3b 共通） |
|---|---|
| 期間 | 2026-W37 から 173 週（2029-W52 まで）。助走 `warmup_lt=17` を含む |
| 報告開始週 | 2027-W01（`vc_config.csv`） |
| cpu_size | 24（1 lot ＝ 1 ケース ＝ 24 個） |
| lot_flow_mode | identity |
| プラグイン | `planning_config.csv` の `recommended_plugins`：HolidayCalendarPlugin, BufferingStockOptimizerPlugin, CapacityOverridePlugin |
| 需要・木・休業・能力 | 元の CSV のまま（ハッシュは §4 の T16） |

実行の経路：`tools.run_headless_from_folder.run()` に、計画後の木を受け取るだけの観測用のプラグイン（`Capture`、`on_post_plan` で木を保存する）を足した。需要の Lot_ID と実出荷（`_actual_ship`）を読むため。依頼書 §5 の手順 2 のコマンド（Capture なし）でも M0 を回し、PPC の台帳・KPI・Flow Check 表1・表2 がバイト単位で同じことを確かめた（観測は結果を変えない）。

## 2. 写しと金額の規則

| モデルフォルダ | 元 | 変更 | 数量の入力が元と同じ |
|---|---|---|---|
| `output/bsseaf_cosmetics/M0` | C3b | 金額の 10 ファイルを置いた。関税 0% | True |
| `output/bsseaf_cosmetics/M0t` | M0 | `WH_JP_Released->DC_TH` の関税率だけ 0 → 0.30 | True |
| `output/bsseaf_cosmetics/M0a` | C3a | M0 と同じ金額の 10 ファイル | True |

- 写しは入力だけ（`_result` と README を除く）。古い PPC・Value Chain の出力は混ざらない。
- 金額のファイルは `gen_money.py` が書いた。9 個の PPC 規則ファイルはすべてモデルの中（共有の規則に依存しない。D8 の `rule_sources` が 9 ファイルとも `model`）。値は依頼書 §3 の表のまま。試算利益を合わせるための調整はしていない。
- 価格・仕入原価・Value Chain の価格の有効開始週は、助走を含む実際の計画開始週 2026-W37。為替は実際の 173 週 × 4 通貨（JPY 1、SGD 115、THB 4.5、USD 150）。
- 木の ID の確認：ノード名・製品 ID は木と一致した（金額のファイルの名前で木に無いものは 0 件）。対応表は付録 `records/sku_node_map.csv`。供給点（`SP_COS_*`）には行を置いていない。
- CSV の `edge_id` の区切りは ASCII の `->`。関税の行：国境の 2 区間（日本→シンガポール、日本→タイ）は `transfer_price`。それ以外の物理区間の 0% の行は `material_cost`（依頼書 §3.5。税額 0 の行を安全に評価するための入力の指定で、国内輸送に課税の意味は無い）。
- 内訳は CSV の `note` に残した：直営店 45%＝店舗運営費 35%＋販社販管費 10%、EC の `sga_cost`＝決済・基盤手数料 5%＋販社販管費 10%＋配送梱包 SGD 3/個、EC の `marketing_cost`＝デジタル広告 15%、代理店の MDF 5%（負担者：SG はシンガポール販社、TH は日本本社）、DC の `conversion_cost` は取扱・通関等の 1 個当たりの仮定額（在庫保有費ではない）。

## 3. 受入条件 A1〜A9 の結果

値はすべて実行の後に `checks_ppc.json`・`checks_vc.json` から `step5_tables.py` で転記した。機械照合の許容差は依頼書 §7.1 のとおり（1 個当たり 0.000001 JPY、総額 max(0.01, 期待額×10^-9)）。表示は小数 2 桁に丸めているが、照合は丸める前の値で行った。

### T1 受入条件 A1〜A8（PPC）

| 条件 | M0 | M0t | M0a |
|---|---:|---:|---:|
| A1 | 合格 | 合格 | 合格 |
| A2 | 合格 | 合格 | 合格 |
| A3 | 合格 | 合格 | 合格 |
| A4 | 合格 | 合格 | 合格 |
| A5 | 合格 | 合格 | 合格 |
| A6 | 合格 | 合格 | 合格 |
| Lot_ID 数×24 ＝ PPC の qty（SKU×チャネル×週） | 合格（1118 記録） | 合格（1118 記録） | 合格（1063 記録） |
| §4.2 M0t と M0 の差 | — | 合格 | — |
| A7（M0a の未充足と売上差） | — | — | 合格 |
| A8（未設定の金額規則が無い） | 合格 | 合格 | 合格 |
| A4 の合成入力（1 個と 24 個） | 合格 | — | — |


| ID | 内容 | 結果 |
|---|---|---|
| A1 | 評価済み、除外なし、価格・仕入原価の欠けと最初の行より前の参照が 0 | 3 ケースとも `評価済み`、`excluded` 無し、`lookup_log` 空、`price_before_first_rule_week` 無し |
| A2 | 金額入力の出どころはモデルの中 | 9 ファイルとも `model`、共有の宣言なし、欠けなし。PPC の出力は、D8 の処理が前回の出力を消してから書く（集計の誤りで止まった実行を含め、同じ出力先で 3 回実行した。残っているのは最後の実行の出力だけ） |
| A3 | 8 通りの 1 個当たりが §4.1 と一致。M0t はタイだけ §4.2 の差、M0a は同じ単価 | 一致（差 0.000000）。全記録で 1 個当たりの値は同じ（記録の間のばらつき 0） |
| A4 | 24 個で 24 倍、EC の配送費と率の費用が 1 回だけ | 合成入力（各 SKU×チャネルで 1 個と 24 個）で売上・費用とも 24 倍、出る事象の種類は同じ、各費用の事象は記録ごとに 1 回。EC の `sga_cost` は 1 記録に 1 事象（1 個当たり 3,053.25 JPY＝(0.15×157＋3)×115）。モデル全体の台帳でも、どの記録も各費用の事象が 1 回 |
| A5 | 外部売上 − 各費用 ＝ 試算利益。台帳と全体 KPI が一致 | 3 ケースとも一致（§4 の T5） |
| A6 | 数量の入力が元と同じ。Flow Check 表1 の保存、表2 の明細が元と同じ | 入力のハッシュ一致、表1・表2 の CSV が基準の実行と一致、表1 は全ノード OK・保存の差 0 |
| A7 | M0a の未充足 104・88 lot、実出荷 92,736 個、売上差 36,547,200 JPY | 一致。要求 ID と実出荷 ID の集合差で確かめた（§4 の T8）。前提（元需要が同じ、M0 は全需要を満たす、タイ以外の実出荷が週ごとに同じ）も確かめた |
| A8 | 費用あり・明示の 0・仮想区間・未設定の対応表。必要なのに未設定が無い | 参照したのに行が無かった費用の規則は 0（§4 の T9） |
| A9 | M3・M5・M6、関税の仕様差、VC 未完了の明記、再現用データ | §0 と本節、付録 |

補足（A1）：`ppc_warnings.csv` は 3 ケースとも見出しだけ（価格・為替の代用の記録は 0 件）。

補足（数量と売上の照合）：PPC の `lot_id` は「PSI-製品-チャネル-週」の週次の集約記録。SKU×チャネル×実出荷週ごとに、数量側の `_actual_ship` の Lot_ID の数 ×24 が、PPC の `market_revenue` の qty と一致した（M0・M0t 1,118 記録、M0a 1,063 記録。逆向きの、実出荷の無い PPC 記録も 0）。売上の個数は `market_revenue` の qty を 1 回だけ合計した（費用の事象の qty は足していない）。

## 4. 結果の表

### T2 実行の条件（3 ケース共通の確認）

| 項目 | M0 | M0t | M0a |
|---|---:|---:|---:|
| 元 | C3b | M0（C3b） | C3a |
| 期間 | 2026-W37 から 173 週 | 2026-W37 から 173 週 | 2026-W37 から 173 週 |
| プラグイン（観測用の Capture を除く） | BufferingStockOptimizerPlugin, CapacityOverridePlugin, HolidayCalendarPlugin | BufferingStockOptimizerPlugin, CapacityOverridePlugin, HolidayCalendarPlugin | BufferingStockOptimizerPlugin, CapacityOverridePlugin, HolidayCalendarPlugin |
| 数量の入力が元と同じ（sha256） | True | True | True |
| 実行で入力が変わらなかった | True | True | True |
| valuation_status | 評価済み | 評価済み | 評価済み |
| 規則の出どころ | 9 ファイルとも model | 9 ファイルとも model | 9 ファイルとも model |

### T3 1 個当たり（JPY）：§4.1 の期待値と PPC の実行値

| SKU・チャネル | 売上 期待 | 売上 実行 | 費用 期待 | 費用 実行 | 利益 期待 | 利益 実行 | 最大の差 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 美容液 直営店 | 18,975.00 | 18,975.00 | 10,940.75 | 10,940.75 | 8,034.25 | 8,034.25 | 0.000000 |
| 美容液 公式 EC | 18,055.00 | 18,055.00 | 8,163.50 | 8,163.50 | 9,891.50 | 9,891.50 | 0.000000 |
| 美容液 代理店（SG） | 8,510.00 | 8,510.00 | 2,827.50 | 2,827.50 | 5,682.50 | 5,682.50 | 0.000000 |
| 美容液 代理店（TH） | 8,550.00 | 8,550.00 | 2,837.50 | 2,837.50 | 5,712.50 | 5,712.50 | 0.000000 |
| 美容液 代理店（TH）（M0t） | 8,550.00 | 8,550.00 | 4,637.50 | 4,637.50 | 3,912.50 | 3,912.50 | 0.000000 |
| クリーム 直営店 | 15,870.00 | 15,870.00 | 9,243.50 | 9,243.50 | 6,626.50 | 6,626.50 | 0.000000 |
| クリーム 公式 EC | 15,065.00 | 15,065.00 | 6,966.50 | 6,966.50 | 8,098.50 | 8,098.50 | 0.000000 |
| クリーム 代理店（SG） | 7,130.00 | 7,130.00 | 2,458.50 | 2,458.50 | 4,671.50 | 4,671.50 | 0.000000 |
| クリーム 代理店（TH） | 7,200.00 | 7,200.00 | 2,470.00 | 2,470.00 | 4,730.00 | 4,730.00 | 0.000000 |
| クリーム 代理店（TH）（M0t） | 7,200.00 | 7,200.00 | 3,970.00 | 3,970.00 | 3,230.00 | 3,230.00 | 0.000000 |

M0a の 8 行は M0 と同じ単価（A3 合格）。

### T4 1 個当たりの費用の内訳（M0、JPY）

| SKU・チャネル | 原料 | 加工 | 物理区間の運賃 | ノード費用（倉庫・DC） | 関税 | 販売費（チャネル） | 計 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 美容液 直営店 | 1,500.00 | 700.00 | 114.50 | 87.50 | 0.00 | 8,538.75 | 10,940.75 |
| 美容液 公式 EC | 1,500.00 | 700.00 | 114.50 | 87.50 | 0.00 | 5,761.50 | 8,163.50 |
| 美容液 代理店（SG） | 1,500.00 | 700.00 | 114.50 | 87.50 | 0.00 | 425.50 | 2,827.50 |
| 美容液 代理店（TH） | 1,500.00 | 700.00 | 126.00 | 84.00 | 0.00 | 427.50 | 2,837.50 |
| クリーム 直営店 | 1,300.00 | 600.00 | 114.50 | 87.50 | 0.00 | 7,141.50 | 9,243.50 |
| クリーム 公式 EC | 1,300.00 | 600.00 | 114.50 | 87.50 | 0.00 | 4,864.50 | 6,966.50 |
| クリーム 代理店（SG） | 1,300.00 | 600.00 | 114.50 | 87.50 | 0.00 | 356.50 | 2,458.50 |
| クリーム 代理店（TH） | 1,300.00 | 600.00 | 126.00 | 84.00 | 0.00 | 360.00 | 2,470.00 |

### T5-M0 SKU × チャネルの合計（全期間、JPY）

| SKU・チャネル | lot | 個 | 売上 | 費用 | 試算利益 |
|---|---:|---:|---:|---:|---:|
| 美容液 直営店 | 546 | 13,104 | 248,648,400 | 143,367,588 | 105,280,812 |
| 美容液 公式 EC | 455 | 10,920 | 197,160,600 | 89,145,420 | 108,015,180 |
| 美容液 代理店（SG） | 897 | 21,528 | 183,203,280 | 60,870,420 | 122,332,860 |
| 美容液 代理店（TH） | 390 | 9,360 | 80,028,000 | 26,559,000 | 53,469,000 |
| クリーム 直営店 | 416 | 9,984 | 158,446,080 | 92,287,104 | 66,158,976 |
| クリーム 公式 EC | 299 | 7,176 | 108,106,440 | 49,991,604 | 58,114,836 |
| クリーム 代理店（SG） | 754 | 18,096 | 129,024,480 | 44,489,016 | 84,535,464 |
| クリーム 代理店（TH） | 299 | 7,176 | 51,667,200 | 17,724,720 | 33,942,480 |
| **計（台帳）** | 4,056 | 97,344 | 1,156,284,480 | 524,434,872 | 631,849,608 |
| **全体 KPI** | — | 97,344 | 1,156,284,480 | 524,434,872 | 631,849,608 |

費用の内訳（台帳、JPY）：原料 137,529,600、加工 63,897,600、物理区間の運賃 11,336,052、ノード費用 8,459,724、関税 0、販売費 303,211,896。

### T5-M0t SKU × チャネルの合計（全期間、JPY）

| SKU・チャネル | lot | 個 | 売上 | 費用 | 試算利益 |
|---|---:|---:|---:|---:|---:|
| 美容液 直営店 | 546 | 13,104 | 248,648,400 | 143,367,588 | 105,280,812 |
| 美容液 公式 EC | 455 | 10,920 | 197,160,600 | 89,145,420 | 108,015,180 |
| 美容液 代理店（SG） | 897 | 21,528 | 183,203,280 | 60,870,420 | 122,332,860 |
| 美容液 代理店（TH） | 390 | 9,360 | 80,028,000 | 43,407,000 | 36,621,000 |
| クリーム 直営店 | 416 | 9,984 | 158,446,080 | 92,287,104 | 66,158,976 |
| クリーム 公式 EC | 299 | 7,176 | 108,106,440 | 49,991,604 | 58,114,836 |
| クリーム 代理店（SG） | 754 | 18,096 | 129,024,480 | 44,489,016 | 84,535,464 |
| クリーム 代理店（TH） | 299 | 7,176 | 51,667,200 | 28,488,720 | 23,178,480 |
| **計（台帳）** | 4,056 | 97,344 | 1,156,284,480 | 552,046,872 | 604,237,608 |
| **全体 KPI** | — | 97,344 | 1,156,284,480 | 552,046,872 | 604,237,608 |

費用の内訳（台帳、JPY）：原料 137,529,600、加工 63,897,600、物理区間の運賃 11,336,052、ノード費用 8,459,724、関税 27,612,000、販売費 303,211,896。

### T5-M0a SKU × チャネルの合計（全期間、JPY）

| SKU・チャネル | lot | 個 | 売上 | 費用 | 試算利益 |
|---|---:|---:|---:|---:|---:|
| 美容液 直営店 | 546 | 13,104 | 248,648,400 | 143,367,588 | 105,280,812 |
| 美容液 公式 EC | 455 | 10,920 | 197,160,600 | 89,145,420 | 108,015,180 |
| 美容液 代理店（SG） | 897 | 21,528 | 183,203,280 | 60,870,420 | 122,332,860 |
| 美容液 代理店（TH） | 286 | 6,864 | 58,687,200 | 19,476,600 | 39,210,600 |
| クリーム 直営店 | 416 | 9,984 | 158,446,080 | 92,287,104 | 66,158,976 |
| クリーム 公式 EC | 299 | 7,176 | 108,106,440 | 49,991,604 | 58,114,836 |
| クリーム 代理店（SG） | 754 | 18,096 | 129,024,480 | 44,489,016 | 84,535,464 |
| クリーム 代理店（TH） | 211 | 5,064 | 36,460,800 | 12,508,080 | 23,952,720 |
| **計（台帳）** | 3,864 | 92,736 | 1,119,737,280 | 512,135,832 | 607,601,448 |
| **全体 KPI** | — | 92,736 | 1,119,737,280 | 512,135,832 | 607,601,448 |

費用の内訳（台帳、JPY）：原料 131,040,000、加工 60,883,200、物理区間の運賃 10,755,444、ノード費用 8,072,652、関税 0、販売費 301,384,536。

### T6 費用の内訳の金額（M0、全期間、JPY）

| 項目 | 美容液 | クリーム | 計 |
|---|---:|---:|---:|
| 直営店 sga 45%（PPC） | 111,891,780 | 71,300,736 | 183,192,516 |
| 　うち店舗運営費 35%（固定費の近似、M5） | 87,026,940 | 55,456,128 | 142,483,068 |
| 　うち販社販管費 10% | 24,864,840 | 15,844,608 | 40,709,448 |
| EC の配送梱包 SGD 3/個（sga_cost に含む） | 3,767,400 | 2,475,720 | 6,243,120 |
| MDF（SG 代理店、負担候補 シンガポール販社） | 9,160,164 | 6,451,224 | 15,611,388 |
| MDF（TH 代理店、負担候補 日本本社） | 4,001,400 | 2,583,360 | 6,584,760 |

35% と 10% の内訳は、PPC の 1 行（45%）を報告で分けた計算（売上 × 0.35 / 0.10）。PPC はこの内訳を持たない。

### T7 M0t と M0（タイ関税 30%）

| 項目 | 美容液 | クリーム | 計 |
|---|---:|---:|---:|
| タイの実出荷（個） | 9,360 | 7,176 | 16,536 |
| 関税（JPY/個、PPC） | 1,800.00 | 1,500.00 | — |
| 利益の減少 期待（個×1,800／1,500） | — | — | 27,612,000 |
| 利益の減少 実行（M0 − M0t の全体 KPI） | — | — | 27,612,000 |

### T8 M0a（C3a の配分後）

| 項目 | 期待 | 実行 |
|---|---:|---:|
| 元需要①（lot） | 4,056 | 4,056 |
| 実出荷で満たした需要④（lot） | 3,864 | 3,864 |
| 期末未充足⑤（lot、要求 ID − 実出荷 ID） | 192（タイ 美容液 104・クリーム 88） | 美容液 104、クリーム 88 |
| M0 の未充足（lot） | 0 | 0 |
| 売上の対象（個、market_revenue の qty） | 92,736 | 92,736 |
| M0 との売上差 美容液（JPY） | 21,340,800 | 21,340,800 |
| M0 との売上差 クリーム（JPY） | 15,206,400 | 15,206,400 |
| M0 との売上差 計（JPY） | 36,547,200 | 36,547,200 |
| 前提：元需要が M0 と同じ | True | True |
| 前提：タイ以外の実出荷（SKU×チャネル×週）が M0 と同じ | True | True |
| 前提：実出荷の差（M0 − M0a、lot） | 192 | 192 |

代表 Lot：
- 美容液 `COS_Serum:TH_Distributor:2029-W25:00001`：需要週 2029-W25。M0 では 2029-W25 に実出荷され、PPC の週次記録 `PSI-COS_Serum-TH_Distributor-2029-W25`（qty 96）に入る。M0a では実出荷されず、同じ週次記録の qty は 記録なし（その週の実出荷 0）。
- クリーム `COS_Cream:TH_Distributor:2029-W21:00003`：需要週 2029-W21。M0 では 2029-W21 に実出荷され、PPC の週次記録 `PSI-COS_Cream-TH_Distributor-2029-W21`（qty 72）に入る。M0a では実出荷されず、同じ週次記録の qty は 48。

### T9 A8 金額規則の行と参照（M0）

| ファイル | ノード・区間 × 製品 | 費目（関税は課税価格の基準） | basis | 率 | 1 個当たりの額・価格 | 通貨 | 参照回数 | 状態 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ppc_node_cost_rule | Materials_JP × COS_Serum | conversion_cost | qty | 0 | 0 | JPY | 0 | 行はあるが計算が参照しない |
| ppc_node_cost_rule | Materials_JP × COS_Cream | conversion_cost | qty | 0 | 0 | JPY | 0 | 行はあるが計算が参照しない |
| ppc_node_cost_rule | Factory_JP × COS_Serum | conversion_cost | qty | 0 | 700 | JPY | 559 | 費用あり |
| ppc_node_cost_rule | Factory_JP × COS_Cream | conversion_cost | qty | 0 | 600 | JPY | 559 | 費用あり |
| ppc_node_cost_rule | WH_JP_Released × COS_Serum | warehouse_cost | qty | 0 | 30 | JPY | 1,118 | 費用あり |
| ppc_node_cost_rule | WH_JP_Released × COS_Cream | warehouse_cost | qty | 0 | 30 | JPY | 1,118 | 費用あり |
| ppc_node_cost_rule | DC_SG × COS_Serum | conversion_cost | qty | 0 | 0.5 | SGD | 910 | 費用あり |
| ppc_node_cost_rule | DC_SG × COS_Cream | conversion_cost | qty | 0 | 0.5 | SGD | 910 | 費用あり |
| ppc_node_cost_rule | DC_TH × COS_Serum | conversion_cost | qty | 0 | 12 | THB | 208 | 費用あり |
| ppc_node_cost_rule | DC_TH × COS_Cream | conversion_cost | qty | 0 | 12 | THB | 208 | 費用あり |
| ppc_node_cost_rule | SG_Store × COS_Serum | sga_cost | revenue | 0.45 | 0 | SGD | 286 | 費用あり |
| ppc_node_cost_rule | SG_Store × COS_Cream | sga_cost | revenue | 0.45 | 0 | SGD | 286 | 費用あり |
| ppc_node_cost_rule | SG_EC × COS_Serum | sga_cost | revenue | 0.15 | 3 | SGD | 312 | 費用あり |
| ppc_node_cost_rule | SG_EC × COS_Cream | sga_cost | revenue | 0.15 | 3 | SGD | 312 | 費用あり |
| ppc_node_cost_rule | SG_EC × COS_Serum | marketing_cost | revenue | 0.15 | 0 | SGD | 312 | 費用あり |
| ppc_node_cost_rule | SG_EC × COS_Cream | marketing_cost | revenue | 0.15 | 0 | SGD | 312 | 費用あり |
| ppc_node_cost_rule | SG_Distributor × COS_Serum | marketing_cost | revenue | 0.05 | 0 | SGD | 312 | 費用あり |
| ppc_node_cost_rule | SG_Distributor × COS_Cream | marketing_cost | revenue | 0.05 | 0 | SGD | 312 | 費用あり |
| ppc_node_cost_rule | TH_Distributor × COS_Serum | marketing_cost | revenue | 0.05 | 0 | THB | 208 | 費用あり |
| ppc_node_cost_rule | TH_Distributor × COS_Cream | marketing_cost | revenue | 0.05 | 0 | THB | 208 | 費用あり |
| ppc_edge_cost_rule | Materials_JP->Factory_JP × COS_Serum | logistics_cost | qty | 0 | 0 | JPY | 559 | 明示の 0 |
| ppc_edge_cost_rule | Materials_JP->Factory_JP × COS_Cream | logistics_cost | qty | 0 | 0 | JPY | 559 | 明示の 0 |
| ppc_edge_cost_rule | Factory_JP->WH_JP_Released × COS_Serum | logistics_cost | qty | 0 | 20 | JPY | 1,118 | 費用あり |
| ppc_edge_cost_rule | Factory_JP->WH_JP_Released × COS_Cream | logistics_cost | qty | 0 | 20 | JPY | 1,118 | 費用あり |
| ppc_edge_cost_rule | WH_JP_Released->DC_SG × COS_Serum | logistics_cost | qty | 0 | 60 | JPY | 910 | 費用あり |
| ppc_edge_cost_rule | WH_JP_Released->DC_SG × COS_Cream | logistics_cost | qty | 0 | 60 | JPY | 910 | 費用あり |
| ppc_edge_cost_rule | WH_JP_Released->DC_TH × COS_Serum | logistics_cost | qty | 0 | 70 | JPY | 208 | 費用あり |
| ppc_edge_cost_rule | WH_JP_Released->DC_TH × COS_Cream | logistics_cost | qty | 0 | 70 | JPY | 208 | 費用あり |
| ppc_edge_cost_rule | DC_SG->SG_Store × COS_Serum | logistics_cost | qty | 0 | 0.3 | SGD | 286 | 費用あり |
| ppc_edge_cost_rule | DC_SG->SG_Store × COS_Cream | logistics_cost | qty | 0 | 0.3 | SGD | 286 | 費用あり |
| ppc_edge_cost_rule | DC_SG->SG_EC × COS_Serum | logistics_cost | qty | 0 | 0.3 | SGD | 312 | 費用あり |
| ppc_edge_cost_rule | DC_SG->SG_EC × COS_Cream | logistics_cost | qty | 0 | 0.3 | SGD | 312 | 費用あり |
| ppc_edge_cost_rule | DC_SG->SG_Distributor × COS_Serum | logistics_cost | qty | 0 | 0.3 | SGD | 312 | 費用あり |
| ppc_edge_cost_rule | DC_SG->SG_Distributor × COS_Cream | logistics_cost | qty | 0 | 0.3 | SGD | 312 | 費用あり |
| ppc_edge_cost_rule | DC_TH->TH_Distributor × COS_Serum | logistics_cost | qty | 0 | 8 | THB | 208 | 費用あり |
| ppc_edge_cost_rule | DC_TH->TH_Distributor × COS_Cream | logistics_cost | qty | 0 | 8 | THB | 208 | 費用あり |
| ppc_tariff_rule | Materials_JP->Factory_JP × COS_Serum | material_cost |  | 0 |  |  | 0 | 行はあるが計算が参照しない |
| ppc_tariff_rule | Materials_JP->Factory_JP × COS_Cream | material_cost |  | 0 |  |  | 0 | 行はあるが計算が参照しない |
| ppc_tariff_rule | Factory_JP->WH_JP_Released × COS_Serum | material_cost |  | 0 |  |  | 1,118 | 明示の 0 |
| ppc_tariff_rule | Factory_JP->WH_JP_Released × COS_Cream | material_cost |  | 0 |  |  | 1,118 | 明示の 0 |
| ppc_tariff_rule | WH_JP_Released->DC_SG × COS_Serum | transfer_price |  | 0 |  |  | 910 | 明示の 0 |
| ppc_tariff_rule | WH_JP_Released->DC_SG × COS_Cream | transfer_price |  | 0 |  |  | 910 | 明示の 0 |
| ppc_tariff_rule | WH_JP_Released->DC_TH × COS_Serum | transfer_price |  | 0 |  |  | 208 | 明示の 0 |
| ppc_tariff_rule | WH_JP_Released->DC_TH × COS_Cream | transfer_price |  | 0 |  |  | 208 | 明示の 0 |
| ppc_tariff_rule | DC_SG->SG_Store × COS_Serum | material_cost |  | 0 |  |  | 286 | 明示の 0 |
| ppc_tariff_rule | DC_SG->SG_Store × COS_Cream | material_cost |  | 0 |  |  | 286 | 明示の 0 |
| ppc_tariff_rule | DC_SG->SG_EC × COS_Serum | material_cost |  | 0 |  |  | 312 | 明示の 0 |
| ppc_tariff_rule | DC_SG->SG_EC × COS_Cream | material_cost |  | 0 |  |  | 312 | 明示の 0 |
| ppc_tariff_rule | DC_SG->SG_Distributor × COS_Serum | material_cost |  | 0 |  |  | 312 | 明示の 0 |
| ppc_tariff_rule | DC_SG->SG_Distributor × COS_Cream | material_cost |  | 0 |  |  | 312 | 明示の 0 |
| ppc_tariff_rule | DC_TH->TH_Distributor × COS_Serum | material_cost |  | 0 |  |  | 208 | 明示の 0 |
| ppc_tariff_rule | DC_TH->TH_Distributor × COS_Cream | material_cost |  | 0 |  |  | 208 | 明示の 0 |
| ppc_transfer_price_rule | Factory_JP × COS_Serum |  |  |  | 6000 | JPY | 2,236 | 価格あり（費用ではない。関税の課税価格に使う） |
| ppc_transfer_price_rule | Factory_JP × COS_Cream |  |  |  | 5000 | JPY | 2,236 | 価格あり（費用ではない。関税の課税価格に使う） |

M0t の関税の行（M0 と違うのはタイの 2 行だけ）：WH_JP_Released->DC_TH × COS_Serum 率 0.3（参照 208、費用あり）、WH_JP_Released->DC_TH × COS_Cream 率 0.3（参照 208、費用あり）。

参照したのに行が無かった費用の規則：なし。利益ゾーンの 2 ファイルは見出しだけ（依頼書 §3.1 で可）なので、利益ゾーンの参照 18 組合せは既定の区分（OPERATION_NODE_COST_BASE）になった。仮想ノード（SP_COS_*）には行を置いておらず、計算も参照しない。


読み方（A8）：

- **行はあるが計算が参照しない** 4 行：`Materials_JP` のノードの費用（PPC は供給者のノードの費用を読まない。原料は仕入原価で計上）と、`Materials_JP->Factory_JP` の関税（PPC は供給者 → 工場の区間の関税を計算しない）。M7 のとおり明示の 0 として置いたが、今の PPC の経路では効かない。必要なのに未設定の金額ではない。
- 利益ゾーンの 2 ファイルは見出しだけ（依頼書 §3.1 で可）。試算利益の計算には使われない（区分の名前だけ）。

### T16 元モデルと写しの数量入力（sha256）

| 元 | ファイル | sha256（先頭 16 桁） | 写し（M0・M0a） |
|---|---:|---:|---:|
| C3b | capacity_plan.csv | aaa92bea0e851637… | 同じ |
| C3b | decouple_optimizer_config.csv | a625f7b091f2ac3f… | 同じ |
| C3b | demand_forecast.csv | b9ae795e4a713cd8… | 同じ |
| C3b | edge_cost_master.csv | 487e0f78228b64d1… | 同じ |
| C3b | holiday_calendar.csv | f4f29af5821b1694… | 同じ |
| C3b | inventory_master.csv | 6101c4b4c2a1028e… | 同じ |
| C3b | lane_assignment.csv | 281e56a90b09e3e7… | 同じ |
| C3b | node_cost_master.csv | 0c383b787c646bb6… | 同じ |
| C3b | node_master.csv | 52256777e1708d1a… | 同じ |
| C3b | planning_config.csv | c12cacd0c740832a… | 同じ |
| C3b | push_config.csv | 625b14e65944a951… | 同じ |
| C3b | route_master.csv | 4dc9750285d9acbf… | 同じ |
| C3b | sc_tree_master.csv | 839b1a72cde594ed… | 同じ |
| C3b | sku_master.csv | 14b6719df3b1bdd9… | 同じ |
| C3b | vc_config.csv | e5867d9d877f292f… | 同じ |
| C3b | vc_entity.csv | 293da8938ec45a6c… | 同じ |
| C3b | vc_node_assignment.csv | cd53da9670344f7d… | 同じ |
| C3a | capacity_plan.csv | 2ca7cf34b3c0719b… | 同じ |
| C3a | decouple_optimizer_config.csv | a625f7b091f2ac3f… | 同じ |
| C3a | demand_forecast.csv | b9ae795e4a713cd8… | 同じ |
| C3a | edge_cost_master.csv | 487e0f78228b64d1… | 同じ |
| C3a | holiday_calendar.csv | f4f29af5821b1694… | 同じ |
| C3a | inventory_master.csv | 6101c4b4c2a1028e… | 同じ |
| C3a | lane_assignment.csv | 281e56a90b09e3e7… | 同じ |
| C3a | node_cost_master.csv | 0c383b787c646bb6… | 同じ |
| C3a | node_master.csv | 52256777e1708d1a… | 同じ |
| C3a | planning_config.csv | c12cacd0c740832a… | 同じ |
| C3a | push_config.csv | 625b14e65944a951… | 同じ |
| C3a | route_master.csv | 4dc9750285d9acbf… | 同じ |
| C3a | sc_tree_master.csv | 839b1a72cde594ed… | 同じ |
| C3a | sku_master.csv | 14b6719df3b1bdd9… | 同じ |
| C3a | vc_config.csv | e5867d9d877f292f… | 同じ |
| C3a | vc_entity.csv | 293da8938ec45a6c… | 同じ |
| C3a | vc_node_assignment.csv | cd53da9670344f7d… | 同じ |


## 5. MDF・EC の配送費・関税の差額・M0a の売上差（まとめ）

| 項目 | 金額（JPY、全期間） | 出典 |
|---|---:|---|
| MDF の自社負担（SG 代理店、負担候補 シンガポール販社） | 15,611,388 | T6 |
| MDF の自社負担（TH 代理店、負担候補 日本本社） | 6,584,760 | T6 |
| EC の配送梱包（SGD 3/個） | 6,243,120 | T6 |
| 直営店の店舗運営費 35%（近似）／販社販管費 10% | 142,483,068 ／ 40,709,448 | T6 |
| タイ関税 30% による利益の減少（M0t） | 27,612,000 | T7 |
| 関税の課税価格を CIF にした場合の追加（M0t、G4） | 347,256 | T14 |
| M0a の M0 との売上差 | 36,547,200 | T8 |

## 6. Value Chain との違い（G1〜G5）

Value Chain は 3 ケースとも `--plugins "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"`（モデルの `recommended_plugins`）で回した。計画が PPC の試行と同じことは、Value Chain が内部で作る PPC の台帳が PPC の試行のものとバイト単位で同じこと、消費者への販売の件数が実出荷と同じことで確かめた。

### T10 Value Chain の実行（観測）

| 項目 | M0 | M0t | M0a |
|---|---:|---:|---:|
| 実行 | OK | OK | OK |
| 計画が PPC 試行と同じ（PPC 台帳の sha256） | True | True | True |
| 消費者への販売の件数 ＝ 実出荷 | True | True | True |
| 保存の検査（conservation） | True（346 行） | True（346 行） | True（346 行） |
| 価格の欠け・未評価の明細 | 0・0 | 0・0 | 0・0 |
| 為替の代用（最初の週・未評価） | 0・0 | 0・0 | 0・0 |
| issues | revenue_based_node_cost_not_supported SG_EC sga_cost：754<br>revenue_based_node_cost_not_supported SG_EC marketing_cost：754<br>revenue_based_node_cost_not_supported SG_Store sga_cost：962 | revenue_based_node_cost_not_supported SG_EC sga_cost：754<br>revenue_based_node_cost_not_supported SG_EC marketing_cost：754<br>revenue_based_node_cost_not_supported SG_Store sga_cost：962 | revenue_based_node_cost_not_supported SG_EC sga_cost：754<br>revenue_based_node_cost_not_supported SG_EC marketing_cost：754<br>revenue_based_node_cost_not_supported SG_Store sga_cost：962 |
| PPC との比較 | 比較した | 比較した | 比較した |

### T11-M0 Value Chain の PPC との比較（vc_ppc_comparison.csv、全期間、JPY）

| 項目 | PPC | 台帳 V3 | 台帳 − PPC |
|---|---:|---:|---:|
| 売上 合計（額の分かる外部売上） | 1,156,284,480 | 1,156,284,480 | 0 |
| 費用 仕入（供給者） | 137,529,600 | 137,529,600 | 0 |
| 費用 加工・取扱 | 69,437,004 | 69,437,004 | 0 |
| 費用 運賃 | 11,336,052 | 11,336,052 | 0 |
| 費用 関税 | 0 | 0 | 0 |
| 費用 保険 | 0 | 0 | 0 |
| 費用 保管 | 2,920,320 | 2,920,320 | 0 |
| 費用 SGA | 235,225,692 | 0 | -235,225,692 |
| 費用 販促 | 67,986,204 | 0 | -67,986,204 |
| 原価 合計（PPC：総原価／台帳：外部売上の原価＋費用） | 524,434,872 | 501,998,016 | -22,436,856 |
| 内部取引の利益（消去前） | 0 | 280,775,040 | 280,775,040 |
| 利益 合計（全期間、消去前） | 631,849,608 | 935,061,504 | 303,211,896 |

### T11-M0t Value Chain の PPC との比較（vc_ppc_comparison.csv、全期間、JPY）

| 項目 | PPC | 台帳 V3 | 台帳 − PPC |
|---|---:|---:|---:|
| 売上 合計（額の分かる外部売上） | 1,156,284,480 | 1,156,284,480 | 0 |
| 費用 仕入（供給者） | 137,529,600 | 137,529,600 | 0 |
| 費用 加工・取扱 | 69,437,004 | 69,437,004 | 0 |
| 費用 運賃 | 11,336,052 | 11,336,052 | 0 |
| 費用 関税 | 27,612,000 | 27,612,000 | 0 |
| 費用 保険 | 0 | 0 | 0 |
| 費用 保管 | 2,920,320 | 2,920,320 | 0 |
| 費用 SGA | 235,225,692 | 0 | -235,225,692 |
| 費用 販促 | 67,986,204 | 0 | -67,986,204 |
| 原価 合計（PPC：総原価／台帳：外部売上の原価＋費用） | 552,046,872 | 529,610,016 | -22,436,856 |
| 内部取引の利益（消去前） | 0 | 280,775,040 | 280,775,040 |
| 利益 合計（全期間、消去前） | 604,237,608 | 907,449,504 | 303,211,896 |

### T11-M0a Value Chain の PPC との比較（vc_ppc_comparison.csv、全期間、JPY）

| 項目 | PPC | 台帳 V3 | 台帳 − PPC |
|---|---:|---:|---:|
| 売上 合計（額の分かる外部売上） | 1,119,737,280 | 1,119,737,280 | 0 |
| 費用 仕入（供給者） | 131,040,000 | 131,040,000 | 0 |
| 費用 加工・取扱 | 66,173,772 | 66,173,772 | 0 |
| 費用 運賃 | 10,755,444 | 10,755,444 | 0 |
| 費用 関税 | 0 | 0 | 0 |
| 費用 保険 | 0 | 0 | 0 |
| 費用 保管 | 2,782,080 | 2,782,080 | 0 |
| 費用 SGA | 235,225,692 | 0 | -235,225,692 |
| 費用 販促 | 66,158,844 | 0 | -66,158,844 |
| 原価 合計（PPC：総原価／台帳：外部売上の原価＋費用） | 512,135,832 | 491,526,336 | -20,609,496 |
| 内部取引の利益（消去前） | 0 | 280,775,040 | 280,775,040 |
| 利益 合計（全期間、消去前） | 607,601,448 | 908,985,984 | 301,384,536 |


| ID | 今回の表現 | 実行結果 | 不足額・出来事 | 後続の設計対象 |
|---|---|---|---|---|
| G1 売上比率の費用 | 直営店 `sga_cost` 45%、EC `sga_cost` 15%＋SGD 3/個、EC `marketing_cost` 15%（すべて `basis=revenue`） | Value Chain は該当する lot ごとに `revenue_based_node_cost_not_supported` を issues に出し、**行全体**を計上しない（M0：直営店 962、EC は 2 費目 × 754。両 SKU の lot 数） | M0・M0t・M0a とも 281,015,748。**EC の 1 個当たり SGD 3（数量に比例、計 6,243,120）も、同じ行の `basis=revenue` のため一緒に落ちる** | 売上の事象を基準に率 × 売上を計上し、受入時の二重計上を防ぐ仕様。費目を分けるか（依頼書 §10.4 の申し送り） |
| G2 MDF の負担者 | 代理店のノードの `marketing_cost` 5% | 計上されない。**issues にも出ない**（外部の代理店の lot はノードの費用の処理の前に抜ける。`ledger.py` `_node_costs` の `rec.external`）。G1 と違い、気づける記録が残らない | M0・M0t 22,196,148、M0a 20,368,788。負担候補の内訳は §5 | 外部取引・対象チャネル・支払法人・計上週を結ぶ販売費の表現。代理店を自社の法人にしない |
| G3 sell-in の数量と売上週 | 代理店の需要は sell-in。PPC は代理店の leaf の実出荷週に卸価格で売上 | Value Chain は **DC の出荷週**に、DC のノード（`DC_SG`・`DC_TH`）で卸価格の売上を立てる。代理店の leaf では、同じ卸価格で「観測の販売」を記録する（`observation_sale`、グループの売上に足さない） | 全 lot で **Value Chain の売上週が PPC より 1 週早い**（DC の出荷 → 1 週後に代理店が受け入れ、同じ週に leaf が出荷）。全期間の合計は同じ（T13）。M0a の未充足 192 lot は Value Chain にも出荷・売上の行が無い。**観測の販売の単価は卸価格**（PPC 向けに `ppc_market_price.csv` に置いたため）で、消費者価格・小売売上の参考値ではない | 代理店の需要が sell-in か sell-out か、受渡点、売上の事象、価格の用途の対応。leaf の観測価格を消費者価格と呼ばない |
| G4 関税の課税価格 | タイの関税 30%、`tariff_basis=transfer_price`（振替価格 6,000／5,000） | PPC・Value Chain とも振替価格 × 30%（1,800／1,500 円/個）。Value Chain は日本本社の `DC_TH` の在庫原価（acquisition）に入れる。M0t の合計は両方 27,612,000 | CIF（6,000／5,000＋海上運賃 70）なら 1,821／1,521 円/個、差 21 円/個、計 347,256（T14）。タイの化粧品の関税は CIF に課される（JETRO、仮定書 §4.3 の出典）ので、業務の定義は CIF、現行 PPC は振替価格だけ、という差 | 法人間の価格と税関の課税価格を別の概念として持つ。CIF を評価するなら運賃・保険の加算の条件を決める。今回の入力単価は変えていない（6,000 を 6,070 にしていない） |
| G5 CIF の運賃の負担と期間 | 仮定では、日本本社が海上運賃を負担して法人間の価格（CIF 6,000／5,000）に含める | Value Chain は `WH_JP_Released->DC_SG` の運賃 60 円/個を、受け手の**シンガポール販社の在庫原価**（acquisition）に入れる（T15）。法人間の価格 6,000／5,000 にも上乗せ | 全期間で 4,848,480（80,808 個 × 60）が、CIF の定義なら日本本社の費用のところ、シンガポール販社の原価になっている。グループの合計は変わらない（運賃の合計は PPC と同じ）。期間：報告開始の前の週の末に 4,320 分がシンガポール販社の在庫に残り、最後の週の末には 0 | 運賃の支払・負担法人と、在庫原価への算入を区別して設計する。今の法人別の損益を CIF 前提の完成した損益と呼ばない |

この表は、Value Chain に一般の機能が無いと一括して断定するものではない。読み取り基準と今回の実行経路で確かめた不足の記録である。別の経路で表せるものは見つからなかった（ノードの費目は `policy.py` の `COST_POLICY` にある conversion・logistics・warehouse・sga・marketing の 5 種と在庫の保有費だけ、ノードの費用は `basis=revenue` を計算しない、外部の法人の lot のノードの費用は計上しない、区間の運賃は「受け手が負担（在庫原価）」と決めている。いずれも `wom/valuechain/` のコードで確認）。

### T12 G1・G2：Value Chain に入らない販売費（M0、全期間、JPY）

| G | SKU | ノード | 費目 | PPC | Value Chain | 入らない額 | issues（両 SKU の lot 数） | 負担の候補 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| G1 | クリーム | SG_EC | marketing_cost | 16,215,966 | 0 | 16,215,966 | 754 | E_SG（シンガポール販社） |
| G1 | 美容液 | SG_EC | marketing_cost | 29,574,090 | 0 | 29,574,090 | 754 | E_SG（シンガポール販社） |
| G1 | クリーム | SG_EC | sga_cost | 18,691,686 | 0 | 18,691,686 | 754 | E_SG（シンガポール販社） |
| G1 | 美容液 | SG_EC | sga_cost | 33,341,490 | 0 | 33,341,490 | 754 | E_SG（シンガポール販社） |
| G1 | クリーム | SG_Store | sga_cost | 71,300,736 | 0 | 71,300,736 | 962 | E_SG（シンガポール販社） |
| G1 | 美容液 | SG_Store | sga_cost | 111,891,780 | 0 | 111,891,780 | 962 | E_SG（シンガポール販社） |
| G2 | クリーム | SG_Distributor | marketing_cost | 6,451,224 | 0 | 6,451,224 | 0 | E_SG（シンガポール販社） |
| G2 | 美容液 | SG_Distributor | marketing_cost | 9,160,164 | 0 | 9,160,164 | 0 | E_SG（シンガポール販社） |
| G2 | クリーム | TH_Distributor | marketing_cost | 2,583,360 | 0 | 2,583,360 | 0 | E_JP（日本本社） |
| G2 | 美容液 | TH_Distributor | marketing_cost | 4,001,400 | 0 | 4,001,400 | 0 | E_JP（日本本社） |

M0：G1 281,015,748 ＋ G2 22,196,148 ＝ 303,211,896。Value Chain と PPC の利益の差（全期間） 303,211,896。

M0t：G1 281,015,748 ＋ G2 22,196,148 ＝ 303,211,896。Value Chain と PPC の利益の差（全期間） 303,211,896。

M0a：G1 281,015,748 ＋ G2 20,368,788 ＝ 301,384,536。Value Chain と PPC の利益の差（全期間） 301,384,536。

### T13 G3：代理店の売上の週（代表 Lot、M0）

| SKU・チャネル | Lot_ID | DC の出荷週 | 代理店の受入週（P） | 代理店 leaf の実出荷週（S） | VC の売上週（計上ノード、単価） | VC の観測の週（単価） | PPC の売上週（単価） |
|---|---:|---:|---:|---:|---:|---:|---:|
| クリーム 代理店（SG） | `COS_Cream:SG_Distributor:2028-W29:00002` | 2028-W28 | 2028-W29 | 2028-W29 | 2028-W28（DC_SG、SGD 62） | 2028-W29（62） | 2028-W29（62） |
| 美容液 代理店（SG） | `COS_Serum:SG_Distributor:2028-W30:00006` | 2028-W29 | 2028-W30 | 2028-W30 | 2028-W29（DC_SG、SGD 74） | 2028-W30（74） | 2028-W30（74） |
| クリーム 代理店（TH） | `COS_Cream:TH_Distributor:2029-W03:00003` | 2029-W02 | 2029-W03 | 2029-W03 | 2029-W02（DC_TH、THB 1600） | 2029-W03（1600） | 2029-W03（1600） |
| 美容液 代理店（TH） | `COS_Serum:TH_Distributor:2029-W04:00003` | 2029-W03 | 2029-W04 | 2029-W04 | 2029-W03（DC_TH、THB 1900） | 2029-W04（1900） | 2029-W04（1900） |

- M0：VC の売上週 − PPC の売上週（週）の分布 クリーム 代理店（SG） 754 lot：{'1': 754}、美容液 代理店（SG） 897 lot：{'1': 897}、クリーム 代理店（TH） 299 lot：{'1': 299}、美容液 代理店（TH） 390 lot：{'1': 390}。代理店の売上の全期間の合計 VC 443,922,960 ／ PPC 443,922,960、週の値が違う週 5、最大の差 3,420,240。
- M0t：VC の売上週 − PPC の売上週（週）の分布 クリーム 代理店（SG） 754 lot：{'1': 754}、美容液 代理店（SG） 897 lot：{'1': 897}、クリーム 代理店（TH） 299 lot：{'1': 299}、美容液 代理店（TH） 390 lot：{'1': 390}。代理店の売上の全期間の合計 VC 443,922,960 ／ PPC 443,922,960、週の値が違う週 5、最大の差 3,420,240。
- M0a：VC の売上週 − PPC の売上週（週）の分布 クリーム 代理店（SG） 754 lot：{'1': 754}、美容液 代理店（SG） 897 lot：{'1': 897}、クリーム 代理店（TH） 211 lot：{'1': 211}、美容液 代理店（TH） 286 lot：{'1': 286}。代理店の売上の全期間の合計 VC 407,375,760 ／ PPC 407,375,760、週の値が違う週 9、最大の差 3,420,240。
- M0a の未充足 Lot：美容液 104 lot（Value Chain の出荷の行 0、売上の明細 0、例 `COS_Serum:TH_Distributor:2029-W25:00001`）、クリーム 88 lot（Value Chain の出荷の行 0、売上の明細 0、例 `COS_Cream:TH_Distributor:2029-W21:00003`）。

### T14 G4：タイの関税の課税価格（M0t）

| SKU | タイの実出荷（個） | PPC（振替価格×30%） | CIF の仮定（（振替価格＋70）×30%） | 差/個 | PPC 計 | CIF 計 | 差 計 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 美容液 | 9,360 | 1,800.00 | 1,821.00 | 21.00 | 16,848,000 | 17,044,560 | 196,560 |
| クリーム | 7,176 | 1,500.00 | 1,521.00 | 21.00 | 10,764,000 | 10,914,696 | 150,696 |
| 計 | 16,536 |  |  |  | 27,612,000 | 27,959,256 | 347,256 |

Value Chain（M0t）の関税の合計：27,612,000（明細：E_JP DC_TH acquisition 27,612,000）。

### T15 G5：CIF の海上運賃（WH_JP_Released → DC_SG、M0）

| 項目 | 値 |
|---|---:|
| Value Chain の運賃の明細 | 3367 行、法人 E_SG、種類 acquisition |
| 金額（JPY） | 4,848,480（80,808 個 × 60.00） |
| 報告開始の前の週の末に E_SG の在庫に残る運賃 | 3 lot、4,320 JPY |
| 最後の週の末に E_SG の在庫に残る運賃 | 0 lot、0 JPY |


## 7. 再現の方法

付録 `docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/`：

| フォルダ | 中身 |
|---|---|
| `scripts/` | 生成・実行・集計のスクリプトの完全な内容（`m0_common.py`、`step1_base.py`、`gen_money.py`、`step2_run.py`、`step4_vc.py`、`step5_tables.py`） |
| `money_csv/M0/` | M0 の金額の 10 ファイル（M0a も同じ内容。M0t は関税のファイルだけ違う） |
| `money_csv/M0t/` | M0t の `ppc_tariff_rule.csv` |
| `records/` | 基準の記録（`base_record.json`：期間・プラグイン・数量入力の sha256・需要と実出荷の lot 数）、写しの記録（`gen_record.json`）、SKU とノードの対応表、A4 の合成入力と結果 |

手順（リポジトリの根から。スクリプトは `output/bsseaf_cosmetics/money_m0_work/` に置いて実行する。出力はすべて `output/` の下で、git の対象外）：

```text
python output/bsseaf_cosmetics/money_m0_work/step1_base.py      # 基準（C3a・C3b の写し）の計画と記録
python output/bsseaf_cosmetics/money_m0_work/gen_money.py       # M0・M0t・M0a と金額のファイル
python output/bsseaf_cosmetics/money_m0_work/step2_run.py       # PPC：A1〜A8、合成入力、M0t・M0a の照合
python -m tools.run_headless_from_folder --model-dir output/bsseaf_cosmetics/M0 --out output/bsseaf_cosmetics/money_m0_work/M0_snapshot.json --ppc-out output/bsseaf_cosmetics/money_m0_work/M0_ppc --flow-check-out output/bsseaf_cosmetics/money_m0_work/flow_check --quiet
python -m tools.valuechain_run --model-dir output/bsseaf_cosmetics/M0  --out output/bsseaf_cosmetics/money_m0_work/M0_vc  --plugins "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
python -m tools.valuechain_run --model-dir output/bsseaf_cosmetics/M0t --out output/bsseaf_cosmetics/money_m0_work/M0t_vc --plugins "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
python -m tools.valuechain_run --model-dir output/bsseaf_cosmetics/M0a --out output/bsseaf_cosmetics/money_m0_work/M0a_vc --plugins "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
python output/bsseaf_cosmetics/money_m0_work/step4_vc.py        # G1〜G5
python output/bsseaf_cosmetics/money_m0_work/step5_tables.py    # 本報告の表
```

`gen_money.py` は、基準の実行が書く `money_m0_work/base/week_labels.json`（実際の 173 週）から計画開始週と為替の週を作る。元の C3a・C3b が無い場合は、`output/bsseaf_cosmetics/gen_models.py` で作り直せる（今回は元がそのまま有った）。

## 8. BS-SEAF の記録

| 項目 | 内容 |
|---|---|
| 再利用した知識 | D8（規則の出どころの記録、評価の状態、`lookup_log`）。R7（PPC の単価は物量当たり）。C3 の試行の実行の型（`run_headless_from_folder.run` に木を受け取るプラグインを足す）。Flow Check 表1・表2。D8 の B.2 の調査で作った、規則の参照を数える包み方 |
| 入口から辿った経路 | 依頼書 v0.2 → 金額仮定書 §5.1 → PPC のコード（区間の列 `walk_ancestor_chain` が DAD だけで供給点を含まないこと、DAD 間の区間の関税、チャネルの率の費用、移転価格 `fixed`）→ Value Chain の読み込み（重複・ノードの運賃・価格の二重を止める検査）→ 台帳（`_node_costs`） |
| Data で済んだ範囲 | M0-PPC のすべて（価格・原価・運賃・ノードの費用・販売費・関税の感度・為替）。標準のコードは変えていない |
| 追加の設計が要る範囲 | G1〜G5（Value Chain の金額の層）。加えて、PPC で明示の 0 を置いても参照されない 2 種類の行（供給者のノードの費用、供給者 → 工場の関税） |
| 予想と結果 | 依頼書の期待値（§4.1 の 8 通り、§4.2 の 1,800／1,500 と 27,612,000、§4.3 の 104・88 lot と 36,547,200）は、モデル全体の実行でもすべて丸める前の値で一致した。GPT君の合成入力での確認が、モデル全体でも成り立った |
| 予想していなかったこと | (1) G2 は issues にも出ない（G1 は出る）。(2) G1 で、EC の 1 個当たりの配送費（数量に比例）も、同じ行の基準が売上なので一緒に落ちる。(3) M7 の明示の 0 の行のうち 4 行は、PPC の今の経路が参照しない。(4) Value Chain と PPC の全期間の利益の差は、ちょうど G1＋G2 の額（3 ケースとも）で、それ以外の費目は全期間の合計で一致した |

## 9. Claude君へ返す知識の更新の材料（実行の根拠）

整理は Claude君にお願いする。Code君からは根拠だけ挙げる。

- 化粧品の事例の仮定（単価・為替・近似・期間・法人）：付録の `money_csv/` と §2。
- 再利用できる業務知識の候補：「数量に比例する費用も、売上の率と同じ行に置くと、率を計算しない仕組みでは一緒に落ちる」（G1 の (2)）。sell-in の代理店では、PPC（leaf の実出荷）と Value Chain（DC の出荷）で売上の週が 1 週ずれる（G3）。
- WOM への対応の設計：G1〜G5 の表（§6）。PPC で参照されない明示の 0 の行（§4 の A8 の読み方）。
- 採否と根拠の確認状態：本報告は新しい会計の方針を採用したものではない。

## 10. 変更の範囲と git

- 標準のコード・テスト・サンプル・golden は変えていない。最後に `git status` で `wom/`・`tools/`・`tests/`・`data/sample/` に変更が無いことを確かめた（§10.1）。全テストは、標準の試行のため依頼書 §5 の手順 5 のとおり実行していない。本試行を保護対象のコアの改修を検証した記録に読み替えないこと。
- 写し・実行結果・作業用スクリプトは `output/bsseaf_cosmetics/`（git の対象外）。git に残すのは本報告と付録だけ。
- commit メッセージの下書き：`commit_msg144.txt`。commit・push は大杉さんが行う。

### 10.1 git status（作業の終わり）

```text
$ git status --short -- wom tools tests data/sample
（出力なし＝変更なし）

$ git status --short
?? docs/design/drafts/Cosmetic_model/
?? docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/
?? requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun_v0.2_GPT_Sample.md
（本報告書は、この確認の後に書いたので一覧に無い。docs/design/drafts/ と requests/…_GPT_Sample.md は着手前からある未追跡で、本作業では追加しない）
```
