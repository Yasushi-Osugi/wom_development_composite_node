# 段階 D（金額編）第 1 回 報告書 — Value Chain の台帳

- 依頼：`requests/RequestLetter_StageD_Phase1_to_CodeKun.md`
- 設計：`docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md`
- 前提の調査：`docs/development/WOM_StageD_Survey_Report.md`
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- **着手時の SHA：`2b19685`**（`2b19685774c6030b5664b853a3ccb1d25c44ca7b`）。commit・push はしていない。
- Python 3.12（anaconda）、Windows 11、画面は DPI を意識しない窓（`python -m main` と同じ）1536×824。

## 0. 要約

| | 結果 |
|---|---|
| Part 0 | 0-1〜0-5 を実施。golden は Cookie と smartphone の `ppc` だけが変わり、再生成した |
| Part 1 | `wom/valuechain/`（台帳・3 つの視点・為替・費用の分け方の表）と `tools/valuechain_run.py` |
| Part 2 | Management タブの中に「Value Chain」を追加（既存の画面は「Overview」として不変） |
| 受入 1〜10 | すべて満たした（§6）。6 の変化 (3) の数字だけ判断待ち。10 は Tk の不安定な 1 件を再実行して緑（§10） |
| 大杉さんの判断が要る点 | **(A)** 手計算の変化 (3) の数字と、依頼 §1-4 の費用の表が食い違う（§7.1）。**(B)** 価格の表の最初の行より前の週（助走週）の扱い（§7.2） |
| 副作用 | Part 0-3 で oil の supply point の運賃の行を消したところ、配分モジュール（`wom/allocation/cost_block.py`）の経路が supply point で切れた。supply point → MOM の橋を足して直し、oil の配分テストの期待値を更新した（§2.3） |

---

## 1. 条件

- 保護対象のコア 6 ファイルは**変えていない**（`git status` で確認。変更は §9 の一覧）。
- 計画（Forward／Backward）は変えていない。台帳は計画を**読むだけ**（`node._actual_ship` と PSI）で、計画をやり直さない。
- 新しく作った黙った既定値はない。値が無いときは NaN（未評価）にして、件数と一覧を出す。
- 題材：`Cookie-jp-2026`（2 法人：E_CN〔CNY〕・E_JP〔JPY〕、チャネル ①②③）と `soysauce-jpy-2027-alloc`（3 法人：E_JP・E_US〔USD〕・E_EU〔EUR〕）。
- 台帳を作った計画：headless の `safe` のプラグイン（BufferingStockOptimizer・CapacityOverride・HolidayCalendar）。**GUI の既定はプラグインがすべて OFF** なので、GUI で同じ計画を作るにはプラグインに印を付ける（§8）。

---

## 2. Part 0 の変更

### 2.1 変更の一覧

| # | ファイル | 直した行 | 直さなかった行と理由 |
|---|---|---|---|
| 0-1 | `smartphone-global-2026-2029/planning_config.csv` | `cpu_size,1000` を追加 | — |
| 0-1 | `smartphone-global-2026-2029/ppc_market_price.csv` | 9 行を 1 台当たりへ（÷10,000。例 9,990,000 → 999 USD。`sku_master.selling_price` と同じ値） | — |
| 0-1 | `smartphone-global-2026-2029/ppc_supplier_cost.csv` | `EMS_A_CN` 450・`EMS_A_CN_i15` 320・`EMS_A_CN_i17` 490（1 台当たり） | `EMS_A_IN` 4,700,000、`SiliconWafer`・`Foundry_A`・`Sensor_A` の行、ノード・区間の `per_lot` の行（説明に「per lot (100 units)」）。**単位の根拠がファイルの中で一致しておらず、1 台当たりに直す係数が決められない**。このため smartphone の PPC は GM −813%（§3）。smartphone を題材にするときに、行ごとの単位を決めて直す |
| 0-2 | `Cookie-jp-2026/ppc_node_cost_rule.csv` | `logistics_cost` の 5 行を削除 | — |
| 0-2 | `Cookie-jp-2026/ppc_edge_cost_rule.csv` | 物理の区間だけに：`Factory_GP_CN->DC_Import_Buffer` 2,500、`DC_Import_Buffer->DC_Import_Main` 1,000、`Factory_DP_JP->DC_Local_JP` 200、`DC_Local_JP->Retail_JP_SM/CVS/EC` 各 300。supply point を通る 4 行を削除 | — |
| 0-2 | `Cookie-jp-2026/README.md`（新規） | 運賃の内訳（区間・金額・元の置き場所） | — |
| 0-3 | `ev-europe-2026`・`ev-thailand-2026`・`ev-thailand-2026_update`・`oil-global-2027` の `ppc_edge_cost_rule.csv` | supply point を通る行を削除（4・4・4・16 行。**28 行すべて、同じ金額がノード費用にもあることを確認**） | `smartx-2027-2029`（8 行）：ノード費用と金額が一致しない行ばかりで、写しかどうか判断できない。そのモデルを題材にするときに確かめる |
| 0-4 | `soysauce-jpy-2027-alloc/ppc_tariff_rule.csv` | 関税を国境の区間へ：`FG_WH_Noda->DC_US_SF` 0.125、`->DC_US_NY` 0.125、`->DC_EU_RTM` 0.08（JP→EU）、`->DC_JP` 0.0 | — |
| 0-4 | `wom/ppc/ppc_tariff.py`・`ppc_backward.py` | DAD → DAD の区間の関税を読む（`rules.get_tariff(edge)`、TARIFF のイベントは受け手の DAD に） | — |
| 0-5 | `wom/ppc/ppc_fx.py`・`ppc_transfer.py`・`ppc_engine.py`・`ppc_models.py`・`ppc_export.py`・`ppc_runner.py`、`wom/engine/landed_cost.py` | 黙った扱いを記録して `ppc_warnings.csv` に出す（**値は変えない**）：前の週の為替（`fx_fallback_prior_week`）、移転価格の為替 0 → 1.0（`transfer_fx_zero_as_1`・`transfer_event_fx_missing_as_1`）、Landed Cost の `fx_rate` 0 → 1.0（`landed_cost_fx_zero_as_1`）。列：`kind, location, currency, requested_week, used_week, count, detail` | Landed Cost の `fx_rate` の空欄は、調べると 1.0 ではなく **NaN になる**（`landed_cost_fx_blank_as_nan` として記録） |

**alloc の関税の総額は移動の前後で同じ**：15,670,707.44（同じ移転価格が基準のため）。
**`tools/gen_tariff_edges.py --check` は alloc で差を出す**：この道具は DC → leaf_out の区間の表を作るため。正典を国境の区間にした今は、道具のほうを国境の区間に合わせる必要がある（今回は直していない）。

### 2.2 golden の差分（`ppc` だけ）

再生成の前の `test_golden` は、**Cookie（本体と legacy）と smartphone の 3 件だけ**が失敗し、13 件は通った。再生成後、すべて通る。

| golden | 項目 | 前 | 後 | 理由 |
|---|---|---:|---:|---|
| Cookie-jp-2026（本体・legacy） | cost_base | 3,573,471,000 | 3,494,541,000 | −78,930,000 ＝ 78,930 lot × 1,000（`DC_Import_Buffer→DC_Import_Main` の 1,000 が区間とノードの両方にあった二重計上の解消） |
| | gross_profit | 686,229,000 | 765,159,000 | 同上 |
| | GM | 16.11% | 17.96% | 同上 |
| smartphone-global-2026-2029 | revenue_base | 641,014,134,734,200 | 64,101,413,473,420 | 市場価格を 1 台当たりへ（÷10,000）、cpu_size 1,000 |
| | cost_base | — | 5.219×10¹⁶ | 直さなかった行（§2.1）が lot 当たりのまま 1,000 倍に |
| | GM | — | −813.2% | 同上。**smartphone は単位がまだ揃っていない**ことの表れ |
| | tariff | — | 5.24×10¹⁵ | 同上 |
| | trust | 390 | 2,644 | NEGATIVE_MARGIN 等の検知が増えた |

`period/products/config/forward/backward/psi` は全 golden で不変。

- smartphone の money（Run Simulation）は 416,331,210,000 で、依頼の想定どおり。
- **Landed Cost の運賃は smartphone で 1,000 倍になる**。`freight_usd_per_lot` に money の数量を掛けるが、cpu_size 1,000 によって、その数量は台の単位になっている。今回は直していない。

### 2.3 副作用：配分モジュールの経路（直した）

oil の supply point の運賃の行（0-3）を消すと、`tests/test_allocation_hierarchical.py` と `tests/test_s1_view_model.py` の oil のテストが落ちた。原因は `wom/allocation/cost_block.py`。この関数は `ppc_edge_cost_rule.csv` の `"A->B"` を**経路そのもの**として使っていた。そのため経路が supply point で切れ、製油所・原油の費用が丸ごと消えていた（KANTO 111,000 → 77,500）。

- **直したこと**：経路を遡って、前のノードが無い supply point に着いたら、その製品の InBound の根の MOM（`product_name` が同じ）へつなぐ。これは計画が使っているのと同じつなぎ方。MOM が 2 つ以上あれば ValueError にし、黙って選ばない。保護対象のコアではない。
- **確かめたこと**：古いデータと新しいデータで原価ブロックを比べた。21 市場すべてで、差は**その市場の経路上にあった supply point の 2 区間の金額の合計に、ちょうど一致**した（例：JP Local 3,000＋2,500＝5,500 JPY、US Local 25＋20＝45 USD、Hormuz/RedSea 90,000,000 JPY）。関税率はどの市場も不変。
- **テストの期待値を更新した**（理由をテストのコメントに記載）：

  | テスト | 項目 | 前 | 後 |
  |---|---|---:|---:|
  | `test_leaf_economics_kanto` | cost | 111,000 | 105,500 |
  | | margin | 59,000 | 64,500 |
  | `test_leaf_economics_us_tx_zero_shipped` | cost | 115,500 | 108,750（45 USD × 150） |
  | | margin | 19,500 | 26,250 |
  | `test_oil_uom_split_and_hierarchy` | profit | 12,137,141,564 | 12,614,052,978 |
  | | hierarchy_gap | 363,942,316 | 374,903,812（再測定） |

  順位・出荷・限界市場の assert は変わらずに通った。soysauce（alloc）の配分の回帰値（132.1M など）は不変。alloc の supply point の行は 0-3 の対象外なので、経路は元のまま。

### 2.4 黙った扱いの件数（`ppc_warnings.csv`、Part 0 の実測）

| モデル | 行数 | 件数 | 内訳 |
|---|---:|---:|---|
| ev-thailand-2026 | 5 | 72 | `fx_fallback_prior_week`（THB）、Step 1〜5 に 18／12／15／6／21 |
| ev-thailand-2026_update | 5 | 75 | 同上（Step 1 が 21） |
| smartphone-global-2026-2029 | 265 | 7,632 | `fx_fallback_prior_week`（USD）、53 週 × Step 1〜5 |
| oil-global-2027 | 760 | 8,948 | `fx_fallback_prior_week`（USD 75 週・EUR 77 週）× Step 1〜5 |
| ほかの 12 モデル | 0 | 0 | — |

移転価格の為替 0 → 1.0 と、Landed Cost の `fx_rate` の置き換えは、今のモデルには 1 件も無かった。

---

## 3. Part 1 の作り（`wom/valuechain/`）

| ファイル | 役割 |
|---|---|
| `policy.py` | 費用の分け方の表（§4）。**この 1 か所だけ**で決める |
| `fx.py` | `ppc_fx_rate.csv` だけを使う。クロスレートは表の基準通貨を経由。表の最初の週より前は最初の週のレート（記録する、判断 d）。表の後の週・無い通貨は NaN（記録する。前の週の値は使わない） |
| `masters.py` | `vc_config`・`vc_entity`・`vc_node_assignment`・`vc_price_rule` の読み込み。重複行、ノードに書いた運賃、移転価格と `vc_price_rule` に**同じ価格が 2 か所**、物理でない区間への価格は、MasterError で止める |
| `records.py` | 実出荷（`_actual_ship`）から出荷の記録を作る。ID は LOVEM と同じ `ship:{product}:{node_id}:{w}:{seq}`。物理の区間は supply point を飛ばす（SP の出荷の物理の出し手は MOM）。MOM → SP は仮想の受け渡し |
| `ledger.py` | 明細（`vc_money_lines.csv.gz`）と週ごとの集計。原価は v1（管理価格）・entity（帳簿）・group（第 2 回用）の 3 つの基準で持つ |
| `views.py` | V1・V2・V3、観測の行、在庫、原価の保存と外部売上の照合 |
| `run.py` | `build_ledger`（GUI から）、`run_valuechain`（道具）、PPC・LOVEM との照合 |
| `tools/valuechain_run.py` | `--model-dir --out [--lovem-run] [--plugins]` |

出力（`output/valuechain/<model>/run_1/`）：
- `vc_shipments.csv.gz`、`vc_money_lines.csv.gz`
- `vc_v1_weekly.csv`、`vc_v2_weekly.csv`、`vc_v3_weekly.csv`
- `vc_observation_weekly.csv`、`vc_inventory_weekly.csv`
- `vc_conservation.csv`、`vc_checks.json`
- `vc_missing_prices.csv`、`vc_fx_log.csv`、`vc_price_log.csv`
- `vc_edge_flows.csv`、`vc_cost_policy.csv`、`vc_ppc_comparison.csv`、`vc_run_info.json`

---

## 4. 費用の分け方の表（依頼 §1-4、`policy.py`）

| 費用 | どこで | 扱い |
|---|---|---|
| purchase（仕入） | グループへ入る・グループの中 | 在庫原価 |
| freight（運賃） | グループへ入る・グループの中 | 在庫原価 |
| freight | グループから外部へ | 売り手のその週の販売費 |
| tariff（関税） | グループへ入る・グループの中 | 在庫原価 |
| tariff | グループから外部へ | 売り手のその週の販売費 |
| insurance（保険） | グループへ入る・グループの中 | 在庫原価 |
| insurance | グループから外部へ | 売り手のその週の販売費 |
| conversion_cost（加工） | ノード | 在庫原価 |
| logistics_cost | ノード | 在庫原価（ただし今回の 2 モデルではノードに運賃があれば止める） |
| warehouse_cost（保管） | ノード | その週の費用 |
| sga_cost | ノード | その週の費用 |
| marketing_cost | ノード | 売り手のその週の販売費 |
| holding（在庫の保有費用） | ノード | その週の費用（独立した項目）。`holding_rate_weekly` が空欄なので**計算しない**（0 として出さない） |

---

## 5. 結果（Cookie と alloc）

### 5.1 V1（ノード・区間、報告の期間の合計、HQ＝JPY）

**Cookie-jp-2026**（報告の期間 2026-W02〜2027-W52）

| 法人 | ノード | 売上 | 売上原価 | 費用 | 利益 | 未評価 |
|---|---|---:|---:|---:|---:|---:|
| E_CN | Factory_GP_CN | 1,264,716,000 | −1,124,192,000 | 0 | 140,524,000 | 0 |
| E_JP | DC_Import_Buffer | 1,814,614,200 | −1,814,614,200 | 0 | 0 | 0 |
| E_JP | DC_Import_Main | 1,181,804,400 | −1,181,804,400 | −116,031,000 | −116,031,000 | 62,490 |
| E_JP | DC_Local_JP | 772,167,600 | −772,167,600 | −255,010,400 | −255,010,400 | 52,016 |
| E_JP | Factory_DP_JP | 1,284,633,000 | −1,223,460,000 | 0 | 61,173,000 | 0 |
| E_JP | Retail_JP_EC（③） | 789,900,000 | −624,592,000 | 0 | 165,308,000 | 0 |
| E_JP | Retail_JP_SM（①） | 1,734,900,000 | −1,360,117,000 | 0 | 374,783,000 | 0 |

同じ法人の中の区間（管理価格が無い）は**原価のまま振り替える**ため、DC の売上と原価は同額。DC_Import_Main・DC_Local_JP の未評価は、CVS（②）への卸の売上（価格が未設定）。

**soysauce-jpy-2027-alloc**（報告の期間 2027-W01〜2028-W52）

| 法人 | ノード | 売上 | 売上原価 | 費用 | 利益 | 未評価 |
|---|---|---:|---:|---:|---:|---:|
| E_JP | Brewing_Noda | 111,181,865 | −111,181,865 | 0 | 0 | 0 |
| E_JP | Bottling_Noda | 198,638,522 | −180,580,475 | 0 | 18,058,048 | 0 |
| E_JP | FG_WH_Noda | 88,636,948 | −88,636,948 | −5,118,900 | −5,118,900 | 83,330 |
| E_JP | DC_JP | 93,927,411 | −93,927,411 | −4,381,800 | −4,381,800 | 0 |
| E_JP | Rest_JP（①） | 112,320,000 | −99,140,100 | 0 | 13,179,900 | 0 |
| E_US | DC_US_SF | 0 | 0 | −6,706,398 | −6,706,398 | 34,082 |
| E_US | DC_US_NY | 0 | 0 | −12,649,948 | −12,649,948 | 34,082 |
| E_US | Rest_US_West（①） | 0 | 0 | 0 | 0 | 34,126 |
| E_EU | DC_EU_RTM | 0 | 0 | −6,982,881 | −6,982,881 | 23,744 |

Bottling_Noda の 18,058,048 は、終端の MOM の移転価格（管理価格）による V1 だけの利益。V2 では消える。E_US・E_EU は法人間の価格が未設定なので、仕入の原価が分からない。原価が分からないため、売上も未評価にしている（Rest_US_West の売上 119,353,000 は額としては分かる。§5.4）。

### 5.2 V2（法人、報告の期間の合計）

| モデル | 法人 | 売上（HQ） | 売上原価 | 費用 | 利益（HQ・管理評価） | 利益（現地通貨） | 現地の利益を HQ に換算 | 未評価 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Cookie | E_CN | 1,264,716,000 | −1,124,192,000 | 0 | 140,524,000 | 6,627,864 CNY | 140,159,462 | 0 |
| Cookie | E_JP | 2,524,800,000 | −1,947,919,000 | −371,041,400 | 205,839,600 | 205,839,600 JPY | 205,839,600 | 114,506 |
| alloc | E_JP | 112,320,000 | −91,236,000 | −9,500,700 | 11,583,300 | 11,583,300 JPY | 11,583,300 | 83,330 |
| alloc | E_US | 0 | 0 | −19,356,345 | −19,356,345 | −111,560 USD | −19,356,345 | 68,208 |
| alloc | E_EU | 0 | 0 | −6,982,881 | −6,982,881 | −41,164 EUR | −6,982,881 | 23,744 |

E_CN の「管理評価」140,524,000 と「換算」140,159,462 の差は、取得原価を受け入れ週の為替で引き継ぐか、利益をその週の為替で換算するかの違い（設計 §5.5）。表と画面では**別の列**に出す。

### 5.3 V3（連結、報告の期間の合計、第 1 回＝内部の未実現利益の消去前）

| | Cookie | alloc |
|---|---:|---:|
| 外部売上 | 2,524,800,000 | 112,320,000 |
| 外部売上の原価（法人の帳簿の原価） | −1,947,919,000 | −91,236,000 |
| 費用 | −371,041,400 | −35,839,926 |
| 内部取引の利益（消去前） | 140,524,000 | 0 |
| **利益（第 1 回、消去前）** | **346,363,600** | **−14,755,926** |
| 利益（共通の評価通貨 USD） | 2,263,099 | −96,928 |
| 参考：第 2 回の利益（`profit_r2`、表示しない） | 300,579,600 | −14,755,926 |
| 未評価の件数 | 114,506 | 175,282 |

**観測（グループの売上に足さない）**

| モデル | ② チャネル | 消費者への販売（HQ） | 現地通貨 | 外部チャネルの在庫の最大 |
|---|---|---:|---:|---:|
| Cookie | Retail_JP_CVS | 1,734,900,000 | 1,734,900,000 JPY | 577 lot（EXT_CH_JP_CVS） |
| alloc | Rest_US_East | 119,353,000 | 682,520 USD | 175 lot |
| alloc | Rest_FR | 44,304,732 | 251,370 EUR | 150 lot |
| alloc | Rest_BE | 16,313,400 | 100,700 EUR | 100 lot |
| alloc | Rest_NL | 16,313,400 | 100,700 EUR | 100 lot |

### 5.4 PPC との対応（受入 9、全期間、`vc_ppc_comparison.csv`）

**Cookie-jp-2026**

| 項目 | PPC | 台帳 V3 | 差 | 説明 |
|---|---:|---:|---:|---|
| 売上 Import SM（①） | 946,800,000 | 946,800,000 | 0 | 同じ市場価格 × 同じ実出荷 |
| 売上 Import EC（③） | 474,300,000 | 474,300,000 | 0 | 同上 |
| 売上 Import CVS（②） | 946,800,000 | 0 | −946,800,000 | PPC は消費者への販売をグループの売上にしている。台帳では CVS は外部チャネルなので、グループの売上は DC → CVS の卸（未設定＝未評価 31,560 件）。消費者への販売は観測 |
| 売上 Local SM・EC | 788,100,000・315,600,000 | 同じ | 0 | |
| 売上 Local CVS（②） | 788,100,000 | 0 | −788,100,000 | 同上（未評価 26,270 件） |
| 費用 仕入 | 1,325,100,000 | 1,325,100,000 | 0 | **一致** |
| 費用 加工・取扱 | 1,277,910,000 | 1,277,910,000 | 0 | **一致** |
| 費用 運賃 | 307,785,000 | 307,785,000 | 0 | **一致** |
| 費用 関税 | 213,111,000 | 213,111,000 | 0 | **一致** |
| 費用 SGA | 370,635,000 | 370,635,000 | 0 | **一致** |
| 内部取引の利益（消去前） | 0 | 157,860,000 | +157,860,000 | PPC は移転価格を売上にしない（Profit Zone の mom_profit にだけ使う）。台帳は 78,930 lot × 18,000（E_CN → E_JP の売上 1,420,740,000）の差を消去前として残す |
| 利益（全期間、消去前） | 765,159,000 | 356,225,000 | −408,934,000 | 上の項目の合計（CVS の売上が未評価、内部の利益） |

Cookie の費用は、5 つの種類すべてで PPC と 1 円まで一致した。

**soysauce-jpy-2027-alloc**

| 項目 | PPC | 台帳 V3 | 差 | 説明 |
|---|---:|---:|---:|---|
| 売上 Rest_JP（①） | 112,320,000 | 112,320,000 | 0 | |
| 売上 Rest_US_West（①） | 119,353,000 | 119,353,000（額は分かる） | 0 | 原価が分からない（法人間の価格が未設定）ので、利益の計算では未評価 |
| 売上 Rest_US_East・FR・BE・NL（②） | 119,353,000・44,304,732・16,313,400・16,313,400 | 0 | 全額 | ② なので消費者への販売は観測。グループの売上は卸（未設定） |
| 費用 仕入 | 83,758,600 | 78,910,400 | −4,848,200 | 為替の週の違い（推定）：台帳は仕入の週の為替、PPC は販売週の為替。原料は USD 建てで、2028 年に円安（150 → 200 円）。仕入は販売より前の週になる |
| 費用 加工・取扱 | 112,936,500 | 112,936,500 | 0 | **一致**（JPY 建て） |
| 費用 運賃 | 75,839,858 | 74,413,183 | −1,426,675 | 同上（為替の週）。未評価の lot に付いた運賃も含めた額 |
| 費用 関税 | 15,670,707 | 15,362,924 | −307,784 | 同上 |
| 費用 保管 | 21,820,120 | 21,704,233 | −115,886 | 同上 |
| 費用 SGA | 6,292,506 | 6,230,674 | −61,832 | 同上 |
| 内部取引の利益 | 0 | 0 | 0 | 法人間の価格が未設定 |
| 利益（全期間、消去前） | 111,639,242 | −15,610,182 | −127,249,424 | ② の売上と、未評価の原価 |

alloc の費用の差は「為替の週の違い」だと推定しているが、項目ごとの分解までは確かめていない（JPY 建ての加工費が一致することと、差がすべて同じ符号であることが根拠）。

### 5.5 未設定価格の一覧（`vc_missing_prices.csv`）

| 区間 | 製品 | 種類 | 売り手 → 買い手 | lot | 最初〜最後の出荷 |
|---|---|---|---|---:|---|
| DC_Local_JP → Retail_JP_CVS | Cookie_Local | wholesale | E_JP → EXT_CH_JP_CVS | 26,270 | 2026-W01〜2027-W51 |
| DC_Import_Main → Retail_JP_CVS | Cookie_Import | wholesale | E_JP → EXT_CH_JP_CVS | 31,560 | 2026-W01〜2027-W51 |
| FG_WH_Noda → DC_US_NY | Soy_Sauce | intercompany | E_JP → E_US | 17,063 | 2026-W44〜2028-W42 |
| FG_WH_Noda → DC_US_SF | Soy_Sauce | intercompany | E_JP → E_US | 17,063 | 2026-W45〜2028-W43 |
| FG_WH_Noda → DC_EU_RTM | Soy_Sauce | intercompany | E_JP → E_EU | 11,915 | 2026-W44〜2028-W42 |
| DC_US_NY → Rest_US_East | Soy_Sauce | wholesale | E_US → EXT_CH_US_EAST | 17,063 | 2026-W53〜2028-W51 |
| DC_EU_RTM → Rest_FR | Soy_Sauce | wholesale | E_EU → EXT_CH_FR | 6,615 | 2026-W53〜2028-W51 |
| DC_EU_RTM → Rest_BE | Soy_Sauce | wholesale | E_EU → EXT_CH_BE | 2,650 | 2026-W53〜2027-W29 |
| DC_EU_RTM → Rest_NL | Soy_Sauce | wholesale | E_EU → EXT_CH_NL | 2,650 | 2026-W53〜2027-W29 |

`vc_price_rule.csv`（今は見出しだけ）に `edge_id, product_id, price_type, effective_week, price, currency` を書き入れれば、評価される。

---

## 6. 受入条件 1〜10

| # | 条件 | 結果 | 根拠 |
|---|---|---|---|
| 1 | 数量の PSI が変わらない | **満たす** | golden 13 件で `period/products/config/forward/backward/psi` が不変（§2.2）。台帳は計画を読むだけ。`vc_run_info.json` の `model_unchanged_by_run: true`（実行の前後でモデルのフォルダのハッシュが同じ） |
| 2 | 記録の照合（LOVEM） | **満たす** | `tools.lovem_observe --lot-flow-mode identity` で観測（`output/lovem_vc/<model>/run_A`、どちらも verify の `all_match=True`）。Cookie 788,880 件・alloc 527,037 件が、出荷イベント ID・品目・ノード・週・数量で 1 対 1。欠け 0、余分 0、重複 0、値の食い違い 0。コードの SHA・モデルの入力・プラグインも同じ。**LOVEM の既知の穴に当たったものは 0 件**（inline の push decoupling・Inbound の P コピーは、この 2 モデルの実出荷の照合には現れなかった） |
| 3 | 原価の保存 | **満たす** | 法人 × 週の全行（Cookie 242 行・alloc 390 行）で「期首 ＋ 受け入れ − 払い出し − 価格の無い販売の払い出し − 評価できなくなった分 ＝ 期末」、差の最大 0.0。組立と、輸送中 → 到着の振替は同じ基準の原価で移す。手計算の基本の表と (5) でも確認 |
| 4 | 外部売上の照合 | **満たす** | Cookie：連結の売上 3,945,540,000 − 法人間 1,420,740,000 ＝ V3 の外部売上 2,524,800,000 ＝ 外部への出荷の記録 × 価格。alloc：231,673,000（法人間 0）。額の分かる明細（`hq_known`）で照合 |
| 5 | チャネル | **満たす** | Cookie の日本で SM（①）・CVS（②）・EC（③）が並ぶ。CVS の卸（未評価）と消費者への販売（観測 1,734,900,000）は別の行。外部チャネルの在庫は観測の行（最大 577 lot）。画面 `1_cookie_v3_hq_cum.png` 下段 |
| 6 | 手計算の再現 | **満たす（1 点は判断待ち）** | `tests/test_valuechain_handcalc.py`：基本の表、変化 (1)(2)(4)(5)、§5.5 の通貨の表、為替、未設定価格。第 2 回の期待値は 3 件を skip で保持（本体は直接実行して通ることを確認）。**変化 (3) は、依頼の表（E1 20）と依頼 §1-4 の費用の表（E1 15）が食い違う**。実装は費用の表に従う（§7.1）。依頼の数字は strict な xfail で保持 |
| 7 | 表示 | **満たす** | 上の帯に「内部の未実現利益の消去前（第 1 回）」。単週と累計の切り替え。区分の列で助走と報告を区別 |
| 8 | 通貨 | **満たす** | 元の金額と通貨を明細に持つ（`amount_orig`・`currency_orig`）。HQ・共通・現地の役割は `vc_config.csv`。使った為替・週・方法は `vc_fx_log.csv`。表の後の週と無い通貨は NaN（`missing_unvalued`、テストで確認）。EUR → USD → JPY ＝ EUR → JPY（テスト）。表示の通貨を切り替えても列を選ぶだけで、数量・元の価格・所属は変わらない。§5.5 を再現し、管理評価と換算を別の列に出す。**為替が黙って 1 や前の週の値になることは無い** |
| 9 | PPC との対応 | **満たす** | §5.4 |
| 10 | 全テスト緑 | **満たす（Tk の不安定な 1 件は再実行で緑）** | §10 |

### 6-10 テスト

- 新規：`tests/test_valuechain_handcalc.py`、`tests/test_stage_d_part0.py`、`tests/test_valuechain_integration.py`。Part 0 と手計算の 2 ファイルは **19 passed, 3 skipped, 1 xfailed**。
- 全体：§10

---

## 7. 大杉さんの判断が要る点・実装での判断

### 7.1 手計算の変化 (3) と費用の表の食い違い（判断待ち）

依頼の (3)「D が外部の販売チャネル（②）」は、「数字は (2) と同じ（運賃 5 は D の負担）」で E1 の W2 の利益を 20 としている。一方、依頼 §1-4 の費用の表では、**グループから外部へ販売する区間の運賃は「売り手のその週の販売費」**になる。そのため E1 ＝ 100 − 80 − 5 ＝ **15** になる。

- 実装は**費用の表に従う**。運賃の負担を決める場所は表の 1 か所だけにするため。
- 依頼の数字（20）は `test_variation_3_letter_numbers` に strict な xfail として残した。
- (2) が 20 で通るのは、D を「グループの会社で、連結範囲の外」（`kind=group`、`consolidated=0`）として置いたから。費用の表の区間の分類は「受け手がグループの会社か」で決まるので、(2) は「グループへ入る・グループの中」になる。そのため運賃は受け手 D の在庫原価になり、連結には入らない。(3) の D は外部の相手（`external_channel`）なので「グループから外部へ」になり、運賃は売り手 E1 の販売費になる。
- **どちらに揃えるか**（表に「チャネルへの出荷の運賃は買い手の負担」の行を足すか、(3) の数字を 15 に直すか）をご判断ください。

### 7.2 価格の表の最初の行より前の週（実装での判断、要確認）

仕入価格（`ppc_supplier_cost`）などの表は、最初の行が 2026-W01（Cookie）・2027-W01（alloc）から始まる。助走週の仕入（Cookie 2025-W39〜、alloc 2026-W28〜）には、行がない。

- 為替（判断 d）と同じように、**最初の行の価格を使い、`vc_price_log.csv` に記録した**（Cookie 17 行・alloc 26 行）。
- NaN（未評価）にすると、助走週に仕入れた在庫がすべて未評価になり、報告の期間の原価が出ない。
- 為替と同じ扱いでよいか、ご確認ください。

### 7.3 そのほか

- **Cookie の為替の表**は `data/ppc/ppc_fx_rate.csv`（モデルのフォルダに無いため、PPC と同じ fallback）。どちらを使ったかは帯と `vc_fx_log.csv` に出す。
- 第 1 回で 0 件だったもの：
  - 為替が NaN になった件数（`fx_unvalued_uses`）：両モデルとも 0
  - 記録の作成で見つかった食い違い（`issues`）：両モデルとも 0
- 為替の最初の週のレートを使った件数（CLI の計画）：
  - Cookie：123,530（GUI の計画では 115,202。プラグインが違うため）
  - alloc：294,810
- **申し送り**（依頼 §申し送り、今回は直していない）：
  - ev の `DC_EV_Import` のノード費用「輸入関税 8％＋DC 取扱費」は、関税を運賃の行に含めている
  - 能力待ちの記録に lot_id が無い
  - money は通貨を換算しない

---

## 8. Part 2：画面（Management → Value Chain）

画像は `docs/development/stage_d_phase1/`。道具 `tools/gui_valuechain_check.py` が、実際のアプリの窓で操作して撮った（PrintWindow）。

| 画像 | 内容 |
|---|---|
| `0_cookie_loaded.png` | モデルを読み込んだ直後：「Planning Engine を実行すると台帳を作ります」。台帳は出ない |
| `1_cookie_v3_hq_cum.png` | V3・HQ・累計。帯に「消去前（第 1 回）」・計画 ID・報告の開始週・通貨・為替の表。右上の隅に未評価 231,320／未設定価格 2／為替：最初の週 115,202。下段に ② の 3 種類の行 |
| `2_cookie_v2_ECN_local_cum.png` | V2・E_CN・現地通貨（CNY）・累計。右端の列「現地の利益を HQ に換算」は、管理評価とは別の列 |
| `3_cookie_v1_DC_Import_Main_hq_wk.png` | V1・DC_Import_Main・HQ・単週 |
| `4_cookie_v3_common_cum.png` | V3・共通の評価通貨（USD）・累計 |
| `5_missing.png`・`6_fx.png`・`7_unvalued.png` | 隅のボタンを押して出る一覧（未設定価格、為替の記録、未評価の明細） |
| `8_alloc_loaded.png` | 別のモデル（alloc）を読み込んだ直後：Cookie の台帳は消えている |
| `9_alloc_v3_hq_cum.png`・`10_alloc_v2_EUS_local_cum.png` | alloc の V3、E_US の現地通貨（USD） |
| `11_after_simulation.png` | Run Simulation の後：「Run Simulation の結果には台帳がありません」 |

**古い結果を出さない（受入 7・前回の P1 の規則）**：alloc の計画中、0.2 秒ごとに帯・行数・台帳の計画 ID・画面の計画 ID を記録した（`output/valuechain/gui/steps.json` の history）。

| 時刻 | 状態 |
|---|---|
| 0.2 秒 | 「モデルを読み込みました」、0 行 |
| 4.0 秒 | 「台帳を作成中」、0 行 |
| 33.4 秒 | alloc の計画 ID の台帳、130 行 |

Cookie の台帳が出た瞬間は無い。台帳には作ったときの計画 ID があり、画面の計画 ID と違えば表示しない。

画面の確認で見つけて直したこと：
- V1 のノードの一覧に ② のチャネル（外部の会社が持つ）が出ていて、選ぶと 0 行になった。② は下段の表で見るので、一覧から外した。
- 隅のボタンが画面の右端で切れていたので、2 行目に移した。
- 週の列の幅を固定した。
- モデルを替えたとき、法人・ノードの絞り込みを戻すようにした。

---

## 9. 変更したファイル

- **データ**：
  - `Cookie-jp-2026`：`ppc_edge_cost_rule.csv`、`ppc_node_cost_rule.csv`、`README.md`（新規）、`vc_*.csv` 4 つ（新規）
  - `ev-europe-2026`・`ev-thailand-2026`・`ev-thailand-2026_update`・`oil-global-2027`：`ppc_edge_cost_rule.csv`
  - `smartphone-global-2026-2029`：`planning_config.csv`、`ppc_market_price.csv`、`ppc_supplier_cost.csv`
  - `soysauce-jpy-2027-alloc`：`ppc_tariff_rule.csv`、`vc_*.csv` 4 つ（新規）
- **PPC**：`wom/ppc/` の `ppc_tariff.py`、`ppc_backward.py`、`ppc_fx.py`、`ppc_transfer.py`、`ppc_models.py`、`ppc_engine.py`、`ppc_export.py`、`ppc_runner.py`。`wom/engine/landed_cost.py`
- **配分**：`wom/allocation/cost_block.py`（supply point → MOM の橋、§2.3）
- **新規**：`wom/valuechain/`（`__init__`・`policy`・`fx`・`masters`・`records`・`ledger`・`views`・`run`）、`wom/gui/valuechain_panel.py`、`tools/valuechain_run.py`、`tools/gui_valuechain_check.py`
- **GUI**：`wom/gui/app.py`。Management を「Overview」と「Value Chain」のサブタブに分けた。計画の完了で台帳を作り、モデルの読み込みと Run Simulation で消す。
- **画面の道具**：`tools/gui_two_model_check.py`・`tools/gui_sim_plan_check.py` を、Management のサブタブに合わせて更新した。
- **golden**：`tests/golden/Cookie-jp-2026.json`、`tests/golden/legacy/Cookie-jp-2026.json`、`tests/golden/smartphone-global-2026-2029.json`（いずれも `ppc` だけ）
- **テスト**：
  - 新規 3 ファイル（§6-10）
  - `tests/test_s1_view_model.py`・`tests/test_allocation_hierarchical.py` の期待値（§2.3）
- **保護対象のコア 6 ファイル：変更なし**

---

## 10. 全テストの結果

`python -m pytest tests/ -q -p no:cacheprovider`（ほかの処理と並べずに 1 回で実行）：

```
1 failed, 685 passed, 6 skipped, 1 xfailed  (10 分 42 秒)
FAILED tests/test_merit_order_plot.py::test_plot_parallel_coordinates
  _tkinter.TclError: Can't find a usable tk.tcl in the following directories: ...
```

- 落ちた 1 件は Tk の初期化の失敗で、依頼が挙げている `test_plot_regime_matrix` と同じ種類の不安定さ。**このファイルだけを再実行すると `10 passed`**。`test_plot_regime_matrix` はこの回は通った。
- skip 6 件：このうち 3 件は第 2 回（消去後）の期待値。xfail 1 件は変化 (3) の依頼の数字（§7.1）。
- golden 13 件は通った（Cookie・smartphone は `ppc` を再生成した後の値）。
- **並べて実行したときの失敗（参考）**：最初の全体の実行は、GUI の確認の道具と同時に動かしたため、24 件が落ちた。
  - `output/ppc/ppc_warnings.csv` の書き換えが重なった（PermissionError）
  - ページングファイルが足りなくなった（WinError 1455）
  - これらは単独で実行すると起きない。`output/ppc` を使うテスト・道具は、並べて動かさないこと。
  - この回で、oil の配分テストの副作用（§2.3）も見つかった。

---

## 11. 大杉さんの手順：台帳を作って画面で見る

### 11.1 道具で作る（CSV で見る）

```powershell
python -m tools.valuechain_run --model-dir data/sample/Cookie-jp-2026 --out output/valuechain/Cookie-jp-2026/run_1
```

- `soysauce-jpy-2027-alloc` も同じ。1 回あたり 2〜3 分。
- 計画は headless の `safe` のプラグインで作る。プラグインを指定するときは `--plugins none` などを付ける。
- LOVEM の出荷と照合するときは、先に観測を作り、`--lovem-run` を付ける。

```powershell
python -m tools.lovem_observe --model-dir data/sample/Cookie-jp-2026 --out output/lovem_vc/Cookie-jp-2026/run_A --lot-flow-mode identity
python -m tools.valuechain_run --model-dir data/sample/Cookie-jp-2026 --out output/valuechain/Cookie-jp-2026/run_1 --lovem-run output/lovem_vc/Cookie-jp-2026/run_A
```

最後の行に `LOVEM True: matched …` と出れば一致。

見るファイル：
- `vc_v3_weekly.csv`（連結）、`vc_v2_weekly.csv`（法人）、`vc_v1_weekly.csv`（ノード）
- `vc_missing_prices.csv`（書き入れる価格）
- `vc_ppc_comparison.csv`（PPC との対応）
- `vc_checks.json`（保存・照合）

### 11.2 画面で見る

1. `python -m main`
2. Load Model Folder… で `data/sample/Cookie-jp-2026`（または `soysauce-jpy-2027-alloc`）を選ぶ。
3. 道具と同じ計画にするときは、左下の Plugins で Holiday Calendar・Buffering Stock Optimizer・Capacity Override に印を付ける。**既定はすべて OFF**。OFF でも台帳は作れるが、計画が少し違う（alloc は 75,291 → 76,663 lot）。
4. Run Planning Engine。PPC と同じく、計画が終わると台帳を作り始める。alloc で約 30 秒、Cookie で約 1 分。
5. Management タブ → 「🔗 Value Chain」。
   - 上の帯で、計画 ID と「消去前（第 1 回）」を確かめる。
   - V1／V2／V3、法人、ノード、単週／累計、通貨（HQ／共通／現地）を切り替える。
   - 右上の隅のボタンで、未評価・未設定価格・為替の一覧が出る。
   - 下段で ② のチャネルの 3 種類の行を見る。
6. vc_* のマスター（`vc_config`・`vc_entity`・`vc_node_assignment`・`vc_price_rule`）が無いモデルでは、「台帳のマスターがありません」と出る。今は Cookie と alloc だけが持つ。

---

## 12. Claude君の確認と修正（2026-10-01）

### 12.1 smartphone の残りの行を 1 台当たりへ（§2.1・§2.2 の更新）

- 直さなかった行（供給者の原価 8 行、ノード費用 32 行、区間の費用 12 行）も、**すべて「1 万台当たり」の桁**だった。÷10,000 で 1 台当たりにすると、組立 50 USD、SoC 38 USD、ウェハー 5 USD、海上運賃 10 USD、DC の作業 5 USD、区間の運賃 17 USD など、どれも 1 台当たりとして筋の通る値になる。ノード費用の説明「per lot (100 units)」は誤りだった（100 台当たりなら組立が 1 台 5,000 USD になる）。
- 3 つのファイルの残りの行を ÷10,000 にし、説明の「per lot」を「per unit」に直した。
- これで smartphone の PPC は、**すべての金額が修正前の 1/10、GM は修正前と同じ 41.19%** になるはず（市場価格・原価とも ÷10,000、数量 ×1,000）。期待値：売上 64,101,413,473,420、原価 約 37,695,124,383,918、関税 約 4,720,497,327,978、GM 41.1946%、trust 390。**確認済み**（大杉さんが Windows で golden を再生成、2026-10-01）：売上 64,101,413,473,420、原価 37,695,124,383,917.75、関税 4,720,497,327,977.75、GM 0.411946、trust 390。修正前の値のちょうど 1/10 で、GM と trust は修正前と同じ。
- 申し送り：Landed Cost の `freight_usd_per_lot` は、cpu_size が 1 でないと「台」の数量に掛かる（§2.2）。列名と単位の扱いは、Landed Cost を台帳の為替・運賃に揃えるときに決める。

### 12.2 手計算の変化 (3)（§7.1）

- 依頼書の誤り（§1-4 の表と、(3) の「数字は (2) と同じ」が食い違っていた）。**表を正とし、(3) は E1 ＝ 15** とする（グループから外部チャネルへの配送の運賃は売り手が負担。Cookie の DC_Local_JP → Retail_JP_CVS の配送費 300 を E_JP が負担するのと同じ）。
- `test_variation_3_letter_numbers`（xfail）を消し、依頼書の (3) を訂正した。

### 12.3 そのほか

- §7.2（助走週の仕入価格に最初の行の価格を使い、記録する）は、判断 d と同じ扱いとして妥当。大杉さんの確認を待つ。
- `wom/allocation/cost_block.py` のエラーの文言が「`MOM->SP` の行を足して経路を選ぶ」と案内していた。supply point の運賃の行を作り直す落とし穴になるので、「物理の区間 `MOM-><最初の DAD>` で選ぶ（`MOM->SP` の行は作らない）」に直した。
- §2.3 の oil の配分の原価が下がった件は、`cost_block` がノード費用と区間の費用の両方を足していたため。消した supply point の行はノード費用の写しだったので、**二重計上がなくなった**ことによる正しい変化である。
