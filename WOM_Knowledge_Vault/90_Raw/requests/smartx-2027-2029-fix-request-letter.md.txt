# Coding Request Letter: smartx-2027-2029 互換性修正(wom-v1r1m7-fix4all_case)

作成日: 2026-07-11
作成者: Claude (Cowork)
ステータス: Step1〜5 全完了・検証済み(+新規発見のProblem E、+USD表示/World Map/KPIパネル重なりの3件、+Open Question 6のスケール根本修正、+Trust Event Type別集計/ドリルダウンパネル追加)。
ブランチ: `wom-v1r1m7-fix4all_case`(`wom-v1r1m7`から分岐、対象: `data/sample/smartx-2027-2029/`および`wom/ppc/`エンジン本体)
準拠: `docs/design/scenario_modeling_principles.md`、`AGENTS.md`のScenario workflow

---

## 0. 背景

過去に定義した5(+1)個のWOM sample model(Rice/Smart Phone/Cookie/EV/Oil、EVはeurope/thailandの2ケース)について、最新版WOM v1r1m7のPythonモジュールとの互換性を調査した。結果、Rice・Cookie・ev-europe・ev-thailandは問題なし、Oilの高いtrust event件数は既存記事の記述と整合する意図された挙動(バグではない)と確認した。

**smartx-2027-2029(Smart Phone Case)のみ、3つの異なる根本原因を持つ非互換が見つかった。** 本レターはこれらを整理し、修正方針を確定した上で実装計画をまとめるものである。スコープは本ケースのみとし、`iphone`/`iphone_global`(旧世代)と`rice-japan-2027-2028_BK260613_1515`(バックアップ)は対象外とする。

オーナーからは、調査の過程で以下の重要な実務的知見の共有があった:

> 「1製品=1 MOMノード」というルールは現実的である。20年間のSCMコンサル経験から、実際の現場ではある完成品工場(MOM)が同一製品を複数の完成品工場(MOM_A, MOM_B)で並行生産する設計は、工場間の品質誤差により同一製品として取り扱えない、という問題が生じる。

この知見に基づき、問題Aは「PPCエンジンを拡張してMulti-MOMを正式サポートする」方向ではなく、「物理的に異なる生産拠点は別SKUとして分離する」方向(リポジトリの既存の設計慣行: Apparel_Import/Local、Cookie_Import/Local、EVmaker_Local/Import、Gasoline_Local/Importと同じパターン)で解決する。

## 1. 対象データの現状構造

`data/sample/smartx-2027-2029/sc_tree_master.csv`より、SmartXProのtree構造:

```text
InBound (2つの独立したMOM root):
  WaferFab_TW(leaf_in,TW) -> Buffer_Chip_TW(mom,TW) -> FoundryTW(mom,TW) -> AssemblyCN(mom,CN, in_root)
  SensorIN(leaf_in,IN)    -> AssemblyIN(mom,IN, in_root)

OutBound (1つのsupply_pointから3つの並列DAD):
  supply_point(SP_SmartXPro)
    -> DC_AMER(dad,AMER,Los Angeles)  -> Retail_AMER(leaf_out)
    -> DC_EMEA(dad,EMEA,Amsterdam)    -> Retail_EMEA(leaf_out)
    -> DC_APAC(dad,APAC)              -> Retail_APAC(leaf_out)

lane_assignment.csv (region -> 実際に使用するMOM root):
  Retail_AMER <- AssemblyIN
  Retail_EMEA <- AssemblyCN
  Retail_APAC <- AssemblyCN
```

Planning Engine(`wom/engine/backward_planner.py`/`forward_planner.py`、`wom/model/sc_tree.py`の`get_in_roots()`)は、この構造(2つのMOM root、`lane_assignment.csv`ベースのregion別ルーティング)を**正しく処理できる**ことを確認済み(`SCTree._in_roots_dict`が複数MOM rootを保持し、両Plannerとも`in_roots.values()`を正しく反復する設計になっている)。

問題はPPCエンジン(`wom/ppc/`)側にある。

## 2. 問題A: PPCのGENERIC自動判定が「1製品=1 MOMノード」しか拾わない

### 根本原因

`wom/ppc/ppc_runner.py`のGENERIC自動判定ロジック(169〜170行目):

```python
elif _nt == NODE_TYPE_MOM and _prod not in _mom_map:
    _mom_map[_prod] = _nm
```

`sc_tree.iter_all_nodes(_prod)`によるproduct_id単位の全ノードpreorder走査で、`mom`型ノードを**最初に見つけた1つだけ**を`_mom_map[product_id]`として採用し、以降に見つかる`mom`型ノード(2つ目のin_root、および後述のTier-N中間ノード)はすべて無視される。Planning Engineが持つ`get_in_roots()`(複数MOM root対応)の情報は、PPC側には一切引き継がれない。

この結果、SmartXProの全Lotが(実際にはAssemblyIN経由のAMER向けLotも含めて)`mom_node = "AssemblyCN"`固定で処理され、AMER向けLotのコスト計算が実態(AssemblyIN由来)と異なるものになる。

### 決定した修正方針(オーナー承認済み)

エンジンをMulti-MOM対応に拡張するのではなく、**SmartXProを物理的な生産拠点ごとに別SKUへ分割する**。

```text
SmartXPro_CN: AssemblyCN系列(WaferFab_TW->Buffer_Chip_TW->FoundryTW->AssemblyCN)
              -> DC_EMEA -> Retail_EMEA
              -> DC_APAC -> Retail_APAC

SmartXPro_IN: AssemblyIN系列(SensorIN->AssemblyIN)
              -> DC_AMER -> Retail_AMER
```

分割後は各SKUが単一のMOM rootのみを持つため、`_mom_map`の「最初の1つだけ拾う」制約は問題化しない。これはApparel_Import/Local等の既存パターンと同じ設計であり、リスクが低い。

## 3. 問題B: InBound多段チェーンのコスト計算漏れ

### 根本原因

`wom/model/plan_node.py`の設計上、`mom`型は「Mother Plant」だけでなく「InBound中間ノード(Tier-N)」も指す(`NODE_TYPE_MOM = "mom"  # InBound intermediate (Mother Plant, Tier-N)`)。SmartXProのAssemblyCN系列は、`AssemblyCN(mom, tier=0) -> FoundryTW(mom, tier=1) -> Buffer_Chip_TW(mom, tier=2) -> WaferFab_TW(leaf_in, tier=3)`という4段のInBoundチェーンであり、FoundryTW・Buffer_Chip_TWは共に`mom`型ノードとして、それぞれ独自の原価(`ppc_supplier_cost.csv`にFoundryTW=$380k、`ppc_node_cost_rule.csv`に相当するnode costが定義されている)を持つ。

しかし`wom/ppc/ppc_forward.py`の`run_forward_propagation`(60〜200行目)は、以下の2種類のイベントしか生成しない:

1. Step 1a(102〜128行目): `s_nodes`(leaf_in、`_sup_list_map`で収集される全Tier-1供給者)の`supplier_cost`
2. Step 1b(130〜158行目): `inbound_edge = f"{s_node}->{m_node}"`という**単純な1ホップ**のedge cost(WaferFab_TW→AssemblyCNの直結表記)
3. Step 1c(160〜198行目): `m_node`(終端MOM、AssemblyCN)自身のnode cost

FoundryTW・Buffer_Chip_TWという中間`mom`型ノード自身のnode cost、および`WaferFab_TW->Buffer_Chip_TW`・`Buffer_Chip_TW->FoundryTW`・`FoundryTW->AssemblyCN`という実際の隣接edgeのcostは、**どこにも計算されない**。Step 1bの`inbound_edge`はWaferFab_TWとAssemblyCNを直結した架空のedge_id(`"WaferFab_TW->AssemblyCN"`)であり、`ppc_edge_cost_rule.csv`上の実際の隣接edge定義とは一致しないため、常にヒットしない。

対照的に、OutBound側の`wom/ppc/ppc_tariff.py`は`dad_nodes_chain`(197〜261行目)で多段DADチェーンを正しく歩くロジックをすでに持っている(問題Cの節で述べる欠陥はあるが、多段自体を扱う仕組みはある)。InBound側には対応する仕組みが存在しない、というのが問題Bの本質である。

### 決定した修正方針(オーナー承認済み)

`ppc_forward.py`に、`ppc_tariff.py`のDADチェーン処理と対称的な「InBound多段mom-typeチェーン」処理を追加する。

## 4. 問題C+D: dad_nodes_chainがLot単位のtree祖先探索になっていない(統合)

### 根本原因(詳細はセッション内での対話で確認済み)

`ppc_runner.py`のGENERIC自動判定(159〜166行目)は、`dad_nodes_chain`を**product_id単位のグローバル・フラットリスト**として、`sc_tree.iter_all_nodes(_prod)`のpreorder走査で見つかった`dad`型ノードを機械的に集めるだけで構築している。

```python
if _nt == NODE_TYPE_DAD:
    _dad_list_map[_prod].append(_nm)   # channel_node(Lotの帰着先)を一切参照しない
```

WOMの基本設計では、Lot(`acc.channel_node`)がどのleaf_outに帰着するかは、Demand LayerからSupply Layerへコピーされた時点、またはBackward Planningのdemand allocation(`lane_assignment.csv`ベースのlane選択)で**既に確定**している。したがって、あるLotのコスト計算で本来歩くべきDADチェーンは、そのLotの`channel_node`からtreeの親子関係(`PlanNode.parent`)を実際に遡って求めるべきものであり、product_id単位で1本に固定してよいものではない。

SmartXProはtree上で`SP_SmartXPro`から`DC_AMER`/`DC_EMEA`/`DC_APAC`という**3つの並列な地域別DAD**へ枝分かれする構造を持つ、リポジトリ内で初めての「1 product_id内に複数の並列DAD」を持つケースである。これまでのCookie/EV/Apparel/Oilはいずれも「1 product_id = 1つのDAD」または「Cookieのような真に直列な2段DAD(DC_Import_Buffer→DC_Import_Main、共に同じ下流に合流)」だったため、この設計の欠陥が表面化しなかった。

実際の挙動として、`ppc_runner.py`は`dad_chain=['DC_AMER', 'DC_EMEA', 'DC_APAC']`(preorderで見つかった順)を全Lot共通で構築し(診断スクリプトで実測確認済み)、`ppc_tariff.py`の`_resolve_chain`(50〜65行目)・`for i, d in enumerate(chain)`(205行目)・`outbound_edge = f"{last_dad}->{channel}"`(264行目)がこれを無条件に「直列チェーン」として解釈する。この結果、例えばAMER向けLotに対しても`"DC_AMER->DC_EMEA"`という物理的に存在しない中間edgeのコストを探しにいき、最終的に`"DC_APAC->Retail_AMER"`という存在しないoutbound edgeを参照する。`ppc_backward.py`側(180〜245行目)も同一の`dad_nodes_chain`を消費するため、同じ誤りが逆方向(backward allowable計算)にも生じる。

### 決定した修正方針(オーナー確認・本レターで正式化)

**「Lot単位の祖先探索方式」への置き換え。** `dad_nodes_chain`をproduct_id単位の事前計算済みフラットリストとして構築するのをやめ、各Lot(実際には各channel_node、同じchannel_nodeを持つLotは同じ結果になるためchannel_node単位でキャッシュ可能)について、`PlanNode.parent`を実際に辿って祖先チェーンを動的に求める方式に変更する。

`wom/model/plan_node.py`の`PlanNode`は`parent: Optional["PlanNode"]`という親への back-pointer をすでに持っている(295〜298行目の`add_child`で設定される)ため、この祖先探索は既存のtree構造だけで実現できる。新たなtree構造の変更は不要。

```text
概念:
  leaf_out(channel)ノードから .parent を辿り、supply_pointに到達するまでに
  通過する dad型ノードを、channel側から mom側へ向かって収集する。
  収集した順序を反転させれば、ppc_tariff.py が期待する
  「mom側が先頭、channel側が末尾」の順序になる。

  Retail_AMER.parent = DC_AMER,  DC_AMER.parent = SP_SmartXPro(stop)
    -> chain = ["DC_AMER"]

  Retail_EMEA.parent = DC_EMEA,  DC_EMEA.parent = SP_SmartXPro(stop)
    -> chain = ["DC_EMEA"]
```

Cookieのような真の直列多段チェーンでも、この方式は自然に`["DC_Import_Buffer", "DC_Import_Main"]`を再現でき、既存ケースを壊さない(DC_Import_Mainのparentを辿るとDC_Import_Buffer、さらに辿るとsupply_point、という実際の親子関係がそのままチェーンになるため)。

## 4.5. Problem E(実装中に新規発見): detect_scenarioのiphone_global誤判定

Step2/3実装後の回帰テストで、smartx-2027-2029のPPC結果が実装前と全く変わらない(margin=100%、cost=0)ことが判明し、調査の結果、Problem A/B/C+Dとは独立な第5の問題が見つかった。

### 根本原因

`wom/ppc/ppc_engine.py`の`detect_scenario()`は、`sales_records`のchannel_node集合と`_IPHONE_GLOBAL_CHANNELS`(`{"Retail_AMER", "Retail_EMEA", "Retail_APAC", ...}`、旧世代iPhone_Globalサンプル専用のチャネル名)の**共通部分の有無だけ**でシナリオを判定していた。

```python
channels = set(sales_records["channel_node"].unique())
if channels & _IPHONE_GLOBAL_CHANNELS:
    return "iphone_global"
```

smartx-2027-2029のSmartXProが使用するleaf_outノード名(`Retail_AMER`/`Retail_EMEA`/`Retail_APAC`)が、たまたま旧iPhone_Globalサンプルと完全一致するため、product_idを一切見ずに`"iphone_global"`と誤判定され、`build_iphone_global_vs_paths()`(Foxconn_CN→SP_iPhone16という、SmartXProには存在しないノード名のハードコードされたパス)が使われてしまう。この結果、smartx-2027-2029のPSIレコード全体(SmartXPro/SmartX/SmartXNextの3製品すべて)が、**Problem A/B/C+Dの修正が実装されているGENERIC分岐に一度も到達しない**まま処理され、コストが一切計上されない(mom_node="Foxconn_CN"がsmartx側のどのCSVにも存在しないため)。

この問題は、事前のSCTree構造診断(GENERIC分岐のロジックを直接呼び出して`dad_chain`を確認したスクリプト)では`detect_scenario()`自体を経由していなかったため、これまで発見されていなかった。

### 決定した修正方針(オーナー承認済み、2026-07-11)

`_IPHONE_GLOBAL_PRODUCTS = {"iPhone16", "iPhone15", "iPhone17"}`を新設し、channel一致に加えてproduct_id一致も必須化する。

```python
if (products & _IPHONE_GLOBAL_PRODUCTS) and (channels & _IPHONE_GLOBAL_CHANNELS):
    return "iphone_global"
```

これにより、旧iPhone_Globalサンプル(product_id="iPhone16"等)の判定は変えずに、smartx-2027-2029の誤判定のみを解消する。低リスク・影響範囲の狭い修正のため、Step2/3の一部として即時実装した。

## 5. 共通の実装方針: Lot/Leaf単位のtree祖先探索ヘルパーの共有化

問題B(InBound側)と問題C+D(OutBound側)は、根本的に同じパターンの欠陥(「product_id単位の事前計算フラットリスト」であるべきは「特定の参照点からtreeの親子関係を実際に辿って動的に求める探索」)である。実装の一貫性とリスク低減のため、共通のtree祖先探索ヘルパーを1つ新設し、InBound(問題B)・OutBound(問題C+D)の両方から利用する設計を提案する。

```text
提案: wom/model/sc_tree.py または新規 wom/ppc/ppc_chain_resolve.py に

  def walk_ancestor_chain(
      start_node: PlanNode,
      node_type_filter: str,
      stop_node: PlanNode,
  ) -> List[str]:
      """start_node.parent を stop_node に到達するまで辿り、
      node_type_filter に一致するノードの node_name を、
      start_node側から stop_node側への順序で収集して返す。
      呼び出し側で必要に応じて reverse() する。"""
```

- OutBound(問題C+D): `start_node = leaf_out(channel)`, `node_type_filter = NODE_TYPE_DAD`, `stop_node = supply_point`。結果をreverseしてmom側先頭の順序にする
- InBound(問題B): `start_node = leaf_in`, `node_type_filter = NODE_TYPE_MOM`, `stop_node = 解決済みmom_node(終端MOM)自身`。結果はleaf側先頭のままでよい(呼び出し側のwalk方向に合わせて`ppc_forward.py`側でloop方向を調整する)

この関数は`sc_tree`(または個々のproductのtree root)から`product_id`と`channel_node`/`leaf_in`のnode_name経由でPlanNodeインスタンスを引ければ呼び出せる。`ppc_runner.py`のGENERIC自動判定は、現在の「一度だけproduct_id単位で`_dad_list_map`/`_mom_map`を構築する」処理を、「product_id×channel_node(またはproduct_id×leaf_in)単位で、この共通ヘルパーを都度呼び出す(または初回計算時にキャッシュする)」処理に置き換える。

## 6. 実装計画

### Step 1: 共通ヘルパー関数の新設(リスク: 低)
- `wom/model/sc_tree.py`に`walk_ancestor_chain`(または同等のメソッド)を追加
- 単体テスト: Cookie(直列2段)・SmartXPro(並列3分岐)・Apparel(単一DAD)の3パターンで期待通りの結果になることを確認

### Step 2: 問題C+D修正(OutBound、リスク: 中)
- `wom/ppc/ppc_runner.py`: GENERIC自動判定の`_dad_list_map`構築ロジックを、product_id単位の事前計算からchannel_node単位の遅延計算(共通ヘルパー呼び出し)に置き換え
- `wom/ppc/ppc_tariff.py`/`wom/ppc/ppc_backward.py`: `_resolve_chain`/`_resolve_node_list`の引数を`(product_id, channel_node)`ベースに拡張(既存の`dict[product_id, list]`シグネチャとの後方互換性を保つため、新形式`dict[(product_id, channel_node), list]`を優先的に見て、無ければ旧形式にフォールバックする設計を推奨)
- 回帰確認: Cookie/EV/Apparel/Oilで既存の`dad_nodes_chain`と完全に同じ結果になることを確認(単一DAD・真の直列2段DADのケースでは新旧の結果が一致するはず)

### Step 3: 問題B修正(InBound、リスク: 中)
- `wom/ppc/ppc_forward.py`: `run_forward_propagation`に、`mom_nodes_chain`(新設、共通ヘルパーで構築)を歩く処理を追加。各中間`mom`型ノードの node cost、および隣接ノード間のedge costを計上する(`ppc_tariff.py`のDADチェーン処理と対称的な実装)
- `wom/ppc/ppc_runner.py`: GENERIC自動判定に`mom_nodes_chain`の構築を追加
- 回帰確認: 既存ケースはInBound側が単純な1段構成(leaf_in直結)のため、中間チェーンが空リストになり、旧来の1ホップ計算と同じ結果になることを確認

### Step 4: 問題A修正(SKU分割、リスク: 低、Step2・3の後で実施)
- `data/sample/smartx-2027-2029/`の全CSVについて、SmartXProの行を`SmartXPro_CN`/`SmartXPro_IN`に分割する移行スクリプト(`tools/split_smartx_sku.py`、一回限りの移行用)を作成
- 対象CSV: `sc_tree_master.csv`, `sku_master.csv`, `demand_forecast.csv`, `capacity_plan.csv`, `inventory_master.csv`, `node_master.csv`, `route_master.csv`, `edge_cost_master.csv`, `node_cost_master.csv`, `holiday_calendar.csv`, `ppc_supplier_cost.csv`, `ppc_transfer_price_rule.csv`, `ppc_tariff_rule.csv`, `ppc_edge_cost_rule.csv`, `ppc_node_cost_rule.csv`, `ppc_node_profit_zone.csv`, `ppc_profit_zone_rule.csv`, `ppc_market_price.csv`, `lane_assignment.csv`(分割後も地域別DAD割当のために必要かどうかは実装時に精査)
- Step2・3を先に実施する理由: SKU分割後もAssemblyCN系列は`DC_EMEA`/`DC_APAC`という2つの並列DADを持ち続ける(問題C+DはSplit後も残る)ため、Step2の修正が先に完了していないと分割後の検証ができない

### Step 5: 統合動作確認(全ケース)
- Rice/Cookie/ev-europe/ev-thailand/Oil/smartx-2027-2029(新)の6ケース全てで`python -m main`を実行し、trust_events件数・PPC KPI Summary・Node P&Lが期待通りであることを確認
- 特にsmartx-2027-2029については、SmartXPro_CN(EMEA/APAC 2チャネル)・SmartXPro_IN(AMER 1チャネル)それぞれで、地域別の関税・輸送費が正しく計上されることを重点確認

## 7. Expected outputs

- Network tab: Product選択ドロップダウンに`SmartXPro_CN`/`SmartXPro_IN`が追加され、旧`SmartXPro`は表示されなくなること
- PPC KPI Summary: trust_events=0(または既知の意図された値のみ)
- Node P&L: `FoundryTW`/`Buffer_Chip_TW`にそれぞれ独立したコストが計上されること(現状は計上されない)
- Node P&L: `DC_AMER`/`DC_EMEA`/`DC_APAC`それぞれに、対応するchannelのLotのみのコスト・関税が正しく帰属すること(現状は誤って混在または存在しないedgeを参照する)

## 8. Known limitations

- Step2〜3の修正(Lot単位祖先探索方式への置き換え)は`wom/ppc/`のコア計算ロジックに関わるため、Cookie/EV/Apparel/Oilを含む既存全ケースへの回帰リスクがある。Step5で必ず全ケースの再確認を行う
- `mom_nodes_chain`の中間ノードが持つべき原価の性質(単純なnode cost加算か、Tier間で独自のtransfer price/マージンを持つ「内部売買」的な扱いか)は、`ppc_transfer_price_rule.csv`にFoundryTW用のmargin_rate=0.15が既に定義されていることから、後者(2段階の内部transfer price)である可能性がある。Step3の詳細設計時に、単純合算かtransfer price方式か、どちらを採用するか改めて確認が必要
- `lane_assignment.csv`のSmartXPro分割後の要否は未確定(Step4で精査)

## 9. Open questions

1. 問題Bの中間`mom`型ノード(FoundryTW/Buffer_Chip_TW)の原価計上方式(単純node cost合算 vs 2段階transfer price)について、どちらを採用するか
2. 問題C+Dの共通ヘルパー関数の配置場所(`wom/model/sc_tree.py`への追加 vs 新規`wom/ppc/ppc_chain_resolve.py`)について、既存のモジュール境界(Planning LayerとPPC Layerの分離)を踏まえてどちらが適切か
3. Step2の`_resolve_chain`/`_resolve_node_list`のシグネチャ変更(`dict[(product_id, channel_node), list]`への拡張)が、既存の`dict[product_id, list]`形式を使う他のテストコード(`tests/test_ppc_vertical_slice.py`等)に影響しないか、実装前に既存テストを確認する必要がある

---

## Step1〜3(+Problem E)実装・検証結果(2026-07-11)

`wom/model/sc_tree.py`(`walk_ancestor_chain`新設)、`wom/ppc/ppc_forward.py`(InBound多段チェーン対応)、`wom/ppc/ppc_runner.py`(per-Lot chain構築)、`wom/ppc/ppc_tariff.py`・`wom/ppc/ppc_backward.py`(per-Lot chain消費)、`wom/ppc/ppc_engine.py`(mom_nodes_chain配線 + Problem Eのdetect_scenario修正)を実装した。

**回帰確認**(スクラッチ環境、`tests/test_ppc_vertical_slice.py`・`tests/test_ppc_multi_supplier.py`: 42 passed / 1 pre-existing failure(今回の変更と無関係、`mom_to_dad_freight_base`分離を反映していない古いテストの期待値ズレ)):

| ケース | trust_events | margin | 判定 |
|---|---|---|---|
| rice-japan-2027-2028 | 0 | 38.8% | 変化なし ✓ |
| Cookie-jp-2026 | 0 | 16.1% | 変化なし ✓ |
| ev-europe-2026 | 0 | 52.5% | 変化なし ✓ |
| ev-thailand-2026 | 0 | 56.5% | 変化なし ✓ |
| oil-global-2027 | 742(MOM_PROFIT_TOO_LOW) | 35.1% | 変化なし(既知の意図された挙動) ✓ |
| apparel-us-2026 | 0 | 42.4% | 変化なし ✓ |
| smartx-2027-2029(分割前) | 0 | 100%→**90.3%** | **cost=0から脱却、GENERIC分岐に正しく到達** |

smartx-2027-2029は`dad_chain_by_channel`が`('SmartXPro','Retail_AMER'):['DC_AMER']` / `('SmartXPro','Retail_EMEA'):['DC_EMEA']` / `('SmartXPro','Retail_APAC'):['DC_APAC']`と、チャネルごとに正しく単一DADへ解決されることを確認した(修正前は3つ全チャネル共通で`['DC_AMER','DC_EMEA','DC_APAC']`という架空の直列チェーンだった)。`mom_chain_by_leaf`も`('SmartXPro','WaferFab_TW'):['Buffer_Chip_TW','FoundryTW']`と正しく多段InBoundチェーンを検出した。

**残存する既知の論点(Problems A-Eとは別、Step4以降で扱う)**: smartx-2027-2029のrevenue/costが依然として桁違いに大きい(revenue≈4.29×10^14)。この値は修正前後で変化していない(Problems A-Eのいずれとも無関係)ため、`ppc_supplier_cost.csv`等のコスト単価(例: AssemblyCN=$4.5M/lot)と`demand_forecast.csv`の数量単位の間に、他のケースとは異なるスケール前提(1 lot=100台等)の食い違いがある可能性がある。margin=90.3%という数値自体は、これが解消されない限り参考値にとどまる。Step4のSKU分割時、または分割後の最終確認時に別途調査が必要。

## Step4(SKU分割)実装・検証結果(2026-07-11)

`tools/split_smartx_sku.py`(新設、一回限りの移行スクリプト)を作成し、`data/sample/smartx-2027-2029/`の以下19ファイルに対して実行した:

`sc_tree_master.csv` / `sku_master.csv` / `demand_forecast.csv` / `inventory_master.csv` / `capacity_plan.csv` / `node_cost_master.csv` / `ppc_supplier_cost.csv` / `ppc_transfer_price_rule.csv` / `ppc_node_cost_rule.csv` / `ppc_node_profit_zone.csv` / `ppc_profit_zone_rule.csv` / `ppc_market_price.csv` / `ppc_tariff_rule.csv` / `ppc_edge_cost_rule.csv` / `lane_assignment.csv` / `route_master.csv` / `edge_cost_master.csv` / `node_master.csv` / `push_config.csv`

**分割方式**: `SmartXPro`の行を、node_name(またはmarket_node/supplier_node/node_id等の関連node列)がCN系列(`AssemblyCN`/`FoundryTW`/`Buffer_Chip_TW`/`WaferFab_TW`/`DC_EMEA`/`Retail_EMEA`/`DC_APAC`/`Retail_APAC`)かIN系列(`AssemblyIN`/`SensorIN`/`DC_AMER`/`Retail_AMER`)かで`SmartXPro_CN`/`SmartXPro_IN`に振り分けた。共有されていた`SP_SmartXPro`(supply_point)は`SP_SmartXPro_CN`/`SP_SmartXPro_IN`の2つに複製し、各SKUが完全に独立したOutBound rootを持つようにした。`ppc_profit_zone_rule.csv`(role×product_idのレート表)は両SKU分の行を複製。`lane_assignment.csv`のSmartXPro行3件は削除した(分割後は各SKUがMOM 1つのみを持つため、multi-MOM解消用のlane_assignmentが不要になった)。

**Problem Cのデータ側バグも同時に修正**: `ppc_tariff_rule.csv`/`ppc_edge_cost_rule.csv`が実際には存在しない経路(`"AssemblyCN->SP_SmartXPro"`、`"SP_SmartXPro->Retail_AMER"`等、supply_pointを経由するedge_id)をキーにしていたため、`ppc_tariff.py`/`ppc_backward.py`が実際に構築するedge_id(`mom->first_dad`、`last_dad->channel`、例: `"AssemblyCN->DC_EMEA"`、`"DC_EMEA->Retail_EMEA"`)と一致せず、関税・国際輸送費のルックアップが常に空振りしていた(smartx-2027-2029のcost=0症状の一因)。移行スクリプトは旧SP経由の2ホップの金額($を保ったまま)を新しい実edge(mom→dad=国際輸送費+関税、dad→retail=国内ラストマイル)に再配分した。IN側(`AssemblyIN->DC_AMER`)は原産国をCNからINに変更したが、実際のインド発関税率は未調査のため、旧データのCN基準の税率(25%)をそのまま暫定値として引き継いだ(要実データ確認、Open Question追加)。

**動作確認**(スクラッチ環境、`wom-v1r1m7-fix4all_case`のStep1〜3修正済みコード + 分割後CSV、105週分full run):

```
products: ['SmartX', 'SmartXNext', 'SmartXPro_CN', 'SmartXPro_IN']
[PPC Runner] Scenario: GENERIC
  mom={'SmartXPro_CN': 'AssemblyCN', 'SmartXPro_IN': 'AssemblyIN', ...}
  dad_chain_by_channel={..., ('SmartXPro_CN','Retail_EMEA'):['DC_EMEA'], ('SmartXPro_CN','Retail_APAC'):['DC_APAC'],
                              ('SmartXPro_IN','Retail_AMER'):['DC_AMER']}
  mom_chain_by_leaf={..., ('SmartXPro_CN','WaferFab_TW'):['Buffer_Chip_TW','FoundryTW']}

RESULT smartx-2027-2029(分割後, 105週): lots=711  revenue=428,601,926,878,100  cost=45,685,792,078,622
  margin=89.3%  trust_events=105 (TARIFF_SHOCK)
```

Node P&L(`ppc_node_pl_summary.csv`)で、`SmartXPro_CN`と`SmartXPro_IN`が完全に独立した行として現れ、相互混入がないことを確認した:

| node_id | product_id | tariff_base |
|---|---|---|
| DC_EMEA | SmartXPro_CN | 488,532,300,000 (EMEA 7.5%関税が正しく計上) |
| DC_APAC | SmartXPro_CN | 0 (APAC 0%、想定通り) |
| DC_AMER | SmartXPro_IN | 2,449,593,000,000 (AMER 25%関税が正しく計上) |

SmartX/SmartXNext(既存2商品)は分割の影響を受けず、`ppc_node_pl_summary.csv`上で従来通り独立して計上されることを確認した。

**新たに発生したtrust_events=105(全てTARIFF_SHOCK)について**: `ppc_reconcile.py`の`TARIFF_SHOCK_RATIO=0.20`(関税がtransfer priceの20%を超えると発火)による。AMER向けの25%関税が、Problem Cのデータ修正により初めて正しくルックアップされるようになったために新規発火した、意図された・正しい挙動と判断する(修正前は関税自体がedge_id不一致で常に0計上されており、シグナルが隠れていた)。バグではなくSKU固有の実際の関税リスクを正しく可視化した結果と考えられる。

**残存する既知の論点(Problems A-Eとは別、Step5で最終確認)**: revenue規模(≈4.29×10^14)はStep4前後で変化していない。SKU分割・edge_id修正のいずれとも無関係であることが今回のフルラン結果で再確認できた。`ppc_supplier_cost.csv`のコスト単価(例: AssemblyCN=$4.5M/lot)と`demand_forecast.csv`の数量単位の間のスケール前提の食い違いが引き続き濃厚な仮説であり、Step5または別タスクで調査する。

## 10. Open questions(追加)

4. `AssemblyIN->DC_AMER`のtariff_rate=0.25は旧CN基準データをそのまま暫定的に引き継いだ値であり、実際のインド発米国向け関税率の裏付けはない。実データに基づく見直しが必要
5. `push_config.csv`の`SmartXPro,Buffer_Chip_TW,...`行は全て0値(実質no-op)だったため機械的に`SmartXPro_CN`へ付け替えたのみ。PUSH機能を実際に有効化する場合は改めて設計要
6. revenue絶対値スケール(後述、Step4検証中にJPY誤表示バグとは別の要因と確認)の根本原因(`ppc_market_price.csv`/`node_cost_master.csv`の$/lot単価とdemand数量の単位前提の食い違い)は未解決。SmartXPro単体で2年(105週)revenue≈$2.8兆は携帯電話事業として非現実的であり、`1 lot=100台`という前提と実際の単価($9.99M/lot ≒ $99,900/台、sku_master.csvのselling_price=$999/台と100倍ズレ)の整合を取るデータ修正が別途必要

## 11. Step4検証中に新規発見した2件の追加修正(ユーザーのGUI実機確認より)

**(a) PPC Financial KPIがJPY表示になっていた(通貨誤表示バグ)**: smartx-2027-2029には他の全ケース(apparel-us-2026等)と異なり model-local な`ppc_fx_rate.csv`が存在せず、`data/ppc/ppc_fx_rate.csv`(Rice/Cookie向けのJPYベース共通FXテーブル)にフォールバックしていた。smartx-2027-2029の`ppc_supplier_cost.csv`/`ppc_market_price.csv`等は全てUSD建てのデータであるにもかかわらず、base_currency=JPYとして扱われ、USD→JPYレート(≈150)がそのまま金額に掛かる形で表示されていた。**修正**: `data/sample/smartx-2027-2029/ppc_fx_rate.csv`を新規作成(apparel-us-2026と同じ形式、`week,currency,base_currency,rate`で全261週×`USD,USD,1.0`)。再検証の結果、105週revenueが¥428,601,926,878,100(JPY誤表示)→$2,795,625,940,000(USD正表示)に変化し、margin(89.3%)は不変であることを確認した。**なお、この修正はrevenue絶対値の桁を約150分の1に縮小したが、$2.8兆という数字自体は依然として携帯電話事業として非現実的であり、Open Question 6の単価/数量スケール問題は当初、独立して未解決のまま残った**(通貨誤表示バグとは別原因)。→ 後述12章の通り、Open Question 6も同日中に根本解決済み。

**(b) World MapでSmartXPro_CN以外(SmartXPro_IN/SmartX/SmartXNext)のnode/edgeが表示されない**: `node_master.csv`(11行)が`sc_tree_master.csv`の実際のnode_name(アンダースコア区切り、地域サフィックス付き)をほとんど網羅しておらず、たまたま`AssemblyCN`/`FoundryTW`のみ名前が完全一致していたために発生していた既存ギャップ(4製品共通、SKU分割由来の新規バグではない)。**修正**: `node_master.csv`に32行を追加し、4製品(SmartX/SmartXNext/SmartXPro_CN/SmartXPro_IN)の全node(DC/Retail/Assembly/Foundry/WaferFab/SensorIN/Supply Point)の緯度経度・node_type(`mother_plant`/`sku_supplier`/`region_dc`/`marketing`/`supply_point`)を補完した。sc_tree_master.csvとnode_master.csvの突合で未解決参照が0件であることをプログラムで確認済み。

**(c) PPC Financial KPIタブの"PPC KPI Summary"パネルが隣接する"Profit Zone Breakdown"パネルと文字が重なる(全ケース共通のGUI描画バグ、smartx固有ではない)**: `wom/ppc/ppc_cockpit_app.py`の`_draw_kpi_text()`が`ax.text()`をclip_on未指定(デフォルトFalse)で描画しており、値の文字列が長い場合にsubplot境界を越えて隣のsubplotへ視覚的にはみ出していた。USD化により金額の桁数が増えたこと(例: `1631889.54M USD`)で顕在化した。**修正**: `_fmt()`に`B`(billion)/`T`(trillion)の単位を追加して数値表示を短縮、KPIパネルのフォントサイズを縮小(タイトル13→11pt、値10→8.5pt等)、ラベルを短縮(`Total Cost`→`Total Cost`のまま等幅を詰める)、`ax.text()`全箇所に`clip_on=True`を追加して、たとえ文字列が長くても自パネルの境界内に収まる(はみ出す場合は切り詰められる)よう修正した。

## 12. Open Question 6 解決: revenue/costスケール問題の根本修正(2026-07-11、オーナー承認済み)

**根本原因の特定**: `sc_tree_master.csv`の`cpu_size`列は全ノードで`1`(=「1 lot = 1台」)である一方、`ppc_market_price.csv`等の$/lot単価は`sku_master.csv`の正しい単価(例: SmartXPro_IN/AMER = $999/台)のちょうど**10,000倍**で入力されていた(9,990,000 ÷ 999 = 10,000。SmartX/SmartXNext含む全9行のmarket_priceで同一の10,000倍を確認)。`node_cost_master.csv`のコメント欄は「$999/unit x 100 units/lot」と書いていたが、実際の入力値は100倍ではなく10,000倍分ズレており、コメント自体も誤りだった。

**オーナー判断**: 選択肢(A: cpu_sizeを1万に変更)ではなく選択肢(B: 価格データを10,000分の1に修正)を採用。cpu_size=1のまま(週次需要の解像度を保持)、価格側をsku_master.csvの正しい単価に合わせる方針。

**修正**: `tools/fix_smartx_price_scale.py`(新規、一回限りの移行スクリプト)を作成し、SmartX/SmartXNext/SmartXPro_CN/SmartXPro_IN の4製品全てに対して以下5ファイルの$金額列を1/10,000に一括スケーリング:
`ppc_market_price.csv`(market_price)、`ppc_supplier_cost.csv`(purchase_price)、`ppc_node_cost_rule.csv`(fixed_amount)、`ppc_edge_cost_rule.csv`(fixed_amount)、`node_cost_master.csv`(selling_price_per_lot/unit_cost_per_lot)。`sku_master.csv`(既に正しい単価)・`ppc_tariff_rule.csv`/`ppc_profit_zone_rule.csv`/`ppc_transfer_price_rule.csv`(いずれも%レートで金額列ではない)・`demand_forecast.csv`/`capacity_plan.csv`/`inventory_master.csv`(数量であり金額ではない)は対象外。

なお、この根本原因(価格データの生成時に10,000倍のスケール誤りが混入)は分割前の単一`SmartXPro`にも、既存のSmartX/SmartXNextにも同様に存在していたケース全体の問題であり、SKU分割(Step4)由来の新規バグではない。

**検証結果**(スクラッチ環境、105週フルラン): revenue $2,795,625,940,000 → **$279,562,594**(ちょうど1/10,000)、margin=89.3%(不変、スケールのみ変化)。sku_master.csvの単価($999/$1099/$949等)とppc_market_price.csvの新しいmarket_price値が完全一致することを確認。他6ケース(Rice/Cookie/ev-europe/ev-thailand/Oil/apparel-us-2026)のデータファイルは本修正で一切変更されていないことをディレクトリ更新時刻ベースで確認済み。

これによりOpen Question 6は解決済みとする。

## 13. Step5: 全7ケース最終統合確認(2026-07-11)

スクラッチ環境で全7ケース(105週)を通し実行し、Step1〜4 + Open Question 6の全修正を反映した最終状態でのKPIを確認した。

| ケース | lots | revenue | margin | trust_events | 判定 |
|---|---|---|---|---|---|
| rice-japan-2027-2028 | 832 | 1,222,428,600 | 38.8% | 0 | 変化なし ✓ |
| Cookie-jp-2026 | 624 | 4,259,700,000 | 16.1% | 0 | 変化なし ✓ |
| ev-europe-2026 | 526 | 366,508,230,000 | 52.5% | 0 | 変化なし ✓(ユーザー実機確認済み) |
| ev-thailand-2026 | 624 | 319,119,580,000 | 56.5% | 0 | 変化なし ✓ |
| oil-global-2027 | 1,408 | 1,649,727,940,180 | 35.1% | 742 (MOM_PROFIT_TOO_LOW) | 変化なし(既知の意図された挙動) ✓ |
| apparel-us-2026 | 444 | 17,493,784 | 42.4% | 0 | 変化なし ✓ |
| smartx-2027-2029(全修正後) | 711 | 279,562,594 (USD) | 89.3% | 105 (TARIFF_SHOCK) | **cost=0から脱却、SKU分割・関税ルーティング・通貨・スケール全て正常** |

Rice〜apparel-us-2026の6ケースは、smartx-2027-2029に対するStep1〜4・Open Question 6のいずれの修正によっても一切変化がないことを確認した(ppc_cockpit_app.pyのGUI描画修正のみ全ケース共通コードに触れているが、これはKPI計算後の表示層のみの変更であり数値には影響しない)。

smartx-2027-2029のtrust_events=105(TARIFF_SHOCK)は、AMER向け25%関税がProblem C修正により正しくルックアップされるようになったことで発火する、意図された・正しいシグナルである(4.5節参照)。

**Step1〜5、全工程完了。** 実装内容は本レター記載の通り、ユーザー側でのGUI最終確認・git commit/pushを残すのみ。

## 14. Trust Event Type別集計+ドリルダウンパネル追加(2026-07-11、オーナー承認済み)

Step5完了後、trust eventの解釈方法についてオーナーと議論する中で、「5種類のtrust eventそれぞれの発生件数と評価KPIを確認するのに画面を行き来する必要がある」という運用上のギャップが判明した。調査の結果、`ppc_kpi.py`の`build_kpi_summary()`は集計件数(`trust_event_count`)と重複排除済みの種類リスト(`trust_event_types`)のみを保持しており、種類別の件数内訳はGUIのどこにも存在しないことを確認した(唯一の詳細データソースは、GUI外でのみアクセス可能な`ppc_lot_reconciliation.csv`の`trust_events_fired`列)。オーナーの承認を得て、PPC Financial KPIタブに以下を追加した。

**実装内容**(`wom/ppc/ppc_cockpit_app.py`):
- `TRUST_EVENT_TYPES`/`TRUST_EVENT_COLORS`/`TRUST_EVENT_LABELS`: `ppc_reconcile.py`の5種類のtrust event typeと対応する表示ラベル・色を定義
- `_count_trust_events()`: `trust_events_fired`列(`|`区切り文字列)を種類別に集計するヘルパー
- `_draw_trust_breakdown()`: 5種類×件数の横棒グラフパネル。クリック用にbar patchと event_type のマッピングを返す
- gridspecを3行→4行に拡張(`ax_trust = gs[3, :]`で全幅)、Figure高さを10→12inchに拡大。既存9パネルは変更なし、新パネルを追加のみ
- `_on_canvas_click()` + `_show_drilldown()`: `canvas.mpl_connect("button_press_event", ...)`でクリックイベントを購読し、クリックされたbarのevent_typeで現在のフィルタ済み`ppc_lot_reconciliation`データを絞り込み、Tkinter Toplevelウィンドウ(Treeview表)でLot ID/Week/Node/Product/Gross Profit/Margin%/Events Firedを一覧表示。件数0のbarはクリックしても何も開かない

**検証**(サンドボックスにtkinterがないため、GUI自体はユーザー側実機確認が必要。それ以外の全ロジックは検証済み):
- `ast.parse`でファイル全体の構文を確認(1011行)
- 実データ(`output/ppc/ppc_lot_reconciliation.csv`、298 lots)で`_count_trust_events()`を実行し、`MOM_PROFIT_TOO_LOW: 221`件・他4種は0件と算出。pandasの`str.contains()`によるクロスチェックと一致を確認
- matplotlib Agg backendで横棒グラフ描画ロジック(5 bars生成)を実行しエラーなしを確認
- ドリルダウンのフィルタロジック(`event_type in trust_events_fired.split("|")`)を実データに適用し、221件のMOM_PROFIT_TOO_LOW対象lot(lot_id/week/channel_node/product_id/gross_profit_base等)が正しく抽出されることを確認

**未検証(ユーザー側での実機確認が必要)**: Tkinterの実描画(パネルレイアウト、bar上でのクリック判定、Toplevelウィンドウの見た目)。

### 14.1 追加修正: KPI Summaryのtrust event badgeとBreakdownパネルの集計範囲不一致(2026-07-11、オーナー承認済み)

上記パネル追加後、ユーザーがOil caseの画面で確認したところ、左上「PPC KPI Summary」パネルのbadge(742 trust events)と、新設のBreakdownパネルの合計(102)が一致しない現象が見つかった。

**原因調査結果**: badgeは`ppc_kpi_summary.json`の`trust_event_count`(=742、そのケースの全期間・全SKU・全Channelを対象にエンジン実行時点で1回だけ計算された固定値)をそのまま表示していた。一方、同じKPI Summaryパネル内のRevenue/Total Cost/Gross Profit/Gross Margin、およびBreakdownパネルはいずれも`rec_filtered`(サイドバーのStart/End Week・SKU・Channelフィルタを反映した絞り込みデータ)から都度計算していた。つまりbadgeだけが「フィルタ非連動」という、本機能追加以前から存在した設計上の不整合であり、今回Breakdownパネルという比較対象ができたことで表面化した。

**修正**: `_draw_kpi_text()`のbadge計算を、`kpi["trust_event_count"]`固定値ではなく`rec_filtered`から`_count_trust_events()`で都度算出する方式に変更(`trust_events_fired`列が無い旧output/ppc/との後方互換フォールバックは維持)。これによりbadgeとBreakdownパネルの合計が常に一致するようになった。

**検証**: 実データ(`output/ppc/ppc_lot_reconciliation.csv`)で新ロジックを実行し、badge値とBreakdownパネル合計が221件で一致することを確認(両者とも同一の`_count_trust_events()`関数を使うため、構造的に必ず一致する)。

## 実装への申し送り

- 出力先: `data/sample/smartx-2027-2029/`(Step4のSKU分割済み・Open Q6のスケール修正済み)、`tools/split_smartx_sku.py`・`tools/fix_smartx_price_scale.py`(新設・一回限りの移行スクリプト)、`wom/ppc/ppc_runner.py`・`ppc_tariff.py`・`ppc_backward.py`・`ppc_forward.py`・`wom/model/sc_tree.py`(Step1〜3のエンジン修正)、`wom/ppc/ppc_engine.py`(Problem E修正)、`wom/ppc/ppc_cockpit_app.py`(KPIパネル重なり修正+Trust Event Type別集計/ドリルダウンパネル追加、全ケース共通)、`data/sample/smartx-2027-2029/ppc_fx_rate.csv`(新設、USD建て)、`data/sample/smartx-2027-2029/node_master.csv`(World Map表示補完)
- 実装順序は本レター6章の通り(Step1→2→3→4→5)。Step1〜5 + Open Question 6 + Trust Event Type別集計/ドリルダウンパネルまで完了・検証済み
- 残タスクはユーザー側でのGUI実機確認(特にTrust Event Type別集計パネルのレイアウト・クリック動作)・git commit/pushのみ
- 本レターの内容についてオーナー確認後、Step1から着手した
