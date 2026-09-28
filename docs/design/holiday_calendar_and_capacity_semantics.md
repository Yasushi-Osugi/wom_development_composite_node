# Holiday Calendar and Capacity Semantics 設計

- **Document Status**: Draft for Design Review
- **Target Release**: WOM v1r2m0 以降
- **Primary Scope**: Holiday Calendar、完全休業、部分操業、Capacity意味論
- **Related Scenario**: `data/sample/soysauce-us-2027`
- **Related Integrated Design**: `docs/design/holiday_calendar_push_lead_time_and_planning_horizon.md`

> **重複に関する注記**  
> 本文書は、統合設計書
> [`holiday_calendar_push_lead_time_and_planning_horizon.md`](holiday_calendar_push_lead_time_and_planning_horizon.md)
> からテーマ別に切り出した設計書である。  
> 単独で参照・レビューできるようにするため、背景、設計原則、設定例、検証条件の一部を意図的に重複して記載している。


---

## 1. 目的

本設計は、WOMのPSI Planningにおいて、次の能力状態を明確に区別することを目的とする。

1. 能力未設定
2. 能力制約なし
3. 有限能力
4. 完全休業
5. 部分操業または一時的な能力変更

特に、現行実装における次の意味衝突を解消する。

```text
capacity = 0
```

が、

```text
能力ゼロ
```

ではなく、

```text
能力未設定
＝能力制約なし
＝実質無制約
```

として扱われる点である。

完全休業は通常Capacityの数値とは独立した状態として表し、Backward PlanningとForward Planningの双方へ一貫して反映する。

---

## 2. 背景

醤油モデル `soysauce-us-2027` の実行ログでは、Holiday Calendar Plugin自体は動作している。

```text
[HolidayCalendar] Loaded 2 rules from holiday_calendar.csv
[HolidayCalendar] Supply closure ... Bottling_Noda cap_hard=1500.0
[HolidayCalendar] explicit_closures written to config
```

しかし、現在の `holiday_calendar.csv` は休業週の `Bottling_Noda` に通常能力と同じ `1500.0` を設定している。

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,1500.0
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,1500.0
```

通常の `capacity_plan.csv` でも `Bottling_Noda` の能力は1,500であるため、現状は次の処理になっている。

```text
W18の通常能力1,500を、Holiday Calendarにより再度1,500へ設定する
```

したがって、Pluginは失敗しているのではなく、CSVを忠実に実行した結果として休業になっていない。

---

## 3. 設計原則

### 3.1 完全休業はCapacity値ではなく状態で表す

完全休業は `cap_hard=0` によって表現せず、`explicit_closure` として管理する。

```python
config["explicit_closures"] = {
    "Bottling_Noda": {week_index_1, week_index_2}
}
```

### 3.2 Capacity意味論を分離する

| 状態 | 推奨表現 | 意味 |
|---|---|---|
| 能力未設定 | `cap_hard <= 0` | 現行互換上、無制約として扱う |
| 有限能力 | `cap_hard > 0` | 週次処理可能Lot数 |
| 完全休業 | `explicit_closure` | 実効能力ゼロ |
| 部分操業 | `capacity_override` | 指定値へ一時変更 |
| 通常操業 | `capacity_plan.csv` | 通常週能力 |

### 3.3 完全休業と部分操業を別effectにする

推奨effect：

```text
supply_closure
capacity_override
```

または、

```text
supply_closure
partial_capacity
```

`effect=supply_closure` の場合、Pluginは `value` に依存せず完全休業として扱うことを推奨する。

---

## 4. Holiday Calendar CSV仕様

### 4.1 完全休業

正式修正後の推奨例：

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,0
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,0
```

`value=0` は可読性のために残してよいが、完全休業の意味は `effect=supply_closure` から決定する。

### 4.2 部分操業

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_PARTIAL_2027,Golden Week partial operation,2027-W18,2027-W18,Bottling_Noda,capacity_override,500
```

この場合は `value=500` を当該週の有限能力として扱う。

---

## 5. Backward Planner処理要件

### 5.1 MOM Capacity処理で休業状態を優先する

Backward Plannerは、各ノード・各週について次の順序で実効能力を決める。

1. `explicit_closure` を確認する
2. 休業週なら実効能力をゼロとする
3. 休業週でなければ `capacity_override` を確認する
4. overrideがなければ通常の `cap_hard` を使用する
5. `cap_hard <= 0` は現行互換上、未設定・無制約とする
6. 能力超過Lotを前週へ前倒しする
7. 前倒し後の必要量を上流へ伝播する

概念コード：

```python
closure_set = self._explicit_closures.get(node.node_name, set())
override_map = self._capacity_overrides.get(node.node_name, {})

for w in range(n_weeks - 1, -1, -1):

    if w in closure_set:
        cap_int = 0

    elif w in override_map:
        cap_int = int(override_map[w])

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

    # overflowを前週側へ前倒しする
```

### 5.2 MOM nodeの休業処理を上流伝播前に行う

醤油モデルのInbound Tree：

```text
Materials_JP --2 weeks--> Brewing_Noda --4 weeks--> Bottling_Noda
```

ノード種別：

| Node | Node Type |
|---|---|
| Materials_JP | `leaf_in` |
| Brewing_Noda | `mom` |
| Bottling_Noda | `mom` |

`Bottling_Noda` はMOM nodeであるため、leaf_inだけを対象としたHoliday Plugin後処理では不十分である。

正しい処理順：

```text
Bottling_Noda休業判定
→ Bottling_Noda Pの前倒し
→ Brewing_Nodaへの必要量・必要週伝播
→ Materials_JPへの必要量・必要週伝播
```

---

## 6. Forward Planner処理要件

Forward Plannerにも `explicit_closures` と `capacity_overrides` を渡す。

```python
forward_planner = ForwardPlanner(
    sc_tree,
    opening_inv=opening_inv,
    explicit_closures=config.get("explicit_closures", {}),
    capacity_overrides=config.get("capacity_overrides", {}),
)
```

週次処理：

```python
is_closed = (
    w in self._explicit_closures.get(node.node_name, set())
)

if is_closed:
    # 当該週の生産・受入Pをゼロとして処理する

elif w in override_map:
    # override能力でcapacity sealing

elif cap_hard > 0:
    # 通常のcapacity sealing
```

Backward Planningで前倒し済みでも、Forward Planning側で休業週Pを再確認することで誤流入を防止する。

---

## 7. 暫定確認方法

正式実装前の原因確認に限り、`value=0.1` を利用できる。

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,0.1
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,0.1
```

現行コードでは、

```text
0.1 > 0
int(0.1) == 0
```

となるため、実質能力ゼロとしてMOM Capacity処理を通過する。

これは **epsilon workaround** であり、本番仕様として使用してはならない。

---

## 8. PSI上の期待挙動

通常需要が1,000 lots、通常能力が1,500 lots、W18が完全休業の場合の概念例：

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

正常なPSIでは、次が期待される。

```text
Bottling_Noda P
    休業週にゼロ

Bottling_Noda / FG_WH_Noda I
    休業前に増加

FG_WH_Noda / DC I
    休業週に減少

Rest_US_* S
    バッファが十分なら維持
```

最終市場のSが滑らかなままであっても異常ではない。休日影響は、その裏側のPとIの変化で確認する。

---

## 9. 検証対象

| Node | Check |
|---|---|
| Bottling_Noda | demand P、supply P、I、CO |
| Brewing_Noda | Pの前倒し |
| Materials_JP | 上流必要週の前倒し |
| FG_WH_Noda | 休業前の在庫上昇、休業中の在庫低下 |
| DC_US_SF / DC_US_NY | 休業影響の吸収 |
| Rest_US_* | Sが維持されたか |

---

## 10. Acceptance Criteria

- [ ] `supply_closure` が完全休業として処理される
- [ ] `capacity=0` と完全休業が区別される
- [ ] 部分操業が完全休業とは別effectで表現できる
- [ ] Bottling_Nodaの休業週Pがゼロになる
- [ ] 休業週需要が休業前へ前倒しされる
- [ ] 前倒し後の必要量がBrewing_Noda、Materials_JPへ整合的に伝播する
- [ ] Forward Plannerが休業週へのP流入を防止する
- [ ] 最終市場Sが維持された場合でも、在庫による吸収を追跡できる

---

## 11. 今後の課題

1. `capacity=None` またはCapacity Mode EnumによるUnlimited / Zero / Finiteの明示化
2. Holiday ClosureとMaintenance Shutdownの共通イベント化
3. 複数休業の優先順位
4. 休業前倒し時のLot優先方針
5. Holiday EventのPSI Graph annotation
6. Closureにより吸収されたLotとCOへ転化したLotの追跡

---

## 12. 設計判断

```text
capacity <= 0
    現行互換上、能力未設定・無制約

explicit_closure
    明示的な完全休業

capacity_override
    部分操業または一時能力変更
```

完全休業はCapacity数値の特殊値としてではなく、Planning Engineが明示的に解釈する供給状態として扱う。

---

## 13. 実装状況（2026-09-27）

依頼書：`requests/RequestLetter_ExplicitClosure_v1r5m0_to_CodeKun.md`（ブランチ `wom-v1r5m0`、基準 `4ed2f14`）。
事実の正本：`docs/development/WOM_Capacity_Trial02_Report.md`。

### 13.1 実装したこと

| 箇所 | 内容 |
|---|---|
| 休業の表現（E1） | `supply_closure` は対象ノード・週の `op_shifts[w] = 0` をセットするだけ。`value` は読まず、能力値も書き換えない（cap_hard＝物理天井のまま）。value が 0／0.1／空以外なら警告 |
| `PlanNode` | `processing_limit(w)`（休業=0.0／未設定=None／それ以外=cap_hard）と `planned_capacity(w)`（休業=0.0／未設定=None／それ以外=cap_soft）を追加。`set_capacity` は渡さなかった側を変更しない（既定引数 None） |
| Backward | `_apply_mom_cap_backward` の休業判定を `not node.is_open(w)` に統一。holiday の休業もここで充填目標 0 になる |
| Mode 4（E3） | leaf の生産週が休業なら、直前の開いている週（無ければ直後）の P に追加。診断 `mode4_closure_shifted` |
| Forward（E2） | 非 push ノードの休業週に届いた P は消さずに次の開いている週の P 末尾へ繰り延べ（`closure_p_deferred`、期間内に無ければ `closure_p_unplaced`） |
| Forward（E4／D4） | push ノードの休業週は P（入庫）を受け入れ、実出荷 0、全量を I に残す（S 計画が 0 でなければ `closure_s_planned`） |
| Step 0b | 非 push は P と `planned_capacity` を比較。push は実出荷と比較 |
| Kitting | 払出予算を `processing_limit` から取る（休業週は 0） |
| その他の読み手 | harvest（休業週は収穫週から除外）、strategic_kpi（休業・未設定の週を稼働率から除外）、`build_capacity_load_report` |
| 表示 | PSI List：CapHard は生値、CapSoft は `planned_capacity`（未設定「—」／休業「0」）。「P vs Capacity Limits」と S3：push は処理量、休業週は灰色背景 |
| データ | soysauce 4モデルの value 0.1→0。0 でも 0.1 でもない supply_closure 行（61行）は effect を `partial_capacity` へ |

### 13.2 `partial_capacity` は移行中（D6）

`partial_capacity` は旧 `supply_closure` と同じ結果を再現する互換 effect である（cap_hard := value、cap_soft 保持、explicit_closures と leaf_in の P シフトの対象）。
部分操業が動かすべきなのは cap_soft であり、LT スキップと P シフトからも外すのが正しい。これは次の依頼で移行する（コード上は `# TRANSITIONAL (D6)`）。

### 13.3 未着手

- 能力値の None／Enum 化（§11-1、D7）：内部の約束「cap = 0 は未設定」は変えていない。新しいコードは `processing_limit` / `planned_capacity` を使う。
- Mode 1〜3 の push スケジュールは休業週を考慮しない（Mode 4 のみ E3 を実装）。
