# Explicit Closure v1r5m0 実装報告

- 依頼書：`requests/RequestLetter_ExplicitClosure_v1r5m0_to_CodeKun.md`
- 実装：Code君（Claude Code, Windows）、2026-09-27
- ブランチ：`wom-v1r5m0`（基準 `4ed2f14`）。**commit・push していません**（§8：大杉さんの `git diff` 確認待ち）
- golden は**再生成していません**（§6.2）
- 付属：`docs/development/explicit_closure_v1r5m0/`（スクリーンショット、前後比較の生出力、計測・移行スクリプト）

---

## 0. 要約

1. 休業は `op_shifts[w]=0`（週の状態）で表すようにした。`supply_closure` は能力値を書き換えない。
2. **変わってはいけないもの（§6.1）はすべて一致。** soysauce 4モデル＋alloc（原需要・P_opt/800）、apparel ×2、oil、rice、iphone_global は PSI・forward・backward・PPC とも完全一致。
3. **変わったのは §6.2 の4モデルだけ**（Cookie・ev-europe・ev-thailand・smartx）。4モデルとも PPC の売上・粗利は1円も変わっていない。
4. テスト：**539 passed / 3 skipped / 5 failed**。失敗5件はすべて上記4モデルの golden 比較（PSI signature drift。forward/backward/ppc は一致）。新規テスト21件は全て緑。GUI Gate 0（`test_gui_panel_invariants.py`）も緑。
5. 副作用（§6.4）は5件。うち要注意は **Cookie の 1,450 lot 未供給**（休業が計画開始の直後にあり、前倒し先が足りない）。

---

## 1. 変更ファイルごとの diff 要約

| ファイル | 変更 |
|---|---|
| `wom/model/plan_node.py`（core） | `processing_limit(w)` / `planned_capacity(w)` を追加（休業=0.0／未設定=None）。`set_capacity` の既定引数を None にし、渡さなかった側を変えない。`psi_summary()` に `is_open` |
| `wom/engine/holiday_calendar_plugin.py` | C2-a：`supply_closure` → `set_operating_shifts(w, 0)` のみ。value が 0／0.1／空以外なら警告。C2-b：`partial_capacity` 新設（`cap_hard=value`、`# TRANSITIONAL (D6)`）。`explicit_closures` と post_backward の対象を `CLOSURE_EFFECTS = {supply_closure, partial_capacity}` に |
| `wom/engine/backward_planner.py`（core） | `_apply_mom_cap_backward` の休業判定を `not node.is_open(w)` に置換（意味は同じ） |
| `wom/engine/push_pull.py`（core） | Mode 4：生産週が休業なら直前の開いている週（無ければ直後）へ**追加**。代入を `extend` に変更。`PushSetupResult.mode4_closure_shifted`、`_nearest_open_week()` |
| `wom/engine/forward_planner.py`（core） | Step 0-closure（非 push：休業週の P を次の開いている週の末尾へ繰り延べ／`closure_p_deferred`・`closure_p_unplaced`）。push の休業週：P 受入・実出荷0・全量 I（`closure_s_planned`）。Step 0b：非 push は `planned_capacity` と P、push は実出荷と比較（出荷計算の後へ移動）。Kitting 予算は `processing_limit` |
| `wom/engine/harvest_batch_plugin.py` | 収穫週の条件に `and node.is_open(w)` |
| `wom/engine/strategic_kpi.py` | 稼働率は `processing_limit`。None と 0 の週を除外 |
| `wom/engine/capacity_sealer.py` | `build_capacity_load_report` を `processing_limit`／`planned_capacity` ベースに。死んだ代入行（`qty_supply(w, 1)`）を削除 |
| `tools/run_headless_from_folder.py` | S3 用 `capacity_series`：`cap_soft` は `planned_capacity`（None→0）、`closed_weeks` を追加 |
| `wom/cockpit/s3_view_model.py`, `s3_run.py` | `closed_weeks` を view に渡し、灰色背景だけ描く |
| `wom/gui/app.py` | 表示ヘルパ `psi_list_capacity_cells()` / `capacity_view_series()` を新設。PSI List：CapHard 生値、CapSoft は `planned_capacity`（未設定「—」／休業「0」）、休業週の行は灰色タグ。「P vs Capacity Limits」：push は処理量、休業週は灰色背景・超過色なし |
| `tests/test_holiday_explicit_closure.py`（新規） | T1〜T17（21件） |
| `docs/design/holiday_calendar_and_capacity_semantics.md` | §13「実装状況（2026-09-27）」を追記 |
| データ | 下表 |

### データ移行（§4.8）

| 対象 | 行数 | 変更 |
|---|---:|---|
| soysauce-eu / jpy / jpy-alloc / us-2027 | 8 | value `0.1` → `0` |
| モデル配下の value≠0,0.1 の supply_closure | 43 | effect → `partial_capacity`（apparel-global 4、apparel-us 4、ev-thailand-2026_update 4、iphone_global 3、oil 7、rice 16、smartx 5） |
| `rice-japan-2027-2028_BK260613_1515` | 16 | 同上。**`.gitignore`（`data/sample/*_BK*/`）の対象なので git diff には出ない** |
| `data/sample/holiday_calendar.csv` | 2 | GW_2027・GW_2028 の DAD_Japan（0.3）を同上 |

value / effect の欄の文字だけを置き換え、他のバイト（改行・BOM・他の行）は保持した（`explicit_closure_v1r5m0/migrate_holiday.py`）。

---

## 2. テスト結果

| | 件数 |
|---|---|
| 変更前（基準） | 523 passed / 3 skipped |
| 変更後 | **539 passed / 3 skipped / 5 failed**（新規 21 件を含む） |

失敗5件（すべて §6.2 の意図した変更。golden 未再生成のため）：

- `test_golden.py::test_golden_matches[Cookie-jp-2026 / ev-europe-2026 / ev-thailand-2026 / smartx-2027-2029]` — PSI signature drift
- `test_planning_state.py::test_golden_unchanged_by_default[Cookie-jp-2026]` — 同じ Cookie golden との比較

新規テスト（`tests/test_holiday_explicit_closure.py`）：

| # | テスト | 層 |
|---|---|---|
| 旧1 | value 0 / 0.1 / 1500 のどれでも `supply_closure` は休業（1500 は警告）、能力値不変 | Unit |
| 旧2 | 休業なしの 0 は未設定（無制約）のまま | Unit |
| 旧3a／T13 | 非 push MOM：休業週の充填目標 0、同じ Lot_ID が前週へ | Unit |
| 旧4 | W05・W06 連続休業 → W04 へ、重複なし | Unit |
| 旧5 | 上流（Tier-1・Raw）が調整後の MOM 週に従う | Unit |
| 旧6／T15 | 非 push：休業週の P は次の開いている週へ繰り延べ、ID 集合不変、ブリッジに休業週由来なし／期間内に開いている週が無ければ `closure_p_unplaced` | Unit |
| 旧7 | ヘッダだけの holiday CSV は完全に no-op | Unit |
| 旧8 | leaf_in 休業の P シフトは1回だけ（Forward で二重に動かない） | Unit |
| T9 | push の休業週：P 受入・実出荷 0・全量 I | Unit |
| T10 | `set_capacity(w, cap_hard=x)` で cap_soft 不変 | Unit |
| T11 | `partial_capacity`：cap_hard=value、cap_soft 保持、explicit_closures と P シフトの対象 | Unit |
| T12 | H1 回帰防止：cap_soft 保持＋soft envelope でも休業週 S=0 | Unit |
| T14 | 表示：休業週 CapHard 生値・CapSoft 0、「—」は未設定だけ、0.3 は「0.3」 | Unit |
| T16 | Mode 4：休業週 → 直前の開いている週、Lot_ID 集合不変／先頭が休業なら直後へ | Unit |
| T17 | 操業カレンダー 18直の W18 に supply_closure → headless・GUI（`WOMApp._build_planning_context`）の両経路で `is_open=False`、cap_hard=800 | Integration（実モデル複写） |

---

## 3. §6.1 の一致確認

13 golden モデル＋ alloc 2条件を、変更前コードと変更後コードでそれぞれモデルフォルダの**複写**に対して実行し、全ノード・全週の P／S／実出荷／I／CO／Demand S・P、cap、is_open を比較した（`explicit_closure_v1r5m0/probe_before_after_diff.txt`）。

| モデル | 結果 |
|---|---|
| soysauce-eu / jpy / us-2027 | PSI・forward・backward・ppc 一致。変わったのは W18 の **cap 値と is_open だけ**（下表） |
| apparel-global、apparel-us、oil-global-2027、rice-japan-2027-2028 | 完全一致（`partial_capacity` 互換） |
| iphone_global | PSI 一致。SiliconWafer_TW 系3ノードの休業週の `is_open` が False になっただけ（活動なし） |
| bom-test-2026 | 完全一致 |

cap／sealed 件数を含むフィールドの変化：forward・backward の値は全モデル変化なし（soysauce 4＋alloc は `cap_hard_sealed=0, cap_soft_violation_count=0, cap_soft_envelope_count=0` のまま）。cap の週次値だけが次のように変わった：

| モデル | Bottling_Noda 2027-W18・2028-W18 |
|---|---|
| soysauce-eu / us | cap_hard 0.1 → 1500、is_open True → False |
| soysauce-jpy | cap_hard 0.1 → 1500、cap_soft 0 → 1286、is_open → False |
| soysauce-jpy-2027-alloc | cap_hard 0.1 → 800、cap_soft 0 → 686、is_open → False |

### soysauce-jpy-2027-alloc（P_opt/800）Bottling_Noda の前後比較

前後で**全く同じ値**（Trial-02 §3 の baseline とも一致）：

| 週 | P | S | 実出荷 | I | CapHard | CapSoft |
|---|---:|---:|---:|---:|---|---|
| 2027-W16 | 686 | 686 | 686 | 0 | 800 | 686 |
| 2027-W17 | 0 | 686 | 0 | 0 | 800 | 686 |
| 2027-W18 | 686 | 0 | 0 | 686 | 0.1 → **800** | 0 → **0**（休業） |
| 2027-W19 | 686 | 686 | 686 | 686 | 800 | 686 |
| 2028-W16 | 686 | 686 | 686 | 686 | 800 | 686 |
| 2028-W17 | 0 | 686 | 686 | 0 | 800 | 686 |
| 2028-W18 | 686 | 0 | 0 | 686 | 0.1 → **800** | 0 → **0**（休業） |
| 2028-W19 | 686 | 686 | 686 | 686 | 800 | 686 |

（CapSoft の「0 → 0」は、変更前は「0＝未設定（表示は —）」、変更後は「休業による 0（表示は 0）」。内部値は `planned_capacity`）

原需要条件でも PSI は一致。粗利 165,007,343.19 円（P_opt）／172,459,615.81 円（原需要）も不変。

---

## 4. §6.2 の差分表（意図した変更）

診断件数：`closure_p_deferred`・`closure_p_unplaced`・`closure_s_planned` は**全モデルで 0**。`mode4_closure_shifted` は smartx のみ 8。
PPC：4モデルとも**売上・粗利とも前後一致**（Cookie 4,259,700,000／686,229,000、ev-europe 366,508,230,000／192,334,774,500、ev-thailand 319,119,580,000／180,288,676,250、smartx 702,250,439／634,628,759.84）。PPC は leaf_out（需要アンカー型）の S から計上されるため、上流の時点変化が金額に出ない。

| モデル | 行 | node | 休業週の処理（前→後） | 移った先（前→後） |
|---|---|---|---|---|
| Cookie-jp-2026 | CNY2026（2026-W05・W06） | Factory_GP_CN / mom / pull | P 750・750 → **0・0** | 2026-W02〜W04 の需要（Backward S）が 788・750・750 → 800・800・800（cap 800 まで）。**入りきらない 1,388 lot は計画開始より前へ（past_due）** → 副作用 SE1 |
| Cookie-jp-2026 | CNY2027（2027-W02・W03） | 同上 | P 788・750 → **0・0** | 2026 後半の各週 P 788 → 800（cap の余り 12/週へ分散） |
| ev-europe-2026 | KASSEL（2026-W32・2027-W32） | Factory_Local_DE / mom / pull | P 500 → **0** | 前週 W31 の P 500 → 1000。部材3種と各 Yard も1週前倒し |
| ev-europe-2026 | HU_SUMMER（2026-W31・W32） | Factory_Import_HU / mom / push | 実出荷 100・100 → **0・0** | W27〜W30 の実出荷 100 → 150（cap 150）。SP_EV_Import の I が一時的に最大 200 |
| ev-europe-2026 | HU_SUMMER（2027-W31・W32） | 同上 | 実出荷 60・50 → **0・0** | 2027-W28〜W30 の実出荷 100 → 110・150・150 |
| ev-thailand-2026 | RAYONG（2026-W32・2027-W32） | Factory_Local_TH / mom / pull | P 500 → **0** | W31 の P 500 → 1000 |
| ev-thailand-2026 | GOLDEN_WEEK（2026-W40・W41） | Factory_Import_CN / mom / push | 実出荷 106・115 → **0・0**（入庫 115・115 は受入、I へ） | 2026-W35〜W37 の実出荷 100 → 121・150・150。ただし W38・W39 で 168 lot の出荷不足 → 副作用 SE2 |
| ev-thailand-2026 | GOLDEN_WEEK（2027-W40・W41） | 同上 | 実出荷 106・115 → **0・0** | 2027-W36〜W39 の実出荷 100 → 150 |
| smartx-2027-2029 | CNY 2026（W08・W09） | WaferFab_TW / leaf_in / push_sub | P 1350・1350 → **0・0** | 2026-W07 の P 1350 → 4050 |
| smartx-2027-2029 | CNY 2027（W06・W07） | 同上 | P 1152・1146 → **0・0** | 2027-W05 へ |
| smartx-2027-2029 | CNY 2028（W05・W06） | 同上 | P 901・901 → **0・0** | 2028-W04 へ |
| smartx-2027-2029 | CNY 2029（W04・W05） | 同上 | P 381・374 → **0・0** | 2029-W03 へ |

smartx の `mode4_closure_shifted`（8件）：2026-W08→W07 1350、W09→W07 1350、2027-W06→W05 1152、W07→W05 1146、2028-W05→W04 901、W06→W04 901、2029-W04→W03 381、W05→W03 374。CNY 2030 は Mode 4 の lot が無い週のため移動なし。WaferFab_TW の Lot_ID 集合は前後で同一。

---

## 5. strategic_kpi（soysauce）

休業週（旧 cap_hard=0.1 で P/0.1＝150% 上限に張り付いていた週）が稼働率から外れた。

| モデル | fixed_cost_coverage（前→後） | avg_cap_utilization（前→後） |
|---|---|---|
| soysauce-eu-2027 | 0.046601 → 0.046238 | 0.376533 → 0.369284 |
| soysauce-jpy-2027 | 0.043779 → 0.043352 | 0.353021 → 0.346283 |
| soysauce-us-2027 | 0.046696 → 0.046333 | 0.377292 → 0.370048 |
| soysauce-jpy-2027-alloc（原需要） | 0.033680 → 0.033377 | 0.489791 → 0.483620 |
| soysauce-jpy-2027-alloc（P_opt/800） | 0.033061 → 0.032758 | 0.480848 → 0.474608 |

（Cookie・ev-europe・ev-thailand・smartx も PSI の変化に伴って production_leveling 等が変化。値は `probe_before_after_diff.txt`）

---

## 6. 副作用の一覧（§6.4）

### SE1 Cookie：休業の前倒し先が足りず 1,450 lot が未供給になる

| 項目 | 内容 |
|---|---|
| どこで | Cookie-jp-2026 / Cookie_Import / Factory_GP_CN、2026-W02〜W06（下流 SP_Cookie_Import・DC_Import_Buffer） |
| 何が | Factory_GP_CN の Demand S 総量 70,262 → 68,874（−1,388＝past_due）。供給 P・実出荷の総量 68,724 → 67,274（−1,450）。SP_Cookie_Import の期末 CO 1,538 → 2,988、DC_Import_Buffer の期末 CO 7,842 → 9,292。leaf_out の S・PPC は不変 |
| なぜ（推定） | E1／C2-a で CNY2026 の休業が効き始めた。休業（2026-W05・W06）は計画開始 2026-W02 の3週後で、前倒し先 W02〜W04 は cap_hard 800 で 3週×800＝2,400 しか入らない。W02〜W06 の需要 3,788 のうち 1,388 が期間前へ押し出され past_due になった（Backward の既存の規則どおり）。残り 62 は立ち上がり期の CO 増（1,538 → 1,600） |
| 実機での見方 | `python -m main` → `data/sample/Cookie-jp-2026` → Run Planning Engine → Network で Factory_GP_CN（Cookie_Import）を選択 → PSI List（Demand）の 2026-W02〜W06：W05・W06 が「—」、W02〜W04 の S が 800。Supply 層の CO 列が 1,600 |
| 期待との差 | 期待「休業週の処理が 0、前の週へ前倒し」は満たす。ただし前倒し量が足りず、全量は前倒しできない。この1,388 lot は PPC に現れない（Trial-02 §7 の 9,293 lot と同じ種類の問題） |

### SE2 ev-thailand：push ノードで休業直前の出荷不足と在庫の積み上がり

| 項目 | 内容 |
|---|---|
| どこで | ev-thailand-2026 / EVmaker_Import / Factory_Import_CN（push）、2026-W33〜2027-W44（下流 SP_EV_Import） |
| 何が | 2026-W38・W39 の実出荷 100・100 → 132・0（S 150・150 に対し 168 lot 不足）。2026-W40・W41 は入庫 115・115 を受け入れて I 115 → 230。以後 I が 230 前後で残り、2027 年の休業前は最大 300。I 合計 3,119 → 12,950 lot-週。**総出荷 9,370・総不足 400 は前後で同じ**（時点がずれただけ）。SP_EV_Import の I 合計は 15,621 → 7,230 に減少 |
| なぜ（推定） | E4（push は休業週の入庫を受け入れる）と、Backward の前倒し（W40・W41 の需要を W35〜W39 へ）、Mode 4 の入庫時点の組合せ。Mode 4（push LT 4、実経路 LT 2）の入庫は需要の2週前に来るため、休業週 W40・W41 には「W42・W43 の需要分」が入庫して滞留する。一方、前倒しされた W38・W39 の需要分の入庫は既に W36・W37 に来て、その週の出荷に使われている。push ノードは lot の同一性ではなく到着順で出荷するため、ずれが解消されずに残る（推定。未検証） |
| 実機での見方 | ev-thailand-2026 → Network → Factory_Import_CN（EVmaker_Import）→ PSI List（Supply）の 2026-W36〜W44：W38 の I 150→0 付近、W39 の I=0、W40・W41 の P 115／S —／I 115・230 |
| 期待との差 | 期待「休業週の実出荷 0」は満たす。表に無い変化として、休業前2週の出荷不足 168 lot と、休業後の在庫積み上がり |

### SE3 ev-europe：push ノードの休業週に入庫そのものが無い

| 項目 | 内容 |
|---|---|
| どこで | ev-europe-2026 / EVmaker_Import / Factory_Import_HU（push）、2026-W31・W32、2027-W31・W32 |
| 何が | 休業週の P（入庫）も 100 → 0。前の週 W27〜W30 の入庫と出荷が 150 に増え、SP_EV_Import の I が最大 200（合計 +830 lot-週） |
| なぜ（推定） | Backward が休業週の需要を前へ移し、Mode 4 は Backward の需要週から入庫を作るため、入庫も一緒に前へ移った |
| 実機での見方 | ev-europe-2026 → Network → Factory_Import_HU → PSI List（Supply）2026-W27〜W32 |
| 期待との差 | 期待表の「入庫は受け入れる」という条件は、受け入れるべき入庫が休業週に来ないため観測されない。実出荷 0 は満たす |

### SE4 pull MOM の前倒し分が supply_point に1週在庫として残る

| 項目 | 内容 |
|---|---|
| どこで | ev-europe・ev-thailand の SP_EV_Local（2026-W31・2027-W31、I 0 → 500）、ev-europe の SP_EV_Import |
| 何が | 前倒しで作った 500 lot が supply_point で1週待つ |
| なぜ（推定） | 前倒しの自然な結果（MOM で早く作り、需要週まで待つ） |
| 実機での見方 | Network → SP_EV_Local → PSI List（Supply）2026-W31 |
| 期待との差 | 期待どおりと考えるが、表に明記が無いので報告 |

### SE5 smartx：Buffer_Chip_TW に 3週分がまとめて入庫

| 項目 | 内容 |
|---|---|
| どこで | smartx-2027-2029 / SmartXPro_CN / Buffer_Chip_TW（push）、2026-W08〜W10 ほか各年 |
| 何が | 2026-W08 の入庫 1350 → 4050（CapHard 1350 の3倍）、W09・W10 は 0。I 合計 +11,326 lot-週 |
| なぜ（推定） | E3 で WaferFab_TW の休業2週分を直前の1週（W07）へ集めたため。push ノードは入庫を封印しないので、そのまま受け入れる。能力の表示は処理量で比較するため、超過色にはならない |
| 実機での見方 | smartx-2027-2029 → Network → Buffer_Chip_TW → PSI List（Supply）2026-W07〜W11 |
| 期待との差 | 期待「休業週の P が 0」は満たす。WaferFab_TW の cap_hard 20000 は超えないが、集中の度合いは次の段階で平準化するか判断が要る |

### 診断件数について

E2（`closure_p_deferred`）は、サンプル12モデルでは**一度も発火しなかった**。休業は Backward（MOM）と Mode 4（leaf）の段階ですべて解決され、Forward の休業週に P が届くことが無かったため。E2 の動作はユニットテスト（T15）でのみ確認している。

---

## 7. 依頼書と変えた実装・補ったところ

1. **PSI List の CapHard 表示**：生値を出すため、整数以外は小数のまま表示した（旧 `{:.0f}` は 0.1 を「0」、rice の 0.3 を「0」と表示していた）。
2. **PSI List の行色**：休業週は灰色の「closed」タグにし、超過判定は能力チャートと同じ系列（push は処理量）で行う。依頼書は列の値だけを指定していたが、休業週の push（P=686）が CapSoft 0 超過として橙色になるのを避けるため。
3. **Mode 4 で期間内に開いている週が1つも無い場合**：lot は元の週に残し、診断の移動先を空文字で記録する（依頼書に規定が無かった）。
4. **push の休業週で S 計画が 0 でない場合**：`closure_s_planned` を記録し、`_push_shortfall[w]` に計画量を入れて処理量表示を 0 にした。物の不足ではないので `record_shortfall`（CO 件数）には数えない。
5. **`build_capacity_load_report`**：`cap_hard`／`cap_soft` フィールドは生値のまま、負荷率と超過フラグを `processing_limit`／`planned_capacity` で計算。休業週（limit 0）も行として残す。
6. **旧 Test 4 のアサーション**：前倒し先 W04 に超過が無い場合、`_apply_mom_cap_backward` は P を書き換えない（現行の仕様）。前倒し先の確認は Demand S で行った。
7. **T17（GUI）**：tkinter のウィンドウは開かず、`WOMApp._build_planning_context` をスタブの self で呼び、`_planning_thread` と同じ順で HOOK_PRE_PLAN を発火して確認した。GUI・headless の読み込み順序（`load_operating_calendar` → `on_pre_plan`）は、コードでも両経路とも依頼書どおりであることを確認した（`app.py` の `_build_planning_context` → `_planning_thread`／DebugPanel、headless の l.181–205）。
8. **S3**：`closed_weeks` は `capacity_series` の各ノードに入れ、view の node にも渡した。描画は灰色背景のみ。
9. **value=0.1 の supply_closure**：警告を出さずに休業として扱う（移行後のサンプルには残っていない）。

---

## 8. 画面確認（§6.3-8）

`explicit_closure_v1r5m0/` に、実際の `PSIListPanel`（`wom/gui/app.py`）を Tk で描画してキャプチャしたものを置いた（soysauce-jpy-2027-alloc、原需要、headless と同じ順序で計画）。

- `psilist_bottling_2027.png`／`psilist_bottling_2028.png`：W16〜W19 の行。**W18 は CapHard 800・CapSoft 0**、行は灰色（休業）。
- `capacity_chart_bottling.png`：「P vs Capacity Limits」。push なので処理量の棒。休業週（2027-W18、2028-W18、操業カレンダーのお盆 2028-W33）が灰色の帯。

PSI List の表示値（Supply 層）：

| 週 | S | CO | I | P | CapHard | CapSoft |
|---|---|---|---|---|---|---|
| 2027-W16 | 686 | — | — | 686 | 800 | 686 |
| 2027-W17 | 686 | — | — | — | 800 | 686 |
| 2027-W18 | — | — | 686 | 686 | 800 | 0 |
| 2027-W19 | 686 | — | 686 | 686 | 800 | 686 |

`python -m main` での最終確認は大杉さんにお願いします。

---

## 9. 再現方法

```powershell
# 前後比較（モデルは一時フォルダへ複写して実行。原本は触らない）
python docs\development\explicit_closure_v1r5m0\probe_closure.py . <出力dir>
python docs\development\explicit_closure_v1r5m0\compare.py <変更前dir> <変更後dir>
```

変更前の計測は、コード変更前の作業ツリーで同じスクリプトを実行したもの。
