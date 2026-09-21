# Request Letter B：BOM 数量 N の導入（"1 set rule"）

**起票日**：2026-09-01
**起票者**：大杉
**種別**：**スキーマ拡張 ＋ 数量・金額計算の変更 ＋ 新規サンプルモデル**
**対象ブランチ**：`wom-v1r3m0`
**先行**：`requests/request_letter_a_cpu_size_to_plan.md`（承認・commit 済み `466aaa8`）

---

## 0. 禁足ルールに基づく承認事項

**保護対象コア6ファイルには触れない見込み。**
Planning Engine はロット数で完結しており、N はその外側（KPI / 表示 / PPC）にのみ効く。

- [x] Request Letter 起票（本書）
- [ ] 3層テスト（Unit / Integration / golden）緑
- [ ] オーナー（大杉）による差分レビュー
- [ ] **golden 全12ケースが無変化であること**（既存は全て N=1）

**上記が揃うまでコミットしないこと。**
**保護対象コアに変更が必要と判明した場合は、実装前に報告して指示を仰ぐこと。**

---

## 1. 目的

EV のタイヤ4本／台のような**構成部品点数**を表現できるようにする。

現在の WOM には BOM 数量の機構が無く、`supply_role=assembly` は
「BOM 必要数が全て1」という限定的な意味しか持たない
（`requests/request_fix_a1_supply_role_rev2.md` §3.4）。

**組立系サプライチェーン（EV、電機等）が正しく表現できない。**

---

## 2. 【最重要】設計原則：N はロットリストに触れない

### 2.1 ロット数は親子で 1:1 のまま

WOM の数量系 PSI Planning Engine では、Demand Lots を構成する各ノードの Lot_ID が
planning process の中で重複して発生することはない。

**したがって部品点数 N で Lot_ID list そのものを触る処理は発生しない。**
PSI を構成する Lot_ID list はそのままで、N の影響を受けない。

```
親 Vehicle_Assy   W15 に 5 ロット
子 Tire_Supply    W15 に 5 ロット   ← ロット数は同じ
```

**リストを N 倍に複製してはならない。** それは
`39bcb44`（A1 修正）で取り除いた重複と同じ形であり、
`_match_by_identity` の集合演算が崩れる。

### 2.2 N が効く層

| 層 | N の影響 |
|---|---|
| Planning Engine（Backward / Forward / PushPull） | **なし**（ロット数で完結） |
| ロット生成（`lot_generator`） | **なし** |
| 生産能力の閾値 | あり（§5 参照） |
| KPI DataFrame の数量 | **あり** |
| GUI チャート表示 | **あり** |
| PPC の金額計算 | **あり** |

### 2.3 数量の定式化

```
S_Qty[w] = len(psi[w]["S"]) × cpu_size × N
```

例：`cpu_size=12`、`N=4`（タイヤ4本／台）、W15 に 5 ロット

```
S_Qty[15] = 5 × 12 × 4 = 240 本
```

### 2.4 【明記】PPC 単価の意味

**PPC の単価は「最小単位1個あたり」である。
`cpu_size` と `bom_qty` は、その上に掛かる係数である。**

```
Revenue   = 単価  × S_Qty[w]  =  単価  × len(psi[w][S]) × cpu_size × N
Cost_TTL  = 原価  × S_Qty[w]
Profit    = Revenue − Cost_TTL
```

上の例なら、単価は**タイヤ1本あたり**の値であり、`× 240` で240本分になる。

**「1ロットあたりの単価」と読んではならない。** 子ノードでそう読むと N が二重に掛かる。

### 2.5 既存モデルへの影響はゼロ

全モデルが `cpu_size=1`、`N=1`（既定）であるため、

```
S_Qty = ロット数 × 1 × 1 = ロット数
```

**現在の挙動と完全に一致する。** そして 1ロット = 1個なので、
「1ロットあたりの単価」と「1個あたりの単価」は同じ値である。
**既存 CSV の単価を書き換える必要はない。**

`oil-global-2027` も同様（1ロット = タンカー1隻、単価もタンカー1隻分、`cpu_size=1`）。

---

## 3. スキーマ拡張：`bom_qty` 列

### 3.1 定義

`sc_tree_master.csv` に列 `bom_qty` を追加する。**`supply_role` と同じく子の行に置く**
（親から自分へのエッジの属性）。

| 項目 | 内容 |
|---|---|
| 意味 | 親1個あたり、この子部材が何個必要か |
| 型 | 正の整数 |
| 既定 | **1**（空欄・未指定も1） |
| 適用対象 | `supply_role=assembly` の子のみ |

### 3.2 `confluence` の子に `bom_qty > 1` は不正

`confluence` は「同種のものが複数経路から集まり、需要を分担する」型である。
倍率は意味を持たない。

**`supply_role=confluence` かつ `bom_qty > 1` は lint でエラーとすること**（§7）。

実装上は、`confluence` の子では `bom_qty` を**常に1として扱う**（値を無視する）。
ただし lint が警告するので、書けてしまう状態は許容しない。

### 3.3 既存モデルへの列追加

**全モデル（git 管理下）に `bom_qty` 列を追加し、値は空欄とする。**
`supply_role` 導入時（`39bcb44`）と同じ方針。

**`.gitignore` 対象のバックアップフォルダには触れないこと。**
`git ls-files` で対象を取得する方式を用いること（`os.listdir()` は使わない）。

---

## 4. 数量計算の実装

### 4.1 格納

`bom_qty` は**ノードごとの値**なので、`PlanNode` の属性として保持する。
`supply_role` と同じ扱い。

（`cpu_size` は計画全体で単一のため `SCTree` 属性。**混同しないこと。**）

### 4.2 反映箇所

| ファイル | 現状 | 変更後 |
|---|---|---|
| `sc_tree_to_df.py` | `len(...) × sc_tree.cpu_size` | `× sc_tree.cpu_size × node.bom_qty` |
| `app.py`（チャート2箇所） | 同上 | 同上 |
| PPC 側 | 数量がロット数ベース | `× cpu_size × bom_qty` |

**PPC の反映箇所は調査して報告すること。**
`ppc_event_ledger` の `qty` 列、`ppc_node_pl_summary`、`ppc_kpi_summary.json` 等、
数量が使われる箇所を全て洗い出し、どこに掛けるかを設計してから実装すること。

### 4.3 Planning Engine は無変更

`backward_planner.py` / `forward_planner.py` / `push_pull.py` /
`plan_copy.py` / `sc_tree.py` は**変更しないこと。**

`plan_node.py` は `bom_qty` フィールドの追加のみ（`supply_role` と同様）。

---

## 5. 能力制約の単位：CSV に換算値を書く

### 5.1 方針

`_apply_mom_cap_backward` は `len(s_lots)` とロット数で比較する。
したがって `cap_hard`（`capacity_plan.csv` の `max_supply`）の単位は**ロット/週**である。

**この方式は変更しない。** エンジンには触らず、CSV に換算値を書く。

```
cap_hard_lots = cap_pieces / (cpu_size × N)
```

例：タイヤ供給者の能力が週20,000本、`cpu_size=12`、`N=4`

```
max_supply = 20000 / (12 × 4) = 416.67 → 416 ロット/週
```

### 5.2 `cap_pieces` 列と `note` の両方を追加する

**両方が必要である。役割が違う。**

| | 役割 |
|---|---|
| `cap_pieces` | **機械が読む。** lint が検算する |
| `note` | **人間が読む。** なぜその値かを説明する |

```csv
sku_id,node_name,week,max_supply,cap_pieces,note
EV_Model_A,Tire_Supply,2026-W02,416,20000,"20000 pieces/wk / (cpu_size 12 x N 4) = 416.67 -> 416"
```

- `cap_pieces` は**エンジンが読まない参考値**。空欄可（既定：検査しない）
- `note` は既存の列。算定式をそのまま書く

### 5.3 既存モデルへの列追加

`capacity_plan.csv` に `cap_pieces` 列を追加する（値は空欄）。

**ただし `capacity_plan.csv` は warm-up 行の自動追記対象である。**
列追加により warm-up の materialize が壊れないことを確認すること。
壊れる場合は報告し、実装前に指示を仰ぐこと。

---

## 6. 検証用モデル `bom-test-2026`

### 6.1 目的

**N が正しく効いていることを、golden を汚さずに検証する。**

既存モデルは全て N=1 なので、既存モデルでは検証できない。
`ev-europe-2026` に手を入れると golden が変わるため、新規に最小モデルを作る。

### 6.2 題材：タイヤ4本

**「EV 1台にタイヤ4本」は説明を要しない題材であり、
N が効いているかを一目で確認できる。**

### 6.3 構成

```
Tire_Supply    (leaf_in, assembly, bom_qty=4)  ┐
                                                ├→ Vehicle_Assy (mom) → SP → DC → Dealer
Battery_Supply (leaf_in, assembly, bom_qty=1)  ┘
```

**同じ親の下に N=4 と N=1 が並ぶ**ため、「N がノードごとに効く」ことが確認できる。

最小構成でよい。SKU は1つ、市場は1つで足りる。
既存モデルの CSV 構成に倣い、必要な22ファイル前後を用意すること。

`planning_config.csv` に `cpu_size` と `warmup_lt` を設定すること。

### 6.4 検証内容

`tools/sweep_flags.py` で `cpu_size` を 1 と 12 で振り、以下を確認する。

| cpu_size | N | ロット数 | S_Qty（タイヤ） | S_Qty（バッテリー） |
|---|---|---|---|---|
| 1 | 4 / 1 | 5 | **20** | **5** |
| 12 | 4 / 1 | 5 | **240** | **60** |

**ロット数は cpu_size / N によらず不変であること。**

金額も同様に、`Revenue = 単価 × S_Qty` で N 倍・cpu_size 倍になることを確認する。

### 6.5 golden への追加

**`bom-test-2026` を golden に追加するかは、本 Letter では決めない。**
まず動作を確認し、golden 追加の要否を報告すること。

---

## 7. lint 項目（設計文書への追記のみ）

**lint 自体は未実装のため、`docs/design/lot_id_traceability_and_coverage_views.md` §6 に
項目を追記するに留める。** 実装は別途。

```
[BOM] supply_role=confluence かつ bom_qty > 1
      → confluence は需要を分担する型であり、倍率は意味を持たない。【エラー】

[BOM] bom_qty が正の整数でない（0、負数、小数）
      → 【エラー】

[能力] max_supply × cpu_size × bom_qty が cap_pieces と一致しない（誤差1単位超）
      → 換算誤りの疑い。【警告】
      cap_pieces が空欄の場合は検査しない

[単位] uom ラベルが実態と食い違っている
      → oil-global の Hormuz / RedSea が KL のまま（実体は10万バレル相当）
      → 機械判定は困難。目視確認項目として記録
```

---

## 8. 本 Letter の範囲外

| 項目 | 扱い |
|---|---|
| PPC 単価を「1個あたり」に書き換える | **不要**（§2.5。既存は全て N=1・cpu_size=1 のため値が同じ） |
| `cpu_size` の SKU 単位化 | **対象外**（`docs/design/global_oil_model_three_steps.md`） |
| コプロダクト・歩留まり | **対象外**（同上） |
| lint の実装 | 別件（本件では設計文書への追記のみ） |
| デッドコード削除（`lots_to_qty` 等） | 別件 |
| CLAUDE.md の A1 記録の訂正 | 別件 |
| `mom_ref_node_id` / `push_eol_week` / `plan_mode` 既定値 | 別件 |

---

## 9. テスト要件（3層）

### 9.1 Unit

- `bom_qty` 列が読まれ、`PlanNode` に格納されること
- 空欄・未指定が **1** になること
- 正の整数以外（0、負数、小数、文字列）が与えられた場合の挙動を定義し、テストすること
- `sc_tree_to_planning_df` の数量が `len(...) × cpu_size × bom_qty` になること
- `supply_role=confluence` の子では `bom_qty` が無視され、常に1として扱われること
- `bom_qty` が `SCTree` ではなく `PlanNode` の属性であること（`cpu_size` との区別）

### 9.2 Integration（`bom-test-2026`）

§6.4 の表の通り。

- cpu_size=1 / N=4 → タイヤ S_Qty = ロット数 × 4
- cpu_size=12 / N=4 → タイヤ S_Qty = ロット数 × 48
- **ロット数は両方で不変**
- バッテリー（N=1）が正しく1倍のままであること
- PPC の Revenue / Cost / Profit が S_Qty に比例すること

### 9.3 golden（12ケース）

| 状況 | 判定 |
|---|---|
| **全12ケースが無変化** | **正常**。既存は全て N=1 |
| いずれかが変化した | **異常**。原因を報告し、コミットしないこと |

`series_md5` はロット件数のハッシュであり、N に依存しない。
**PPC の金額も、N=1・cpu_size=1 では変わらないはずである。**

---

## 10. 報告してほしいこと

1. **PPC の数量反映箇所の調査結果**（§4.2）と、どこに掛けるかの設計
2. `capacity_plan.csv` への `cap_pieces` 列追加が warm-up materialize に影響しないか（§5.3）
3. `bom-test-2026` の構成（ファイル一覧、ノード構成、パラメータ）
4. 修正の差分（`git diff`）
5. §9.1 の Unit テスト結果
6. §9.2 の Integration 結果（**§6.4 の表の全数値**）
7. §9.3 の golden 結果（**全件無変化であること**）
8. `bom-test-2026` を golden に追加すべきかの意見（§6.5）
9. `git status`（`.gitignore` 対象に触れていないこと）
10. 気づいた点

---

## 11. 手順

```
① PPC の数量反映箇所を調査し、設計を報告する（実装前に一度停止）
② スキーマ拡張（bom_qty 列、cap_pieces 列）
③ 数量計算の実装（KPI / 表示 / PPC）
④ bom-test-2026 の作成
⑤ §9.1 Unit テスト
⑥ §9.2 Integration（sweep で cpu_size 1/12 を振る）
⑦ §9.3 golden 12ケース（全件無変化を確認）
⑧ lint 項目を設計文書に追記
⑨ 大杉の差分レビュー
⑩ 承認後、コミット
```

**⑨の前にコミットしないこと。**
**①の時点で一度報告し、設計の合意を得てから②へ進むこと。**

---

## 12. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること
- `capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと
- **`.gitignore` 対象のフォルダに触れないこと**（`git ls-files` で対象を取得する）
- コミットメッセージは、指定したもの以外の行（`Co-Authored-By` 等）を
  **勝手に追加しないこと**
- **指示に矛盾を見つけた場合は、実装前に指摘すること。**
  Letter A §2.6 は §4.2 と矛盾しており、指摘を受けて訂正した経緯がある

---

## 13. 参考

- `requests/request_letter_a_cpu_size_to_plan.md` と承認通知（`cpu_size` の意味論）
- `requests/request_fix_a1_supply_role_rev2.md`（`supply_role` の導入）
- `docs/design/global_oil_model_three_steps.md`（単位変換を実装しない判断）
- `docs/design/design_memo_confluence_assembly_autotuning.md` §B（組立型）
- `docs/design/demand_anchored_lot.md`（Rule 2 / Rule 5、lot identity の保全）
- `tools/sweep_flags.py`（検証手段）
