# Phase 7a 追加指示 — 計画と実績の差を分解する／未配線の3点

**宛先**: Code君
**作成日**: 2026年9月12日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（Phase 8 の結論行がこの数字を使う）
**ブランチ**: `wom-v1r4m0`
**先行**: `requests/Phase7_RequestLetter_to_CodeKun.md`（本書が V1.3 を上書きする）
**前提**: Phase 7 完了（`2a47c86`、412件全PASS）

---

## 0. 何が起きていたか — `gap_vs_plan_pct = +20.3%`

実装は指示どおりだった。**指示が間違っていた。**

`run_planning_loop` を soysauce `s1_base` / `cap_wk=800` / 配分 `(0.10, 0.45, 0.45)` で1周させると、実績が計画を **20.3% 上回る**。実績が計画を2割上回るはずがない。原因は2つあり、**どちらも Claude君の設計ミス**である。

### (1) 分母の取り違え

`gap_vs_plan_pct` の分母を `P_opt`（135,529,822.5）にしていた。しかし**実際に選んだ配分は格子点**で、その A系統評価は `P_grid`（132,133,072.5）である。「**この配分は最善からどれだけ劣るか**」（`P_opt` との差）と「**計画どおりに実行できたか**」（実績との差）という別の問いを、1つの数字に混ぜていた。

### (2) 2つの層が、違う為替を見ている（**こちらが本体**）

実測した。

```
A系統が使う為替   USD 150.00 / EUR 162.00          ← Scenario(fx_usd=150) の1点
PPC が使う為替    USD 平均 174.28（150 → 200）     ← ppc_fx_rate.csv の週次パス
                  EUR 平均 188.22（162 → 216）
```

`soysauce-jpy-2027-alloc` は**期間を通じて円安が進む**モデルである。**A系統の利益地形図は「為替が基準値のまま」という前提の地図**であり、PPC は与えられた為替パス上の実現値である。引き算すると「計画と実績の差」ではなく「**為替前提の差**」が出る。

A系統を PPC の平均為替で再評価すると、こうなる（実測）。

| | 売上 | 原価 | 粗利 |
|---|---:|---:|---:|
| A系統 @ fx=150 | 459,542,100 | 327,409,028 | **132,133,072** |
| A系統 @ fx=174.28 | 528,755,202 | 360,147,241 | 168,607,961 |
| PPC 台帳 | 531,159,148 | 368,101,737 | **163,057,411** |

**売上は 0.45% まで一致する。** 30.9M の差は次のように分解できる。

```
P_plan(fx=150)      132,133,072      地図の前提
  ＋ 為替前提の差    +36,474,889      基準 150円 → 実際の平均 174.28円
P_plan(fx=174.28)   168,607,961
  ＋ 残差             −5,550,550      原価モデルの粒度差
P_ppc               163,057,411      実現利益
```

**これは Phase 4/5 で `gap_amt` を `expected_gap` と `structural_residual` に分けたのと同じ構図である。** 単一の比率にするのをやめ、**分解して記録する**。

経営の言葉にするとこうなる——**「地形図の 1.32億 と実行結果の 1.63億 の差 3,100万円のうち、3,650万円は為替前提の違いで、残り −560万円だけが原価モデルの粒度差」**。これなら S1 の結論行に出せる。

---

## A1: `plan_eval` を新設する — 「選んだ配分を、地図の前提で評価した値」

Planning State に追加する。`profit_levels` とは役割が違う——あちらは**水準の一覧**（どれを選べたか）、こちらは**選んだ配分そのものの評価**である。

```json
"plan_eval": {
  "basis": "allocation_layer",        // 固定文字列。どの原価モデルかを明示する
  "fx_usd": 150.0,                    // 評価に使った為替（シナリオの値）
  "material_usd": 6.0,
  "profit":  132133072.5,             // evaluate_point(x)["profit"]
  "revenue": 459542100.0,
  "cost":    327409028.0,
  "lots":    78671                    // sum(evaluate_point(x)["q"].values())
}
```

`evaluate_point()` の返却をそのまま載せる。**再計算しない。**

**`profit_levels.source` が `"manual"` のときも `"P_opt"` のときも、`plan_eval` は「実際に渡した配分」を評価する。** ここが (1) の是正である。

---

## A2: `realized` を書き換える

### A2.1 `gap_vs_plan_pct` を廃止し、分解に置き換える

```json
"realized": {
  "allocation": {"JP": 0.1058, "US": 0.4471, "EU": 0.4471},

  "ppc": {
    "basis": "ppc_ledger",            // 週次の価格・FX を積み上げた台帳
    "profit":  163057410.69,
    "revenue": 531159148.0,
    "cost":    368101737.0,
    "lots":    78671,                 // PSI bridge の数量（= plan_eval.lots と一致するはず）
    "lot_records": 624                // PPC の lot レコード数。lots とは別物
  },

  "fx_effective": {                   // PPC が実際に使った為替の出荷数量加重平均
    "USD": 174.28,
    "EUR": 188.22
  },

  "plan_at_realized_fx": {            // A系統を fx_effective で再評価した値
    "profit":  168607961.0,
    "revenue": 528755202.0,
    "cost":    360147241.0
  },

  "gap_decomposition": {
    "total":          30924338.19,    // ppc.profit − plan_eval.profit
    "quantity":              0.0,     // 数量差に由来（lots が一致すれば 0）
    "fx_assumption":  36474888.5,     // plan_at_realized_fx − plan_eval
    "residual":       -5550550.31,    // ppc − plan_at_realized_fx
    "residual_revenue": 2403946.0,    // 売上ベースの残差
    "residual_cost":    7954496.0     // 原価ベースの残差
  },

  "unmet_lots": 0,
  "capacity_violation_weeks": [...],
  "peak_inventory_weeks": [...],
  "issues": [...]
}
```

**`gap_vs_plan_pct` キーは削除する。** null で残さない——「0% なのか未定義なのか」が読めなくなる。

### A2.2 恒等式（**テストで固定する**）

```
total == quantity + fx_assumption + residual        （誤差 ±1 円）
```

`residual` は引き算で決める（`ppc.profit − plan_at_realized_fx.profit`）ので、この恒等式は**定義上つねに成立する**。成立しなかったら、どこかで別の値を混ぜている。

### A2.3 `residual` の中身を正直に書く

`residual` は**純粋な「原価モデルの粒度差」ではない**。次の2つが混ざっている。

1. **原価モデルの粒度差**（主）— A系統は1 lot あたりの原価ブロックによる1点評価、PPC は PSI を通した実際の積み上げ
2. **為替の加重近似**（従）— `fx_effective` は加重平均の1点であり、週ごとの数量と為替の相関までは再現しない

**どちらが主かは `residual_revenue` と `residual_cost` を並べれば読める。** 実測では売上側の残差が +240万（+0.45%）、原価側が +795万（+2.2%）——**残差のほとんどは原価側にある**。つまり 1 が主で 2 は従である。

docstring にこの但し書きを残すこと。「残差＝原価モデル差」と言い切らない。

### A2.4 `fx_effective` の定義

**出荷数量加重平均**とする。

```
fx_effective[ccy] = Σ_w ( 出荷数量(w) × rate(ccy, w) ) / Σ_w 出荷数量(w)
```

- 出荷数量は **leaf_out の S 系列の週次値**。`planning_state_extras` に `leaf_out_S_weekly` を足して取り出す（現状は合計のみ）
- `rate` は `ppc_fx_rate.csv`
- **単純平均にしないこと。** 円安が進むモデルでは、出荷が後半に寄るか前半に寄るかで値が変わる

**本書の実測値（174.28 / 188.22）は単純平均である。** 数量加重にすると変わる。**Code君が測った値を報告し、それを正典とする**（本書の数値に合わせにいかないこと）。

### A2.5 数量の検算

```python
if plan_eval["lots"] != realized["ppc"]["lots"]:
    # 数量が一致しない = ハンドオフが壊れている
    gap_decomposition["quantity"] = <数量差に由来する分>
```

**現状は一致している**（78,671 / 78,671。PSI bridge のログで確認済み）。一致している限り `quantity = 0.0` でよい。**一致しない場合の扱いは本書では決めない**——そのときは止めて報告すること。数量がずれるのは、需要が能力に届かない／warmup の助走が噛んでいる等、原因を特定すべき事象である。

---

## A3: 未配線の3点

### A3.1 `reversal` が常に `{}`

`new_state()` は `reversal` 引数を受け取るが、`run_planning_loop` が渡していない。`scan_regime_grid()` から、現在のシナリオ点における**判断が反転する境界**を取って渡すこと。

```json
"reversal": {"axis": "fx_usd", "current": 150.0, "boundary": 117.0,
             "direction": "below", "flips_to": "EU>US>JP"}
```

soysauce の切替点は **117円 / 119円**（`analytics.switching_points()`・回帰テスト済み）。`boundary` は「現在地から最も近い切替点」、`flips_to` はそこを越えた先の順位ラベルとする。切替点が無ければ `{}` のままでよい。

### A3.2 `issues` が常に `[]`

`attach_realized()` は `mgmt_result` 引数を持つが、`run_planning_loop` が渡していない。`ManagementAnalysisResult` を生成して渡すこと。生成経路が headless に無いなら、**無いことを報告**してほしい（その場合は Phase 8 に送る）。

### A3.3 `placement.backward_envelope_violations` の型

スキーマは**件数（int）**だが、実装は**リスト**を返している。

```json
"placement": {"earliest_start_week": "2026-W28", "backward_envelope_violations": []}
```

**リストのほうが情報量が多いので、実装に合わせてスキーマを直す。** ただし名前を `backward_envelope_violation_weeks` に変え、**件数が要る場面では `len()` を取る**こと。`violations` という名前でリストが入っていると、件数と誤読される。

---

## A4: `run_planning_loop` の結論行

分解を出す。**日本語。**

```
[planning_loop] A01 soysauce-jpy-2027-alloc / s1_base
  計画   JP 10 / US 45 / EU 45    地図の利益 132,133,072 円（為替 150円の前提）
  実績   JP 11 / US 45 / EU 45    実現利益   163,057,411 円（為替 実効 174.3円）
  差 +30,924,338 の内訳:  為替前提 +36,474,889 ／ 原価モデル −5,550,550 ／ 数量 0
  未充足 0 lot   能力超過 4週（2027-W13, W17, 2028-W13, W17）   在庫ピーク 0週
  -> output/planning_state/soysauce-jpy-2027-alloc/A01.json
```

**「計画比 +20.3%」は出さない。** あの1行が経営者を誤読させる。

---

## A5: テスト（新規5件）

`tests/test_planning_state.py` に追記。

1. `test_plan_eval_uses_chosen_allocation` — `--allocation` を明示したとき、`plan_eval.profit` が `P_opt` ではなく**その配分の評価**になること（soysauce `(0.10,0.45,0.45)` で `132,133,072.5`、±1円）
2. `test_gap_decomposition_identity`（**最重要**）— `total == quantity + fx_assumption + residual`（±1円）
3. `test_no_gap_vs_plan_pct_key` — `realized` に `gap_vs_plan_pct` が**存在しない**こと
4. `test_fx_effective_is_quantity_weighted` — 出荷が偏る合成ケースで、単純平均と**異なる値**になること
5. `test_reversal_populated` — soysauce で `reversal.boundary` が 117.0 または 119.0 になること

**回帰値は 1 以外は本書で指定しない。** 実装で決まる値なので、測って報告してもらい、それを正典とする。

---

## 成功基準

- [ ] `plan_eval` が「選んだ配分」を評価している（`P_opt` を流用していない）
- [ ] `gap_vs_plan_pct` キーが消えている
- [ ] 分解の恒等式が ±1円で成立
- [ ] `fx_effective` が出荷数量加重
- [ ] `reversal` / `issues` が埋まる（`issues` の生成経路が無ければ報告）
- [ ] 結論行に「計画比 ○%」が出ない
- [ ] golden 13ケース・Phase 4/5/6 の全回帰値が不変
- [ ] **417件全PASS**（既存412 + 新規5）

---

## 実装者への申し送り

**1. これは Claude君の設計ミスの是正であって、実装のやり直しではない。**
Phase 7 の実装は指示どおりだった。`gap_vs_plan_pct` を「単一の比率」として定義したのが誤りである。

**2. 2つの層が違う為替を見ていることは、バグではない。**
A系統の利益地形図は「為替が基準値のまま」という前提の地図である。Regime Map（為替×関税）は、まさにその前提を動かして見るための道具だった。PPC は与えられた為替パス上の実現値である。**どちらも正しく、比較するには前提を揃える必要がある**——それが `plan_at_realized_fx` である。

**3. 「残差＝原価モデル差」と言い切らないこと（A2.3）。**
為替の加重近似も混ざっている。`residual_revenue` と `residual_cost` を並べて、読む人が判断できるようにする。実測では原価側が主だが、それはこのケースでの観測であって定理ではない。

**4. 数量が一致しなくなったら止めて報告すること（A2.5）。**
いまは 78,671 で一致している。ずれたらハンドオフが壊れているか、需要・能力・warmup のどこかに原因がある。**`quantity` 項で吸収して先に進まないこと。**

**5. 本書の 174.28 / 188.22 は単純平均である。**
数量加重にすると変わる。**合わせにいかないこと。** 測った値を報告してもらい、それを正典とする。
