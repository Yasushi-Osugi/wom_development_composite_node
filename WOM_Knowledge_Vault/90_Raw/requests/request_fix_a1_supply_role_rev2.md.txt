# Request Letter：`supply_role` の導入と複数子への需要複製の修正（A1）Rev 2

**起票日**：2026-08-30（Rev 2、初版を全面改訂）
**起票者**：大杉
**種別**：**禁足コア変更**（`wom/engine/backward_planner.py`）＋ **スキーマ拡張**（`sc_tree_master.csv`）
**対象ブランチ**：`wom-v1r3m0`
**初版からの変更**：事前調査で `ev-europe-2026` が「合流」ではなく「組立」であることが判明したため、
一律の均等割りを取りやめ、`supply_role` 列による明示的な区別に変更した。

---

## 0. 禁足ルールに基づく承認事項

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

**全ロットを各子へ丸ごと複製している。**

**Forward**：`_propagate_to_parent`（`forward_planner.py:527`）は
`walk_postorder()` で子ごとに1回呼ばれ、親の P に `extend` する。

**結果：同一 Lot_ID が子の数だけ物理的なモノとして数えられる。**

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

### 1.3 CLAUDE.md の記録の訂正

CLAUDE.md 末尾の A1 記録「発生条件は MOM の週次 demand.S に段差が生じること」は**不正確**。

- CO 発生開始週は **2026-W15**。ディワリ（2026-W45/46）よりずっと前
- `B_multi_smooth`（ディワリなし）でも CO 429,299 が発生
- CO=20,386 という記録値は再現せず（実測 9,854 / 7,873）

**真の条件は「複数子への複製で P が倍化 × その P が MOM の cap_hard を超えること」。
需要段差は無関係。**

### 1.4 Ghee_Export がクリーンだった理由

`capacity_plan.csv` の注記：
> `※複数leaf_in合算後のPを基準に設定`

**モデル構築時点で重複が認識され、cap_hard を嵩上げして回避されていた。**
複数子があれば重複は常に発生しており、cap_hard の余裕で見えるか否かが決まるだけ。

---

## 2. 初版からの重要な訂正：ev-europe は「合流」ではない

### 2.1 事前調査の結果

`data/sample/` 全モデルで、InBound 側に子を2つ以上持つノードは4件。

| モデル | golden | ノード | 子 | 性質 |
|---|---|---|---|---|
| **ev-europe-2026** | **対象** | Factory_Import_HU | Battery_HU, Motor_HU, ECU_HU | **組立** |
| **ev-europe-2026** | **対象** | Factory_Local_DE | Battery_DE, Motor_DE, ECU_DE | **組立** |
| ev-thailand-2026_update | 対象外 | Factory_Local_TH | Platform_Unit_Assy, Motor_Unit_Assy | **組立** |
| india-ghee-2026 | 対象外 | Ghee_Plant_Export | Anand_Export_Route, Mehsana_Milk_Route | **合流** |

### 2.2 均等割りを一律に適用してはならない

```
合流   生乳100 を Anand 50 / Kheda 50 に分ける         ← 分割が正しい
組立   EV 100台に Battery 33 / Motor 33 / ECU 34       ← 誤り
       正しくは Battery 100 / Motor 100 / ECU 100      ← 複製が正しい
```

**現在の「全複製」は、組立型としては正しい実装である。**
ev-europe が動いているのは、BOM 必要数が全て1だから。

初版の判定表「multi-leaf_in が変化する → 正常」は、**ev-europe には当てはまらない。**

### 2.3 設計文書との関係

`docs/design/` 全13文書に、複数子への配分の規定は無い。
`demand_anchored_lot.md` の Open Questions 3 に未解決として明記されている：

> How should lot identity be preserved when demand is aggregated, **split**,
> substituted, or reallocated?

**未設計の領域である。** ただし Rule 2 / Rule 5 の原則からは、
「同一 Lot_ID が複数の物理的モノとして数えられてはならない」が導ける。

---

## 3. 修正内容

### 3.1 スキーマ拡張：`supply_role` 列

`sc_tree_master.csv` に列 `supply_role` を追加する。**子ノードの行に置く**
（親から自分へのエッジの属性として解釈する）。

| 値 | 意味 | 挙動 |
|---|---|---|
| `confluence` | 同種のものが複数経路から集まる | 親の需要を、同じ `confluence` の兄弟と**分担**する（分割） |
| `assembly` | 異なる部材が揃って一つになる | 親の需要と**同数**を供給する（現在は N=1 固定） |
| 空欄・未指定 | — | **`assembly` として扱う（既定）** |

**既定を `assembly` にすることで、既存の全モデルが無変更で動く。**

### 3.2 混在を許すこと

同じ親の子に `confluence` と `assembly` が混在してよい。

```
Anand_Milk_Route,Ghee_Plant_Anand,...,confluence
Kheda_Milk_Route,Ghee_Plant_Anand,...,confluence
Packaging_Supply,Ghee_Plant_Anand,...,assembly
```

このとき：
- `confluence` の子どうしで需要を**分割**する（この例では 50/50）
- `assembly` の子には**全量**を渡す

### 3.3 `_in_propagate` の変更

```python
# 現状（全複製）
for lot_id in all_lots:
    for child in node.children:
        child.psi4demand[child_w][S].append(lot_id)

# 変更後（概念）
confluence_children = [c for c in node.children if c.supply_role == "confluence"]
assembly_children   = [c for c in node.children if c.supply_role != "confluence"]

# assembly: 全量を各子へ（現状と同じ。将来 N 倍に拡張する箇所）
for child in assembly_children:
    child_w = self._offset_week(w, child.lt_wks + child.ss_wks, child.node_name)
    for lot_id in all_lots:
        child.psi4demand[child_w][S].append(lot_id)

# confluence: 均等割り＋余りで分割
if confluence_children:
    n = len(confluence_children)
    base, remainder = divmod(len(all_lots), n)
    idx = 0
    for i, child in enumerate(confluence_children):
        take = base + (1 if i < remainder else 0)
        child_w = self._offset_week(w, child.lt_wks + child.ss_wks, child.node_name)
        for lot_id in all_lots[idx: idx + take]:
            child.psi4demand[child_w][S].append(lot_id)
        idx += take
```

**`child_w` は子ごとに `lt_wks` / `ss_wks` が異なりうるため、必ず子のループ内で計算すること。**

### 3.4 【重要】`assembly` は将来 N 倍に拡張できる形にすること

現在の `assembly` は「BOM 必要数が全て1」という**限定的な意味**である。
将来、部品点数 N（例：タイヤ4本／台）を扱えるようにする予定がある。

**したがって「複製」をハードコードせず、「親1に対して子N（現在は N=1 固定）」
という構造で実装すること。**

例えば `multiplier = 1` のような変数を経由させ、将来そこを可変にすれば済む形にする。
実装の詳細は任せるが、**次の拡張で書き直しにならないこと**を条件とする。

### 3.5 分割方式は均等割り＋余り

`divmod(len(lots), n)` による連続スライス。理由：

1. `push_pull.py` の Mode4 リーフ分配が既に同じイディオムを採用しており、一貫する
2. 能力比例は `cap_hard` が週変動するため「どの週の値か」等の判断が増える。第二段階へ
3. 要件（決定的・子1つで現状同一・漏れなし・重複なし）を満たす

### 3.6 Forward 側は触らないこと

`_propagate_to_parent` の `extend` は、Backward が正しく分割していれば重複を生まない。

**まず Backward のみを修正し、A1 が解消するか確認すること。**
解消しない場合のみ Forward 側の調査に進み、その旨を報告すること。
**Forward を先に変更しないこと。**

### 3.7 本 Request Letter の範囲外

| 項目 | 理由 |
|---|---|
| **BOM 数量 N の実装（"1 set rule"）** | **次の Request Letter で着手する。本件では N=1 固定** |
| `cpu_size` を生かす改修 | 上記に含める。調査で「死んでいる列」と判明済み |
| 分割比率のマスタ化（能力比例・利益地形） | 第二・第三段階 |
| `node_type` を `mom` にするモデル定義の見直し | CSV のみ。エンジン変更不要 |
| OutBound 側の配分 | 既に正しく動いている（分配の根拠が需要側にある） |

---

## 4. CSV の更新

### 4.1 既存モデル

**`supply_role` 列を追加するが、値は空欄でよい**（既定 `assembly` で現状維持）。

列を追加しない選択肢もあるが、**スキーマの一貫性のため全モデルに列を追加し、
値は空欄とすること**を推奨する。判断は任せるので、選んだ方針を報告すること。

### 4.2 india-ghee-2026

`Ghee_Export` 側の2 leaf_in に `confluence` を設定する。

```
Anand_Export_Route,Ghee_Plant_Export,...,confluence
Mehsana_Milk_Route,Ghee_Plant_Export,...,confluence
```

**これにより `Ghee_Plant_Export` の P_sum が 55,952 → 27,976 に戻るはず。**
そして `capacity_plan.csv` の「※複数leaf_in合算後のPを基準に設定」という
cap_hard の嵩上げが不要になる。

**ただし capacity_plan.csv の修正は本件では行わないこと。**
嵩上げされたままでも CO は出ない（余裕が増えるだけ）。別途整理する。

### 4.3 ev-europe / ev-thailand

**変更しないこと。** 空欄＝`assembly` として現状の挙動を維持する。

---

## 5. テスト要件（3層）

### 5.1 Unit

- `supply_role` 列が読まれ、`PlanNode` に格納されること
- 空欄・未指定が `assembly` として扱われること
- `confluence` の子が2つのとき、Lot が均等に分割されること
- **同一 Lot_ID が複数の `confluence` 子に現れないこと**
- 全 Lot がいずれかの子に割り当てられること（漏れなし）
- `assembly` の子には全量が渡ること（現状と同じ）
- `confluence` と `assembly` が混在するとき、それぞれ正しく処理されること
- 子が1つのとき、`confluence` / `assembly` のどちらでも挙動が変わらないこと

### 5.2 Integration（india-ghee-2026）

- `Ghee_Export` の 2 leaf_in の P_sum が各 27,976、合計 55,952
- **`Ghee_Plant_Export` の P_sum が 27,976 になること**（現状 55,952 から半減）
- CO_sum が 0 のままであること
- `Ghee_Domestic`（単一 leaf_in）が無変化であること

### 5.3 golden（12ケース）

**判定基準（初版から変更）**：

| 状況 | 判定 |
|---|---|
| **全12ケースが無変化** | **正常**。既定 `assembly` により既存挙動が保たれる |
| ev-europe-2026 が変化した | **異常**。`assembly` の実装が現状と違う。コミットしないこと |
| 他のケースが変化した | **異常**。単一子連鎖なので変化しないはず |

**本件では golden は1件も変化しないのが正常。**
変化した場合は原因を報告し、コミットしないこと。

---

## 6. 報告してほしいこと

1. `supply_role` 列を全モデルに追加したか、india-ghee のみか（選んだ方針と理由）
2. `assembly` を「N=1 固定」として実装した箇所（§3.4）と、将来 N を可変にする方法
3. 修正の差分（`git diff`）
4. §5.1 の Unit テストが**修正前に赤・修正後に緑**であること
5. §5.2 の Integration 結果（特に `Ghee_Plant_Export` の P_sum）
6. §5.3 の golden 結果（**全件無変化であること**）
7. 判定
8. `git status`（`data/sample/` に意図した変更のみ）
9. 気づいた点

---

## 7. 手順

```
① supply_role 列の追加方針を決め、報告する
② Backward のみを修正する（assembly は N=1 固定の構造で）
③ §5.1 Unit テストを追加し、修正前後で赤→緑を確認
④ india-ghee の CSV に confluence を設定
⑤ §5.2 Integration を実施
⑥ §5.3 golden 12ケースを実行（全件無変化を確認）
⑦ 大杉の差分レビュー
⑧ 承認後、コミット
```

**⑦の前にコミットしないこと。**

---

## 8. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること
- `capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと

---

## 9. 参考

- `docs/design/demand_anchored_lot.md`（Rule 2 / Rule 5、Open Questions 3）
- `docs/design/three_layer_production_allocation.md` §2
- `docs/design/design_memo_confluence_assembly_autotuning.md` §A/§B（合流と組立の区別）
- `CLAUDE.md` 末尾の A1 記録（**§1.3 の通り訂正が必要**）
- `tools/sweep_specs/india_ghee_a1.yaml`（再現手段）
- `requests/request_fix_mode4_double_count.md`（先行する同種の修正）
- `cpu_size` 調査（2026-08-30）：**`cpu_size` は実質的に死んでいる列**。
  全17モデル・全ノードで値1、Planning Engine は一切参照しない、
  `lot_generator` の呼び出し元は全て固定値1を渡す。
  MEU（oil-global のタンカー1隻等）は `demand_forecast.csv` の数量と
  `unit_cost` の桁で表現されており、`cpu_size` による換算機構は使われていない

---

## 10. 本修正の後に来るもの

```
次の Request Letter  BOM 数量 N の実装（"1 set rule"）
                     EV のタイヤ4本／台のような構成部品点数を扱う
                     組立系サプライチェーンの表現に必須

第二段階             分割比率のマスタ化（能力比例等）
第三段階             ask_global_allocation の利益地形図との接続
```

**"1 set rule" は本件の完了後、間を置かずに着手する。**
組立系（EV 等）のサプライチェーンが正しく表現できないため。
