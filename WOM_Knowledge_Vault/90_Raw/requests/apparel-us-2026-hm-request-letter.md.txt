# Coding Request Letter: apparel-us-2026 (Phase 1 — H&M-inspired side only)

作成日: 2026-07-10
更新日: 2026-07-10(8季節SKU再設計を反映)
作成者: Claude (Cowork)
ステータス: Phase 1(Apparel_Import、8季節SKU構成)。GUI動作確認済み(World Map/Network/PPC/Management各パネル)。Phase 2でApparel_Local(Zara型)を同じフォルダに追加予定。
準拠: `docs/design/scenario_modeling_principles.md`のRecommended scenario document structure、`AGENTS.md`のScenario workflow(手順1〜8がこのレターの範囲、9〜11は実装フェーズ)

**改訂履歴**:
- v1(初版): 単独SKU(Apparel_Import)、通期サイン波での季節変動モデル
- v2(本版): 実店舗の商品企画に合わせ、**8つの季節限定SKU**(`Apparel_Import_S1`〜`S8`)に再設計。各SKUは特定の季節ウィンドウ(6〜7週間)でのみ需要が発生し、シーズン外は需要ゼロ。物理ノード(工場・DC・店舗)は8SKUで共有

---

## 1. Business question

```text
How does an offshore, fabless sourcing strategy (long and variable lead time,
import buffering, tariff exposure) behave under WOM's weekly PSI + PPC engine,
as a first step toward comparing it against a nearshore, vertically integrated
strategy (Phase 2)?
```

Phase 1はApparel_Import側(8季節SKU)のみで、比較のストーリーはPhase 2でApparel_Localを追加した時点で完成する。Phase 1の目的は、(a)長いリードタイム・輸入バッファ・関税による着地コストという要素が、既存のCookie/EVパターン(シングルMOM構成)を踏襲した形で正しく動作すること、(b)アパレル特有の「季節ごとに商品そのものが入れ替わる」需要構造(1つの連続SKUが波打つのではなく、複数の季節限定SKUが順番にアクティブになる)がWOMのPSI/PPCエンジン上で自然に表現できること、の2点を確認すること。

## 2. Educational disclaimer

This model is fictional and educational, consistent with `docs/design/wom_canonical_concepts.md`のCanonical concept 11。

Company names, factories, distribution centers, prices, costs, and capacities are simplified or fictionalized. The scenario is informed by publicly reported characteristics of the fast-fashion industry (offshore sourcing footprint, wide lead-time range, 2025-2026 US tariff escalation) but should not be interpreted as a factual statement about H&M Hennes & Mauritz AB or any other specific real company. `sku_id`は`Apparel_Import`という匿名名を使用する(実在ブランド名は使わない、Cookie/EVケースの命名規則を踏襲)。

## 3. SKU structure (Phase 1, 8季節SKU)

```text
Apparel_Import_S1  Pre-Spring   / 初春物      2026-W01〜W07
Apparel_Import_S2  Spring       / 春物        2026-W08〜W14
Apparel_Import_S3  Early Summer / 初夏物      2026-W15〜W20
Apparel_Import_S4  High Summer  / 盛夏物      2026-W21〜W27
Apparel_Import_S5  Early Fall   / 初秋物      2026-W28〜W33
Apparel_Import_S6  Fall Coats   / 秋物・コート 2026-W34〜W40
Apparel_Import_S7  Early Winter / 初冬物      2026-W41〜W46
Apparel_Import_S8  Winter Holiday / 真冬・ホリデー 2026-W47〜W53
```

(offshore, fabless — H&M-inspired。2年目`2027-W01`〜`W52`は同じ季節パターンを繰り返す)

各SKUは季節ウィンドウの外では需要ゼロ(=商品として存在しない)。物理ノード(`Factory_Import_CN`, `Fabric_CN`, `DC_Import_Buffer`, 3店舗)は8SKUで共有し、`sc_tree_master.csv`側でSKUごとにツリーを複製する形で表現する(ノード数は7のまま、ツリー行数のみ8倍)。

Phase 2で`Apparel_Local`(nearshore, vertically integrated — Zara-inspired)を同じフォルダに追加する。

## 4. Physical network

```text
Inbound:
Fabric_CN (leaf_in, CN) -> Factory_Import_CN (mom, CN, lt_wks=8) -> supply_point

Outbound:
supply_point -> DC_Import_Buffer (dad, US, ss_days=21, buffering_stock_flag=1)
             -> Sales_US_TX_I / Sales_US_CA_I / Sales_US_NY_I (leaf_out)
```

上記ネットワーク構造は8SKU共通(ノードは共有、`sc_tree_master.csv`でSKUごとに7行×8=56行として複製)。

**設計変更(Phase 1で単純化)**: 当初はFactory_Import_CN(中国)+Factory_Import_BD(バングラデシュ)のMulti-MOM構成を検討したが、`lane_assignment.csv`で1つのleaf_outに複数MOM(priority 1/2)を割り当てた場合の需要配分の挙動について、確証の持てる実例(既存ケースでの検証済みパターン)が見当たらなかった。CLAUDE.mdにはiPhoneモデルでMulti-MOM(Buffer_Wafer_TW)の実績があるとの記載はあるが、実CSVを確認していない。リスクを避けるため、**Phase 1はFactory_Import_CN単独のシングルMOM構成**とし、ev-thailand-2026と同じ実績あるパターンに揃える。バングラデシュ側(Factory_Import_BD)の追加は、Phase 1の動作確認が完了した後の追加ステップ(Phase 1.5)として切り出す。

## 5. Demand assumptions

**設計変更(v2、8季節SKU化)**: 当初は単独SKUに対する連続サイン波(`1.0 + 0.15*sin(2π*idx/13)`)で季節性を表現していたが、実際のアパレル事業では「秋物のコート」「春物のパンツ」のように商品そのものが季節ごとに入れ替わる。これを反映し、8つの季節限定SKUそれぞれに独立した需要ウィンドウを持たせる方式に変更した。

- Demand generated at `leaf_out`: `Sales_US_TX_I`, `Sales_US_CA_I`, `Sales_US_NY_I`(8SKU共通の3店舗)
- Base weekly demand(ピーク時、SKUごとに同一): TX=1200, CA=1100, NY=900 lots/week
- 季節ウィンドウ内の変動は「持ち上げサイン波」(raised sine, `weight = sin(π * t)`, t=season内の正規化位置)で表現。ウィンドウの両端で需要ゼロ、中間週でピークとなる山型。ウィンドウ外は行自体を出力しない(=需要ゼロ)
- 結果として、隣接シーズンの境界付近(各シーズンの端週)に自然な需要ゼロ〜低需要の谷ができる(例: 2026-W07/W08は中国春節の稼働率低下時期とも重なり、都合よく整合)
- シミュレーション期間: `2026-W01` 〜 `2027-W52`(105週。2026年はISO暦で53週あるため`NUM_WEEKS=105`とし、`date.fromisocalendar()`ベースで週境界を自動計算 — CLAUDE.mdに記載のある「2027-W53が存在せず2028-W01に繰り上がる」バグを回避)

## 6. Capacity assumptions

| node | cap_hard(代表値) | 備考 |
|---|---|---|
| `Factory_Import_CN` | 15000 lots/week | 基礎品中心、大きめの能力 |
| `Fabric_CN` | 事実上無制限(ev-thailand-2026のComponents_CN=500と同様の「制約にならない」設定) | |
| `DC_Import_Buffer` | 25000 lots/week | スループット制約 |

`capacity_plan.csv`は`sc_tree_master.csv`と同様、SKUごとに行を複製している(node × product × week)。**未検証の設計上の注意点**: 各SKUが同じ`cap_hard`値(例: Factory_Import_CN=15000)を独立に持つため、エンジンが「SKUをまたいだ同一物理ノードの合算」でcap_hardを判定するのか、「SKU単位で個別に」判定するのかによって、複数シーズンが重なる週(境界週)の挙動が変わりうる。8シーズンは意図的に重複を避ける設計にしているため、Phase 1の検証では顕在化しないが、Phase 2で複数SKUの需要期が重なるケースを扱う場合は要確認(Open questionsに追記)。

`holiday_calendar.csv`に`Factory_Import_CN`の中国春節(Chinese New Year)による稼働率低下を1件追加(2週間、cap_hard→通常の10%程度。CLAUDE.mdの既知の注意点通り、0.0ではなく小さい正の値を使う)。ノードベースのため8SKU共通で適用される。

## 7. Buffer and decoupling assumptions

- `DC_Import_Buffer`: `ss_days=21`, `buffering_stock_flag=1` — 長く変動の大きいオフショアのリードタイムを輸入バッファ在庫で吸収する、Cookie-jp-2026の`DC_Import_Buffer`と同じ設計思想
- InBound側(工場側)のバッファ配置最適化は対象外(リポジトリの既定方針通り)

## 8. PPC assumptions

- `ppc_transfer_price_rule.csv`: `Factory_Import_CN`はfixed方式
- `ppc_tariff_rule.csv`: **現在(2026年)時点の関税水準を静的に設定**する。中国20%、バングラデシュ26.5%(2026年2月最高裁判決後の水準)。
  - **重要な設計修正(Phase 1で判明)**: `ppc_tariff_rule.csv`にはweek列が無く、シミュレーション期間全体で単一の静的関税率としてしか表現できない(oil-global-2027の価格スパイクのようなweek別の時系列変化は`ppc_supplier_cost.csv`側でのみ可能)。よって「関税ショックの時系列変化」はライブシミュレーションでは表現せず、代わりに`edge_cost_master.csv`の`scenario`列(`Base`=2025年1月水準14.7%相当、`TariffShock2025`=現行水準、`TariffRelief2026`=部分緩和後)を使い、Management タブのLanded Cost / Tariff & FXパネルで**比較シナリオとして**見せる。これはev-thailand-2026の`Base/EV30/EV35/TariffRestore/SubsidyEnd`と同じ使い方であり、当初の設計メモにあった「時系列ショック」という表現は不正確だったため、ここで訂正する。
- `ppc_market_price.csv`: 据え置き価格(sticky price)。関税上昇分を小売価格に転嫁しない設計とし、マージン圧縮を可視化する
- `ppc_node_profit_zone.csv` / `ppc_profit_zone_rule.csv`: `OUTBOUND_CHANNEL_PROFIT`のchannel_margin rateはH&Mの粗利率(53.4%)を参考に0.35前後に設定
- 上記PPC系CSV(`ppc_tariff_rule.csv`, `ppc_transfer_price_rule.csv`, `ppc_node_profit_zone.csv`, `ppc_profit_zone_rule.csv`, `ppc_edge_cost_rule.csv`, `node_cost_master.csv`)は全て8SKU分に複製(`product_id`列で区別)。`edge_cost_master.csv`(scenario比較用)のみノードペア単位のためSKU非依存で共通

**エンジン側の設計修正(Phase 1で実施、重要)**: `wom/gui/app.py`の`_run_ppc_from_planning`が`base_currency="JPY"`をハードコードしていたため、USD運用のapparel-us-2026でFXレート未検出エラーが発生した。既存ケース(Cookie/EV/oil)はすべてJPYベースで集計する慣習だが、「グローバルオペレーション企業はHQが日本にあってもUSDベースが普通」との方針により、**JPYへのハードコード自体を撤廃**し、モデルローカルの`ppc_fx_rate.csv`が持つ`base_currency`列から自動検出する方式に変更した(値が無い/複数ある場合はJPYにフォールバックし、既存3ケースの挙動は不変)。この変更は`apparel-us-2026`固有の対応ではなく、**リポジトリ共通の恒久的な機能追加**として`app.py`に直接コミットされている。

**エンジン側の設計修正2(Phase 1動作確認後に発見・修正、重要)**: Node P&L/PPC KPI Summaryパネルの売上・コストが、Management P&L Summaryパネルより大幅に小さい値になる既存バグを発見・修正した(詳細は下記Known limitationsの旧記載を参照)。原因は`wom/ppc/`のPPCエンジンが、`ppc_psi_bridge.py`の週次集計済みPSI行(1行=その週の実数量qtyをまとめた1lot)を、内部的に「1 lot = 1 unit」として扱い、`LotCostAccumulator`/`PPCEvent`が実数量`qty`を保持・反映していなかったこと。`ppc_node_cost_rule.csv`のbasis列に`"qty"`という値が既に存在すること(`c_local = rate * 1 + fixed`という未完成のプレースホルダ実装)、およびev-thailand-2026の`ppc_node_cost_rule.csv`備考欄に"THB/台"(=単位あたり)と明記されていることから、この`qty`スケーリングは元々意図されていた設計だが実装されていなかったと判断した。

修正は`wom/ppc/ppc_models.py`(`LotCostAccumulator`に`qty`フィールド追加)、`ppc_engine.py`(`_build_accumulators()`でsales_records.qtyから設定)、`ppc_forward.py`/`ppc_tariff.py`/`ppc_transfer.py`/`ppc_profit_zone.py`/`ppc_backward.py`(各PPCEvent生成箇所の`qty=1`を実数量に置換)、`ppc_kpi.py`(`build_node_week_summary`/`build_profit_zone_summary`/`build_node_pl_summary`/`build_kpi_summary`の集計時に`qty`を掛けて真の合計値に変換)。**関税率・マージン率などの比率ベースの計算(reconciliation trust events含む)は一切変更していない**(per-unit同士の比率は元々qtyスケール不変のため)。**リポジトリ共通のコアエンジン修正**であり、apparel-us-2026以外の既存4ケース(Cookie/EV/oil/iPhone)でもNode P&L/PPC KPI Summaryパネルの表示額が本修正後は変わる(より大きく、より正確になる)点に注意。Management P&L Summaryパネル(`wom/engine/money.py`ベース、元々正しい)は影響を受けない。

初回の動作確認(2026-07-10)でManagement タブのNode P&L(拠点別損益)は修正が反映され、663,558 USD(チャネル3店舗合計 228,144+186,592+248,822)とP&L Summaryが完全一致することを確認した。一方、**PPCタブのPPC Financial KPI Cockpit(`ppc_cockpit_app.py`)は別実装で、`ppc_lot_reconciliation.csv`/`ppc_event_ledger.csv`を独自に再集計する仕組みだったため、当初は旧い882 USDのままだった**。追加調査の結果、このコックピットは`ppc_kpi.py`を経由せず、`self._rec`(lot_reconciliation)や`self._ev`(event_ledger)から直接`amount_base`を合算していることが判明。`ppc_reconcile.py`の出力行に`qty`列を追加し、`ppc_cockpit_app.py`の`_draw_kpi_text`(PPC KPI Summaryテキストパネル、チャネル別内訳)と`_draw_profit_zone`(Profit Zone Breakdown棒グラフ)、および`_draw_fwd_bwd`のチャネルランキングロジックに`qty`乗算を追加した。「Cost Waterfall (avg/lot)」「Forward vs Backward vs Revenue (avg/lot)」「Lot Gross Margin by Channel」など、明示的に"avg/lot"とラベル付けされたper-unit平均値パネルは意図通りの設計のため変更していない。

**2回目の動作確認(2026-07-10)で最終確認**: PPCタブのPPC KPI SummaryがRevenue 663.6K USD / Tariff Cost 51.5K USD / チャネル別内訳(TX 248.8K / CA 228.1K / NY 186.6K)となり、Management タブのNode P&L・P&L Summaryと完全に一致することを確認した。qtyスケーリングバグの修正は完了。

**新たに判明した別問題(Cost/COGSの差異、qtyバグとは別原因)**: PPC KPI Summary/Node P&LのTotal Cost(139.5K USD = Fabric_CN 88,023 + DC_Import_Buffer 51,460 + Factory_Import_CN 0)と、Management P&L SummaryのCogs(257,298 USD)が一致しない。原因調査の過程で、**原価構造そのものの二重計上**を発見した: `node_cost_master.csv`の備考でFactory_Import_CNの$19.0/着を「契約工場CIF価格」(=生地込みの完成品渡し価格)としていたが、`ppc_supplier_cost.csv`は別途Fabric_CN(生地)$6.5/着もPPCエンジン上で独立コストとして計上しており、実質的に生地代が二重計上されていた。オーナーに確認したところ、「$19.0はCIF価格(生地込み)が正しい設計」との回答を得たため、以下の対応を行った。

1. `ppc_supplier_cost.csv`: Fabric_CNのpurchase_priceを6.5→0.0に変更(物理ノードとしてのFabric_CNはsc_tree_master.csv/Networkビューに残す。PPCコストのみ無効化し二重計上を解消)
2. `ppc_node_cost_rule.csv`を新規作成(apparel-us-2026にこのファイルが無かったこと自体が既知のギャップだった): `Factory_Import_CN`にconversion_cost=$19.0/着(CIF価格全額、生地込み)、`DC_Import_Buffer`にwarehouse_cost=$1.0/着(node_cost_master.csvのDC着地コスト23.8 = 転送価格19.0+関税3.8+この1.0)を追加

**3回目の動作確認(2026-07-10)で最終確認**: S4のNode P&Lで`Factory_Import_CN`のCost=257,298となり、Management P&L SummaryのCogs=257,298と**桁まで完全一致**(=総数量13,542着×$19.0のCIF価格)。`Fabric_CN`のCostは0(二重計上解消)。PPC KPI SummaryのTotal Cost=322.3K USD(=Factory conversion 257,298 + DC tariff 51,460 + DC warehouse 13,542)で、これは想定通りManagement Cogs(257,298)より大きい。差分65.0K(=関税51.5K+DC運営費13.5K)は、PPC Total Costが着地コストに近い広い定義を採用していることによる想定内の差であり、二重計上のような不整合ではないことを数値的に確認した。`tools/gen_apparel_model.py`を更新し`ppc_node_cost_rule.csv`生成関数を追加、再実行済み(全20 CSVファイル)。**H&M(Apparel_Import)側Phase 1の検証はこれで完了**。

## Expected outputs

- Network tab: Product選択ドロップダウンに`Apparel_Import_S1`〜`S8`の8件が並び、いずれを選んでも`Factory_Import_CN`からsupply_point、DC_Import_Bufferへの接続が表示されること
- PSI chart: 各SKUがそれぞれの季節ウィンドウ内でのみ山型の需要・在庫パターンを描き、ウィンドウ外はゼロで平坦になること。`DC_Import_Buffer`の在庫が`ss_days=21`分積み上がること
- PPC/Node P&L: `Factory_Import_CN`のコストが計上されること
- Landed Cost / Tariff & FXパネル: `Base`/`TariffShock2025`/`TariffRelief2026`シナリオ間でLanded GM%が変化すること

**動作確認結果(2026-07-10、ユーザー側`python -m main`実行)**: 上記いずれも確認済み。Network/PSIチャートで8SKUの季節山型が正しく表示され、Management P&L SummaryもUSD表示でSKUごとに算出されることを確認。SからDへのLT_offsetも自然な形で反映されている。

## Known limitations (Phase 1)

- Zara側の定量データ不足は本レターの範囲外(Phase 2で別途対応)
- 関税ショックは時系列変化ではなく、シナリオ比較(静的複数シナリオ)としてのみ表現される
- 8SKUは季節ウィンドウが重ならない設計のため、複数SKUの需要が同時にFactory_Import_CNの容量を奪い合うケースは未検証(セクション6参照)
- ~~apparel-us-2026には`ppc_node_cost_rule.csv`が未作成~~ → **修正済み**(新規作成、Factory_Import_CNのconversion_cost・DC_Import_Bufferのwarehouse_costを追加)
- ~~Node P&L / PPC KPI Summaryパネルの売上額が、Management P&L Summaryパネルの売上額と大きく乖離~~ → **修正済み**(上記「エンジン側の設計修正2」参照)
- ~~Fabric_CNとFactory_Import_CNの原価二重計上~~ → **修正済み**(Fabric_CNのPPCコストを無効化)。いずれもユーザー側での再動作確認待ち
- PPC Total Cost(着地コストに近い広い定義)とManagement Cogs(工場出荷原価のみの狭い定義)は会計スコープが異なるため、二重計上解消後も完全一致はしない設計。将来的にScope統一するか判断が必要
- ~~`ppc_edge_cost_rule.csv`/`ppc_tariff_rule.csv`のedge_idが`"Factory_Import_CN->SP_Apparel_Import"`/`"SP_Apparel_Import->DC_Import_Buffer"`という2段階表記になっており、supply_pointは`dad`型ノードではないためエンジンの`dad_nodes_chain`に含まれず、輸送費が常に$0計算になっていた~~ → **修正済み**(Phase 2実装中に発見。edge_idを`"Factory_Import_CN->DC_Import_Buffer"`に直結修正、`tools/gen_apparel_model.py`のBRANDS配列化リファクタリング時に反映。Total Costが322.3K→輸送費$4.8×qty分増加見込み。詳細はZara側レター参照)
- ~~輸送費修正により全312 lotで`MOM_PROFIT_TOO_LOW`トラストイベントが誤検知(`ppc_tariff.py`がMOM→first DAD輸送費を`logistics_in_base`に混在させ、MOM自身の粗利からFOB建て輸送費を誤って差し引いていた)~~ → **修正済み**(`LotCostAccumulator`に`mom_to_dad_freight_base`フィールドを新設して分離。`ppc_models.py`/`ppc_tariff.py`/`ppc_reconcile.py`を修正。詳細・修正箇所一覧はZara側レター参照。いずれもユーザー側での再動作確認待ち)

## Open questions

1. `push_config.csv`でH&Mの80/20事前生産比率を表現するか、Phase 1では省略するか
2. `decouple_optimizer_config.csv`を適用するか、`ss_days=21`/`buffering_stock_flag=1`を手動設定のまま確定するか
3. `capacity_plan.csv`のcap_hardはSKUごとの複製行になっているが、エンジンは同一物理ノードの複数SKU分を合算して容量判定しているか、SKUごとに独立枠として判定しているか(Phase 2で季節重複を扱う場合に要確認)
4. ~~Node P&L/PPC KPI Summaryの売上スケール食い違いの根本原因~~ → 解消(qtyフィールド追加により修正)。ユーザー側再確認待ち
5. apparel-us-2026用の`ppc_node_cost_rule.csv`を新規作成するか(Phase 1.5候補、DAD拠点のSGA/倉庫費が現状未計上)

---

## 実装(9〜11)への申し送り

- 出力先: `data/sample/apparel-us-2026/`(新規フォルダ)
- 週次展開が必要なCSV(`demand_forecast.csv`, `capacity_plan.csv`, `ppc_fx_rate.csv`, `ppc_supplier_cost.csv`, `ppc_market_price.csv`)は`tools/gen_apparel_model.py`という生成スクリプトを新規作成して機械的に展開する(CLAUDE.mdに記録されていた「手動probeスクリプトが毎回消えている」問題への対応として、リポジトリにコミットする形にする)
- `docs/scenarios/apparel.md`は実装・動作確認が完了してから作成する(手順11)
