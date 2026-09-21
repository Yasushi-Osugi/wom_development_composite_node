# Request Letter：複数子への需要複製による Lot 重複加算の修正（A1）

**起票日**：2026-08-30
**起票者**：大杉
**種別**：**禁足コア変更**（`wom/engine/backward_planner.py`、場合により `wom/engine/forward_planner.py`）
**対象ブランチ**：`wom-v1r3m0`
**先行調査**：`tools/sweep_specs/india_ghee_a1.yaml` による再現スイープ（2026-08-30）

---

## 0. 禁足ルールに基づく承認事項

本件は保護対象コアの変更を伴う。CLAUDE.md 冒頭の禁足ルールに従い、以下を条件とする。

- [x] Request Letter 起票（本書）
- [ ] 3層テスト（Unit / Integration / golden）緑
- [ ] オーナー（大杉）による差分レビュー
- [ ] golden 差分が「正しくなった結果」であることの確認

**上記が揃うまでコミットしないこと。**

---

## 1. 確定した原因

### 1.1 機構

**Backward**：`_in_propagate`（`backward_planner.py:399-401`）

```python
for lot_id in all_lots:
    for child in node.children:
        child.psi4demand[child_w][S].append(lot_id)
```

**全ロットを「分割」ではなく「各子へ丸ごと複製」している。**

**Forward**：`_propagate_to_parent`（`forward_planner.py:527`）

```python
parent.psi4supply[target_w][P].extend(confirmed_s)
```

`walk_postorder()` で**子ノードごとに1回ずつ呼ばれる**ため、子が2つあれば親の P に2回 extend される。

**結果：同一 Lot_ID が物理的に2本のモノとして数えられる。**

### 1.2 実測（india-ghee-2026 / Ghee_Domestic、2 leaf_in に戻した状態）

| ノード | base_single | A_multi_spike | B_multi_smooth |
|---|---|---|---|
| Anand_Milk_Route P_sum | — | 48,532 | 47,520 |
| Kheda_Milk_Route P_sum | — | 48,532 | 47,520 |
| **2 leaf_in 合計** | — | **97,064** | **95,040** |
| Ghee_Plant_Anand P_sum | 48,532 | **87,210** | **87,167** |
| forward.cap_hard_sealed | 0 | 9,854 | 7,873 |
| Ghee_Plant_Anand CO_sum | 0 | **505,979** | **429,299** |

**「2 leaf_in 合計 − cap_hard_sealed」が寸分違わず MOM の P_sum と一致する。**

```
97,064 − 9,854 = 87,210
95,040 − 7,873 = 87,167
```

すなわち：

1. 各 leaf_in が単独で**フルの需要を丸ごと**受け取っている（分割されていない）
2. MOM の P に両 leaf_in の実出荷が**そのまま加算**される（同一 Lot_ID の二重計上）
3. 水増し分のうち cap_hard を超えた分が `cap_hard_sealed` として切り落とされ、CO に転化する

### 1.3 CLAUDE.md の記録の訂正

CLAUDE.md 末尾の A1 記録には「発生条件は **MOM の週次 demand.S に段差が生じること**」とあるが、
**これは不正確。**

- CO 発生開始週は **2026-W15**。ディワリ（2026-W45/46）よりずっと前
- `B_multi_smooth`（ディワリなし）でも CO 429,299 が発生
- CO=20,386 という記録値は再現せず（実測は 9,854 / 7,873）。定性的な再現は成立、定量的な再現は不成立

**真の条件は「multi-leaf_in（→ 常に P_sum が構造的に子の数だけ倍になる）×
その水増し後の P が MOM 自身の cap_hard を超えること」。需要段差の有無は無関係。**

### 1.4 Ghee_Export がクリーンだった理由

対照群の `Ghee_Export`（元から 2 leaf_in、需要は滑らか）は全ケースで CO=0 だが、
**同じ重複は起きている。**

| ノード | 値 |
|---|---|
| Anand_Export_Route P_sum | 27,976 |
| Mehsana_Milk_Route P_sum | 27,976 |
| 2 leaf_in 合計 | **55,952** |
| Ghee_Plant_Export P_sum | **55,952**（sealed ゼロ、丸ごと素通り） |

`capacity_plan.csv` の該当行に注記がある：

> `Ghee_Domestic,Ghee_Plant_Export,2026-W02,1215,...※複数leaf_in合算後のPを基準に設定`

**モデル構築時点で重複が認識されており、cap_hard を「重複後の値」に嵩上げして
回避されていた。**`Ghee_Plant_Anand` 側は単一需要ベースの値で据え置かれていたため、
2 leaf_in に戻すと超過する。

**すなわち、2 leaf_in 構成があれば重複は常に発生しており、
cap_hard に余裕があるかどうかで「見えるか見えないか」が決まるだけ。**

---

## 2. 設計文書との関係

### 2.1 規定は存在しない

`docs/design/` 全13文書を確認したが、**複数子への需要配分を規定した記述は無い。**

`demand_anchored_lot.md` の Open Questions 3 に、未解決の問いとして明記されている：

> How should lot identity be preserved when demand is aggregated, **split**,
> substituted, or reallocated?

**A1 は「仕様と実装の不一致」ではなく、未設計の領域である。**

### 2.2 ただし原則からは答えが導ける

`demand_anchored_lot.md` より：

> **Rule 2**: Lot identity should be preserved. Do not discard lot identity
> unless the aggregation is explicitly documented.
>
> **Rule 5**: Inventory should represent unused physical supply.
>
> `I = available supply - demand to satisfy`
> The subtraction should be interpreted **by lot identity, not merely by count**.

**同一 Lot_ID が2本の物理的なモノとして数えられることは、この原則に反する。**
1つの需要ロットは1つのモノである。

### 2.3 構造上の空白

`docs/design/three_layer_production_allocation.md` §2 の整理と合わせると：

```
市場 → 工場     lane_assignment.csv が担当（静的 1:1、priority 未実装）
工場 → 調達源   規定なし → 全複製（現在の _in_propagate）
```

**上流側の配分だけが未定義。** これが A1 の根本にある。

---

## 3. 修正内容

### 3.1 方針

**`_in_propagate` の「全ロットを各子へ複製」を「分割」に変える。**

一つの需要 Lot_ID は、**ちょうど一つの子に割り当てられる**こと。
複数の子に同じ Lot_ID が現れてはならない。

### 3.2 分割の基準（本 Request Letter の範囲）

**第一段階として、決定的（deterministic）で再現可能な分割を実装する。**

推奨は以下のいずれか。**実装しやすい方を選び、選んだ理由を報告すること。**

| 案 | 内容 |
|---|---|
| (a) ラウンドロビン | Lot を順に子へ1つずつ割り当てる。子の数で剰余を吸収 |
| (b) 能力比例 | 各子の `cap_hard` の比率で分割 |
| (c) 均等割り + 余り | `divmod(len(lots), n_children)` で連続スライス |

**要件**：
- 同じ入力に対して同じ結果になること（再現可能）
- 子が1つの場合は現状と同じ挙動になること
- 全 Lot がいずれかの子に必ず割り当てられること（欠落なし）
- 同一 Lot が複数の子に現れないこと（重複なし）

### 3.3 Forward 側の扱い

`_propagate_to_parent` の `extend` は、**Backward が正しく分割していれば
重複を生まない**はずである。

**まず Backward のみを修正し、それで A1 が解消するかを確認すること。**
解消しない場合のみ Forward 側の調査に進み、その旨を報告すること。

**Forward を先に変更しないこと。**

### 3.4 本 Request Letter の範囲外

以下は実装しないこと。別途起票する。

| 項目 | 理由 |
|---|---|
| 分割比率のマスタ化（`lane_assignment.csv` 相当の上流版） | 機能追加。第二段階 |
| `ask_global_allocation` の利益地形図との接続 | 機能追加。第三段階 |
| BOM（組立型）の実装 | 別概念。`design_memo_confluence_assembly_autotuning.md` §B |
| `node_type` を `mom` にするモデル定義の見直し | CSV のみ。エンジン変更不要 |

---

## 4. テスト要件（3層）

### 4.1 Unit

`tools/sweep_specs/india_ghee_a1.yaml` の観測を固定するテストを追加する。

- india-ghee-2026 の `Ghee_Domestic` を 2 leaf_in にした状態で、
  **各 leaf_in の P_sum の合計が、単一 leaf_in の場合（48,532）と一致すること**
- **`Ghee_Plant_Anand` の CO_sum が 0 であること**
- 同一 Lot_ID が複数の子の `psi4demand[w][S]` に現れないこと
- 子が1つの場合、挙動が変わらないこと

**修正前にこのテストが赤になることを、先に確認すること。**

### 4.2 Integration

- `Ghee_Export`（元から 2 leaf_in）の P_sum が 55,952 → **27,976** に戻ること
  （重複が解消される。cap_hard の嵩上げが不要になる）
- 全 leaf_in の P_sum 合計 = MOM の P_sum（cap_hard_sealed を除く）となること
- 単一 leaf_in のケース（apparel-us-2026 等）が無変化であること

### 4.3 golden（12ケース）

**全ケースを実行し、`series_md5` の差分を報告すること。**

**事前に、全モデルの multi-leaf_in 構成を機械的に洗い出して報告すること。**
複数の子を持つ MOM ノードがあるケースは、変化するはずである。

判定基準：

| 状況 | 判定 |
|---|---|
| 単一 leaf_in のケースが**変化しない** | **正常** |
| multi-leaf_in のケースが**変化する** | **正常**（正しくなった結果） |
| 単一 leaf_in のケースが変化した | **異常**。修正が過剰。コミットしないこと |
| multi-leaf_in のケースが変化しなかった | **要調査**。報告すること |

**golden の JSON は、大杉の承認を得るまで更新しないこと。**

---

## 5. 報告してほしいこと

1. **§4.3 の事前調査**：全モデルの multi-leaf_in 構成の一覧（MOM 名、子の数、子の名前）
2. 採用した分割方式（(a)/(b)/(c)）と、選んだ理由
3. 修正の差分（`git diff`）
4. §4.1 の Unit テストが**修正前に赤・修正後に緑**であること
5. §4.2 の Integration 結果
6. §4.3 の golden 差分（変化したケース名と内容）
7. 判定表に照らした判定
8. `git status`（`data/sample/` が clean であること）
9. 気づいた点

---

## 6. 手順

```
① §4.3 の事前調査（multi-leaf_in 構成の洗い出し）を先に報告する
② 分割方式を選び、理由とともに報告する
③ Backward のみを修正する
④ §4.1 Unit テストを追加し、修正前後で赤→緑を確認する
⑤ §4.2 Integration を実施
⑥ A1 が解消したか確認。解消しない場合は Forward 側の調査に進み報告する
⑦ §4.3 golden 12ケースを実行し、差分を報告する
⑧ 大杉の差分レビュー
⑨ 承認後、golden JSON を更新し、コミット
```

**⑧の前にコミットしないこと。**
**②の時点で一度報告し、方式の合意を得てから③へ進むこと。**

---

## 7. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- golden テストは `planning_config.csv` を持つモデルに対して実ファイルへ warm-up 行を
  書き込む。実行後は必ず `git status -- data/sample/` を確認すること
- `capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと

---

## 8. 参考

- `docs/design/demand_anchored_lot.md`（Rule 2 / Rule 5、Open Questions 3）
- `docs/design/three_layer_production_allocation.md` §2（Demand 層の配分）
- `docs/design/design_memo_confluence_assembly_autotuning.md` §A（合流と組立の区別）
- `CLAUDE.md` 末尾の A1 記録（**§1.3 の通り訂正が必要**）
- `tools/sweep_specs/india_ghee_a1.yaml`（再現手段）
- `requests/request_fix_mode4_double_count.md`（先行する同種の修正。手順の参考）

---

## 9. 補足：本修正の後に来るもの

本件は**第一段階（重複を止める）**であり、以下が続く。

```
第二段階  分割比率をマスタで指定できるようにする
          （lane_assignment.csv の上流版）

第三段階  分割比率を ask_global_allocation の利益地形図と接続する
          「生産者と市場のペアで利益がどう変わるか」を
          Demand Layer の配分として事前に解く
```

**第一段階が済んでいないと、地形図を描いても土台が倍になっている。**
順序を守ること。
