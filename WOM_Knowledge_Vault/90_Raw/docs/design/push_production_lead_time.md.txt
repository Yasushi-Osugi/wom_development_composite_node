# Push Production Lead Time 設計

- **Document Status**: Draft for Design Review
- **Target Release**: WOM v1r2m0 以降
- **Primary Scope**: Push Production、先行供給週、Demand Reference、Production Node
- **Related Scenario**: `data/sample/soysauce-us-2027`
- **Related Integrated Design**: `docs/design/holiday_calendar_push_lead_time_and_planning_horizon.md`

> **重複に関する注記**  
> 本文書は、統合設計書
> [`holiday_calendar_push_lead_time_and_planning_horizon.md`](holiday_calendar_push_lead_time_and_planning_horizon.md)
> からテーマ別に切り出した設計書である。  
> 単独で参照・レビューできるようにするため、背景、設計原則、設定例、検証条件の一部を意図的に重複して記載している。


---

## 1. 目的

本設計は、WOMにおける `push_lead_time_weeks` の意味、適用対象、Planning Horizonとの関係を明確にする。

特に、DC nodeの初期COを解消する目的で `push_lead_time_weeks` を変更することと、計算開始週を前倒しすることを区別する。

本設計の主要判断は次のとおりである。

```text
push_lead_time_weeks = 7
```

は供給側のオペレーション特性として維持し、Planning Horizon不足を補うために短縮しない。

---

## 2. 現行設定

`push_config.csv`：

```csv
sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week
Soy_Sauce,Bottling_Noda,0,0,False,,0,,7,
```

主要項目：

| Field | Current Value | Meaning |
|---|---:|---|
| `sku_id` | Soy_Sauce | 対象SKU |
| `node_id` | Bottling_Noda | Decoupling node |
| `push_qty_per_week` | 0 | 固定Push数量は未使用 |
| `buffer_lots` | 0 | 固定Lot Bufferは未使用 |
| `push_lead_time_weeks` | 7 | 将来需要を7週先行して供給側へ配置 |
| `push_eol_week` | blank | Push終了週なし |

---

## 3. `push_lead_time_weeks` の意味

Mode 4の概念処理：

```python
push[w] = demand_ref_node.psi4demand[w + LT][S]
```

将来週 `w + LT` に存在するDemand Anchored Lotを、供給側の週 `w` へ前倒しする。

したがって、`push_lead_time_weeks` は次を表す。

```text
供給側が、将来需要Lotを何週前から準備するか
```

これはPlanning Horizonの表示幅ではなく、供給側の先行供給方針またはオペレーションLTである。

---

## 4. 醤油モデルのInbound Lead Time

Inbound Tree：

```text
Materials_JP --2 weeks--> Brewing_Noda --4 weeks--> Bottling_Noda
```

概念上の物理LT：

```text
Materials_JP → Brewing_Noda     2 weeks
Brewing_Noda → Bottling_Noda    4 weeks
---------------------------------------
Total physical LT               6 weeks
```

現行 `push_lead_time_weeks=7` は次のように解釈できる。

```text
Physical LT 6 weeks
＋ Bottling_Noda buffer 1 week
＝ Push Lead Time 7 weeks
```

したがって、現行値7はモデル構造と整合する。

---

## 5. `7` を `4` へ変更しない理由

`push_lead_time_weeks=4` とすると、概念上は次の関係になる。

```text
供給開始
    需要の4週前

物理所要期間
    6週
```

このため、約2週間の遅れ、在庫不足、COが発生する可能性がある。

また、現在のPush Production Plannerは、`Bottling_Noda` をdecoupling nodeとした後、その配下の `leaf_in`、すなわち `Materials_JP` のP scheduleを前倒しする。

したがって、

```text
push_lead_time_weeks=4
```

は、

```text
Bottling_Nodaで市場需要の4週前に瓶詰を開始する
```

という直接指定ではない。

DC初期COを解消するために7を4へ変えると、Planning Horizon不足を供給LT短縮で隠すことになるため推奨しない。

---

## 6. Planning Horizonとの責任分離

| Design Element | Responsibility |
|---|---|
| `push_lead_time_weeks` | 将来需要に対する供給側の先行週 |
| Planning Start | 計算可能な最初の週 |
| Planning Warm-up Period | 最終需要前の調達・生産・輸送・在庫形成期間 |
| Reporting Start | 通常レポートを開始する週 |

正しい対処：

```text
Push Lead Time
    7週のまま維持

Final Demand Start
    2027-W01のまま維持

Planning Start
    2026年側へ前倒し
```

誤った対処：

```text
Planning Horizonが短い
→ Push Lead Timeを短縮する
```

---

## 7. Push Planningの処理要件

### 7.1 Demand Anchored Lot Identityを維持する

先行週へ移動するのはDemand量の集計値だけではなく、Demand Anchored Lot IDである。

要件：

- 同一Demand Lotを別IDへ再生成しない
- 元の市場、需要週、チャネルを追跡可能にする
- 前倒し週と元需要週の双方をEvent Ledgerで確認可能にする

推奨属性：

```text
lot_id
demand_week
push_scheduled_week
push_lead_time_weeks
demand_reference_node_id
production_node_id
```

### 7.2 物理LTとPush LTを検証する

次を満たさない場合は警告またはValidation Errorとすることを検討する。

```text
push_lead_time_weeks >= cumulative_physical_lt
```

ただし、意図的な不足シナリオを評価する場合は警告のみとし、実行を許可する。

### 7.3 Node責任を明確にする

現行 `node_id` だけでは、次の意味が曖昧になり得る。

- Demandを参照するNode
- Push判断を行うDecoupling Node
- 実際に生産を開始するNode
- P scheduleを配置するleaf_in Node

将来は各役割を分離する。

---

## 8. 将来のPush Config拡張

推奨項目：

```csv
sku_id,decoupling_node_id,demand_reference_node_id,production_node_id,supply_start_node_id,push_lead_time_weeks
Soy_Sauce,Bottling_Noda,Rest_US_East,Bottling_Noda,Materials_JP,7
```

役割：

| Field | Meaning |
|---|---|
| `decoupling_node_id` | Push/Pull境界 |
| `demand_reference_node_id` | 将来需要を参照するNode |
| `production_node_id` | 先行生産開始を評価するNode |
| `supply_start_node_id` | P scheduleを最初に配置するNode |
| `push_lead_time_weeks` | Demand Referenceに対する先行週 |

MOM工程の生産開始を直接指定する場合：

```text
production_node_id       = Bottling_Noda
demand_reference_node_id = Rest_US_East
production_lead_weeks    = 4
```

この指定は、現行 `push_lead_time_weeks` とは別概念として追加する方が明確である。

---

## 9. Push Lead Timeの検証

### 9.1 基本検証

| Check | Expected |
|---|---|
| Config load | `push_lead_time_weeks=7` |
| Lot retiming | 元需要週の7週前へ配置 |
| Lot identity | Lot ID維持 |
| Inbound propagation | Brewing_Noda、Materials_JPへ整合伝播 |
| Capacity | 各週の有限能力を適用 |
| Horizon | 先行週がPlanning Horizon内に存在 |

### 9.2 PSI確認

| Node | Check |
|---|---|
| Materials_JP | 需要前にPが立ち上がる |
| Brewing_Noda | LTに従ってPが立ち上がる |
| Bottling_Noda | 瓶詰要求と供給が整合する |
| FG_WH_Noda | 出荷前在庫を形成する |
| DC_US_* | 初期在庫を形成する |
| Rest_US_* | 需要週からSを維持する |

---

## 10. 異常時の切り分け

Push設定後もCOが残る場合、次を確認する。

1. Planning HorizonがPush先行週を含んでいるか
2. `demand_reference_node_id` が意図したNodeか
3. Push scheduleの配置Nodeが意図したNodeか
4. 累積物理LTとPush LTが整合しているか
5. Lot IDの週移動が維持されているか
6. Forward propagation LTが重複加算されていないか
7. Capacity不足が発生していないか
8. Safety Stock期間が別途必要ではないか
9. Opening Inventoryがゼロのまま販売開始していないか

---

## 11. Acceptance Criteria

- [ ] `push_lead_time_weeks=7` の意味が供給側先行週として明確である
- [ ] Planning Horizon不足の補正にPush LTを使用しない
- [ ] 累積物理LT6週とPush LT7週の関係が説明できる
- [ ] Demand Anchored Lot IDを維持して週移動する
- [ ] 元需要週とPush配置週を追跡できる
- [ ] Materials_JP、Brewing_Noda、Bottling_Nodaの週関係が整合する
- [ ] Push先行週がPlanning Horizon内に含まれる
- [ ] 将来のNode役割分離案が定義されている

---

## 12. 設計判断

```text
push_lead_time_weeks = 7
    維持する

push_lead_time_weeks = 4
    DC初期CO対策としては使用しない

DC初期CO
    Planning Warm-up Periodで解消する

MOM工程の直接的な生産開始指定
    production_node_idとdemand_reference_node_idを分離して将来拡張する
```

`push_lead_time_weeks` は、計算期間を埋めるための便宜的パラメータではなく、Supply Chain Operationの時間特性を表す。
