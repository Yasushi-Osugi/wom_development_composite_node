# cosmetics-sg-th-2027-2029

日本の工場で作る高級スキンケア 2 SKU（美容液・クリーム）を、シンガポールとタイで売るモデル。
BS-SEAF の化粧品の検証で採用したモデル（試行の名前は M0）を、そのまま正式なサンプルにした。

**架空のブランドの、教育・実証用のモデルである。** 実在の企業の値は使っていない。金額は
「WOM が金額を正しく流せるか」を確かめるための仮定で、業務の判断に使える精度ではない。

## 業務の問い

販売開始と市場の追加（シンガポールの直営店の開店、タイの代理店の追加）に対して、日本の工場の能力で
足りるか。足りないとき、どの需要を供給の対象にするか。残存期間（納品時の年齢 52 週以内）を守れるか。
チャネルごとにいくら残るか。

このモデルは**能力が足りた基準**である。能力が足りない案・配分を変える案は、このモデルから作る
（手順は `docs/scenarios/cosmetics.md` の Comparison cases）。

## 物理のネットワーク

```text
Materials_JP（原料） → Factory_JP（工場） → WH_JP_Released（判定済み倉庫）
    → DC_SG（シンガポールの DC） → SG_Store（直営店）・SG_EC（公式 EC）・SG_Distributor（代理店）
    → DC_TH（タイの DC）        → TH_Distributor（代理店）
```

| SKU | 期間 |
|---|---|
| `COS_Serum`（美容液）、`COS_Cream`（クリーム） | 2026-W37 から 173 週（2029-W52 まで）。助走 `warmup_lt=17` を含む。報告の開始は 2027-W01 |

| 法人 | ノード |
|---|---|
| 日本本社（JPY） | Factory_JP、WH_JP_Released、DC_TH |
| シンガポール販社（SGD） | DC_SG、SG_Store、SG_EC |
| 外部 | 供給者（Materials_JP）、代理店 2 社（SG_Distributor、TH_Distributor） |

## 単位

**1 lot ＝ 1 ケース ＝ 24 個（良品）**（`cpu_size=24`）。需要・能力は lot、価格・費用は **1 個当たり、税抜き**。
シンガポールの GST・タイの VAT は売上にも費用にも入れない。報告の通貨は JPY。

## 仮定

数量（化粧品設計書 §1.4）：

| # | 仮定 |
|---|---|
| A1 | 1 lot ＝ 24 個 |
| A2 | 工場の出荷判定 1 週（`WH_JP_Released` の `lt_wks`） |
| A3 | 日本→シンガポール 海上 2 週（タイも 2 週） |
| A4 | DC→各チャネル 1 週 |
| A5・A6 | 使用期限 36 か月、納品時の残存 24 か月 ＝ 許容の滞留 52 週 |
| A7 | 販売開始：EC・代理店 2027-W01、直営店 2027-W14、タイの代理店 2028-W01 |
| A8 | 定常の需要（lot／週）：美容液 直営 4・EC 3・代理店 6・タイ 4、クリーム 直営 3・EC 2・代理店 5・タイ 3。開始から 13 週は 50% |
| A9 | 工場の能力：ピーク週の需要 ÷ 歩留まり × 1.2 を切り上げ。美容液 `max_supply` 22・`cap_soft` 18、クリーム 17・14 |
| A10 | 歩留まり 0.97（`sc_tree_master.csv` の `yield_rate`。数量の上限に効く） |
| A11 | 価格・原価・為替は下の M1〜M8 |
| A12 | 直営店の店頭在庫：`SG_Store` の `ss_days=14` |
| A13 | 工場は `demand_envelope=soft`（cap_soft で平準化、max_supply は物理の天井） |

金額（M1〜M8 の要点。全文は `requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md`）：

| # | 仮定 |
|---|---|
| M1 | 価格・原価は架空の水準。直営店 SGD 165／138、EC 157／131、代理店（SG）74／62、代理店（TH）THB 1,900／1,600（美容液／クリーム） |
| M2 | 為替は期間中一定：SGD 115、THB 4.5、USD 150 円 |
| M3 | 歩留まりの損は原価に入れない |
| M4 | タイの関税は 0%（EPA を使う仮定）。今の税率は確かめていない |
| M5 | 店舗の運営費は売上の 35% で近似 |
| M6 | 日本本社の研究開発・グローバルなブランドの費用は置かない |
| M7 | 費用の無い区間・ノードにも 0 の行を明示する。行が無いのは supply point だけ |
| M8 | タイの DC は日本本社のまま |

金額の規則は全部このフォルダの中にある（`ppc_*.csv`・`vc_price_rule.csv`・`vc_sales_cost_rule.csv`・`vc_customs_valuation_rule.csv`・`vc_trade_terms.csv`）。共有の規則は使わない。

`vc_sales_cost_rule.csv` は Value Chain 用の、直販（直営店・公式 EC）の売上比率の費用の費目の表
（販社販管費 10%、決済・EC 基盤手数料 5%、デジタル広告費 15%、店舗運営費 35%）。PPC は読まず、
`ppc_node_cost_rule.csv` の合計の率（直営店 45%、EC 15%＋15%）で同じ額を計算する。公式 EC の配送・梱包
（1 個 3 SGD）は `ppc_edge_cost_rule.csv` の `SG_EC->CONSUMER` の行（`delivery_packing_cost`）に置く。
二つのファイルの率・固定額が合わなければ、Value Chain の読み込みで止まる。

`vc_customs_valuation_rule.csv` は Value Chain 用の、タイ向けの区間 `WH_JP_Released->DC_TH` の関税の課税価格の
決め方（G4）。課税価格 ＝ 振替価格（クリーム 5,000・美容液 6,000 円/個、運賃別）＋ タイまでの運賃 70 円/個
＋ 保険・その他 0（明示）。関税は DC_TH の受入の週（通関の確定の週の代用）に日本本社の在庫原価として計上し、
税率 0%（M4）の出荷には関税の行を立てず、`vc_customs_valuation.csv` に課税価格を 1 行ずつ残す（689 行、
課税価格の合計 93,197,520 円、税額 0）。税率は `ppc_tariff_rule.csv` から読む。PPC はこの表を読まず、
振替価格だけに課税する。

`vc_trade_terms.csv` は Value Chain 用の、シンガポール向けの区間 `WH_JP_Released->DC_SG` の取引条件（G5）。
CIF シンガポール：運賃は日本本社（`E_JP`）が負担し、法人間価格（クリーム 5,000・美容液 6,000 円/個）に含める
（`seller`・`1`）。海上運賃は出荷の週に `E_JP` の法人間売上の原価として計上し（3,367 件、4,848,480 円）、
シンガポール販社（`E_SG`）の取得は法人間価格だけになる。グループの在庫原価には運賃が 1 回入り、消去する
未実現利益は運賃の分だけ小さくなる。法人別の利益は `E_JP` −4,848,480 円・`E_SG` ＋4,848,480 円（和は同じ）、
消去後の連結の利益とグループの在庫は表が無いときと同じ。PPC は法人を持たず、この表を読まない。

## 実行の方法

CLI（リポジトリの根から）：

```bash
python -m tools.run_headless_from_folder --model-dir data/sample/cosmetics-sg-th-2027-2029
```

```bash
python -m tools.shelf_life_check --model-dir data/sample/cosmetics-sg-th-2027-2029 --max-age-weeks 52
```

```bash
python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/valuechain/cosmetics
```

GUI：`python -m main` → Load Model Folder でこのフォルダを選ぶ → Run Planning Engine。プラグインの
チェックは `planning_config.csv` の `recommended_plugins` に自動で合う。

## 期待する結果

| 項目 | 値 |
|---|---|
| 期間 | 2026-W37 から 173 週 |
| Flow Check 表2 | 需要 4,056 lot（美容液 2,288、クリーム 1,768）を全量、納期どおりに充足。未充足 0 |
| PPC | `評価済み`。売上 1,156,284,480 円、費用 524,434,872 円、試算利益 631,849,608 円（54.6%） |
| 製品の年齢 | 最大 6 週（直営店 6 週、ほか 4 週）。52 週超 0 |
| Value Chain（`vc_ppc_comparison.csv`、利益 合計、消去前） | PPC 631,849,608 円、台帳 631,849,608 円、差 0 円（G2 の MDF を計上した後。前は差 22,196,148 円） |
| Value Chain の直販の売上比率の費用（G1） | 全期間 281,015,748 円（うち配送・梱包 6,243,120 円）。販売の週に費目ごとに 1 行。issues 0 |

「試算利益」は、今回対象にした費用を控除した PPC の値で、営業利益ではない。

| SKU・チャネル | 売上（円/個） | 費用（円/個） | 試算利益（円/個） |
|---|---:|---:|---:|
| 美容液 直営店 | 18,975.00 | 10,940.75 | 8,034.25 |
| 美容液 公式 EC | 18,055.00 | 8,163.50 | 9,891.50 |
| 美容液 代理店（SG） | 8,510.00 | 2,827.50 | 5,682.50 |
| 美容液 代理店（TH） | 8,550.00 | 2,837.50 | 5,712.50 |
| クリーム 直営店 | 15,870.00 | 9,243.50 | 6,626.50 |
| クリーム 公式 EC | 15,065.00 | 6,966.50 | 8,098.50 |
| クリーム 代理店（SG） | 7,130.00 | 2,458.50 | 4,671.50 |
| クリーム 代理店（TH） | 7,200.00 | 2,470.00 | 4,730.00 |

## 既知の限界

**計画**

- 休業日を置いていない（`holiday_calendar.csv` は見出しの行だけ）。工場・DC・店は毎週動く仮定。
- 配分の週の粒度（U4）：配分の案は SKU × チャネルの lot 数で渡し、減らす週は道具が需要の形に比例して
  散らす。どの週から減らすかを業務として決めたわけではない。
- 計画の境界の効果：計画の最初の週へ押し戻された lot は原料のリードタイムで作れず、最後の 2 週の生産の
  余裕は使えない。配分の案に数 lot の未充足が出るのはこのため。

**金額**

- 歩留まりの損は原価に入っていない。原価は約 3% 低い（M3）。
- 店舗の運営費は売上の 35% の近似で、固定費ではない。売上が下がると費用も下がり、損益を良く見せる（M5）。
- 日本本社の固定費が無い。試算利益はグループの営業利益ではない（M6）。
- タイの関税は 0% の仮定。一般税率 30% なら試算利益は 27,612,000 円減る（M0t）。
- 関税の課税価格：PPC は振替価格だけに課税する。Value Chain は運賃を足した課税価格を使う（G4、下）。
  税率 0% なので今は差 0。30% にすると Value Chain は 27,959,256 円、PPC は 27,612,000 円（差 347,256 円）。

**Value Chain**

G1〜G5 の業務定義（採用済み）どおりに計上されることを、代表の lot と全期間の照合で確かめた。法人別・連結の損益を、経営の判断に使える水準だと判定したわけではない（上の「金額」の限界が残る）。

- G1：**解決済み（直販）**。直営店・公式 EC の売上比率の費用を、販売の週に費目ごとに計上する
  （`vc_sales_cost_rule.csv`。報告書 `docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md`）。
  `vc_ppc_comparison.csv` では、配送・梱包 6,243,120 円が台帳は「運賃」、PPC は「SGA」に入る（合計は同じ）。
- G2：**解決済み（2026-11-12）**。代理店向けの販促協賛金（MDF）を、代理店への卸売の週に税抜卸売額の 5% で、売り手（シンガポール販社・日本本社）の販売費として計上する（`vc_sales_cost_rule.csv` の `distributor_mdf`。報告書 `docs/development/WOM_BSSEAF_Cosmetics_G2_DistributorMDF_Report.md`）。PPC は代理店の leaf の出荷週（1 週遅い）に立てる。
- G3：解決済み（2026-11-08）。代理店の売上は DC の出荷週に立ち、業務定義（出荷時の認識、`docs/design/drafts/WOM_G3_SellIn_Business_Definition_v0.1.md`）どおり。PPC は代理店の leaf の出荷週（1 週遅い）に立てる別の方式で、照合用の参考値（`docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md`）。
- G4：**解決済み（Value Chain）**。タイ向けの関税は課税価格（振替価格 ＋ 運賃 ＋ 保険 0）× 税率で、DC_TH の
  受入の週に計上する（`vc_customs_valuation_rule.csv`。報告書 `docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_Report.md`）。
  通関の確定の週は受入の週で代用している。PPC は照合の参考値のまま。
- G5：**解決済み（Value Chain、2026-11-12）**。CIF シンガポールの海上運賃は、出荷の週に日本本社の法人間売上の
  原価として計上する（`vc_trade_terms.csv`。報告書 `docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_Report.md`）。
  シンガポール販社の在庫原価は法人間価格だけ、グループの在庫原価には運賃が 1 回入る。PPC は法人を持たないので、
  照合は全期間の運賃の合計（4,848,480 円）だけ。

**画面**

- Management の Tariff & FX パネルは空のまま（`edge_cost_master.csv` が見出しだけ。シナリオ別のルート費用を
  置いていない）。関税は PPC の `ppc_tariff_rule.csv` で計算している。
- Management の Inv Value・CCC・AR・AP は 0（`sku_master.csv` に単価・回転日数を置いていない）。
- PPC タブの Cost Waterfall の GM は 1 lot 当たりの平均で出す値（53.4%）で、全体の 54.6% とは違う。

## このフォルダの CSV について

登録した CSV を正本とする。試行でモデルを作った生成の道具は試行の記録で、このサンプルの入力ではない。
値を変えるときは CSV を直接直し、`docs/scenarios/cosmetics.md` と golden を合わせる。

`source=warmup` の行は助走の行で、`warmup_lt=17` から生成されたものが既に入っている（実行しても
書き換わらない）。
