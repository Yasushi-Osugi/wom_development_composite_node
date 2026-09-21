# Coding Request Letter: apparel-global-2028-2029

作成日: 2026-07-13
更新日: 2026-07-13(実装・全エンジン動作検証完了を反映)
作成者: Claude (Cowork)
ステータス: **実装完了・検証済み**。`tools/gen_apparel_global_model.py`で全20 CSVを生成し、`data/sample/apparel-global-2028-2029/verify/`のヘッドレス検証(PSI/PPC/Management/Landed Cost/FXシナリオ)がすべてパス。ユーザー側GUI動作確認は未実施(次のステップ)。
準拠: `docs/design/scenario_modeling_principles.md`のRecommended scenario document structure、`AGENTS.md`のScenario workflow(手順1〜8がこのレターの範囲、9〜11は実装フェーズ)
出自: 別AI(Grok)との対話で発案された「オフショア多階層 vs 近接垂直統合」という題材(H&M型/Zara型、2028-2029、単一SKU)を、WOM v1r1m8で実際に動くケースとして再設計する。Grokが生成したCSVは列構成・必須列がWOMの実エンジンと非互換だったため(検証済み)、ゼロから設計し直す。

---

## 1. Business question

```text
How does an offshore, multi-tier sourcing strategy (China fabric -> Bangladesh
dyeing -> Vietnam trim -> Bangladesh garment assembly, long cumulative lead
time) compare against a near-shore, vertically-integrated strategy (Spain
fabric -> Portugal dyeing -> Morocco trim -> Portugal garment assembly, short
cumulative lead time) when both brands serve the SAME two export markets
(US + Japan) under WOM's weekly PSI + PPC engine, including FX exposure from
serving a non-USD market?
```

apparel-us-2026(第6回)は「同一市場(米国3州)向けに異なる調達戦略を持つ2ブランド」の比較だったが、本ケースは「異なる調達拠点構成を持つ2ブランドが、同一の複数市場(US+JP)向けに輸出する」という設定に拡張する。狙いは2点: (a) apparel-us-2026で確立した多階層InBound(MOM chain)パターンを、より深い階層(3段階の中間加工)で実際に機能させること、(b) apparel-us-2026にはなかったFX(為替)変動という新しい次元を、複数市場展開のシナリオとして追加すること。

## 2. Educational disclaimer

This model is fictional and educational, consistent with `docs/design/wom_canonical_concepts.md`のCanonical concept 11。

Company names, factories, distribution centers, prices, costs, and capacities are simplified or fictionalized. The scenario is informed by publicly reported characteristics of the fast-fashion industry (multi-tier offshore sourcing footprint, near-shore vertical integration, 2028-2029 tariff/FX environment as a forward-looking illustrative assumption) but should not be interpreted as a factual statement about H&M Hennes & Mauritz AB, Inditex/Zara, or any other specific real company. `sku_id`は`Apparel_Offshore`/`Apparel_Vertical`という匿名名を使用する(実在ブランド名は使わない、apparel-us-2026の命名規則を踏襲)。

## 3. SKU structure

apparel-us-2026の8季節SKU展開とは異なり、本ケースは**各ブランド単一SKU**とする(ユーザー確認済みの「フルスペック」はファイル数・エンジン機能のフルスペックを指し、季節SKU分割は今回のスコープに含めない)。

```text
Apparel_Offshore  AW_Jacket相当、単一SKU、2028-W01〜2029-W52(104週)
Apparel_Vertical  AW_Jacket相当、単一SKU、2028-W01〜2029-W52(104週)
```

秋冬物(AW = Autumn/Winter)を主力とし、年1山の季節性(ピーク: 9月〜11月出荷)を持たせる。apparel-us-2026のような「商品入れ替え型」ではなく、ev-thailand-2026/oil-global-2027に近い「単一連続SKUの需要が山型に変動する」設計とする。

## 4. Physical network

両ブランンドとも「原料 → 染色 → 縫製・仕上げ(Trim) → 完成品縫製」の3段階中間加工を持つ多階層InBoundとし、apparel-us-2026では見送った構成(単純なFabric→Factoryの1段階)を、smartx-2027-2029で確立済みの多階層MOMチェーンパターン(`parent_node`が終端の`mom`ノードに向かって連なる方式)で表現する。

```text
[Apparel_Offshore] (H&M型オフショア多階層)
Inbound:
  Fabric_CN (leaf_in, CN, lt_wks=3)
    -> Dyeing_BD (mom, BD, lt_wks=3)
      -> Trim_VN (mom, VN, lt_wks=2)
        -> Garment_BD (mom, BD, lt_wks=4, terminal/転送価格ノード)
          -> supply_point (累積リードタイム 約12週)

Outbound:
  supply_point -> FG_WH_BD (dad, BD, ss_days=21, buffering_stock_flag=1)
    -> DC_US_Offshore (dad, US, lt_wks=6) -> Retail_US_Offshore (leaf_out)
    -> DC_JP_Offshore (dad, JP, lt_wks=4) -> Retail_JP_Offshore (leaf_out)

[Apparel_Vertical] (Zara型近接垂直統合)
Inbound:
  Fabric_ES (leaf_in, ES, lt_wks=1)
    -> Dyeing_PT (mom, PT, lt_wks=1)
      -> Trim_MA (mom, MA, lt_wks=1)
        -> Garment_PT (mom, PT, lt_wks=1, terminal/転送価格ノード)
          -> supply_point (累積リードタイム 約4週)

Outbound:
  supply_point -> FG_WH_PT (dad, PT, ss_days=7, buffering_stock_flag=1)
    -> DC_US_Vertical (dad, US, lt_wks=2) -> Retail_US_Vertical (leaf_out)
    -> DC_JP_Vertical (dad, JP, lt_wks=2) -> Retail_JP_Vertical (leaf_out)
```

**設計判断メモ**:
- Trim_MA(モロッコ)はGarment_PTへの中間加工tierとして表現し、独立した並行縫製拠点(第2のGarmentノード)にはしない。smartx-2027-2029のSmartXPro_CN/IN構成を調査した結果、あれは「1product=1InBoundツリー」という**製品分割**パターンであり、真の複数調達先(multi-root)パターンの実例ではないことを確認済み。複数調達先の表現は、apparel-us-2026のClosing sectionで既に「将来トピック」と明記されている領域のため、本ケースでもスコープ外とする。
- DC(FG_WH/DC_US/DC_JP)はブランドごとに別ノードとする(`DC_US_Offshore`/`DC_US_Vertical`のように分離)。理由: apparel-us-2026の演習④で検討した通り、リードタイム・ss_daysが大きく異なる2ブランドを同一物理ノードに統合すると、PSIロジック上「1ノードに2つの補充カデンスが混在する」問題が生じるため、共有キャパシティという概念が未実装の現状では分離が安全。
- 店舗ノード(`Retail_*`)もapparel-us-2026の`_I`/`_L`サフィックス方式を踏襲し、ブランド別に分離。
- **ノード命名の修正(実装時)**: ドラフト時点では地域倉庫を`FG_WH_CN`/`FG_WH_ES`(原料調達国名)としていたが、最終縫製地(BD/PT)と原料調達国(CN/ES)が異なる本ケースの構造では紛らわしいため、実装では最終縫製地に揃えて`FG_WH_BD`/`FG_WH_PT`に変更した。
- **関税賦課エッジの設計変更(実装時、重要)**: `wom/ppc/ppc_tariff.py`を直接読み、関税(tariff)ルックアップが発生できるのは「mom→chain[0](最初のDADノード)」と「chain[-1]→channel(最後のDADノードから販売チャネルへ)」の2箇所のみで、中間のinter-DAD edge(chain[i]→chain[i+1])では発生しないことをコードで確認した。本ケースはFG_WH(国内ステージング倉庫)→DC_market(輸出先国)という構成のため、国境をまたぐのはinter-DAD edge側であり、関税をそこに置くことができない。そこで関税は**chain末端(`DC_US_Offshore->Retail_US_Offshore`等)のOutbound tariffとして計上**する設計に変更した(`ppc_tariff_rule.csv`の`edge_id`列)。これは実務上も正当な代替モデル(仕向地通関=DDP方式)であり、apparel-us-2026の「mom→単一DAC」という1階層DAD構成では選択肢になかった、多階層DAD構成ならではの設計判断。国際輸送費(ocean/air freight)はinter-DAD edge(`FG_WH_BD->DC_US_Offshore`等)に配置。

## 5. Demand assumptions

- Demand generated at `leaf_out`: `Retail_US_Offshore`, `Retail_JP_Offshore`, `Retail_US_Vertical`, `Retail_JP_Vertical`(2ブランド×2市場=4店舗ノード)
- 季節性: 秋冬物想定で「持ち上げサイン波」(raised sine)、ピークウィンドウ 2028-W36〜W48 / 2029-W36〜W48(9月上旬〜11月末、約13週)、ウィンドウ外は低需要のベースライン(ゼロにはしない — 通年商品として最低限の店頭在庫は動く想定)
- Base weekly demand(ピーク時、市場別): US=1500 lots/week、JP=800 lots/week(ブランド間は同一需要量とし、供給チェーン差のみで比較可能にする — apparel-us-2026の「同一需要・異なる調達戦略」という比較設計思想を踏襲)
- シミュレーション期間: `2028-W01`〜`2029-W52`(104週。`date.fromisocalendar()`ベースで週境界を自動計算し、既知の暦バグ(53週年のズレ)を回避する既存の`tools/gen_apparel_model.py`ロジックを再利用)

## 6. Capacity assumptions

| node | cap_hard(代表値) | 備考 |
|---|---|---|
| `Garment_BD` | 3500 lots/week | Offshore側の最終縫製ボトルネック |
| `Dyeing_BD` / `Trim_VN` | 事実上無制限 | 中間加工tierは制約にしない(まずは終端ノードのみで律速させる) |
| `Garment_PT` | 2000 lots/week | Vertical側は生産規模が小さい設定(近接小ロット型) |
| `FG_WH_BD` / `FG_WH_PT` | 6000 / 4000 lots/week | スループット制約 |

`capacity_plan.csv`は演習③で発見した「需要週のみカバーし生産週(リードタイム分手前)をカバーしない」ギャップを本ケースでは踏襲しない。生成スクリプトで**全期間×該当ノードにcap_hardを明示設定**し、既知のギャップを再現しないよう対応する(apparel-us-2026本体は既知の限界として残すが、新規ケースでは同じ落とし穴を作らない)。

`holiday_calendar.csv`にOffshore側`Garment_BD`の稼働率低下(繁忙期の労働力逼迫を想定、年1回2週間、cap_hard→通常の20%程度)を追加。Vertical側は該当なし(近接小ロット生産のため季節休暇の影響は軽微と設定)。

## 7. Buffer and decoupling assumptions

- `FG_WH_BD`: `ss_days=21`, `buffering_stock_flag=1` — 長い累積リードタイム(約12週)を輸入バッファ在庫で吸収
- `FG_WH_PT`: `ss_days=7`, `buffering_stock_flag=1` — 短い累積リードタイム(約4週)のため小さいバッファで足りる設計
- DC層(`DC_US_*`/`DC_JP_*`)はスループット中心のノードとし、`buffering_stock_flag`は立てない(FG_WH層のみが意図的な在庫バッファ)
- InBound側(中間加工tier)のバッファ配置最適化は対象外(リポジトリの既定方針通り)

## 8. PPC assumptions

- `ppc_transfer_price_rule.csv`: `Garment_BD`/`Garment_PT`(各ツリーの終端mom)のみに設定(cost_plus方式)。中間tier(Dyeing/Trim)は`ppc_transfer.py`を直接読み、terminal mom_nodeしか参照しないことを確認済みのため設定不要(smartx-2027-2029の中間tier行は未使用のデッドデータと判明)
- `ppc_tariff_rule.csv`: 静的関税率(week列を持たないエンジン仕様のため、時系列変化ではなくシナリオ比較として表現— apparel-us-2026で確立した`edge_cost_master.csv`の`scenario`列方式を再利用)。**edge_idは`DC_market->Retail_market`(outbound側)** — 上記「物理ネットワーク」節の設計変更メモ参照。Offshore側(BD発、対米16.5%/対日2.0%)とVertical側(PT発、対米12.0%/対日1.0%)で異なる関税構造を反映(Bangladeshは対米GSP適用外/対日LDC特恵、EUは対日EPAで大半非課税という実際の非対称性を根拠とした)
- `ppc_market_price.csv`: US向けはUSD建て、JP向けはJPY建て(`currency`列で区別)。PPCエンジンの`FXConverter`が`ppc_fx_rate.csv`経由でUSDに換算する。据え置き価格(sticky price)方式は踏襲
- `ppc_fx_rate.csv`: `base_currency=USD`。ライブシミュレーション用にBase想定(JPY/USD=150、`rate=1/150`)の週次一定値で生成。**FXシナリオ比較(Base/StrongYen/WeakYen)は`ppc_fx_rate.csv`自体には持たせない** — 詳細は下記
- `ppc_node_profit_zone.csv` / `ppc_profit_zone_rule.csv`: OUTBOUND_CHANNEL_PROFITのchannel_margin rateはOffshore側35%、Vertical側42%(apparel-us-2026のApparel_Integrated 65.3%より抑えめ — 多階層中間加工コストを織り込んだ結果、Landed GM自体がVertical側で12%前後と低めに出るため。下記「検証結果」参照)

**FXシナリオ実装方式の決定(実装時に判明)**: `wom/ppc/ppc_fx.py`を直接読み、`ppc_fx_rate.csv`は`week,currency,base_currency,rate`の単純な週次テーブルであり、`edge_cost_master.csv`のような`scenario`列を持たないことを確認した。またLanded Cost engine(`edge_cost_master.csv`の`fx_rate`列)はfreight/assembly costのUSD換算にのみ使われ、JP市場の売上（revenue）換算には一切関与しない(revenue換算は`ppc_market_price.csv`+`ppc_fx_rate.csv`経由のPPCエンジン側のみ)ことも確認した。したがって「関税と同じ仕組みでFXシナリオを比較する」ことは構造的にできない。実装では、(a) ライブシミュレーション用に単一のBase想定`ppc_fx_rate.csv`を生成し、(b) Base/StrongYen/WeakYenの比較は`data/sample/apparel-global-2028-2029/verify/verify_fx_scenarios.py`という別スクリプトで、3通りのJPY/USDレートそれぞれについてPPCエンジンを`tempfile`隔離コピー上で再実行し数値比較する方式とした(apparel-us-2026のexercises/ex1・ex2と同じ「実際にエンジンを再実行して検証する」流儀)。GUI上の単一パネルでシナリオ切替はできない点は、Known limitationsに記載。

## Expected outputs / 検証結果(実装・ヘッドレス検証完了、2026-07-13。CO対応後の数値に更新)

`data/sample/apparel-global-2028-2029/verify/`の2スクリプトで全項目を検証済み(詳細はそのREADME.md参照)。数値は下記「MOM節点CO対応」実施後(需要に立ち上げランプを追加した後)の再計測値。

- Network tab相当: 両ブランドとも4段階InBoundチェーン(Fabric→Dyeing→Trim→Garment)、2分岐OutBound(FG_WH→DC_US/DC_JP→Retail)が破綻なく計画された
- PSI: `FG_WH_BD`の最大在庫lot数(6,629)が`FG_WH_PT`(2,300)より大きく、ss_days差(21日 vs 7日)を反映
- PSI: Garment節点のCarry-Over(CO)は立ち上げ期(week 0〜upstream_lt)に一時的に積み上がった後プラトーする現象だったが(下記「MOM節点CO対応」参照)、需要ランプ + Step 8 PushProductionPlanner(InBound decoupling)の組み合わせにより、両ブランドともCO最大値が**完全にゼロ**になることを直接検証済み(立ち上げ期の物理的に不可避な供給ギャップは、恒久累積するCOではなく週次の非累積shortfall信号として表現される)
- PPC: 全394lot(qty=0週を明示的に含めたため対象lot数はやや減、詳細は下記)、Trust Event(異常検知)**0件**(下記「発見・修正したエンジンバグ」参照)
- Management engine(narrow GM): Apparel_Offshore 粗利率 US 57.6%/JP 58.7%、Apparel_Vertical 粗利率 US/JP共通57.9%(Management engineはFX非対応のためUSD換算後の一律価格で計算)
- Landed Cost / Tariffシナリオ比較: Apparel_Offshore Landed GM% Base 32.9% → TariffEscalation2028 31.5% → TariffRelief2029 32.6%。Apparel_Vertical Landed GM% Base 11.7% → TariffEscalation2028 10.3% → TariffRelief2029 11.3%(多階層中間加工の積み上げコストにより、Vertical側のLanded GMがManagement GMより大きく圧縮される — 二重スコープの新しい実例)
- FXシナリオ(別スクリプトで検証): Base(JPY/USD=150) JP売上$3.64M/GM41.6% → StrongYen(130) $4.20M/GM49.4%(+15.4%) → WeakYen(170) $3.21M/GM33.8%(-11.8%)。US市場売上はFXシナリオに関わらず不変であることも確認(アサーション自動検証)

## 発見・修正したエンジンバグ(実装時)

`ppc_tariff.py`のOutBound多階層DAD chain処理で、2段目以降のinter-DAD edge(`FG_WH_BD->DC_US_Offshore`等)の国際輸送費が`acc.logistics_in_base`(本来Supplier→MOM専用)に混入し、`ppc_reconcile.py`のMOM_PROFIT_TOO_LOWチェックを全lotで誤発火させるバグを発見・修正した。2026-07-10に修正済みの`mom_to_dad_freight_base`分離と同種のバグで、`inter_dad_freight_base`という新フィールドを追加して同様に分離(`wom/ppc/ppc_models.py`, `wom/ppc/ppc_tariff.py`, `wom/ppc/ppc_reconcile.py`)。**この修正はリポジトリ共通のコアエンジン修正であり、他ケースにも影響する** — 特に`Cookie-jp-2026`が同じ2階層DAD構成(`DC_Import_Buffer->DC_Import_Main`)を持ち、`ppc_edge_cost_rule.csv`に非ゼロ費用が設定されているため、同じ潜在バグの影響を受けていた可能性がある(本セッションでは未検証、ユーザー側での別途確認を推奨)。

## Known limitations

- FXシナリオ比較はGUI単一パネルでの切替ではなく、別スクリプト(`verify_fx_scenarios.py`)による3回再実行方式。将来的にGUI統合する場合は要追加設計
- Trim_MA(モロッコ)は中間加工tierとしてのみ表現し、独立調達先としての多重ソーシング(multi-root)は対象外
- 共有キャパシティ・共有店舗網(演習④で議論した拡張トピック)は本ケースでも未実装。DC/店舗はブランドごとに完全分離
- 8SKU季節分割(apparel-us-2026の特徴)は本ケースでは採用しない単一SKU設計のため、シーズン重複時のキャパシティ競合検証(演習③のテーマ)は本ケースの主眼ではない
- `Cookie-jp-2026`が同種の`inter_dad_freight_base`バグの影響を受けていた可能性(上記参照、未検証)
- Garment節点のCarry-Over(CO)は、需要ランプのみでは大幅削減(-15.6%/-11.1%)にとどまったが、Step 8 `PushProductionPlanner`によるInBound decoupling(Garment自体をdecoupling nodeに指定、`push_config.csv`)を追加導入した結果、**完全にゼロ化**した(詳細・数値・副作用は`verify/README.md`参照)。GUIのPSI Chartパネルは現状、立ち上げ期の非累積shortfall信号(`node._push_shortfall`)を専用可視化していないため、供給ギャップ自体は画面上で明示的には見えない点が既知の制約として残る(将来的なGUI拡張候補)
- Step 8導入の副作用として、`FG_WH_BD`/`FG_WH_PT`の最大在庫lot数が0になった(需要が供給にぴったり追従するため、サージ在庫が発生しない)。現実の需要変動リスクに対するクッションが実質ゼロになっている点は、実運用を想定する場合`buffer_lots`設定(Mode 2/3)の追加検討が必要
- **解決済み**: Step 8導入直後、OutBound側(`FG_WH_BD`/`FG_WH_PT`)でCOが全期間にわたり単調増加する現象を発見したが、原因(Step 8 Mode 4が需要紐付けの既存Lot_IDを使わず新規Lot_IDを鋳造していたため、OutBound側の`_match_by_identity`完全一致マッチングが不成立になっていた「ロット識別子の不一致」。WOMの「Lot_IDは初期計画時に一度だけ生成」という原則違反が真因)を特定し、`wom/engine/push_pull.py`のMode 4を既存Lot_ID再利用方式に修正して解消した。修正後はFG_WH最大CO 88,760→5,174(Offshore)、92,766→2,070(Vertical)まで縮小し、total_Pもpush量に100%到達することを確認済み。`tests/test_step8_push_pull.py`(既存8テスト)および他3ケース(smartx-2027-2029、ev-europe-2026、ev-thailand-2026)への回帰確認も完了、影響なし。Mode 1〜3(fixed/replenishment/time-phased)は同種の問題が起き得る未修正の既知の限界として残る(詳細は`verify/README.md`参照)

## Open questions

1. ~~`ppc_fx_rate.csv`のシナリオ表現方式~~ → 解決(別スクリプト方式に決定、上記参照)
2. Offshore側の関税構造(CN/BD/VN経由)を`edge_cost_master.csv`にどう反映するか — 中間加工国(染色=BD、Trim=VN)を経由する関税(原産地規則)は簡略化し、Garment_BD(最終縫製=原産国)→US/JP間の1本の関税率にまとめた(実装確定)
3. Vertical側のEU域内+モロッコ特恵関税(EU-Morocco Association Agreement相当)は簡略化し、Garment_PT(最終縫製=原産国)→US/JP間の1本の関税率にまとめた(実装確定)
4. 需要のUS/JP配分比率(US=1500, JP=800)は仮置きの数値のまま実装。実際の輸出比率として妥当か、レビュー時に確認を推奨
5. **新規**: `Cookie-jp-2026`の`inter_dad_freight_base`バグ影響有無の確認(上記Known limitations参照)

---

## 実装(9〜11)への申し送り

- 出力先: `data/sample/apparel-global-2028-2029/`(新規フォルダ、両ブランド統合)— **作成済み、全20 CSV生成済み(CO対応版、2026-07-13再生成)**
- 生成スクリプト: `tools/gen_apparel_global_model.py` — **作成済み**(既存`tools/gen_apparel_model.py`のBRANDS配列化パターンを踏襲し、Offshore/Verticalの2ブランド×4ノード階層×2市場を機械的に展開)。`ramp_factor()`と`gen_demand_forecast()`の需要立ち上げランプ(CO対応、下記参照)を含む
- 週次展開が必要なCSV(`demand_forecast.csv`, `capacity_plan.csv`, `ppc_fx_rate.csv`, `ppc_supplier_cost.csv`, `ppc_market_price.csv`)は上記スクリプトで生成し、手動編集はしない — 遵守
- ヘッドレス動作検証: `data/sample/apparel-global-2028-2029/verify/verify_pipeline.py`(PSI/PPC/Management/Landed Cost)と`verify_fx_scenarios.py`(FXシナリオ) — **作成・実行済み、全項目パス**
- エンジン修正1: `inter_dad_freight_base`バグ修正(`wom/ppc/ppc_models.py`, `ppc_tariff.py`, `ppc_reconcile.py`) — **実施済み**、コミット時は必ずgit差分に含めること(apparel-global-2028-2029のCSVだけでなく、コアエンジン修正である点に注意)
- エンジン修正2(新規、2026-07-13): GUIの`_run_ppc_from_planning`が週リストをPlanning設定欄から再構築していたため、別ケースの古い設定値が残っているとPPC Financial KPIパネルが全項目0になるバグを発見・修正(`wom/gui/app.py`)。ケース固有ではなく汎用GUIバグのため、コミット時は必ず含めること
- CO対応(新規、2026-07-13): Garment節点のCarry-Over急増を`ramp_factor()`+需要立ち上げランプで大幅削減(Offshore -15.6%、Vertical -11.1%)した上で、ユーザー提案を受けてStep 8 `PushProductionPlanner`(InBound decoupling、`data/sample/apparel-global-2028-2029/push_config.csv`新規)を追加導入し、**両ブランドともCO完全ゼロ化を達成**(GUIコード変更不要、既存のCSV自動検出機構を活用)。詳細・副作用は`verify/README.md`参照
- エンジン修正3(新規、2026-07-13): Step 8導入によりOutBound側(FG_WH)でCOが単調増加する副作用を発見。ユーザーが指摘した「Lot_IDは初期計画時に一度だけ生成すべき」というWOM原則に基づき、`wom/engine/push_pull.py`のMode 4(LT-shifted demand)を、新規Lot_ID鋳造ではなく既存Lot_ID再利用方式に修正。FG_WH最大CO 88,760→5,174/92,766→2,070まで縮小、`tests/test_step8_push_pull.py`全8テストおよび他3ケース(smartx-2027-2029、ev-europe-2026、ev-thailand-2026)への回帰確認済み。コミット時は`wom/engine/push_pull.py`を必ず含めること
- FXシナリオの実装方式は「別スクリプトでの再実行方式」に確定。`docs/design/scenario_modeling_principles.md`への新パターン追記は次のステップ(未実施)
- 次のステップ: ユーザー側`python -m main`によるGUI動作確認(Network/PSI/PPC/Management/Landed Cost各パネル、特にPPCパネルとCO削減の見え方)。`Cookie-jp-2026`の`inter_dad_freight_base`バグ影響有無の確認もあわせて推奨
- git commit対象: CSV一式(20ファイル) + `push_config.csv`(新規) + `tools/gen_apparel_global_model.py` + `wom/ppc/ppc_models.py` + `wom/ppc/ppc_tariff.py` + `wom/ppc/ppc_reconcile.py` + `wom/gui/app.py` + `wom/engine/push_pull.py`(Mode 4 Lot再利用修正) + `data/sample/apparel-global-2028-2029/verify/`一式(README.md、verify_pipeline.py、verify_fx_scenarios.py含む) + 本Request Letter
- `docs/scenarios/apparel-global.md`はGUI動作確認が完了してから作成する(手順11、未実施)
