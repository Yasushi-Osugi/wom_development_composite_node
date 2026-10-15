# WOM QuickCheckTests Report — テストの段（smoke・領域別・全テスト）

- 依頼書：`requests/RequestLetter_QuickCheckTests_to_CodeKun.md`（2026-10-15）
- 着手時の SHA：`8f50c281f3198a0d466e1418757a15ccc3bc4c96`（branch `wom-v1r5m1_cap_trial`）
- 変えたもの：`tests/conftest.py`・`pytest.ini`・`tests/test_test_areas.py`・`tools/quick_check.py`（いずれも新規）、`tests/README.md`（新規）、`CLAUDE.md`（テスト実行の節）。**既存のテストのファイル・golden・保護対象のコア・`wom/` は変えていない。** 新しい依存は無い（pytest の marker・`-m`・conftest だけ）。
- 全テストの実行は 2 回（最初の測定と最後の確認）。途中は smoke・rice・core・golden 1 件で確かめた。

## 結論

| 段 | 件数 | 実測（Windows） |
|---|---:|---:|
| smoke | 497 | **57 秒**（3 分以内） |
| 領域 rice | 70 | 66 秒 |
| 領域 core | 289 | 132 秒 |
| golden 1 件（rice） | 1 | 18 秒 |
| full | 892（889 passed・3 skipped） | 17 分 49 秒（最初の測定は 15 分 24 秒。いずれも pytest の表示） |

全テストの 916 秒のうち、**20 秒以上の 7 件で 494 秒（54%）**。LOVEM の観測 3 件・Value Chain の alloc 2 件・世代ラインの 1 件・Rice の K-R10 が、ほぼ全部を占める。

## Q-1 時間の表

測定：`set PYTHONDONTWRITEBYTECODE=1` ＋ `python -m pytest tests/ -q -p no:cacheprovider --durations=0 --junitxml=...`（単独で 1 回）。**885 passed・3 skipped、924 秒（15 分 24 秒）**。テストごとの時間の合計 916.6 秒（残りは収集など）。生の記録は `output/test_timing/`（git の対象外：`full_before.log`・`junit_before.xml`・`timing.json`・`by_file.md`）。時間は setup・call・teardown の合計なので、module の fixture の時間はその fixture を最初に使うテストに乗る。

### 重いテストの上位 10 件

| # | 秒 | テスト | 何に時間を使っているか |
|---:|---:|---|---|
| 1 | 89.6 | `test_lovem_observer.py::test_intervals_restore_every_digest` | `wom.lovem.verify.verify_run` で、観測した全区間から週ごとの digest を戻して照合する（照合そのもの） |
| 2 | 88.3 | `test_lovem_observer.py::test_se2_168_is_reproduced` | module の fixture `se2_run`：ev-thailand-2026 の写しを warm-up なしで観測つきで計画する |
| 3 | 86.6 | `test_lovem_observer.py::test_q12_observation_does_not_change_the_plan` | module の fixture `q12`：同じモデルを観測あり・なしで 2 回計画し、PSI と PPC の出力を比べる |
| 4 | 67.2 | `test_generation_line_upper_layer.py::test_plugin_on_keeps_market_ids_and_ships_nothing_early` | smartx-2027-2029 を、容量の層のプラグインの off と on で 2 回計画する |
| 5 | 61.9 | `test_valuechain_integration.py::test_alloc_sample_prices_leave_nothing_unvalued` | soysauce-jpy-2027-alloc で Value Chain を最初から 1 回回す（計画＋台帳） |
| 6 | 57.5 | `test_valuechain_integration.py::test_alloc_ledger_records_match_the_plan` | module の fixture `alloc_run`：**5 と同じモデルの Value Chain をもう 1 回**回す |
| 7 | 42.6 | `test_rice_seasonal_layer.py::test_k_r10_migration_copy_regression` | Rice の写しを上位の層つきで計画し、実出荷から数え直す（`tools.rice_seasonal_check.plan`） |
| 8 | 18.9 | `test_no_real_names.py::test_public_list_has_no_hits` | リポジトリの追跡しているテキストをすべて読んで、公開の一覧の語を探す |
| 9 | 18.8 | `test_golden.py::test_golden_matches[smartx-2027-2029]` | 一番大きいモデルの headless 実行＋PPC |
| 10 | 14.5 | `test_golden.py::test_golden_matches[smartphone-global-2026-2029]` | 同上 |

（11 位以下：`test_allocation_grid.py::test_scan_surface_guard_raises` 13.0 秒〔230,230 点の格子を実際に評価〕、`test_worldmap_actual_flows.py::test_no_tkintermapview_and_no_network` 12.4 秒〔子プロセスで GUI を起動〕、golden rice 11.2 秒）

### ファイルごと（合計の多い順。0.0 秒は 0.05 秒未満）

| ファイル | 件数 | 合計 秒 | 最も重いテスト | 秒 |
|---|---:|---:|---|---:|
| `test_lovem_observer.py` | 6 | 273.3 | `test_intervals_restore_every_digest` | 89.6 |
| `test_valuechain_integration.py` | 11 | 124.4 | `test_alloc_sample_prices_leave_nothing_unvalued` | 61.9 |
| `test_golden.py` | 18 | 109.4 | `test_golden_matches[smartx-2027-2029]` | 18.8 |
| `test_generation_line_upper_layer.py` | 12 | 67.8 | `test_plugin_on_keeps_market_ids_and_ships_nothing_early` | 67.2 |
| `test_rice_seasonal_layer.py` | 25 | 54.2 | `test_k_r10_migration_copy_regression` | 42.6 |
| `test_push_pull_mode4_double_count.py` | 10 | 50.7 | `test_mode4_only_flag_still_skips_p_schedule` | 5.4 |
| `test_gui_panel_invariants.py` | 72 | 42.6 | `test_s3_fits_within_default_window[s3_before_run]` | 4.9 |
| `test_worldmap_actual_flows.py` | 12 | 26.2 | `test_no_tkintermapview_and_no_network` | 12.4 |
| `test_planning_state.py` | 14 | 19.1 | `test_plan_eval_uses_chosen_allocation` | 5.1 |
| `test_no_real_names.py` | 20 | 19.0 | `test_public_list_has_no_hits` | 18.9 |
| `test_ev_update_kitting.py` | 11 | 16.6 | `test_late_part_keeps_the_early_part_and_makes_no_kit_until_both_arrive` | 4.4 |
| `test_allocation_hierarchical.py` | 14 | 15.2 | `test_hierarchy_gap_is_nonnegative` | 9.6 |
| `test_allocation_grid.py` | 16 | 13.6 | `test_scan_surface_guard_raises` | 13.0 |
| `test_s2_actual_shipment_eval.py` | 12 | 9.2 | `test_c3_4_capacity_cut_on_a_copy_reaches_node_quantity_and_money` | 8.7 |
| `test_stage_d_part0.py` | 10 | 8.1 | `test_alloc_tariff_on_border_edges` | 5.0 |
| `test_stage3a1_stockyard.py` | 11 | 7.8 | `test_ev_europe_2026_local_chain_matches_pre_yard_baseline` | 3.5 |
| `test_holiday_explicit_closure.py` | 21 | 5.9 | `test_t17_headless_load_order` | 5.0 |
| `test_allocation_plot.py` | 7 | 5.7 | `test_plot_each_scenario` | 2.9 |
| `test_lovem_viewer.py` | 4 | 4.7 | `test_tk_viewer_draws_everything_and_selects` | 2.7 |
| `test_ppc_vertical_slice.py` | 33 | 4.5 | `TestT9_TariffScenarioChange::test_higher_tariff_increases_cost` | 0.3 |
| `test_ppc_run_info.py` | 10 | 4.2 | `test_management_panel_reads_ppc_only_for_the_current_plan` | 2.0 |
| `test_merit_order_plot.py` | 10 | 3.9 | `test_plot_pareto_scatter` | 0.8 |
| `test_stage3a2_kitting_gate.py` | 9 | 3.7 | `test_ev_europe_2026_import_factory_p_matches_real_demand` | 3.3 |
| `test_valuechain_handcalc.py` | 12 | 3.6 | `test_basic_table` | 0.6 |
| `test_worldmap_ne.py` | 8 | 2.8 | `test_converter_is_deterministic` | 1.5 |
| `test_allocation_regime_map.py` | 9 | 2.6 | `test_cli_demo_generates_all` | 1.5 |
| `test_flow_check.py` | 9 | 2.2 | `test_psi_list_table_ship_and_sum_row` | 1.4 |
| `test_lovem_interval_check.py` | 4 | 2.2 | `test_new_check_and_week_expansion_agree_on_the_run` | 1.3 |
| `test_public_readiness.py` | 22 | 2.1 | `test_headless_without_plugins_uses_the_recommended_set_and_records_it` | 1.3 |
| `test_decouple_optimizer.py` | 4 | 1.5 | `test_find_optimal_decouple_placement_cookie_import` | 0.9 |
| `test_sim_mgmt_display.py` | 14 | 1.2 | `test_management_simulation_then_planning_never_mixes_sources` | 0.8 |
| `test_s1_view_model.py` | 22 | 1.2 | `test_plot_kind_by_child_count` | 0.3 |
| `test_capacity_layer_trial.py` | 10 | 1.2 | `test_greedy_loss_is_structural_resource_usage` | 1.1 |
| `test_lot_identity_flow.py` | 15 | 1.1 | `test_integration_planning_config_selects_mode` | 0.9 |
| `test_allocation_cli.py` | 6 | 1.0 | `test_run_writes_seven_files` | 0.3 |
| `test_capacity_zero_blank.py` | 31 | 0.7 | `test_headless_run_stops_on_a_wrong_node_name` | 0.2 |
| `test_report_start.py` | 5 | 0.6 | `test_flow_check_table_2_report_columns_only_with_a_report_start` | 0.3 |
| `test_warmup_materialize.py` | 13 | 0.4 | `test_materialize_demand_zero_and_copy` | 0.1 |
| `test_demand_envelope_soft.py` | 3 | 0.3 | `test_soft_mode_levels_at_cap_soft` | 0.3 |
| `test_rice_seasonal_trial.py` | 22 | 0.2 | — | 0.0 |
| `test_money_units.py` | 5 | 0.2 | — | 0.1 |
| `test_merit_order.py` | 28 | 0.2 | — | 0.0 |
| ほか 31 ファイル | — | 各 0.1 未満 | — | < 0.1 |

（ほか 31 ファイル：`test_smartx_evidence_ranges`・`test_plan_period`・`test_composite_kitting_recovery`・`test_buffering_stock_optimizer_plugin`・`test_ppc_bom_qty`・`test_allocation_nonconcave`・`test_rice_retire`・`test_ppc_multi_supplier`・`test_bom_qty`・`test_step10_hooks`・`test_cpu_size_plan_wide`・`test_step8_push_pull`・`test_allocation_nmarket`・`test_allocation_cost_block`・`test_init_stock_days_wiring`・`test_regime_map`・`test_step7_capacity`・`test_pareto_front`・`test_allocation_merit_order`・`test_allocation_material_invariant`・`test_capacity_soft`・`test_backward_holiday_carryback`・`test_allocation_analytics`・`test_backward_supply_role`・`test_kitting_stage1`・`test_capacity_soft_backward`・`test_operating_calendar`・`test_lovem_intervals`・`test_push_pull_mode4_supply_role`・`test_shift_cap_soft`・`test_allocation_transmission`。全行は `output/test_timing/by_file.md`）

## Q-2 作業の前後

| | 前（8f50c28） | 後 |
|---|---|---|
| `--collect-only` の件数 | 888 | 892 |
| ID の差 | — | **増えたのは `tests/test_test_areas.py` の 4 件だけ**。前の 888 件はすべて同じ ID（`Compare-Object` で差 0） |
| 全テスト | 885 passed・3 skipped（15 分 24 秒） | **889 passed・3 skipped**（17 分 49 秒、`quick_check --full`）。885＋新しい 4 件 |

skipped の 3 件は前後とも同じ（`test_gui_panel_invariants.py::test_descendable_rows_are_bound[triangle_n3／leaf_shipped／leaf_zero_shipped]`）。2 回目の全テストが 2 分 25 秒長いのは、同じパソコンの負荷の違いと見られる（テストの中身・件数は同じ。全テストは 2 回までの約束なので、測り直していない）。

`pytest.ini` を repo の root に置いたが、テストの ID は変わらない（前から root からの相対の `tests/test_*.py::...` だった）。

## Q-3 smoke

`python -m tools.quick_check --smoke` → `-m smoke`：**497 passed、395 deselected、57 秒**（pytest の表示 52 秒＋起動）。

入れたもの（`tests/conftest.py` の `SMOKE`）：
- `core` の 3 層テストの Unit・Integration の速いファイル 20 個（`test_lot_identity_flow`・`test_capacity_soft`・`test_capacity_soft_backward`・`test_capacity_zero_blank`・`test_step7_capacity`・`test_step8_push_pull`・`test_backward_supply_role`・`test_backward_holiday_carryback`・`test_push_pull_mode4_supply_role`・`test_operating_calendar`・`test_shift_cap_soft`・`test_demand_envelope_soft`・`test_init_stock_days_wiring`・`test_bom_qty`・`test_kitting_stage1`・`test_composite_kitting_recovery`・`test_warmup_materialize`・`test_plan_period`・`test_flow_check`・`test_report_start`。どれも 3 秒未満）
- golden：`bom-test-2026`（0.3 秒）・`Cookie-jp-2026`（5.1 秒）
- ほかの領域から速くて代表になるファイル：capacity（`test_capacity_layer_trial`・`test_cpu_size_plan_wide`）、rice（`test_rice_seasonal_trial`・`test_rice_retire`）、plugins（`test_step10_hooks`・`test_buffering_stock_optimizer_plugin`・`test_decouple_optimizer`）、ppc（`test_ppc_vertical_slice`・`test_valuechain_handcalc`・`test_money_units`）、allocation（`test_merit_order`・`test_allocation_transmission`・`test_allocation_nonconcave`・`test_pareto_front`）、lovem（`test_lovem_intervals`）、gui（`test_s1_view_model`・`test_sim_mgmt_display`）、worldmap（`test_worldmap_ne`）、public（`test_public_readiness`・`test_smartx_evidence_ranges`）
- 必ず：`test_no_real_names`（19 秒）・`test_test_areas`

外したもの：時間の合計の大きい core のファイル（`test_push_pull_mode4_double_count` 51 秒・`test_planning_state` 19 秒・`test_ev_update_kitting` 17 秒）と、20 秒以上のテストを含むファイル。smoke は 3 分の枠に余裕があるので、必要ならこれらを足せる。

## Q-4 領域ごと

実際に回したのは rice・core（と smoke・golden 1 件）。ほかは 2.1 の実測の合計＋収集の約 6 秒の見積もり。

| 領域 | 件数 | 時間 | 20 秒以上（slow）を外すと |
|---|---:|---:|---:|
| `core` | 289 | **132 秒（実測）** | 同じ（slow 無し） |
| `capacity` | 79 | 約 130 秒 | 約 20 秒（世代ラインの 67 秒・K-R10 の 43 秒を外す） |
| `rice` | 70 | **66 秒（実測）** | 約 20 秒 |
| `plugins` | 64 | 約 16 秒 | 同じ |
| `ppc` | 113 | 約 160 秒 | 約 40 秒 |
| `allocation` | 195 | 約 50 秒 | 同じ |
| `lovem` | 26 | 約 285 秒 | 約 20 秒 |
| `gui` | 142 | 約 90 秒 | 同じ |
| `worldmap` | 20 | 約 35 秒 | 同じ |
| `golden` | 18 | 約 115 秒 | 同じ |
| `public` | 49 | 約 27 秒 | 同じ |

どの領域も 5 分以内。lovem だけが 5 分に近い（観測の 3 件で 264 秒）。`-m "lovem and not slow"` なら約 20 秒。

## Q-5 `--changed`（`--dry-run`、ファイルは変えずにパスを引数で渡した）

```
python -m tools.quick_check --changed wom/capacity_layer/rice_seasonal.py --dry-run
  -> pytest tests/ -m "capacity or rice"                                   areas=capacity,rice

python -m tools.quick_check --changed wom/engine/forward_planner.py --dry-run
  NOTE: PROTECTED CORE changed: run --full and the 3-layer tests (Unit / Integration / E2E golden) before review
  -> pytest tests/ -m "core or golden or smoke"                            areas=core,golden,smoke

python -m tools.quick_check --changed data/sample/rice-japan-2027-2028/capacity_plan.csv --dry-run
  -> pytest tests/ -m "rice or smoke"
  -> pytest tests/test_golden.py::test_golden_matches[rice-japan-2027-2028]    areas=rice,smoke golden=rice-japan-2027-2028

python -m tools.quick_check --changed docs/WOM_Start_Here.md requests/RequestLetter_QuickCheckTests_to_CodeKun.md --dry-run
  -> pytest tests/ -m public                                               areas=public
```

ほかに確かめたこと：`data/sample/bom-test-2026/...` → smoke ＋ golden の bom-test 1 件。対応の無いパス（例 `setup_foo.cfg`）→ smoke ＋「no rule in PATH_RULES」の表示。`--golden Cookie-jp-2026` は legacy の golden も含めて 2 件。知らない領域（`--area foo`）は誤りで止まる。`--golden rice-japan-2027-2028` は実際に回して 1 passed（18 秒）。`python -m pytest tests/test_golden.py -k bom-test-2026` でも 1 件だけ選ばれる（モデル名のハイフンは `-k` でそのまま使える）。

## Q-6 漏れを防ぐテスト

`tests/test_test_areas.py`（4 件、smoke と `public` に入れた）：
1. `tests/test_*.py` のすべてが `AREAS` のどれかの領域に入っている
2. `AREAS` は実在するファイルと、知っている領域だけを名指す
3. `SMOKE` が空でなく、どの行もテストのファイルを名指す
4. 使う印（11 の領域・`smoke`・`slow`）がすべて `pytest.ini` に登録され、`--strict-markers` がある

緑（4 passed）。`AREAS` から `test_rice_retire.py` の行を一度外すと `test_every_test_file_has_an_area` が `add these files to tests/conftest.py AREAS: ['test_rice_retire.py']` で落ちることを確かめ、元に戻した（戻した後の内容は外す前と一致、4 passed）。

## Q-7 変更の範囲

`git status`：`M CLAUDE.md`、新規 `pytest.ini`・`tests/conftest.py`・`tests/test_test_areas.py`・`tests/README.md`・`tools/quick_check.py`。`git diff --stat` は `CLAUDE.md | 17 +++++++++++------` だけ。**既存の `tests/test_*.py`・`tests/golden/`・保護対象のコア・`wom/` に変更は無い。**

## 領域の対応表（判断に迷った分類）

全表は `tests/conftest.py` の `AREAS` と `tests/README.md`。案から変えた所・迷った所：

| ファイル | 決めた領域 | 理由 |
|---|---|---|
| `test_s1_view_model.py` | `allocation`・`gui` | tkinter は使わない（純関数）。S1 Allocate 画面の view model なので両方に入れた。`not gui` で外れても 1 秒なので損は小さい |
| `test_s2_actual_shipment_eval.py` | `core`・`ppc` | 案は gui だが tkinter を使わない。実出荷（`_actual_ship`）で充足と金額を数え直すテストなので |
| `test_flow_check.py` | `core` | Flow Check の表を計算で確かめる。窓は開かない |
| `test_holiday_explicit_closure.py` | `core`・`plugins` | 休業の週の状態は Planning Engine 側、読み込みは HolidayCalendarPlugin |
| `test_stage_d_part0.py` | `core`・`ppc` | Value Chain の Stage D の入口（計画＋台帳） |
| `test_report_start.py` | `core`・`rice` | 案のとおり両方（報告の開始の読み込みは World Map と Rice の層の共通） |
| `test_rice_seasonal_layer.py`・`test_rice_seasonal_trial.py` | `rice`・`capacity` | Rice の層は上位の層の一つ |
| `test_ev_update_kitting.py` | `core` | Kitting の判定（Planning Engine の上の段階 1） |
| `test_public_readiness.py` | `public`・`plugins` | 推奨のプラグインの組を確かめる |
| `test_ppc_run_info.py`・`test_lovem_viewer.py`・`test_worldmap_*` | それぞれの領域＋`gui` | 窓を開く部分がある |
| `test_test_areas.py` | `public` | 段の仕組みの点検 |

`gui` の印は「窓を開く（または GUI の view model の）テスト」で、`-m "not gui"` で外すのに使える。

## 依頼書の種類ごとの段（提案）

| 依頼の種類 | 途中 | 最後 |
|---|---|---|
| 文書・依頼書だけ | — | `--changed`（＝`public`、約 30 秒） |
| サンプルのデータだけ | `--golden <モデル>` | `--changed`（smoke ＋ そのモデルの golden、約 1 分半） |
| プラグイン・上位の層・PPC・GUI | smoke ＋ 関係する領域（`--changed`） | full 1 回 |
| 保護対象のコア | smoke ＋ `core` ＋ `golden`（`--changed` が選ぶ。約 5 分） | full 1 回 ＋ 3 層テストの明示 |
| テストの段そのもの（この依頼） | smoke | full 1 回 |

依頼書の表から変えた所：「サンプルのデータだけ」の最後は、`--changed` がそのまま smoke ＋ golden を選ぶので、コマンドを一つにした。

## 速くできそうなテスト（提案。実施していない）

1. **`test_valuechain_integration.py`（約 60 秒の節約）**：`test_alloc_sample_prices_leave_nothing_unvalued` が、module の fixture `alloc_run` と同じモデル（soysauce-jpy-2027-alloc）の Value Chain を、もう一度最初から回している。fixture の結果を使えば 1 回で済む見込み（同じ入力か要確認）。
2. **`test_lovem_observer.py`（最大で約 170 秒）**：ev-thailand-2026 の観測つきの計画を、`q12` と `se2_run` の 2 つの fixture で別々に回している（warm-up の有無が違う）。片方を小さいモデル（bom-test-2026。LOVEM の viewer のテストはこれで済ませている）にできないか、`verify_run` を週の一部に絞れないか。ただし SE2 の 168 lot は ev-thailand で固有の値。
3. **`test_generation_line_upper_layer.py`（約 30 秒）**：smartx を off と on で 2 回計画している。off の結果を module の fixture にして、同じファイルのほかのテストと分け合えないか。
4. **`test_push_pull_mode4_double_count.py`（約 30 秒）**：10 件のパラメータそれぞれで apparel の headless 計画を回している。LT ごとの結果を module で 1 回だけ作れば、ほぼ半分になる見込み。
5. **`test_rice_seasonal_layer.py` の K-R10（43 秒）**：Rice の計画 1 回。`tools/rice_seasonal_check.plan` の結果を module の fixture にして、同じファイルのほかの Rice の計画と分け合えないか。
6. **`test_no_real_names.py`（19 秒）**：テキストのファイルを全部読む。`git ls-files` のうち変わらない大きいデータ（golden の json・sample の CSV）の結果をキャッシュするか、二つの一覧（公開・非公開）を 1 回の走査でまとめて調べれば半分ほどになる見込み。
7. 並行（pytest-xdist）は使わない約束なので提案しない。golden の warm-up の書き込みが競合するため。

## 追加・変更のファイル

追加：
- `pytest.ini`
- `tests/conftest.py`
- `tests/test_test_areas.py`
- `tests/README.md`
- `tools/quick_check.py`
- `docs/development/WOM_QuickCheckTests_Report.md`（この報告書）

変更：
- `CLAUDE.md`（冒頭の「テスト実行」を段の表に書き換え、golden を並行させない注意の節に参照を 1 行）

git の対象外：`output/test_timing/`（測定の記録）。
