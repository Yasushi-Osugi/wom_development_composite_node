# Phase 7 実装 Request Letter — Planning State と層間ハンドオフ（GUI なし）

**宛先**: Code君
**作成日**: 2026年9月12日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（Phase 8 経営コックピットの前提。GUI を作る前にデータ契約を固める）
**ブランチ**: `wom-v1r4m0`
**設計正典**: `requests/Phase8_DesignMD_CockpitGUI.md` §2 / §8.1、`requests/Roadmap_WOM_Cockpit_ThreeLayer.md` Phase 7
**前提**: Phase 6 完了（`d42972f`、402件全PASS）

---

## 概要

WOM の三層（配分 → 配置 → 実行 → 損益評価）は、**いま層と層がデータで繋がっていない。** 第1層（A系統）で選んだ配分は第2層（Planning Engine）に自動では渡らず、第3層を通った結果も第1層に戻ってこない。

本 Phase で、その2本の矢印を実装し、**閉ループを headless で1周させる**。**GUI は一切作らない。**

```
  [第1層] A系統          [第2層] Backward      [第3層] Forward → PPC
   利益地形図・配分  ──①──▶  配置              ──────────▶  損益評価
        ▲                                                        │
        └──────────────────── ② ─────────────────────────────────┘

  ① allocation_id → demand_forecast_<id>.csv        （成果物2）
  ② PPC の実績 → Planning State の realized         （成果物3）
```

**この Phase が終わった時点で、GUI がなくても三層を CLI で行き来できる。** コックピットは、それを画面にするだけになる。

### 対象ファイル

| ファイル | 扱い |
|---|---|
| `wom/planning_state/` | **新規パッケージ**。スキーマ・生成・読込・書込 |
| `wom/allocation/handoff.py` | **新規**。配分 → `demand_forecast_<id>.csv` の生成 |
| `tools/run_planning_loop.py` | **新規**。S1〜S4 を CLI で1周する |
| `tools/run_headless_from_folder.py` | **引数追加のみ**（`demand_file` / `planning_state`）。既定の返却は1バイトも変えない |
| `wom/engine/warmup.py` | `_DEMAND` 定数を引数化（下記 V2.4）。既定は従来どおり |
| 上記以外 | **無変更**（禁足コア6ファイル・A系統・PPC・GUI） |

---

## ⚠️ 絶対制約

- **C1**: matplotlib のみ（本 Phase では描画なし）。**C2**: 新規依存なし（標準ライブラリ + 既存の pandas のみ）
- **C3**: （描画なし）。**C4**: （描画なし）
- **C5**: 返却は Dict / JSON。**C6**: 禁足コア6ファイル（`backward_planner.py` / `forward_planner.py` / `plan_copy.py` / `plan_node.py` / `sc_tree.py` / `push_pull.py`）に一切触れない
- **C7**: **乱数を使わない。** JSON のキー順・リストの順序は決定的であること
- **C8**: **golden 13ケースが1バイトも変わらないこと。** `run_headless_from_folder.run()` の既定の返却（`ppc` / `psi` / `forward` / `backward`）に**フィールドを足さない**。追加情報は opt-in の別キーに載せる（V2.3）
- **C9**: 既存ケース（`allocation_id` を指定しない従来の実行）が**完全に従来どおり**動くこと。後方互換の絶対条件

---

## V1: `wom/planning_state/` — 計画案の履歴書

### V1.1 スキーマ

設計書 §2.3 のとおり。`output/planning_state/<case>/<allocation_id>.json`。

```json
{
  "allocation_id": "A03",
  "case": "soysauce-jpy-2027-alloc",
  "scenario_id": "s1_base",
  "mode": "cockpit",
  "state": "pre_plan",
  "created": "2026-09-12T10:00:00",

  "allocation": {"JP": 0.10, "US": 0.45, "EU": 0.45},
  "profit_levels": { … },
  "reversal": { … },
  "placement": { … },
  "realized": null
}
```

### V1.2 `profit_levels` — **基準は `P_opt` である（Phase 6 の結論を反映）**

設計書 §2.3 は Phase 6 より前に書かれており、`gap_vs_plan_pct` の分母を `P_grid` にしていた。**これは誤りである。本書で訂正する。**

Phase 6-3 で実測したとおり、**格子の最良点 `P_grid` は解像度と次元に依存し、`P_greedy` との大小すら決まっていない**。物差しには使えない。使えるのは格子を経由しない `P_opt`（`true_continuous_optimum()`）である。

```json
"profit_levels": {
  "P_opt":     135529822.5,          // 基準。true_continuous_optimum()
  "P_greedy":  135529822.5,          // build_allocation_merit_order()
  "P_grid":    132133072.5,          // best_point(scan_surface())
  "P_hier":    null,                 // N>=4 のとき scan_hierarchical()。N<=3 は null
  "gap_amt":                  3396750.0,
  "expected_gap":             3396750.0,
  "structural_residual":            0.0,
  "structural_optimality_gap":      0.0,
  "grid_resolution_error":    3396750.0,
  "residual_coverage":             null,
  "hierarchy_gap":                 null,   // N>=4 のとき P_opt - P_hier
  "n_markets": 3,
  "source": "P_opt"                  // この配分をどの水準から採ったか
}
```

- **`compare_with_grid()` と `hierarchy_gap()` の返却をそのまま載せる。** 値をここで再計算しない（式の二重定義を作らない）
- **`source`** は `"P_opt" | "P_greedy" | "P_grid" | "P_hier" | "manual"`。「どの水準を選んで意思入れしたか」が後から分かるようにする。**S1 の推奨配分は `P_opt` 由来を既定とする**（Phase 6-1 で計算できるようになったので、格子の最良点を推奨する理由はもう無い）

### V1.3 `realized` の7項目

設計書 §2.2 のとおり（大杉さん確認済み）。ただし `gap_vs_plan_pct` の定義を V1.2 に合わせて訂正する。

| フィールド | 定義 | 出どころ（**実測で確認済み**） |
|---|---|---|
| `allocation` | 実際に供給できた配分比率 | `psi[prod][<leaf_out>]["S"]` を市場ごとに合計し、総和で正規化 |
| `profit_ppc` | PPC 台帳の実現利益 | `ppc["gross_profit_base"]` |
| `gap_vs_plan_pct` | **`(profit_ppc − P_opt) / P_opt × 100`** | 計算。**`P_grid` ではない**（V1.2） |
| `unmet_lots` | 未充足（CO）の合計 | `psi[prod][<leaf_out>]["CO"]` の合計 |
| `capacity_violation_weeks` | cap_hard/cap_soft 超過の週 | **現状スナップショットに無い。V2.3 で足す** |
| `peak_inventory_weeks` | 在庫が安全在庫の N 倍を超えた週 | **同上。V2.3 で足す** |
| `issues` | severity 付きの問題一覧 | `ManagementAnalysisResult.issues` |

**`capacity_violation_weeks` と `peak_inventory_weeks` は、いまのスナップショットからは取れない。** 確認した結果:

```
forward.cap_soft_violation_count   件数だけ（週の内訳が無い）
psi[prod][node]                    P/S/I/CO の合計と I_max、週次系列は md5 のみ
```

週リストが必要なので V2.3 で opt-in の追加経路を作る。**golden を変えずに**。

**`peak_inventory_weeks` の閾値**: 「安全在庫の N 倍」の N は **2.0** を既定とし、引数で変更可能にする。根拠は薄いので、実ケースを見てから調整する前提で、**定数を1箇所に置いて名前を付ける**こと（`PEAK_INVENTORY_MULTIPLE = 2.0`）。

### V1.4 API

```python
# wom/planning_state/__init__.py
def new_state(case, scenario_id, allocation, profit_levels, *,
              allocation_id=None, mode="cockpit", reversal=None) -> dict
def save(state, out_dir="output/planning_state") -> str     # 返り値はパス
def load(case, allocation_id, out_dir="output/planning_state") -> dict
def list_states(case, out_dir="output/planning_state") -> List[dict]   # S5 の一覧用
def attach_placement(state, *, earliest_start_week, backward_envelope_violations) -> dict
def attach_realized(state, snapshot, mgmt_result=None) -> dict          # state を feasible_plan に
```

- `allocation_id` は **`A01`, `A02`, … の連番**。`out_dir` の既存ファイルを見て次を決める。**乱数・UUID は使わない（C7）**
- `attach_realized()` が `state["state"]` を `"pre_plan"` → `"feasible_plan"` に変える。**これが「地形図を見ていたときの計画」と「Weekly PSI を通過した後の計画」が別物であることを、データ自身に語らせる仕掛けである**
- JSON は `ensure_ascii=False` / `indent=2` / **`sort_keys=False`**（スキーマの並び順を保つ。読む人のため）

---

## V2: 第1層 → 第2層のハンドオフ

### V2.1 `wom/allocation/handoff.py`

```python
def write_demand_for_allocation(model_dir, allocation, allocation_id, *,
                                cap_wk, weeks=104, uom=None,
                                out_path=None) -> dict:
    """配分比率から demand_forecast_<allocation_id>.csv を生成する。

    返却: {"path": str, "per_market": {market: qty}, "per_region": {region: qty},
           "scale": {market: float}, "total_before": int, "total_after": int}
    """
```

**これが note 記事で「生産配分の確定の意思入れ」と呼んだ操作の実体である。** Planning Engine は生成された CSV を通常どおり読むだけなので、**禁足コアは無変更**。

### V2.2 スケーリングの規則（**ここを曖昧にしない**）

1. **市場ごとの目標数量** `q[m] = min(x[m] × cap_wk × weeks, demand[m])`
   `evaluate_point()` と同じ式。**配分は需要を増やさない**（`q[m] ≤ demand[m]` が常に成り立つ）
2. **市場 → 地域** は `ga_market_aggregation.csv` の `internal_ratio` で按分する（固定比率・仕様書 v0r6 §2.4 の3市場モード）
3. **地域 → 週** は**元の週次形状に比例**させる。季節性を壊さない
4. **端数は最大剰余法（largest remainder）で配る。** 単純な四捨五入では市場合計が `q[m]` と一致しない。**合計が1 lot もずれないこと**
5. **需要ゼロの週はゼロのまま**にする。warmup の助走行（`quantity=0`）を潰さない
6. 列は元と同一（`sku_id, region, week, quantity`）、**行順も元と同一**にする（差分が読めるように）

**検算**: `sum(per_region.values()) == sum(per_market.values())` かつ `total_after ≤ total_before`。**破れたら書き出さずに `ValueError`。**

### V2.3 `run_headless_from_folder.run()` に引数を2つ足す

```python
def run(model_dir, plugins_spec="safe", output_ppc_dir="output/ppc", verbose=True,
        demand_file: str = "demand_forecast.csv",       # ← 追加1
        planning_state: bool = False) -> dict:          # ← 追加2
```

**`demand_file`**: 需要 CSV のファイル名。既定は従来どおり。`"demand_forecast_A03.csv"` を渡せばそれを読む。

**`planning_state`**: `True` のときだけ、返却に **`"planning_state_extras"`** キーを足す。

```python
"planning_state_extras": {
    "cap_hard_violation_weeks": ["2027-W32", …],    # Forward の cap_hard seal が出た週
    "cap_soft_violation_weeks": ["2027-W32", …],    # Forward の cap_soft 違反の週
    "backward_envelope_weeks":  [...],              # Backward の envelope 違反の週
    "inventory_peak_weeks": {product: {node: ["2027-W10", …]}},
    "leaf_out_S":  {product: {node: total_S}},      # 市場ごとの実供給
    "leaf_out_CO": {product: {node: total_CO}},
}
```

**`planning_state=False`（既定）のとき、返却は現行と1バイトも同一であること（C8）。** golden 13ケースはこの経路を通らない。

週リストは `_fres.cap_soft_violations` / `_bres.cap_soft_envelope_violations` の要素と、`nd.psi4supply` の週次 I 系列から作る。**`_psi_signature()` は変更しない**（golden が依存している）。別関数を足すこと。

### V2.4 `warmup.py` の `_DEMAND` 定数

```python
_DEMAND = "demand_forecast.csv"       # ← ファイル名が1箇所に埋まっている
```

`materialize_warmup(model_dir, demand_file="demand_forecast.csv")` と**引数化**する。既定は従来どおりなので、既存呼び出しは無変更で通る。

**これを忘れると、`demand_forecast_A03.csv` を読ませているのに warmup だけ元ファイルを見る**、という噛み合わせのズレが起きる。今回の Phase 6 で3回踏んだ「2箇所に分かれたものが片方だけ更新される」形である。

---

## V3: `tools/run_planning_loop.py` — 閉ループを1コマンドで

```
python -m tools.run_planning_loop --model-dir data/sample/soysauce-jpy-2027-alloc \
       --scenario s1_base --cap-wk 800 --allocation 0.10,0.45,0.45
python -m tools.run_planning_loop --model-dir <case> --scenario s1_base --cap-wk 800 --from P_opt
```

処理順:

1. `derive_cost_blocks()` → `build_allocation_merit_order()` / `true_continuous_optimum()` / `scan_surface()`（N≥4 なら `scan_hierarchical()`）
2. `--allocation` 明示、または `--from {P_opt|P_greedy|P_grid|P_hier}` でその水準の配分を採る（既定 **`P_opt`**）
3. `new_state()` → `save()`（`state = "pre_plan"`）
4. `write_demand_for_allocation()` → `demand_forecast_<id>.csv`
5. `run(model_dir, demand_file=…, planning_state=True)`
6. `attach_placement()` / `attach_realized()` → `save()`（`state = "feasible_plan"`）
7. 結論を**日本語1行**で標準出力に出す

```
[planning_loop] A01 soysauce-jpy-2027-alloc / s1_base
  計画   JP 10 / US 45 / EU 45    P_opt 135,529,822 円
  実績   JP 12 / US 43 / EU 45    PPC   128,900,000 円   計画比 −4.9%
  未充足 240 lot   能力超過 4週（W32〜W35）   在庫ピーク 2週
  -> output/planning_state/soysauce-jpy-2027-alloc/A01.json
```

**結論行は日本語とする**（大杉さん判断・2026-09-12）。`matplotlib` ではなく標準出力／tkinter Label なので、図中テキスト英語の制約（豆腐化防止）とは衝突しない。

---

## V4: テスト仕様（新規8件）

**新規ファイル `tests/test_planning_state.py`**。

### V4.1 `test_golden_unchanged_by_default`（**最重要**）

`run(model_dir)` の返却が **`planning_state` 引数の追加前と完全に一致**すること。soysauce と Cookie の2ケースで、`ppc` / `psi` / `forward` / `backward` を **golden JSON と `==` で厳密比較**。`planning_state_extras` キーが**存在しないこと**も assert する。

### V4.2 `test_allocation_conserves_demand`

`write_demand_for_allocation()` が需要を増やさないこと。

```python
assert r["total_after"] <= r["total_before"]
for m, q in r["per_market"].items():
    assert q <= demand[m] + 1e-9
```

### V4.3 `test_allocation_rounding_is_exact`（**端数の落とし穴**）

最大剰余法で市場合計が**1 lot もずれない**こと。`x = (0.10, 0.45, 0.45)` と、割り切れない `x = (1/3, 1/3, 1/3)` の両方で。

```python
for m in markets:
    assert sum(週次の quantity for m の全 region) == round(r["per_market"][m])
```

### V4.4 `test_zero_weeks_preserved`

元の `quantity == 0` の週が、生成後も 0 のままであること（warmup の助走行を潰さない）。行数・行順が元と同一であることも。

### V4.5 `test_state_transitions`

`new_state()` → `state == "pre_plan"` かつ `realized is None`。`attach_realized()` 後に `state == "feasible_plan"` かつ `realized` の7項目が埋まる。`allocation_id` が `A01` → `A02` と連番で増えること。

### V4.6 `test_gap_vs_plan_uses_P_opt`（**V1.2 の訂正が入っていることの確認**）

`gap_vs_plan_pct` の分母が `P_opt` であること。`P_grid` で割った値と**一致しない**ことを、両者が異なるケース（soysauce `s1_base`：`P_opt` 135,529,822.5 / `P_grid` 132,133,072.5）で確認する。

### V4.7 `test_planning_loop_closes`（**この Phase の合否**）

`run_planning_loop` を soysauce `s1_base` / `cap_wk=800` / 格子最適点 `(0.10, 0.45, 0.45)` で1周させ、

- `state == "feasible_plan"`
- `realized.allocation` の各市場が**需要天井の範囲に収まる**
- `realized.unmet_lots` が 0 以上
- JSON が `output/planning_state/<case>/A01.json` に書かれている

**回帰値は本書で指定しない。Code君が測った値を報告し、それを次の正典とする。**

### V4.8 `test_warmup_respects_demand_file`

`materialize_warmup(model_dir, demand_file="demand_forecast_A01.csv")` が、元ファイルではなく指定ファイルを見ること（V2.4）。

---

## 成功基準

- [ ] **golden 13ケースが1バイトも変わらない**
- [ ] 既定引数のままの `run()` の返却が現行と完全一致
- [ ] 配分が需要を増やさない。端数が1 lot もずれない
- [ ] `pre_plan` → `feasible_plan` の遷移が起き、`realized` の7項目が埋まる
- [ ] `gap_vs_plan_pct` の分母が `P_opt`
- [ ] `run_planning_loop` が soysauce で1周し、結論を日本語1行で出す
- [ ] Phase 4/5/6 の全回帰値が不変
- [ ] **410件全PASS**（既存402 + 新規8）

---

## 実装者への申し送り

**1. 設計書 §2.3 の `gap_vs_plan_pct` は誤りである（V1.2）。**
分母を `P_grid` にしていたが、Phase 6-3 で「格子の最良点は物差しに使えない」ことが実測で分かった。**本書が設計書を上書きする。** 設計書側は Phase 8 の Request Letter を書くときに rev.2 で直す。

**2. `demand_file` の分岐が2箇所あることに注意（V2.4）。**
`run_headless_from_folder` と `warmup.py` の両方がファイル名を持っている。片方だけ直すと、需要は差し替わったのに warmup だけ元を見る、という状態になる。**Phase 6 で3回踏んだ形と同じ**なので、先に両方を引数化してから配線すること。

**3. `_psi_signature()` を変更しないこと。**
golden 13ケースがこの出力に依存している。週リストが要るなら**別関数**を足し、`planning_state=True` のときだけ呼ぶ。

**4. 端数は最大剰余法で（V2.3 の 4）。**
四捨五入で配ると市場合計が目標とずれる。「配分は需要を増やさない」という不変条件が、丸めのせいで1 lot 破れる——という形の壊れ方をする。**テストで固定する。**

**5. 回帰値は本書に書いていない。**
V4.7 の1周の結果は実装で決まる。**測って報告してもらい、それを正典にする。** こちらが先に値を書いて合わせにいく順序を作らない（Phase 6 でこの運用が効いた）。

**6. GUI は作らない。**
本 Phase の成果物は JSON とコマンドだけである。画面は Phase 8。**「ついでに画面も」をやらないこと**——データ契約が固まる前に画面を作ると、画面ごとに違う形のデータを持ち回ることになる。
