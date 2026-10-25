# 報告書：BS-SEAF 化粧品の適用実験 — 第4段階（試行）：調査と基準ケースの写し

- 依頼書：`requests/RequestLetter_BSSEAF_Cosmetics_Trial_to_CodeKun.md`（`bbe713f`）
- 設計書：`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.2.md`（以下「設計書」）
- 実施：Code君（Claude Code、Windows）、2026-10-25
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`

---

## 1. SHA とコードを変えていないこと

- **着手時**：`889e0cb`（歩留まり Part A）。作業中に大杉さんが依頼書を `bbe713f`（docs(request)）として commit した。
- **コードは変えていない**：`git status --short -- wom tools tests data/sample` は 0 行（完了時、HEAD `bbe713f`）。作ったものはすべて `output/bsseaf_cosmetics/`（git の対象外）にある。
- テストはコードを変えていないので回していない（依頼書のとおり）。

## 2. Part 0：調べたこと

### Q1：MOM の `_actual_ship` に市場と同じ Lot_ID が入るか

**入る（identity の pull の MOM、試行で確認）。** push の MOM も identity なら入るが、push の数量の作り方によっては市場に無い ID が入る。

- `_actual_ship` の正体は `ForwardPlanner._actual_s[node_id][w]`。`run()` の最後に各ノードへ `node._actual_ship` として写す（`forward_planner.py` 453 行付近）。
- **pull の MOM**（通常の分岐、870 行付近）：`matched = (CO＋S) ∩ (I＋P)` を Lot_ID の同一性で取り、`_actual_s[mom][w] = matched`。S は Backward が市場の需要 lot を逆伝播したリストなので、ID は市場の Lot_ID そのもの。**試行で確認**：B0 の工場の実出荷 3,367 lot はすべて `LotIDGenerator.parse()` で需要週が読め、3,367 lot すべてが市場（leaf_out）の実出荷と 1 対 1 に対応した。
- **push の MOM**（identity の push の分岐、755〜798 行付近）：照合は pull と同じく `(CO＋S)` 対 `(I＋P)` の Lot_ID の照合で、`actual_s` は需要側の ID。P（入庫）が需要の ID で作られる **Mode 4（`push_lead_time_weeks`）なら市場の ID と一致する**。Mode 1〜3 は需要に紐づかない Lot_ID を作る（コードに非推奨の警告がある）ので、その分は市場の ID と一致しない。legacy の push（800 行付近）は `available[:n]` を位置で取るので、ID の一致は保証されない。
- 化粧品の基準ケースは pull の MOM なので、`w_ship` に `_actual_ship` をそのまま使える。

### Q2：工場の出荷週と市場の出荷週を対にする方法

| 方法 | 中身 | 向き・不向き |
|---|---|---|
| ① headless の木から直接 | `node._actual_ship`（MOM・supply point・leaf_out） | 一番素直。余計なマスターが要らず速い（B0 で 4.9 秒）。headless の `extra_plugins` に POST_PLAN で木を受け取るだけのプラグインを渡せば、コードを変えずに木が取れる |
| ② 段階 D の出荷の記録（`wom/valuechain/records.py` の `build_records`） | ①と同じ `_actual_ship` を 1 lot 1 行の記録にしたもの（`ship_id` は LOVEM と同じ形式） | **木だけで作れる**（Value Chain のマスターは要らない）。MOM→supply point を「仮想の受け渡し（物は MOM にとどまる）」として区別して持つので、Q5 の解釈がそのまま記録に入っている |
| ③ LOVEM（`tools.lovem_observe`） | 実出荷を事象としてファイルに書き出す | 監査・独立照合には強いが、ファイルを経由するぶん重い。判定のためだけなら過剰 |

**試行では ①** を使った（`output/bsseaf_cosmetics/run_trial.py` の `Capture` プラグイン → `shelf_life_check.py`）。**リポジトリの道具にするなら ②** を推す：記録の形式が決まっていて（`Shipment` の列）、区間の種類（`handoff_to_sp` 等）を持ち、LOVEM・Value Chain と同じ ID で突き合わせられるため。どちらも同じ `_actual_ship` を読むので、値は変わらない。

### Q3：Cookie-jp-2026 を雛形にするとき

- **追加したファイル**：無し（雛形の 27 ファイルで足りた）。列は 2 つ足した：`sc_tree_master.csv` の `yield_rate`（Part A）、`capacity_plan.csv` の `cap_soft`（Cookie には無く、代わりに使っていない `cap_pieces` 列がある）。
- **削除したファイル**：無し。金額の 11 ファイルは見出しの行だけにした（§3.1）。
- **書き換え**：17 ファイル（一覧は §3.1）。`push_config.csv` だけが雛形のまま（もともと見出しだけ）。
- **Cookie の決めごとが使えるか**：
  - leaf_out の `region` 列：使える。ただし Cookie は `region`（`CVS`）とノード名（`Retail_JP_CVS`）が別の値。化粧品は **`region`＝ノード名**（`SG_Store` 等）にした。`demand_forecast.csv` の `region` は leaf_out の `region` の値と一致させる必要がある（ノード名ではない）。名前をそろえておくと取り違えない。
  - `demand_forecast.csv` の `region`：上のとおり、leaf_out の識別子として使えた（`CLAUDE.md` 2026-08-18 の規則）。
  - MOM の `lt_wks`：Cookie の MOM の行には `lt_wks` 1 が書いてあるが、親が空の MOM では使われない。化粧品では空欄にした（builder は空欄を 1 として読むが、使われないので影響なし）。
  - `vc_config.csv` の `report_start`：Cookie は空欄。依頼書どおり 2027-W01 を入れた。
  - `lane_assignment.csv` の `mom_node_id` は `IN:mom:<工場名>:<SKU>` の形式（Cookie と同じ）。
  - `node_master.csv` は Cookie と同じく、SKU で共用するノードを 1 行で書き、supply point だけ SKU ごとに行を持つ。

### Q5：supply point に作り置きの在庫が現れる理由

**経路**：

1. Backward の `_apply_mom_cap_backward` が、良品の上限を超えた lot を **MOM 自身の** `psi4demand[w−1][S]` に押し戻す（前倒し）。押し戻しは MOM の中だけで、OutBound（supply point 以下）の需要の位置は変えない（docstring にも「子の再伝播はしない」とある）。InBound の `_in_propagate` はこの後に走るので、原料（leaf_in）は前倒しされた週に合わせて届く。
2. `copy_demand_to_supply` で、MOM の供給側の S も前倒しの週になる。
3. Forward：MOM は前倒しの週に `(CO＋S) ∩ (I＋P)` で照合でき、その週に出荷する → **`_actual_ship[MOM][前倒しの週]` に記録される**。MOM の I には残らない。
4. Phase 2 のブリッジ（`forward_planner.py` 412〜424 行付近）が、MOM の実出荷を**同じ週に** supply point の P に入れる。
5. supply point は普通の pull のノードで、その S は OutBound の需要の位置（前倒しされていない週）のまま。P が S より早く来るので、照合で余った lot が supply point の I に残り、S の週に出ていく。

**答え**：作り置きの lot は、**工場を出た扱い（MOM の `_actual_ship` に記録済み）**で、MOM の I にはいない。在庫は supply point の I に現れる。ただし `records.py` の説明どおり、MOM→supply point は仮想の受け渡しで、**物理的には工場の完成品倉庫にある在庫**である。Start Here の「supply point は在庫を持たない」と食い違うのは、この表し方のため（エンジンの誤りではなく、在庫の所在の表示の問題）。

**§3.3 の判定に当てはめると**：

- 起点を **工場の出荷週 `w_ship`** にすると、supply point で待った期間が滞留に**入る**。作り置きは前倒しの週に作られているので、使用期限の起点（製造）から見るとこれが正しい。
- 起点を **supply point の出荷週** にすると、その待ちが**入らず**、滞留を短く数える（残存期間の判定としては甘くなる）。
- → **残存期間の判定は `w_ship`（工場の出荷週）を起点にするのが正しい**（設計書 §3.2 のとおり）。試行の道具は両方を出す（`dwell`、`dwell_from_sp`）。
- 基準ケース B0 では作り置きが起きない（§4.1 V06）ので、二つの数え方は一致した。差が出るのは、能力が効いて前倒しが起きる変更課題⑤（歩留まり 0.90）など。

## 3. 作った写し

### 3.1 B0（基準ケース）のファイル

作り方：`output/bsseaf_cosmetics/gen_models.py`（Cookie-jp-2026 を写して書き換える。B0・B1 を作る）。

| ファイル | 扱い | 行数（Cookie → B0） | 中身 |
|---|---|---|---|
| `sc_tree_master.csv` | 書き換え | 16 → 17 | §2.1 の木 × 2 SKU。`yield_rate` 列を追加（`Factory_JP`＝0.97、ほかは空欄） |
| `demand_forecast.csv` | 書き換え | 727 → 1,039 | 2027-W01〜2029-W52、6 系列 × 156 週＝936 行。**headless の warmup が 2026-W37〜W53 の 0 の行（102 行）を足した**（§3.3） |
| `capacity_plan.csv` | 書き換え | 848 → 347 | `Factory_JP` だけ、`max_supply`・`cap_soft`、312 行。warmup が 34 行を足した |
| `planning_config.csv` | 書き換え | 3 → 5 | `warmup_lt` 17・`lot_flow_mode` identity・`cpu_size` 24・`recommended_plugins`（Cookie と同じ） |
| `vc_config.csv` | 書き換え | 5 → 5 | `report_start` 2027-W01 |
| `vc_entity.csv` | 書き換え | 6 → 5 | 日本本社（JPY）・シンガポール販社（SGD）・外部の供給者（日本）・代理店（`external_channel`、SGD） |
| `vc_node_assignment.csv` | 書き換え | 16 → 17 | `SG_Store`＝own、`SG_EC`＝online、`SG_Distributor`＝external（代理店の法人）。日本のノードは日本本社、`DC_SG`・`SG_Store`・`SG_EC` は販社 |
| `node_master.csv` | 書き換え | 13 → 10 | 一般的な地点（日本の工場・港の倉庫、シンガポールの DC と 3 チャネル） |
| `lane_assignment.csv`・`route_master.csv`・`inventory_master.csv`・`sku_master.csv`・`decouple_optimizer_config.csv` | 書き換え | 同程度 | SKU・チャネルの名前を入れ替え。金額の列は空欄（`sku_master`）、在庫は 0 |
| `holiday_calendar.csv` | 見出しだけ | 3 → 1 | 休業なし |
| `push_config.csv` | 雛形のまま | 1 → 1 | もともと見出しだけ |
| `ppc_*.csv`（8 本）・`vc_price_rule.csv`・`node_cost_master.csv`・`edge_cost_master.csv` | **見出しだけ** | — | 金額は置かない（設計書 A11）。消さずに空にした理由は §4.2 |

### 3.2 B1

B0 と同じで、`Factory_JP` の `yield_rate` を空欄（1.0）にしたもの。

### 3.3 §2 から外れた所

- **warmup の行**：依頼書は「`capacity_plan.csv` に計画の全週（warmup の週を含む）」としていたが、2027-W01〜2029-W52 だけを書き、warmup の週（2026-W37〜W53）は headless の起動時の materialize（`wom/engine/warmup.py`）に作らせた。materialize は最初の需要週より前の行を消して作り直すので、手で書いても同じ結果になる。写しのフォルダの CSV は実行後に warmup の行を含む（上の行数）。
- `sku_master.csv` の `lead_time_wks` 4・`shelf_life_wks` 156（36 か月）は、計画では使われない参考の値として入れた。
- ほかは §2 のとおり。

## 4. Part 2：結果

実行：`python output/bsseaf_cosmetics/run_trial.py`（headless、推奨の組 `HolidayCalendarPlugin, BufferingStockOptimizerPlugin, CapacityOverridePlugin`、Flow Check）。結果は `output/bsseaf_cosmetics/<B0|B1>/_result/`（`checks.json`・`snapshot.json`・`flow_check/`・`shelf_life.csv`・`valuechain/`）。計画期間は 2026-W37 から 173 週。

### 4.1 V01〜V09

| ID | 期待 | 結果 | 判定 |
|---|---|---|---|
| V01 数量の保存 | 全ノード OK | 16 ノードすべて OK、`conservation_diff` 最大 0 | ✓ |
| V02 開店前の直営店の実出荷 | 0 | 2 SKU とも 0。最初の実出荷は 2027-W14 | ✓ |
| V03 開店直前の在庫に出どころの無い lot | 0 | 0。**ただし在庫そのものが 0**（2027-W13 の `WH_JP_Released`・`DC_SG` とも 0 lot。下の §4.4） | ✓（ただし意味が無い。§5.2） |
| V04 残存期間 | 分布を報告 | 全 3,367 lot の滞留が **4 週**（最小＝最大）。52 週を超える lot は 0。§4.3 | — |
| V05 判定済み倉庫の通過 | 全 lot、工場からの区間 1 週 | 市場に出た 3,367 lot すべてが `WH_JP_Released` を通った。工場の出荷 → `WH_JP_Released` への到着は全 lot 1 週 | ✓ |
| V06 工場の週の P の最大 | Serum ≦ 16、Cream ≦ 12 | Serum **13**、Cream **10**（＝ピーク週の需要）。良品の上限（hard 16／12、soft 13／10）を超えた週は 0。`cap_soft_violation` 0、`cap_hard_deferred_lots` 0、Backward の `cap_soft_envelope` 0 | ✓（能力が効かない。§4.4） |
| V07 チャネル別の当週出荷・遅配・期末注文残 | 値を報告 | 下の表 | — |
| V08 法人・チャネルの区分 | 意図どおり | Value Chain が金額の無いまま**最後まで動いた**。区分は意図どおり（下） | ✓ |
| V09 実名 | 無い | `output/bsseaf_cosmetics/` の 128 ファイルを、公開の一覧と大杉さんの手元の一覧（`tests/test_no_real_names.py` の照合の仕組み）で走査して 0 件。名前は §2.1 の規則で付けた（`COS_Serum`・`Factory_JP`・`SG_Distributor` 等の役割名、法人は「日本本社」「シンガポール販社」「代理店（シンガポール）」） | ✓ |

**V07（Flow Check の表 2、報告期間＝2027-W01 以降。計画の全期間と同じ値）**：

| SKU | チャネル | 需要 | 当週出荷 | 早出し | 遅配 | 期末注文残 |
|---|---|---|---|---|---|---|
| COS_Serum | SG_Store | 546 | 546 | 0 | 0 | 0 |
| COS_Serum | SG_EC | 455 | 455 | 0 | 0 | 0 |
| COS_Serum | SG_Distributor | 897 | 897 | 0 | 0 | 0 |
| COS_Cream | SG_Store | 416 | 416 | 0 | 0 | 0 |
| COS_Cream | SG_EC | 299 | 299 | 0 | 0 | 0 |
| COS_Cream | SG_Distributor | 754 | 754 | 0 | 0 | 0 |
| 合計 | | 3,367 | 3,367 | 0 | 0 | 0 |

当週の充足率は全チャネル 100%。

**V08（Value Chain、`python -m tools.valuechain_run --model-dir output\bsseaf_cosmetics\B0`）**：出荷の記録 20,202 件、保存 OK、未実現利益の消去（第 2 回）も OK。金額が無いので「未評価」が 42,120 行、価格の不足が 10 行。その 10 行がそのまま、意図した区分の価格の一覧になっている：

| 区間 | 価格の種類 | 売り手 → 買い手 |
|---|---|---|
| `Materials_JP→Factory_JP` | supplier_cost | 外部の供給者（日本）→ 日本本社 |
| `WH_JP_Released→DC_SG` | intercompany | 日本本社 → シンガポール販社（国境を越える区間） |
| `DC_SG→SG_Distributor` | wholesale | シンガポール販社 → 代理店（外部の法人） |
| `SG_EC` | market_price | 販社 → 消費者（③ 自社ネット） |
| `SG_Store` | market_price | 販社 → 消費者（① 自社） |

（2 SKU で 10 行。）代理店のチャネルでは販社の売上が卸価格（sell-in）になり、直営店・EC は市場価格になる。設計書 COS-R07・D3 のとおり。

### 4.2 PPC と Value Chain の金額（設計書 A11：数字そのものは評価しない）

| 置き方 | PPC | Value Chain |
|---|---|---|
| **見出しだけ（B0・B1 の採用）** | 止まらずに動くが、**見本のデータに黙って切り替わる**。化粧品の製品がどれも PPC の規則に無いので、`ppc_runner.py` の Step 4（「Falling back to sample data」）が、**このモデルに無い `SMARTPHONE` の lot 2,595 件**（`L-JP-2026W37-001` 等、`JP_Channel`）を作って計算する。金額は 0、信頼性の警告 2,595 件。snapshot の `ppc.total_lots`＝2,595 は化粧品の lot 数（3,367）ではない | 動く。金額は「未評価」になる（上）。為替は `data/ppc/ppc_fx_rate.csv` に黙って切り替わる（`vc_fx_log.csv` に「data/ppc (fallback)」と記録）。SGD がそこに無いので未評価 |
| ファイルを消す（試しに `B0_noppc` で確認） | `ppc_market_price.csv` が無いと、規則も `data/ppc/`（見本）に切り替わる。見本の規則 × 見本の販売で、**粗利率 30.4%・売上 3.6 億円の、もっともらしい数字**が出る（化粧品とは無関係） | （確かめていない） |

→ **見出しだけ** にした。消すと、無関係なもっともらしい金額が化粧品の結果に見えてしまうため。ただしどちらでも、**PPC は化粧品の計画を評価していない**。金額の段階（設計書 A11 の次）では、この黙った切り替えを先に止める必要がある（§5.2）。

### 4.3 残存期間の判定（V04）

道具：`output/bsseaf_cosmetics/shelf_life_check.py`（リポジトリに入れていない）。lot ごとに `w_ship`＝工場の実出荷週、`w_due`＝max（需要週、市場の実出荷週）、滞留＝`w_due − w_ship`。週の差は計画の週の番号（`sc_tree.week_labels` の位置）で数え、ISO の週ラベルは引き算していない（計画には 2026-W53 がある）。

| 区分 | lot 数 | 滞留 最小 | 最大 | 分布 | 52 週超 |
|---|---|---|---|---|---|
| 全体 | 3,367 | 4 | 4 | 4 週：3,367 | 0 |
| COS_Serum（SG_Store／SG_EC／SG_Distributor） | 546／455／897 | 4 | 4 | すべて 4 週 | 0 |
| COS_Cream（SG_Store／SG_EC／SG_Distributor） | 416／299／754 | 4 | 4 | すべて 4 週 | 0 |

- 4 週＝判定 1 週＋海上 2 週＋DC→チャネル 1 週（区間のリードタイムの合計）。どこにも在庫が滞留しないので、全 lot がちょうどリードタイムだけで届いている。
- **supply point の出荷週を起点にした数え方**（Q5）も全 lot 4 週で、同じ値（作り置きが無いため）。
- **遅配の lot**：0 件（`max` は効いていない）。**期末注文残の lot**：0 件。道具は、期末注文残の lot（市場の実出荷が無い）は需要週を `w_due` にして「下限」として数え、`backlog` の印を付けて別に数える作りにしてある。

### 4.4 B0 と B1 の違い

**違いは無い。** snapshot の違いはフォルダ名（`case`）だけで、PSI の全系列の md5・PPC・forward・backward まで一致した。

- 理由：工場の良品の上限（Serum：hard 16・soft 13、Cream：hard 12・soft 10）が、どの週でもピーク週の需要（13／10）以上ある。**cap_soft の良品の上限がちょうどピーク週の需要と同じ**（依頼書 §2.4 の意図どおり）なので、歩留まり 0.97 では 1 lot も切り詰められず、記録も出ない。
- 能力 × 1.2 の余裕（A9）と、cap_soft をピーク ÷ 0.97 の切り上げにした値（A9 の計算）のため、**基準ケースでは歩留まりは数字に表れない**。歩留まりの効きを見るのは変更課題⑤（0.97 → 0.90）になる。

### 4.5 直販比率（数量基準、設計書 D3）

報告期間（2027-W01〜）の実出荷 lot 数：

| | SG_Store | SG_EC | SG_Distributor | 直販比率（(Store＋EC) ÷ 3 チャネル） |
|---|---|---|---|---|
| COS_Serum | 546 | 455 | 897 | **52.7%** |
| COS_Cream | 416 | 299 | 754 | **48.7%** |
| 合計 | 962 | 754 | 1,651 | **51.0%** |

直営店は 2027-W14 開店なので、最初の 13 週は代理店と EC だけで売っている。

## 5. Part 3：BS-SEAF の記録

### 5.1 Mapping の実際

| ID | 設計書の表し方 | 実際の表し方 | 設計書どおりか | 使った既存の知識 |
|---|---|---|---|---|
| COS-R01 | `demand_forecast.csv`（`region`＝leaf_out 名） | `region`＝leaf_out の `region` の値。化粧品ではノード名と同じ値にした | ほぼどおり。正確には「leaf_out の `region` 列の値」で、ノード名ではない（Cookie では別の値） | `CLAUDE.md` 2026-08-18（`region` は leaf_out の識別子）。**Cookie の `region`≠ノード名の例を新たに確認** |
| COS-R02 | `planning_config.csv` の `cpu_size` | `cpu_size`＝24 | どおり（Flow Check の数量の列が lot × 24 で出る：3,367 lot＝80,808 個） | Start Here R7 |
| COS-R03 | `leaf_in` → `mom`（1 つの工場） | `Materials_JP` → `Factory_JP` | どおり | 設計書 D2 |
| COS-R04 | 工場→判定済み倉庫の `lt_wks`＝1 | `WH_JP_Released` の `lt_wks`＝1 | どおり。全 lot が通り、区間 1 週（V05） | `lt_wks` は親→自分の区間の属性（`CLAUDE.md` 2026-08-20） |
| COS-R05 | 実行の後の判定の道具 | `shelf_life_check.py`（写しの外の道具、Core 変更なし） | どおり。入力は `_actual_ship`（Q2 ①） | `LotIDGenerator.parse()`、週は位置で数える（OPEC+ の教訓）。**Q5 で「起点は工場の出荷週」が正しいことを確認** |
| COS-R06 | 開店前の需要 0＋`warmup_lt` 17 の先行生産 | 0 の行＋`warmup_lt` 17 | **表し方はどおりだが、結果が設計書の想定と違う**：開店時の在庫は作られない（全ノードの在庫が全期間 0）。§5.2 | 決定記録 D7（期首在庫は計画の中で作る）。**`init_stock_days`（X2）を使っていない**（§5.2） |
| COS-R07 | leaf_out 3 つ＋`channel_type`＋代理店の法人 | own／online／external、`EXT_CH_SG_DIST`（`external_channel`） | どおり（V08、価格の不足の一覧が区分どおり） | Start Here R10、`vc_node_assignment.csv`、Cookie の 3 チャネルの手本 |
| COS-R08 | 需要を正規の leaf_out にだけ置く | どおり | どおり（自明） | — |
| COS-R09 | Flow Check の表 2 | 表 2 の報告期間の列 | どおり（全チャネル 100%） | Start Here §4.4、`vc_config.csv` の `report_start` |
| COS-R10 | 販売開始週（モデルの外） | 開店前の 0 の行（COS-R06 と同じ） | どおり | — |
| COS-R11 | `capacity_plan.csv` の `max_supply`・`cap_soft`（投入の量） | `Factory_JP` に 17／14（Serum）、13／11（Cream） | どおり。ただし**一度も効かない**（V06） | Start Here R4・R5。**Cookie には `cap_soft` 列が無く、新たに足した** |
| COS-R12 | 価格を期間中一定 | 金額は置いていない（A11） | 未着手（次の段階） | — |
| COS-R13 | MOM の `yield_rate` | `Factory_JP` に 0.97 | 表し方はどおり。**基準ケースでは効かない**（B0＝B1、§4.4） | Part A（`889e0cb`）。設計書 §2.4 の `bom_qty` の考え方 |

### 5.2 設計書に無かったこと

1. **開店時の在庫が作られない（COS-R06）**。WOM は需要に錨を下ろした計画（Demand Anchored）で、`ss_days`・`init_stock_days`・能力の制約のどれも効かないと、lot はちょうど需要週に着くように作られ、どのノードにも在庫が残らない。`warmup_lt` 17 は「助走の期間を空けておく」だけで、在庫を作る仕組みではない（工場の最初の生産は 2026-W50＝最初の需要の 4 週前で、17 週のうち 13 週は何もしない）。設計書 §2.4 は決定記録 D7（お米の 2025 年産）を根拠にしたが、お米で在庫ができたのは**収穫の季節性（供給の制約）**があったからで、化粧品の基準ケースにはその制約が無い。
   - 開店時の店頭在庫が業務の要件なら、表し方は `init_stock_days`（X2、OutBound の立ち上げ初期在庫、`CLAUDE.md` v1r2m2）か `ss_days`（X1）を `DC_SG` 等に置く案になる（Data／Parameter、Core 変更なし）。どちらを使うか、そもそも要件にするかは大杉さんの判断（§6）。
   - V03 は「出どころの無い lot が 0」で合格だが、在庫が 0 なので、今の基準ケースでは検査として意味を持たない。
2. **能力も歩留まりも効かない**。A9 の 1.2 倍の余裕と、cap_soft をピーク ÷ y の切り上げにしたことで、良品の上限が常にピーク需要以上になる。基準ケースとしては正しいが、COS-R11・R13 の確かめは変更課題⑤に持ち越しになる。
3. **PPC の黙った見本への切り替え**。製品が PPC の規則に無いと、`ppc_runner.py` が見本の `SMARTPHONE` の販売を作って計算し、snapshot の `ppc` に化粧品と無関係な値が入る。規則のファイルを消すと、見本の規則でもっともらしい粗利率（30.4%）まで出る。Value Chain の為替も `data/ppc/` に黙って切り替わる。**金額を置く段階の前に、この切り替えを止める（ファイル・理由を出して止める）のがよい**。Core（`wom/ppc/`）の変更になるので、今回は変えていない。BS-SEAF の観点では、「新しい業務で、マスターの中身がまだ空」という第4段階の自然な状態で、結果が誤読される落とし穴になる。
4. **Cookie の雛形の決めごとの違い**：Cookie は `cap_soft` 列を持たず、`report_start` が空欄、MOM の行に使われない `lt_wks` 1 を持つ。雛形をそのまま写すと、化粧品の要件（cap_soft・報告期間）が入らない。
5. **Forward の decoupling の既定**：`buffering_stock_flag` をすべて 0 にすると、Forward は全 DAD（`WH_JP_Released`・`DC_SG`）を decoupling 点として扱う（`forward_planner.py` 430〜444 行付近の後方互換）。基準ケースでは在庫が 0 なので影響は見えないが、変更課題で在庫が出たときに、どこが decoupling 点かを意識する必要がある。

設計書の仮定・Mapping で直す必要があるもの：

- 設計書 §2.4「期首在庫は計画の中の先行生産で作る」→ 化粧品の基準ケースでは**作られない**。COS-R06 の「開店時の在庫は計画の中の先行生産で作る」を、(a) 開店時の在庫を要件から外す、または (b) `init_stock_days`／`ss_days` で表す、のどちらかに直す。
- 設計書 §4 の V06「cap_soft についても同様」は、hard の封印と違い、cap_soft は記録だけ（`demand_envelope`＝hard）。良品の cap_soft を超えたかは `cap_soft_violation` の件数で見る、と書き分けるとよい。

Data／Parameter で足りなかったところ：無し（基準ケースはすべて Data・Parameter と Part A の列で表せた）。Core の変更が要りそうなのは §5.2 の 3（PPC の黙った切り替え）だけで、計画の数量には不要。

### 5.3 手間の記録（変更課題①〜⑤の比較の基準）

- **ファイル**：雛形 27 ファイル。書き換え 17、見出しだけ 11（うち休業 1・金額 10＋`vc_price_rule`）、そのまま 1。新しいファイル 0。新しい列 2（`yield_rate`、`cap_soft`）。
- **行**：手で決める中身は、木 16 行、需要 6 系列（開始週・立ち上げ・定常の 3 つの数 × 6）、能力 2 SKU × 2 値、法人 4 行、法人の割当 16 行、ノード 9 行、設定 4 キー。需要 936 行・能力 312 行は生成スクリプトで展開した。
- **道具**：生成 `gen_models.py` 188 行、実行と検査 `run_trial.py` 165 行、残存期間 `shelf_life_check.py` 74 行（すべて `output/bsseaf_cosmetics/`）。
- **迷った所**：
  1. `region` を leaf_out のノード名にするか Cookie と同じ短い名前にするか（ノード名と同じにした）。
  2. 金額のファイルを消すか空にするか（試した結果、空にした。§4.2）。
  3. warmup の行を手で書くか materialize に任せるか（任せた。§3.3）。
  4. 開店時の在庫が 0 なのは誤りかどうか（誤りではなく、設計書の想定の違いと判断した。§5.2 の 1）。
- **実行時間**：B0 の headless＋検査＋残存期間の判定で 4.9 秒（Python の起動を含む）、Value Chain 5.3 秒。

## 6. 第5段階で大杉さんに決めてほしいこと

1. **開店時の在庫（COS-R06）**：基準ケースでは作られない。(a) 要件から外す（直営店も需要週にちょうど着けばよい）、(b) `init_stock_days`（X2）で `DC_SG`（または直営店の上流）に立ち上げの在庫を置く、(c) `ss_days` で安全在庫として置く、のどれにするか。(b)・(c) は Data／Parameter で、Core 変更は要らない。
2. **PPC の黙った見本への切り替え**：金額を置く前に、製品が規則に無いとき・規則のファイルが無いときに止める（ファイルと理由を出す）よう、Core（`wom/ppc/ppc_runner.py`、Value Chain の為替の既定の切り替えも）を直す依頼書を起こすか。
3. **残存期間の判定の道具**：`shelf_life_check.py` をリポジトリの道具（`tools/`）に入れるか。入れるなら、入力は `records.build_records`（Q2 ②）に替え、起点は工場の出荷週（Q5）にする。基準ケースでは全 lot 4 週で、52 週の上限には遠い。
4. **変更課題の順番**：基準ケースでは能力・歩留まり・残存期間のどれも効かないので、効きが見える課題（⑤ 歩留まり 0.90、① 海上 4 週）を先にするか。
5. **supply point の作り置きの在庫の表示**（Start Here §7、Q5）：エンジンの誤りではなく、工場の完成品在庫を supply point に表示している。表示（所在の名前）を直すか、Start Here の「supply point は在庫を持たない」の記述を直すか。
