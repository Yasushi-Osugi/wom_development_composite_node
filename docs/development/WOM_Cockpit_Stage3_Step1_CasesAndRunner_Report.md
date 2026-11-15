---
handoff:
  case_id: COCKPIT-GUI-001
  task_id: STEP1-cases-and-runner
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  start_commit: 5fa18f3        # 着手時（2026-11-13 21:39）。作業中に大杉さんの commit が進み、終わりの時点の HEAD は 3a570fc
  request: requests/RequestLetter_Cockpit_Stage3_Step1_CasesAndRunner_to_CodeKun.md
  acceptance:
    S1: pass   # 6 案の P0・クリームの納品・未充足・未配分、5 組の ΔP0・境目が §1 と 1 円も違わない
    S2: pass   # 6 案はコマンドだけで作った（付録 build_six.sh）
    S3: pass   # 入力が変わった → 戻すと済み、作業ごと写して list が同じ
    S4: pass   # smoke 507 passed、allocation・gui 466 passed（3 skipped）、失敗 0
    S5: pass
  stop_reasons: []
  open_items:
    - "生産量を上げる費用は未設定（GPT-MC の業務定義が採用されたら、道具 2 と費用の前提に足す）"
  next: owner
---

# 報告書：経営コックピット 到達点 3・段 1 — 事業計画の案を保存して実行する仕組み（画面なし）

- 依頼書：`requests/RequestLetter_Cockpit_Stage3_Step1_CasesAndRunner_to_CodeKun.md`（v0.1）
- 設計の正本：`requests/Cockpit_Stage3_DesignMD_PlanCompareScreen_v0.1.md`（採用済み）
- 作業：Code君（Claude Code、Windows）
- 着手時の SHA：`5fa18f3`（依頼書の基準 `3c3d677` の 2 つ後。間の差は依頼書と棚卸しの報告書だけで、`wom/`・サンプル・golden は同じ）
- 付録：`docs/development/WOM_Cockpit_Stage3_Step1_CasesAndRunner_appendix/`
- 作業の出力（git の対象外）：`output/cockpit_cases/stage1/`（6 案と 5 つの比較）

## 一言で

**前回 Code君が手で作った 6 つの案を、「作る・複製する・入力を変える・実行する・並べる」の決まった操作だけで作り直し、前回と 1 円も違わない数字が出ました。** 1 案の実行は約 25〜33 秒（方針ありの案は数量配分の分だけ長い）。画面はまだ作っていません。段 2（見る画面）と段 3（操作）は、この仕組みを呼ぶだけで作れます。

## 1. 作ったもの

| ファイル | 中身 |
|---|---|
| `wom/cockpit/cases.py` | 案の置き場と記録。作業を作る・案を複製する・入力を変える（投入の表を置く、1 つの鍵の投入週、計画の生産量、`max_supply` と `cap_soft` の組、供給の方針、費用の前提）・状態を読む・一覧。Tk を import しない |
| `wom/cockpit/case_runner.py` | 1 案を段の順に実行する（`run_case`）、2 案を並べる（`compare_cases`）。進み具合を呼ぶ側の関数へ渡す。Tk を import しない |
| `tools/cockpit_cases.py` | 上の二つを呼ぶだけのコマンド：`new`・`copy`・`set`・`run`・`compare`・`list`・`status` |
| `tests/test_cockpit_cases.py`（11 件）・`tests/test_cockpit_case_runner.py`（13 件） | §5 |

### 1.1 置き場

設計書 §3 のとおり。補足：

- 案の ID は `C01`、`C02` …。`case.json` に親の案と、入力を変えた履歴（いつ・何を・前の値と後の値）を残す。
- `workspace.json` に、元のモデルの場所と全ファイルの sha256、Git の SHA、需要の期間（元のモデルの `demand_forecast.csv` の最初と最後の週、2026-W37〜2029-W52）、報告期間（`vc_config.csv` の `report_start` 〜 需要の最後の週、2027-W01〜2029-W52）、年齢の検査の上限（`--max-age-weeks`、必須）。
- 記録の中のパスは作業のフォルダからの相対パス。作業ごと別の場所に写しても同じ表が出る（S3）。
- 方針ありの案は、数量配分を案のモデルの写し（`udp/work/<案>`）で回す。道具が配分後の需要（`demand_forecast_Q01.csv`）をモデルのフォルダに書くので、案の `model/` を書き換えないため。金額の実行は、配分後の需要を `demand_forecast.csv` に置いた写し（`run/model_alloc`）で行う（前回の `A_late_m` と同じ作り）。

### 1.2 状態

| 状態 | 決め方 |
|---|---|
| 未実行 | 実行の記録が無い |
| 実行中 | 実行の記録の state が実行中（今の段も出す） |
| 済み | 実行が終わり、実行の時の入力の hash と今の入力の hash が同じ |
| 止まった／衝突／未達／不整合 | 段の結果（理由と道具のメッセージをそのまま `case.json` に） |
| 入力が変わった | 実行の記録の hash と今の hash が違う（違うファイルの名前も出す） |

- hash の対象：`model/` の全ファイルと、方針のファイル（数量枠・最低供給量・知識）と方針の設定。**費用の前提（`inputs/fixed_cost.csv`）は含めない**（計画を回し直す必要が無く、比較だけが読むため。§7 の D2）。
- 依頼書の「変えたら未実行に戻す」は、状態を記録から導く形にした：入力を変えると「入力が変わった」（＝実行し直す）になり、結果は出さない。元に戻すと「済み」に戻る（§3 手順 5 を満たすため。実行の記録は消さない）。
- 一覧（`list_cases`）は、「済み」の案にだけ結果の要点を付ける（設計書 §2.2 の 1：今の入力の結果だけを出す）。

### 1.3 実行の段と、道具の呼び方

| 順 | 段 | 呼ぶもの | 呼び方 |
|---|---|---|---|
| 1 | 需要 | 道具 1 で投入の表から需要を作り、案の `demand_forecast.csv` とバイト単位で同じかを確かめる（違えば止める。需要 CSV を手で書き換えた場合） | 関数 |
| 2 | 数量配分（方針ありだけ） | `tools.run_quantity_allocation`（`--week-rule`・`--policy-file`・`--knowledge-file`・`--unallocated-note`・`--plugins`） | 子プロセス |
| 3 | 計画・PPC・Flow Check | `tools.run_headless_from_folder`（`--out`・`--ppc-out`・`--flow-check-out`） | 子プロセス |
| 4 | Value Chain | `tools.valuechain_run` | 子プロセス |
| 5 | 年齢の検査 | `tools.shelf_life_check`（`--max-age-weeks` は作業の値） | 子プロセス |
| 6 | 突き合わせ | 道具 2 の関数（`load_run`・`supply_by_request_week`・`check_against_flow`・`money_by_week_sku`・`allocation_table`・`report_p0`）で、要求週別の供給 ＝ Flow Check の表 2、SKU 別の試算利益の合計 ＝ `profit_r2_hq_wk`、方針ありは金額の実行の出荷 ＝ 数量配分の結果（鍵 × 要求週）。結果の要点を作る。実行の間にモデルと入力が変わっていないことも確かめる | 関数 |
| — | 2 案を並べる | `tools.compare_scenarios.compare`。固定費の表は二つの案の費用の前提から作る（`compare/<基準>__<相手>/fixed_cost_plan.csv`） | 関数 |

- **子プロセスにした理由**：計画の道具は、実行のたびにプラグインと計画の木を作り直し、標準出力に書く。1 つのプロセスで続けて回したときの状態の持ち越しを避け、前回の手の手順と同じコマンドにし、道具が出したメッセージをそのまま記録（`run/logs/<段>.log`）に残すため。段 3 の画面を裏のスレッドで動かすときも、画面のプロセスを道具の出力で汚さない。
- **関数にした理由**：道具 1・道具 2 は CSV を読み書きするだけで、止める理由を例外（`EntryPlanError`・`CompareError`）で返すので、関数で呼べる。
- プラグインは各段に、案のモデルの `recommended_plugins` を明示（無ければ止める）。
- 数量配分の終了コード：3 → 衝突、4 → 未達、1 → 不整合、ほかの 0 以外 → 止まった。どれも道具のメッセージの最後の 40 行を `case.json` の `message` に残し、後の段は回さない。
- 進み具合：`run_case(..., on_progress=f)` に、段ごとの開始・終了・止まったを渡す（案・段・見出し・何段目／全段・秒・メッセージ）。
- **既存の道具・エンジンのコードは変えていない。** 変えないと進めない所は無かった。

## 2. 確かめた手順と結果

### 2.1 6 案を作る（S2）

付録 `build_six.sh`（実行の記録 `build_six.log`）。ファイルの書き換えはすべて `cockpit_cases set` を通した。数量枠・最低供給量・知識・固定費・投入の表は、前回の付録 `inputs/` のファイルを `set` で指定した。

1. `new`（正式なサンプルの写し）→ C01 に投入の表（後期）を置き、C3a（美容液 17/14、クリーム 13/11）、固定費（後期）＝「基準・後期」
2. C01 → C02：タイのクリームの投入週を 2027-W27、固定費（早期）＝「基準・早期」
3. C01 → C03：方針（TH70 の数量枠 ＋ MS50TH70、`trim_to_capacity_latest`）＝「方針あり・後期」
4. C02 → C04：方針（早期の数量枠 ＋ MS50TH70）＝「方針あり・早期」
5. C01 → C05、C02 → C06：クリームの計画の生産量 12＝「生産量を上げる」

作った 6 案のモデルは、前回 Code君が手で作ったモデル（cmp1 の `model_late`・`model_early`、cmp2 の `A_*`・`B_*`）と、`demand_generation_log.json`（中の絶対パスだけが違う）以外の全ファイルが同じだった。C01 の需要は正式なサンプルの `demand_forecast.csv` とバイト単位で同じ。

### 2.2 6 案の結果と §1 の照合（S1）

付録 `s1_cases_vs_request.csv`。

| 案 | クリームの納品 | タイのクリームの未充足 | SG 代理店のクリームの未配分 | `P0`（円） | 状態 |
|---|---:|---:|---:|---:|---|
| C01 基準・後期 | 1,680 | 88 | — | 606,871,080 | 済み・一致 |
| C02 基準・早期 | 1,680 | 166 | — | 606,871,080 | 済み・一致 |
| C03 方針あり・後期 | 1,680 | 0 | 88 | 607,046,472 | 済み・一致 |
| C04 方針あり・早期 | 1,680 | 0 | 166 | 607,155,984 | 済み・一致 |
| C05 生産量を上げる・後期 | 1,768 | 0 | — | 616,860,840 | 済み・一致 |
| C06 生産量を上げる・早期 | 1,846 | 0 | — | 625,715,400 | 済み・一致 |

- 方針ありの 2 案は、クリームの供給の対象の未充足（⑤）が全鍵で 0。
- 6 案とも「評価済み」（連結の法人の未評価の明細 0）。突き合わせ（Flow Check 表 2・`profit_r2_hq_wk`・方針ありは数量配分の結果）はすべて通った。

### 2.3 5 つの組（S1）

付録 `s1_compare_vs_request.csv`。

| 組 | `ΔP0`（円） | `ΔW` | 境目 | 期待 |
|---|---:|---:|---|---|
| C01 → C02（基準 後期 → 早期） | 0 | 26 | 0 円で同額 | 一致 |
| C03 → C04（方針あり 後期 → 早期） | ＋109,512 | 26 | **f* ＝ 4,212 円／週** | 一致 |
| C05 → C06（生産量を上げる 後期 → 早期） | ＋8,854,560 | 26 | **f* ＝ 340,560 円／週** | 一致 |
| C01 → C05（生産量だけ） | ＋9,989,760 | 0 | 順位変化なし | 一致（前回 C3） |
| C02 → C04（方針だけ） | ＋284,904 | 0 | 順位変化なし | 一致（前回 C4） |

### 2.4 「入力が変わった」と開き直し（S3）

付録 `compare_and_check.sh`・`compare_and_check.log`。

- 済みの C05 のクリームの計画の生産量を 12 → 11 にすると、状態が「入力が変わった（`model/capacity_plan.csv`）」になり、一覧から C05 の結果が消えた。12 に戻すと「済み」に戻り、結果も出た。
- 作業のフォルダを丸ごと別の場所（`stage1_moved`）に写して `list` した表は、元の表と同じだった。
- 一覧の出力：付録 `list_original.txt`。

### 2.5 段ごとの時間（段 3 の進み具合の材料）

付録 `stage_seconds.csv`（Windows、6 案を続けて実行）。

| 段 | 秒 |
|---|---|
| 需要 | 0.0 |
| 数量配分（方針ありだけ） | 2.9〜3.3 |
| 計画・PPC・Flow Check | 6.4〜9.5 |
| Value Chain | 10.6〜11.9 |
| 年齢の検査 | 6.6〜7.6 |
| 突き合わせ | 1.1〜1.6 |
| **1 案の計** | **方針なし 約 25 秒、方針あり 約 31〜33 秒** |
| 2 案を並べる | 約 10〜15 秒 |

計画は 3 回回っている（計画・PPC、Value Chain、年齢の検査がそれぞれ計画する）。段 3 で待ち時間が気になれば、これを 1 回にまとめるのが一番効く（§7 の D3）。

## 3. 段 2（見る画面）へ渡すもの

画面は次の関数とファイルを読むだけでよい（数字を作り直さない）。

| 使い道 | 関数・ファイル | 形 |
|---|---|---|
| ① 案の表 | `cases.list_cases(ws)` | 1 案 1 行の dict：`id`・`name`・`parent`・`inputs`（`launch_week`：鍵 → 週、`capacity`：`SKU@工場` → `max_supply/cap_soft`、`policy`、`fixed_cost`〔週額が空欄なら「未設定」〕）・`state`・`reason`・`result`（済みだけ：`P0_report`・`report_period`・`valuation`・`deliveries_by_sku`・`demand_by_sku`・`backlog_end_by_key`・`late_by_key`・`unallocated_by_key`〔方針なしは None＝「—」〕・PPC の全計画期間の粗利と売上・通貨） |
| 変えた所だけを並べる | `cases.format_list(rows)` の作り（案の間で違う入力の列だけを出す） | 画面の列の選び方の手本 |
| 状態 | `cases.status(ws, cid)` | `state`・`reason`・`changed_files` |
| ② 入力 | 案の `model/market_entry_plan.csv`・`model/capacity_plan.csv`、`case.json` の `inputs`、`inputs/` のファイル | |
| ③ 比較 | `compare/<基準>__<相手>/` の道具 2 の出力（`supply_allocation_by_request_week.csv`・`supply_by_request_week.csv`・`factory_weekly.csv`・`factory_idle_weeks.csv`・`money_totals.csv`・`money_by_week_sku.csv`・`fixed_cost_breakeven.csv`・`inventory_by_week_sku.csv`・`age_summary.csv` など）と `compare.json`（`P0`・`ΔP0`・固定費の表、比較の時の両案の入力の hash） | |
| 比較の状態 | `case_runner.compare_status(ws, base, alt)` | 済み／未実行／入力が変わった（比較の後で案を変えた・実行し直した）／不整合 |
| ④ 注意 | 案の `run/logs/*.log`、`case.json` の `run.message`、`compare.json`、道具 2 の `comparison_summary.md` | |

## 4. 合格の条件

| # | 条件 | 結果 |
|---|---|---|
| S1 | 6 案の `P0`・クリームの納品・未充足・未配分、比較の `ΔP0` と境目が §1 と一致 | **合格**（§2.2・§2.3。`P0` は 1 円も違わない） |
| S2 | ファイルを手で書き換えていない | **合格**（付録 `build_six.sh`・`build_six.log`） |
| S3 | 「入力が変わった」の検出と、開き直しで同じ表 | **合格**（§2.4） |
| S4 | §4 のテスト | **合格**（§5.1） |
| S5 | 変えたのは新規の 3 ファイル、テスト、`tests/conftest.py`、報告書と付録だけ | **合格**（`git status`。`wom/engine`・`wom/ppc`・`wom/valuechain`・既存の道具・`data/sample/`・`tests/golden/`・`wom/gui/app.py`・9 月のコックピットの画面は変えていない。作業中に見えた `docs/design/drafts/` の変更は私の作業ではない） |

## 5. テスト

- `tests/test_cockpit_cases.py`（11 件）：作業を作るときの記録と、元のモデルに書かないこと（前後の hash）、作業を元のモデルの中・空でない場所に作らないこと、複製で `run/`・`udp/` を写さない・ID の連番・親の記録、1 つの鍵の投入週だけが変わり需要が作り直されること（親は変わらない）、期間の外の投入週で止まりファイルが元のまま、計画の生産量が助走の行を含む全行に書かれ `max_supply` を超える値で止まる、`max_supply`・`cap_soft` の組の検査、方針と費用の前提のファイル（2 案の表から片側を取る、空欄は「未設定」）、hash による「入力が変わった」と戻すと「済み」・手の書き換えも検出・費用の前提は hash に入らない、作業ごと写して同じ表。
- `tests/test_cockpit_case_runner.py`（13 件）：段の順と進み具合の記録（方針なし・方針あり）、止まった段の道具のメッセージが残り後の段を回さない、予期しない例外も「止まった」になる、数量配分の終了コード 3・4・1・2 の状態、手で書き換えた需要で止まる、`recommended_plugins` が無いと止まる、済みでない案は並べられない、**化粧品の写しでの通し（基準・後期の `P0` 606,871,080 と クリームの納品 1,680、未充足 88／104、評価済み）**。
- 領域：二つとも `allocation`・`gui`（`tools/quick_check.py` の `wom/cockpit/*` の対応と同じ。`test_s1_view_model.py` と同じ扱い。Tk は開かない）。通しのテストは `SLOW` に足し、smoke に入れない。
- 実行結果：§5.1。

### 5.1 実行結果

付録 `qc_smoke.log`・`qc_area.log`。

| 段 | 結果 |
|---|---|
| `quick_check --smoke` | **507 passed・失敗 0（92 秒）** |
| `quick_check --area allocation,gui` | **466 passed・3 skipped・失敗 0（213 秒）**。新しい 24 件、道具 1（21 件）・道具 2（21 件）、9 月のコックピット（`test_s1_view_model.py` など）を含む |
| 通しのテストと道具 1・道具 2 のテストを単独で | 43 passed（33 秒。通しのテストが skip されていないことを確かめた） |

`--full` は回していない（エンジンを変えていないため、依頼書 §4）。

## 6. 申し送り

1. **投入の表を置く操作を足した**（`set entry-plan`）。正式なサンプルには `market_entry_plan.csv` が無いので、最初の案に投入の表を置く操作が要った。依頼書の (a)〜(e) には無い。
2. **費用の前提は、2 案の表（`case` 列あり）から片側を取って入れる**（`set fixed-cost --file … --side base|alt`）。前回の固定費の表が 2 案の組の形だったため。1 行ずつ指定する形（`--cost-item` など）も使える。
3. **方針の設定には、知識のファイルと未配分の扱いの注記も入れる**（前回の手順と同じ引数を渡すため）。
4. 数量配分の道具は `--unallocated-note` を省くと記録に「未決（U1）」と書く。前回の注記を `set policy` で渡した。
5. 1 案の実行で計画が 3 回回る（§2.5）。
6. 作業中に `HEAD` が `5fa18f3` → `3a570fc` に進んだ（大杉さんの commit。`wom/`・サンプル・golden は変わっていない）。

## 7. 大杉さんに決めてほしいこと

| # | 一言で | 中身 | 推奨 |
|---|---|---|---|
| D1 | 「未実行に戻す」の読み方 | 入力を変えたら状態を「入力が変わった」（＝実行し直す）にし、元に戻せば「済み」に戻す形にした。依頼書の「未実行に戻す」を文字どおりにすると、手順 5 の「戻すと済み」と両立しないため | **この形で可**。画面では「入力が変わった」を「実行し直す」と出す |
| D2 | 費用の前提を hash に入れるか | 今は入れない（週額を変えても計画を回し直さずに比べ直せる）。代わりに比較の記録に両案の固定費の表を残す | **入れない**。費用の前提を変えたら比べ直すだけでよい |
| D3 | 1 案の実行で計画を 3 回回すのを 1 回にするか | 今は前回の手順どおり、計画・PPC、Value Chain、年齢の検査の 3 つの道具がそれぞれ計画する（1 案 25〜33 秒）。1 回にするには、道具を変えずに計画の木を共有する入口が要る | **今はこのまま**。段 3 で待ち時間が問題になってから |
| D4 | 段 2 に進む | §3 の関数とファイルで、見る画面を作る | **進む** |

## 8. 記録

- 時刻：始め 2026-11-13 21:39、利用の上限で中断、再開 2026-11-15 09:16、終わり 2026-11-15（Windows の時計）。
- 人の橋渡し：なし（中断の後に大杉さんが「続けて」）。
- 再利用した知識：前回の 2 つの報告書（6 つの案の入力と結果、実行の手順、付録の入力のファイル）、道具 1・道具 2、`tools.run_quantity_allocation` の終了コード、`tools.shelf_life_check`・`tools.valuechain_run` の `--plugins` を省いたときの既定（フォルダ名の golden か `safe`）の注意。
- **迷った所・足りなかった情報**：
  1. 正式なサンプルに投入の表が無い（§6 の 1）。最初の案にどの表を置くかは、前回の付録の後期の表にした。
  2. 「変えたら未実行に戻す」と「戻すと済みに戻る」の両立（D1）。
  3. 費用の前提の形（2 案の組の表 → 案ごとの表、§6 の 2）と、hash に含めるか（D2）。
  4. 年齢の検査の上限（52 週）は依頼書に無かったので、作業を作るときの必須の値にした（黙った既定値を作らない）。
  5. 道具 2 の固定費の表は「2 案の組」の形なので、比べるたびに二つの案の費用の前提から作る。
