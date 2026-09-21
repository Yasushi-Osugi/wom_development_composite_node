# 承認通知：BOM 数量 N の導入（Letter B）

**発行日**：2026-09-01
**発行者**：大杉（オーナー）
**対象**：`requests/request_letter_b_bom_qty.md`
**種別**：**スキーマ拡張＋数量・金額計算＋新規サンプルモデルの承認とコミット指示**

---

## 1. 差分を承認します

Request Letter §0 の承認条件を、以下により満たしたと判断します。

- [x] Request Letter 起票
- [x] 3層テスト（Unit / Integration / golden）実施と報告
- [x] **オーナーによる差分レビュー — 本書をもって承認**
- [x] **golden 既存12ケースが無変化であること**
- [x] 保護対象コア6ファイルに触れていないこと（`plan_node.py` のフィールド追加のみ、Letter §4.3 で承認済み）

### 1.1 承認の根拠

**① PPC の増幅点を1箇所に絞り込んだ調査**

`LotCostAccumulator.qty` が accumulator（product × channel × week）ごとに1つしかなく、
**ノードごとの倍率を表現できない**という発見が本質だった。

Letter B §4.2 の「PPC 側に `× cpu_size × bom_qty` を掛ける」という指示は、
**この構造を知らずに書かれていた。** そのまま実装すれば、タイヤもバッテリーも
同じ倍率になっていた。**指摘に感謝する。**

Step 1a のみを変更し、Transfer Price → Tariff → Landed Cost → Profit Zone → KPI が
`acc.supplier_cost_base` の上に積まれることで自動伝播する、という設計は
依存関係を追跡した上での結論であり、確度が高い。

**② Step 1b / 1c を対象外とした判断**

①の承認時点では「Step 1a/1b」としていたが、実装時に 1b も対象外へ絞られた。
**設計判断であるため確認を求めたところ、既存3モデルを調査した回答が返った。**

- 質問の前提そのものを訂正（Step 1b が読むのは `edge_cost_master.csv` ではなく
  `ppc_edge_cost_rule.csv`。前者は Tariff&FX パネル用の別エンジン）
- soysauce の `Materials_JP→Brewing_Noda` が唯一の実例で、$0.3/lot は
  「醤油1ケース分の原材料を運ぶ費用」＝**完成品1個分あたり**
- apparel は該当行なし（生地代は MOM の conversion_cost に "CIF価格（生地込み）" として一本化）
- ev-europe も該当行なし（部材ごとの輸送費は一切モデル化されていない）
- 構造的根拠：`ppc_edge_cost_rule.csv` と `ppc_node_cost_rule.csv`（Step 1c、
  (b) と確定済み）が、コード上まったく同じ `basis="per_lot"` の扱いを受けている

**結論「既存モデルは全て (b) 完成品1個分あたりの規約」を妥当と判断する。**

そして「"反証なし＋支持事例1件" という強さの根拠」と**確度を正直に述べた**点、
将来の例外マップの余地を示した点、調査結果を `ppc_forward.py` の docstring に
根拠として残した点を評価する。

**③ `ppc_psi_bridge.py` で `bom_qty` を適用しない判断**

leaf_out の売上数量に部材の倍率は関係ない。**EV を5台売ったのであって、
タイヤ20本を売ったのではない。** 正しい区別。

**④ golden の検算が合う**

```
Vehicle_Assy   P=200  S=100     ← 子2つから各100が加算（assembly = 全量供給）
Tire_Supply    P=100  S=100     series_md5 = c1efed775621
Battery_Supply P=100  S=100     series_md5 = c1efed775621  ← 完全一致
```

**`Tire_Supply` と `Battery_Supply` の `series_md5` が同一**であることは、
**ロット数が N によらず不変**であることのハッシュレベルでの証明である。
Letter B §2.1 の設計原則が守られている。

金額も整合する。

```
Tire      $80 × 4本 × 100台 =  32,000
Battery $6,000 × 1個 × 100台 = 600,000
                      小計    632,000
差分（conversion / logistics）  175,000
                      合計    807,000  = cost_base
revenue 3,200,000 − 807,000 = 2,393,000 = gross_profit
gross_margin 74.7812%
```

**`bom_qty=4` が金額に正しく効いている。**

**⑤ テスト 239 passed / 0 failed**

既存200件に退行なし、新規38件が緑、`bom-test-2026` の golden 1件を追加して239件。

**⑥ `.gitignore` の扱い**

`git ls-files` ベースの列挙を継続。バックアップフォルダに触れていない。

**⑦ apparel-us-2026 の warm-up 汚染を自己申告**

bash タイムアウトによる中断から生じた不整合を発見し、`git checkout` で復元してから
再実行した経緯を報告している。**隠さず報告する姿勢を評価する。**

---

## 2. 実施してほしいこと

### 2.1 コミット対象

| 分類 | 対象 |
|---|---|
| コード | `wom/engine/sc_tree_builder.py`、`wom/engine/sc_tree_to_df.py`、`wom/gui/app.py`、`wom/model/plan_node.py`、`wom/ppc/ppc_engine.py`、`wom/ppc/ppc_forward.py`、`wom/ppc/ppc_psi_bridge.py`、`wom/ppc/ppc_runner.py` |
| スキーマ | 16モデルの `sc_tree_master.csv`（`bom_qty` 列）、16モデルの `capacity_plan.csv`（`cap_pieces` 列） |
| 新規モデル | `data/sample/bom-test-2026/`（22ファイル） |
| golden | `tests/golden/bom-test-2026.json`（**新規追加**） |
| テスト | `tests/test_bom_qty.py`、`tests/test_ppc_bom_qty.py` |
| spec | `tools/sweep_specs/bom_test_cpu_size.json` |
| 設計文書 | `docs/design/lot_id_traceability_and_coverage_views.md`（lint 項目の追記） |

**`git commit -am` は使わないこと。** 明示的に `git add` すること。

### 2.2 コミットに含めてはならないもの

- **`output/` 配下**（`bom-test-2026` の golden 生成で `output/ppc/` が作られている）
- `capacity_plan.csv` / `demand_forecast.csv` の **warm-up 自動追記分**
  （スキーマ列追加は含める。warm-up 行は含めない）
- `.gitignore` 対象のフォルダ

### 2.3 コミット前の確認

**`git diff --cached --stat` を提示すること。**

確認したいのは以下。

- `sc_tree_master.csv` が **16件ちょうど**
- `capacity_plan.csv` が **16件ちょうど**、かつ**列追加のみで warm-up 行を含まない**
- `data/sample/bom-test-2026/` が **22ファイル**、`output/` サブフォルダを含まない
- `tests/golden/bom-test-2026.json` が含まれている
- **既存の `tests/golden/*.json` 12件が含まれていない**（無変化のため）
- 保護対象コア（`backward_planner` / `forward_planner` / `plan_copy` / `push_pull` / `sc_tree`）が
  **含まれていない**

**上記のいずれかが合わない場合は、コミットせず報告すること。**

### 2.4 コミットメッセージ

**以下の通りに書くこと。指定していない行（`Co-Authored-By` 等）を追加しないこと。**

```
feat(schema): add bom_qty for component quantity per unit

WOM had no way to say that one vehicle needs four tyres. supply_role=assembly
meant "the child supplies the full quantity", which is only correct when every
BOM quantity is 1. Organised assembly chains -- EV, electronics -- could not be
modelled honestly.

Adds bom_qty to sc_tree_master.csv, on the child row alongside supply_role, as
an attribute of the edge from parent to child. Blank defaults to 1, so all 16
existing models are unaffected and the 12 existing golden cases are unchanged.

N never touches the lot lists. Lot counts stay 1:1 between parent and child, so
lot identity survives intact -- multiplying the list would recreate the
duplication removed in 39bcb44. N applies outside the planning engine:

  S_Qty[w] = len(psi[w][S]) * cpu_size * bom_qty

PPC unit prices are per smallest unit; cpu_size and bom_qty are coefficients on
top. Only Step 1a in ppc_forward.py multiplies by bom_qty. Transfer price,
tariff, landed cost, profit zone and KPI all accumulate on top of
supplier_cost_base, so one point is enough for the whole chain.

Step 1b and 1c are left alone. A survey of the three models that could have
shown otherwise found that ppc_edge_cost_rule.csv prices are per finished unit,
not per component: soysauce prices Materials_JP -> Brewing_Noda at $0.3 for the
raw material behind one case of soy sauce, while apparel and ev-europe carry no
per-component freight rows at all. The evidence is one supporting case and no
counter-example; if a model ever needs genuinely per-component freight, an
exception map keyed by (product_id, edge_id) is the place to add it.

New sample model bom-test-2026 exercises this: Tire_Supply (bom_qty=4) and
Battery_Supply (bom_qty=1) both feed Vehicle_Assy. Their series_md5 hashes are
identical -- the lot counts really are the same -- while the tyre cost comes out
at $80 x 4 x 100 = $32,000 against the battery's $6,000 x 1 x 100. Added to
golden so the feature is covered by the anti-degrade net.

Also adds cap_pieces to capacity_plan.csv as a reference column the engine does
not read. cap_hard stays in lots per week, so a supplier able to make 20,000
tyres a week with cpu_size 12 and bom_qty 4 is written as 416, and cap_pieces
records the 20,000 the number came from. Lint items for this and for
confluence with bom_qty > 1 are recorded in the traceability design doc.
```

### 2.5 コミット後

- `git status` で `data/sample/` に意図しない変更が無いことを確認して報告
- `tasklist | findstr python` で孤立プロセスが無いことを確認
- **push はしないこと。** オーナーが手元で実施する

---

## 3. 本コミットに含めないこと（別途起票）

| 項目 | 扱い |
|---|---|
| lint の実装 | 別件（本件では設計文書への追記のみ） |
| `cpu_size` の SKU 単位化、コプロダクト、歩留まり | **対象外**（`docs/design/global_oil_model_three_steps.md`） |
| `oil-global` の `uom` ラベル修正 | 別件（lint 候補として記録済み） |
| デッドコード削除（`lots_to_qty` / `qty_to_lot_count` / `cpu_size_default`） | 別件 |
| CLAUDE.md の A1 記録の訂正 | 別件 |
| `mom_ref_node_id` / `push_eol_week` / `plan_mode` 既定値 | 別件 |
| `guarded_files` の中断耐性（§10 で報告された OSError） | 別件。要調査 |
| `pysi_env` に pytest / PyYAML が無い件 | 別件（環境整備） |

---

## 4. 記録：Letter A・B で確定した単位の意味論

```
cpu_size    1ロットが何個を表すか
            計画全体で単一。planning_config.csv → SCTree.cpu_size
            ロット生成には効かない（解釈のパラメータであり、切り方ではない）

bom_qty     親1個あたり、この子部材が何個必要か
            ノードごと。sc_tree_master.csv の子の行 → PlanNode.bom_qty
            supply_role=confluence では常に1として扱う

数量        S_Qty[w] = len(psi[w][S]) × cpu_size × bom_qty

単価        PPC の単価は「最小単位1個あたり」
            cpu_size と bom_qty はその上に掛かる係数

能力        cap_hard の単位はロット/週
            CSV に換算値を書く（cap_pieces と note で根拠を残す）

ロット数    親子で 1:1。N でも cpu_size でも変わらない
            リストを複製してはならない（A1 の重複と同じ形になる）
```

---

## 5. 経緯

```
2026-08-30  A1 修正      supply_role 導入。assembly は N=1 固定と明記
2026-09-01  Letter A     cpu_size を node 属性 → 計画パラメータへ
                         §2.6 が §4.2 と矛盾。指摘を受けて訂正
            Letter B     bom_qty の導入
            ①           PPC の増幅点を調査。§4.2 の指示が構造を知らずに
                         書かれていたことが判明
            訂正         Step 1b の扱いを確認。既存3モデルの調査で (b) と確定
            ②〜⑧        実装、bom-test-2026 作成、239 passed
            ⑨           本書による承認
```

**Letter A・B とも、オーナーの指示に誤りがあり、実装側の指摘によって訂正された。**
指示の文言に従うのではなく、矛盾を指摘した上で意図に沿って実装する対応を、
今後も求める。
