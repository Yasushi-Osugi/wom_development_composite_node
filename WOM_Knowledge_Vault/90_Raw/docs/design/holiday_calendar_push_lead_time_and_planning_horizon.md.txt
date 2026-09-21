# Holiday Calendar・先行生産週・Planning Horizon 設計

- **Document Status**: Draft for Design Review
- **Target Release**: WOM v1r2m0 以降
- **Target Scenario**: `data/sample/soysauce-us-2027`
- **Recommended Repository Path**: `docs/design/holiday_calendar_push_lead_time_and_planning_horizon.md`
- **Source**: 2026-07-27 chatlog「先行生産と計画期間の設定について」

---

## 1. 目的

本設計は、WOM の PSI Planning における次の3項目を、相互に混同しない形で定義する。

1. **休日カレンダーによる工場休業・能力変更**
2. **`push_lead_time_weeks` による供給側の先行計画**
3. **Planning Horizon の前倒しによる Warm-up Period の確保**

特に、醤油モデル `soysauce-us-2027` で発生している次の事象を対象とする。

- Holiday Calendar Plugin は読み込まれているが、PSI Graph に休業影響が現れない
- `capacity=0` が「能力ゼロ」ではなく「能力未設定＝無制約」と解釈される
- DC node の初期 CO を解消するために、`push_lead_time_weeks` を短縮すべきか、Planning Horizon を前倒しすべきかが曖昧
- 2027-W01 より前に必要な調達・生産・輸送・在庫形成が Planning Horizon 外に切り落とされている

本設計では、これらを **能力状態、先行供給ロジック、計算期間** の3つの独立した設計要素として整理する。

---

## 2. WOM Planning における基本原則

WOM は、次の流れで Supply Chain Planning を行う。

1. 市場需要から **Demand Anchored Lot** を生成する
2. Backward Planning で必要供給週を算定する
3. Forward Planning で能力・物理制約下の供給可能性を検証する
4. PSI と PPC で数量・金額を評価する

このため、休日、能力制約、先行生産、計画期間は次の原則に従う。

### 2.1 休日・能力制約

休日や供給制約は、シナリオ CSV と Plugin により定義し、PSI 上の生産・在庫・CO に反映する。

### 2.2 先行生産週

`push_lead_time_weeks` は、供給側のリードタイムまたは先行供給方針を表すパラメータであり、Planning Horizon の不足を補うために短縮してはならない。

### 2.3 Planning Horizon

最終需要の開始前に必要な調達・生産・輸送・安全在庫形成を計算するため、Business Analysis Period より前に Planning Warm-up Period を置く。

---

## 3. 用語定義

| 用語 | 定義 |
|---|---|
| `explicit_closure` | 特定ノード・特定週を完全休業とする明示的状態 |
| `capacity_override` | 特定週の能力値を通常能力から別の値へ変更する設定 |
| `push_lead_time_weeks` | 将来需要 Lot を供給側へ何週先行させて配置するかを表す供給特性 |
| Planning Start | Planning Engine が計算を開始する週 |
| Planning Horizon | Planning Engine が計算対象とする全期間 |
| Planning Warm-up Period | 最終需要発生前の先行調達・生産・輸送・在庫形成期間 |
| Business Analysis Period | 販売、PSI、PPC を経営評価する主要期間 |
| Reporting Start | Chart や PPC Report の通常表示を開始する週 |

---

## 4. 現状分析

### 4.1 Holiday Calendar Plugin は動作している

実行ログでは、次の処理が確認されている。

```text
[HolidayCalendar] Loaded 2 rules from holiday_calendar.csv
[HolidayCalendar] Supply closure ... Bottling_Noda cap_hard=1500.0
[HolidayCalendar] explicit_closures written to config
```

したがって、Holiday Calendar Plugin の未読込が原因ではない。

### 4.2 Holiday CSV が通常能力を再設定している

現在の `holiday_calendar.csv` は、休業週の `Bottling_Noda` に `1500.0` を設定している。

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,1500.0
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,1500.0
```

一方、`capacity_plan.csv` における通常能力も 1,500 である。

したがって、現状の Plugin は次の処理を行っている。

```text
W18 の通常能力 1,500 を、Holiday Calendar により再度 1,500 に設定する
```

このため、PSI Graph に休業影響が現れない。

### 4.3 `capacity=0` の意味が衝突している

現行 Planning Engine では、概念的に次の判定が存在する。

```python
if cap_hard <= 0:
    continue  # unconstrained
```

そのため、

```text
capacity = 0
```

は「能力ゼロ」ではなく、次の意味になる。

```text
能力値未設定
＝能力制約なし
＝実質無制約
```

これは、次の2状態を同一値で表そうとすることによる設計上の衝突である。

- 能力未設定・無制約
- 明示的な完全休業・能力ゼロ

### 4.4 Bottling_Noda は MOM node である

醤油モデルの Inbound Tree は次の構造である。

```text
Materials_JP --2 weeks--> Brewing_Noda --4 weeks--> Bottling_Noda
```

ノード種別は次のとおりである。

| Node | Node Type |
|---|---|
| Materials_JP | `leaf_in` |
| Brewing_Noda | `mom` |
| Bottling_Noda | `mom` |

現行 Holiday Calendar Plugin の休業後補正が `leaf_in` のみを対象とする場合、`Bottling_Noda` 自身の休業週 P の前倒しは処理されない。

MOM node の休業は、Backward Planning の MOM Capacity 処理において、上流への需要伝播前に処理する必要がある。

---

## 5. Holiday Calendar の正式設計

### 5.1 完全休業は能力値ではなく状態として表す

完全休業は `cap_hard=0` ではなく、`explicit_closure` として管理する。

```python
config["explicit_closures"] = {
    "Bottling_Noda": {week_index_1, week_index_2}
}
```

### 5.2 状態の意味を分離する

| 設定 | 意味 |
|---|---|
| `cap_hard <= 0` | 能力未設定・無制約 |
| `explicit_closure` | 明示的な完全休業 |
| `capacity_override > 0` | 部分操業または特定週能力 |
| 通常 `capacity_plan.csv` | 通常週能力 |

### 5.3 Holiday CSV の推奨表現

正式修正後の完全休業は次のように記述する。

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,0
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,0
```

ただし、`effect=supply_closure` の場合、Plugin は `value` に依存せず完全休業として扱うことを推奨する。

### 5.4 部分操業は別 effect とする

部分操業または能力削減は、完全休業と分離する。

推奨 effect 名：

```text
capacity_override
partial_capacity
```

例：

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_PARTIAL_2027,Golden Week partial operation,2027-W18,2027-W18,Bottling_Noda,capacity_override,500
```

---

## 6. Backward Planner の処理要件

### 6.1 MOM Capacity 処理で休業を優先する

Backward Planner は、各ノード・各週について次の順序で能力を解釈する。

1. `explicit_closure` を確認する
2. 休業週なら実効能力をゼロとする
3. 休業週でなければ通常の `cap_hard` を確認する
4. `cap_hard <= 0` は未設定・無制約とする
5. 能力超過 Lot を前週へ移動する
6. 移動後の計画を上流ノードへ伝播する

概念コード：

```python
closure_set = self._explicit_closures.get(node.node_name, set())

for w in range(n_weeks - 1, -1, -1):

    if w in closure_set:
        cap_int = 0

    else:
        cap_w = node.cap_hard(w)

        if cap_w <= 0.0:
            continue  # unset = unconstrained

        cap_int = int(cap_w)

    s_lots = list(node.psi4demand[w][S])

    if len(s_lots) <= cap_int:
        continue

    within_cap = s_lots[:cap_int]
    overflow = s_lots[cap_int:]

    # 現行の MOM Capacity ロジックに従い、
    # overflow を前週側へ前倒しする
```

### 6.2 MOM node での前倒しを上流伝播より先に行う

休業週の Bottling_Noda の Lot を後処理で移動すると、Brewing_Noda と Materials_JP への Backward Propagation と不整合になる。

したがって、処理順は必ず次のようにする。

```text
Bottling_Noda 休業判定
→ Bottling_Noda P の前倒し
→ Brewing_Noda への必要量・必要週伝播
→ Materials_JP への必要量・必要週伝播
```

---

## 7. Forward Planner の処理要件

Forward Planner にも `explicit_closures` を渡し、休業週の生産・受入をゼロにする安全弁を設ける。

概念コード：

```python
forward_planner = ForwardPlanner(
    sc_tree,
    opening_inv=opening_inv,
    explicit_closures=config.get("explicit_closures", {}),
)
```

週次処理：

```python
is_closed = (
    w in self._explicit_closures.get(node.node_name, set())
)

if is_closed:
    # 当該週の生産・受入 P をゼロとして処理する

elif cap_hard > 0:
    # 通常の capacity sealing
```

Backward Planning で休業前倒しが完了していても、Forward Planning 側で閉鎖週 P を再確認することで、誤配置 Lot の流入を防止する。

---

## 8. 暫定確認方法

正式実装前に原因のみを確認する場合、`holiday_calendar.csv` の `value` を一時的に `0.1` とする。

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,0.1
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,0.1
```

現行ロジックでは、

```text
0.1 > 0
int(0.1) == 0
```

となり、実質的なゼロ能力として MOM Capacity 処理を通過する。

これは **epsilon workaround** であり、本番仕様として残してはならない。

PSI Graph 上で影響を確認しやすくするため、一時的に W18～W19 の2週間休業とする方法もある。

---

## 9. `push_lead_time_weeks` の意味

### 9.1 現行設定

`push_config.csv` の現行設定は次のとおりである。

```csv
sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week
Soy_Sauce,Bottling_Noda,0,0,False,,0,,7,
```

### 9.2 `push_lead_time_weeks=7` は維持する

醤油 Inbound Tree の物理 LT は概念的に次のとおりである。

```text
Materials_JP → Brewing_Noda     2 weeks
Brewing_Noda → Bottling_Noda    4 weeks
---------------------------------------
Total physical LT               6 weeks
```

現行の `push_lead_time_weeks=7` は次のように解釈できる。

```text
Physical LT 6 weeks
＋ Bottling_Noda buffer 1 week
＝ Push Lead Time 7 weeks
```

したがって、DC の初期 CO を解消するために `7` を `4` へ短縮すると、Planning Horizon の不足を供給 LT の短縮で隠すことになる。

これは WOM の因果関係を崩すため、推奨しない。

### 9.3 現行 Mode 4 の対象

現行 Push Production Planner は、Bottling_Noda を decoupling node とした後、その配下の `leaf_in`、すなわち Materials_JP の P schedule を前倒しする。

そのため、

```text
push_lead_time_weeks=4
```

は「Bottling_Noda が市場需要の4週前に瓶詰を開始する」という直接指定ではない。

### 9.4 将来拡張

MOM 工程の生産開始を直接指定する場合、次の識別子を分離する。

```text
production_node_id
demand_reference_node_id
```

例：

```text
production_node_id       = Bottling_Noda
demand_reference_node_id = Rest_US_East
production_lead_weeks    = 4
```

ただし、本設計の醤油モデルでは、現行 `push_lead_time_weeks=7` を維持する。

---

### 9.5 先行生産の三成分：`LT_offset(D2S) = B + X1 + X2`

先行生産は単一の機構ではなく、Planning Sequence 上の3つのフェーズに役割分担される。

| フェーズ | Layer | 担当する前倒し | 時間軸の性格 |
|---|---|---|---|
| Backward Demand Allocation | Demand | 能力・休日由来の前倒し（cap 超過、休業週の作り溜め） | need-date の「割り付け」 |
| Layer Transition (D→S) | 遷移 | 恒常的な LT 先行（`LT_offset`） | need→build の「変換」 |
| Forward Planning + Push-Pull | Supply | buffering node の積み溜め・引き出し | build 後の「時系列展開」 |

Demand Layer 上で Demand Allocation を完了した後、Demand Layer から Supply Layer へ
S と P を copy する際に、先行生産に相当する LT offset をこの Layer Transition の中に
組み込む。その後 Forward Planning が Supply Layer 上で Supply Chain Simulation として
機能する。

Layer Transition が「need-date と build-date の差」を担うのは、Demand/Supply の
two-layer 構造からの必然であり、恣意的な実装ではない。また Forward Planner は時間
シフトを一切担わないため、原則「Forward Planning は決して時間を遡及しない」がそのまま
保たれる。

#### LT_offset(D2S) の構成

```text
LT_offset(D2S) = B + X1 + X2
```

| 成分 | 実装 | 生む在庫 | 溜まる場所 | 決定主体 |
|---|---|---|---|---|
| B | `lt_wks` | pipeline 在庫（WIP・輸送中） | lane 上に分散 | 物理（LT そのもの、選べない） |
| X1 | `ss_wks` = ceil(`ss_days`/7) | 需要変動を吸収する安全在庫 | buffer node | 在庫政策 |
| X2 | `init_stock_wks` = ceil(`init_stock_days`/7) | 立ち上げ期の初期在庫 | buffer node | 人の意思入れ（計画パラメータ CSV） |

#### なぜ「時間」で在庫が立つのか

buffer node で P を S より `(B + X1 + X2)` 週手前へずらすと、Forward の

```text
I(W) = I(W-1) + P - S
```

において P が S に先行するため、その差分が I として自動的に積み上がる。
在庫の「高さ」を注入しなくても、P と S の「時間差」を作れば高さは Forward が生成する。

これは「初期状態は外から与えず、計画が生成する」という WOM の設計原則の実装形である。

#### 横軸（Planning Horizon）との二層関係

X2 は per-node の offset であり、Planning Warm-up Period（横軸の延長、10〜11章）とは
別の層である。両者は競合せず、次の関係にある。

```text
Planning Warm-up Period（横軸）
    必要条件：build が走る計算領域を確保する
    これが無いと offset は past_due に落ちるだけで在庫は立たない

LT_offset の X2（per-node）
    十分条件：どの node にどれだけ在庫を残すかを決める
    これが無いと横軸を延ばしても buffer に狙った在庫は立たない
```

したがって計画期間のサイジングは次のとおり。

```text
D = A + B + X2
    A  : 最終需要地での需要計画期間（例 104 weeks）
    B  : E2E Supply Chain の LT（例 20 weeks）
    X2 : warm-up 分（初期在庫のカバレッジ週数）
```

窓の先頭 B 週は「需要ゼロだが build は走る領域」＝ Warm-up、末尾 B 週は「build 済みだが
pipeline が流れ切る領域」＝ EOL ドレインである。C = A + B は LT offset が生む自然な
張り出しであり、恣意的なマージンではない。

**依存関係の注意**：`init_stock_days` を増やすと、その分だけ Backward の遡り量が増える。
Planning Start が前倒しされていないと `parent_w < 0` となり `record_past_due` に落ちる。
X2 を設定する際は、Planning Warm-up Period も連動して確保すること。

#### X2 は定常状態にも残る（設計判断）

`LT_offset` は全期間に一律に効く定数であるため、X2 は立ち上げ後もドレインせず恒久的に
残る。これはバグではなく設計選択である。

- X1 + X2 を合わせて「この node の在庫政策」と見なす
- そもそも buffer node の役割・目的は最終市場の需要変動を吸収する政策的な在庫であり、
  この仕組みはその目的と合致する
- トレードオフ：運転資本が恒久的に増える（CCC 悪化、PPC のキャッシュ回収週に影響）。
  ただし PPC 側で可視化されるため、X2 を絞る経営判断が可能である

#### 検討したが採用しなかった案

**(1) `opening_inv` による外部注入**

`ForwardPlanner(opening_inv={node_id: [lot_id, ...]})` は既存機構として存在するが、
warm-up の主機構としては採用しない。注入する lot_id の発番が「Lot_ID の発番は需要計画
（S_month / S_week）生成のみ」という単一源泉原則と衝突するためである。

`opening_inv` は「計画期間外で既に発生済みの実在庫（前期繰越・棚卸ロード）」専用として
意味を限定し、warm-up とは役割を分ける。

**(2) 先行需要（マーケ初期需要）として建てる案**

warm-up 分を「初期ロット・試作品」の先行需要として需要計画に建てれば発番原則は守れるが、
**先行需要が積んだ在庫を先行需要自身が消費してしまうため、buffer node の棚在庫は残らず
初期 CO は解消しない**。先行需要が担えるのは pipeline 充填（B）のみである。この案は破棄。

**実務照合**：MRP / APS の一般解でも、期首在庫（Beginning On Hand）は「計算で作るもの
ではなく計算に与えるもの」であり、棚在庫を需要では作らない。また新製品立ち上げの実務
指標は「pipeline fill ＋ safety stock ＋ LT buffer」を別々に週数で数える（合計 6〜8 週が
典型）——WOM の B / X1 / X2 分解と同型である。初期配分は均等割りではなく経営判断で
非対称に置き、立ち上げ期は自動最適化ではなく人が短サイクルで見直すのが標準である。
したがって手動調整（人の意思入れ）を主機構とする本設計は実務標準に沿う。

#### 適用範囲

`init_stock_days` は OutBound Tree の任意の node に設定できる（既定 0 = opt-in）。
buffer node に限定するガードは設けない。ボトルネックもバッファも固定属性ではなく状態で
あり、外部環境（市場、物流）・内部環境（設備、資金）の変化により制御対象 node は移動する
ためである。WOM は既に `decouple_optimizer.py` / `BufferingStockOptimizerPlugin` により
バッファ配置を動かす前提で設計されており、静的ガードはこれと矛盾する。

設定は運用者の裁量に委ねる。

---

## 10. Planning Warm-up Period

### 10.1 問題の本質

現行 AutoDetect は `demand_forecast.csv` の最初の週を Planning Start とし、ユニーク週数を Planning Horizon としている。

現状：

```text
Planning Start   = 2027-W01
Planning Weeks   = 104
```

しかし、2027-W01 の販売需要を満たすためには、2026年中に次の活動が必要である。

- 原材料手配
- 醸造
- 瓶詰
- FG_WH_Noda への事前配置
- 米国 DC への輸送
- 安全在庫形成

現状では、これらの一部または全部が Planning Horizon の外に切り落とされ、2027-W01 付近の DC に初期 CO が発生する。

### 10.2 期間を2層に分ける

```text
Planning Warm-up Period
    先行調達・先行生産・先行輸送・初期在庫形成

Business Analysis Period
    販売、PSI、PPC、利益評価
```

今回のモデルでは、最終需要開始週は変更しない。

```text
Final Demand Start = 2027-W01
```

変更するのは Planning Engine の計算開始週である。

---

## 11. Warm-up Period の設定水準

### 11.1 4週間の表示を可能にする最小設定

2027-W01 より4週間前は次のとおりである。

```text
2026-W53  1 week before
2026-W52  2 weeks before
2026-W51  3 weeks before
2026-W50  4 weeks before
```

最低限の4週間 Warm-up：

```text
Planning Start = 2026-W50
Planning Weeks = 108
```

これは、4週間の先行挙動をグラフ上で確認するための最小設定である。

### 11.2 Push Lead Time 7週間を完全に含む最小設定

`push_lead_time_weeks=7` を Planning Horizon 内で完全に表現するには、最低7週間が必要である。

```text
Planning Start = 2026-W47
Planning Weeks = 111
```

### 11.3 米国 DC の初期 CO 解消を目的とする推奨設定

米国 DC までの Outbound 側には、輸送 LT と安全在庫期間が存在する。

概算：

| Market | Outbound Lead / Buffer | Push 7 weeks included | Planning Start Guide |
|---|---:|---:|---|
| Japan | approx. 6 weeks | approx. 13 weeks | 2026-W41 |
| US West | approx. 13 weeks | approx. 20 weeks | 2026-W34 |
| US East | approx. 14 weeks | approx. 21 weeks | 2026-W33 |

米国東海岸の概念時間構造：

```text
Rest_US_East
← 1 week
DC_US_NY
← 6 weeks + safety stock 3 weeks
FG_WH_Noda
← 1 week + safety stock 3 weeks
SP / Bottling_Noda
← push lead time 7 weeks
```

したがって、DC の初期 CO 解消を検証するための推奨値は次のとおりである。

```text
Planning Start          = 2026-W33
Planning Warm-up Period = 2026-W33 .. 2026-W53
Business Analysis       = 2027-W01 .. 2028-W52
Planning Weeks          = 125
```

---

## 12. `demand_forecast.csv` の設定

### 12.1 ゼロ需要行を追加する

AutoDetect に Planning Warm-up Period を認識させるため、2026-W33～W53 に全地域のゼロ需要行を追加する。

```csv
sku_id,region,week,quantity
Soy_Sauce,JP,2026-W33,0
Soy_Sauce,US_W,2026-W33,0
Soy_Sauce,US_E,2026-W33,0
Soy_Sauce,FR,2026-W33,0
Soy_Sauce,BE,2026-W33,0
Soy_Sauce,NL,2026-W33,0
```

上記を 2026-W53 まで繰り返す。

2027-W01 以降の実需要は変更しない。

### 12.2 期待する AutoDetect 結果

```text
[AutoDetect] period: 2026-W33 × 125 weeks
```

ゼロ需要行は「最終需要の開始時期を変更する」設定ではなく、Planning Engine の計算期間を前倒しするための設定である。

---

## 13. `capacity_plan.csv` の設定

Demand だけを 2026-W33 まで延長し、Capacity Plan を 2027-W01 開始のままにすると、Warm-up Period の能力が未設定になる。

現行仕様では未設定能力 `0` が無制約扱いになるため、Warm-up Period だけ無限能力で生産できる可能性がある。

したがって、`capacity_plan.csv` も同じ期間へ延長する。

```csv
sku_id,node_name,week,cap_hard,note
Soy_Sauce,Bottling_Noda,2026-W33,1500,瓶詰 週次能力
Soy_Sauce,Brewing_Noda,2026-W33,1500,醸造 週次能力
Soy_Sauce,Materials_JP,2026-W33,50000,素材供給 実質無制約
```

上記を 2026-W53 まで設定する。

---

## 14. Planning Horizon と Reporting Horizon の分離

ゼロ需要行を CSV に追加する方法は、現行 AutoDetect を利用するための実装方法である。

将来的には、Planning と Reporting の期間を設定として分離する。

推奨パラメータ：

```yaml
planning_start_week: 2026-W33
planning_weeks: 125
reporting_start_week: 2027-W01
warmup_weeks: 21
```

または：

```yaml
business_start_week: 2027-W01
pre_horizon_weeks: 21
```

処理イメージ：

```text
Planning Engine
    2026-W33 から計算

PSI Internal State
    2026-W33 から保持

Standard Charts / PPC Reports
    2027-W01 から表示

Diagnostic Charts
    Warm-up Period を含めて表示可能
```

これにより、Planning Horizon と Management Reporting Horizon を明確に分離できる。

---

## 15. 期待される PSI 挙動

### 15.1 Warm-up Period

2027-W01 より前に、次の状態が形成される。

| Node | Expected Behavior |
|---|---|
| Materials_JP | P が先行して立ち上がる |
| Brewing_Noda | 醸造要求・供給が立ち上がる |
| Bottling_Noda | 瓶詰と一部在庫形成が始まる |
| FG_WH_Noda | 輸出前バッファ在庫が形成される |
| DC_US_SF | 初期安全在庫が形成される |
| DC_US_NY | 初期安全在庫が形成される |

2027-W01 の販売開始時点では、次を期待する。

```text
DC Inventory > 0
DC CO ≈ 0
Rest_US shipment = demand
```

### 15.2 Holiday Closure

1週間完全休業で通常需要が 1,000 lots、通常能力が 1,500 lots の場合、概念的には次のような前倒しとなる。

通常：

```text
W16 P = 1,000
W17 P = 1,000
W18 P = 1,000
```

休業対応例：

```text
W16 P = 1,500
W17 P = 1,500
W18 P = 0
```

実際の前倒し配分は、現行 MOM Capacity ロジック、Lot 順序、在庫状態に従う。

最終市場の S が滑らかなままであること自体は異常ではない。

正常な Holiday PSI は、次のように現れる。

```text
Bottling_Noda P
    休業週に低下またはゼロ

Bottling_Noda / FG_WH_Noda I
    休業前に上昇

FG_WH_Noda / DC I
    休業週に低下

Rest_US_* S
    バッファが十分なら維持
```

休日影響は、販売 S の乱れではなく、その裏側の生産・在庫変動として確認する。

---

## 16. 検証対象ノードと KPI

### 16.1 Holiday Calendar 検証

| Node | Check |
|---|---|
| Bottling_Noda | demand P、supply P、I、CO |
| Brewing_Noda | P の前倒し |
| Materials_JP | 上流必要週の前倒し |
| FG_WH_Noda | 休業前の在庫上昇、休業中の在庫低下 |
| DC_US_SF / DC_US_NY | 休業影響の吸収 |
| Rest_US_* | S が維持されたか |

### 16.2 Warm-up Period 検証

| Check | Acceptance Guide |
|---|---|
| AutoDetect | `2026-W33 × 125 weeks` |
| Warm-up P | 2026年中に上流 P が発生する |
| DC Opening Inventory | 2027-W01 時点で在庫を保持する |
| Initial DC CO | 0 または業務上許容範囲 |
| Rest Shipment | 2027-W01 から需要どおり |
| Capacity | Warm-up Period でも通常能力を適用 |
| Lot Identity | 先行週移動後も Demand Anchored Lot ID を維持 |

---

## 17. 異常時の切り分け

Planning Start を 2026-W33 まで前倒ししても DC CO が残る場合、Planning Horizon 不足以外を確認する。

優先確認項目：

1. Lot ID の週移動不整合
2. Push supply と DC demand の identity mismatch
3. Forward propagation LT
4. Decoupling node の供給設定
5. Safety stock の二重加算または未反映
6. Capacity shortage
7. Closure 前倒し後の上流伝播不整合
8. Opening inventory の初期化
9. `transit_lt_wks` と `lt_wks` の意味混在

Matplotlib の次の警告は、本件とは無関係である。

```text
No artists with labels found to put in legend
```

---

## 18. 推奨する実施順序

### Phase 1: Holiday 設定の原因確認

1. `holiday_calendar.csv` の休業値を一時的に `0.1` とする
2. Bottling_Noda の W18 P がゼロまたは前倒しになるか確認する
3. 必要に応じて W18～W19 の2週休業で変化を強調する

### Phase 2: Holiday の正式実装

1. `explicit_closures` を能力値とは別状態として保持する
2. Backward Planner の MOM Capacity 処理へ休業判定を追加する
3. 上流伝播前に休業週 Lot を前倒しする
4. Forward Planner に休業週 P=0 の安全弁を追加する
5. 部分操業を別 effect として定義する

### Phase 3: Warm-up Period の導入

1. `push_lead_time_weeks=7` を維持する
2. `demand_forecast.csv` に 2026-W33～W53 のゼロ需要行を追加する
3. `capacity_plan.csv` に同期間の通常能力を追加する
4. AutoDetect が `2026-W33 × 125 weeks` を認識することを確認する
5. 2027-W01 時点の DC inventory と CO を確認する

### Phase 4: Horizon 分離機能

1. `planning_start_week`
2. `planning_weeks`
3. `reporting_start_week`
4. `warmup_weeks` または `pre_horizon_weeks`

をモデル設定へ追加し、ゼロ需要行への依存を減らす。

---

## 19. 推奨シナリオ設定

`soysauce-us-2027` の推奨設定：

```text
push_lead_time_weeks
    7 weeks
    変更しない

Final Demand Start
    2027-W01

Planning Start
    2026-W33

Planning Warm-up Period
    2026-W33 .. 2026-W53

Business Analysis Period
    2027-W01 .. 2028-W52

Total Planning Weeks
    125 weeks

Holiday Closure
    explicit_closure として定義

Normal Bottling Capacity
    1,500 lots/week

Holiday Week Bottling Capacity
    0 lots/week through explicit closure state
```

---

## 20. 設計判断

本設計の主要な判断は次のとおりである。

### Decision 1

`capacity=0` の既存意味は、当面「未設定・無制約」として維持する。

### Decision 2

完全休業は `capacity=0` ではなく、`explicit_closure` で表す。

### Decision 3

`push_lead_time_weeks=7` は供給側の特性として維持する。

### Decision 4

DC 初期 CO の解消は、Push Lead Time の短縮ではなく、Planning Warm-up Period の追加により行う。

### Decision 5

最終需要は 2027-W01 から変更せず、Planning Engine の計算開始を 2026-W33 へ前倒しする。

### Decision 6

将来的に Planning Horizon と Management Reporting Horizon を分離する。

### Decision 7

先行生産の機構は Tree で役割を分ける。

```text
InBound Tree
    完成品が作られるまでのボトルネック解消
    → push_lead_time_weeks（Mode 4）が担当

OutBound Tree
    完成品が市場へ流れ出した後の需要変動吸収
    → LT_offset(D2S) の init_stock_wks（X2）が担当
```

両者は解いている問題が異なる。InBound は供給側の不確実性（素材が届くか、工程が回るか）
に対する備えであり、OutBound は需要側の不確実性（市場がいくら買うか）に対する備えで
ある。decoupling point がこの2つの世界の境界であり、その上流は `push_lead_time_weeks`、
下流は `init_stock_wks` が担当する。

適用範囲は排他であり、同一 lane で二重に前倒しされることはない。この排他性は
`backward_planner.py` の実装で保証する（X2 は OutBound propagation にのみ加算し、
InBound propagation には加算しない）。

---

## 21. Acceptance Criteria

本設計の完了条件は次のとおりである。

- [ ] `supply_closure` が通常能力の再設定ではなく完全休業として処理される
- [ ] `capacity=0` と完全休業が明確に区別される
- [ ] Bottling_Noda の休業週 P がゼロになる
- [ ] 休業週需要が休業前へ前倒しされる
- [ ] 前倒し後の必要量が Brewing_Noda、Materials_JP へ整合的に伝播する
- [ ] Forward Planner が休業週への P 流入を防止する
- [ ] `push_lead_time_weeks=7` が維持される
- [ ] Planning Start が 2026-W33 として認識される
- [ ] Warm-up Period に通常 Capacity が適用される
- [ ] 2027-W01 より前に DC 在庫が形成される
- [ ] 2027-W01 付近の DC CO が解消または合理的に説明される
- [ ] Standard Report は 2027-W01 以降を表示できる
- [ ] Diagnostic Report は Warm-up Period を表示できる

---

## 22. 今後の設計課題

1. `capacity=None` または Capacity Mode Enum による Unlimited / Zero / Finite の明示化
2. Holiday Closure と Maintenance Shutdown の共通イベント化
3. 休業週の前倒し方針：FIFO、Priority、Demand Date、Market Priority
4. ~~Planning Warm-up Period の Auto Calculation~~
   → 部分解決（9.5）。必要 warm-up の構成は `LT_offset(D2S) = B + X1 + X2` として確定。
   横軸の自動算定（Planning Start の自動前倒し）は未実装。
5. ~~SC Tree の累積 LT と Safety Stock から必要 Warm-up Weeks を算定する機能~~
   → 式は確定（9.5）。`B + X1` が累積 LT と Safety Stock に対応し、`X2` が
   `optional_prebuild_buffer` に対応する。自動算定の実装は未着手。
6. `production_node_id` と `demand_reference_node_id` の分離
7. Warm-up Period を除外した PPC Reporting
8. ~~Opening Inventory と Warm-up Production の役割分担~~
   → 解決（9.5、Decision 7）。`opening_inv` は計画期間外の実在庫（前期繰越・棚卸ロード）
   専用とし、warm-up による在庫形成は `LT_offset` の X2 が担当する。
9. Holiday Event の PSI Graph annotation
10. Closure により吸収された Lot と CO へ転化した Lot の追跡
11. X2 が定常状態に残す運転資本増を PPC / CCC でどう可視化するか
12. 環境変化の narrative 入力から、適切な bottleneck と buffer の配置を割り出す機能
    （`init_stock_days` の per-node 化により、探索空間の一次元として扱える素地はできた）

---

## 23. まとめ

休日、先行生産、計画期間は、次のように分離して扱う。

```text
Holiday Calendar
    特定週の能力状態を定義する

push_lead_time_weeks
    InBound 側で、供給側が将来需要を何週先行して準備するかを定義する

LT_offset(D2S) = B + X1 + X2
    OutBound 側で、need-date から build-date への変換量を定義する
    X2 = init_stock_wks が立ち上げ期の初期在庫を生む

Planning Warm-up Period
    先行調達・生産・輸送・在庫形成を計算可能にする（横軸の確保）

Business Analysis Period
    実需要、PSI、PPC、経営評価を行う
```

醤油モデルでは、次を基本設定とする。

```text
push_lead_time_weeks = 7          （InBound）
init_stock_days      = 運用者設定  （OutBound buffer node、既定 0）
Planning Start       = 2026-W33
Final Demand Start   = 2027-W01
Planning Weeks       = 125
```

これにより、

> 2027年から販売を開始するために、2026年から原材料調達・生産・輸送・DC在庫形成を開始する

という、実際の Supply Chain Operation に沿った PSI Planning を表現する。

初期 CO の解消は、Supply Chain の LT を短く見せることではなく、
(1) 販売開始前の供給準備期間を Planning Horizon へ正しく含めること（横軸）、
(2) buffer node の LT_offset に X2 を与えること（per-node）、
の2層で行う。
