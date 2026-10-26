# 報告書：数量で配分を渡す経路（数量配分モード）

- 依頼書：`requests/RequestLetter_QuantityAllocationMode_to_CodeKun.md` v0.2（`07fdd26`）
- 実装：Code君（Claude Code、Windows）、2026-10-26

---

## 1. SHA と変えたファイル

- **着手時**：`07fdd26`（依頼書 v0.2 の commit）。**完了時**：未 commit（下書き `commit_msg130.txt`）。
- **保護対象のコア（`AGENTS.md` §10 の 6 ファイル）は変えていない。**

| ファイル | 内容 |
|---|---|
| `wom/allocation/handoff.py` | C.1 `read_quantity_allocation()`・`write_demand_for_quantity_allocation()`・`QuantityAllocationError` を追加。C.4 `write_demand_for_allocation()` に二重計上の検査を追加 |
| `wom/engine/warmup.py` | C.2 `materialize_warmup(..., warmup_real_start=None)` |
| `tools/run_headless_from_folder.py` | C.2 `run(..., ppc=True, warmup_real_start=None)` |
| `tools/run_quantity_allocation.py`（新規） | C.3 数量配分の一巡と記録 |
| `wom/planning_state/__init__.py` | C.5 `realized.unmet_lots` → `backlog_lot_weeks`、`load()` が旧い名前を新しい名前で読む |
| `wom/cockpit/s3_run.py`・`wom/cockpit/s3_view_model.py`・`tools/run_planning_loop.py` | C.5 読む名前と画面の語（「未充足 X lot」→「注文残 延べ X lot・週」） |
| `tests/test_quantity_allocation.py`（新規、19 件）・`tests/test_planning_state.py`（名前 2 か所）・`tests/conftest.py`（1 行） | §D |
| `requests/Phase7_RequestLetter_to_CodeKun.md`・`requests/Phase7a_Addendum_to_CodeKun.md`・`requests/Phase8_DesignMD_CockpitGUI.md` | C.5 訂正の注記を末尾に 1 段落（本文は当時の記録として残した） |
| `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md` | §3.1 数量配分モードの節 |
| `docs/WOM_Start_Here.md` | 機能の地図の「生産配分と優先供給（三層）」の行に `tools/run_quantity_allocation.py` |

## 2. §A の確認（着手の前に読んだ結果）

**F1〜F10 はすべてコードのとおりだった**（止める理由なし）。

| # | 確かめた所 | 結果 |
|---|---|---|
| F1 | `run()` の需要 → ロット：`assign_demand_lots_from_dict(…, cpu_size=1)` | そのとおり |
| F2 | `write_demand_for_allocation()`：`derive_cost_blocks()` を最初に呼ぶ。地域 × 週の重みを全 SKU の行で作り、その地域・週の各行に同じ数量を入れる | そのとおり（2 SKU が同じ地域なら二重） |
| F3 | `run()` は計画の後に `_run_ppc()` を無条件に呼ぶ | そのとおり |
| F4・F10 | 表2：leaf_out × SKU ごとに S の Lot_ID を `_actual_ship` の**最初の**出荷週と照合、`check` は分類の合計との差。製品の小計（`Σ（製品）`）・モデル合計の行がある | そのとおり |
| F5 | `attach_realized()`：`realized.allocation` は leaf_out の S の比率、`unmet_lots` は leaf_out の毎週の CO の合計 | そのとおり |
| F6 | ID は `A\d+`（`_ID_RE`）、保存先 `output/planning_state/<case>/` | そのとおり |
| F7 | 能力の層の `unallocated`：「要求週までに内部の計画へ配置できなかった量」で、市場の注文残として残る | そのとおり |
| F8 | Lot_ID の連番は (sku_id, region, week) ごとに 1 から | そのとおり |
| F9 | `materialize_warmup()` は渡した CSV の最初の非ゼロ需要週を基準にし、その前の行を落として作り直す（需要・能力・操業カレンダー、モデルのフォルダを書き換える） | そのとおり。**合成のモデルで再現**：先頭 3 週の需要を未配分にして、修正前の経路（`warmup_real_start` なし）で回すと、計画が 2026-W51 × 15 週 → 2027-W01 × 12 週に動き、W01 の能力 7 の行が消えた（T12 は修正後の経路で、期間・能力の CSV が変わらないことを確かめる） |

**依頼書に書かれていなかった点（実装で扱った）**：表2 の `leaf` 列は leaf_out の**ノード名**で、配分の鍵の `region`（需要 CSV の `region`＝leaf_out の `region` 列）とは**同じとは限らない**（Cookie：ノード名 `Retail_JP_CVS`、region `CVS`）。道具は leaf_out の `node_id`（`OUT:leaf_out:<region>:<製品>`）から region を読んで対応させた。化粧品・合成のモデルは同じ値なので、結果には影響していない。

## 3. 実装

### 3.1 C.1 数量のハンドオフ

- 読むのは需要 CSV と配分のファイルだけ（`derive_cost_blocks` を呼ばない）。
- 鍵 (sku_id, region) の行ごとに、週の数量に比例して `alloc_lots` を `_largest_remainder()` で配る（需要 0 の行は 0 のまま。同じ鍵・同じ週の行が複数あっても行ごとに配る）。`alloc_lots` ＝ ① の鍵は行の文字列を**そのまま**写す。列・行の順は元のまま（需要 CSV の列をすべて残す）。
- 止める条件（B の 1〜3）は、該当する鍵・行をすべて並べて一度に `QuantityAllocationError` で知らせ、何も書かない。
- 書いた後に読み直し、鍵ごとの ② が `alloc_lots` と一致し、行数が元と同じことを確かめる。

### 3.2 C.2 `run()` の引数

- `ppc=False`：`_run_ppc()` を呼ばず、`"ppc": {"status": "未評価", "reason": "quantity allocation mode"}`。
- `warmup_real_start`：`materialize_warmup()` の基準の週を固定する。配分後の需要が全部 0 でも、この週で助走行を作る（`first_nonzero_demand_week` は None になるため）。
- 既定（`ppc=True`・`warmup_real_start=None`）の経路は変えていない（golden は §4 のとおり）。

### 3.3 C.3 `tools/run_quantity_allocation.py`

- **identity でなければ計画の前に止める**（診断を書いて終了コード 1、需要 CSV も作らない）。
- **期間と能力の固定**：元の需要 CSV で warmup を materialize（通常の実行と同じ）→ その基準の週・開始週・終了週・週数と、`capacity_plan.csv`・`operating_calendar.csv` の sha256 を記録 → 生成した CSV で `run(ppc=False, warmup_real_start=<基準の週>)` → `period` と hash を照合。
- **生成する需要 CSV の名前**は、次に使う予定の `Q<nn>` で `demand_forecast_Q<nn>.csv`。不整合のときは消すので、Q の番号は使われない（T15）。
- **表2 の鍵の集合**：表2 は木のすべての leaf_out の行を持ち、需要の無い leaf_out も 0 の行で出る。一方、配分のファイルは需要 0 の鍵を省いてよい（B の 2）。そのため照合は「表2 の明細の鍵 ⊇ 需要 CSV の鍵」、かつ「需要 CSV に無い表2 の鍵は demand が 0」とした（依頼書の字面の「配分のファイルの鍵の集合と一致」より、需要 CSV の鍵を基準にした）。
- 不整合の検査は依頼書 C.3 の 4 のすべて（identity・鍵の集合・②観測＝②・`check`・表1 の NG と `dup_supply_ids`・leaf_out の二重出荷・①＝②＋③・期間と能力の固定）。結果は検査ごとに `ok` と内容を診断の JSON に書く。
- 状態の JSON は依頼書 C.3 の 6 のとおり（`mode`・`allocation_id`・配分の写し・`period`・`unit`・`cpu_size`・`valuation: "未評価"`・`quantities`〔`by_key`・`by_sku`・`total`、`q1_original`〜`q5_backlog_end`、`q4_delivered` の内訳〕・`observed_at`・`judged_at`・`unallocated_treatment`・`state: "plan_computed"`・`outcome`）。`evidence` に commit・需要 CSV の名前・能力の hash・方式・プラグイン・`ppc` の返り値・PPC の出力フォルダを作らなかったこと（`ppc_output_created: false`）を入れた。利益・売上・原価のキーは無い。
- 表2・表1 の CSV は `Q<nn>_flow_check/` に残す（状態の隣）。

### 3.4 C.4 比率の経路の二重計上

`write_demand_for_allocation()` は、配分の対象の地域に **2 つ以上の `sku_id` の行**（需要 0 の行を含む。0 の行にもその地域・週の数量が入るため）があると `ValueError`（地域と SKU を並べる）。**既存のテスト・サンプルモデルでこの検査に当たるものは無かった**（full の結果、§4）。

### 3.5 C.5 名前の置き換え

- `realized.unmet_lots` → `realized.backlog_lot_weeks`（新しい記録は新しい名前）。`load()` は `unmet_lots` だけがあれば `backlog_lot_weeks` として読み（値をそのまま）、両方あれば新しい名前を使う。JSON のファイルは書き換えない（T16）。既存の `output/planning_state/soysauce-jpy-2027-alloc/A02・A04・A06.json` は旧い名前のまま。
- 画面・CLI の語：「未充足 X lot」（lot × 週の値を lot と表示していた）→「注文残 延べ X lot・週」（`s3_run.py`・`s3_view_model.py`・`run_planning_loop.py`）。

`grep -rn unmet_lots`（変更後、`output/` を除く。`.py`・`.md`）：

```
requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.1.md:22   （Q05：意味を「lot × 週」と正しく書いている。注記不要）
requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md:30   （同上）
requests/Phase7a_Addendum_to_CodeKun.md:118               "unmet_lots": 0,           → 末尾 264 行に訂正の注記
requests/Phase7_RequestLetter_to_CodeKun.md:114, 292      → 末尾 338 行に訂正の注記
requests/Phase8_DesignMD_CockpitGUI.md:85, 96, 161, 535   → 末尾 771 行に訂正の注記
requests/RequestLetter_QuantityAllocationMode_to_CodeKun.md:36, 124, 127, 128, 153, 183（本依頼書）
tests/test_quantity_allocation.py:303, 308, 310, 313, 315 （T16：旧い名前の読み込みの互換）
wom/planning_state/__init__.py:131  _REALIZED_RENAMES = {"unmet_lots": "backlog_lot_weeks"}
wom/planning_state/__init__.py:332  （コメント：旧い名前の説明）
```

**置き換えなかった名前の一覧**（依頼書のとおり、置き換えるかは大杉さんが次に決める）：

`feasible_plan`（`.py`、12 か所）：

```
tests/test_planning_state.py:183, 217
tools/run_planning_loop.py:28, 222
wom/cockpit/frame.py:15
wom/cockpit/s3_view_model.py:31, 38
wom/cockpit/state_header.py:30      _STATE_LABEL_JA = {"pre_plan": "Pre-Plan", "feasible_plan": "Feasible Plan"}
wom/planning_state/__init__.py:7, 21, 283, 390
```

`realized.allocation`（要求 S の比率）を読む・作る所（`.py`、7 か所）：

```
tests/test_planning_state.py:222
tools/run_planning_loop.py:256
wom/cockpit/s3_view_model.py:97
wom/planning_state/__init__.py:295, 308, 317, 380
```

数量配分モードの記録は `state: "plan_computed"` で、`feasible_plan`・`realized` を使っていない。

## 4. テストの結果

| 段 | 結果 |
|---|---|
| 新規 `tests/test_quantity_allocation.py` | **19 passed**（4.3 秒） |
| `quick_check --smoke` | 505 passed（73 秒） |
| `quick_check --full` | **973 passed, 3 skipped, failed 0**、1,028 秒（17 分 2 秒）。前回の full 954 件＋新規 19 件 |

golden（通常 15 件・legacy 3 件）：**すべて緑（不変、再生成なし）**。full の後の `git status` で `data/sample/` に変更なし（既定の `run()` がモデルのファイルへ書く内容は変わっていない）。C.4 の検査に当たった既存のテストは無かった。

§D の対応：

| # | テスト | 確かめたこと |
|---|---|---|
| T01・T02 | `test_t01_t02_…` | 金額のファイル無し、`_run_ppc` を呼ぶと失敗する差し替えでも最後まで動く。`valuation` が `"未評価"`、利益・売上・原価・`unallocated` のキーが無い、`ppc_output_created` が false |
| T03 | `test_t03_…` | 鍵ごとに ①＝②＋③、②＝④＋⑤。2 SKU が同じ地域名でも ② が `alloc_lots` のまま（二重にならない） |
| T04 | `test_t04_…` | `alloc_lots`＝① の鍵の行は元と同じ文字列 |
| T05 | `test_t05_…` | 能力 10：⑤＝0、`outcome` が全量引渡し |
| T06 | `test_t06_…` | 能力 2：⑤＞0 で止まらずに保存、表2 の `check` はすべて 0 |
| T07 | `test_t07_…`（5 件） | 止める条件 1〜3、整数でない・負・数値でない値と重複がまとめて出る。どれも需要 CSV・状態を書かない |
| T08・T15 | `test_t08_t15_…`、`test_t08_cli_…` | 生成した CSV の 1 行を書き換えて計画すると、「入力・記録の不整合」で `Q02.json` を作らず診断を書く（`q2_observed_equals_handoff` が NG）。生成した CSV も消える。次の正常な実行が Q02（番号が飛ばない）。CLI は終了コード 1 |
| T09 | `test_t09_…` | soysauce-jpy-2027-alloc の写しに別の SKU の行を 1 行足すと、`write_demand_for_allocation()` が地域と SKU を並べて止まり、CSV を書かない（`ga_*` が要るため、合成のモデルではなくサンプルの写しで確かめた） |
| T10 | `test_t10_…` | 手で作った木：最終週の CO にあり最終週に出荷された lot は遅配（⑤ に入らない）、最終週に要求され出荷されない lot は ⑤ に入る |
| T11 | `test_t11_…` | 能力の層 ON（`capacity_layer_config.csv` の窓 3 週）で動く。③ は配分のファイルだけで決まり（A/X の 4）、②＝④＋⑤。実測（同じ設定）：能力の層の `unallocated` A 8・B 12、道具の ⑤ A 8・B 12、③ A 4・B 0。この例では ⑤ と `unallocated` が同じ値になったが、テストはそれを仮定していない |
| T12・T13 | `test_t12_t13_…` | 先頭 3 週だけに需要のある鍵を未配分にしても、全量を未配分にしても、`period`（開始・終了・週数・基準の週）と能力の CSV が配分しない場合と同じ（W01 の能力 7 の行も残る）。全量未配分は ③＝①、④＝⑤＝0 で保存 |
| T14 | `test_t14_…` | legacy のモデルは計画の前に止まり、需要 CSV・状態を作らない |
| T16 | `test_t16_…` | `unmet_lots` だけの JSON を `load()` で読むと `backlog_lot_weeks` に値が入る。両方あれば新しい名前。ファイルは書き換わらない |

## 5. 化粧品での確かめ（§E）

`output/bsseaf_cosmetics/C3a` を `output/bsseaf_cosmetics/C3a_qty` に写し、全ての鍵で `alloc_lots`＝① の配分のファイルで回した（`--out-dir output/bsseaf_cosmetics/planning_state`）。元の C3a は変えていない。

**V09**：金額なしで最後まで動き、`Q01.json` を保存した（終了コード 0）。①〜⑤ は C3a の Flow Check 表2（変更課題①②③の報告書）と一致した。

| | ① | ② | ③ | ④（当週／前倒し／遅配） | ⑤ |
|---|---|---|---|---|---|
| COS_Serum（SG 3 チャネル） | 1,898 | 1,898 | 0 | 1,898（1,898／0／0） | 0 |
| COS_Serum TH_Distributor | 390 | 390 | 0 | 286（286／0／0） | **104** |
| COS_Cream（SG 3 チャネル） | 1,469 | 1,469 | 0 | 1,469（1,469／0／0） | 0 |
| COS_Cream TH_Distributor | 299 | 299 | 0 | 211（211／0／0） | **88** |
| 全体 | **4,056** | 4,056 | **0** | **3,864** | **192** |

**V10**：`valuation` は `"未評価"`、`state` は `"plan_computed"`、`outcome` は「配分後の未充足あり」。`evidence.ppc` は `{"status": "未評価", "reason": "quantity allocation mode"}`、`ppc_output_created` は false で、出力先に PPC のフォルダ・ファイルは 0 件だった。期間は 2026-W37〜2029-W52（173 週、基準の週 2027-W01）。

## 6. 止める理由と申し送り

**止める理由**：無し（§A の事実はすべてコードのとおり、golden は §4、C.4 の検査に当たる既存のテスト・モデルは無し、V09 は一致）。

**申し送り**：

1. **表2 の `leaf` はノード名**（§2）。配分の鍵（region）との対応は leaf_out の `node_id` から読んでいる。region とノード名が違うモデル（Cookie）で使うときも動くが、表2 を人が読むときは列の値が鍵と違って見える。
2. **鍵の集合の照合を「需要 CSV の鍵」基準にした**（§3.3）。依頼書の字面とは違うが、需要 0 の鍵を配分のファイルから省いてよい規則（B の 2）と、表2 が需要の無い leaf_out も出すことに合わせた。
3. **生成した需要 CSV はモデルのフォルダに残る**（`demand_forecast_Q<nn>.csv`。比率の経路と同じ）。warmup の materialize も、元の需要 CSV・能力の CSV を通常の実行と同じく書き換える（作業用の写しで使う前提。依頼書 §E・三層設計 MD §3 のとおり）。
4. **⑤ と能力の層の `unallocated`**：T11 の例では同じ値（A 8・B 12）になったが、意味は別（F7）。能力の層で配置できた lot が Forward で届かない場合は一致しない。
5. **`feasible_plan`・`realized.allocation` の名前**（§3.5 の一覧）は未変更。cockpit の画面（`state_header.py` の「Feasible Plan」）が使う。

## 7. 文書

- 三層設計 MD v0.2 に §3.1「数量配分モード」を足した。
- Start Here の機能の地図の行に `tools/run_quantity_allocation.py` を足した。Start Here の R 表・§7 への追記は、報告書を見て Claude君が行う。
