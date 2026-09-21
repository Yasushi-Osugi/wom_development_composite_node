# Request Letter：Kitting List 段階1（記録のみ・挙動不変）

**起票日**：2026-09-01
**起票者**：大杉
**種別**：**禁足コア変更**（`wom/engine/forward_planner.py`、`wom/model/plan_node.py`）
**対象ブランチ**：`wom-v1r3m0`
**設計文書**：`docs/design/kitting_list_assembly.md`

**本 Letter は段階1のみ。記録するだけで、計画結果は一切変えない。**
段階2（可視化）・段階3（gate keeping の有効化）は別途起票する。

---

## 0. 禁足ルールに基づく承認事項

- [x] Request Letter 起票（本書）
- [ ] 3層テスト（Unit / Integration / golden）緑
- [ ] オーナー（大杉）による差分レビュー
- [ ] **golden 全13ケースが無変化であること**（記録のみのため）

**上記が揃うまでコミットしないこと。**

**本件は `forward_planner.py`（保護対象コア）を変更する。**
ただし変更は**記録の追加のみ**で、既存の計画ロジックには一切触れない
（Fork A パターン。`_actual_s` 追加時と同じ流儀）。

---

## 1. 背景：実証された問題

### 1.1 欠品が完全に隠蔽される

2026-09-01 の実測（`tools/sweep_specs/bom_test_shortage.json`）。

| | base | battery_short | battery_zero |
|---|---|---|---|
| Battery_Supply P_sum | 100 | **40** | **20** |
| Battery_Supply CO_sum | 0 | **1,620** | **2,160** |
| **Vehicle_Assy S_sum** | 100 | **100** | **100** |
| **Vehicle_Assy CO_sum** | **0** | **0** | **0** |
| 下流の `series_md5` | — | **完全一致** | **完全一致** |
| PPC Revenue | $3.2M | **$3.2M** | **$3.2M** |

**バッテリーが需要の1/5しか供給できていないのに、車両は週5台売れ続け、
売上も利益も1ドルも変わらない。**

### 1.2 原因

Lot_ID が供給元を識別しないため、`_match_by_identity` の
`supply_set = set(supply_lots)` で重複が1つに吸収され、
**Tire が単独で全ロットを届けていれば「揃っている」と判定される。**

### 1.3 影響範囲

`supply_role=assembly` で複数の子を持つ InBound ノード。

| モデル | golden | ノード | 子 |
|---|---|---|---|
| `ev-europe-2026` | **対象** | Factory_Import_HU | Battery_HU / Motor_HU / ECU_HU |
| `ev-europe-2026` | **対象** | Factory_Local_DE | Battery_DE / Motor_DE / ECU_DE |
| `ev-thailand-2026_update` | 対象外 | Factory_Local_TH | Platform_Unit_Assy / Motor_Unit_Assy |
| `bom-test-2026` | **対象** | Vehicle_Assy | Tire_Supply / Battery_Supply |

---

## 2. 方針：Lot_ID には触らない

`_match_by_identity` の集合演算や lot_id のスキーマに手を入れると、
Demand Anchored の原則が崩れ、複雑性が一気に上がる。

**「誰がいつ届けたか」を別構造（Kitting List）で横に持つ。**

詳細は `docs/design/kitting_list_assembly.md` §2 を参照。

---

## 3. 実装内容

### 3.1 データ構造

```python
plan_node.kitting[assembly_week][lot_id] = {child_node_name: arrival_week}
```

**命名を厳守すること。** キーの `assembly_week` と、値の `arrival_week` は
意味が異なるため、変数名で明確に区別する。

| | 意味 |
|---|---|
| `assembly_week` | 親ノードが組立を評価する週（親の視点） |
| `lot_id` | 需要 Lot_ID（Demand Anchored。既存のもの） |
| `child_node_name` | 部材を届けた子ノードの名前 |
| `arrival_week` | その部材が親に届いた週 |

**例**：

```python
Vehicle_Assy.kitting[15]["EV_Model_A:US:2026-W15:00001"] = {
    "Tire_Supply": 12,      # 3週前に届いて待っていた
    "Battery_Supply": 15,   # 当週着
}
```

### 3.2 格納先：`PlanNode` の属性

**`ForwardPlanner` の内部辞書ではなく、`PlanNode` に持たせること。**

理由：`_actual_s` は `ForwardPlanner` の内部にあるため、
プランナーが消えると失われ、**GUI から一切参照できない**
（2026-09-01 確認済み）。

`plan_node.kitting` であれば、Network パネルが既に行っている
「`product_name` と `plan_node` で InBound tree を root から辿る」という
同じ経路で読める。**新しい配線が不要。**

### 3.3 存在する場所

**組立親ノードにのみ持たせる。**

| ノード | kitting |
|---|---|
| `supply_role=assembly` の子を持つ InBound ノード | **持つ** |
| 子が `confluence` のみのノード | 持たない（空） |
| 子を持たないノード（leaf_in） | 持たない（空） |
| OutBound ノード | 持たない（空） |

`confluence` は「同種のものが集まる」型であり「揃う」という概念が無いため、
`required` に含めない（設計文書 §4.4）。

### 3.4 記録するタイミング

`forward_planner.py` の `_propagate_to_parent` で、
子から親の `psi4supply[w][P]` へ extend する際に、
**同時に `kitting` へ記録する。**

```python
# 既存（変更しない）
parent.psi4supply[target_w][P].extend(confirmed_s)

# 追加（記録のみ）
for lot_id in confirmed_s:
    parent.kitting[target_w].setdefault(lot_id, {})[child.node_name] = target_w
```

**上記は概念を示すもので、実装は既存コードの構造に合わせてよい。**
`arrival_week` に何を入れるべきか（`target_w` か、子側の週か）は
実装時に判断し、**選んだ理由を報告すること。**

### 3.5 【重要】段階1では gate keeping を行わない

**揃っていない Lot_ID も、これまで通り親の P に入れること。**

```python
# 段階1：判定して記録するが、通す
required = {assembly の子ノード名の集合}
arrived  = set(parent.kitting[w][lot_id].keys())
is_complete = arrived >= required     # ← 記録するだけ

# P への extend は従来通り無条件に行う
```

**これにより計画結果が一切変わらず、golden も無変化になる。**

段階3で `is_complete` が False の Lot_ID を P に入れない形へ切り替える。
そのため、**判定ロジックはこの段階で正しく実装しておくこと。**

### 3.6 判定の実装

以下を、段階3でそのまま使える形で実装すること。

```python
required = {c.node_name for c in node.children
            if c.supply_role != "confluence"}     # assembly の子（既定含む）

arrived  = set(node.kitting[w][lot_id].keys())
missing  = required - arrived                     # 不足部材
is_complete = not missing

# 揃った場合、最も早く届いた部材の滞留週数
if is_complete and node.kitting[w][lot_id]:
    max_wait = w - min(node.kitting[w][lot_id].values())
```

**`missing` が「Battery が遅れたのか Tire が遅れたのか」に直接答える。**

### 3.7 切り替えフラグ

段階3で gate keeping を有効化するためのフラグを、**コード内の定数として置くこと。**

```python
KITTING_GATE_ENABLED = False   # 段階3で True にする
```

`planning_config.csv` へのキー追加は**段階3で判断する。**
段階1では定数で足りる。

### 3.8 本 Letter の範囲外

| 項目 | 扱い |
|---|---|
| **gate keeping の有効化** | **段階3。別 Letter** |
| GUI での可視化 | 段階2。別 Letter |
| auto-debug の判定ルール | 段階2 |
| 部材待ち在庫の I バケットへの反映 | 段階3 |
| 多段の組立（子自身が組立ノード） | 未検討。触らないこと |
| `_actual_s` の GUI 露出 | 別件 |

---

## 4. テスト要件（3層）

### 4.1 Unit

- `PlanNode` に `kitting` 属性が存在し、既定が空であること
- `supply_role=assembly` の子を持つノードでのみ記録されること
- `confluence` のみの子を持つノードでは空のままであること
- leaf_in / OutBound ノードで空のままであること
- `required` が `confluence` を除外して構成されること
- `missing` が正しく算出されること
- `arrived >= required` の判定が正しいこと
- **`KITTING_GATE_ENABLED = False` のとき、P への extend が従来通りであること**

### 4.2 Integration（`bom-test-2026`）

`tools/sweep_specs/bom_test_shortage.json` の3ケースを再実行し、
**kitting の中身を出力して確認すること。**

| ケース | 期待される kitting の状態 |
|---|---|
| `base` | 全 lot で `arrived = {Tire_Supply, Battery_Supply}`、`missing` 空 |
| `battery_short` | 一部の lot で `missing = {Battery_Supply}` |
| `battery_zero` | より多くの lot で `missing = {Battery_Supply}` |

**そして PSI / CO / PPC は3ケースとも従来通りであること**（段階1では挙動不変）。

`missing = {Battery_Supply}` となる lot の件数を報告すること。
これが**現在隠蔽されている欠品の実数**である。

### 4.3 golden（13ケース）

| 状況 | 判定 |
|---|---|
| **全13ケースが無変化** | **正常**。記録のみで挙動を変えていない |
| いずれかが変化した | **異常**。gate keeping が誤って有効になっている疑い。コミットしないこと |

---

## 5. 報告してほしいこと

1. `arrival_week` に何を入れたか（`target_w` か、子側の週か）と、その理由
2. `kitting` の初期化方法（`defaultdict` か、明示的な初期化か）
3. 修正の差分（`git diff`）
4. §4.1 の Unit テスト結果
5. §4.2 の Integration 結果
   - **3ケースの kitting の中身**
   - **`missing = {Battery_Supply}` となる lot の件数**（= 隠蔽されている欠品の実数）
   - PSI / CO / PPC が従来通りであること
6. §4.3 の golden 結果（**全13件無変化**）
7. `ev-europe-2026`（3部材）で kitting がどう記録されるか。
   **3部材とも揃っているか、欠けている lot があるか**
8. `git status`（`data/sample/` が clean であること）
9. 気づいた点

---

## 6. 手順

```
① kitting の初期化方法と arrival_week の定義を決め、報告する（実装前に一度停止）
② PlanNode に kitting 属性を追加
③ _propagate_to_parent に記録処理を追加（gate keeping はしない）
④ 判定ロジック（required / arrived / missing / is_complete）を実装
⑤ §4.1 Unit テスト
⑥ §4.2 Integration（bom_test_shortage の3ケース）
⑦ §4.3 golden 13ケース（全件無変化を確認）
⑧ 大杉の差分レビュー
⑨ 承認後、コミット
```

**⑧の前にコミットしないこと。**
**①の時点で一度報告し、合意を得てから②へ進むこと。**

---

## 7. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `tasklist | findstr python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること
- `capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと
- **`.gitignore` 対象のフォルダに触れないこと**（`git ls-files` で対象を取得）
- コミットメッセージは、指定したもの以外の行（`Co-Authored-By` 等）を
  **勝手に追加しないこと**
- **指示に矛盾を見つけた場合は、実装前に指摘すること**

---

## 8. 参考

- `docs/design/kitting_list_assembly.md`（本件の設計文書）
- `docs/design/design_memo_confluence_assembly_autotuning.md` §B（合流と組立の区別）
- `docs/design/demand_anchored_lot.md`（Rule 2 / Rule 5、lot identity の保全）
- `tools/sweep_specs/bom_test_shortage.json`（問題の実証）
- `requests/request_fix_a1_supply_role_rev2.md`（`supply_role` の導入）
- `39bcb44` / `44e67bf`（Lot_ID の重複が引き起こした過去の障害。**同じ轍を踏まないこと**）

---

## 9. 補足：なぜ段階を分けるか

gate keeping を有効にすると、`ev-europe-2026`（実運用の golden）と
`bom-test-2026` の結果が変わる。**変化の内容を精査してから golden を更新する必要がある。**

一方、記録だけなら挙動が変わらず、**今日から欠品が観測可能になる。**

段階1だけで「静かに誤る」という性質は消える。
その状態で実データを見てから、gate keeping の設計を確定させる。
