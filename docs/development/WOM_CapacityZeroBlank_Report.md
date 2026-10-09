# 能力の「0」と「空欄」の意味を揃える ＋ smartx の能力 408 行の行き先　報告

- 依頼書：`requests/RequestLetter_CapacityZeroBlank_to_CodeKun.md`
- 発見：`docs/development/WOM_SmartxBottleneck_Report.md` §2.1・§2.2（Astra君）
- 実装：Code君（Claude Code, Windows）、2026-10-07
- リポジトリ：`Yasushi-Osugi/wom_development_composite_node`（このフォルダではリモート名 `composite_node`）
- ブランチ：`wom-v1r5m1_cap_trial`（GitHub の default branch）
- **着手時の SHA：`c97d50e`**（GitHub の `wom-v1r5m1_cap_trial` と同じ。進み・遅れなし）
- **保護対象のコアの変更を含む**（AGENTS.md §10）：`wom/model/plan_node.py`・`wom/engine/forward_planner.py`・`wom/engine/backward_planner.py`。本書の範囲（能力の値の意味）に限った。
- **commit・push はしていない。** 大杉さんが diff を確かめる。push するときのリモート名は `composite_node`（`origin` は別のリポジトリ）。
- 付表：`docs/development/capacity_zero_blank/`

本書は「観測結果／コードで確かめたこと／解釈／未確認」を分けて書く。

---

## 0. 受入のまとめ

| # | 受入 | 結果 |
|---|---|---|
| 1 | 全モデルの調べ（0・空欄・読めない行）と、変わるモデルの一覧（golden の再生成の前） | **合**。0 の行（開いている週）があるのは smartx だけ（39 行）。空欄・読めない値は、どのモデルにも無い。計画の木に無いノードの行は smartx の 408 行だけ。golden の再生成の前に「変わるのは smartx だけ」と報告し、了承を得た（§2） |
| 2 | 変わるモデルだけ golden を再生成し、変わった項目と理由を表にする | **合**。`tests/golden/smartx-2027-2029.json` だけを作り直した。ほかの 12 件と legacy の 3 件は 1 バイトも変わらない（§3） |
| 3 | 3 層のテスト | **合**。単体・結合 31 件を新しく加えた（`tests/test_capacity_zero_blank.py`）。「0 ＝ 上限なし」を前提にしていた既存のテスト 8 件を、新しい意味に直した（§5） |
| 4 | smartx の 408 行が読まれる（`node_not_found` 0）、前後の比較 | **合**（§4） |
| 5 | 全テスト緑 | **合**。754 passed／4 skipped、失敗 0（1 回の実行、16 分 45 秒）。Tk の不安定なテストも、この回は失敗しなかった |

---

## 1. 変更したもの

### 1.1 値の意味（決定 c）

| CSV の値 | 意味 | ノードの値（`cap_hard()`／`cap_soft()`） | 前 |
|---|---|---|---|
| 空欄（列が無い、または値が空） | 未設定。上限なし | `None` | （空欄は `NaN` → 読み込みで 0 か読み飛ばし） |
| 0 | **能力ゼロ**。その週は処理できない | `0.0` | **上限なし** |
| 正の数 | その値が上限 | その値 | 同じ |
| 負の数・数値でない値 | **読み込みで止める**（ファイル・行・値） | — | 黙って 0（上限なし）や例外の握りつぶし |

適用した経路：`capacity_plan.csv` の `max_supply`・`cap_soft`、`cap_override.csv`（CapacityOverride プラグイン）の `cap_hard`・`cap_soft`、`holiday_calendar.csv` の `partial_capacity` の `value`。

### 1.2 コード

| 区分 | ファイル | 内容 |
|---|---|---|
| コア | `wom/model/plan_node.py` | 能力の既定値を `[None, None]`（未設定）に。`cap_hard()`／`cap_soft()` は `Optional[float]`。`processing_limit()`／`planned_capacity()` は、休業 0.0・未設定 None・能力ゼロ 0.0・正の数はその値。`clear_capacity()`（未設定に戻す）、`is_zero_capacity()`（開いている週で cap_hard が 0）を追加 |
| コア | `wom/engine/forward_planner.py` | Step 0a：`ch > 0` → `ch is not None`（能力ゼロなら P は全部、翌週へ繰り延べ〔identity〕／封印〔legacy〕）。Step 0b（cap_soft の違反の印）：`pc > 0` → `pc is not None`（3 か所） |
| コア | `wom/engine/backward_planner.py` | MOM の能力の押し戻し：`cap_w <= 0` で飛ばしていたのを `cap_w is None` に（能力ゼロの週は 0 個だけ置き、残りを前の週へ）。soft の平準化と cap_soft の印：`cs > 0` → `cs is not None` |
| 読み込み | `wom/engine/capacity_sealer.py` | `parse_capacity_value()`・`CapacityDataError`。`load_capacity_dataframe()` は、全行の値を先に読み（読めない値で止める）、計画の木に無いノードの行を全部挙げて止め（直し方つき）、計画期間の外の週は警告。旧書式（`node_name` 列なし）は、同じ製品・週に空欄が 1 つでもあれば未設定。操業カレンダーからの cap_soft の導出は「cap_hard が未設定なら導出しない」（0 なら 0 を導出）。`CapacityProfile` の既定値を None に |
| 読み込み | `wom/plugins/capacity_override.py` | 同じ規則（空欄＝その列は上書きしない）。木に無い製品の行で止める。期間外は警告 |
| 読み込み | `wom/engine/holiday_calendar_plugin.py` | `partial_capacity` の `value` を同じ規則で読む（空欄・負・数値でない値で止める。0 は能力ゼロ）。休業前の作り溜めの空き容量の計算を None／0 で区別 |
| プラグイン | `wom/engine/harvest_batch_plugin.py` | 収穫週の判定を `int(cap_hard or 0) > 0` に（未設定・能力ゼロ・1 lot 未満〔rice の 0.1〕は収穫週でない。意味は前と同じ） |
| 呼び出し | `tools/run_headless_from_folder.py`、`wom/gui/app.py` | 能力の読み込みの例外を握りつぶさない（前は `except: pass` で、能力が黙って失われていた）。GUI では Planning Engine のエラーとして表示される。`max_supply` を文字列で読み、値の規則を当てる |
| 表示 | `wom/gui/app.py` | PSI List の CapHard の欄：未設定「—」、能力ゼロ「0」（前は 0 も「—」）。P と能力の図・Debug の能力の線：未設定は線を切り、能力ゼロは 0 に引く。違反の色は「未設定でないこと」で判定 |
| 表示 | `tools/run_headless_from_folder.py`（`planning_state_extras`）、`wom/lovem/observer.py` | 能力の系列は未設定を 0 として出す（前と同じ形）。能力ゼロだけのノードも「能力を持つノード」に数える。LOVEM の `capacity.csv` は、未設定を空欄で書く（前は 0.0） |
| 調査用 | `tools/probe_rice_dal_trial.py` | 収穫週の判定を None に対応 |

### 1.3 データ（決定 a）

`data/sample/smartx-2027-2029/capacity_plan.csv`：`node_name=AssemblyCN` のうち、SmartX の 278 行を `AssemblyCN_g1`、SmartXNext の 130 行を `AssemblyCN_g3` に直した。値は同じ。差分は、この 408 行のノード名だけ（408 行の追加・408 行の削除）。

### 1.4 文書

- `CLAUDE.md`：「Master CSV スキーマ」の下に「能力の値の意味」の節を加えた（空欄と 0 の意味、読めない行・木に無いノードで止まること、期間外は警告、旧書式の空欄、例外を握りつぶさないこと、smartx の行の直し）。過去の節にある「cap_hard=0.0 の曖昧さ」「0 ではなく小さい正の値を入れる」の注意は、この節で解消したと明記した（過去の節そのものは、当時の記録として残した）。
- 本書と付表。

---

## 2. 全モデルの調べ（受入 1、観測結果）

`python -m tools.capacity_csv_survey`：モデルのコピーで headless の計画を 1 回流し、計画の木・計画期間・最終的な休業の状態を使って `capacity_plan.csv` の各行を分けた（付表 `survey_before.json`・`survey_after_smartx.json`、0 の行の一覧 `zero_open_rows_*.csv`）。

| モデル | 行数 | 正の数 | 開いている週の 0 | 休業の週の 0 | 空欄 | 読めない値 | 木に無いノード | 計画期間の外 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cookie-jp-2026 | 847 | 847 | 0 | 0 | 0 | 0 | 0 | 0 |
| apparel-global-2028-2029 | 1,638 | 1,638 | 0 | 0 | 0 | 0 | 0 | 0 |
| apparel-us-2026 | 636 | 636 | 0 | 0 | 0 | 0 | 0 | 0 |
| bom-test-2026 | 36 | 36 | 0 | 0 | 0 | 0 | 0 | 0 |
| ev-europe-2026 | 1,140 | 1,140 | 0 | 0 | 0 | 0 | 0 | 90（警告） |
| ev-thailand-2026 | 726 | 726 | 0 | 0 | 0 | 0 | 0 | 0 |
| ev-thailand-2026_update | 847 | 847 | 0 | 0 | 0 | 0 | 0 | 0 |
| smartphone（旧サンプル） | 104 | — | — | — | — | — | — | —（PPC の為替の欠落で、今回の前から計画が最後まで動かない） |
| smartphone-global-2026-2029（旧書式） | 442 | 442 | 0 | 0 | 0 | 0 | 0 | 0 |
| oil-global-2027 | 1,664 | 1,664 | 0 | 0 | 0 | 0 | 0 | 0 |
| rice-japan-2027-2028 | 936 | 936 | 0 | 0 | 0 | 0 | 0 | 0 |
| rice-japan-2027-2028-dal | 1,038 | 1,038 | 0 | 0 | 0 | 0 | 0 | 0 |
| **smartx-2027-2029（直す前）** | 2,076 | 1,629 | **39** | 0 | 0 | 0 | **408** | 0 |
| **smartx-2027-2029（直した後）** | 2,076 | 2,011 | **65** | 0 | 0 | 0 | **0** | 0 |
| soysauce-eu／jpy／jpy-alloc／us | 各 390 | 各 390 | 0 | 0 | 0 | 0 | 0 | 0 |

- `cap_soft` の列を持つモデルは無い。`cap_override.csv` を持つモデルも無い。`holiday_calendar.csv` の `partial_capacity` の値は、すべて正の数（25〜1,500）。
- rice は、非収穫週の能力を 0.1 で入れている（0 ではない）。今回の変更の影響を受けない。
- **0 の意味の変更で計画が変わりうるモデルは smartx だけ**：SmartXPro_CN・AssemblyCN の 2030-W14〜W52（39 行）。直した後は、SmartX・AssemblyCN_g1 の 26 行（2030-W27 以降）が加わる。

---

## 3. golden（受入 2）

再生成の前の確認（観測結果）：新しいコード・直したデータで golden のテストを流すと、smartx だけが違い、ほかの 12 件と legacy の 3 件は一致した。了承を得てから、smartx だけを作り直した（`tools/run_headless_from_folder`、golden に記録されたプラグイン、`PYTHONHASHSEED=0`）。

| 項目 | 前 → 後 | 理由 |
|---|---|---|
| period・products・config・forward・backward | 変わらない | — |
| ppc | 売上 702,250,439 → **661,330,146**、原価 67,621,679 → 63,587,091、粗利 634,628,760 → 597,743,055、粗利率 90.37% → 90.39%、lot 数 1,716 → 1,613、関税・trust event は同じ | 408 行の読み替え（SmartX の期末注文残 59,057） |
| psi | 34 ノード中 **17** が変わる：SmartX 8・SmartXNext 4・SmartXPro_CN 5 | SmartX・SmartXNext は 408 行の読み替え、SmartXPro_CN は 0 の意味の変更（下） |

原因の切り分け（観測結果。同じデータに、基準 `c97d50e` のコードと今のコードを当てた。付表 `A_`〜`D_*.json`）：

| 条件 | コード | データ | 変わるもの |
|---|---|---|---|
| A | 基準 | 直す前 | （基準） |
| B | 基準 | 直した後（0 は上限なしのまま） | SmartX・SmartXNext の 12 ノード、PPC。**408 行の読み替えの効果** |
| C | 今 | 直した後 | B ＋ SmartXPro_CN の 5 ノード。**0 の意味の変更の効果**。PPC・市場は B と同じ |
| D | 今 | 直す前 | **止まる**（`CapacityDataError`：計画の木に無いノードの行が 408 行） |

0 の意味の変更の効果（B → C）：SmartXPro_CN の AssemblyCN は 2030-W14〜W52 が能力ゼロになり、その期間の生産を前の週へ押し戻す。P・S・CO の合計は変わらず、SP_SmartXPro_CN の在庫が増える（期間の在庫の合計 79,094 → 389,556、最大 3,098 → 5,165）。市場の出荷・注文残・PPC は変わらない。SmartX の 26 行（2030-W27 以降の 0）は、計画に影響しなかった。

---

## 4. smartx の 408 行（受入 4、観測結果）

- 直した後、能力の行はすべて計画の木のノードに入る：`node_not_found` 0（テスト `test_smartx_assembly_rows_are_all_read`）。
- AssemblyCN_g1（SmartX）に 252 週、AssemblyCN_g3（SmartXNext）に 130 週の上限が入る（直す前は、どちらにも 1 週も入っていなかった）。

| 製品 | 指標 | 直す前（A） | 直した後（C） |
|---|---|---:|---:|
| SmartX | 需要 | 149,145 | 149,145 |
| | 当週出荷 | 149,145 | **90,088** |
| | 遅配 | 0 | 0 |
| | **期末注文残** | 0 | **59,057** |
| | 能力による繰り延べ（Forward、identity） | 0 | 0 |
| | Backward の能力の押し戻しで計画期間の前に出た件数 | 0 | **59,057** |
| SmartXNext | 需要 | 293,764 | 293,764 |
| | 当週出荷 | 293,764 | 293,764 |
| | 遅配・期末注文残・能力による繰り延べ | 0・0・0 | 0・0・0 |
| | SP_SmartXNext の在庫の最大 | 0 | **157,849** |
| SmartXPro_CN | 市場 | 全数当週出荷 | 全数当週出荷 |
| SmartXPro_IN | 遅配・能力による繰り延べ | 16,073・19,887 | 16,073・19,887（変わらない） |

**解釈**：

- SmartX：組立の能力（期間の上限の合計 96,856）が需要 149,145 より小さい。Backward が超過分を前の週へ押し戻し、計画期間の初めを越えた 59,057 件が期末注文残になる。Forward の繰り延べは 0（Backward が能力の範囲に収めた計画を渡すため）。
- **SmartXNext：依頼書の見込み（大きな能力不足）とは違い、注文残は出なかった**。AssemblyCN_g3 の能力の行は 2028-W27〜2030-W52 の 130 週だけで、それより前の 148 週は**行が無い＝未設定（上限なし）**。Backward は、能力の超過分を、発売前の上限の無い週へ押し戻す。そのため、発売の何年も前から作り溜める計画になり（SP_SmartXNext の在庫が最大 157,849）、能力の不足は注文残ではなく在庫として現れる。これは今のデータの「行が無い週＝上限なし」によるもので、今回の規則どおりの動きである。ラインの能力を決め直す次の依頼書（`RequestLetter_GenerationLine_UpperLayer_to_CodeKun.md`）で、発売前の週を能力ゼロにするか（0 の行を置く）を決める必要がある。
- SmartXPro_IN は、AssemblyCN の行と関係なく、前と同じ。

---

## 5. テスト（受入 3・5）

### 5.1 3 層

| 層 | テスト | 内容 |
|---|---|---|
| 単体 | `tests/test_capacity_zero_blank.py` | 値の 5 通り（空欄 4 形・0 の 3 形・正の数 3 形 → それぞれ None／0.0／値。負の数・数値でない値 5 形 → ファイル・行・値つきで止まる）。PlanNode が未設定と 0 を区別すること、`clear_capacity`、休業は別の状態であること。**能力ゼロの週に P が入らず、翌週の P の先頭へ繰り延べになる**（identity。ID はそのまま、その週は出荷しない）。legacy では封印。未設定の週は前と同じ（上限なし）。Backward は能力ゼロの週の要求を全部前の週へ押し戻す（CO に記録）。**休業の週の振る舞いは、能力が未設定でも正の数でも同じ**（休業の移動 E2 で、能力の繰り延べではない） |
| 結合 | 同上 | CSV → `load_capacity_dataframe` → ノード：空欄と 0 が別に読まれる（cap_hard・cap_soft とも）。cap_soft の列が無いときは未設定。**ノード名の誤り・木に無い製品で止まり、全行を挙げる（1 行も入れない）**。読めない値で止まる。計画期間の外は警告して続ける。旧書式の合計と空欄。cap_override.csv・partial_capacity も同じ規則。**headless の実行（CSV からの経路全体）でも、ノード名の誤りで止まる**。smartx の能力の行がすべて読まれる |
| E2E golden | `tests/test_golden.py` | 13 件＋legacy の 3 件（smartx だけ作り直し） |

### 5.2 新しい意味に直した既存のテスト（8 件）

どれも「0 ＝ 上限なし」「既定値 0.0」を前提にしていた。テストの目的は変えず、「未設定」を `None`（または値を渡さない）に直した。

| テスト | 直したこと |
|---|---|
| `test_capacity_soft.py::test_loader_absent_cap_soft_column_is_backward_compatible` | cap_soft の列が無いとき、cap_soft は `None`（前は 0.0） |
| `test_capacity_soft_backward.py::test_backward_cap_soft_does_not_move_lots` | 「cap_soft 無効」を cap_soft=0 から未設定に |
| `test_composite_kitting_recovery.py::test_hard_capacity_csv_loader_to_gate` | パラメータを（空欄→2 個、0→0 個、0.1→0 個、1→1 個）に。0 は能力ゼロで、部材は置場で待つ |
| `test_holiday_explicit_closure.py::test_t2_zero_without_closure_is_unset` | 能力を設定しない週は `cap_hard() is None` |
| `test_holiday_explicit_closure.py::test_t14_capacity_view_cells_and_headless_series` | 「cap_soft 未設定」の週を `clear_capacity` で作る。能力ゼロの欄が「0」と出ることを追加 |
| `test_shift_cap_soft.py::test_no_cap_hard_no_derivation` | cap_hard 未設定なら cap_soft も `None` のまま |
| `test_step7_capacity.py::test_cap_soft_violation_no_movement` | 試験用の木の作り方で、未設定を `None` に（「CapHard=0」を「CapHard 未設定」に） |
| `test_warmup_materialize.py::test_old_format_csv_to_warmup_to_real_loader` | 発売前の週は `None` |

同じ理由で、テストの結果は変わらないが意図を合わせるため、`cap_soft=0.0`（未設定のつもり）を外したテストがある：`test_backward_holiday_carryback.py`（3 か所）、`test_shift_cap_soft.py`（2 か所、うち 1 件は据え置きの確認を `None` に）、`test_holiday_explicit_closure.py`（1 か所）。

### 5.3 全テスト

- `python -m pytest tests/ -q -p no:cacheprovider`：**754 passed／4 skipped、失敗 0**（1 回の実行、16 分 45 秒）。golden 13 件＋legacy の 3 件を含む。
- Tk の初期化が不安定なテスト（`test_merit_order_plot.py::test_plot_regime_matrix` など）も、この回は失敗しなかった（再実行はしていない）。
- 全テストの後、`git status` で変わっている golden は `tests/golden/smartx-2027-2029.json` だけ、サンプルの入力は `data/sample/smartx-2027-2029/capacity_plan.csv` だけであることを確かめた。

---

## 6. 副作用・判断を仰ぎたいこと

### 6.1 今回の変更によるもの

| # | どこで | 何が | 期待との差 |
|---|---|---|---|
| S1 | 能力の CSV に問題のあるモデル | 計画の実行が止まる（GUI は Planning Engine のエラーの画面、headless は例外）。メッセージに行と直し方が出る | 決定 c のとおり。前は黙って能力を失っていた |
| S2 | GUI・headless の能力の読み込み | 能力以外の例外（壊れた CSV など）も止まるようになった（前は `except: pass`） | 黙った既定値を作らない、の方針に合わせた |
| S3 | ev-europe-2026 | 計画期間の外の週の行 90 件の警告が、毎回出る | 止めない（依頼書のとおり） |
| S4 | PSI List・能力の図 | 能力ゼロの週は「0」・0 の線で出る（前は「—」・線なし。ただし、前は 0 が上限なしの意味だった） | — |
| S5 | LOVEM の `capacity.csv` | 未設定の週の raw_hard・raw_soft が空欄になる（前は 0.0） | 区別のため |
| S6 | `PlanNode.cap_hard()`／`cap_soft()` を直接使う外部のスクリプト | 未設定で `None` が返る。`> 0` や `int()` で比べていると例外になる（リポジトリの中は直した） | 区別を強いるための変更 |

### 6.2 判断を仰ぎたいこと（次の依頼書へ）

1. **smartx の SmartXNext・SmartX の発売前の週**：能力の行が無いので上限なしになり、Backward が何年も前から作り溜める（§4）。発売前の週に 0 の行を置けば「能力ゼロ」になり、不足は注文残として現れる。ラインの能力を決め直す次の依頼書で扱うのがよいと考える。
2. **休業と能力ゼロの違い**：今回、能力ゼロは「上限が 0」の意味だけを持たせた。休業と違い、Backward の LT オフセットではその週を飛ばさない（その週に要求を置いたうえで、能力の押し戻しで前の週へ移す）。push の入庫は能力で封じない（前と同じ）。モデルを作る人に、どちらを使うかの目安が要るかもしれない（CLAUDE.md に書いた）。

### 6.3 未確認

- GUI の実機での確認（エラーの画面、PSI List の「0」の表示）。§7 に手順を書いた。
- `smartphone-legacy`（旧サンプル。2026-10-09 削除済み）は、今回の前から PPC の為替の欠落で最後まで動かない。

---

## 7. `python -m main` で確かめる手順

| # | 操作 | 期待する表示 |
|---|---|---|
| 1 | smartx-2027-2029 を読み込み、Run Planning Engine | エラーなく終わる。Network → Flow Check の表 2 で SmartX の期末注文残 59,057 |
| 2 | Network → PSI List で `IN:mom:AssemblyCN_g1:SmartX` | CapHard の欄に値が入る（前は全週「—」）。2030-W27 以降は「0」 |
| 3 | 同じく `IN:mom:AssemblyCN:SmartXPro_CN` | 2030-W14 以降の CapHard が「0」 |
| 4 | モデルのコピーの `capacity_plan.csv` で、どれか 1 行のノード名を誤らせて読み込み、Run Planning Engine | 「Planning Engine Error」の画面に「計画の木に無いノードの行が 1 行あります…直し方：…」 |
| 5 | コピーで、どれか 1 行の `max_supply` を `-1` にする | 同じ画面に「… N 行目 の max_supply が読めません：'-1'」 |
| 6 | コピーで、ある週の `max_supply` を空にする | 止まらない。その週は上限なし（PSI List の CapHard が「—」） |

---

## 8. 成果物

| 種類 | 場所 |
|---|---|
| コード | §1.2 の表 |
| データ | `data/sample/smartx-2027-2029/capacity_plan.csv`（408 行のノード名） |
| golden | `tests/golden/smartx-2027-2029.json` |
| テスト | `tests/test_capacity_zero_blank.py`（新規 31 件）、既存 8 ファイルの修正 |
| 測定スクリプト | `tools/capacity_csv_survey.py`（全モデルの調べ）、`tools/smartx_capacity_compare.py`（smartx の前後） |
| 付表 | `docs/development/capacity_zero_blank/`（調べの結果、0 の行の一覧、smartx の A〜D） |
| 文書 | 本書、`CLAUDE.md`（能力の値の意味の節） |

差分の確認：`git diff -- wom/model/plan_node.py wom/engine/forward_planner.py wom/engine/backward_planner.py`（保護対象のコア）、`git diff --stat -- data/sample`（smartx の 408 行だけ）、`git diff -- tests/golden`（smartx だけ）。
