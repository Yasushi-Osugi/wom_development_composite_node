# Request Letter：Mode4 Supply-Role Semantics 修正（Backward = WHO / Mode4 = WHEN）

**起票日**：2026-09-04  
**起票者**：大杉  
**種別**：**禁足コア変更**（`wom/engine/push_pull.py`）  
**対象リポジトリ**：`Yasushi-Osugi/wom_v1r3m0_private`  
**対象ブランチ**：`wom-v1r3m0`  
**関連 Request Letter / 設計**：

- `requests/request_fix_a1_supply_role_rev2.md`
- `requests/request_letter_b_bom_qty.md`
- `requests/request_fix_mode4_double_count.md`
- `requests/request_kitting_stage1.md`
- `docs/design/kitting_list_assembly.md`
- `AGENTS.md` §10 Protected Core

---

## 0. 禁足ルールに基づく承認事項

本件は Protected Core である `wom/engine/push_pull.py` の変更を伴う。

- [x] Request Letter 起票（本書）
- [ ] 修正前の影響範囲調査を完了
- [ ] Unit test で修正前に問題を再現（red）
- [ ] 最小差分で実装
- [ ] Unit / Integration / E2E golden の3層テストを実施
- [ ] `ev-europe-2026` の Kitting 診断を再実行
- [ ] オーナー（大杉）による `git diff` レビュー
- [ ] intentional golden 差分の内容をオーナーが確認
- [ ] 承認後にのみ golden 更新・commit

**上記が揃うまで commit しないこと。**

---

## 1. 本 Request の要約

Mode4（`push_lead_time_weeks > 0`）は現在、Demand Anchored Lot_ID 自体は再発番せず再利用しているが、  
その Lot_ID を **decoupling node 配下の全 `leaf_in` にもう一度 1/n 分割している**。

しかし v1r3m0 では、Backward Planning がすでに `supply_role` に基づいて、

- `assembly`：同一 Demand Lot を必要な各 component child へ full copy
- `confluence`：同一種類の供給 sibling 間で Demand Lot を split

という **Supply Responsibility（誰がその Lot を供給するか）** を決定している。

したがって Mode4 が再度 allocation を行うと、Backward で確定した Supply-Role semantics を破壊する。

今回、以下を canonical rule として固定する。

> **Backward Planner determines WHO supplies each Demand Anchored Lot.**  
> **Mode4 determines WHEN those already-assigned suppliers produce it.**

日本語で言えば、

> **Backward Planning が「誰が供給するか」を決め、  
> Mode4 は「いつ生産するか」だけを前倒しする。**

Mode4 は Supply Allocation Planner ではなく、  
**Backward で確定済みの recipient membership を維持した Lot-identity-preserving Re-timing Planner** とする。

---

## 2. 現行 v1r3m0 の前提

実装前に必ず最新 branch のコードで以下を確認すること。

### 2.1 Backward の `supply_role` semantics

`wom/engine/backward_planner.py` の `_propagate_to_children()` では、現在、

```text
assembly child
    → parent の all_lots を各 child へ full copy

confluence siblings
    → parent の all_lots を siblings 間で divmod split
```

となっている。

`assembly` / `confluence` の判定は **junction（parent → children）単位**で行われる。

### 2.2 `supply_role` は child 側に持つ edge semantics

`wom/model/plan_node.py` では、

```text
supply_role="assembly"
```

が default であり、CSV の blank も assembly として扱う。

意味は、

> 「この child の需要は、同じ parent の siblings との関係でどのように解釈されるか」

であり、単純な leaf 属性ではなく **parent-child edge 相当の意味**を持つ。

### 2.3 `bom_qty` は Lot_ID list を増殖させない

`bom_qty` は physical quantity interpretation の係数であり、

```text
タイヤ4本 / 車1台
```

であっても同じ Vehicle Lot_ID を4回 list に入れない。

今回もこの原則を維持する。

### 2.4 Mode4 Lot_ID identity fix は維持する

Mode4 は既に、

```text
未来需要の「数量」だけを読んで新しい Lot_ID を作る
```

方式から、

```text
ref.psi4demand[future_w][S] に存在する
既存 Demand Anchored Lot_ID をそのまま使う
```

方式へ修正済みである。

この原則を変更しない。

### 2.5 Mode4 double-count fix は維持する

`request_fix_mode4_double_count.md` により、Mode4 の leaf-in assignment 前に、

```python
for leaf_node in leaf_in_nodes:
    for w in range(n_weeks):
        leaf_node.psi4supply[w][P] = []
```

相当の全週 clear が入っている。

これは Step 5 の自然コピーを残さず、

> **re-timing, not duplication**

を成立させるための重要な修正である。

**今回この clear 処理を削除・移動・弱体化しないこと。**

### 2.6 Kitting Stage 1 は record-only

`PlanNode.kitting` と `tests/test_kitting_stage1.py` は既に存在する。

今回 Kitting は **Mode4 修正結果の観測装置**として使う。

Gate keeping は有効化しない。

---

## 3. 確定した根本原因

### 3.1 現在の Mode4

現行 `wom/engine/push_pull.py` の Mode4 branch は概念的に以下。

```python
future_w = w + lt_weeks
lots = list(ref.psi4demand[future_w][S])

base, remainder = divmod(len(lots), n_leaves)

for leaf in leaf_in_nodes:
    leaf_lots = contiguous_slice(lots)
    leaf.psi4supply[w][P] = leaf_lots
```

Lot_ID 自体は保存されるが、  
**Backward が決めた「どの leaf がどの Lot を担当するか」は保存されない。**

Mode4 が全 leaf-in を flat に並べて再 allocation しているためである。

---

## 4. EV Europe で発生している意味上の破綻

`ev-europe-2026` Import 側は概念上、

```text
Factory_Import_HU
 ├─ Battery_HU
 ├─ Motor_HU
 └─ ECU_HU
```

であり、3部材は `assembly` である。

Vehicle Demand Lot が、

```text
A B C D
```

なら Backward の正しい意味は、

```text
Battery_HU : A B C D
Motor_HU   : A B C D
ECU_HU     : A B C D
```

である。

ところが Mode4 が flat split を行うため、例えば、

```text
Battery_HU : A
Motor_HU   : B
ECU_HU     : C D
```

のようになる。

これは実質的に、

```text
EV 100台に
Battery 33台分
Motor   33台分
ECU     34台分
```

という意味になり、assembly ではなく confluence と同じ配分になってしまう。

Stage 1 Kitting によって、調査時点では `Factory_Import_HU` で

```text
complete = 0 / 7,945
```

という gross symptom が観測された。

3 component の Lot_ID 集合が互いにほぼ disjoint であり、  
union は親需要に近いが intersection が成立しない。

今回の fix は、この **Mode4 による Supply Responsibility の破壊**を除去する。

---

## 5. 設計判断：Supply Allocation の Truth は Backward に一本化する

### 5.1 Mode4 に第二の `supply_role` router を作らない

以下のような実装は行わない。

```python
if leaf.supply_role == "assembly":
    full_copy(...)
elif leaf.supply_role == "confluence":
    split(...)
```

一見単純だが、canonical design として不適切。

理由は、`supply_role` が leaf 単体ではなく junction semantics だからである。

将来、

```text
Vehicle
 ├─ Battery_Module              assembly
 │    ├─ Supplier_A             confluence
 │    └─ Supplier_B             confluence
 ├─ Motor                       assembly
 └─ ECU                         assembly
```

という tree では、

```text
Vehicle → Battery / Motor / ECU
    = assembly

Battery → Supplier_A / Supplier_B
    = confluence
```

となる。

final leaf だけを見ても、正しい allocation は再構築できない。

Backward は tree を junction ごとに辿るため、この意味論を既に解決している。

したがって、

> **Mode4 must consume the result of Backward allocation,  
> not re-interpret the allocation policy.**

---

## 6. Required Semantics：Mode4 は WHO を変えず、WHEN だけ変える

Mode4 では二つの情報を分離する。

### 6.1 WHEN：production timing

従来どおり、

```python
future_w = w + config.push_lead_time_weeks
future_lots = ref.psi4demand[future_w][S]
```

を timing source とする。

つまり、

```text
Demand reference week = d
Mode4 production week = d - push_lead_time_weeks
```

という contract は変更しない。

### 6.2 WHO：recipient membership

各 `leaf_in` がどの Demand Anchored Lot_ID を担当しているかは、  
Backward 完了後の、

```python
leaf.psi4demand[*][S]
```

を source of truth とする。

### 6.3 【重要】recipient membership は horizon-wide に取得する

次のように **同じ week index だけで判定してはならない**。

```python
# NG
lot_id in leaf.psi4demand[future_w][S]
```

Backward では child ごとに、

- `lt_wks`
- `ss_wks`
- operating calendar / closure skip

が異なり得るため、同じ Demand Anchored Lot_ID が leaf 側では別weekに配置される。

したがって、recipient判定は planning horizon 全体で行う。

概念：

```python
leaf_membership = {}

for leaf in leaf_in_nodes:
    leaf_membership[leaf.node_id] = {
        lot_id
        for week in range(n_weeks)
        for lot_id in leaf.psi4demand[week][S]
    }
```

Mode4 の各production weekでは、

```python
future_lots = list(ref.psi4demand[future_w][S])

leaf_lots = [
    lot_id
    for lot_id in future_lots
    if lot_id in leaf_membership[leaf.node_id]
]
```

とする。

これにより、

### assembly

Backward:

```text
Battery membership = {A,B,C,D}
Motor   membership = {A,B,C,D}
ECU     membership = {A,B,C,D}
```

Mode4:

```text
Battery.P = A B C D
Motor.P   = A B C D
ECU.P     = A B C D
```

### confluence

Backward:

```text
Supplier_A membership = {A,C}
Supplier_B membership = {B,D}
```

Mode4:

```text
Supplier_A.P = A C
Supplier_B.P = B D
```

### mixed / multi-level

Backward が最終 leaf recipient を既に解決しているため、  
Mode4 は tree semantics を再計算せず、その membership をそのまま使える。

---

## 7. 推奨実装アルゴリズム

以下は exact code prescription ではない。

既存 style / helper / typing に合わせて最小差分で実装すること。

```python
# Mode4 branch only

ref = demand_ref_node if demand_ref_node is not None else decoupling_node
lt_weeks = config.push_lead_time_weeks

# Existing double-count protection: KEEP THIS.
for leaf_node in leaf_in_nodes:
    for w in range(n_weeks):
        leaf_node.psi4supply[w][P] = []

# Backward result is the source of truth for WHO.
leaf_membership = {}
for leaf_node in leaf_in_nodes:
    membership = set()
    for dw in range(n_weeks):
        membership.update(leaf_node.psi4demand[dw][S])
    leaf_membership[leaf_node.node_id] = membership

# Mode4 decides WHEN.
for w in range(n_weeks):
    future_w = w + lt_weeks
    if future_w >= n_weeks:
        continue

    future_lots = list(ref.psi4demand[future_w][S])
    if not future_lots:
        continue

    wk_label = self.sc_tree.week_labels[w]

    for leaf_node in leaf_in_nodes:
        membership = leaf_membership[leaf_node.node_id]

        # Preserve future_lots order.
        leaf_lots = [
            lot_id
            for lot_id in future_lots
            if lot_id in membership
        ]

        if not leaf_lots:
            continue

        leaf_node.psi4supply[w][P] = list(leaf_lots)
        result.record(
            leaf_node.node_id,
            wk_label,
            len(leaf_lots),
        )

return result
```

### この変更の本質

Before:

```text
future Demand Lots
        ↓
Mode4 が flat 1/n allocation
        ↓
leaf_in
```

After:

```text
Backward Planning
        ↓
WHO = leaf recipient membership
        ↓
Mode4
        ↓
WHEN = LT shift only
        ↓
same recipient leaf_in
```

つまり、

> **remove Mode4 re-allocation, preserve Mode4 re-timing.**

---

## 8. 必ず維持する Invariants

### 8.1 Demand Anchored Lot_ID

Mode4 で新しい Lot_ID を発番しない。

`LotIDGenerator` を Mode4 path で使わない。

### 8.2 Lot_ID string

Lot_ID の文字列を変更しない。

### 8.3 Demand truth

Mode4 は `psi4demand` を書き換えない。

Backward result は read-only source とする。

### 8.4 Recipient truth

recipient assignment は Backward の結果を再利用する。

Mode4 自身は allocation policy を決定しない。

### 8.5 Timing

```text
production week w
    ← reference demand week w + push_lead_time_weeks
```

を維持する。

### 8.6 EOL / horizon

```text
future_w >= n_weeks
```

では production 0。

既存の natural EOL stop を維持する。

### 8.7 Mode4 P clear

`request_fix_mode4_double_count.md` の全週 P clear を維持する。

### 8.8 Lot order

output lot list は `future_lots` の順を維持する。

membership set を list 化して order を作り直さない。

### 8.9 No duplicate inside one leaf/week

assembly では **同じLotが複数leafに存在することは正常**。

一方、同じleaf/weekに、

```text
[A, A]
```

と同じDemand Lot_IDを重複appendしない。

### 8.10 `bom_qty`

`bom_qty > 1` でも Lot_ID list を N 倍しない。

### 8.11 Modes 1–3

Mode1 / 2 / 3 の挙動は変更しない。

### 8.12 `mom_ref_node_id`

Mode4 で `mom_ref_node_id` が現在どう扱われているかは本件の範囲外。

今回同時に修正しない。

---

## 9. 実装前の影響範囲調査【必須】

コードを変更する前に、`data/sample/` 全体について  
`push_config.csv` の `push_lead_time_weeks > 0` を抽出し、以下を一覧化すること。

| Case | SKU | decoupling node | LT | leaf_in count | topology | current Mode4 risk |
|---|---|---|---:|---:|---|---|
| ... | ... | ... | ... | ... | single / assembly / confluence / mixed | ... |

### 分類

#### A. single leaf

Mode4 flat split は実質 no-op。

今回のfixで原則結果不変。

#### B. multi-leaf assembly

今回の主対象。

現状は誤って 1/n split しているため、修正後に leaf-level P が intentional に変化する。

#### C. multi-leaf confluence

Backward recipient membership を維持する。

現行 Mode4 の contiguous split と偶然一致しているケースでも、  
「Mode4が再計算してよい」という意味ではない。

#### D. mixed / multi-level

特に報告すること。

今回の設計の有効性を確認する重要ケースである。

### 報告

**修正前に「どの golden case が変化し得るか」を確定してから実装すること。**

---

## 10. Unit Test 要件

新規 test file は原則、

```text
tests/test_push_pull_mode4_supply_role.py
```

を推奨する。

ただし既存test構造に統合した方が明確であれば、

- `tests/test_step8_push_pull.py`
- `tests/test_push_pull_mode4_double_count.py`

へ追加してもよい。

### U1 — assembly full recipient preservation

Synthetic setup:

```text
ref future demand = [A,B,C,D]

Backward leaf membership:
Battery = {A,B,C,D}
Motor   = {A,B,C,D}
ECU     = {A,B,C,D}
```

Expected:

```text
Battery.P = [A,B,C,D]
Motor.P   = [A,B,C,D]
ECU.P     = [A,B,C,D]
```

**修正前はこのtestが red になること。**

---

### U2 — confluence recipient preservation

Mode4が独自splitしないことを明確にするため、  
unitでは意図的に非contiguous membershipをseedしてよい。

```text
ref future demand = [A,B,C,D]

Supplier_A membership = {A,C}
Supplier_B membership = {B,D}
```

Expected:

```text
Supplier_A.P = [A,C]
Supplier_B.P = [B,D]
```

Mode4が `[A,B] / [C,D]` へ並べ直してはならない。

---

### U3 — mixed / multi-level final-leaf membership

Concept:

```text
Final_Assy
 ├─ Component_X
 │    ├─ Supplier_X1
 │    └─ Supplier_X2
 ├─ Component_Y_leaf
 └─ Component_Z_leaf
```

Backward membership:

```text
Supplier_X1      = {A,C}
Supplier_X2      = {B,D}
Component_Y_leaf = {A,B,C,D}
Component_Z_leaf = {A,B,C,D}
```

Expected Mode4:

```text
Supplier_X1.P      = [A,C]
Supplier_X2.P      = [B,D]
Component_Y_leaf.P = [A,B,C,D]
Component_Z_leaf.P = [A,B,C,D]
```

**Mode4 codeに `supply_role` branchを追加せず passすること。**

---

### U4 — horizon-wide membership

Backward の leaf demand week と Mode4 reference week をずらす。

例：

```text
ref demand:
W10 = [A]

supplier leaf demand:
W07 = [A]
```

Mode4:

```text
push_lead_time_weeks = 2
```

Expected:

```text
supplier.P[W08] contains A
```

`leaf.psi4demand[W10][S]` だけを見る implementation は fail すること。

---

### U5 — no new Lot_ID

Mode4後の全P Lotについて、

```text
Mode4 produced Lot_ID
    ⊆ existing Demand Anchored Lot_ID universe
```

を確認する。

---

### U6 — double-count fix regression

既存、

```text
tests/test_push_pull_mode4_double_count.py
```

を全てgreenにする。

特に、

- P_sum conservation
- stale week absence
- `mode_only=True`
- LT < physical tau の genuine shortage

を壊さない。

---

### U7 — EOL / horizon

`future_w >= n_weeks` では production 0。

---

### U8 — no duplicate within leaf/week

同一 leaf/week に同じ Lot_ID が2回入らない。

---

## 11. Backward Supply-Role Regression【必須】

既存、

```text
tests/test_backward_supply_role.py
```

を必ず実行する。

今回 Backward Planner は変更しないため、

```text
assembly = full copy
confluence = split
blank/default = assembly
```

は完全にgreenであるべき。

failした場合は今回のscope外へのside effectを疑い、commitしない。

---

## 12. BOM Regression【必須】

既存、

```text
tests/test_bom_qty.py
tests/test_ppc_bom_qty.py
```

を実行する。

Mode4修正を理由に `bom_qty` と Lot list identity の関係を変えない。

---

## 13. Integration Test：CSV → Backward → Copy → Mode4

Synthetic objectだけではなく、  
実際の CSV / loader / PlanNode / Backward / `copy_demand_to_supply()` / Mode4 の経路を通すこと。

最低限、以下を確認する。

1. CSV `supply_role` が PlanNode にロードされる
2. Backward 後の leaf recipient membership が期待どおり
3. Step 5 copy 後に Mode4 setup
4. Mode4 が同じ recipient membership を保持
5. production week だけが Mode4 LT で変化
6. `psi4demand` は不変
7. no stale P

---

## 14. EV Europe Integration / Kitting 再診断【重要】

`ev-europe-2026` を実行し、

```text
Factory_Import_HU
Battery_HU
Motor_HU
ECU_HU
```

について、修正前後を比較する。

### 14.1 Lot set

修正前に見られた、

```text
Battery / Motor / ECU の Lot_ID 集合がほぼdisjoint
```

という pattern が消えること。

Backward で Vehicle Lot `A` が3 component recipientへ存在するなら、  
Mode4 production後も、

```text
A ∈ Battery_HU.P
A ∈ Motor_HU.P
A ∈ ECU_HU.P
```

となること。

### 14.2 Kitting

既存、

```text
tests/test_kitting_stage1.py
```

および Stage 1 diagnostics を使用する。

調査時点の、

```text
complete = 0 / 7,945
```

がどう変化するかを報告する。

### 14.3 重要：7,945 / 7,945 を acceptance にしない

Mode4 gross semantics error を除去した後にも、

- horizon boundary
- component LT差
- capacity delay
- operating calendar
- genuine shortage
- Forward behavior

による incomplete kit が残る可能性がある。

したがって、

```text
remaining missing
```

について component / week / cause を分類して報告すること。

**Kittingを「答えを作る機能」ではなく「正しくなったかを観測する機能」として使う。**

---

## 15. Stage 1 Kitting の境界

今回も、

```text
KITTING_GATE_ENABLED = False
```

相当の record-only 状態を維持する。

今回行わないこと：

- incomplete kit を止める
- parent P への flow をgateする
- Stock Yardへ保留する
- Yard inventoryを作る
- productionを再allocationする

正しい順序：

```text
Mode4 semantics fix
        ↓
Stage 1 Kittingで再観測
        ↓
remaining missing原因を分類
        ↓
Stage 2 visualization
        ↓
Stage 3a Stock Yard + Kitting Gate
```

---

## 16. E2E Golden【必須】

`AGENTS.md` の Protected Core rule に従い、

```text
pytest tests/test_golden.py
```

および現行 golden harness を実行する。

### 16.1 golden件数は実ファイルを基準にする

`AGENTS.md` 内の古い件数表記を hard-code しない。

実行時点の、

```text
tests/golden/*.json
```

を列挙し、**current branchの全golden**を対象にする。

v1r3m0 では `bom-test-2026` も golden に含まれているため、  
過去の「12ケース」という固定記述だけを根拠にしないこと。

### 16.2 判定

#### Non-Mode4 case

原則 unchanged。

変化したら regression として調査。

#### Single-leaf Mode4 case

recipient ambiguity がないため原則 unchanged。

#### Multi-leaf assembly Mode4 case

今回の intentional behavior change 対象。

leaf-level PSI / P_sum / series md5 等が変化し得る。

#### Confluence Mode4 case

Backward allocation membership と一致することを確認。

aggregate totalが同じでも recipient assignment diff があれば意味を確認する。

### 16.3 Golden JSON は先に更新しない

まず、

```text
old vs new diff
```

を報告する。

**オーナーが「今回の semantics fix による正しい差分」と確認するまで golden JSON を更新しないこと。**

---

## 17. Result Accounting に関する注意

`PushSetupResult.record()` は leaf production event qty を加算している。

assembly修正後、

```text
Vehicle Demand Lots = 100

Battery production events = 100
Motor production events   = 100
ECU production events     = 100
```

となるので、

```text
push_lots_total = 300
```

のように unique finished-goods Demand Lot 数より大きくなる可能性がある。

これは、

> 3種類の component production event を数えている

のであれば正常。

今回、

- finished-goods unique lot 数に合わせて deduplicate
- `push_lots_total` の意味を変更
- UI表示を変更

は行わない。

もし既存表示が `push_lots_total` を「完成品数量」と解釈しているなら、  
**別issueとして報告すること。**

---

## 18. Edge Case：recipient membership が0件のLot

`ref.psi4demand[future_w][S]` にある Lot_ID が、  
対象 decoupling subtree のどの leaf-in Backward membership にも存在しない場合、

**1/n split や round-robin fallback を行ってはならない。**

それをすると Mode4 が再び Supply Allocation Policy を作ることになる。

まず、

- planning horizon
- `past_due_lots`
- LT / SS offset
- capacity carry-back
- tree / decoupling scope

を確認する。

Target integration case で実際に発生する場合は、

```text
lot_id
reference week
decoupling node
leaf membership
past_due / horizon state
```

を報告する。

**本Request内で新しいfallback policyを発明しないこと。**

---

## 19. 今回変更してよいファイル

### Primary

```text
wom/engine/push_pull.py
```

### Tests

必要に応じて：

```text
tests/test_push_pull_mode4_supply_role.py     # 新規推奨
tests/test_step8_push_pull.py                 # 既存testへ統合する場合
tests/test_push_pull_mode4_double_count.py    # regression追加が自然な場合
```

### Documentation

実装結果・追加知見を残す必要がある場合：

```text
requests/request_fix_mode4_supply_role_semantics.md
docs/design/...
```

ただし design 文書を大きく書き換えない。

---

## 20. 今回原則変更してはいけない Protected Core

以下は今回原則変更しない。

```text
wom/engine/backward_planner.py
wom/engine/forward_planner.py
wom/engine/plan_copy.py
wom/model/plan_node.py
wom/model/sc_tree.py
```

これらへの変更が必要と判断した場合は、

> **実装を拡張せず、理由を先に報告すること。**

本Requestの authorization は `push_pull.py` の Mode4 recipient semantics 修正に限定する。

---

## 21. 本 Request の範囲外

以下を同時に行わない。

| 項目 | 理由 |
|---|---|
| Kitting Gate 有効化 | Stage 3a の別Request |
| Stock Yard実装 | Stage 3a |
| Kitting GUI | Stage 2 |
| Mode1–3再設計 | 別件 |
| Mode4 `mom_ref_node_id` 問題 | 別件 |
| `supply_role` policy変更 | A1で確定済み |
| confluence能力比例配分 | 将来拡張 |
| BOM quantity semantics変更 | Letter Bで確定済み |
| Lot_ID schema変更 | Demand Anchored原則を守る |
| Forward `_match_by_identity` 改修 | 今回は触らない |
| EV CSVでのworkaround | engine semanticsを直すべき |
| unrelated refactor / rename | 禁止 |

---

## 22. Acceptance Criteria

以下をすべて満たすこと。

- [ ] 対象repo / branch が `Yasushi-Osugi/wom_v1r3m0_private` / `wom-v1r3m0`
- [ ] 実装前 impact scan を報告
- [ ] 修正前に assembly Mode4 test が red
- [ ] `push_pull.py` の Mode4 branch を最小変更
- [ ] Mode4 の flat `divmod(..., n_leaves)` が recipient決定に使われなくなった
- [ ] Mode4 に第二の `supply_role` router を追加していない
- [ ] WHO は Backward leaf membership から取得
- [ ] membership は horizon-wide
- [ ] WHEN は既存 `future_w = w + LT` を維持
- [ ] Mode4で新規 Lot_ID を生成していない
- [ ] Lot_ID string を変更していない
- [ ] existing all-week P clear を維持
- [ ] Mode1–3 unchanged
- [ ] `mom_ref_node_id` semantics unchanged
- [ ] `tests/test_backward_supply_role.py` green
- [ ] `tests/test_bom_qty.py` green
- [ ] `tests/test_ppc_bom_qty.py` green
- [ ] `tests/test_push_pull_mode4_double_count.py` green
- [ ] new Mode4 supply-role Unit tests green
- [ ] CSV→Backward→Copy→Mode4 Integration green
- [ ] `ev-europe-2026` の disjoint component Lot pattern が解消
- [ ] Kitting Stage1 の結果を再報告
- [ ] Kitting Gate remains OFF
- [ ] current branch の全 golden を実行
- [ ] intentional diff と unexpected diff を分離して報告
- [ ] golden JSONはオーナー承認前に更新していない
- [ ] `git diff` をオーナーへ提示
- [ ] `git status` を提示
- [ ] sample data が意図せず変更されていない

---

## 23. 実装後に報告してほしいこと

以下の順序で報告すること。

1. **Baseline**
   - current branch / HEAD
   - `git status`
   - prerequisite確認

2. **Impact Scan**
   - 全 Mode4 sample case
   - leaf count
   - topology分類
   - 変化予想

3. **Root Cause Confirmation**
   - 現行 Mode4 の flat split 箇所
   - Backward recipient membershipとの不一致

4. **Implementation Diff**
   - `git diff -- wom/engine/push_pull.py`
   - test diff

5. **Unit**
   - 修正前 red
   - 修正後 green

6. **Regression**
   - `test_backward_supply_role.py`
   - `test_bom_qty.py`
   - `test_ppc_bom_qty.py`
   - `test_push_pull_mode4_double_count.py`
   - relevant Step8 tests

7. **EV Europe**
   - Battery / Motor / ECU の Lot set comparison
   - intersection / union
   - Kitting complete / incomplete
   - remaining missing component / week / cause

8. **Golden**
   - 全 current golden case
   - unchanged cases
   - changed cases
   - 各diffの説明
   - **golden file自体は未更新の状態で報告**

9. **Final**
   - `git status`
   - 気づいた点
   - scope外で新たに発見した問題

---

## 24. 実装手順

```text
① latest wom-v1r3m0 / clean working tree を確認
② §9 Mode4 impact scan を実施
③ focused Unit test を追加し、修正前 red を確認
④ push_pull.py Mode4 を最小修正
⑤ focused Unit / Regression を実行
⑥ CSV integration を実行
⑦ ev-europe-2026 + Stage1 Kitting を再診断
⑧ current golden 全件を実行
⑨ diff と結果を大杉へ報告
⑩ 大杉が内容をレビュー
⑪ 承認された intentional golden のみ更新
⑫ 最終test
⑬ commit
```

---

## 25. 設計上の最終原則

今回の修正で WOM の責務境界を次のように固定する。

```text
Demand Anchored Lot
        ↓
Backward Planning
        ↓
WHO supplies this Lot?
        │
        ├─ assembly  → all required component branches
        └─ confluence → selected / allocated supplier branch
        ↓
recipient membership is fixed
        ↓
Mode4
        ↓
WHEN should that already-assigned supplier produce?
        ↓
Forward Planning
        ↓
Stage 1 Kitting observes whether all required components arrived
```

したがって、今後の canonical statement は：

> **Backward decides WHO.  
> Mode4 decides WHEN.  
> Kitting observes WHETHER THE ASSEMBLY IS COMPLETE.**

この3つの責務を混ぜないこと。

---

**End of Request Letter**
