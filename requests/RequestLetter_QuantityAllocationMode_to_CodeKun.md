# Request Letter：数量で配分を渡す経路（数量配分モード）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-26）。レビュー：GPT君（`6a57760` の静的レビュー、2026-10-26）
- 版：v0.2（2026-10-26）。GPT君の `a085a85` のレビュー（計画期間と能力の固定、不整合の検査、記録の互換）を反映
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の根拠 `a085a85`。この依頼書 v0.2 は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：判断 J3・J4（`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §4）。意味体系 `docs/semantics/supply_allocation.md` v0.2（§2・§3 は採用）。三層設計 MD `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md`
- 種別：**コードの変更を含む**。保護対象のコア（`AGENTS.md` §10 の 6 ファイル）は**変えない**。golden（`tests/test_golden.py`：通常 15 件・legacy 3 件）は**変わらないこと**。変わったら止める

---

## 0. 目的と、大杉さんの判断

人が**数量**で配分を決めたとき、価格・原価・為替を一つも置かずに、配分 → Backward → Forward → 結果の記録までを一巡させる。業務として、数量で決める配分に金額は要らない（意味体系 §6）。今の経路は、数量の決定・受け渡し・計画・保存が、金額の評価から分かれていない（対応表 Q09）。

| # | 判断（2026-10-26） |
|---|---|
| J1 | 意味体系の定義と数量の関係を採用。①元の需要 ＝ ②供給対象 ＋ ③未配分、② ＝ ④実納品 ＋ ⑤配分後の未充足。**同じ需要の集合・同じ判定時点・同じ単位（lot）**で数える |
| J2 | 未配分の扱い（U1）は一般則を保留。道具は U1 を決めない。③ の**量**は記録する |
| J3 | 数量配分モードを作る。範囲は SKU の鍵・金額なしの実行・④⑤ の正しい計測・結果の保存まで。財務は「未評価」と明示する |
| J4 | この依頼の後に、化粧品の P0〜P1（別の依頼書）。今回は化粧品での一致の確認（§E の V09）まで |

**比べる条件を固定する**：配分案どうしを比べるとき、変えてよいのは配分（②・③）だけである。**元の需要から決めた対象期間・warmup を含む計画期間・能力と操業カレンダーは、配分案の間で固定する。配分後の需要が 0 でない最初の週によって決め直さない**（§A の F9、§C.3 の 2）。

## A. 先に確かめること（コードを読んで。違えば止めて報告）

Claude君が `6a57760` のコードを読んで確かめた事実。着手の前に読み、違う所があれば、実装の前に止めて報告する。

| # | 事実 | 所 |
|---|---|---|
| F1 | 需要 CSV の `quantity` は lot の数（`assign_demand_lots_from_dict(…, cpu_size=1)`）。`cpu_size` は表示で個数に直すときだけ使う | `tools/run_headless_from_folder.py` の需要 → ロット |
| F2 | `write_demand_for_allocation()` は配分を明示しても `derive_cost_blocks()` を最初に呼ぶ。地域 × 週の重みを全 SKU の行で作り、その地域・週の**各行に同じ数量**を入れる（2 SKU が同じ地域名なら二重になる） | `wom/allocation/handoff.py` |
| F3 | `run()` は計画の後に `_run_ppc()` を無条件に呼ぶ | `tools/run_headless_from_folder.py` |
| F4 | Flow Check 表2 は leaf_out × SKU ごとに、S の Lot_ID を `_actual_ship` の最初の出荷週と照合し、demand・on_time・early・late・backlog_end・check を数える。`run(flow_check_dir=…)` で `flow_check_market.csv` に書く | `wom/engine/flow_check.py` |
| F5 | `attach_realized()` の数量一致の検査は `plan_eval.lots` と `leaf_out_S`（要求）の比較。`realized.allocation` は要求の比率、`realized.unmet_lots` は毎週の CO の合計（lot × 週） | `wom/planning_state/__init__.py` |
| F6 | `planning_state` の ID は `A\d+`、保存先は `output/planning_state/<case>/` | 同上 |
| F7 | 能力の層（`CapacityLayerPlugin`、既定 OFF）は数量だけで、内部の計画週を割り当てる。その `unallocated` は「設定した能力・前倒しの窓の下で、**内部の計画へ配置できなかった**量」で、③（Management が供給の対象に選ばなかった量）でも ⑤（Forward の後、判定時点までに引き渡されていない量）でもない（配置できた lot でも Forward で届かなければ ⑤ になる）。数量配分モードは能力の層を置き換えない | `wom/plugins/capacity_layer.py`、`wom/capacity_layer/` |
| F8 | Lot_ID の連番は (sku_id, region, week) ごとに 1 から振る。配分で週の数量を減らすと、残る Lot_ID は元の Lot_ID の部分集合になる | `wom/model/lot_generator.py` の `LotIDGenerator` |
| F9 | `run()` は渡した需要 CSV で `materialize_warmup()` を呼ぶ。warmup は**その CSV の需要が 0 でない最初の週**（`first_nonzero_demand_week`）を基準に、それより前の行を落とし、最初の実週の行を写して助走の行を作り直す。対象は需要 CSV・`capacity_plan.csv`・操業カレンダーで、**モデルのフォルダのファイルを書き換える**。配分で先頭の週の需要が 0 になると、計画の開始週が動き、能力の行が置き換わる（GPT君が小さな CSV で再現：W01〜W03 の需要が 0 になると開始が動き、W03 の能力 0 が W04 の 10 に置き換わる） | `wom/engine/warmup.py`（`materialize_warmup`・`_rebuild`） |
| F10 | Flow Check 表2 は、需要の ID を当週・前倒し・遅配・未充足のどれかに分類し、その合計から `check` を作る。同じ ID の出荷が複数あっても**最初の出荷だけ**を使う。**`check = 0` は、重複の出荷や物量の保存まで確かめた証拠ではない**。表2 には製品の小計（`Σ（製品）`）とモデルの合計の行もある | `wom/engine/flow_check.py` の表2 |

## B. 入力：配分の数量のファイル

`allocation_qty_<allocation_id>.csv`（置き場所は引数で渡す。モデルのフォルダに置かなくてよい）。

| 列 | 中身 |
|---|---|
| `sku_id` | 需要 CSV の `sku_id` |
| `region` | 需要 CSV の `region`（チャネル。leaf_out） |
| `alloc_lots` | 対象期間に供給の対象にする lot 数（0 以上の整数） |

- **対象期間**は、この版では計画の需要の期間全体（需要 CSV の最初の週から最後の週）とする。報告書・状態の記録に、開始週・終了週・週数を書く。期間の一部だけを配分する機能は作らない（需要の集合 D を Flow Check 表2 とそろえるため）。
- **止める**（エラーで止め、何も書かない）：
  1. `alloc_lots` が、その鍵の ①（元の需要の lot 数の合計）を超える（配分は需要を増やさない）
  2. 需要が 1 lot 以上ある (sku_id, region) が、ファイルに無い（黙って素通しも 0 もしない）
  3. 需要 CSV に無い鍵、同じ鍵の重複、整数でない値・負の値
- 止めるときは、該当する鍵をすべて並べて一度に知らせる。

## C. 実装

### C.1 数量のハンドオフ（`wom/allocation/handoff.py` に関数を足す。既存の関数の動きは C.4 以外変えない）

`write_demand_for_quantity_allocation(model_dir, alloc_path, allocation_id, *, demand_file="demand_forecast.csv", out_path=None) -> dict`

1. **原価・価格・`ga_*` のファイルを一つも読まない**（`derive_cost_blocks` を呼ばない）。読むのは需要 CSV と配分のファイルだけ。
2. 鍵は (sku_id, region)。その鍵の行の週の形に比例して `alloc_lots` を配る。端数は既存の `_largest_remainder()`。需要 0 の週は 0 のまま。
3. `alloc_lots` ＝ ① の鍵は、行を**そのまま**写す。
4. 列・行の順は元のまま。出力は既定で `<model_dir>/demand_forecast_<allocation_id>.csv`。
5. 返り値に、鍵ごとの ①・②・③（③ ＝ ① − ②）と合計を入れる。書いた後に読み直して、鍵ごとの ② が `alloc_lots` と一致することを確かめる（違えば止める）。

### C.2 PPC を呼ばない実行（`tools/run_headless_from_folder.py`）

- `run()` に引数 `ppc: bool = True` を足す。`False` のときは `_run_ppc()` を呼ばず、返り値の `"ppc"` を `{"status": "未評価", "reason": "quantity allocation mode"}` にする。
- `run()` に引数 `warmup_real_start: Optional[str] = None` を足し、`materialize_warmup()` に渡す（`materialize_warmup()` にも同じ名前の引数を足す）。指定したときは、warmup の基準の週を、渡した需要 CSV から求めず、この週に固定する。`None` のときは今までどおり。
- **既定（`ppc=True`・`warmup_real_start=None`）の返り値と、モデルのファイルへの書き込みは 1 バイトも変えない**（golden 通常 15 件・legacy 3 件）。

### C.3 数量配分の一巡と記録（新しい道具 `tools/run_quantity_allocation.py`）

`run_planning_loop.py` には足さない（金額の経路と分けるため）。

```
python -m tools.run_quantity_allocation --model-dir <作業用のモデル> --allocation-file <allocation_qty_X.csv> ^
    [--out-dir output/planning_state] [--unallocated-note "<U1 の仮定>"]
```

1. 配分の ID は `Q\d+`（`A` の連番と別。`planning_state` の連番の規則にそろえる）。
2. **期間と能力を固定する**：
   - 計画の前に、**元の需要 CSV** から warmup の基準の週（`first_nonzero_demand_week`）・計画の開始週・週数を求め、記録する。`capacity_plan.csv`・操業カレンダーのファイルの hash も記録する。
   - C.1 → `run(model_dir, demand_file=<生成した CSV>, ppc=False, warmup_real_start=<元の需要の基準の週>, flow_check_dir=<状態の隣のフォルダ>)`。
   - 計画の後に、`run()` の返り値の `period`（開始週・週数）が元の需要の値と一致し、能力・操業カレンダーのファイルの hash が変わっていないことを確かめる。違えば不整合（4）。
   - 生成した需要 CSV は、元の需要 CSV と同じ (sku_id, region, week) の行を同じ順で持つ（需要 0 の行も落とさない。C.1 の 4）。
3. Flow Check 表2 の行から、鍵ごとに **② 観測 ＝ demand、④ ＝ on_time + early + late（内訳を残す）、⑤ ＝ backlog_end** を取る。
4. **不整合**（下のどれか）なら、正常な結果として確定しない。メッセージは「入力・記録の不整合」とし、鍵と数を並べる：
   - 方式が identity でない（`lot_flow_mode`）。数量配分モードは identity だけを受ける。legacy などは**計画の前に**止める
   - 表2 は**市場・チャネルの明細の行だけ**を使う（`Σ（製品）`・モデル合計の行を足さない）。明細の (product, leaf) の集合が、配分のファイルの (sku_id, region) の集合と一致しない
   - ② 観測 ≠ C.1 の ②（ハンドオフまたは需要 → ロットの不整合）
   - 表2 の `check` ≠ 0
   - 表1（ノードの表）に `status` が NG の行がある（数量の保存・到着の照合）、または `dup_supply_ids` > 0
   - leaf_out の `_actual_ship` で、同じ Lot_ID が 2 回以上出荷されている（表2 は最初の出荷しか見ないので、別に数える）
   - ① ≠ ② ＋ ③
   - 2 の期間・能力の固定が破れた
5. 保存の扱いを分ける：
   - **不整合が無い**：正常な結果 `<out-dir>/<case>/Q<nn>.json` を保存する。**⑤ > 0（配分後の未充足）は止めずに、計画の結果として保存する**（⑤ が正であることと、記録が壊れていることは別）。
   - **不整合がある**：正常な結果の JSON は書かない（Q の番号も使わない）。診断のために `<out-dir>/<case>/diagnostics/<配分のファイル名>_inconsistent.json` に、検査ごとの結果と数を書き、終了コード 1 で終える。同じ配分のファイルで回し直したら上書きする。
6. 状態の JSON（`<out-dir>/<case>/Q01.json` など）に持たせる：
   - `mode: "quantity"`、`allocation_id`、`case`、配分のファイルの写し（鍵ごとの `alloc_lots`）
   - `period`：開始週・終了週・週数。`unit: "lot"`、`cpu_size`（個数に直すときの値）
   - `valuation: "未評価"`（利益・売上・原価のキーは**作らない**。0 を入れない）
   - `quantities`：鍵ごと・SKU ごと・全体の ①〜⑤ と ④ の内訳。キーの名前は `q1_original`・`q2_in_supply_scope`・`q3_not_in_supply_scope`・`q4_delivered`（`on_time`・`early`・`late`）・`q5_backlog_end`。**`unallocated` という語は使わない**（能力の層の `unallocated` は ⑤ の意味で使われている。F7）
   - `observed_at: "leaf_out の _actual_ship（Flow Check 表2）"`、`judged_at`：計画期間の終わりの週
   - `unallocated_treatment`：`--unallocated-note` の文字列。省略時は `"未決（U1）"`。道具は扱いを決めない
   - `state`：`"plan_computed"`（計画を計算した）。`feasible_plan` は使わない（全量を届けた・違反が無い・人が受け入れた、のどれでもないため。意味体系 §8 の 7）
   - `outcome`：⑤ ＝ 0 なら `"配分した量を期間内に全て引渡し"`、⑤ > 0 なら `"配分後の未充足あり"`
   - 根拠：着手時の commit、需要 CSV のファイル名
7. 標準出力に 1 ブロックで：鍵ごとの ①②③④⑤ の表と、「財務：未評価」。

### C.4 既存の比率の経路の二重計上を止める（`write_demand_for_allocation()`）

F2 の二重計上を、**黙って通さず止める**。配分の対象の地域に、2 つ以上の `sku_id` の需要の行があれば `ValueError`（地域と SKU を並べる）。SKU を鍵にした比率の配分は、この依頼では作らない（金額の経路は D8 の後）。既存のテスト・モデルでこの検査に当たるものがあれば、直さずに止めて報告する。

### C.5 誤読を招く名前の置き換え

`realized.unmet_lots` は毎週の CO の合計（lot × 週）で、注文残の lot 数ではない。`backlog_lot_weeks` に置き換える（コード・テスト・GUI の表示の語をすべて。`grep -rn unmet_lots` の結果を報告書に貼る）。

- **新しい記録は新しい名前で書く**。
- **既存の記録（`output/planning_state/` の JSON）は旧い名前のまま読めるようにする**：`load()` で `unmet_lots` だけがあれば `backlog_lot_weeks` として読む。値があるのに 0 や欠落として扱わない。両方あれば新しい名前を使う。既存の JSON のファイルは書き換えない。
- **過去の報告書・依頼書は当時の記録として残す**。必要な所に「`unmet_lots` は `backlog_lot_weeks`（lot × 週）に改名」の訂正の注記を付ける。

`realized.allocation`（要求の比率）と状態の名前 `feasible_plan` も誤読を招くが、cockpit の画面が使っているため、この依頼では**置き換えない**。使われている所を `grep` で数え、報告書に一覧を書く（置き換えるかは大杉さんが次に決める）。

## D. テスト（`tests/test_quantity_allocation.py`、合成の小さなモデル）

モデル：2 SKU が同じ地域名を 2 つ使う。工場 1 つ。`cpu_size` ≠ 1。`ppc_*`・`ga_*` のファイルは**置かない**。

| # | 確かめること |
|---|---|
| T01 | 金額のファイルが無くても、C.3 が最後まで動き、状態を保存する |
| T02 | `_run_ppc` を呼ぶと失敗する差し替え（monkeypatch）でも動く。状態の `valuation` が `"未評価"` で、利益のキーが無い |
| T03 | 鍵ごとに ① ＝ ② ＋ ③、② ＝ ④ ＋ ⑤。2 SKU が同じ地域名でも二重にならない |
| T04 | `alloc_lots` ＝ ① の鍵は、生成した CSV の行が元と同じ |
| T05 | 能力を足りるようにすると ⑤ ＝ 0、`outcome` が全量引渡し |
| T06 | 能力を下げると ⑤ > 0 で、**止まらずに**保存され、`check` は 0 |
| T07 | B の止める条件 1〜3（それぞれ、何も書かれていない） |
| T08 | 不整合（例：生成した CSV の 1 行を書き換えてから計画する）で、保存せずに止まり、「入力・記録の不整合」と出る |
| T09 | C.4：2 SKU が同じ地域にあるモデルで、`write_demand_for_allocation()` が止まる |
| T10 | 期末の注文残を最終週の CO で数えていない：最終週の CO に入っていて当週に出荷された lot が ⑤ に入らず、最終週に要求されて出荷されない lot が ⑤ に入る |
| T11 | 能力の層（`CapacityLayerPlugin`）を ON にしたモデルでも動く。③ は配分のファイルだけから決まり、能力の層の `unallocated` は ③ に入らない。④・⑤ は Forward の後の照合で決まる（能力の層の `unallocated` の数と ⑤ が同じとは仮定しない）。合成のモデルが能力の層の対応する木（直列の inbound）でないときは、このテストを作らず理由を報告書に書く |
| T12 | 先頭の週の需要をすべて未配分にする（例：最初の 3 週の ② を 0）。計画の開始週・週数・能力の行が、配分しない場合と同じ（F9 の再現の逆） |
| T13 | 全量を未配分にする（全ての鍵で ② ＝ 0）。止まらずに計画し、③ ＝ ①、④ ＝ ⑤ ＝ 0 で保存する。期間・能力は同じ |
| T14 | legacy のモデル（`lot_flow_mode` が legacy）で、計画の前に止まる |
| T15 | 不整合のときに `Q<nn>.json` が作られず、`diagnostics/` に診断が書かれる。次の正常な実行の番号が飛ばない |
| T16 | `unmet_lots` だけを持つ既存の JSON を `load()` で読むと、値が `backlog_lot_weeks` として読める（0 や欠落にならない） |

既存：`tests/test_golden.py`・`tests/test_planning_state.py`・`tests/test_flow_check.py`・`tests/test_no_real_names.py` を含む全体が通ること。件数と時間を報告書に書く（実行した後の数を書く。先に書かない）。

## E. 化粧品での確かめ（作業用の写しで。元のモデルは変えない）

`output/bsseaf_cosmetics/C3a` を作業用に写す。配分のファイルは、全ての鍵で `alloc_lots` ＝ ①（配分しない）。

| # | 確かめること |
|---|---|
| V09 | C.3 が金額なしで動き、①〜⑤ が C3a の Flow Check 表2 と一致する：全体 demand 4,056・④ 3,864・⑤ 192（タイの代理店 美容液 104・クリーム 88）、③ ＝ 0 |
| V10 | `valuation` が `"未評価"`、PPC の出力フォルダが作られていない |

P0〜P1（配分を変える試行）は、この依頼では行わない。

## F. 止める理由と申し送り

報告では、**止める理由**（動き・数字・誤読に関わる。先に直す）と**申し送り**（潜在の危険・改善の余地。記録して進む）を分ける。コメントの重複や言い回しのような些細なものは、往復させずに直して報告だけにする。

止める理由に当たるもの：§A の事実が違う、golden が変わる、既定の `run()` がモデルのファイルへ書く内容が変わる、既存のテストが C.4 の検査に当たる、V09 の数が合わない。

## G. 報告書と commit

- 報告書：`docs/development/WOM_QuantityAllocationMode_Report.md`。着手時の SHA、§A の確認の結果、変えたファイル、テストの結果（実行後の数）、V09・V10 の数、C.5 の grep の一覧、止める理由と申し送り。
- 文書：三層設計 MD v0.2 の §3（経路）に数量配分モードの節を足す。`docs/WOM_Start_Here.md` の機能の地図の「生産配分と優先供給（三層）」の行に `tools/run_quantity_allocation.py` を足す。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に書く。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-10-26 | 初版 |
| v0.2 | 2026-10-26 | GPT君のレビュー（`a085a85`）：期間・能力・操業カレンダーの固定（F9、C.2 の `warmup_real_start`、C.3 の 2、T12・T13）、不整合の検査を広げた（F10、identity だけ、明細の行だけ、表1・重複出荷、C.3 の 4）、保存の扱い（正常な結果と診断、T15）、`unmet_lots` の読み込みの互換（C.5、T16）、能力の層の `unallocated` の意味（F7、T11）、golden の件数（通常 15・legacy 3） |
