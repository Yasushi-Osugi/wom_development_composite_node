# Coding Request Letter: apparel-us-2026 (Phase 2 — Zara-inspired side)

作成日: 2026-07-10
作成者: Claude (Cowork)
ステータス: Phase 2(Apparel_Local、8季節SKU構成)。Phase 1(Apparel_Import/H&M型)は動作確認・qtyスケーリング修正・原価二重計上修正まで完了済み。同一フォルダ(`data/sample/apparel-us-2026/`)に追加する形で実装完了(CSV生成済み)。ユーザー側での`python -m main`動作確認待ち。
準拠: `docs/design/scenario_modeling_principles.md`のRecommended scenario document structure、`AGENTS.md`のScenario workflow(手順1〜8がこのレターの範囲、9〜11は実装フェーズ)

**実装完了報告(2026-07-10)**: `tools/gen_apparel_model.py`をBRANDS配列(Import/Local)でループする構造に全面リファクタリングし、全20 CSVファイルを再生成した(16 SKU: Apparel_Import_S1〜S8 + Apparel_Local_S1〜S8)。

**実装中に発見・修正した第3のバグ(Phase 1側にも遡って適用)**: `ppc_edge_cost_rule.csv`/`ppc_tariff_rule.csv`のedge_idを、実際に`wom/ppc/ppc_tariff.py`が参照する`"{mom_node}->{dad_node}"`(supply_pointを経由しない直結表記)に修正した。従来Phase 1の`edge_cost_rule.csv`は`"Factory_Import_CN->SP_Apparel_Import"`/`"SP_Apparel_Import->DC_Import_Buffer"`という2行に分けていたが、supply_pointはWOMエンジン上`dad`型ノードではないため`dad_nodes_chain`に含まれず、これらの行は一度もマッチせず**輸送費が常に$0として計算されていた**(Phase 1の動作確認時点では気づけなかった潜在バグ)。正しいedge_id(`"Factory_Import_CN->DC_Import_Buffer"`)に統合・修正し、Import側は$4.8/着(海上輸送)、Local側は$7.0/着(航空輸送、意図的に高め)として正しく計上されるようにした。**この修正により、Phase 1(H&M側)の輸送費・Total Costが前回確認時点から変わる**(前回322.3K USD→本輸送費修正で+4.8×qty分増加する見込み)。再確認時にご留意いただきたい。

**実装中に発見・修正した第4のバグ(Phase 1側にも遡って適用、エンジン修正)**: 上記の輸送費修正により、`Factory_X->DC_X`間のMOM→first DAD輸送費が正しく計上されるようになった結果、全312 lotで`MOM_PROFIT_TOO_LOW`トラストイベントが誤検知されるようになった(PPC KPI Summaryが緑「OK No trust events」→赤「! 312 trust event(s)」に変化)。

原因調査の結果、`wom/ppc/ppc_tariff.py`のStep 3(Tariff & Landed Cost計算)がMOM→first DAD間の輸送費(`logistics_cost`)を、本来Supplier→MOM間の輸送費専用であるべき`acc.logistics_in_base`に混在させて加算していたことが判明した。これにより`wom/ppc/ppc_reconcile.py`のMOM_PROFIT_TOO_LOW判定(`transfer_price - (supplier_cost + conversion_cost + logistics_in_base)`)が、本来MOM側の粗利計算に含めるべきでない買い手側(FOB建て)の輸送費をMOM自身の利益から誤って差し引く形になっていた(実際の粗利率は41.6%と健全であるにも関わらず、機械的に赤字判定されていた)。

ユーザー判断により「エンジンを修正(logistics_in_baseを分離)」を選択、以下の通り修正した(Phase 1・Phase 2 両方に影響する共通エンジン修正のため、H&M側レターにも同内容を反映予定):

- `wom/ppc/ppc_models.py`: `LotCostAccumulator`に新フィールド`mom_to_dad_freight_base`を追加。`total_forward_cost_base()`には引き続き合算されるため、Total Cost等の総額には影響しない
- `wom/ppc/ppc_tariff.py`: MOM→first DAD間の`logistics_cost`を`acc.mom_to_dad_freight_base`へ、`insurance_cost`を(従来未使用だった)`acc.insurance_in_base`へ正しくルーティング。Landed cost informational event(`landed_base`)にも`mom_to_dad_freight_base`を合算し直した
- `wom/ppc/ppc_reconcile.py`: Check 5(`LANDED_COST_EXCEEDS_MARKET`)のlanded_cost計算にも`mom_to_dad_freight_base`を追加(上記の分離により、この判定が輸送費を見落とさないようにするための連動修正)。Check 3(`MOM_PROFIT_TOO_LOW`)自体は`logistics_in_base`のみを参照する設計のままで正しく機能する(freight write先の変更により自動的に解消)
- `wom/ppc/ppc_profit_zone.py`(`mom_profit`イベント)・`wom/ppc/ppc_kpi.py`(`build_kpi_summary`の`mom_supply_all`)は、いずれも`logistics_in_base`を参照する既存ロジックのまま、上記のfreight write先変更により自動的に正しい値になる(直接修正は不要と判断)
- `wom/ppc/ppc_transfer.py`(cost_plus方式の転送価格計算)はStep 2で実行されStep 3より前に完了するため、この修正の影響を受けない(元々Supplier→MOM分のみを参照しており、設計通り)

**再確認していただきたい点**: trust_events件数が312→0(または近い値)に戻ること、Total Cost/Total Revenue/Gross Marginの数値(Import側: Revenue 663.6K, Total Cost 387.3K, Margin 41.6%/42.4%)が本修正前後で変わらないこと(利益の帰属先が変わるだけで、全体のコスト・利益総額は不変のはず)。

---

## 1. Business question

```text
How does a vertically-integrated, air-freight-based nearshore-to-market
sourcing strategy (short and stable lead time, low buffer requirement,
moderate tariff exposure) compare against an offshore, fabless strategy
(Phase 1 / Apparel_Import) under WOM's weekly PSI + PPC engine, for the
same US market and product calendar?
```

Phase 1(Apparel_Import/H&M型)は単独で動作確認済み。Phase 2はApparel_Local(Zara型)を同じフォルダに追加し、両SKUグループを同一Network/PPC画面上で対比できる状態にする。これにより「オフショア・ファブレス vs ニアショア・垂直統合」という当初からのケース設計コンセプトが完成する。

## 2. Educational disclaimer

This model is fictional and educational, consistent with `docs/design/wom_canonical_concepts.md`のCanonical concept 11。

Company names, factories, distribution centers, prices, costs, and capacities are simplified or fictionalized. The scenario is informed by publicly reported characteristics of Inditex/Zara's operating model (vertically-integrated Spain-based production, Arteixo distribution hub, twice-weekly store replenishment, significant use of air freight for overseas markets) but should not be interpreted as a factual statement about Industria de Diseño Textil, S.A. (Inditex) or any other specific real company. `sku_id`は`Apparel_Local`という匿名名を使用する(実在ブランド名は使わない、Phase 1の命名規則を踏襲)。

**重要な設計修正(調査段階で判明)**: 当初はZara型を「米国市場向けにメキシコ/CAFTA-DRへニアショアした架空企業」として設計する案を検討したが、Zara/Inditex自身が実際に西半球へ米国向けニアショアを行っている一次情報が確認できなかったため不採用とした。オーナーの指示により、**Zara/Inditexの実際の運営モデル(スペインの垂直統合工場 → 航空輸送 → 海外直営店)をそのまま米国市場に適用する**設計に変更した。この方が実在の運営慣行に基づいており、「ニアショア」ではなく「垂直統合+航空輸送による見かけ上の短リードタイム化」という、Zaraの実際の強みにより忠実な表現になる。

## 3. SKU structure (Phase 2, 8季節SKU)

Phase 1と同じ8季節構造を`Apparel_Local`側にも適用する(直接比較のため)。

```text
Apparel_Local_S1  Pre-Spring   / 初春物      2026-W01〜W07
Apparel_Local_S2  Spring       / 春物        2026-W08〜W14
Apparel_Local_S3  Early Summer / 初夏物      2026-W15〜W20
Apparel_Local_S4  High Summer  / 盛夏物      2026-W21〜W27
Apparel_Local_S5  Early Fall   / 初秋物      2026-W28〜W33
Apparel_Local_S6  Fall Coats   / 秋物・コート 2026-W34〜W40
Apparel_Local_S7  Early Winter / 初冬物      2026-W41〜W46
Apparel_Local_S8  Winter Holiday / 真冬・ホリデー 2026-W47〜W53
```

(nearshore-in-operating-model, vertically integrated — Zara-inspired。需要ウィンドウ・季節ラベルはApparel_Importと完全に同一にし、同じ市場・同じシーズンで「供給網の違いだけ」を対比できるようにする)

## 4. Physical network

```text
Inbound:
Fabric_ES (leaf_in, ES) -> Factory_Local_ES (mom, ES, lt_wks=1) -> supply_point

Outbound:
supply_point -> DC_Local_US (dad, US, ss_days=7, buffering_stock_flag=1)
             -> Sales_US_TX_L / Sales_US_CA_L / Sales_US_NY_L (leaf_out)
```

- `Factory_Local_ES`: スペインの垂直統合工場(自社/系列)。Fabric_ESからの生地調達を含め域内で完結
- `DC_Local_US`: 航空輸送で受け取った完成品を米国内で保管・仕分けする拠点。Apparel_Importの`DC_Import_Buffer`と同じ`dad`ロールだが、`ss_days`は21→7に短縮(輸送の安定性・頻度の高さを反映)
- 店舗ノードはApparel_Import側(`Sales_US_TX_I`等)と物理的に別ノード(`_L`サフィックス)とし、「同じ3州(TX/CA/NY)に、H&M型とは別の直営店網を構える」という設定にする(実店舗の重複を避け、Network図上で両ブランドの並存を視覚的に見せる)

**リードタイム設計の要点**: Phase 1(工場lt_wks=8、生地lt_wks=3、DC lt_wks=4)に対し、Phase 2は工場lt_wks=1・生地lt_wks=1・DC lt_wks=1という大幅な短縮を提案する。これはArteixoディストリビューションセンターの「週2回・6,900店舗への航空輸送による補充」という実際の運用に基づく(週次粒度のWOMでは「ほぼ即応」を意味する最小値として1週を採用)。

## 5. Demand assumptions

Apparel_Importと**完全に同一**の需要仮定を用いる(同じ市場規模・同じ季節パターン)。供給網の違いだけで両者の在庫・PPC挙動がどう変わるかを見せるのが目的のため、意図的に需要側を統一する。

- Demand generated at `leaf_out`: `Sales_US_TX_L`, `Sales_US_CA_L`, `Sales_US_NY_L`
- Base weekly demand(ピーク時): TX=1200, CA=1100, NY=900 lots/week(Apparel_Importと同一)
- 季節ウィンドウ・raised-sine bumpの数式もApparel_Importと同一(`tools/gen_apparel_model.py`のSEASONS/season_weight関数をそのまま再利用)
- シミュレーション期間: `2026-W01` 〜 `2027-W52`(105週、Apparel_Importと同一)

## 6. Capacity assumptions

| node | cap_hard(代表値) | 備考 |
|---|---|---|
| `Factory_Local_ES` | 15000 lots/week | Apparel_Importの`Factory_Import_CN`と同水準(供給網の質の違いを見せるため、生産能力の大小では差をつけない) |
| `Fabric_ES` | 事実上無制限(50000 lots/week、Apparel_Import側のFabric_CNと同じ「制約にならない」設定) | |
| `DC_Local_US` | 25000 lots/week | Apparel_ImportのDC_Import_Bufferと同水準 |

**新規の休業設定(スペイン夏季休暇)**: `holiday_calendar.csv`に、欧州で広く行われる8月の工場夏季休暇("agosto")による`Factory_Local_ES`の稼働率低下を追加する(2026-W32〜W33、2027-W32〜W33の2週間、cap_hard→通常の10%程度)。これはApparel_Import側の中国春節(Chinese New Year)と対になる、地域性を反映した休業パターンであり、High Summer(S4, W21-27)〜Early Fall(S5, W28-33)シーズンの端境期に重なるため、Chinese New YearがS1/S2の端境期に重なったのと同様の設計上の整合性がある。

## 7. Buffer and decoupling assumptions

- `DC_Local_US`: `ss_days=7`, `buffering_stock_flag=1` — 短く安定した航空輸送のリードタイムを反映し、Apparel_Importの`ss_days=21`より大幅に小さいバッファで足りることを示す(在庫回転の速さ・キャッシュ効率の良さがZara型の強みであるという実データ[stock-in-trade比率、粗利率58.3%]と整合)
- InBound側(工場側)のバッファ配置最適化は対象外(リポジトリの既定方針通り、Phase 1と同じ)

## 8. PPC assumptions

**Phase 1で発生した原価二重計上の教訓を踏まえ、Phase 2は当初から`ppc_node_cost_rule.csv`を含めて設計する**(Fabric費用とFactory加工費を明確に分離し、後から二重計上に気づいて修正する手戻りを避ける)。

- `ppc_supplier_cost.csv`: `Fabric_ES` = $7.0/着(生地代)
- `ppc_node_cost_rule.csv`: `Factory_Local_ES`にconversion_cost = $10.0/着(加工費のみ、生地代を含まない)を計上。`DC_Local_US`にwarehouse_cost = $1.0/着を計上
- `ppc_transfer_price_rule.csv`: `Factory_Local_ES`は**cost_plus方式**(margin_rate想定0.10前後)を用いる。Phase 1の`fixed`方式(アービトラリーなCIF価格を直接指定)とは異なり、実際に積み上がった生地代+加工費+域内輸送費に対してマージンを乗せる形にすることで、二重計上を構造的に起こしにくくする(オーナーへの推奨: cost_plusの方がvertically-integrated企業の内部原価管理としても自然)
- `ppc_edge_cost_rule.csv`: `Factory_Local_ES->SP_Apparel_Local`(域内輸送、$1.0/着)、`SP_Apparel_Local->DC_Local_US`(**航空輸送**、$6.0/着 — Apparel_Import側の海上輸送$3.8/着より高い設定とし、「航空輸送はコスト高だがリードタイムを劇的に短縮する」というトレードオフを明示する)
- `ppc_tariff_rule.csv`: **15%(EU-US通商合意、2026年7月1日発効の包括上限)**。中国20%・バングラデシュ26.5%(Apparel_Import側)との中間的な税率になる。tariff_basis=transfer_price(Phase 1と同じ)
- `ppc_market_price.csv`: $49.0/着(Apparel_Importと同一の小売価格。供給網コスト構造の違いだけで粗利率の差が出ることを見せる)
- `ppc_node_profit_zone.csv` / `ppc_profit_zone_rule.csv`: `OUTBOUND_CHANNEL_PROFIT`のchannel_margin rateはZaraの粗利率(58.3%)を参考に0.40前後に設定(Apparel_Importの0.35より高め)

**Phase 1との比較サマリー(設計意図)**:

| 項目 | Apparel_Import(H&M型) | Apparel_Local(Zara型) |
|---|---|---|
| 生産拠点 | 中国(契約工場、ファブレス) | スペイン(自社工場、垂直統合) |
| 輸送手段 | 海上輸送 | 航空輸送 |
| リードタイム(工場+生地+DC合計) | 約15週 | 約3週 |
| DCバッファ(ss_days) | 21日 | 7日 |
| 輸送コスト(SP→DC) | $3.8/着 | $6.0/着(高コストだが短LT) |
| 関税 | 20%(中国) | 15%(EU) |
| Transfer Price方式 | fixed($19.0、CIF一括) | cost_plus(生地+加工費の積み上げ+マージン) |
| チャネル粗利率想定 | 35% | 40% |

## Expected outputs

- Network tab: Product選択ドロップダウンに`Apparel_Local_S1`〜`S8`が追加され、`Apparel_Import_S1`〜`S8`と合わせて16 SKUが並ぶこと
- PSI chart: Apparel_Local側の在庫の積み上がりがApparel_Importより小さく・短い期間であること(ss_days=7 vs 21の差が視覚的に出ること)
- PPC/Node P&L: `Factory_Local_ES`と`Factory_Import_CN`のコスト構成(生地/加工費/輸送/関税の内訳比率)が明確に異なること
- Management タブ: 両SKUグループのGross Margin%を比較し、Apparel_LocalがApparel_Importより高くなること(58%台 vs 現状のPhase 1実績51.4%〜61.2%と同水準かそれ以上)

## Known limitations (Phase 2)

- 実際のZara/Inditexは西半球への米国向けニアショアを行っていない(8-1参照)。本ケースは「Zaraの実際の運営モデル(スペイン+航空輸送)」を忠実に再現したものであり、地理的にはEU→US間の直送という設定
- 航空輸送費・関税率・マージン率の具体的数値は、公開財務指標(粗利率58.3%等)から**逆算的に設定した仮置き値**であり、実際のコスト構造の一次情報ではない(H&M側と同様の限界)
- Fabric_ES/Factory_Local_ESの原価分離比率($7.0/$10.0)は説明用の仮置きであり、実際の按分は非開示
- 店舗ノードをApparel_Import側と分離した(`_L`サフィックス)ため、実際には同一店舗網を共有する小売企業のケース(例: 同一小売業者が2ブランドを展開)を表現したい場合は、Phase 3として店舗共有パターンの設計が別途必要

## 動作確認結果(Apparel_Local側、2026-07-11)

MOM_PROFIT_TOO_LOW修正後、Apparel_Local_S4で確認。trust_events=0(緑「OK No trust events」)。PSIは期待通りss_days=7を反映した短く鋭い在庫バッファ形状(Importのss_days=21より明らかに幅が狭い)。

PPC KPI Summary: Revenue 663.6K / Total Cost 376.5K / Gross Profit 287.0K / Gross Margin 43.3% / Tariff 38.0K。Cost Waterfall: Revenue 49, Supplier(Fabric) 7, Mfg Conv 10, CIF Freight 8, Tariff ~3, Gross Profit 21 — Fabric($7)とConversion($10)が別コストとして両方計上されているが、これはH&M側の二重計上バグとは異なり、cost_plus方式による**意図した設計**(それぞれ独立した加算コンポーネント、合算してtransfer_price=17×1.10≈18.7を構成)であり、二重計上ではないことを確認。

Node P&L: `Fabric_ES` Cost 94,794、`Factory_Local_ES` Cost 135,420(Management Cogsと一致)、`DC_Local_US` Cost 146,321 / Tariff 37,985 — Fabric_ES:Factory_Local_ES ≈ 7:10の比率で整合。

**新たに判明した差異**: Management タブのGross Margin%は79.6%(Cogs=135,420、Factory_Local_ESのみの狭い定義)、PPC KPI SummaryのGross Marginは43.3%(広い定義)。期待していた「Zara実績58.3%程度」よりもManagement側の79.6%はかなり高い(Import側は61.2% vs Zara実績58.3%と比較的近かったのと対照的)。margin_rate=0.10のcost_plus方式では、狭い定義のCogsが小さくなりすぎる(Fabric_ESのコストがCogsに含まれないため)。

**対応(2026-07-11、オーナー選択: 「Fabric_ESコストもCogsに合算」)**: `tools/gen_apparel_model.py`の`gen_sku_master`を修正し、`sku_master.csv`の`unit_cost`をcost_plus方式(Local)の場合`fabric_unit_cost + conversion_cost`(=7.0+10.0=17.0、マージン抜きの積み上げ原価)に変更。fixed方式(Import)側は`factory_cif_price`(=19.0、CIF込み転送価格)のままで変更なし。この`unit_cost`は`wom/engine/money.py`のManagement P&L(COGS = demand_fulfilled × unit_cost)が参照する値であり、PPCエンジンの転送価格算定ロジック(`ppc_transfer.py`)とは独立した別エンジンだが、両エンジン間で「MOMが実際に負担する原価」の定義を揃える目的の修正。CSV再生成済み(`sku_master.csv`のApparel_Local_*行がunit_cost=17.0に変更)。

再計算後の見込み: Local側 Cogs ≈ 230,214(旧135,420+Fabric_ES分94,794相当)、Gross Profit ≈ 433,344、Gross Margin% ≈ 65.3%(旧79.6%から低下、Zara実績58.3%によりわずかに近づく方向)。margin_rateにマージンを含めた完全一致(58.3%ちょうど)を狙う調整は行っていない(オーナー選択は「合算」のみで、精緻なmargin_rateチューニングは見送り)。ユーザー側`python -m main`での再確認が必要。

## Open questions

1. ~~`ppc_transfer_price_rule.csv`のcost_plus方式で、margin_rateを0.10程度と仮置きしたが、粗利率58.3%という開示数値ともっと精緻に整合させるべきか~~ → **対応済み**(上記「動作確認結果」参照。Management Cogsにfabric_unit_costを合算する会計スコープ修正を実施。margin_rate自体のチューニングは見送り、65.3%程度に着地する見込み。ユーザー確認待ち)
2. Factory_Local_ESの8月休業を「Chinese New Yearと対になる地域性の演出」として追加提案したが、シーズンS4/S5の端境期との重なり方がストーリー上自然かどうか、動作確認後に見え方を確認する必要がある
3. 店舗ノードをApparel_Import側と分離(`_L`サフィックス)したが、将来的に「同一店舗が2ブランドを扱う」設定にする場合は`lane_assignment.csv`の優先順位ロジックの再設計が必要(Phase 1の「Multi-MOM構成をリスク回避のため見送った」判断と同種の検討事項)

---

## 実装(9〜11)への申し送り

- 出力先: `data/sample/apparel-us-2026/`(既存フォルダに追加、上書きではなく新規SKU・新規ノードの追加)
- `tools/gen_apparel_model.py`を拡張し、Apparel_Local用の生成関数(`gen_*_local`系、またはSEASONS/REGIONSループを共通化した上でブランド別に分岐)を追加する形で実装する。既存のApparel_Import生成ロジックは変更しない(冪等性を保つ)
- `ppc_node_cost_rule.csv`は既存(Apparel_Import用に追加済み)ファイルに、Apparel_Local用の行を追記する形になる(新規ファイル作成ではなく既存ファイルへの追記)
- `docs/scenarios/apparel.md`は実装・動作確認が完了してから作成する(手順11、Phase 1+Phase 2両方が揃った時点で一度に作成するのが効率的)
