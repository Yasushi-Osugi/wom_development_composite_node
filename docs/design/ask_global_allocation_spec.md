# ASK 仕様書: `ask_global_allocation` v0r4

**グローバル生産配分シミュレーション — 外部環境パラメータ感度モデル**

| 項目 | 内容 |
|---|---|
| ASK ID | `ask_global_allocation` |
| Version | **v0r4** |
| 前版 | v0r3 (2026-08-05) |
| WOM 層 | Management 層(戦略配分層) |
| 対象ブランチ | `wom-v1r4m0`(baseline = `wom-v1r3m0`) |
| 実装依頼書 | `requests/global-allocation-request-letter.md` Rev 3<br>`requests/Phase6-2_RequestLetter_to_CodeKun.md`(次元の一般化)<br>`requests/Phase6-2a_RequestLetter_to_CodeKun.md`(N市場 E2E) |
| 参照実装 | `tools/proto_terrain2.py`(3 市場のみ) |
| 検証ケース | `data/sample/soysauce-jpy-2027-alloc/` |
| 状態 | Phase 6-2 まで実装済み(388 件全 PASS)。Phase 6-3(階層化)は未着手 |

---

## 0. v0r2 からの変更点

本版は **実 CSV(`soysauce-jpy-2027`)の確認と、プロトタイプによる地形実測**の結果を反映する。v0r2 は WOM の実装を確認する前に書かれており、**複数の箇所で WOM の挙動と食い違っていた**。本版はその是正である。

| # | 変更 | 理由 |
|---|---|---|
| ① | `natural_hedge_ratio` → **`fx_exposure_balance`(FXB)** | ヘッジ比率 `h` との混同を避ける。測っているのは「収入側と原価側の通貨構成の釣り合い」であり balance が正確 |
| ② | 関税基準 CIF → **`transfer_price`** | WOM の `ppc_tariff_rule.csv` は `tariff_basis = transfer_price`。グループ内取引の実態としても正しい |
| ③ | `oil_brent_usd` → **`material_price_usd`** | WOM は原油を独立変数として持たず、`ppc_supplier_cost.csv` の USD 価格ステップで表現する。より直接的 |
| ④ | 原価ブロックを**入力から導出へ** | WOM は原価の原産地分離を SC ツリー構造で既に表現している。既存 CSV から導出可能であることを実測 4 点で検証済み |
| ⑤ | 粒度束縛に**市場軸を追加** | soysauce は 6 市場。三角形の地図には 3 市場への集約が必要であり、これも粒度束縛である |
| ⑥ | Step 7 を **Demand Anchored に修正** | WOM は需要を超えて生産しない。v0r2 の「余剰生産を機会損失として計上」は誤り |
| ⑦ | **交互作用・台地の実測値を収録** | 交互作用は 1% ではなく −18〜−40%。最適点の失敗モードは平面化ではなく台地化 |

### 特に重要な二つの訂正

**(a) 交互作用は残差ではなく主役である**

v0r2 は交互作用を「総効果の 1% 程度の残差」と想定していた。soysauce の実測では **−18〜−40%**、国内厚めの配分では**結論の符号を反転させる**規模である。原料が USD 建てであることによる乗法的相互作用が原因。

**(b) 失敗モードは平面化ではなく台地化である**

v0r2 は「価格固定・弾力性なしなら利益が配分の線形関数になり、地形が傾いた平面に退化する」と記述したが誤り。Demand Anchored により `min()` の折れ線が必ず入るため、地形は常に非線形になる。実際の失敗モードは**最適点が広い台地の上に乗って不定になる**ことである。

### 本版で実装しないもの

| 項目 | 送り先 | 理由 |
|---|---|---|
| 価格弾力性 ε | v0r4 | WOM に相当機構がない。まず能力拘束で地形を成立させる |
| 関税吸収率 α | v0r4 | 同上 |
| 輸送費の燃費感応度 β | v0r4 | `ppc_edge_cost_rule.csv` への列追加が必要(既存 21 CSV の変更) |
| 形態選択(FG/SKD/CKD) | v0r4 | 粒度構造の変更を伴う |
| FTA / 原産地規則 | v0r5 | β と形態選択に依存 |
| 多期間化(在庫繰越) | v0r4 | 形態選択と同時 |

> **注(v0r4 で追記)**: 上表の送り先 `v0r4` / `v0r5` は「本版より後の版」という意味であり、**版番号と一対一に対応しない**。実際の v0r4(本版)は Phase 6 の市場軸束縛の変更のみを扱っており、上表の項目はいずれも未実装である。ロードマップの実体は Phase 番号(Phase 6 / 7-9)の側にある。

---

## 0b. v0r3 からの変更点(Phase 6・市場軸の束縛)

**本版は市場軸の粒度束縛を「モデル全体で 3 市場」から「1 ノードあたり 3 市場」に読み替える。** Phase 6-2(`32b2544`)で配分エンジンが N 市場化され、v0r3 の記述が実装と食い違ったためである。

| # | 変更 | 理由 |
|---|---|---|
| ⑧ | §2.4 束縛を **「1 ノードあたり 3 市場」** に変更 | 3 市場束縛の根拠は「三角図として描けること」と「経営が一度に比較できる数」の 2 つ。階層化はどちらも壊さない——どのノードでも見るのは 3 つ以下である。束縛は廃止ではなく**適用範囲の変更**で足りる |
| ⑨ | §2.5 の **「4 市場以上の指定 → 拒否」を撤回** | `scan_surface()` は N=4〜6 を受理する。拒否するのは格子点数が `MAX_GRID_POINTS` を超えたときだけである。**なおこの拒否ルールは実装されたことが一度もない**(3 市場を強制していたのは三角図の描画側だけ)。仕様書だけが 3 市場固定を言い続けていた |
| ⑩ | §4.2 の **`market_group` 3 種以下の制約を撤廃**し、`internal_ratio` の意味を 1 つに確定 | この列はコード上**原価集約の重みとしてしか使われていない**(`cost_block.py` の `w = ratio / tot_ratio` 1 箇所)。「グループ内配分を固定する」という意味は実装されたことがなく、3 市場モデルにその変数が無かっただけである。階層化でも列の役割は変わらない |

**⑧〜⑩ はいずれも「実装が先に進み、仕様書が取り残された」ことの是正である。** v0r2 → v0r3 が「WOM の実装を確認する前に書かれていた」ことの是正だったのと同じ構図であり、**仕様書は実装の後ろを追いかける版があってよい**——ただし追いかけ損ねたまま放置しない、という運用にする。

---

## 1. 目的とスコープ

### 1.1 解く問題

生産能力が需要を下回る状況において、限られた能力を複数の販売市場にどう配分するかを決定する。外部環境パラメータ θ =(関税, 為替, 原料価格, 金利)の変動が、自社の売上・営業利益にどう影響するかを配分比率空間の全域で評価する。

検証ケース: 日本(千葉県野田)に醸造拠点を持つ醤油メーカーが、国内 / 対米輸出 / 対欧輸出の配分を決定する。醸造は 4 週の発酵期間を要し短期増産できない。

### 1.2 既存 WOM 運用との関係

本 ASK は置き換えではなく**上流への拡張**である。

```
現状(v1r2m0 で確立):
  soysauce-us-2027 フォルダ ─┐
                              ├ demand_forecast.csv の配分だけが違う 2 点を手作業で比較
  soysauce-eu-2027 フォルダ ─┘

本 ASK:
  ask_global_allocation ─→ 配分比率 231 通りを自動評価し、利益地形を得る
```

sc_tree は不変。変わるのは `demand_forecast.csv` の region 別配分のみである。

### 1.3 スコープ内

- 外部環境パラメータの、調達原価・輸送費・移転価格・関税・運転資本への伝達
- 為替エクスポージャーの収入側 / コスト側の分離評価(FXB)
- 意思決定レートと決済レートの乖離が配分に与える影響
- 配分比率空間全域における営業利益の評価(利益地形)
- 台地の検出と `robust_point`(ミニマックス点)の算出
- 非経済的制約のコスト定量化

### 1.4 スコープ外

| 非目的 | 理由 |
|---|---|
| 設備投資判断 | 既存キャパシティ内の配分に限定 |
| 週次オペレーション計画 | 下位 PSI 層の責務 |
| SKU 別の需要予測 | 製品クラス粒度で束縛 |
| BOM 全展開 | 原価ブロックは 5〜7 に束縛 |
| 一般均衡効果 | 部分均衡モデル。競合価格は外生 |
| 為替・原料価格・金利の予測 | すべて外生シナリオ |
| 価格弾力性・関税転嫁 | v0r4 |
| 現地組立・FTA | v0r4 / v0r5 |

---

## 2. 粒度束縛の宣言(Granularity Binding Declaration)

### 2.0 束縛の根拠 — 粒度は上下から挟まれる

モデルの粒度は設計者が自由に選べるものではなく、**入力パラメータの解像度(下限)と意思決定の解像度(上限)の両方から決定される**。下限を割ってモデルを細かくした場合、その細部は精緻化ではなく**捏造**となる。

### 2.1 時間軸: 四半期(13 週バケット)

- 束縛: すべての量・金額は四半期単位で集計
- 下限: 価格改定ラグ・在庫回転が四半期単位でしか観測できない
- 上限: 配分の意思決定周期が四半期

> **soysauce での運用**: 検証ケースは 104 週(2027-W01〜2028-W52)。8 四半期に集計する。ただし v0r3 の初期実装では**全期間一括**での評価も許容する(FX の時系列変化を扱わない簡易モード)。

### 2.2 製品軸: 製品クラス(3〜5)/ 原価ブロック(5〜7)

- 束縛: SKU ではなく製品クラス
- 原価ブロックは**導出**するが、ブロック数は 5〜7 に束縛する
- 根拠: ブロックの目的は「調達通貨と価格感応度が異なるコスト塊の分離」であり部品管理ではない。8 個以上では構成比が安定推定できない
- BOM 全展開は製品軸の粒度束縛違反であり拒否する

> **soysauce での実績**: 1 製品(`Soy_Sauce`)。原価ブロックは通貨別に集約すると 3 群(USD / EUR / JPY)、ノード種別で分けると 6〜7 群。**製品軸の粒度束縛は soysauce では実質的に検証されない**(複数 SKU ケースへ持ち越し)。

### 2.3 フロー軸: 配分比率 [%](ロットではない)

- 束縛: 決定変数は市場別配分比率 x ∈ [0,1], Σ x = 1
- **刻み幅 δ = 0.05 はフロー軸の粒度宣言そのものである。** 「配分比率を 5% 未満の精度で主張しない」という宣言に等しい
- δ を細かくする要求は**拒否してよい**。α・ε の推定精度がそこまで高くないため、細部は捏造になる
- ロットへの復元は下位 PSI 層への受け渡し時のみ

### 2.4 市場軸: 1 ノードあたり 3 市場(v0r3 で新設・v0r4 で適用範囲を変更)

**決定変数が市場空間に住むため、市場軸にも粒度が存在する。** これは WOM の正典三軸(時間・製品・フロー)への本 ASK 固有の拡張である。

- 束縛: **1 ノードあたり 3 市場**(v0r4 で変更。v0r3 までは「モデル全体で 3 市場」だった)。**モデル全体の市場数に上限はない**
- 根拠(上限): 3 市場なら配分空間は 2 次元単体 = 三角形となり、**地図として描ける**。4 市場では三次元四面体となり平面に描けない。**ただしこれは三角図の制約であって、計算エンジンの制約ではない**(Phase 6-2 で分離済み。`tools/plot_allocation_map.py` の `_require_three_markets()` が三角図側だけを N=3 に縛る)
- 根拠(下限): 2 市場では単体が線分となり、地形の概念が成立しない
- **可視化の制約であると同時に、経営が同時に比較検討できる市場数の上限でもある。** 階層化(Phase 6-3)はこの上限を壊さない——木のどのノードでも、経営者が一度に見るのは 3 つ以下である
- 内部配分: **3 市場モードでは固定比率・最適化の対象外**(従来どおり)。**階層モードでは各ノードの決定変数**となる。`internal_ratio` 列そのものの役割は変わらない(§4.2 参照)
- 計算上の上限は市場数ではなく**格子点数**である。`C(1/δ + N − 1, N − 1)` が `MAX_GRID_POINTS`(既定 100,000)を超えると `scan_surface()` が計算前に停止する(δ=0.05 で N=6 は 53,130 点で通り、N=7 は 230,230 点で止まる)

> **soysauce での集約**
>
> | 集約先 | 内訳 region | 数量 | 比率 | 内部固定比 |
> |---|---|---|---|---|
> | JP | JP | 30,150 | 30.0% | — |
> | US | US_W, US_E | 35,176 | 35.0% | 1 : 1 |
> | EU | FR, BE, NL | 35,175 | 35.0% | 1.5 : 1 : 1 |
>
> 基準配分 (x_JP, x_US, x_EU) = **(0.300, 0.350, 0.350)**
>
> 「EU 内・US 内の配分は最適化しない」という宣言でもある——**ただし 3 市場モードでの話である**。階層モード(Phase 6-3)では、EU 内 3 地域・US 内 2 地域が下位ノードの決定変数になる。したがって階層モードの最良点は 3 市場モードの最良点**以上**になる(一致しない)。これは不具合ではなく、階層化が獲得した自由度である。

### 2.5 束縛違反時の挙動

以下は仕様上の**エラー**であり、暗黙の内挿・補完を行わない。

| 違反 | 挙動 |
|---|---|
| 週次データの入力 | 拒否。四半期集計を要求 |
| SKU 単位の需要データ | 拒否。製品クラスへの集約規則の提示を要求 |
| ロット数量の直接指定 | 拒否。比率への変換を要求 |
| 原価ブロックが 8 個以上 | 拒否。集約規則の提示を要求 |
| 導出ブロックの合計が原価総額と不一致 | 拒否。自動補正しない |
| **4 市場以上の指定** | **受理**(v0r4 で変更。v0r3 は「拒否」としていたが、この拒否は実装されたことがない) |
| 格子点数が `MAX_GRID_POINTS` 超過 | 拒否。階層化(`hierarchical_simplex`)の使用を要求。**点を生成する前に止める** |
| 三角図(`plot_allocation_map`)に N ≥ 4 を渡す | 拒否。2 次元射影が定義できない。階層ドリルダウンを要求。**黙って上位 3 市場だけ描くことは禁止** |
| δ < 0.01 の指定 | 拒否。粒度宣言に反する |

---

## 3. 記号と集合

### 3.1 集合

| 記号 | 意味 | soysauce での値 |
|---|---|---|
| `P` | 生産拠点 | {Bottling_Noda}(終端 MOM) |
| `M` | 販売市場(集約後) | {JP, US, EU} |
| `K` | 製品クラス | {Soy_Sauce} |
| `B` | 原価ブロック(導出) | {material, logistics, brewing, bottling, warehouse, dc_local, sga} |
| `T` | 四半期 | 2027Q1〜2028Q4 |
| `S` | シナリオ | {base, weak_yen, oil_shock, compound, strong_yen, ...} |
| `C` | 通貨 | {JPY, USD, EUR} |

### 3.2 決定変数

| 記号 | 定義 | 範囲 |
|---|---|---|
| `x[m,t]` | 市場 m への配分比率 | [0,1], Σ_m x = 1 |

### 3.3 外部パラメータ(シナリオベクトル θ)

| 記号 | 意味 | 単位 | v0r2 からの変更 |
|---|---|---|---|
| `τ[m,k,s,t]` | 従価関税率 | 比率 | 課税ベースが変更(§5 Step 3) |
| `e[c,s,t]` | 為替スポットレート | JPY / 通貨 c | — |
| `pm[s,t]` | **原料価格** | **USD / lot** | **`o`(原油)から置換** |
| `i[s,t]` | 調達金利(年率) | 比率 | — |

### 3.4 為替レートの三系統

| 記号 | 用途 | 使用箇所 | 正本 |
|---|---|---|---|
| `e_set[c,s,t]` | **決済レート** | 原価換算・売上計上 | **`ppc_fx_rate.csv`**(既存。参照のみ) |
| `e_dec[c,t]` | **意思決定レート** | 配分判断 | `ga_fx_policy_master.csv`(新規) |
| `e_trf[c,t]` | **移転価格レート** | 移転価格・関税課税ベース | `ppc_transfer_price_rule.csv`(既存) |

`e_dec` は**シナリオに依存しない**。社内レートは外部環境の実現値と無関係に据え置かれるためであり、この非依存性が §7.6 の機会損失を生む源泉となる。

### 3.5 構造パラメータ

| 記号 | 意味 | 範囲 | v0r3 での扱い |
|---|---|---|---|
| `w[k,b]` | 原価ブロック構成比 | Σ_b w = 1 | **導出**(§5 Step 0.5) |
| `mr[p,k]` | 移転価格マージン率 | ≥ 0 | 既存 `ppc_transfer_price_rule.csv`(soysauce は 0.10) |
| `h[c,t]` | 為替ヘッジ比率 | [0,1] | `ga_fx_policy_master.csv` |
| `R[c]` | 社内レート改定ラグ | 四半期数 | 同上 |
| `Cap[p,t]` | 生産能力 | lot | 既存 `capacity_plan.csv` |
| `D[m,t]` | 需要 | lot | 既存 `demand_forecast.csv`(集約後) |
| ~~`α[m,k]`~~ | 関税吸収率 | — | **v0r4 送り** |
| ~~`ε[m,k]`~~ | 価格弾力性 | — | **v0r4 送り** |
| ~~`β[lane]`~~ | 輸送費の燃費感応度 | — | **v0r4 送り** |

---

## 4. データスキーマ

### 4.1 既存 CSV(読み取りのみ・変更禁止)

| ファイル | 本 ASK での用途 |
|---|---|
| `sc_tree_master.csv` | チャネル経路の抽出(leaf_out から root まで) |
| `demand_forecast.csv` | 市場別需要(集約して D[m] を得る) |
| `capacity_plan.csv` | 生産能力 Cap[p] |
| `ppc_supplier_cost.csv` | 原料費ブロック(通貨・週次ステップ) |
| `ppc_edge_cost_rule.csv` | 物流費ブロック(通貨) |
| `ppc_node_cost_rule.csv` | 加工費・倉庫費・SGA ブロック(通貨) |
| `ppc_transfer_price_rule.csv` | 移転価格ルール(`cost_plus`、マージン率、通貨) |
| `ppc_tariff_rule.csv` | 関税率・課税ベース(`tariff_basis`) |
| `ppc_market_price.csv` | 市場価格・通貨 |
| `ppc_fx_rate.csv` | 決済レート(`base_currency` 自動検出の起点) |
| `ppc_node_profit_zone.csv` | node → country マッピング |
| `sku_master.csv` | `dso_wks` / `dpo_wks`(運転資本) |

### 4.2 新規追加 CSV(3 ファイル)

#### `ga_market_aggregation.csv`

```
market_group, region, internal_ratio, note
JP, JP,   1.0000, 
US, US_W, 0.5000, internal_ratio は原価集約の重み（§2.4 参照）
US, US_E, 0.5000,
EU, FR,   0.4286,
EU, BE,   0.2857,
EU, NL,   0.2857,
```

制約: 同一 group 内の `internal_ratio` の合計 = 1.0(誤差 1e-6)。

**`market_group` の個数制限は v0r4 で撤廃した**(v0r3 までは「3 種以下」)。3 市場モードでは 3 種に揃えるのが前提だが、**仕様上の拒否理由にはしない**(§2.5)。

**`internal_ratio` の意味は 1 つだけである**——**原価ブロックを集約するときの重み**。実装は `wom/allocation/cost_block.py` の `w = float(r["internal_ratio"]) / tot_ratio` の 1 箇所のみで、ここでしか使われていない。**「グループ内の配分を固定する」という意味は実装されたことがない。** 3 市場モデルにグループ内配分の決定変数がそもそも無く、結果として固定されていただけである。したがって階層化(Phase 6-3)がグループ内配分を最適化しても、**この列の役割は変わらない**。

なお `region` 列は、階層化における**下位ノードの葉**にそのまま対応する。`market_group` 列は**グルーピングの正解表**として `build_hierarchy()` の検証に使える(Phase 6 設計書 §5.5(2))。

#### `ga_scenario_master.csv`

```
scenario_id, quarter, currency_or_market, tariff_rate,
fx_spot_jpy, material_price_usd, interest_rate_annual, note
```

制約: `material_price_usd` と `interest_rate_annual` は同一 (scenario_id, quarter) 内で一意(グローバル変数)。

#### `ga_fx_policy_master.csv`

```
currency, quarter, rate_type, rate_jpy, applied_to, coverage_ratio, revision_lag_q
```

- `rate_type = internal` の行のみが必須(`applied_to = decision`)
- `settlement` は `ppc_fx_rate.csv` から取得するため、本ファイルには `hedge`(forward + coverage_ratio)のみ記述する

### 4.3 廃止

| ファイル | 理由 |
|---|---|
| ~~`ga_cost_block_master.csv`~~ | **既存 CSV から導出可能(§5 Step 0.5)。実証済み** |
| ~~`ga_market_master.csv`~~ | 価格は `ppc_market_price.csv`、需要は `demand_forecast.csv` から取得。ε / α は v0r4 送りのため本版では不要 |
| ~~`ga_lane_master.csv`~~ | 物流費は `ppc_edge_cost_rule.csv` から導出 |
| ~~`ga_plant_master.csv`~~ | 能力は `capacity_plan.csv` から取得 |
| ~~`ga_hedge_master.csv`~~ | `ga_fx_policy_master.csv` に統合(v0r2 で実施済み) |

**v0r2 の 7 ファイルから 3 ファイルへ減少した。** これは既存 WOM 資産の再利用が進んだ結果であり、二重管理の回避という点で望ましい。

---

## 5. 伝達式(Transmission Equations)

評価順序は依存関係により固定される。**Step 0.5 と Step 7 が v0r3 の主要な変更点である。**

### Step 0: レートの解決

```
e_set[c,s,t] = h[c,t] × rate_forward[c,t] + (1 − h[c,t]) × e_spot[c,s,t]
               ※ e_spot は ppc_fx_rate.csv から取得
e_dec[c,t]   = rate_internal[c, t − R[c]]      （シナリオ非依存）
e_trf[c,t]   = ppc_transfer_price_rule.csv の currency に対応する e_set
```

### Step 0.5: 原価ブロックの導出【v0r3 新設】

**原価ブロックは入力ではなく導出物である。**

```
for each leaf_out チャネル c:
    経路 = sc_tree_master を leaf_out から root まで遡って得たノード列・エッジ列

    for each ノード n in 経路:
        ppc_node_cost_rule の (n, product) 行を通貨別に加算
    for each エッジ e in 経路:
        ppc_edge_cost_rule の (e, product) 行を通貨別に加算
    原料費:
        ppc_supplier_cost の leaf_in 行（週次 latest-prior-week 参照）

    → ブロック集合 {(block_id, currency, amount_local)} を得る
```

**通貨判定**: `currency != base_currency` であれば外貨建。v0r2 の `fx_exposure_flag` は不要。

**出力**: `output/allocation/ga_cost_block_derived.csv`(監査用)

> **soysauce での導出結果**(1 lot = 1CS = 12×1L)
>
> | チャネル | USD 建て | EUR 建て | JPY 建て |
> |---|---|---|---|
> | JP | 9.10 | — | 1,725 |
> | US(W/E 平均) | 15.65 | — | 1,575 |
> | EU | 14.60 | 2.15 | 1,575 |
>
> ※ 関税は Step 3 で別途加算されるため、上表には含まれない。

### Step 1: 製造原価の合成

```
unit_cost_ex_tariff[c,s,t]
  = Σ_b ( amount_local[c,b] × e_set[currency_b, s, t] )

ただし 原料ブロックの amount_local は pm[s,t]（シナリオの原料価格）で上書きする
```

**v0r2 との差**: v0r2 は `c0 × Σ w × (e/e_base) × (1 + γ(o/o_base − 1))` という比率合成だった。v0r3 は**通貨別の実額 × 為替**という直接合成に変更する。基準値からの比率を取る必要がなくなり、`ga_baseline_master.csv` も不要になる。

### Step 2: 移転価格【v0r3 新設】

```
transfer_price_local[p,k,t]
  = 終端MOM の累積 unit_cost × (1 + mr[p,k])
    （ppc_transfer_price_rule.csv の currency 建て）
```

> soysauce: `Bottling_Noda` 累積原価 16.0 USD × 1.1 = **17.6 USD**

### Step 3: 関税【v0r3 で課税ベースを変更】

```
duty_local[m,k,s,t] = τ[m,k,s,t] × transfer_price_local
```

**v0r2 との差**: v0r2 は `τ × CIF_local`(CIF = 製造原価 + 輸送費 + 保険)としていた。WOM の `ppc_tariff_rule.csv` は `tariff_basis = transfer_price` であり、こちらに合わせる。

**重要な帰結**: 移転価格が USD 建てで固定されているため、**円安が円建て関税額を押し上げる経路が存在する**。

```
円安 → 円建て移転価格 ↑ → 課税ベース ↑ → 円建て関税額 ↑
```

この経路は WOM に既に存在しており、v0r2 では表現できていなかった。

> soysauce: US 12.5% × 17.6 = **2.20 USD**、EU 8% × 17.6 = **1.408 USD**、JP 0%

### Step 4: チャネル原価の確定

```
unit_cost[m,s,t] = unit_cost_ex_tariff[m,s,t] + duty_local[m,s,t] × e_set[c_duty,s,t]
```

> soysauce(FX=150、EUR=162、原料 $6.0)
>
> | 市場 | 原価(JPY/lot) | 売価(JPY/lot) | マージン |
> |---|---|---|---|
> | JP | 3,090 | 3,840 | **750(19.5%)** |
> | US | 4,252 | 6,000 | **1,748(29.1%)** |
> | EU | 4,324 | 6,156 | **1,832(29.8%)** |

### Step 5: 販売価格

```
price_jpy[m,s,t] = market_price_local[m] × e_set[c_m, s, t]
```

**v0r4 でも価格は外生固定**である(`ppc_market_price.csv`)。為替転嫁 φ・関税転嫁 α による価格改定は**後続版**で導入する(§0 の注を参照。本版 v0r4 は市場軸束縛の変更のみを扱う)。

### Step 6: 需要

```
D[m,t] = Σ_{region ∈ m} demand_forecast[region, week ∈ t]
```

**v0r4 でも需要は外生固定**である。価格弾力性 ε は**後続版**で導入する(§0 の注を参照)。

### Step 7: Demand Anchored 数量確定【v0r3 で修正】

```
supply[m,t]     = x[m,t] × Cap[p,t]
production[m,t] = min( supply[m,t] , D[m,t] )       ← 需要を超えて生産しない
idle[t]         = Cap[p,t] − Σ_m production[m,t]
unmet[m,t]      = D[m,t] − production[m,t]
```

**v0r2 との差**: v0r2 は「余剰は当期の機会損失として記録」としていたが、WOM は Demand Anchored Lot を基礎とするため**需要を超えた生産は行わない**。余った能力は遊休となり、売れ残り在庫は発生しない。

**この `min()` が利益地形に折れ線(尾根)を生む。** 尾根線の位置は:

```
x[m] = D[m] / Cap
```

> soysauce(能力 800/週 × 104 週 = 83,200 lot)
> ```
> x_JP = 0.362    x_US = 0.423    x_EU = 0.423    合計 = 1.208 > 1
> ```
> 合計が 1 を超えるため**全市場の需要を同時に満たせない**。配給(rationing)が必要となり、配分の意思決定が意味を持つ。

### Step 8: 売上

```
revenue_jpy[m,s,t] = production[m,t] × price_jpy[m,s,t]
```

### Step 9: 運転資本費用

```
inventory_weeks = lead_time_weeks + coverage_weeks     （sc_tree_master の lt_wks, ss_days）
inventory_value = (inventory_weeks / 13) × production × unit_cost
receivable      = (dso_wks / 13) × revenue_jpy
payable         = (dpo_wks / 13) × (production × unit_cost)
wc_cost         = (i[s,t] / 4) × (inventory_value + receivable − payable)
```

> soysauce: `sku_master.csv` の dso=8週 / dpo=6週 → CCC ≒ +2週

### Step 10: 損益

```
cogs         = Σ_m production[m] × unit_cost[m]
sga          = Σ_m revenue_jpy[m] × sga_rate
gross_profit = revenue_jpy − cogs
op_profit    = gross_profit − wc_cost − sga − fixed_cost
```

### Step 11: FXB の算出【v0r3 で改名】

```
外貨建コスト  FC = Σ_m production[m] × ( unit_cost[m] − 円建ブロック合計 )
総コスト      TC = Σ_m production[m] × unit_cost[m]
外貨建収入    FR = Σ_{m: 売価通貨 ≠ JPY} revenue_jpy[m]
総収入        TR = Σ_m revenue_jpy[m]

FCR = FC / TC        外貨建コスト比率
FRR = FR / TR        外貨建収入比率
FXB = FCR / FRR      FX Exposure Balance
```

| FXB | 意味 | 円安時の含意 |
|---|---|---|
| ≈ 1.0 | 収入と原価の外貨エクスポージャーが均衡 | 為替中立 |
| < 1.0 | 収入の外貨比率が原価を上回る | 円安が利益にプラス |
| > 1.0 | 原価の外貨比率が収入を上回る | 円安が利益にマイナス |

**FXB は配分比率 x の関数である。** 配分の変更が為替エクスポージャーの符号を変えうる。

> **soysauce での実証**
>
> 基準配分 (0.300, 0.350, 0.350) において **FCR = 0.588 / FRR = 0.787 / FXB = 0.747**(円安メリット型)。
>
> **FXB = 1.0 の等値線は輸出比率 42.4%(国内 57.6%)を通る。** すなわち国内比率を上げると円安デメリット型に転じる。「国内回帰は為替リスクを下げる」という直感は誤りである(調達が外貨建のまま残るため)。
>
> CLAUDE.md 1077 行の実測がこれを裏付ける: 円安に対し US/EU の GM は 28-30% → 33-34% に改善する一方、Rest_JP は 19.5% → −2.7% に悪化した。

### 5.1 恒等式(V&V 用)

```
revenue_jpy − cogs − wc_cost − sga − fixed_cost − op_profit = 0
Σ_m x[m,t] − 1 = 0
Σ_b amount_local[c,b] × e_set = unit_cost_ex_tariff[c]      （導出の保存性）
Σ_{region ∈ m} internal_ratio = 1                            （市場集約の保存性）
```

---

## 6. 求解手続き

### 6.1 方針: 最適化ではなくグリッド全数評価

LP/MILP による単一最適解の算出は行わない。理由:

1. **出力しているものが違う**。LP の出力は一点、グリッドの出力は面
2. **説明可能性**。LP は地形情報を失い、反証にさらされたとき根拠を示せない
3. **将来の不連続性**。v0r5 の FTA 原産地規則で地形が不連続化する。グリッドなら各格子点で判定するだけで済む

WOM の README「It is not a solver that hands you *the optimal answer*; it is a model you run, watch, and reason about」と矛盾しない。**231 回 run しているだけ**である。

### 6.2 アルゴリズム

```
Step 0, 0.5 を事前実行（配分に依存しない）
for each scenario s:
  for each quarter t:
    Step 1〜6 を評価              ← 配分に依存しない
    for each x in Simplex(3, δ=0.05):    ← 231 点
      Step 7〜11 を評価
      レコードを profit surface に追加
```

格子点数 = C(22,2) = **231**

### 6.3 台地検出【v0r3 新設】

```
plateau = { x | profit(x) ≥ max_profit − |max_profit| × 0.001 }
```

| 台地サイズ | 判定 |
|---|---|
| 1 点 | 一意。意思決定が意味を持つ |
| 2〜5 点 | 準一意 |
| **6 点以上** | **台地。利益基準では決定できない → §6.4 へ** |

### 6.4 robust_point の算出【v0r3 新設】

台地が検出された場合、判断基準を利益から別軸へ移す。

```
robust_point = argmax_{x ∈ plateau} ( min_{s ∈ scenarios} profit(x, s) )
```

**台地の各点を全シナリオで評価し、最低利益が最大の点を選ぶ**(ミニマックス)。計算コストはゼロ(`ga_profit_surface.csv` の既存値の集計)。

台地上の点は利益こそ同じだが、以下が異なる。

| 軸 | 台地上での違い |
|---|---|
| FXB | 台地を FXB=1.0 線が横切る。同じ今期利益でも来期の感応度が正反対 |
| 遊休能力の配分 | どの市場の需要上振れに応えられるかが違う |
| 他シナリオでの標高 | 台地は「今の前提が続けば同じ」であり「何が起きても同じ」ではない |

### 6.5 制約コストの算出【v0r3 新設】

```
cost_of_constraint = max_x profit(x) − max_{x ∈ 制約領域} profit(x)
```

**必要性**: 円安×原油シナリオでの最適解は `x_JP = 0.00`(国内供給の完全停止)である。数値上は正しいが、醤油という商材で実行できる企業はまずない。「国内 20% を維持すると利益がいくら落ちるか」を定量化することで、経営判断の材料になる。

---

## 7. 出力仕様

### 7.1 `ga_profit_surface.csv`

```
scenario_id, quarter, x_JP, x_US, x_EU,
revenue_jpy, cogs, duty_cost, wc_cost, sga, fixed_cost, op_profit,
production_JP, production_US, production_EU, idle, unmet_total,
fcr, frr, fx_exposure_balance
```

### 7.2 `ga_cost_block_derived.csv`【新規】

```
channel, block_id, currency, amount_local, amount_jpy_at_base, source_file
```

導出の監査証跡。`source_file` により、どの既存 CSV 由来かを追跡可能にする。

### 7.3 `ga_fx_balance.csv`【改名】

```
scenario_id, quarter, x_JP, x_US, x_EU,
fcr, frr, fx_exposure_balance,
net_exposure_jpy_per_1pct, interpretation_ja
```

`interpretation_ja`: 「為替中立」/「円安メリット型」/「円安デメリット型」

### 7.4 `ga_plateau.csv`【新規】

```
scenario_id, plateau_size, plateau_points,
fxb_min, fxb_max,
robust_point, robust_worst_profit, argmax_worst_profit
```

### 7.5 `ga_constraint_cost.csv`【新規】

```
constraint_id, constraint_expr, scenario_id,
profit_unconstrained, profit_constrained, cost_of_constraint
```

### 7.6 `ga_sensitivity.csv` / `ga_interaction.csv`

```
ga_sensitivity.csv:
  parameter, delta_unit, d_op_profit_jpy, d_revenue_jpy, d_cogs_jpy, rank

ga_interaction.csv:
  scenario_pair, x_JP, x_US, x_EU,
  effect_single_1, effect_single_2, effect_combined,
  interaction, interaction_pct, layer_decomposition_valid
```

**`layer_decomposition_valid`** は `|interaction| ≤ 5% × |effect_combined|` の真偽値。**偽の場合、層分解による説明は無効である。**

### 7.7 `ga_switching_point.csv`

```
from_market, to_market, trigger_parameter, trigger_value, statement_ja
```

> soysauce の生成例:
> 「USD/JPY が 119 円を割った場合、米国向け配分を国内に振り替えるべき。」

### 7.8 `ga_fx_decision_gap.csv`

```
scenario_id, quarter, rate_internal, rate_settlement, gap_pct,
x_optimal_by_settlement, x_actual_by_internal, opportunity_loss_jpy
```

---

## 8. WOM 本体への接続

### 8.1 Demand Anchor への受け渡し

```
選択配分 x*[m,t]（四半期・市場グループ・比率）
   ↓ ① 市場グループ → region 展開（ga_market_aggregation.csv の internal_ratio）
   ↓ ② 四半期 → 週次展開（既存 demand_forecast.csv の週次プロファイルを比例配分）
   ↓ ③ 比率 → ロット丸め（cpu_size）
demand_forecast.csv（生成物）
```

**接続は「展開」ではなく「`demand_forecast.csv` の生成」である。** v1r2m0 で確立された case1 方式(sc_tree 同一、demand の配分だけを変える)の延長線上にある。

### 8.2 助走区間の保護

`planning_config.csv` の `warmup_lt`(soysauce は 26)により生成される助走行は **quantity = 0 のまま維持すること**。配分比率を掛けてはならない(D1「実需要の捏造禁止」に抵触する)。

### 8.3 逆流の禁止

```
✓  配分（四半期） → demand_forecast.csv（週次）
✗  週次実績 → 配分の自動修正
```

週次実績で配分を自動調整すると、戦略層が週次ノイズに振り回される。四半期に一度、人間が地図を見て決める——この頻度の分離が設計の要点である。

---

## 9. V&V 規準

### 9.1 宣言整合性(Verification 側)

| 検査項目 | 内容 |
|---|---|
| 市場数 | `ga_market_aggregation.csv` の `market_group` が 3 種以下 |
| 内部比率 | 同一 group 内の `internal_ratio` 合計 = 1.0(誤差 1e-6) |
| 配分和 | Σ_m x[m] = 1.0 |
| 刻み幅 | δ ≥ 0.01 |
| ブロック数 | 導出ブロックが 5〜7 |
| シナリオ一意性 | `material_price_usd` / `interest_rate_annual` が (scenario, quarter) 内で一意 |

### 9.2 変換保存性(三軸制約の中核)

```
時間軸: 週次 demand_forecast 13 週分の合計 = 四半期値        許容 < 0.1%
製品軸: SKU 展開後の合計 = 製品クラス値                      許容 < 0.1%
フロー軸: |Σ(lot_count × cpu_size) − x × Cap| ≤ cpu_size
市場軸: Σ_{region ∈ m} production[region] = production[m]    許容 < 0.1%
原価軸: Σ_b amount × e_set = unit_cost_ex_tariff             許容 1e-6
```

保存性違反は、**モデルのどこかに特定の粒度でしか成立しない仮定が存在すること**の物証である。反実仮想シナリオであっても検査可能であり、これが従来の Validation 手法との決定的な差となる。

### 9.3 モデル妥当性(回帰値)

**以下は `soysauce-jpy-2027-alloc` での実測値であり、実装はこれらを再現しなければならない。**

#### (a) 原価ブロック導出 — 実測 4 点

Rest_JP チャネルの GM:

| 条件 | 期待値 | CLAUDE.md 1077 行の実測 |
|---|---|---|
| FX 150 / 原料 $6.0 | **19.53%** | 19.5% |
| FX 200 / 原料 $6.0 | **7.68%** | +7.7% |
| FX 200 / 原料 $8.0 | **−2.73%** | −2.7% |
| FX 200 / 原料 $6.5 | **5.08%** | +5.1% |

許容誤差 0.1pp。

#### (b) 単位マージン(JPY/lot)

| FX | 原料 | JP | US | EU |
|---|---|---|---|---|
| 150 | $6.0 | 750 | 1,748 | 1,832 |
| 200 | $6.0 | 295 | 2,855 | 2,967 |
| 200 | $8.0 | **−105** | 2,455 | 2,567 |
| 115 | $6.0 | 1,068 | 972 | 1,037 |

#### (c) 需要天井(能力 800/週)

```
x_JP = 0.362    x_US = 0.423    x_EU = 0.423    合計 = 1.208
```

#### (d) 最適配分と台地サイズ

| シナリオ | 最適配分 | 最大利益 | 台地サイズ |
|---|---|---|---|
| 基準 USD 150 | (0.10, 0.45, 0.45) | 132.1M | **1** |
| 円安 USD 200 | (0.10, 0.45, 0.45) | 207.2M | **1** |
| 円安×原油 $8 | (0.00, 0.45, 0.55) | 176.7M | 3 |
| 円高 USD 115 | (0.35, 0.25, 0.40) | 85.8M | **1** |
| **能力 1,500(退化)** | (0.50, 0.25, 0.25) | 148.5M | **28** |

#### (e) FXB

```
基準配分 (0.300, 0.350, 0.350) → FCR = 0.588 / FRR = 0.787 / FXB = 0.747
FXB = 1.0 の等値線 → 輸出比率 42.4%
```

#### (f) 切替点

```
USD 119 円 を下回る → EU > US > JP から EU > JP > US
USD 117 円 を下回る → JP が 2 位に浮上
USD 100 円 付近     → JP > EU > US
```

#### (g) 交互作用(能力 800/週、円安 × 原油)

| 評価点 | 為替単独 | 原料単独 | 合計 | 交互作用 | 比率 |
|---|---|---|---|---|---|
| (0.30, 0.35, 0.35) | +54.0M | −25.0M | +20.7M | −8.3M | **−40.2%** |
| (0.10, 0.45, 0.45) | +75.1M | −23.6M | +43.6M | −7.9M | **−18.0%** |
| (0.60, 0.20, 0.20) | +23.6M | −19.0M | **−1.8M** | −6.3M | **符号反転** |

**交互作用は残差ではなく主役である。** 5% 閾値は soysauce では常に超過する。これは仕様の失敗ではなく、規準が正しく機能している証拠である。

### 9.4 構造的検証

| 項目 | 内容 |
|---|---|
| 損益恒等式 | §5.1 第一式が全レコードで成立 |
| 単調性 | τ[m] 単調増加 → 市場 m 向け限界利益が単調減少 |
| 原価単調性 | 調達通貨の円安 → `unit_cost` が単調増加 |
| Demand Anchored | `production[m] ≤ D[m]` が全点で成立 |
| 能力制約 | `Σ_m production[m] ≤ Cap` が全点で成立 |
| 尾根の存在 | 需要天井の位置で利益の勾配が不連続に変化 |
| 既存 golden | **12 ケースが全緑のまま**(本 ASK は Planning Engine を変更しない) |

### 9.5 パラメータ推定に関する規準

| パラメータ | 扱い |
|---|---|
| `w[k,b]`(ブロック構成比) | **導出値**。推定ではない |
| `mr`(移転価格マージン) | 既存 CSV の実値 |
| `h`(ヘッジ比率) | 財務部門からの実値 |
| `R`(社内レート改定ラグ) | 運用実態のヒアリング |
| ε / α(v0r4) | 点推定を放棄し、レンジで振ることを標準手続きとする |

### 9.6 v0r2 からの再 V&V 範囲

| 項目 | 再実施 | 理由 |
|---|---|---|
| 宣言整合性 | **要** | 市場軸の検査追加 |
| 時間・製品・フロー軸保存性 | 不要 | 束縛不変 |
| 市場軸保存性 | **要** | 新規追加 |
| 原価軸保存性 | **要** | 導出方式に変更 |
| モデル妥当性 | **要(全項目)** | 伝達式が変更されたため |

---

## 10. 既知の限界

| 限界 | 内容 | 状態 |
|---|---|---|
| 価格が外生固定 | 数量を増やしても価格が下がらない。弾力性なし | **v0r4 で解消** |
| 関税転嫁なし | 関税が全額自社負担として扱われる | **v0r4 で解消** |
| 輸送費が原油に反応しない | `ppc_edge_cost_rule.csv` は USD 固定額。醤油は嵩張るため影響大 | **v0r4 で解消** |
| 単一期間 | 在庫繰越なし | **v0r4 で解消** |
| 形態単一 | 完成品輸出のみ。SKD/CKD 不可 | **v0r4 で解消** |
| FTA 未対応 | 原産地規則・特恵税率を扱わない | **v0r5 で解消** |
| 3 市場まで | 4 市場以上は地図として描けない | 恒久的制約(§2.4) |
| 部分均衡 | 競合の反応を織り込まない | 恒久的制約 |
| 関税の近似 | 従価税のみ | 恒久的制約 |
| 製品軸の未検証 | soysauce は 1 製品のため、製品軸の粒度束縛が検証されない | 複数 SKU ケースへ持ち越し |

**特記事項**: 本版は FTA/原産地規則を扱わないため、日欧 EPA の特恵税率は τ = 0.08 の外生入力として暫定対応している。原産地規則の充足判定は行われていないことを報告書に明記すること。

---

## 付録 A: 実装スケルトン

```
wom/allocation/                      ← 新設パッケージ
├── __init__.py
├── loader.py            # CSV 読込・スキーマ検証・粒度束縛違反の検出
├── fx_resolver.py       # Step 0: レート三系統の解決
├── cost_block.py        # Step 0.5: 既存 CSV からの原価ブロック導出
├── transmission.py      # Step 1〜11
├── grid.py              # Simplex 格子生成・スキャン・台地検出
├── analytics.py         # FXB・感度・交互作用・切替点・robust_point・制約コスト
├── statement.py         # statement_ja の生成
└── vv.py                # §9 の検証ルーチン

tools/
├── run_allocation_map.py            # CLI エントリポイント
├── plot_allocation_map.py           # 静止画生成（Phase 2）
└── proto_terrain2.py                # 参照実装（本番コードではない）
```

**保護コア(`backward_planner.py` / `forward_planner.py` / `plan_copy.py` / `plan_node.py` / `sc_tree.py` / `push_pull.py`)には一切触れない。**

### 実装順序

```
① transmission.py 単体
   → §9.3(a) の実測 4 点を再現するテストを最初に書く
   → 231 点のループより前に、1 点が正しいことを確認する
② grid.py で 231 点展開 → §9.3(d) の台地サイズを検証
③ analytics.py → FXB・交互作用・切替点・robust_point
④ Phase 2 可視化
⑤ vv.py
```

**伝達式の解釈で迷った場合、文章より `proto_terrain2.py` を優先すること。**

---

## 付録 B: 検証ケースの構成

```
data/sample/soysauce-jpy-2027/              ← 変更禁止（golden 対象）
data/sample/soysauce-jpy-2027-alloc/        ← 本 ASK 用の派生ケース
    capacity_plan.csv                          max_supply: 1500 → 800
    ga_market_aggregation.csv                  新規
    ga_scenario_master.csv                     新規
    ga_fx_policy_master.csv                    新規
    （他の 21 CSV は soysauce-jpy-2027 と同一）
```

派生ケースは golden 対象外とし、`tests/test_golden.py` に追加しないこと。

### 基礎数値

| 項目 | 値 |
|---|---|
| 期間 | 2027-W01〜2028-W52(104 週)+ 助走 26 週 |
| 総需要 | 100,501 lot |
| 能力(変更後) | 800/週 × 104 = 83,200 lot(充足率 82.8%) |
| 移転価格 | 16.0 USD × 1.1 = 17.6 USD |
| 関税 | US 12.5% / EU 8% / JP 0%(HS 2103.10) |
| FX | 2027: USD 150 / EUR 162、2028: USD 200 / EUR 216 |
| 原料 | $6.0 →(2028-W10)$8.0 →(2028-W26)$6.5 |
| CCC | dso 8 週 − dpo 6 週 = +2 週 |

---

## 改訂履歴

| Version | 日付 | 変更点 |
|---|---|---|
| v0r1 | 2026-08-05 | 初版。粒度束縛宣言、スキーマ、伝達式を定義 |
| v0r2 | 2026-08-05 | 拡張③(為替三系統)・①(原価ブロック分解)を反映 |
| v0r3 | 2026-08-05 | 実 CSV 確認とプロトタイプ実測を反映。FXB 改名、関税基準を transfer_price へ、原油を material_price へ、原価ブロックを導出方式へ、市場軸の粒度束縛を追加、Step 7 を Demand Anchored に修正、台地検出と robust_point を新設、回帰値を §9.3 に収録。入力 CSV が 7 → 3 に減少 |
| **v0r4** | **2026-09-11** | **市場軸の束縛を「モデル全体で 3 市場」→「1 ノードあたり 3 市場」に変更(§2.4)。§2.5 の「4 市場以上は拒否」を撤回し、拒否条件を格子点数(`MAX_GRID_POINTS`)と三角図の描画可能性に置き換え。§4.2 の `market_group` 3 種以下の制約を撤廃し、`internal_ratio` の意味を「原価集約の重み」1 つに確定。いずれも Phase 6-2(`32b2544`)で配分エンジンが N 市場化され、仕様書が実装に取り残されていたことの是正である** |
