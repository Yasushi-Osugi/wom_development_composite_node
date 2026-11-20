---
handoff:
  case_id: COCKPIT-M6-004
  task_id: row-order-bias-stage1-overflow-policy
  role_from: implement         # Code君
  role_to: owner               # 大杉さん（保護対象のコアの diff を確かめてから commit）
  start_commit: 8b8f18115bb210406f2ad04730870f9dd2ec88cf
  request: requests/RequestLetter_M6_RowOrder_Stage1_OverflowPolicy_to_CodeKun.md（v0.1a）
  design: requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §3・§4
  acceptance: "S1〜S5 合格（§1）"
  status: "合格。commit していない（下書き commit_msg231.txt）"
  open_items:
    - "smartphone の Backward だけで見ると、新しい二つの方式は変更前のエンジンの 3.1〜3.2 倍（計画全体では 1.5 倍、今の tail と比べると 2.0 倍）。§4"
    - "醤油の瓶詰の工場で、休業の週（2027-W18・2028-W18・2028-W33）の供給の P が 800（6 つとも。今の動きと同じ。push の Mode 4）。§5"
  stop_reasons: []
  next: owner
---

# 報告：行の順の偏りの直し方 — 段 1：能力を超えた分の押し戻し方を設定で選べるようにした

- 依頼：`requests/RequestLetter_M6_RowOrder_Stage1_OverflowPolicy_to_CodeKun.md`（v0.1a）／設計：`requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md`
- 着手時の SHA：`8b8f18115bb210406f2ad04730870f9dd2ec88cf`
- **保護対象のコアの変更**（`wom/engine/backward_planner.py`）。3 層のテストは緑。commit はしていない（下書き `commit_msg231.txt`）
- 付録：`docs/development/WOM_M6_RowOrder_Stage1_OverflowPolicy_appendix/`（醤油の表・判定・明細、smartphone の時間、スクリプト 4 本）。作業の出力は `output/roworder_stage1/`（git の対象外）

## 一言で

`planning_config.csv` の `overflow_policy` で、`tail`（今の動き、既定）・`proportional_week`・`balance_cut_ratio` を選べるようにしました。**既定の `tail` では golden 16 件・legacy 3 件が全件そのまま**です。醤油 C02 では、新しい二つの方式は木の行の順を入れ替えても、市場別の数・納品する Lot_ID と週・押し戻しの数がすべて同じでした。④÷① の開きは、今の 55.72 ポイントが、`proportional_week` で 4.43、`balance_cut_ratio` で 0.14 ポイントになります。総納品（87,375）は 3 方式とも同じです。

## 1. 合格の条件

| # | 条件 | 結果 |
|---|---|---|
| S1 | 3 方式が選べ、知らない値で止まる。全入口で渡る | **合格**。§2.3 の一覧 |
| S2 | 設計書 §4 の例 1〜6 が期待値どおり。合成の木で行の順に対して不変 | **合格**。`tests/test_overflow_policy.py` |
| S3 | 醤油 T2＝T3、T4＝T5。T1・T6 が到達点 6 を再現 | **合格**。§3 |
| S4 | golden 16 件・legacy 3 件が全件不変。`--full` が通る | **合格**。§2.5 |
| S5 | `tail` の経路で Backward の動きが 1 つも変わらない | **合格**。§2.2 の diff の説明 |

## 2. 作ったもの

### 2.1 規則の本体 `wom/engine/overflow_policy.py`（新規。保護対象ではない）

- `OverflowTracker`：状態は工場 × 製品ごとに 1 つ。Backward の実行ごとに作り直す。
- 市場キー・要求週・連番は、`LotIDGenerator.parse()` で Lot_ID から取る。
- `proportional_week`：設計書 §3.1 のとおり。
  - 累積の丸め前の割当 R_m と、累積の不足 d_m ＝ R_m − A_m を使う。
  - まず floor を割り当て、残りは d_m の大きい市場から配る（同点は r_m の大きい順 → 市場キーの文字の順）。
  - その週の lot の数は超えない。
- `balance_cut_ratio`：設計書 §3.2 のとおり。
  - 母数は、処理済みの週に現れた lot の数（同じ Lot_ID は 1 回だけ数える）。分子は延べの押し戻し。
  - 負担率は整数の掛け算で比べる。同点は、その週の lot の多い順 → 市場キーの文字の順。
  - **速さのため、まとめて割り当てる**：「足した後の負担率がある値 V 以下」の分を一度に取り、残りを 1 lot ずつ取る。V 以下を全部取ると同じ値のものも全部入るので、1 lot ずつ選ぶのと同じ結果になる。テストで、ランダムな 400 例が素朴な 1 lot ずつの選び方と一致することを確かめた。
- 市場の中で押し戻す lot：要求週の遅いものから、同じ要求週は連番の大きいものから（§3.3）。
- 新しい二つの方式では、残す lot・押し戻す lot を「要求週 → 市場キー → 連番」の順に並べ直して返す。
- 延べの押し戻しと母数は、どの方式でも工場 × 市場ごとに数える（報告用）。
  - `tail` では数えるだけで、並びは触らない。
  - Lot_ID が読めないときは、数えるのをやめて計画を続ける。新しい方式では止める。
- 押し戻しの規則と関係のない、速さのための工夫が 2 つある。Backward は、押し戻した lot を前の週の並びの末尾に足す。そこで、
  - 並びの末尾がその押し戻しと同じか（最初と最後の lot が同じもの）を確かめたうえで、末尾の lot は見た後として扱う。
  - その市場ごとの並びを使い回す。
  - 確かめが合わないときは、全部を見る。
- `proportional_week` で floor の合計が n を超える場合（その週に lot の無い市場の累積の不足が負のとき）に備え、超えた分を配る順の逆から戻す処理を入れた。設計書・参照計算には無い場合で、醤油・smartphone では起きていない。

### 2.2 Backward（保護対象のコア）：diff の説明

`git diff --stat`：`wom/engine/backward_planner.py` は 40 行足して 3 行消した。変えたのは 6 か所。

| 場所 | 中身 |
|---|---|
| import | `overflow_policy` から `TAIL`・`OverflowTracker`・`resolve_overflow_policy` |
| `BackwardPlanResult` | 欄を 2 つ足した（`overflow_policy`、`overflow_by_node`〔工場 → 市場 → {pushed, denominator}〕）。報告用で、計画には使わない |
| `__init__` | `config["overflow_policy"]` を読む（無し・空欄 ＝ `tail`、知らない値は止める） |
| `run()` | 結果に方式を入れる |
| `_apply_mom_cap_backward` の先頭 | 能力か休業の週がある工場だけ `OverflowTracker` を作る。各週の初めに `tracker.observe(S[w])`（読むだけ） |
| 同・切り取り | `tail` なら**前と同じ 2 行**（`s_lots[:cap_int]`／`s_lots[cap_int:]`）を通したうえで、`tracker.record_tail(...)`（数えるだけ）。それ以外は `tracker.split(...)` の結果を使う |
| 同・終わり | `result.overflow_by_node[node_id] = tracker.summary()` |

**`tail` の経路が不変な理由**：
- `tail` では、残す lot と押し戻す lot の一覧を、前と同じ式で作っている。
- 足した `observe`・`record_tail` は、ノードの並びを読んで数を数えるだけで、書かない。
- そのあとの処理は 1 行も変えていない（P・S を書く、CO に記録する、前の週の S に足す、最初の週で past_due にする、cap_soft の記録）。
- golden 19 件の一致（§2.5）が、これを機械で確かめている。

**大杉さんが diff で見るべき所**：
- `if self._overflow_policy == _OVERFLOW_TAIL:` の分岐で、`tail` 側の 2 行が前と同じであること。
- `observe`・`record_tail` が `node` に書いていないこと（中身は `overflow_policy.py`）。

### 2.3 設定の読み込みと入口

- `wom/engine/warmup.py`：`read_overflow_policy(model_dir)` を足した。
  - ファイル・キーが無いとき、値が空欄のときは `tail`。
  - 3 つ以外の値は `OverflowPolicyError` で止める。メッセージに、ファイル・値・使える値・直し方を出す。
- `BackwardPlanner(` を作る所（`grep`）：

| 所 | 渡すか |
|---|---|
| `wom/gui/app.py`（2 か所。どちらも `_build_planning_context` の `cfg`） | 渡す（`_cfg["overflow_policy"]`）。`tail` 以外のときはコンソールに出す |
| `tools/run_headless_from_folder.py` | 渡す（`cfg["overflow_policy"]`） |
| `tools/sweep_flags.py` | 渡す |
| コックピットの案（`wom/cockpit/case_runner.py`） | 配分・計画・Value Chain・残存期間の段は、どれも案のモデルの写しで headless の `run()` を通る。モデルの `planning_config.csv` に書けば効く（コードを読んで確かめた。コックピットで案を回すことまではしていない） |
| `tools/probe_composite_baseline.py`、`tools/probe_rice_seasonal_definition.py` | 渡さない（固定のモデルを調べる道具。いつも `tail`） |
| `data/sample/apparel-global-2028-2029/verify/*.py`（2）、`data/sample/apparel-us-2026/exercises/*/reproduce.py`（3） | 渡さない（正式なサンプルの中なので変えない。いつも `tail`） |

- headless の snapshot：`tail` のときは config に何も足さない（golden の config と同じ）。`tail` 以外のときだけ `config.overflow_policy` を記録する。

### 2.4 テスト（`tests/test_overflow_policy.py`、19 件、`core` の領域に足した）

| 層 | 中身 |
|---|---|
| 単体 | 設計書 §4 の例 1〜6（参照計算の出力を数で書いた）。結果が全部一致した |
| 単体 | 並べ直しの順。延べの数え方（同じ Lot_ID を 2 回押し戻すと 2、母数は 1） |
| 単体 | まとめての割り当て ＝ 1 lot ずつ（ランダムな 400 例） |
| 単体 | 合成の木（工場 1・市場 3、能力 6 が続く、休業の週 1 つ、少量の市場）。木の CSV の行の順と需要の順を入れ替えた 2 つで、各週の S・P・CO、押し戻した Lot_ID、past_due、数が一致。3 方式とも、lot の保存と能力・休業への適合を確かめた |
| 結合 | `planning_config.csv` → `read_overflow_policy` の経路。ファイル無し・キー無し・空欄は `tail`、知らない値で止まる |
| 結合 | headless の snapshot。キーが `tail` なら config と psi が golden と同じ、キーありなら記録する。知らない値なら計画の前に止まる |
| E2E | `test_golden.py`（§2.5） |

### 2.5 `--full`

`python -m tools.quick_check --full`：**1343 passed・3 skipped・失敗 0**（2,150 秒）。golden 19 件（16 件 ＋ legacy 3 件、`tests/test_golden.py`）を含む。出力は `output/roworder_stage1/quick_full.txt`。

## 3. 醤油での確かめ（到達点 6 の C02、21 シフト、配分なし）

- 写しは `output/roworder_stage1/soy/T1〜T6/model`。
  - 元の木は `output/cockpit_m6/soy/C02/model`。
  - 入れ替えた木は `output/cockpit_m6/r0_order_test/model`（到達点 6 §3.3 と同じ。欧州の DC を先に、子を NL・BE・FR の順）。
  - `planning_config.csv` に `overflow_policy` を 1 行足しただけ。
- 1 つずつ headless で回した。セルは ④ 当週／⑤ 未充足（④÷①）。

| 写し | 方式 | 木 | US_W | US_E | JP | FR | BE | NL | ④÷① の開き |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | tail | 元 | 17,238／350（98.01%） | 17,238／350（98.01%） | 29,550／600（98.01%） | 14,775／300（98.01%） | 4,324／5,726（43.02%） | 4,250／5,800（42.29%） | 55.72 pt |
| T2 | proportional_week | 元 | 15,149／2,439（86.13%） | 15,037／2,551（85.50%） | 27,114／3,036（89.93%） | 12,889／2,186（85.50%） | 8,593／1,457（85.50%） | 8,593／1,457（85.50%） | 4.43 pt |
| T3 | proportional_week | 入れ替え | T2 と同じ | 同 | 同 | 同 | 同 | 同 | 4.43 pt |
| T4 | balance_cut_ratio | 元 | 15,297／2,291（86.97%） | 15,298／2,290（86.98%） | 26,185／3,965（86.85%） | 13,112／1,963（86.98%） | 8,741／1,309（86.98%） | 8,742／1,308（86.99%） | 0.14 pt |
| T5 | balance_cut_ratio | 入れ替え | T4 と同じ | 同 | 同 | 同 | 同 | 同 | 0.14 pt |
| T6 | tail | 入れ替え | 17,238／350 | 17,238／350 | 18,424／**11,726**（61.11%） | 14,775／300 | 9,850／200 | 9,850／200 | 36.90 pt |

① は US_W 17,588・US_E 17,588・JP 30,150・FR 15,075・BE 10,050・NL 10,050（計 100,501）。⑤ の計は 6 つとも 13,126、総納品は 87,375。

**一致の確かめ**（付録 `soy/soy_checks.json`・`soy/ship_digest.txt`）：

| 項目 | T2＝T3 | T4＝T5 |
|---|---|---|
| 市場別の ①・④・遅配・⑤ | 一致 | 一致 |
| 納品する Lot_ID と納品の週（87,375 件。digest は T2・T3 とも `6c382c0b6c35`、T4・T5 とも `7887a0096281`） | 一致 | 一致 |
| 工場 × 市場の延べの押し戻し・母数 | 一致 | 一致 |
| 計画の前に落ちた lot（12,326） | 一致 | 一致 |

- 数量の保存：6 つとも ① ＝ 当週 ＋ 遅配 ＋ ⑤ ＝ 100,501。早出しは 0。
- T1 は到達点 6 の C02、T6 は到達点 6 §3.3 の入れ替えの結果と、市場別の未充足が全部一致した。
- 能力・休業：Backward が置いた量は、6 つとも全週で能力以内。休業の週は 0。供給の側の P については §5 に書いた。

**工場 × 市場の累積押戻負担率**（延べの押し戻し ÷ 母数、瓶詰の工場）：

| 写し | US_W | US_E | JP | FR | BE | NL |
|---|---:|---:|---:|---:|---:|---:|
| T1 tail | 2.378 | 2.378 | 2.378 | 2.386 | **58.838** | **59.102** |
| T2 proportional_week | 13.910 | 14.018 | 13.012 | 14.018 | 14.019 | 14.019 |
| T4 balance_cut_ratio | 13.698 | 13.698 | 13.698 | 13.698 | 13.698 | 13.698 |
| T6 tail（入れ替え） | 2.378 | 2.380 | **40.109** | 2.378 | 2.378 | 2.378 |

- 延べの押し戻しの合計は、6 つとも 1,376,623 で同じ（毎週はみ出す数は方式に依らない）。違うのは市場への分け方だけ。計画の前に落ちた lot（12,326）も 3 方式で同じ。
- `balance_cut_ratio` は、負担率を全市場で 13.698 にそろえた（設計どおり）。
- `proportional_week` では JP の負担率が低く（13.012）、④÷① が高い（89.93%）。比例の割り振りはその週の並びの lot の数によるので、累積の負担率は市場でそろわない。理由の詳しい分析はしていない。差があっても、行の順には依らない。
- US_W と US_E（需要は同じ）は、`proportional_week` で少し違う。DC までの LT が 5 週と 6 週で違い、工場の週の並びに入る週がずれるためと見ている（確かめてはいない）。

## 4. 計算の速さ（smartphone-global-2026-2029 の写し、各 1 回、参考）

| 方式 | 計画全体（秒） | うち Backward（秒） | tail 比（全体／Backward） |
|---|---:|---:|---|
| 変更前のエンジン（着手時の HEAD の `backward_planner.py`）・tail | 22.7 | 4.8 | — |
| tail | 24.1 | 7.7 | 1.00／1.00 |
| proportional_week | 33.7 | 14.8 | 1.40／1.92 |
| balance_cut_ratio | 35.4 | 15.5 | 1.47／2.01 |

- 3 方式とも、PPC・past_due・工場ごとの延べの押し戻しは、速くする前の書き方と同じ値だった。tail は golden の psi とも一致した。
- tail が変更前より Backward で 2.9 秒（全体で 1.4 秒）遅いのは、報告用に数えている分。
  - 延べの押し戻しは、Phone17 だけで 3,217,648。
  - 最初の素直な書き方では、数えるだけで 8 秒かかっていた。§2.1 の工夫で 2.9 秒まで縮めた。
- **3 倍の目安**：
  - 今の tail と比べると、全体で 1.5 倍、Backward だけで 2.0 倍。
  - 変更前のエンジンと Backward だけで比べると、3.1 倍・3.2 倍で、3 倍を少し超える（計画全体では 1.5 倍・1.6 倍）。
  - 依頼書の「tail の 3 倍」は今の tail（3 方式の比較）と読んで、止めなかった。基準を変更前の Backward にするなら、この数字で判断をお願いします。
- 速くする前（素朴な 1 lot ずつ・押し戻しのたびに全部を数える）の balance_cut_ratio は、Backward 41.6 秒だった（変更前の 8.7 倍）。

## 5. 気づいたこと・申し送り

1. **醤油の休業の週の供給の P**：瓶詰の工場は push（Mode 4、`push_lead_time_weeks=7`）。
   - 休業の 3 週（2027-W18・2028-W18・2028-W33）に、`psi4supply[w][P]` が 800 になっている。Backward が置いた需要は 0。
   - 6 つとも同じで、今の動き（tail）でも起きている。今回の変更とは関係がない。push の計画は休業を見ていない可能性がある。Forward・push は触らない約束（Q5）なので、調べていない。
2. **新しい方式は、押し戻す lot を「要求週の遅いもの」から選ぶ**（Q6）。醤油では、遅い要求週の lot を各市場で少しずつ押し戻すので、⑤ が 6 市場に散った。行の順による偏りは消えた。
3. **段 2（化粧品）へ**：醤油は毎週の市場の構成が同じなので、`proportional_week` と `balance_cut_ratio` の差は小さい（開き 4.43 と 0.14）。販売開始がずれる市場があるモデルで差が出るかは、段 2 で見る。
4. **画面**：`overflow_policy` を選ぶ画面の部品は作っていない（依頼の範囲外）。GUI は `planning_config.csv` を読むだけ。GUI を起動しての確かめはしていない。

## 6. テストの記録

- `tests/test_overflow_policy.py`：19 passed。
- smoke（作業の途中）：509 passed。
- `--full`：`[quick_check] tier=full | passed=1343 failed=0 skipped=3 error=0 | 2150 s | OK`（前回の記録 892 件・15〜18 分より件数・時間とも多い。今回足した 19 件を含む）。

## 7. 作り直す手順

```bash
python output/roworder_stage1/soy_compare.py
python output/roworder_stage1/soy_tables.py
python output/roworder_stage1/speed_smartphone.py
python output/roworder_stage1/speed_head_engine.py <着手時の HEAD の backward_planner.py の写し>
python -m tools.quick_check --full
```

（スクリプトは付録 `scripts/` にもある。`output/` に置いて使う。）
