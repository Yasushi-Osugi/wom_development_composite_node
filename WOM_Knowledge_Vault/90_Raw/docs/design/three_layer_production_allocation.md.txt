# WOM 三層生産配分：Management / Demand / Supply の設計記録

**設計記録のみ・実装なし（2026-08-20）。** branch `wom-v1r3m0`。エンジン・GUI・CSV スキーマはすべて無変更。

本文書は `docs/design/lot_id_traceability_and_coverage_views.md`（三層可視化）と対になる。前者が「モデルが正しいことをどう示すか」を扱うのに対し、本書は「生産配分をどこで、どう決めているか」を扱う。

---

## 0. 要約

WOM には**三つの異なる層に、それぞれ独立した「配分」の仕組み**がある。

| 層 | 実装 | 決めること | 決め方 |
|---|---|---|---|
| **Management** | `wom/allocation/`＋`ask_global_allocation` | 限られた能力を、どの市場にどの比率で配分するか | 231格子点の全数評価 → 利益地形図 |
| **Demand** | `lane_assignment.csv` → Backward Phase 2 | どのチャネルの需要を、どの MOM に着地させるか | **静的な 1:1 固定テーブル** |
| **Supply** | `ForwardPlanner._actual_s` | 実際に出荷できたロットをどう集約するか | Lot_ID identity-matching |

**三層はいずれも「配分」を扱うが、互いに接続されていない。** これが本書で特定した最大の設計課題である。

---

## 1. Management 層：`ask_global_allocation`

**設計文書（正典）**：`requests/global-allocation-request-letter.md`（Rev 3）、`docs/design/ask_global_allocation_spec.md`（v0r3）
**参照実装**：`tools/proto_terrain2.py`

- 限られた醸造能力を **国内 / 米国 / 欧州の3市場**にどう配分するかを、配分比率単体 (x_JP, x_US, x_EU) の **231格子点を全数評価**して利益地形として描く。
- **LP 最適化はしない。** 面を出すことが目的で、経営判断に要るのは最適点でなく地形。
- **Planning Engine・保護コアは一切不変。** 実現方法は `demand_forecast.csv` の配分を書き換える case1 方式であり、**エンジンの外側から需要を差し替えている**。
- 出力：`ga_profit_surface` / `ga_switching_point` / `ga_plateau` / `ga_interaction` 等（`output/allocation/`）。

**重要**：この層の配分は **Planning Engine の内部には存在しない**。エンジンにとっては「与えられた需要」でしかない。

---

## 2. Demand 層：`lane_assignment.csv`

### 2.1 スキーマと実体

```
sku_id, leaf_node_name, mom_node_id, priority
Apparel_Outsourced_S1, Sales_US_TX_I, IN:mom:Factory_Import_CN:Apparel_Outsourced_S1, 1
```

- `mom_node_id` は**完全修飾 node_id**（`side:type:name:product`）。`sc_tree_master.csv` の `parent_node` が短い `node_name` を使うのとは形式が異なる。
- ローダ：`wom/engine/lane_assignment.py` の `LaneTable.from_csv()`
- 格納：`LaneTable._table: Dict[(sku_id, leaf_node_name), mom_node_id]`
- 呼び出し元：`wom/gui/app.py:5142`（GUI）、`tools/run_headless_from_folder.py:176`（headless）。いずれも `ctx["lane_table"]` に格納。
- **参照は Backward のみ。** `BackwardPlanner.__init__` が `lane_table` を受け取り、`run()` の Phase 2 で `resolve()` を呼ぶ。`ForwardPlanner` には `lane_table` 引数自体が存在しない。

### 2.2 これが「二本の木の接続」を担っている

`sc_tree_master.csv` は MOM root と supply_point root の間に親子関係を持たない（両方とも `parent_node=""` の独立 root）。**木の形は `sc_tree_master.csv` が定義し、二本の木の接続は `lane_assignment.csv` が担う**という役割分担になっている。

`(sku_id, leaf_node_name)` 粒度で MOM を指定できるため、**市場ごとに別工場へ振り分けることは可能**である（Multi-MOM 構成）。apparel-us-2026 では全48行が単一 MOM を指しているため分岐が発生していないだけで、スキーマとしては分岐を表現できる。

```
S1, Sales_US_TX_I, IN:mom:Factory_VN:...   ← TX向けはベトナム工場
S1, Sales_US_CA_I, IN:mom:Factory_CN:...   ← CA向けは中国工場
```

### 2.3 `resolve()` の解決順序

```
exact leaf match  →  region fallback  →  None（呼び出し側が primary MOM へ）
```

**いずれの段階でも MOM の cap_hard／残余能力を参照しない。**

### 2.4 【重要】`priority` 列は未実装

- `LaneAssignment.priority` フィールドに `int(row.get("priority") or 1)` としてパースはされる（`lane_assignment.py:160`）
- しかし `self._rows` にも `self._table` にも反映されず、`resolve()` / `get_mom_node_id()` を含む全メソッドで `.priority` を参照する箇所は**ゼロ**
- ファイル自身の docstring に「priority: (future use)」と明記（`lane_assignment.py:50`）

**同一 `(sku_id, leaf_node_name)` に複数行がある場合**：辞書内包表記のため **CSV で後に書かれた行が先の行を単純に上書き**する（"Last row wins on duplicate keys"）。priority 値の大小は一切関与しない。

**能力不足時のフェイルオーバーは存在しない。** ルーティング決定は Backward Phase 2 で一度だけ行われ、この時点では Phase 3b の `_apply_mom_cap_backward`（能力クリップ）はまだ実行されていない。後段で能力が足りなければ、**別 MOM へ回らず、同じ MOM の CO（欠品）になる**（`backward_planner.py:416-469`。cap 超過分を CO へ積む／前週へ carry-back するのみで、他ノードへの再配分ロジックは無い）。

**実装の正確な要約：1:1 の固定ルーティングテーブル。動的フェイルオーバーなし、比率按分なし、priority 無視。**

---

## 3. Supply 層：`ForwardPlanner._actual_s`

- `S` と `CO` は「計画値」として**一切書き換えない**（S の一意性を守る）。物理的に実際に出荷される Lot_ID は `ForwardPlanner._actual_s: Dict[node_id, Dict[w, List[lot_id]]]` という別チャネルに保持する。
- `_propagate_to_child` / `_propagate_to_parent` / MOM→supply_point ブリッジは、`psi4supply[w][S]` ではなく `self._actual_s` を参照する。
- Forward Phase 2（`forward_planner.py:177-186`）のブリッジは、`SCTree.prod_tree_dict_IN[prod_nm]` / `prod_tree_dict_OT[prod_nm]` という **product_name キーの辞書引き**で二本の木を接続する。`sc_tree_master.csv` の `parent_node` 列は見ていない。
- **`lane_assignment.csv` は参照しない**（`ForwardPlanner` に `lane_table` 引数が無く、grep しても該当ゼロ）。

### なぜ Forward は lane を引き直さないのか

**「どの MOM がどのロットを持つか」は Backward Phase 2 で既に Lot_ID に刻印済み**だから。Forward は各 MOM が実際に出荷できたロットを product_name 一致で全 MOM 分プールし、`supply_point.P` へ戻すだけでよい。

これは Demand Anchored Lot 設計の直接的な効用である。ロットが自分の帰属を持ち歩くため、二度目のルックアップが不要になる。

---

## 4. CLAUDE.md の記述訂正

### 4.1 L931 の表現は実装を美化している

```
現状: | Multi-MOM 配分比率 | lane_assignment.csv | 物流コスト比率・製造コスト比率 |
修正: | Multi-MOM 静的チャネル振分け | lane_assignment.csv（priority 未実装・能力連動の動的再配分なし） | 物流コスト比率・製造コスト比率 |
```

実装は「比率」ではなく**チャネル単位の 1:1 固定割当て**。複数チャネルが異なる MOM に割り当てられた結果として、集計上「比率のように見える」production distribution が生まれるに過ぎない。

### 4.2 L503 と L931 は矛盾していない（別レイヤーの話）

| | 対象 | 記述の正しさ |
|---|---|---|
| L503「ブリッジは product_name 一致」 | **Forward** Phase 2（二本の木の実行時接続） | 正しい |
| L931「Multi-MOM 配分比率 = lane_assignment」 | **Backward** Phase 2（需要ロットの MOM 振分け） | 対象は正しいが「比率」が不正確 |

### 4.3 既に記録されている原則（再掲・散在している）

- **L1142（v1r2m2）**：「Backward の Demand Allocation が"親心"で全部やる。Forward Planning は `I(W)=I(W-1)+P−S` を前へ回すだけで、決して時間を遡及しない。」
  - 成立経緯も記録済み：Forward 側に `_apply_operating_calendar_shift` を入れたところ soysauce-jpy お盆デモで cap_hard を超える 2143 のスパイクが出て、大杉さんの「Forward は遡及するな」の指摘で撤回した。
- **L656（v1r0m3）**：BackwardPlanner は純粋な需要逆伝播（LT offset のみ）。cap_hard enforcement は `_apply_mom_cap_backward`（MOM 専任）と ForwardPlanner に移譲。「上流ノードは cap 前の全量需要を受け取り、ForwardPlanner が supply allocation を判断できる」
- **L354-359（v1r0m4）**：`_actual_s` の新設と、S/CO を書き換えない設計

**これら三箇所が分散しているため、「二層配分は記録されていないのでは」という疑問が生じた。** 本文書はその集約を兼ねる。

---

## 5. `lt_wks` の意味論（2026-08-20 の実測で確定）

三層配分とは別件だが、同日の検証で確定したため記録する。

### 5.1 `lt_wks` はノード属性ではなくエッジ属性

**「親から自分への到達時間（物流LT）」**であり、そのノードでの加工時間ではない。

実測（apparel-us-2026 / Apparel_Outsourced_S1、Start=2025-W02 / 126週）：

```
SP_Apparel_Outsourced (lt=1w) : S/P = W45〜W50
DC_Import_Buffer      (lt=4w) : P   = W49〜W54   ← ちょうど4週後
```

InBound 側も同じ規則。ただし木の向きが逆（親が下流）なので、`Fabric_CN` の `lt_wks=3` は Fabric→Factory の3週として効く。

### 5.2 MOM の `lt_wks` は無意味

`Factory_Import_CN` は `parent_node` が空欄の InBound root であり、上流に親を持たない。MOM→SP のブリッジ区間は**同一拠点の生産 location と出荷 location の受け渡し**であり、物理的な移動が存在しないため **LT という概念が定義できない**。

したがって `lt_wks=8` は適用先が無く、**無視される**。実測でこれを確認した：

- `lt_wks` を 8→4 に変更しても、Fabric_CN / Factory_Import_CN の PSI が**1単位も変わらない**
- Fabric_CN（W42〜W47）と Factory_Import_CN（W45〜W50）の差 3週は、**Fabric_CN 自身の lt=3w** である

**これはバグではなく、データ定義の誤り。** 行そのものは InBound root として必要だが、`lt_wks` に値を置くべきではない。

### 5.3 8週の実体は物流LTだった

apparel の縫製は実務上 1〜2日（大手中国ベンダー）。`Factory_Import_CN` の `lt_wks=8` は縫製時間ではなく、**工場出荷から米国 DC 着荷までの国際物流LT**（内陸輸送・通関・船積み待ち・海上輸送）である。

正しい置き場所は **DAD 側の `lt_wks`**。実験（`DC_Import_Buffer` の `lt_wks` を 4→8）で、意図した8週オフセットが正しく現れることを確認した。

**副次的な含意**：加工時間（縫製1〜2日）は全LTの約3%であり、支配的なのは海上輸送3〜4週と通関待ち。これらは日単位の精度を持たない。Weekly Granularity Thesis は「週で妥協した」のではなく「**支配的な要素の粒度に合わせた**」という主張として成立する。

### 5.4 InBound 側に在庫が立たない理由

MOM の LT が効かないため P と S が同週に置かれ、`I = I(前週) + P − S = 0` が恒等的に成立する。OutBound 側（`DC_Import_Buffer`）では lt=4 の間に在庫が積み上がる（W49:450 → W50:2379 → W51:5271 → W52:7900）。

**現状の apparel では実害は無い**が、加工そのものに数週かかる業種（醸造・製油）では、加工時間を持つ列が無いことが問題になりうる。soysauce の `Brewing_Noda` の `lt_wks` に何が入っているかは未確認。

---

## 6. 静的 lint への追加項目

`docs/design/lot_id_traceability_and_coverage_views.md` §3 第1層に、以下を追加する。

```
[配線] node_type=mom かつ parent_node が空のノードに lt_wks > 0 が設定されている
       → MOM は InBound 木の root であり上流に親を持たない。
         ブリッジ区間（MOM→SP）は同一拠点内の受け渡しであり LT は定義されない。
         したがって lt_wks は無視される。値を 0 にすることを推奨。【警告】

[参照] lane_assignment.csv の mom_node_id が、sc_tree_master.csv に実在する
       MOM ノードを指しているか（完全修飾 node_id 形式 side:type:name:product での照合）

[重複] lane_assignment.csv に同一 (sku_id, leaf_node_name) の行が複数ある
       → 後勝ちで無言に上書きされる。priority は未実装で効かない。【警告】

[網羅] demand_forecast.csv に存在する (sku_id, region) に対応する
       lane_assignment.csv の行が存在するか（欠落＝primary MOM へのフォールバック）
```

いずれも CSV のみで検査可能。

---

## 7. 未実装・未確定事項

| 項目 | 状態 |
|---|---|
| `priority` による代替 MOM（第一候補が能力不足なら第二候補へ） | **未実装**（docstring に future use と明記） |
| 能力連動の動的再配分 | **未実装**（能力不足は CO に落ちるのみ） |
| 三層（Management / Demand / Supply）の相互接続 | **未接続** |
| `_actual_s` の GUI 露出 | 未対応（三層可視化 v2 で予定） |
| 加工時間を表す列 | スキーマに存在しない。業種依存の設計課題 |
| soysauce の `Brewing_Noda` の `lt_wks` の意味 | 未確認（加工時間が入っている可能性） |
| ev-europe-2026 の BOM 構成（tier-1 が複数）での lane の効き方 | 未確認 |

### 三層が接続されていないことの意味

```
Management 層  ask_global_allocation  配分比率を探索
               　　　↓ demand_forecast.csv を書き換える（エンジンの外側）
Demand 層      lane_assignment.csv    静的振り分け（priority 未実装）
               　　　↓ Lot_ID に刻印
Supply 層      _actual_s              実出荷の集約（GUI 非露出）
```

Management 層の探索結果は CSV の書き換えとしてしか Demand 層に伝わらず、Demand 層の振り分けは能力を見ず、Supply 層の実績は上流にフィードバックされない。**三層とも「配分」を扱いながら、一方向にすら繋がっていない。**

これは欠陥ではなく、各層が独立に発展した結果である。ただし次の設計を考える際の出発点になる。

---

## 8. 未解決問題：Global N Plants × M Markets への一般化

### 8.1 問題

`ask_global_allocation` の利益地形図は強力だが、**3拠点の制約**がある。231格子点で覆えるのは3次元単体だから成立した。

**5 Mother Plants × 100 Markets** を対象とした場合、配分空間は 500 次元になる。全数評価は次元の呪いにより不可能。かといって LP で最適解を一点返せば、それは WOM が意図的に捨てた道（§1「LP 最適化はしない」）である。

**この問題が解ければ、WOM は「3拠点の可視化ツール」から「グローバル製造業の意思決定基盤」になる。**

### 8.2 考えられる三つの方向（いずれも未検証）

**方向A：次元を落とすのではなく、問いを分割する**

経営者が実際に決めるのは500変数の同時最適ではなく、「この市場群は、どの工場から供給すべきか」という**担当領域の切り分け**である。100市場を関税圏・通貨圏・輸送レーンで束ねれば、実質的な意思決定単位は10〜20 に落ちる。地形図は「工場 i の担当領域がどこまで広がるか」を描くものになる。

**方向B：地形ではなく境界を描く**

3拠点だから面が描けた。高次元では面は見えないが、**境界は見える**。「この市場が工場Aから工場Bに切り替わるのは、関税が何%になったときか」は2次元平面に描ける。

実例：2026-08-20 に apparel で導出した**中国関税 15.8%**（これを下回ると輸入が自社スペイン工場を逆転する）。醤油の**切替点 117/119円**も同型。

**地形図の高次元版は、等高線ではなく切替点の一覧になる**のではないか。既に `ga_switching_point.csv` として出力する仕組みがある。

**方向C：探索を人間に返す**

500次元を機械が探索して答えを出すのは、WOM が拒否した「黙って解く黒箱」そのもの。むしろ経営者が「この市場をここから供給したい」と置いたときに、**その帰結を即座に返す**。探索の主体を人間に置いたまま、評価だけを高速化する。`ask_` の思想そのもの。

### 8.3 三方向に共通する思想

**最適解を探さず、判断の材料を渡す。**

地形図の本質は面そのものではなく、「動かせる範囲」と「切り替わる点」を見せることだった。だとすれば、次元が増えても思想は生き残る。

そしてこの一般化は、§7 で挙げた「三層が接続されていない」という課題と直結する。Management 層の探索が Demand 層の `lane_assignment` を直接生成し、Supply 層の実績が次の探索に戻る — その循環が閉じたとき、初めて N×M 規模が扱えるようになると考えられる。

---

## 9. 本節のステータス

**設計記録のみ。実装なし。** `wom-v1r3m0` に対するコード変更・CSV スキーマ変更は一切行っていない。

即座に有効なのは以下：

- **§4.1**：CLAUDE.md L931 の記述訂正（「配分比率」→「静的チャネル振分け」）
- **§5.2**：MOM ノードの `lt_wks` に値を置かない（無視されるため）
- **§6**：静的 lint への追加項目
