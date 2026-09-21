# 承認通知：`cpu_size` の計画パラメータ化（Letter A）

**発行日**：2026-09-01
**発行者**：大杉（オーナー）
**対象**：`requests/request_letter_a_cpu_size_to_plan.md`
**種別**：**スキーマ変更＋リファクタリングの承認とコミット指示**

---

## 1. 差分を承認します

Request Letter §0 の承認条件を、以下により満たしたと判断します。

- [x] Request Letter 起票
- [x] 3層テスト（Unit / Integration / golden）実施と報告
- [x] **オーナーによる差分レビュー — 本書をもって承認**
- [x] **golden 全12ケースが無変化であること**

### 1.1 §2.6 の指示が誤っていました。訂正します

**Code 君の判断が正しく、Request Letter §2.6 が誤っていました。**

`lot_generator` の `cpu_size` は `lot_count = ceil(qty / cpu_size)` という
**ロット数そのものを決める除数**である。ここに `planning_config.csv` の値（例：12）を
渡すと、**ロット数が 1/12 になる。**

一方で同じ Letter の §4.2 は「`cpu_size=12` でもロット数が変わらないこと」を要求していた。
**同一文書の中で矛盾していた。**

そして意味論としても、Code 君の実装が正しい。

```
ロット生成    需要数量をロットに切る。cpu_size 非依存であるべき
表示・KPI     1ロットが何個かを掛ける。cpu_size に依存する
```

**`cpu_size` は「1ロットが何個を表すか」という解釈のパラメータであって、
ロットの切り方を決めるものではない。** したがって表示・KPI 層にのみ効くのが正しい。

この判断は、次の "1 set rule" の定式化とも整合する。

```
S_Qty[w] = len(psi[w]["S"]) × cpu_size × N
           ↑ ロット数は不変    ↑ 解釈だけが変わる
```

**矛盾を指摘し、指示の文言ではなく意図に沿って実装し、
その判断を明示的に報告した対応を評価する。**

### 1.2 承認の根拠

**① 実測が予測通り**

```
lot-bucket-entries   cpu=1 → 1,708,517    cpu=12 → 1,708,517   完全に不変
KPI 数量             cpu=12 が cpu=1 の正確に12倍
```

**ロット数は変わらず、数量だけが12倍。** Letter A が目指した状態そのもの。

**② golden 全12ケース無変化**

判定表の「全12ケースが無変化 → 正常」に一致。本件は動作を変えないリファクタリングであり、
`series_md5` はロット件数のハッシュなので `cpu_size` に依存しない。予測通り。

**③ テスト 200 passed / 0 failed**

旧190件に退行なし、新規10件が緑。`PlanNode` に `cpu_size` 属性が存在しないこと、
`PlanNode(cpu_size=...)` が `TypeError` になることまで確認されている。

**④ 保護対象コアへの言及が正確**

`plan_node.py` と `sc_tree.py` への変更が、いずれも事前承認済みであることを
自ら確認し報告している（前者は Letter §2.3、後者は①の承認メッセージ）。
`backward_planner` / `forward_planner` / `plan_copy` / `push_pull` には触れていない。
**禁足ルールの手続きが正しく機能した。**

**⑤ `.gitignore` の扱いを改善**

前回（2026-08-30）にバックアップフォルダを誤って触った反省を踏まえ、
`os.listdir()` ではなく `git ls-files` で対象16件を取得する方式に変更している。
**同じ誤りを繰り返さない仕組みにした。**

---

## 2. これで確定した `cpu_size` の意味論

```
定義        1ロットが何個を表すか（計画全体で単一の値）
置き場所    planning_config.csv の key → SCTree.cpu_size（既定1で初期化）
読み込み    warmup.py の read_cpu_size(model_dir)
効く層      表示・KPI・（今後）コスト算定
効かない層  ロット生成、Planning Engine
```

**Letter B（BOM 数量 N）の土台が整った。**
「どのノードの cpu_size か」という曖昧さが消え、N を足す場所が明確になった。

---

## 3. 実施してほしいこと

### 3.1 コミット対象

| 対象 | 現状 |
|---|---|
| `data/sample/*/sc_tree_master.csv`（16モデル） | modified（`cpu_size` 列削除） |
| `wom/engine/warmup.py` | modified |
| `wom/engine/sc_tree_builder.py` | modified |
| `wom/engine/sc_tree_to_df.py` | modified |
| `wom/model/plan_node.py` | modified |
| `wom/model/sc_tree.py` | modified |
| `wom/gui/app.py` | modified |
| `tools/run_headless_from_folder.py` | modified |
| `tools/sweep_flags.py` | modified |
| `tests/test_cpu_size_plan_wide.py` | **untracked。add を忘れないこと** |

**`git commit -am` は使わないこと。** 明示的に `git add` すること。

### 3.2 コミット前の確認

**`git diff --cached --stat` を提示すること。**

- `sc_tree_master.csv` が **16件ちょうど**
- `capacity_plan.csv` / `demand_forecast.csv` が**含まれていない**
- `tests/test_cpu_size_plan_wide.py` が含まれている
- `tests/golden/*.json` が**含まれていない**（本件では golden は無変化）
- `.gitignore` 対象のバックアップフォルダが含まれていない

### 3.3 コミットメッセージ

**以下の通りに書くこと。指定していない行（`Co-Authored-By` 等）を追加しないこと。**

```
refactor(schema): make cpu_size a plan-wide parameter, not a node attribute

WOM's rule is that cpu_size is a single planning parameter shared by every
node, but it lived as a per-node column in sc_tree_master.csv, so a model
could silently give different nodes different values. All 17 models happened
to use 1 everywhere, which is why nothing broke.

Moves it to planning_config.csv, read by warmup.read_cpu_size() and held on
SCTree (initialised to 1, so the attribute always exists and callers need no
getattr fallback). Drops the column from the 16 tracked models and removes
PlanNode.cpu_size.

Lot generation keeps its own cpu_size=1: lot_count = ceil(qty / cpu_size)
decides how demand is cut into lots, which must stay independent of how many
pieces a lot represents. cpu_size is an interpretation applied downstream --
in KPI conversion and chart display -- not a divisor on lot creation. Feeding
the config value there would have divided the lot count by 12, contradicting
the requirement that lot counts stay fixed.

Verified on soysauce-jpy-2027: raising cpu_size from 1 to 12 leaves the raw
PSI bucket lengths identical at 1,708,517 while every KPI quantity scales by
exactly 12. All 12 golden cases unchanged; series_md5 hashes lot counts and
so does not depend on cpu_size.

Groundwork for the "1 set rule" (BOM quantity N), where
S_Qty[w] = len(psi[w][S]) * cpu_size * N.
```

### 3.4 コミット後

- `git status` で `data/sample/` に意図しない変更が無いことを確認して報告
- `Get-Process python` で孤立プロセスが無いことを確認
- **push はしないこと。** オーナーが手元で実施する

---

## 4. 本コミットに含めないこと

| 項目 | 扱い |
|---|---|
| **BOM 数量 N（`bom_qty` 列）の実装** | **Letter B。承認後すぐ起票する** |
| `capacity_plan.csv` の `cap_pieces` 列と note | Letter B |
| 検証用モデル `bom-test-2026` の作成 | Letter B |
| lint 項目の追加 | Letter B |
| デッドコード削除（`lots_to_qty` / `qty_to_lot_count` / `cpu_size_default`） | 別件 |
| CLAUDE.md の A1 記録の訂正 | 別件 |
| `mom_ref_node_id` / `push_eol_week` / `plan_mode` 既定値 | 別件 |
| smartx の `holiday_calendar.csv` 文字化け、`uom` ラベルの不一致 | 別件（lint 候補） |

---

## 5. 記録

```
2026-08-30  調査    cpu_size は死んでいる列と判明
                    全17モデルで値1、Planning Engine は一切参照しない
                    呼び出し元は全て固定値1、lots_to_qty 等はデッドコード
2026-09-01  Letter A 起票
            ①       格納先の提案。warmup_lt はどこにも保存されていないことが判明し、
                    SCTree 属性を選択。オーナーが __init__ での初期化を条件に承認
            ②〜⑤   実装。§2.6 の矛盾を発見し、意図に沿って実装を変更
            ⑥       本書による承認
```

**§2.6 の矛盾は、Letter を書いた側（オーナー）の誤りである。**
指示の文言に従わず、矛盾を指摘した上で意図に沿って実装した判断が正しかった。
同様のケースでは、今後も同じ対応を求める。
