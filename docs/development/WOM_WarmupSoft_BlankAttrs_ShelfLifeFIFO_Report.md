# 報告書：warmup の cap_soft・木の属性の空欄・残存期間の判定（先入れ先出し）

- 依頼書：`requests/RequestLetter_WarmupSoft_BlankAttrs_ShelfLifeFIFO_to_CodeKun.md`（`cedf2f3`）
- 設計書：`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.4.md`
- 実装：Code君（Claude Code、Windows）、2026-10-25

---

## 1. SHA と変えたファイル

- **着手時**：`cedf2f3`（試行 2 の報告書 `76f4c86` の後、依頼書の commit）。
- **完了時**：未 commit（HEAD は `cedf2f3` のまま。下書き `commit_msg122.txt`）。
- **保護対象のコア（`AGENTS.md` §10 の 6 ファイル）は変えていない。**

| 区分 | ファイル | 内容 |
|---|---|---|
| Part A | `wom/engine/warmup.py` | 助走行に写す能力の列を一覧 `_CAPACITY_COPY_COLS`（`max_supply`・`cap_soft`）にした |
| Part B | `wom/engine/tree_attrs.py`（新規） | `TreeAttributeError`、`parse_days`、`parse_envelope` |
| Part B | `wom/engine/sc_tree_builder.py` | `ss_days`・`init_stock_days`・`demand_envelope` をこの読み取りに替えた |
| Part B | `wom/engine/yield_rate.py` | `YieldRateError` を `TreeAttributeError` の子クラスにした（GUI の再送出を一つにするため） |
| Part B | `wom/gui/app.py` | 木の読み込みで `TreeAttributeError` を Demo tree に落とさず再送出（`YieldRateError` も含む） |
| Part C | `tools/shelf_life_check.py`（新規） | 残存期間の判定（先入れ先出しの年齢） |
| テスト | `tests/test_warmup_soft_blank_attrs_fifo.py`（新規、39 件）、`tests/conftest.py`（1 行）、`tests/test_warmup_materialize.py`（期待値 1 件） | §5 |
| 文書 | `CLAUDE.md`（末尾の節）、本書 | |

## 2. Part A・B

### 2.1 Part A：warmup の行に cap_soft を写す

- 新書式（`node_name` 列あり）の助走行は、`(sku_id, node_name)` ごとに最初の実週の **`_CAPACITY_COPY_COLS` の列**（`max_supply`・`cap_soft`）を写す。列がファイルに無ければ写さない（列も作らない）。値は文字列のまま写すので、空欄＝未設定・0＝能力ゼロの意味は変わらない（Start Here R4）。
- 写さない列とその理由はコメントに書いた：`sku_id`・`node_name`・`week`（行のキー）、`source`（助走行の印 `warmup`）、`cap_pieces`（エンジンが読まない記録用の列。写すと全サンプルの能力の CSV が書き換わる）、`region`（記録用）。
- 旧書式（`node_name` 列なし、smartphone）は、もともと最初の実週の行を週だけ替えて**丸ごと**写しているので、`cap_soft` 列があれば既に写っていた。変えていない。
- **既存のテストの期待値を 1 件直した**：`tests/test_warmup_materialize.py` の旧 `test_new_format_multi_node_unchanged_behaviour` は、助走行の `cap_soft` が空欄であることを期待値にしていた（＝この欠けを固定していた）。`80` が写る期待値に直し、docstring に理由を書いた。
- **名前も中身に合わせた**（追補 1）：`test_new_format_multi_node_copies_capacity_values` に変えた（「挙動は変えない」と読める名前のままだと、warmup は max_supply だけを写すと誤読されるため）。名前だけの変更で、`--area core` は 346 passed・失敗 0（176 秒）（full は回し直していない。§5 の full は名前を変える前の値）。
- **化粧品の写しでの効き**：B3 を作り直すと、助走行に `cap_soft`（Serum 14・Cream 11）が入り、工場の週の P の最大が 15・11 → **12・9**（平準化の良品の上限どおり）になった。試行 2 で手で warmup の行を書いた参考の写し B3s と、**PSI が完全に一致**した。

### 2.2 Part B：木の属性の空欄・不正な値

| 列 | 空欄・列なし | 0 | 正の整数 | それ以外 |
|---|---|---|---|---|
| `ss_days`・`init_stock_days` | 未設定（ノードは 0 のまま＝計画は 0 と同じ） | 0 | その日数 | 止める |
| `demand_envelope` | `hard` | — | — | `hard`・`soft`（大文字・前後の空白は可）以外は止める |

- 整数かどうかは値で見る（pandas は空欄のある列を float で読むので、`14.0` は 14 として受ける。`2.5`・`-7`・`abc` は止める）。
- 止めるときのメッセージは歩留まりと同じ形：`sc_tree_master.csv line 11: node 'DC_Local_JP' (product 'Cookie_Local'): ss_days='-3' is not a whole number of days >= 0. Write 0 or a positive integer (e.g. 14), or leave the cell blank for 'not set'.`
- **GUI**：木の読み込みは、どの例外でも Demo tree に切り替えて計画を続ける作りだった。歩留まりのときに `YieldRateError` だけを再送出していたのを、親の `TreeAttributeError` に広げた（空欄・綴りの誤りが、GUI では黙って別の木の計画になるのを防ぐ）。
- **計画の動き**：未設定と 0 は、計画の上ではどちらも「在庫の時間を持たない」で同じ。`plan_node.py` は変えていないので、ノードの属性は 0 で持つ。

### 2.3 golden の前の一覧

`data/sample/` の 16 フォルダを先に調べた（golden の対象外の `rice-…_BK…` を含む）。

| 調べたこと | 結果 |
|---|---|
| `capacity_plan.csv` に `cap_soft` 列があり、warmup がある（Part A で変わりうる） | **0 モデル**（どのサンプルも `cap_soft` 列を持たない。soysauce の cap_soft は `operating_calendar.csv` から作られる） |
| `ss_days` の空欄 | 0 モデル（全行に値がある） |
| `init_stock_days` の列 | どのサンプルにも無い（＝全ノード未設定） |
| `demand_envelope` の値 | 2 モデル（soysauce-jpy-2027・-alloc）だけが列を持ち、値は `hard`・`soft` だけ。空欄・不正な値は 0 |

→ **golden は変わらない見込み**だったので、そのまま full を回した（§5）。

### 2.4 `supply_role`・`bom_qty` の黙った既定値（今回は変えていない）

| 列 | 黙った既定値（今の作り） | サンプルの実際 |
|---|---|---|
| `supply_role` | `confluence` 以外（空欄・綴りの誤り・`assembly`）はすべて `assembly` | 15 モデルは全行空欄。`bom-test-2026` だけ値 `assembly`（4 行空欄）。**不正な値は 0** |
| `bom_qty` | 空欄・0・負・整数でない・数値でないは 1。`confluence` の子は値に関わらず 1 | 15 モデルは全行空欄。`bom-test-2026` は `1`・`4`（6 行空欄）。**不正な値は 0** |

今のサンプルでは、黙った既定値に**空欄だけ**が当たっていて、不正な値は無い。止める形に揃える場合も、空欄の意味（`supply_role`＝assembly、`bom_qty`＝1）を決めておけばサンプルは止まらない。ただし `supply_role` の綴りの誤り（例：`confluense`）は、合流の分け方を黙って組立の複製に変える（需要が子の数だけ増える）ので、止める形にする価値が大きい。

### 2.5 未設定と明示の 0 を区別して記録したほうがよい所（提案、今回は直さない）

1. **lint・Flow Check の表示**：`ss_days` が未設定のバッファ（`buffering_stock_flag`＝1 の DAD）は「安全在庫を決めていない」可能性があり、明示の 0（「持たないと決めた」）とは意味が違う。lint で「decoupling 点で `ss_days` 未設定」を警告にすると、設定漏れが見つかる。
2. **`PlanNode` の属性**：今は未設定も 0 も 0 で持つ。区別が要るなら、`ss_days_set: bool` のような印を builder が付ける（`plan_node.py` は保護対象なので、要るときに依頼書で）。
3. **BS-SEAF の記録**：Mapping の表で「この属性は意図して 0 か」を追えるように、モデルの CSV に明示の 0 を書く運用（決定 d のとおり）を Start Here に書く。

## 3. Part C：残存期間の判定の道具

### 3.1 作り

- **入力**：headless（`tools.run_headless_from_folder.run`）に、POST_PLAN で木を受け取るだけのプラグインを `extra_plugins` で渡し、その木から `wom/valuechain/records.py` の `build_records` で出荷の記録を作る。
- **待ち行列**：`(SKU, 所)` ごとの最小ヒープ（札＝製造週の番号）。所は、supply point（工場の完成品倉庫）・DAD・leaf_out の店頭。
  - MOM → supply point の受け渡し（`handoff_to_sp`）＝製造。その週の番号を札にして supply point の列に入れる。
  - OutBound の出荷（`outbound_move`）：その所の列から一番古い札を取り出し、記録の着いた週（受け手の P に入った週）に受け手の列に入れる。計画期間の後に着く物は「期末の移動中」として数える。
  - 市場の実出荷（`consumer_sale`）：店頭の列から一番古い札を取り出し、**年齢＝納品週 − 札**。
- **週の中の順**：`records` の `NodeInfo.rank`（上流から）の順に、各所で「着いた物を入れる → 出る物を出す」。同じ週の受け渡し（製造の週にそのまま supply point から出る）も正しく並ぶ。
- **参考の列**：Lot_ID で数えた滞留＝max（需要週、納品週）− その Lot_ID の工場の出荷週（前回までの式）。
- **止める条件**：ある所の列が空なのに出荷がある（「`SP ships 2 lot(s) in week W02 but has only 1`」）、着く週が出る週より前、市場への納品の総数が木の市場の実出荷の総数（`_actual_ship` から独立に数える）と合わない。
- **期末注文残**：需要の Lot_ID のうち市場の実出荷が無いものの件数を出す（納品としては数えない）。

### 3.2 テスト（`tests/test_warmup_soft_blank_attrs_fifo.py`、39 件）

| 層 | 中身 |
|---|---|
| A 単体・結合 | 助走行に cap_soft が入る／0 は 0／列が無ければ作らない（見出しも不変）／CSV → materialize → 実ローダ → ノードの `cap_soft` が助走週にも入る |
| B 単体 | `parse_days` の空欄 4 通り・0・正の整数（`14.0`・`"21.0"` を含む）、不正な値 6 通りが止まりメッセージに行・ノード・列が出る。`demand_envelope` の空欄・`Soft`・` soft `・`HARD`、`sfot` が止まる。`YieldRateError` が `TreeAttributeError` の子 |
| B 結合 | Cookie-jp-2026 の `sc_tree_master.csv` を書き換えて実ローダに通す：空欄・0・14・` Soft ` がノードに届く。不正な値（`ss_days`＝-3、`init_stock_days`＝2.5、`demand_envelope`＝sfot）が正しい行番号で止まる |
| C 単体（合成の記録） | (1) 作り置きの無い直列：年齢＝Lot_ID の滞留＝リードタイム 2。(2) 作り置き 2 lot：Lot_ID の滞留は最大 20 週、先入れ先出しの年齢は手計算どおり W5＝4・W6＝5・以後 4（＝リードタイム 2＋在庫の深さ 2）。(3) 1 つの所から 2 チャネル。(4) 持っている数を超える出荷で止まる |
| C 結合 | Cookie-jp-2026 を headless で計画し、納品の総数＝市場の実出荷の総数、年齢はすべて 0 以上。実出荷に 1 件足すと止まる |

### 3.3 化粧品の写しの値（`output/bsseaf_cosmetics/`、リポジトリには入れない）

`python -m tools.shelf_life_check --model-dir output\bsseaf_cosmetics\<写し> --max-age-weeks 52`。B3 は Part A の後に作り直したもの（＝B3s と同じ計画）。

| 写し | 納品 | 先入れ先出しの年齢 最小／最大 | 52 週超 | Lot_ID の滞留の最大 | Lot_ID で 52 週超 |
|---|---|---|---|---|---|
| B2（歩留まり 0.97） | 3,367 | 4／6 | 0 | 6 | 0 |
| B3（歩留まり 0.90） | 3,367 | 4／**21** | **0** | 165 | 195 |
| B3s（参考：warmup を手で書いた写し） | 3,367 | 4／21 | 0 | 165 | 195 |
| B3ss（参考：店頭在庫を `ss_days`＝14 で表した写し） | 3,367 | 4／21 | 0 | 165 | 195 |

B3 の SKU・チャネル別の最大：

| | SG_Store | SG_EC | SG_Distributor | SKU の最大 |
|---|---|---|---|---|
| COS_Serum | 17 | 15 | 15 | **17** |
| COS_Cream | 21 | 19 | 18 | **21** |

- B3 の年齢の分布（Serum）は 4〜17 週に広がり、7〜14 週がそれぞれ 160 前後の納品：作り置き 130 lot が毎週入れ替わるので、定常の年齢はおよそ「リードタイム＋作り置きの深さ（130 lot ÷ 週 13 lot ≒ 10 週）」になる。
- **B3ss**：設計書 v0.4 D15（店頭在庫を X2 から `ss_days`＝14 へ）について、「計画の数字は同じ」を確かめた。B3 と **PSI が完全に一致**した（`ss_days` と `init_stock_days` は OutBound で同じ週数のずれを足すため）。
- 作り直しにより、試行 2 の報告書の B3 の値（Lot_ID の滞留の最大 163 週・工場の P の最大 15・11）は、Part A の後は 165 週・12・9 になる（52 週超の数 195 は同じ）。

**Claude君の近似（Serum 16・Cream 19、52 週超 0）との比較**：

- 近似は「SKU ごとに、製造（工場の出荷）の早い順と納品の早い順を対にする」＝SKU に 1 本の列。これを道具の出力から計算し直すと、**16・19 がそのまま出る**（近似の計算は正しい）。
- 本当の先入れ先出し（所ごとの列）では **17・21** で、1〜2 週大きい。差は**店頭**で出る（最大はどちらも `SG_Store`）。
- 粗かった所：近似は「納品の順＝工場を出る順」としている。実際には、直営店の lot は店頭在庫（2 週）のぶん**ほかのチャネルより 2 週早く工場の倉庫を出る**ので、その時点の古い札を取り、さらに店で 2 週待つ。1 本の列で納品の順に並べると、この店頭の 2 週の列が消え、古い札がほかのチャネルの納品に回る。依頼書の例（「店頭の 2 週の在庫を別の列として持ったこと」）のとおり。
- 結論（52 週超 0）は同じ。

## 4. 前回までの道具との関係

`output/bsseaf_cosmetics/shelf_life_check.py`（Lot_ID の滞留）は写しの中に残した。新しい道具はその式を参考の列（`lot_dwell`）として持ち、値は一致する（B3：最大 165・52 週超 195）。

## 5. テストの結果

| 段 | 結果 |
|---|---|
| 新規 `tests/test_warmup_soft_blank_attrs_fifo.py` | 39 passed（23 秒） |
| `quick_check --smoke`（途中） | 505 passed（114 秒） |
| `quick_check --full`（最後に 1 回） | **954 passed, 3 skipped, failed 0**、1,134 秒（18 分 46 秒）。前回の full 915 件＋新規 39 件 |

golden（15 件＋legacy 3 件）：**すべて緑（不変、再生成なし）**。full のログで golden に出たのは、ev-europe-2026 の「計画期間の外の能力の行 90 件を読み飛ばした」既存の警告だけ。サンプルの CSV（warmup の materialize が書く `data/sample/*/capacity_plan.csv` 等）も、full の後に `git status` で変更が無いことを確かめた。

## 6. 大杉さんに決めてほしいこと（次の段階へ）

1. `supply_role`・`bom_qty` を止める形に揃えるか（§2.4。揃えるなら `supply_role` が先）。
2. 未設定と明示の 0 の記録（§2.5）：lint の警告から始めるか。
3. 化粧品の変更課題①（海上 4 週）に進む：warmup の cap_soft が直ったので、warmup の週の工場の作り方が読める状態になった。
