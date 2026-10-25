# Request Letter：warmup の cap_soft・木の属性の空欄・残存期間の判定（先入れ先出し）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-25）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `0f40094`。試行 2 の報告書は大杉さんがこの依頼書より先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：試行 2 の報告書 `docs/development/WOM_BSSEAF_Cosmetics_Trial_B2_Report.md`（§5 の決めてほしいこと）と、それへの大杉さんの回答（2026-10-25）。設計書 `requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.4.md`
- 種別：**コードの変更を含む**。保護対象のコア（`AGENTS.md` §10 の 6 ファイル）は**変えない**。変えるのは `wom/engine/warmup.py`・`wom/engine/sc_tree_builder.py` と、新しい道具 `tools/shelf_life_check.py`。golden が変わる場合は、再生成の前に変わるモデルと理由を報告する。

---

## 0. 大杉さんの決定（2026-10-25）

| # | 決定 |
|---|---|
| a | 残存期間を割るときの業務の扱いは「**能力を足す**」 |
| b | 残存期間の判定は**先入れ先出しの年齢**で数える。エンジンは変えない（Lot_ID の割り当ては需要の単位のまま）。判定の道具の側で計算する |
| c | warmup の cap_soft の件は、変更課題①の**前に直す**（Claude君の判断に同意） |
| d | 木の属性の**空欄は N/A（未設定）、0 は明示の 0**。0 を設定したいときは 0 を書く |
| e | 店頭在庫は `ss_days`＝14 日で表す（X2 ではなく安全在庫として） |
| f | 残存期間の判定の道具を `tools/` に入れる（Claude君の判断に同意） |

**b の理由（Claude君が試行 2 の結果から数え直したもの）**：Lot_ID は需要の単位で物理の個体ではない（決定記録 §1.1）。B3 で「52 週を超える lot が 195」と出たのは、作り置きに回された代理店の 2029 年分の Lot_ID が工場の出荷から納品まで待っているように数えたため。SKU ごとに製造の早い順と納品の早い順を対にした（先入れ先出しの近似）と、滞留の最大は 159・163 週 → **16・19 週**、52 週超は 195 → **0** になる。倉庫は古い物から出すので、作り置きは毎週入れ替わる。

## Part A：warmup の行に cap_soft を写す（`wom/engine/warmup.py`）

### A.1 今の動き（試行 2 の報告書）

warmup の行を作る処理が、`capacity_plan.csv` の `max_supply` だけを最初の実週から後方へ写し、`cap_soft` を写さない。soft の工場（`demand_envelope`＝soft）は warmup の週に cap_soft が未設定になり、cap_hard の良品の上限まで作る。cap_soft の超過の記録も数えられない。以前の「cap_soft の配線が切れて休眠した」件と同じ型の、データの経路の欠けである。

### A.2 直すこと

- warmup の行に、最初の実週の **`cap_soft` も写す**（新書式・旧書式の両方。最初の実週の `cap_soft` が空欄なら、warmup の行も空欄＝未設定）。
- 能力の値の意味（空欄＝未設定、0＝能力ゼロ、Start Here R4）を変えない。
- `capacity_plan.csv` に `cap_soft` 列が無いモデルは、今と完全に同じ（列を作らない）。
- 今後 `capacity_plan.csv` に能力の値の列が足されたときに同じ欠けが起きないよう、**写す列を一か所の一覧**にし、写さない列（`source` など）は理由をコメントに書く。

### A.3 確かめること

- 単体：`cap_soft` 列のある能力の表で、warmup の行に cap_soft が入る。空欄は空欄のまま。列が無ければ列を作らない。
- golden：`capacity_plan.csv` に `cap_soft` 列があり warmup のあるモデルを先に一覧にし、golden が変わるかを報告する（変わるなら、変わるモデル・項目・理由を表にしてから再生成）。

## Part B：木の属性の空欄・不正な値（`wom/engine/sc_tree_builder.py`）

### B.1 今の動き

- `ss_days`・`init_stock_days` の列に空欄の行があると、`int(row.get("ss_days", 0) or 0)` が NaN を int にしようとして止まる（`cannot convert float NaN to integer`。ファイル・行・列が出ない）。
- `demand_envelope` は、`hard`・`soft` 以外の値（綴りの誤りなど）を黙って `hard` にする。化粧品の工場は soft が要件なので、綴りを誤ると黙って定義どおりでない計画になる。

### B.2 直すこと（決定 d）

| 列 | 空欄・列なし | 0 | 正の整数 | それ以外（負、整数でない、数値でない） |
|---|---|---|---|---|
| `ss_days` | 未設定（在庫の時間を持たない。計画は 0 と同じ） | 明示の 0 | その日数 | **止める** |
| `init_stock_days` | 同上 | 明示の 0 | その日数 | **止める** |

| 列 | 空欄・列なし | `hard`・`soft`（大文字・前後の空白は許す） | それ以外 |
|---|---|---|---|
| `demand_envelope` | `hard`（今の既定） | その値 | **止める** |

- 止めるときは、`sc_tree_master.csv` の**行・列・ノード名・製品・値**と、直し方を出す（歩留まり Part A の `YieldRateError` と同じ形）。
- 計画の上では、空欄（未設定）と 0 はどちらも「在庫の時間を持たない」で同じ動きになる。保護対象のコア（`plan_node.py`）は変えないので、ノードの属性は 0 のまま持ってよい。未設定と明示の 0 を区別して記録したほうがよい所（Flow Check の表示、lint など）があれば、報告書に提案として書く（今回は直さない）。
- `supply_role`・`bom_qty` も、不正な値を黙って既定にしている（`_parse_bom_qty` の docstring）。**今回は変えず**、サンプルモデルに不正な値・空欄が実際にあるかを調べて報告する（止める形に揃えるかは後で大杉さんが決める）。

### B.3 確かめること

- 単体・結合：CSV → 実ローダ → ノードで、空欄・0・正の整数・不正な値が上の表のとおりになる。`demand_envelope` の `Soft`・` soft ` は soft、`sfot` は止まる。
- golden：サンプルモデルに `ss_days`・`init_stock_days` の空欄、`demand_envelope` の不正な値が無いかを先に一覧にする（あれば、それが止まるようになる。報告してから直し方を決める）。golden は変わらない見込み。

## Part C：残存期間の判定の道具（`tools/shelf_life_check.py`、決定 b・f）

### C.1 何を数えるか

市場への納品（leaf_out の実出荷）ごとに、**先入れ先出しで出荷したと考えたときの製品の年齢**を数える。

- **製造週**：工場（MOM）の実出荷週（`_actual_ship`）。作り置きが supply point の I にいる間は、物理的には工場の完成品倉庫にいる（試行 1 の報告書 Q5、Start Here §2.1）。
- **先入れ先出し**：物の在る所（工場の完成品倉庫＝supply point の I、DAD、市場の leaf_out の店頭）ごとに、SKU 別の待ち行列を持つ。入ってきた物に「製造週」の札を付けて後ろに並べ、出ていく物は**一番古い札**から出す。区間を移動中の物は札を持ったまま運ばれ、着いた週に着いた所の列に入る。
- **年齢**：納品週 − その物の製造週（**計画の週の番号**で数える。ISO の週ラベルを引き算しない）。
- 数える単位は lot（1 lot＝`cpu_size` 個）。同じ週に出ていく物どうしの順は問わない（年齢は週の単位なので結果に影響しない）。
- 入力は段階 D の出荷の記録（`wom/valuechain/records.py` の `build_records`。試行 1 の報告書 Q2 の推奨）。木は headless（`tools.run_headless_from_folder.run` の `extra_plugins`）から受け取る。

### C.2 使い方と出力

```
python -m tools.shelf_life_check --model-dir <モデル> --max-age-weeks 52 [--plugins …] [--out <フォルダ>]
```

- `--max-age-weeks` は**必須**（許容の年齢。黙った既定値を作らない）。`--plugins` は headless と同じ規則（省略でモデルの推奨の組）。
- 出力（CSV）：
  - 納品ごと：SKU・チャネル・納品週・製造週・**先入れ先出しの年齢**・参考として **Lot_ID で数えた滞留**（前回までの式：max（需要週、市場の実出荷週）− その Lot_ID の工場の出荷週）。
  - 集計：SKU 別・チャネル別の年齢の最小・最大・分布、許容を超えた納品の数。
- 画面への出力：集計の表と、許容を超えた納品があればその数・SKU・週。
- 期末注文残（市場の実出荷が無い需要）は納品ではないので数えない。件数だけ別に出す。

### C.3 止める条件（物の数が合わないとき）

- ある所から出ていく数が、その週にその所にある数を超える（記録の食い違い）。
- 市場への納品の総数が、市場の実出荷の総数と合わない。
- どちらも、所・週・SKU・数を出して止める（黙って 0 や負の年齢にしない）。

### C.4 確かめること

- 単体（合成の記録）：(1) 作り置きの無い直列の流れで、先入れ先出しの年齢＝Lot_ID で数えた滞留＝リードタイムの合計。(2) 作り置きのある流れで、Lot_ID の滞留は長いが、先入れ先出しの年齢は在庫の深さの分だけ（例を手で作って値を固定する）。(3) 1 つの所から複数のチャネルへ出る場合。(4) C.3 の止める条件。
- 結合：Cookie-jp-2026 で動き、納品の総数＝市場の実出荷の総数。
- 化粧品の写しの値（報告書に書く。写しはリポジトリに入れない）：`output/bsseaf_cosmetics/` の B2・B3（と B3s）で、先入れ先出しの年齢の最大と 52 週超の数。Claude君の近似（B3 で美容液 16・クリーム 19 週、52 週超 0）とどれだけ違うか。違う場合、近似の何が粗かったか（例：店頭の 2 週の在庫を別の列として持ったこと）。

### C.5 前回までの道具との関係

`output/bsseaf_cosmetics/shelf_life_check.py`（Lot_ID の滞留）は写しの中に残す。新しい道具は、その式を参考の列として持つ。

## Part D：テストと文書

- 新しいテストのファイルは `tests/conftest.py` の対応表に 1 行足す。
- 途中：`python -m tools.quick_check --smoke`、`--area core`。最後に 1 回：`--full`（読み込みと warmup を変えるので、全モデルに関わる）。golden を含む pytest は並行させない。
- `CLAUDE.md` の末尾に節を足す（3 つの変更、`tools/shelf_life_check.py` の使い方、先入れ先出しの年齢の定義）。
- Start Here への追記は、報告書を見て Claude君が行う。

## Part E：報告書

`docs/development/WOM_WarmupSoft_BlankAttrs_ShelfLifeFIFO_Report.md` に次を書く：

1. 着手時と完了時の SHA、変えたファイル。
2. Part A・B：変えた所、golden の前の一覧（cap_soft 列と warmup のあるモデル、空欄・不正な値のあるモデル）、golden の結果。
3. Part B：`supply_role`・`bom_qty` の黙った既定値の調べ。未設定と明示の 0 を区別して記録したほうがよい所の提案。
4. Part C：道具の作り（待ち行列の持ち方、入力）、テスト、化粧品の写しの値と Claude君の近似との比較。
5. テストの結果（件数、full の時間）。

## Part F：commit

依頼書（`docs(request): …`）と実装を別の commit にする。git は大杉さんが Windows で行う。commit メッセージの下書きは `commit_msg*.txt`（空いている番号を使う）。
