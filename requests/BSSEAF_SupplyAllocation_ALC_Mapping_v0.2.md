# 供給配分：ALC-Q01〜Q09 の対応表と、三層設計 MD・化粧品設計書 v0.5 への反映

- 版：v0.2（2026-10-26）。v0.1 を置き換える
- 作成：Claude君（設計・Knowledge Curator）。レビュー：GPT君（2026-10-26、`6a57760` の静的レビュー）。判断：大杉さん
- 前提：
  - 意味体系 `docs/semantics/supply_allocation.md` v0.2（WOM-SEM-SUPPLY-ALLOCATION-001。§2・§3 は採用）
  - 三層設計 MD `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md`（WOM-KB-ALLOCATION-001）
  - 化粧品の試行：`docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md`（`b120fdb`）、写し `output/bsseaf_cosmetics/`
- 根拠：`6a577604e5a04ca8fa7237da332a77e985820bfc` の**コード確認**（Claude君）。C3a の数は試行の出力ファイル（`output/bsseaf_cosmetics/C3a/_result/flow_check/flow_check_market.csv`）を読んだもの。新しい実行はしていない
- 記号：**事実**＝コードまたは出力・報告書で確かめた。**提案**＝Claude君の案。**判断**＝大杉さんの判断

## 0. v0.1 からの訂正

| # | v0.1 の記述 | 訂正 | 指摘 |
|---|---|---|---|
| 1 | Q05：実納品は出荷の記録、期末の注文残は**最終週の CO** で数え直す | 最終週の CO は期末の注文残ではない。identity では CO[w] はその週へ繰り越された要求で、当週に出荷してもバケットを書き換えない。最終週に新しく出た未充足は入らない。**要求の Lot_ID と実出荷の Lot_ID を照合する**（既存の Flow Check 表2） | GPT君 |
| 2 | Q05：配分後に供給が足りないと `attach_realized()` が数量の不一致で止まる可能性 | 誤り。比べているのは `plan_eval.lots`（配分の目標）と `leaf_out_S`（**要求**）の合計で、どちらも出荷ではない。供給不足では止まらない。止まるのはハンドオフ・入力の不整合のとき。代わりに `realized.allocation` が要求の比率になっている（実納品の比率ではない） | Claude君（今回のコード確認） |
| 3 | Q02：未配分（③）を記録する所は「U1 を決めてから」 | ③ の**量の記録**は U1 を待たない。待つのは、その後の扱い | GPT君 |
| 4 | J3：変える所は道具 2 ファイル | `run_headless()` は計画の後に PPC を無条件に呼ぶ。数量の受け渡しから結果の保存まで、金額なしで完結させる範囲にする（§4 J3） | GPT君 |
| 5 | K5：一時的なら先行生産、恒常的なら能力を足す | 計画期間の終わりの状態だけでは、一時的か恒常的かを判定できない。継続する需要の水準と有効な能力、累計の条件、在庫の量・保管の期間で判断する（意味体系 §7） | GPT君 |

## 1. ALC-Q01〜Q09 の対応表

| ID | 問い | 事実（根拠） | 既存機能で対応できる範囲 | 化粧品へつなぐのに要る作業 | なお足りない表現 |
|---|---|---|---|---|---|
| Q01 | 実行の経路 | 化粧品の試行は `output/bsseaf_cosmetics/run_trial.py` から `run_headless_from_folder.run(model_dir, …, extra_plugins=[…])` を呼ぶ。`demand_file` は既定、`planning_state` は既定（False）。`flow_check_dir` は渡している（C3a に `_result/flow_check/` がある）。`run_planning_loop` もハンドオフも通っていない | 三層を一巡する経路は `tools/run_planning_loop.py` にある | 配分を試すときは、数量で配分を渡す経路（J3）を使う | — |
| Q02 | 元の需要・配分済みの需要・未配分 | C3a は元の需要のまま計画した（③ は 0）。ハンドオフは元の CSV を残し、`demand_forecast_<allocation_id>.csv` を別に書く。**需要 CSV の `quantity` は lot の数**：`run()` は `assign_demand_lots_from_dict(…, cpu_size=1)` で 1 行の quantity をそのまま lot 数にする（`cpu_size`〔化粧品は 24〕は表示・KPI で個数に直すときだけ使う。`tools/run_headless_from_folder.py` の Request Letter A の注記） | 元の需要を消さずに、配分済みの需要を別のファイルにできる | ①・② を lot で数える。個数で見るときは lot × `cpu_size`（Flow Check 表2 の `*_qty` 列） | ③ を記録する所が無い（ハンドオフは数量を減らすだけ）。③ ＝ ① − ② を SKU × チャネルで記録する。**U1 の判断を待たない** |
| Q03 | 対象期間 | `wom/allocation/grid.py` の `WEEKS = 104`。ハンドオフの目標数量は `min(x × cap_wk × weeks, demand)` で、`run_planning_loop` は `weeks` を渡さない（常に 104） | 期間はハンドオフの引数 `weeks` で変えられる | 化粧品は 156 週（＋warmup 17）。数量で配分を渡すなら、期間は配分の入力に書く（J3） | `run_planning_loop` に期間の引数が無い |
| Q04 | 2 SKU と能力の単位 | ハンドオフは市場 → 地域 → 週で数量を配り、**SKU を区別しない**。地域 × 週の重みは全 SKU の行の合計で作り、**その地域・週の各行に同じ数量を入れる**（`new_q = new_qty_by_region_week[region][week]`）。化粧品は 2 SKU が同じ地域名（`SG_Store`・`SG_EC`・`SG_Distributor`・`TH_Distributor`）を使う | 単一 SKU のモデル、または `uom` で SKU の系統が分かれるモデル | このままでは使えない。鍵を（SKU, 地域）にする | 各行に地域の合計が入り、**数量が二重になる**（実行では未確認）。`total_after > total_before` の検算に当たらない配分では黙って通る |
| Q05 | ④・⑤ の観測 | **Flow Check 表2**（`wom/engine/flow_check.py` `compute_flow_check()`）が leaf_out × SKU ごとに、S の Lot_ID（demand）を `_actual_ship` の最初の出荷週と照合し、on_time・early・late・backlog_end（期間内に一度も出荷されない）を数える。`check = demand − (on_time + early + late + backlog_end)`。`vc_config.csv` の `report_start` があれば要求週で絞った列も出す。C3a の出力：モデル全体で demand 4,056・on_time 3,864・backlog_end 192 lot（タイの代理店 美容液 104・クリーム 88） | ②＝demand、④＝on_time + early + late、⑤＝backlog_end。同じ需要の集合（その leaf の S の Lot_ID）と判定時点（計画期間の終わり）で、② ＝ ④ ＋ ⑤ が `check = 0` として成り立つ | `planning_state` の `realized` に、この数を SKU × チャネルで入れる（J3） | `attach_realized()` の `realized.allocation` は要求 S の比率、`unmet_lots` は毎週の CO の合計（lot × 週）で、どちらも ④・⑤ ではない。**受渡点**：WOM は leaf_out の `_actual_ship` を引渡しとして数える。化粧品の各チャネルで、それが業務のどの引渡しに当たるか（店頭の販売か、代理店への引渡しか）は事例の記録に書く（未確認） |
| Q06 | 利益の基準と金額 | 化粧品は金額を置いていない（`ppc_*.csv` は見出しの行だけ）。PPC は製品が規則に無いと黙って見本に切り替わる（D8、未対応）。歩留まり Part B（良品 1 lot 当たりの原価）は未実装 | 利益の評価（`merit_order`・`grid`・`true_continuous_optimum`）はある。基準は単位当たりの利益の額 | D8 → 価格・原価の設定 → 歩留まり Part B の順に整える | 利益率で比べる基準は無い。資源当たりで比べる考えも無い |
| Q07 | 配置の後も配分が保たれるか | ハンドオフは対象期間の合計を、元の週の形に比例して配り直す。週の中の順、Backward の前倒し、能力での押し戻しは、要求の並びの順で決まる | 対象期間の SKU × チャネルごとの合計は、配分で決められる | 配分の合計が能力の合計以下でも、週ごとのピークで前倒しが起き、期間の終わりの近くでは ⑤ が残りうる。P1 で確かめる | 週の単位の優先（どの週の、どのチャネルを先に満たすか）は持たない |
| Q08 | 製品の年齢・在庫・再計画 | 先入れ先出しの年齢の道具 `tools/shelf_life_check.py`（R18）、店頭在庫 `ss_days`、warmup の cap_soft（R19）は入った | 配分の後の計画にも、そのまま使える | 配分の試行で、変える条件と固定する条件を記録する | — |
| Q09 | 経路ごとの必須の入力 | **ハンドオフ**：配分を明示しても、最初に `derive_cost_blocks()` を呼び、`ga_market_aggregation.csv`・`ppc_node_cost_rule.csv`・`ppc_edge_cost_rule.csv`・`ppc_supplier_cost.csv`・`ppc_tariff_rule.csv`・`ppc_market_price.csv`・`sc_tree_master.csv`・`sku_master.csv`・`ppc_transfer_price_rule.csv` を読む。**`run_planning_loop`**：加えて `ga_scenario_master.csv`（`--scenario` 必須）・`--cap-wk` 必須。配分を明示しても利益の評価（`evaluate_point` 等）を先に回す。`--allocation` は市場ごとの**比率**（× `cap_wk` × 104）。**`run_headless()`**：計画の後に `_run_ppc()` を無条件に呼ぶ（モデルに `ppc_market_price.csv` があればそれを、無ければ `data/ppc` の見本を読む）。**`planning_state`**：`new_state()` は利益の水準と `plan_eval` を前提にする | 金額の入力がそろったモデル（soysauce-jpy-2027-alloc、oil-global-2027）では動く | 化粧品には `ga_*.csv` が無い。**数量だけの配分を今の経路で回すことはできない** | 業務としては、数量を人が指定する配分に金額は要らない（意味体系 §6）。今の実装は、数量の決定・受け渡し・計画・保存が、金額の評価から分かれていない |

### 1.1 Q10（追加）：既存の能力の層（Capacity Layer）

v0.1 では見落としていた既存の機能。Claude君が v0.2 を書く途中、リポジトリのファイルの一覧で見つけた（E4 と同じ型の見落としを、索引を作る側がもう一度しかけた）。

| ID | 問い | 事実（根拠） | 既存機能で対応できる範囲 | 化粧品へつなぐのに要る作業 | なお足りない表現 |
|---|---|---|---|---|---|
| Q10 | 能力の層と配分の関係 | `wom/capacity_layer/`（汎用ソルバー：要求ごとに計画週の選択肢を持ち、資源 × 週の能力の下で、1) 元の要求週までに割り当てられる lot を最大化、2) その中で前倒しの lot × 週を最小化。貪欲法と LP）と、`wom/plugins/capacity_layer.py` の `CapacityLayerPlugin`（POST_BACKWARD、**既定 OFF**、`capacity_layer_config.csv` の `max_advance_weeks` が必須）。**金額を使わない**。市場の要求（Lot_ID・要求週）を変えず、需要 CSV も書き換えず、内部の計画位置だけを渡す。対応する木は直列の inbound（leaf_in 1 つ、分岐なし、bom_qty 1）。報告書 `docs/development/WOM_SmartxBottleneck_Report.md`（§3・§6 の 4：配分 → 能力の層 → Forward の役割分担）、依頼書 `RequestLetter_GenerationLine_UpperLayer` | 意味体系 §7 の「先行生産で対象期間を満たせるか」（前倒しの窓の中での累計の条件）を、数量だけで確かめられる。Backward の押し戻しの順ではなく、要求週の早い順の規則で lot を配置する | 化粧品の木が直列の inbound の条件に合うかを確かめる。合えば、C3a で「先行生産で足りるか」（一時的か恒常的か）を、warmup を延ばす前に確かめる道具になる | **語の衝突**：能力の層の `unallocated` は「前倒しの窓と能力の中で計画週に割り当てられず、市場に注文残として残る lot」で、意味体系の **⑤**（供給の対象のまま届かない）に当たる。**③（未配分：供給の対象にしない）ではない**。どの市場を優先するかは目的に入っていない（報告書 §3.1） |

## 2. 三層設計 MD への反映（v0.2 に反映済み）

| # | 反映 |
|---|---|
| T1 | §6 に ALC-Q09 を足した。`ga_*.csv` を一括して必須にしない |
| T2 | ALC-Q04 に二重計上（コード確認、実行では未確認） |
| T3 | ALC-Q05 を訂正した（§0 の 1・2）。Flow Check 表2 の再利用 |
| T4 | §1 の冒頭に意味体系への案内 |
| T5 | PA-R05・R06 の証拠を ①〜⑤ に合わせた |
| T6 | §7.2 の P1 に前提（Q09、数量で配分を渡す経路） |
| T7 | 版を 0.2 に、ファイル名を v0.2 に。根拠の版 `6a57760` を足した |
| T8 | §2 の表に WOM-ALLOC-07（能力の層）を足し、`unallocated` の語の衝突を書いた（§1.1 の Q10） |

## 3. 化粧品設計書 v0.5 への反映（v0.5 に反映済み）

| # | 反映 |
|---|---|
| K1 | 推奨 3 を書き直した：「Management 層の既存の配分機能で、対象期間の SKU × チャネル別の**供給対象の数量**を決め、Backward で生産・調達を配置し、Forward で実納品と配分後の未充足を確かめる。元の需要との差は**未配分の需要**として量を記録する」。「誰を待たせるか」は取り下げた |
| K2 | C3a の読み方：期末の注文残 192 lot は Flow Check 表2 の backlog_end（ID の照合）で、意味体系の ⑤。③ は 0。タイを後回しにする経営の判断ではない |
| K3 | §2.4 に 2 行：意味体系を正とする、三層の配分経路は既存の機能で、適用の前に ALC-Q01〜Q09 を確かめる |
| K4 | BS-SEAF の記録に E4「知識はあるのに見つけられなかった」 |
| K5 | warmup の記述を意味体系 §7 に合わせた（§0 の 5） |
| K6 | 次の順番（§4 J4） |

## 4. 大杉さんの判断（2026-10-26）

| # | 事項 | 判断 | 補足（GPT君のレビュー） |
|---|---|---|---|
| J1 | 意味体系の定義（§2）と数量の関係（§3） | **採用**。受渡点・需要の集合・判定時点・単位の条件を補って | 意味体系 v0.2 §0 に記録 |
| J2 | 未配分の需要の扱い（U1） | **一般則は保留**。化粧品の試行では「**当該期間は供給の対象にしない予測需要**」という仮定として扱う | 実際に失われた販売と断定しない。③ の量は記録する |
| J3 | 数量だけで配分を渡す経路 | **作る** | 範囲は、SKU の鍵に加えて、金額なしの実行・④⑤ の正しい計測・結果の保存まで。財務の評価は「未評価」と明示する。「入力・記録の不整合」と「供給制約による未充足」を区別する。依頼書：`requests/RequestLetter_QuantityAllocationMode_to_CodeKun.md` |
| J4 | 次の順番 | (1) J3 の依頼書 → (2) 化粧品で P0〜P1（数量で配分を渡し、①〜⑤ を数える）→ (3) D8 と金額 → (4) 利益で選ぶ P2 | J3 で数量の経路が金額から独立していることを確かめてから P0〜P1 へ |

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-10-26 | 初版 |
| v0.2 | 2026-10-26 | GPT君のレビューと Claude君のコード確認で訂正（§0）。Q02・Q05・Q09 を書き直し、Q10（能力の層）を追加、判断 J1〜J4 を記録 |
