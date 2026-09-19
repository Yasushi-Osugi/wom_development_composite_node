# WOM Composite Node Architecture 基本設計のドラフトメモ

## 1. 文書の位置づけ

本書は、WOMに以前から実装されてきたFactory、Assembly、Stocker、Buffering Stock、Picking、Kitting、Push／Pull制御などの構造を、今後正式な基本設計へ整理するための検討メモである。

現段階では、設計を確定する文書ではない。特に、`node_character`、要素別capacity、新しいCSV列、PSIエンジンの条件分岐を実装する根拠として、本書を単独で使用してはならない。

本書の目的は次のとおりである。

- ここまでの検討経緯と問題意識を記録する
- 既存実装に内在する構造を言語化する
- 確認済み事実、設計仮説、未決事項を区別する
- core変更前に必要な調査と設計判断を明らかにする
- 後続のAIや開発者が、同じ概念を異なる意味で使用することを防ぐ

本書では、以下の5原則を上位の出発点とする。

1. 物理lotはForwardに動く
2. 補充指示はBackwardに動く
3. Market PullとBuffer Pullは別の制御ループである
4. DBRとKanbanはBuffer Pullを実現する異なるPolicyである
5. FactoryやBufferは、複数のPSIとEventからなるComposite Nodeとして表現できる

---

## 2. 検討の発端

WOMのS3 Runにおいて、工場閉鎖週の`cap_hard`とPSI系列の関係を確認した際、push型MOMノードの`P`が生産量なのか入庫量なのかについて混乱が生じた。

当初は、`cap_hard=0.1`の週に`P=1000`であるため、能力制約を無視して1,000 lotを生産していると解釈された。しかし週次状態を実測すると、対象ノードでは以下の状態だった。

```text
P = 1000    上流からの入庫
S = 0       当週の処理または実出荷
I = 1000    当週に処理されず残った在庫
```

したがって、閉鎖週の処理量はすでに0であり、処理能力自体は守られていた。問題の一部は、能力集計の結論ではなく、S3の図が`P`とcapacityを比較していたため、能力超過のように見えたことにあった。

この事例から、次の問題が明らかになった。

- `P/S/I/CO`の意味がノードや制御方式によって変わる
- `plan_mode="push"`が物理的役割と計画方式の複数の意味を持っている
- capacityが何を拘束するか宣言されていない
- Market PullとBuffer Pullが設計上明確に分離されていない
- FactoryやBufferを単一ノードとして扱うと、複数の物理操作が一つのPSIへ混在する
- Demand Layerの未充足とPhysical Layerの在庫を二者択一で扱う危険がある

この問題は、局所的な表示修正だけでなく、WOMが以前から内包してきた構造を正式なアーキテクチャとして言語化する必要性を示している。

---

## 3. 現時点で確認している重要な認識

### 3.1 PSI記号は業務上の表示名とエンジン上の状態を分けて考える

WOMの各ノードは、基本的に`P/S/I/CO`のlot listを持つ。しかし、文字の業務的な読み方はノードによって異なる。

| ノードの例 | P | I | S |
|---|---|---|---|
| Factory finished goods | Production completion | Finished goods inventory | Shipment |
| Raw material stocker | Purchase／Receipt | Material inventory | Picking／Issue |
| Warehouse | Receipt | Storage inventory | Shipment |
| Sales location | Purchase／Receipt | Store inventory | Sales |

この違いを、単一の`node_character`から直接エンジン分岐させるのは危険である。FactoryやWarehouseは、receive、store、transform、shipなど複数の能力を同時に持つためである。

### 3.2 物理状態と需要充足状態は異なる

大杉の基本認識は次のとおりである。

- 本来の需要週または出荷週がまだ来ていないlotはInventoryとして扱う
- 本来の需要週または出荷週を過ぎても供給できていないlotはCOとして扱う

ただし、同一の状況について、Physical LayerとDemand Layerでは異なる状態が同時に成立し得る。

例として、工場閉鎖により出荷できなかったlotは、工場側では物理在庫`I`として存在し、下流需要側では未充足`CO`として認識される場合がある。

したがって、「溢れたlotをIへ移すかCOへ移すか」という二者択一ではなく、以下を別々に記録する必要がある。

- 物理lotがどこに存在するか
- どの需要または注文が未充足か
- 物理lotと需要lotがどの時点でbindされているか

### 3.3 物理lotと補充要求は別物である

物理lotは上流から下流へForwardに移動する。一方、Market Pull、Kanban、DBR Ropeなどの補充・投入要求は、下流から上流へBackwardに伝播する。

Backwardに動くものは物理lotではなく、原則として次のいずれかである。

- Demand requirement
- Pull request
- Replenishment request
- Reservation／Binding request
- Production release instruction

計画上の要求lotと実在する物理lotを同一視しないことが重要である。

---

## 4. アーキテクチャ上、分離すべき概念

単一の`node_character`や`plan_mode`に意味を集中させず、少なくとも次の概念を分離する。

| 概念 | 例 | 主な目的 |
|---|---|---|
| Physical Role | factory、warehouse、store、supplier | 人間とGUIが施設を理解する |
| Node Capabilities | receive、transform、store、pick、ship、sell | ノードで可能な物理操作を示す |
| Planning Role | push、pull、decoupling | 需給計画と伝播方法を示す |
| Control Policy | market_pull、kanban、dbr_rope、reorder_point | 指示を生成する規則を示す |
| Constraint Scope | processing、receiving、storage、shipping、transport | capacityが拘束する操作を示す |
| Event | arrival、shipment、inventory_move、pull_request、bind、transform | 状態変化を表す |
| PSI State | P、S、I、COのlot lists | 特定段階の数量・lot状態を表す |

`node_character`という名称を使用する場合でも、それはFacility Templateまたは人間向け分類として位置づけ、エンジン上のすべての挙動を一つの列から導出しない。

---

## 5. Factory Composite Node

### 5.1 基本構造

Factoryは、単一のPSIノードではなく、少なくとも二つのPSIと、その間のTransformation EventからなるComposite Nodeとして表現できる。

```text
Inbound Stocker PSI
    P_stock : Receipt／Purchase
    I_stock : Material／WIP inventory
    S_stock : Picking／Issue to production
          |
          v
Picking／Kitting／Transformation Event
          |
          v
Production PSI
    P_production : Production completion
    I_production : Finished goods inventory
    S_production : Shipment
```

### 5.2 Transformationの意味

`transform`は、PSIの箱そのものではなく、二つのPSIを接続するEventとして扱う。

```text
S_stock(w)
  -- BOM／Yield／Lead Time／Processing Capacity -->
P_production(w + LT)
```

`P_production`はTransformationの開始ではなく、原則としてTransformationが完了した結果である。

加工リードタイムや工程内仕掛を表現する必要がある場合は、Transformation開始、WIP状態、Transformation完了を別イベントまたは別状態として扱う必要がある。

### 5.3 既存実装との関係

SmartPhone完成組立モデルに実装されている以下の関係は、Factory Composite Nodeの先行実装または参照モデルと考えられる。

```text
Stocker Node
  -> Picking Event Control
  -> Kitting Control
  -> Assembly Node
```

今後Factory Templateを一般化する場合、抽象的な分類から新規実装するのではなく、この既存実装のLot ID遷移、BOM関係、能力制約、週次タイミングを正典化し、参照モデルとして利用する。

### 5.4 Factory Templateの候補

Supply Chain Network Construction Kitでは、Factoryアイコンを配置すると、内部的に次の構造を生成する方式が考えられる。

```text
Factory Template
├─ Inbound Stocker PSI
├─ Receiving Event
├─ Picking／Kitting Event
├─ Transformation／Assembly Event
└─ Finished Goods PSI
```

GUI上では一つのFactoryとして表示し、必要に応じて内部のComposite構造を展開表示する。

---

## 6. Buffer Pull Composite Node

### 6.1 基本構造

TWの半導体buffering stockのようなノードは、単なるWarehouseではなく、物理在庫と補充制御を組み合わせたComposite Nodeである可能性がある。

```text
Upstream shipment
      |
      v
Buffer PSI
    P_buffer : Arrival／Receipt
    I_buffer : Buffer inventory
    S_buffer : Picking／Withdrawal
      |
      v
Downstream process／Assembly

S_buffer／Withdrawal
      |
      v
Pull Request／Replenishment Signal
      |
      v
Upstream release instruction
```

Bufferから後工程へ払い出されたことを契機として、上流へ補充指示を戻す。このBackward方向の指示は、物理lotの逆流ではない。

### 6.2 Buffer PullのCanonical Event候補

Buffer Pullは、既存のCanonical Event構想を利用して次のようなEvent Chainで表現できる。

```text
inventory_move／withdrawal
  -> pull_request
  -> upstream allocation
  -> bind
  -> shipment
  -> arrival
```

`pull_request`は物理lotではなく、補充すべき品目、数量、要求時期、補充先、対応する需要または消費を表すControl Layerのイベントである。

### 6.3 Buffer_Chip_TWに関する現時点の扱い

`Buffer_Chip_TW`は名前上はBufferである一方、既存データでは`node_type=mom`、decoupling設定、capacity設定などを持つ。この状態だけから「誤ってMOMに分類された倉庫」と断定してはならない。

考えられる仮説には以下がある。

- 単純な保管倉庫
- 後工程引きを制御するBuffer Pull Node
- 下流工程の能力を代理保持する論理ノード
- DBRのBufferまたはRope制御点
- Kanban補充の起点
- データ設定上の誤分類または不足

正式分類前に、以下を追跡する必要がある。

1. `P_buffer`をどの処理が書くか
2. `S_buffer`を何が起動するか
3. 上流への補充指示をどの処理が生成するか
4. `cap_hard=1350`がどの実数量と一致するか
5. Picking／Kitting／Assemblyとの接続関係
6. Lot IDがいつ要求lotまたは上流物理lotへbindされるか

---

## 7. OutboundとInboundのPush／Pull

### 7.1 Outbound側

Outbound側には、少なくとも次の制御方式がある。

- Push：需要予測や計画に基づく供給・配置
- Market Pull：市場需要を起点として上流へ要求を伝播

Market Pullでは、市場需要からBackwardに必要量を配置し、物理供給はForwardに実行する。

### 7.2 Inbound側

Inbound側には、少なくとも次の制御方式がある。

- Push：上流計画に基づく部材投入・補給
- Buffer Pull：Buffer消費を起点とする補充

Buffer Pullでは、後工程の消費またはBuffer状態を起点として補充要求をBackwardに伝え、物理部材をForwardに補給する。

### 7.3 一つのノードが複数Policyを持つ可能性

同一Factoryでも、以下の組み合わせがあり得る。

```text
outbound_demand_policy       = market_pull
inbound_replenishment_policy = kanban
production_release_policy    = dbr_rope
long_lead_material_policy    = forecast_push
```

したがって、単一の`plan_mode=push/pull`だけで施設全体の挙動を表現することには限界がある。

---

## 8. DBRとKanban

### 8.1 Kanban

Kanbanでは、後工程の消費、空容器、Kanbanカードなどを契機として、消費量に対応する補充要求を生成する。

単純な消費補充型では、概念的に次の関係となる。

```text
Replenishment Request(w) = Withdrawal(w)
```

ただし、カード枚数、容器量、最小補充単位、補充LTを別途考慮する。

### 8.2 Reorder Point／Min-Max

```text
Inventory Position
  = On Hand + On Order - Backorder

Replenishment Request
  = max(0, Target - Inventory Position)
```

### 8.3 DBR

DBRでは以下を分ける。

| DBR要素 | WOM上の意味候補 |
|---|---|
| Drum | ボトルネック工程の能力計画 |
| Buffer | Drum前または出荷前の時間・在庫Buffer |
| Rope | Drumの予定とBuffer状態に基づく上流投入許可 |

概念的には、上流への投入許可を次のように扱う。

```text
Release(w) = f(Drum Schedule, Buffer Status, Lead Time)
```

DBRとKanbanはいずれもBuffer Pull系統に属するが、補充または投入量を決定するPolicyが異なる。

---

## 9. Capacityの考え方

### 9.1 現行課題

現行WOMでは、ノード×週に`cap_hard`と`cap_soft`があり、実装上どのPSI要素または物理操作を拘束するかが十分に宣言されていない。

また、`P`の意味がReceipt、Production Completionなどノードによって異なるため、`P_cap/I_cap/S_cap`を直ちに導入すると、PSI文字の意味混在をそのままcapacityへ持ち込む危険がある。

### 9.2 物理操作に基づくCapacity候補

| Capacity | 拘束対象 |
|---|---|
| Receiving Capacity | 入庫、荷下ろし、検収 |
| Processing Capacity | 生産、加工、組立、キッティング |
| Storage Capacity | 在庫保管量、置場 |
| Picking Capacity | 部材払出し、ピッキング |
| Shipping Capacity | 出荷、積込み |
| Transport Capacity | Edge上の輸送 |

将来のConstraint定義では、以下を明示する案がある。

```text
constraint_id
constraint_type
target_node_or_edge
hard_or_soft
unit
calendar
lot_selector
measurement_event
```

### 9.3 Composite Factoryにおける対応

| 操作 | Capacity適用候補 |
|---|---|
| `P_stock`への受入れ | Receiving Capacity |
| `I_stock` | Raw Material Storage Capacity |
| `S_stock`／Picking | Picking Capacity |
| Transformation Event | Processing Capacity |
| `I_production` | Finished Goods Storage Capacity |
| `S_production` | Shipping Capacity |

生産能力は、`P`リストを事後的に切り詰めるより、Transformation Eventが当週処理できる入力lot数として制約する方が、物理的意味を明確にできる可能性がある。

---

## 10. Lot操作の基本不変条件候補

本節は今後の正式設計で検証・確定する。

### 10.1 物理lotの一意性

同一物理lotは、同一時点で複数の物理場所または物理状態に重複して存在しない。

```text
Physical location count per Lot ID = 1
```

BOM分解、組立、分割、統合がある場合は、親子Lot ID関係を記録する。

### 10.2 Stocker払出しと工程投入の一致

```text
S_stock(w) = Input_to_transformation(w)
```

Pickingしたが工程へ入らないlot、またはPickingせずに工程へ現れるlotを許容しない。待機状態が必要な場合は、その状態を明示する。

### 10.3 生産完了とリードタイム

```text
P_production(w + LT)
  = transform(S_stock(w), BOM, Yield)
```

### 10.4 能力制約

```text
Input_to_transformation(w) <= Processing Capacity(w)
```

能力不足で処理できないlotを削除しない。物理的待機場所、需要側の未充足、後追い処理規則を分けて記録する。

### 10.5 Demand Due Week

Demand Layerでは、Lot IDまたは需要要求が本来の出荷週を過ぎたかどうかに基づいてCOを判定する。

Physical Layerの在庫状態とDemand LayerのCO状態は、必要に応じて同時に成立する。

### 10.6 Backward信号とPhysical Lotの区別

Backwardに伝播する要求を、物理lot移動として記録しない。少なくともEvent Typeまたは状態により、次を区別する。

- Planned requirement
- Pull request
- Reserved／bound lot
- Physical lot
- Shipped lot
- Arrived lot

---

## 11. S3 Capacity表示に関する暫定対応

現行S3のcapacity chartについては、push型処理ノードで`P`を表示すると、入庫量と処理能力を比較することになり、誤解を生む場合がある。

暫定対応として、現行仕様においてcapacityが意味する処理系列を表示する案は有効である。ただし、この修正は表示側に限定する。

暫定対応の条件は次のとおりである。

- Forward Plannerのlot操作を変更しない
- CSV schemaを変更しない
- `node_character`をcoreの分岐条件として追加しない
- golden snapshotを変更しない
- 表示系列が処理量、実出荷量、入庫量のいずれかを明示する
- 暫定的な`series_kind`を永続的な正典属性へ昇格させない

将来、Constraint Scopeが正式に定義された場合、表示系列はConstraintから導出する。

---

## 12. Supply Chain Network Construction Kitへの示唆

将来、GUI上でFactory、Warehouse、Sales、Transportなどのアイコンをドラッグ&ドロップしてSupply Chain Networkを構築する場合、アイコンは単純な一ノードではなく、Facility Templateとして扱うことが考えられる。

例を以下に示す。

```text
Factory Template
  capabilities = receive, transform, store, ship
  internal structure = stocker PSI + transform event + finished goods PSI

Warehouse Template
  capabilities = receive, store, pick, ship
  internal structure = receiving PSI + storage + picking event + shipping PSI

Sales Template
  capabilities = receive, store, sell
  internal structure = receiving PSI + store inventory + sales event

Buffer Pull Template
  capabilities = receive, store, withdraw, request_replenishment
  internal structure = buffer PSI + withdrawal event + pull request controller
```

テンプレートは初期値を提供するが、Facilityの全挙動を単一のcharacter列で固定しない。必要に応じてCapabilities、Policies、Constraintsを追加・変更できる構造とする。

---

## 13. 設計上の危険と禁止事項

正式設計が完了するまで、以下を避ける。

1. `node_character`だけでP/S/Iの意味とcapacity適用先を自動決定する
2. `node_type=mom`を一律にFactoryとみなす
3. 名前に`Buffer`が含まれることだけでWarehouseへ再分類する
4. `plan_mode=push`を物理ノード種別として利用する
5. `P`を全ノード共通でProductionと解釈する
6. Backwardに伝播する補充要求を物理lotの逆移動として扱う
7. Physical InventoryとDemand COを排他的な状態として扱う
8. `cap_hard`を根拠なくP、I、Sのいずれかへ一律適用する
9. 1モデルの例外だけを根拠に18モデルのcoreを変更する
10. 調査文書をCode実装の承認済み仕様として扱う

---

## 14. 推奨する設計・検証手順

### Step 1. 現行coreの保護

現行`wom-v1r4m0`を基準として保持し、Composite Node／Capacity Ontologyの実験は別ブランチまたは既定OFFのfeature flagで行う。

### Step 2. PSI Lot操作の正典化

既存コードとモデルを読み、以下を文書化する。

- 各ノードでP/S/I/COへ誰が書き込むか
- Lot IDの生成、bind、移動、分割、統合
- Backward Planning上の要求lotとPhysical Lotの違い
- Demand Due WeekとCO判定
- Inventoryの物理的位置

### Step 3. 既存モデルの意味監査

18モデルの全ノードについて、少なくとも以下を一覧化する。

```text
node_type
plan_mode
inbound／outbound
decoupling
parent／children
P writer
S writer
capacity source
cost rules
physical role hypothesis
evidence
confidence
```

事実と推測を別の列にする。

### Step 4. 参照モデルの詳細化

以下を参照モデルとする。

- SmartPhone Assembly：Composite Factory
- TW Buffering Stock：Composite Buffer Pull

両モデルについて、週次Lot ID traceとEvent Chainを作成する。

### Step 5. Read-only classifier／Shadow evaluation

エンジンの挙動を変えずに、推定Physical Role、Capabilities、Control Policy、Constraint Scopeと、その根拠を出力する診断機能を検討する。

さらに、各capacity解釈をshadow計算し、既存PSIを変更せず超過週と影響量だけを比較する。

### Step 6. 基本設計の判断

調査結果をもとに、以下の採否を判断する。

- Facility Template
- Node Capabilities
- Composite Node
- Canonical Event拡張
- Control Policy分離
- Constraint Scope schema
- 既存`plan_mode`との互換方針

### Step 7. 限定的な試験実装

1モデルまたは1Composite Templateに限定し、既定OFFで試験する。Lot conservation、golden、PPC、GUI、期末在庫・COを検証した後に適用範囲を拡大する。

---

## 15. 未決事項

以下は現時点で未確定である。

1. `node_character`という名称を採用するか
2. Physical Roleを単一値にするか、Capabilitiesの集合を正典にするか
3. Existing `node_type`とPhysical Roleの対応関係
4. Buffer_Chip_TWの正確な業務的役割
5. `cap_hard=1350`の意味
6. Processing CapacityをTransformation Eventへ移すか
7. Receiving、Storage、Picking、Shipping Capacityをいつ導入するか
8. Backward PlannerとForward Plannerの週オフセットの意味
9. Kanbanカード、DBR Rope、Reorder Pointの共通interface
10. Pull RequestとPhysical LotのLot IDまたは参照IDの関係
11. 工程内WIPを別PSIまたはEvent stateとして持つか
12. Composite NodeをGUI上で展開表示する方法
13. Inventory holding cost、WIP cost、terminal inventoryをS4でどう評価するか
14. 中間ノードCOと顧客未充足COをどう区別するか

---

## 16. 基本設計へ昇格するためのGate

本メモを正式な基本設計へ昇格する前に、少なくとも次を満たす。

- SmartPhone AssemblyのLot／Event traceが説明できる
- TW BufferingのLot／Pull Signal traceが説明できる
- Market PullとBuffer Pullの両方を同じ用語体系で表現できる
- Physical LotとPlanning Requirementが区別できる
- Physical InventoryとDemand COが異なるLayerとして説明できる
- Factory Composite NodeのBOM、Yield、LT、Capacityが説明できる
- KanbanとDBRのPolicy差を表現できる
- 既存18モデルの主要ノードが分類不能にならない
- 既存coreとの互換方針が定義されている
- Code実装前に独立した反証レビューを受けている
- 大杉が基本設計への昇格を承認している

---

## 17. 現時点のまとめ

今回の検討で得られた中心的な認識は以下である。

```text
Physical Lot Flow          : Forward
Demand／Replenishment Signal: Backward
Market Pull                : 市場需要を起点とするOutbound制御
Buffer Pull                : 後工程消費を起点とするInbound制御
Kanban／DBR                : Buffer Pullの異なるPolicy
Factory／Buffer            : 複数PSIとEventによるComposite Node
Capacity                   : PSI文字ではなく物理操作を拘束するConstraint
```

この整理は、WOMへまったく新しい構造を外部から追加するものではない。SmartPhone Assembly、TW Buffering、Canonical Event、Push／Pull Planningなど、WOMが以前から個別に実装してきた構造を発見し、共通の言葉と境界を与える作業である。

今後もモデル追加や実測を通じて定義は改良される。本段階で重要なのは、分類体系を一度で完成させることではなく、確定事項、有力な仮説、未解決事項を区別し、core変更より先に意味と不変条件を整えることである。

---

## 付録 A 用語候補

| 用語 | 暫定定義 |
|---|---|
| Atomic PSI Node | 一つのP/S/I/CO lot list構造を持つ最小状態単位 |
| Composite Node | 複数のAtomic PSI NodeとEventから構成される施設モデル |
| Facility Template | GUI上のFactory、Warehouse等からComposite構造を生成する雛形 |
| Capability | receive、transform、store、pick、ship、sell等の可能な操作 |
| Policy | Push、Market Pull、Kanban、DBR等の制御規則 |
| Constraint Scope | processing、receiving、storage等、capacityが拘束する物理操作 |
| Pull Request | 下流消費または需要に基づく上流への補充要求 |
| Physical Lot | 現実の物理的な製品・部材に対応するlot |
| Planned Requirement | Backward Planning上の必要量・必要時期を表す要求 |
| Bind | 要求と供給可能な物理lotを対応付けるEvent |

## 付録 B 文書ステータス

```text
Status        : DRAFT MEMO
Authority     : Non-normative
Implementation: Not authorized by this document
Scope         : Composite Node／Flow／Control／Capacity semantics
Next Review   : SmartPhone AssemblyおよびTW Bufferingの実装trace確認後
```
