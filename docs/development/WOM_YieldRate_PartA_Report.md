# 報告書：完成品の出荷時点の歩留まり（yield_rate）— Part A：計画の数量

- 依頼書：`requests/RequestLetter_YieldRate_PartA_to_CodeKun.md`
- 設計：`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.2.md` §3.2・§6 D1・§7
- 実装：Code君（Claude Code、Windows）、2026-10-25
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（branch `wom-v1r5m1_cap_trial`）

---

## 1. SHA と変えたファイル

- **着手時**：`0ef44e4246340fdc6dbcce5d03fe047274ffc3fd`（依頼書と同じ）
- **完了時**：未 commit（HEAD は `0ef44e4` のまま。commit は大杉さんが Windows で行う。下書き `commit_msg115.txt`＝依頼書、`commit_msg116.txt`＝実装）

| 区分 | ファイル | 内容 |
|---|---|---|
| 保護対象コア | `wom/model/plan_node.py` | `yield_rate`（既定 1.0）・`yield_rate_line`、読み出し `shippable_of`／`shippable_limit`／`shippable_planned` |
| 保護対象コア | `wom/engine/backward_planner.py` | `_apply_mom_cap_backward` の充填目標と cap_soft の記録を良品の上限に |
| 保護対象コア | `wom/engine/forward_planner.py` | Step 0a・Step 0b・Kitting Gate の回復を良品の上限に、`run()` 先頭の止める検査 |
| 新規 | `wom/engine/yield_rate.py` | 値の読み取りと止める検査（`YieldRateError`） |
| ローダ | `wom/engine/sc_tree_builder.py` | `yield_rate` 列の読み込み（行番号つき） |
| 能力の利用者 | `wom/engine/holiday_calendar_plugin.py`、`wom/capacity_layer/serial_adapter.py` | 良品の上限に |
| 報告・観測 | `wom/engine/capacity_sealer.py`（負荷の報告）、`wom/engine/strategic_kpi.py`、`wom/lovem/observer.py` | 良品の上限に |
| 計画の入口 | `tools/run_headless_from_folder.py`、`wom/gui/app.py`、`tools/sweep_flags.py` | legacy・Rice Seasonal の止める検査。GUI は `YieldRateError` を Demo tree に落とさず再送出 |
| テスト | `tests/test_yield_rate_part_a.py`（新規）、`tests/conftest.py`（1 行：`core`・`capacity`） | |
| 文書 | `CLAUDE.md`（Master CSV スキーマの近く＋末尾の節）、本書 | |

**改行（2026-10-25 追記）**：`plan_node.py`・`backward_planner.py`・`forward_planner.py`・`sc_tree_builder.py` の作業ツリーが CRLF だった（HEAD は LF）。Claude君の指摘で LF に戻し、`--area core,capacity` 386 passed を再確認した。**見立て**：今回の編集で変わったのではなく、着手前から作業ツリーが CRLF だった可能性が高い。根拠は、編集していない `wom/engine/push_pull.py`・`hammock_layout.py` も同じく作業ツリーが CRLF（HEAD は LF）であること、編集に使った道具がファイルの改行を保つこと、`core.autocrlf=true` の checkout・コピーでこの状態になること。`autocrlf=true` では git add のときに LF に直るので、diff（`--stat`）は前から全行の書き換えにはなっていなかった。CRLF の 2 ファイル（`push_pull.py`・`hammock_layout.py`）は今回の範囲外なので触っていない。

保護対象コアの diff は 3 ファイル合計 約 60 行（うちコメントが半分）。lot を動かすロジックそのもの（overflow・carry-back・繰り延べ・照合）は変えていない。**上限の値を作る 1 行を差し替えただけ**。

## 2. §1 の表の各箇所をどう切り替えたか

| 箇所 | 切り替え | 備考 |
|---|---|---|
| Backward `_apply_mom_cap_backward` | `cap_w = shippable_of(cap_hard(w))`、`cs = shippable_of(cap_soft(w))`。`cap_int`（hard／soft）と cap_soft 超過の記録の両方がこの値を使う | None の判定（未設定の週は飛ばす）は物理の値で先に行うので不変。閉鎖週 0 も不変 |
| Forward Step 0a | `ch = shippable_of(cap_hard(w))` | push を飛ばす条件は不変 |
| Forward Step 0b | `shippable_planned(w)` | |
| Kitting Gate の回復 | `shippable_limit(w)` | |
| HolidayCalendar の再配置 | 空き ＝ `shippable_of(cap_hard(w))` − 置かれている P | **この処理は leaf_in だけが対象**（`node_type != leaf_in` は飛ばす）。`yield_rate` は MOM にしか書けないので、**CSV からはこの箇所に届かない**。切り替えは整合のため（単体テスト 8 は属性を直接付けて確かめた） |
| `serial_adapter` | `state[...]["processing_limit"] = shippable_limit(w)` | キー名は変えていない（上位の層の中では「エンジンが封じる上限」の意味で使われているため） |
| `capacity_sealer` 負荷の報告 | `lim = shippable_limit`、`pc = shippable_planned`（稼働率・超過の判定）。列 `cap_hard`・`cap_soft` は物理の値のまま | |
| `strategic_kpi` 稼働率 | `shippable_limit(w)` | |
| LOVEM `capacity.csv` | `effective_limit`・`planned_capacity` を良品の上限に。`raw_hard`・`raw_soft` は物理 | 列は増やしていない |
| 画面の能力の線、headless の snapshot | **変えない**（物理） | golden を守る。試行で snapshot の能力の値が物理のままであることも確認 |

### 2.1 表に漏れていた箇所

| 箇所 | 扱い | 理由 |
|---|---|---|
| `wom/engine/capacity_sealer.py` 512 行付近（`load_operating_calendar` の cap_soft の導出 `shift × cap_hard ÷ 21`） | **変えない** | 依頼書 §2.4 のとおり物理の能力を作る処理。歩留まりはその後に掛かる |
| `tools/lot_identity_checks.py` 187 行付近（K6：`processing_limit(w) == 0` の週の出荷） | **変えない** | K6 は「閉鎖週・能力ゼロの週に実出荷がある」を見る検査。良品の上限で 0 になる週（例：能力 1 × 0.9）でも、在庫からの出荷は正しいので、良品の上限に替えると誤検知になる |
| `tools/probe_smartx_bottleneck.py`、`tools/smartx_capacity_compare.py`、`tools/generation_line_compare.py` | 変えない | 調査用の道具で物理の能力を出力するだけ |
| **`wom/gui/app.py` の SCTree 読み込み**（5458 行付近） | `except YieldRateError: raise` を足した | 既存の作りは builder の**あらゆる例外を表示して Demo tree で計画を続ける**。そのままだと止める条件が GUI では黙って別の木の計画になる。今回の止める条件だけを再送出し、Planning Engine Error として止める（他の例外の扱いは不変） |
| `tools/sweep_flags.py` | 計画の入口の検査を足した | headless と同じ経路を持つため |

## 3. 新しい読み出しの名前

`shippable_of(value)`・`shippable_limit(w)`・`shippable_planned(w)`（依頼書の案のまま）。

- 大杉さんの定義「当週の**引当て可能な**完成品の出荷数量」をそのまま名前にした。`ship` は Ship_Qty と同じ語で、**物理の能力（capacity／limit）ではなく出せる良品の数**であることが名前から読める。
- `capacity` という語を使わない（物理と取り違えない）。対になる物理の読み出し `processing_limit`／`planned_capacity` と語尾をそろえ（`_limit`／`_planned`）、どちらの良品版かが一目で分かるようにした。
- 戻り値の型は物理の読み出しと同じ（None／float）。y＝1.0 のときは**値をそのまま返す**（`floor(v×1+1e-9)` は v が 4.9999999999 のような値で `int(v)` と 1 違いうるため、y＝1.0 は計算を通さない）。これで「属性なし」と「1.0 明示」が全経路で一致する（単体テスト 6）。

## 4. テストの結果

| 段 | 結果 |
|---|---|
| 新規 `tests/test_yield_rate_part_a.py` | **18 passed**（3.2 秒）。Unit 1〜8、Integration 9・10a〜10f（10a は 4 値をパラメータ化） |
| `quick_check --smoke`（途中） | 505 passed |
| `quick_check --area core,capacity`（途中） | **386 passed**、255 秒 |
| `quick_check --full`（最後に 1 回） | **915 passed, 3 skipped, failed 0**、**913 秒（15 分 8 秒）** |

### 4.1 full

`python -m tools.quick_check --full`（golden を含む pytest は並行させず単独で実行）：915 passed・3 skipped・0 failed・0 error。golden は 18 件（`tests/golden/*.json` 15 件＋`tests/golden/legacy/` 3 件）すべて緑で、`tests/golden/` のファイルは変更していない（再生成なし）。3 件の skip は golden ではなく、条件付きの既存の skip（画面・サンプルの有無に依存するもの）。

依頼書 §3.1 との対応：

| # | テスト | 確かめたこと |
|---|---|---|
| 1 | `test_1_hard_capacity_limits_good_lots_backward_and_forward` | y=0.97・cap_hard=100・需要 120×6 週：Backward の MOM の P・S が各週 97 以下、超過は前の週へ（S = 41,97×7、合計 720 で lot は消えない）。Forward の P も 97 以下・合計 720 |
| 2 | `test_2_soft_envelope...` | soft・cap_soft=80・y=0.9 → 充填の目標 72 |
| 3 | `test_3_cap_soft_flags...` | Backward（hard、目標 90）placed 85 → 記録 13（＝85−72）。Forward も 13。y なしなら 5 |
| 4 | `test_4_zero_unset_and_closed...` | 能力ゼロ・休業・未設定の週：y=0.5 でも PSI が y なしと完全一致、上限は 0／0／None |
| 5 | `test_5_float_rounding...` | 100×0.29 → 29（28 ではない）、Forward の P の最大も 29 |
| 6 | `test_6_explicit_one...` | y=1.0 明示と属性なしで全ノード・全週・全バケットの Lot_ID の並びが一致（hard・soft の両モード） |
| 7 | `test_7_kitting_recovery...` | Kitting Gate：cap 4 × 0.5 → 各週の組立 ≦ 2、繰り延べ記録 1 件、lot は消えない |
| 8 | `test_8_holiday_replacement...` | 再配置は良品の上限 2 まで（物理 4 ではない） |
| 9 | `test_9_column_reaches_plan_node` | CSV → 実ローダ → `PlanNode.yield_rate`（0.9、行 15）。空欄・列なしは 1.0 |
| 10 | `test_10a`〜`10f` | 不正な値（abc／0／−0.1／1.2）、MOM 以外（leaf_in）、legacy（headless）、Rice Seasonal ON（headless）、push の MOM（headless、push_config の行を足した写し）がすべて止まる。メッセージに `sc_tree_master.csv line N`・ノード名・値・直し方 |

golden（`tests/golden/*.json` 15 件・`tests/golden/legacy/` 3 件）：§4.1 の full で**全件不変**を確認。

## 5. 試行（`output/yield_trial/`、リポジトリには入れない）

Cookie-jp-2026 の写し。headless（推奨プラグインの組）＋ Flow Check。

| | 条件 | snapshot |
|---|---|---|
| T0 | そのまま | — |
| T1 | 両 SKU の MOM（`Factory_GP_CN`・`Factory_DP_JP`）に `yield_rate`＝1.0 | **T0 と一致**（差は試行名 `case` だけ） |
| T2 | `Factory_DP_JP` に 0.90、写しの `capacity_plan.csv` の `Factory_DP_JP` を **700 → 600** | — |
| T3（参考に追加） | `Factory_DP_JP` の能力 **540**、yield なし | **T2 と完全に一致**（差は `case` だけ） |

- **能力を下げた理由**：元の 700 では良品の上限 630 に対して週の P の最大が 629 で、歩留まりが効かなかった。600 × 0.90 ＝ 540 で効く。
- **T2 の `Factory_DP_JP` の週の P の最大**：**540**（＝ floor（600 × 0.90））。上限を超える週は 0。
- **T3 を足した理由**：「歩留まり 0.90 × 物理 600」と「物理 540・歩留まりなし」が同じ計画になることは、歩留まりが**良品の上限としてだけ**効いている（ほかに副作用がない）ことの直接の証拠になる。snapshot は psi の全系列 md5・PPC まで一致した。

Flow Check の表 2（市場、Cookie_Local の 3 チャネル合計）：

| | 需要 | 当週出荷 | 早出し | 遅配 | 期末注文残 |
|---|---|---|---|---|---|
| T0 | 63,060 | 63,060 | 0 | 0 | 0 |
| T2 | 63,060 | 63,060 | 0 | 0 | 0 |
| 変化 | 0 | 0 | 0 | 0 | 0 |

（Cookie_Import も全行で変化なし）

- **市場の結果は変わらない**。Backward が上限 540 を超える週の lot を前の週へ前倒しし（carry-back）、作り置きが在庫として吸収した。その在庫は `SP_Cookie_Local` に現れる：I の合計 0 → **401,800** lot 週、I の最大 0 → **6,900** lot。`Factory_DP_JP` の P・S の合計は 63,060 のまま（良品の lot 数は需要と同じ）。
- **数量の保存**：表 1（ノード）は T2 で **15 ノードすべて OK、`conservation_diff` 最大 0**。不良で lot は消えていない。
- PPC の粗利率は 17.96% のまま（Part A は金額を変えない。作り置きの在庫・投入の物量 1／y の原価は Part B）。

## 6. Part B へ渡すこと

1. **投入の物量の解釈**：良品 1 lot の裏に投入 1／y lot がある。`bom_qty` と同じく「lot 数は不変・物量の解釈だけが変わる」層（`sc_tree_to_df.py`・画面の数量・PPC の供給原価）で扱う。leaf_in の調達量（原材料）を 1／y 倍で見るかが論点。
2. **良品 1 lot 当たりの原価**：MOM の加工費・原材料費を 1／y 倍にするか（不良品の原価を良品が負担）。`node_cost_master.csv`／`ppc_node_cost_rule.csv` の単価の意味（投入 1 lot 当たり／良品 1 lot 当たり）を決める必要がある。
3. **画面の良品の上限の線**（設計書 §7.6）：Part A では物理の線のまま。PSI List の「P vs Capacity Limits」に良品の上限の線を足すかは大杉さんの判断。
4. **LOVEM `capacity.csv` に `yield_rate` 列を足す提案**：今は `effective_limit`（良品）と `raw_hard`（物理）の比から y を逆算できるが、floor のため厳密には戻らない。観測の記録としては `yield_rate` の列があるほうが誤読がない（Part A では列を増やしていない）。
5. **作り置きの在庫の見え方**：試行 T2 のとおり、歩留まりで上限が下がると Backward の前倒しで在庫が増える。これは歩留まりの「コスト」の一部で、Part B の在庫評価（CCC・棚卸資産）に現れる。
6. **push の MOM の歩留まり**（Part A では止める）：push の P は入庫で Step 0a で封じないため、効かせるには push の数量の計算（Mode 4 等）側に入れる必要がある。必要になったら別の依頼。
