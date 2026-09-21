# Request Letter A：`cpu_size` を計画パラメータへ移設（node → plan）

**起票日**：2026-09-01
**起票者**：大杉
**種別**：**スキーマ変更 ＋ リファクタリング**（動作は変わらない想定）
**対象ブランチ**：`wom-v1r3m0`
**先行**：`cpu_size` 実装調査（2026-08-30）、`requests/request_fix_a1_supply_role_rev2.md`

**本 Letter は "1 set rule"（BOM 数量 N）実装の前段である。**
N の実装は **Letter B** で別途起票する。本件では N に一切触れない。

---

## 0. 禁足ルールに基づく承認事項

本件は保護対象コアには**触れない見込み**だが、`sc_tree_master.csv` のスキーマ変更を伴う。

- [x] Request Letter 起票（本書）
- [ ] 3層テスト（Unit / Integration / golden）緑
- [ ] オーナー（大杉）による差分レビュー
- [ ] **golden 全12ケースが無変化であること**（本件は動作を変えないため）

**上記が揃うまでコミットしないこと。**
**保護対象コア6ファイルに変更が必要と判明した場合は、実装前に報告して指示を仰ぐこと。**

---

## 1. 背景

### 1.1 WOM の原則

**`cpu_size` は、計画上のすべてのノードが同一の値を持つ計画パラメータである。**

したがって、現在 `sc_tree_master.csv` に**ノード単位の列**として存在すること自体が
原則と食い違っている。ノードごとに異なる値を書けてしまう。

### 1.2 調査で判明した現状（2026-08-30）

| 項目 | 実態 |
|---|---|
| 読み込み | `sc_tree_builder.py:181` で行ごとに読み、`PlanNode(cpu_size=...)` へ渡す |
| 格納 | `plan_node.py:107` の dataclass フィールド（**ノードごと**） |
| Planning Engine | `backward_planner.py` / `forward_planner.py` / `push_pull.py` に**文字列すら出現しない** |
| ロット生成 | `lot_generator.py:247` の `ceil(qty/cpu_size)`。ただし**全呼び出し元が固定値1を渡す** |
| 表示・KPI | `sc_tree_to_df.py:74,135`、`app.py:414,482` で**ノードごとの値**を独立に掛ける |
| デッドコード | `lots_to_qty()` / `qty_to_lot_count()` は**呼び出し元ゼロ** |
| 未使用引数 | `landed_cost.py:171,187` に引数として存在。docstring に "Currently unused" |
| 実データ | **全17モデル・全ノードで `cpu_size=1`** |

**すなわち `cpu_size` は実質的に死んでいる列である。**

- 入口（`lot_generator`）が CSV を読まない
- Planning Engine が参照しない
- 唯一生きている表示・KPI 層も、値が全て1なので実質 no-op

### 1.3 なぜ今、移設するか

次の Letter B で **BOM 数量 N（"1 set rule"）** を実装する。そこでは

```
S_Qty[w] = len(psi[w]["S"]) × cpu_size × N
```

という計算が必要になる。**`cpu_size` がノード属性のままだと、
「どのノードの値を使うのか」が曖昧になり、実装が混乱する。**

先に原則どおりの位置へ移しておく。

---

## 2. 変更内容

### 2.1 `planning_config.csv` に `cpu_size` キーを追加

```
key,value
warmup_lt,52
planning_start,
cpu_size,1
```

**既定値は 1。** キーが無い場合も 1 とすること（既存モデルとの互換）。

### 2.2 `sc_tree_master.csv` から `cpu_size` 列を削除

全モデル（git 管理下の16モデル）から列を削除する。

**`.gitignore` 対象のバックアップフォルダ（`rice-japan-2027-2028_BK260613_1515` 等）には
触れないこと。** 2026-08-30 に誤って触れた事例がある。
`os.listdir()` による網羅走査は `.gitignore` を考慮しないため注意すること。

### 2.3 `PlanNode.cpu_size` の削除

`plan_node.py:107` のフィールドを削除する。
参照している箇所を、計画パラメータ側の値を見るように変更する。

### 2.4 格納先

**`warmup_lt` / `planning_start` と同じ場所に置くこと。**
実装を確認し、それに合わせて一貫させること。選んだ場所と理由を報告すること。

`SCTree` のインスタンス属性、あるいは planning context の dict が候補と思われる。

### 2.5 参照箇所の修正

| ファイル | 現状 | 変更後 |
|---|---|---|
| `sc_tree_builder.py:181,204` | CSV 行から読み `PlanNode` へ | 削除（列が無くなる） |
| `plan_node.py:107` | dataclass フィールド | 削除 |
| `sc_tree_to_df.py:74,135` | `node.cpu_size` | 計画パラメータの値 |
| `app.py:414,482` | `node.cpu_size` | 同上 |
| `lot_generator.py:247` | スカラー引数 | **§2.6 参照** |

### 2.6 `lot_generator` の呼び出し元

現在、全呼び出し元が `cpu_size=1` を固定で渡している。

```
wom/gui/app.py:5114
tools/run_headless_from_folder.py:154
tools/sweep_flags.py:350
tests/*.py（8ファイル）
data/sample/*/exercises/*.py（3ファイル）
```

**GUI・headless・sweep_flags の3つは、`planning_config.csv` の値を渡すように変更すること。**

テストと exercises のスクリプトは、**固定値のままでよい**（単体テストとして意図的な値を
渡している可能性があるため）。ただし変更が必要と判断した場合は、理由とともに報告すること。

### 2.7 デッドコードの扱い

以下は**本件では削除しないこと**。別途整理する。

- `lots_to_qty()` / `qty_to_lot_count()`（呼び出し元ゼロ）
- `landed_cost.py` の `cpu_size_default` 引数（"Currently unused"）

**ただし、`cpu_size` の意味が変わることで docstring が不正確になる箇所は、
コメントを修正すること。**

---

## 3. 本 Letter の範囲外

| 項目 | 扱い |
|---|---|
| **BOM 数量 N（`bom_qty` 列）の実装** | **Letter B** |
| `capacity_plan.csv` の `cap_pieces` 列と note | **Letter B** |
| `S_Qty = len(...) × cpu_size × N` の実装 | **Letter B** |
| 検証用モデル `bom-test-2026` の作成 | **Letter B** |
| lint 項目の追加 | **Letter B**（設計文書への追記） |
| デッドコードの削除 | 別件 |
| CLAUDE.md の A1 記録の訂正 | 別件 |

---

## 4. テスト要件（3層）

### 4.1 Unit

- `planning_config.csv` の `cpu_size` が読まれ、計画パラメータとして保持されること
- キーが無い場合、既定値 1 になること
- `PlanNode` に `cpu_size` 属性が**存在しない**こと
- `sc_tree_to_df.py` / `app.py` が計画パラメータの値を使うこと

### 4.2 Integration

- 既存モデル（例：soysauce-jpy-2027）を実行し、**KPI DataFrame の数量が変わらないこと**
- `cpu_size` を 1 から 12 に変更したとき、
  **KPI 表示の数量が12倍になり、ロット数は変わらないこと**
  （この確認は既存モデルの CSV を一時的に変更して行い、必ず元に戻すこと）

### 4.3 golden（12ケース）

**判定基準**：

| 状況 | 判定 |
|---|---|
| **全12ケースが無変化** | **正常**。本件は動作を変えないリファクタリング |
| いずれかが変化した | **異常**。原因を報告し、コミットしないこと |

`series_md5` は週次のロット件数のハッシュであり、`cpu_size` の値に依存しない。
**したがって golden は1件も変化しないはずである。**

---

## 5. 報告してほしいこと

1. `cpu_size` の格納先として選んだ場所と、その理由（`warmup_lt` との一貫性）
2. `lot_generator` の呼び出し元をどう変更したか（§2.6）
3. 修正の差分（`git diff`）
4. §4.1 の Unit テスト結果
5. §4.2 の Integration 結果（**特に `cpu_size=12` で数量が12倍になること**）
6. §4.3 の golden 結果（**全件無変化であること**）
7. 判定
8. `git status`（`data/sample/` に意図した変更のみ、`.gitignore` 対象に触れていないこと）
9. 気づいた点

---

## 6. 手順

```
① cpu_size の格納先を決め、報告する
② 実装する
③ §4.1 Unit テストを追加
④ §4.2 Integration を実施（cpu_size=12 での検証を含む）
⑤ §4.3 golden 12ケースを実行（全件無変化を確認）
⑥ 大杉の差分レビュー
⑦ 承認後、コミット
```

**⑥の前にコミットしないこと。**
**①の時点で一度報告し、格納先の合意を得てから②へ進むこと。**

---

## 7. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること
- `capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと
- **`.gitignore` 対象のフォルダに触れないこと**
- コミットメッセージは、指定したもの以外の行（`Co-Authored-By` 等）を
  **勝手に追加しないこと**

---

## 8. 参考

- `docs/design/demand_anchored_lot.md`
- `docs/design/three_layer_production_allocation.md`
- `requests/request_fix_a1_supply_role_rev2.md`（`supply_role` の導入。本件の先行）
- `cpu_size` 実装調査（2026-08-30）：§1.2 の表を参照

---

## 9. 次に来るもの（Letter B の予告）

```
bom_qty 列        sc_tree_master.csv の子の行に追加（既定1）
                  supply_role と同じ場所（親から自分へのエッジの属性）

数量計算          S_Qty[w] = len(psi[w]["S"]) × cpu_size × N
                  PPC / KPI / 表示層に反映。Planning Engine は無変更の見込み

cap_pieces 列     capacity_plan.csv に追加（参考値、エンジンは読まない）
note              算定式を記述
                  例：max_supply=416, cap_pieces=20000,
                      note="20000 pieces/wk / (cpu_size 12 x N 4) = 416.67 -> 416"

検証用モデル      data/sample/bom-test-2026
                  Tire_Supply (bom_qty=4) と Battery_Supply (bom_qty=1) が
                  同じ Vehicle_Assy に供給する最小構成
                  「タイヤ4本」は説明不要な題材であり、N が効いているかを
                  一目で確認できる

lint              max_supply × cpu_size × N ≒ cap_pieces の検算
```

**Letter A が済んでいれば、Letter B では「どのノードの cpu_size か」という
曖昧さが無くなる。**
