---
tags: [wom, source]
---
# docs/design/wom_model_typology.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/wom_model_typology.md) · [原文テキスト](../../../90_Raw/docs/design/wom_model_typology.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- WOM Model Typology — 配分問題の構造を測って分類する
- 1. なぜこの文書があるか
- 2. 構造の型
- 3. 判定方法
- 4. 実測結果
- 4.1 `soysauce-jpy-2027-alloc`（9シナリオ）
- 4.2 測定できていないケース
- 5. パラメータ語彙
- 6. 測り方
- 7. この文書の更新ルール
- 関連文書
- 改版履歴

## 関連する知識源

- [[80_Sources/requests/Phase4_DesignMD_AllocationMeritRegime.md|requests/Phase4_DesignMD_AllocationMeritRegime.md]]
- [[80_Sources/requests/Phase5_DesignMD_NonConcaveTariff.md|requests/Phase5_DesignMD_NonConcaveTariff.md]]
- [[80_Sources/requests/Phase6_DesignMD_NMarketHierarchy.md|requests/Phase6_DesignMD_NMarketHierarchy.md]]
- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]

## 全文（コメント・原文を省略せず収録）

````markdown
# WOM Model Typology — 配分問題の構造を測って分類する

**作成日**: 2026年9月11日
**位置づけ**: 設計正典（`docs/design/`）。WOM で扱う配分問題を、**利益関数の構造**によって型に分けるための文書
**前提**: Phase 6-1（`true_continuous_optimum()`）実装済み — `wom-v1r4m0` / commit `8a8eb1f` 以降

---

## 1. なぜこの文書があるか

WOM のケースが増えるたびに、新しいパラメータと新しい構造が現れる。「WOM モデルの類型を体系的に整理するのは、ケースがもっと増えてからでないと難しいのではないか」という問いが自然に出てくる。

**本文書の立場は、その逆である。** 類型化は「ケースを集めてから帰納する」のではなく、**測定器を作ってから、ケースを測る**。

Phase 4 / 5 / 6-1 を通じて、その測定器ができた。`structural_optimality_gap`（構造由来の取りこぼし）は、ケースを1本流せば数字が出て、**その数字が型を教えてくれる**。20ケース集めてから分類を考えるのではなく、いま表を書いて、次のケースはその表に照らして測る。

空欄があること自体が資産である。「ここはまだ分かっていない」と示せる表のほうが、埋まった表より信頼できるし、次に何を探すべきかのチェックリストになる。

---

## 2. 構造の型

配分変数 `x`（各市場への供給比率）に対する利益関数の形で分ける。

| 型 | 利益関数の形 | 経営上の意味 | 貪欲法（単価の良い順に積む） | `structural_optimality_gap` |
|---|---|---|---|---|
| **L 線形・分離可能** | 直線 | 単価は量によらない | **厳密に最適** | 0 |
| **N 非凹（閾値）** | 階段（上にジャンプ） | 一定量を超えると**条件が良くなる** | 構造的に外す | > 0 |
| **F 固定費（離散選択）** | 原点で下にジャンプ、以降は直線 | 一定量に届かないと**赤字**（腰高経営） | さらに外す | > 0（N より大きくなりやすい） |

**L 型**では、単位マージンが配分量によらず一定なので、「マージンの高い市場から需要天井まで埋める」という手続きが厳密解を与える。メリットオーダー曲線がそのまま答えになる。

**N 型**では、配分量そのものが単価を変える。FTA の原産地規則（一定数量以上で関税ゼロ）が典型。貪欲法は「いまこの市場の単価はいくらか」で順位を決めるため、**閾値の手前で止まり、永久に閾値に届かない**。

**F 型**は未実装（Phase 7 以降の候補）。市場に参入するだけで固定費がかかる構造である。酒類の登録、ラベル規制対応、輸入業者との契約、初期リスティング料——**数量に関係なく先に払う費用**があると、各市場に**損益分岐点**が生まれる。「開けるなら分岐点以上、開けないならゼロ」という離散的な判断が混じる。

**これは実務で「腰高経営」と呼ばれる構造そのものである。** 固定費が重い事業は損益分岐点が高く、量が落ちた瞬間に成立しなくなる。N 型（閾値関税）が「閾値を超えると**条件が良くなる**」構造であるのに対し、F 型は「**一定量に届かないと、そもそも赤字**」という構造で、経営上の意味がまったく違う。だから N 型の一種として畳まず、独立した型として立てる。

貪欲法の失敗の仕方も N 型とは異なる。単位マージンの良い順に薄く広く配ると、**どの市場でも固定費を回収できない**。N 型が「1つの市場で閾値の手前に止まる」失敗なのに対し、F 型は「全市場で分岐点に届かない」失敗になりうる。だから `structural_optimality_gap` は N 型より大きく出やすい。

そして問いそのものが変わる。「**どこへ、どれだけ配るか**」という連続的な配分問題から、「**どの市場を開けるか**」という離散的な選択問題になる。利益地形図でいえば、地形に**崖ではなく穴**が空く。

---

## 3. 判定方法

ケースを `true_continuous_optimum()` に通し、3つの利益水準を比べる。

```
P_greedy   貪欲法（メリットオーダー）の解
P_grid     δ=0.05 格子上の最良点
P_opt      真の連続最適（cliff の on/off を全列挙して厳密に解いた値）

structural_optimality_gap = P_opt − P_greedy      ← 構造由来の取りこぼし
grid_resolution_error     = P_opt − P_grid        ← 格子解像度の誤差
gap_amt                   = P_greedy − P_grid     ← 符号が非凹性の指標
structural_residual       = gap_amt − grid_idle × λ
residual_coverage         = |structural_residual| / structural_optimality_gap
```

**判定:**

| 観測 | 型 | 読み方 |
|---|---|---|
| `structural_optimality_gap == 0` | **L** | 貪欲法で判断してよい。Merit Order の順位づけをそのまま信じられる |
| `structural_optimality_gap > 0` かつ `gap_amt < 0` | **N** | 閾値がどこかにある。貪欲法が格子の最良点にも負けている |
| `structural_optimality_gap > 0` かつ `gap_amt > 0` | 要調査 | 格子が粗すぎて真の構造が見えていない可能性。δ を細かくして再測定する |

**常に成り立つのは2本の不等式だけ**である。

```
P_opt ≥ P_greedy     （貪欲法は最適を超えられない）
P_opt ≥ P_grid       （格子は連続空間の部分集合）
```

`P_greedy` と `P_grid` の順序は決まっていない。**その順序が型によって反転する**ことが、`gap_amt` の符号を指標にできる理由である。

**`residual_coverage` は下界の質を示す。** `structural_residual` は実装が常に返す値だが、`grid_idle = 0` のとき `expected_gap = 0` となり、構造由来の取りこぼしを過小評価する。その被覆率がこの値である。`P_opt` が計算できない状況でも `|structural_residual|` は**安全側の下界**として使える。

---

## 4. 実測結果

### 4.1 `soysauce-jpy-2027-alloc`（9シナリオ）

`true_continuous_optimum()` を全シナリオに適用した結果（2026-09-11、commit `19fd1b1` 時点）。

| scenario | cap_wk | P_greedy | P_grid | P_opt | gap_amt | structural_optimality_gap | coverage | 型 |
|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| `s1_base` | 800 | 135,529,822 | 132,133,072 | 135,529,822 | +3,396,750 | 0 | — | **L** |
| `s2_weak_yen` | 800 | 208,582,160 | 207,246,105 | 208,582,160 | +1,336,055 | 0 | — | **L** |
| `s3_material_shock` | 800 | 110,569,822 | 108,531,772 | 110,569,822 | +2,038,050 | 0 | — | **L** |
| `s4_compound` | 800 | 176,651,305 | 176,651,305 | 176,651,305 | 0 | 0 | — | **L** |
| `s5_strong_yen` | 800 | 86,058,408 | 85,837,232 | 86,058,408 | +221,176 | 0 | — | **L** |
| `s6_us_tariff_up` | 800 | 123,921,742 | 120,957,412 | 123,921,742 | +2,964,330 | 0 | — | **L** |
| `s7_rate_up` | 800 | 135,529,822 | 132,133,072 | 135,529,822 | +3,396,750 | 0 | — | **L** |
| `s8_actual_path` | 800 | 135,529,822 | 132,133,072 | 135,529,822 | +3,396,750 | 0 | — | **L** |
| `s9_fta_cliff` | 500 | 93,824,700 | 103,552,800 | **103,891,296** | **−9,728,100** | **10,066,596** | 0.966 | **N** |

**読み取れること。**

外部環境（為替・原材料価格・関税率）をどれだけ動かしても、**構造は L のまま変わらない**（s1〜s8）。`gap_amt` は 221,176 から 3,396,750 まで振れるが、これは全量が格子解像度の誤差であり、`structural_optimality_gap` は一貫してゼロである。**外部環境の変化は地形の高さを変えるが、地形の性質は変えない。**

型を変えたのは `s9_fta_cliff` だけである。ここで変えたのは外部環境ではなく、**関税の与え方**（固定税率 → 配分量に依存する cliff）——すなわち**伝達式の構造そのもの**である。

`s4_compound` で `gap_amt = 0` になっているのは、格子点がたまたま連続最適と一致したためで、構造的な意味はない。

### 4.2 測定できていないケース

現時点で A系統（配分分析）が走るのは **18ケース中1ケースだけ**である。

| 状況 | ケース数 | 内訳 |
|---|---:|---|
| 測定済み | 1 | `soysauce-jpy-2027-alloc` |
| **`ga_market_aggregation.csv` のみ不足** | 13 | `Cookie-jp-2026` / `apparel-global-2028-2029` / `apparel-us-2026` / `bom-test-2026` / `ev-europe-2026` / `ev-thailand-2026` / `ev-thailand-2026_update` / `india-ghee-2026` / `iphone_global` / `oil-global-2027` / `smartx-2027-2029` / `soysauce-eu-2027` / `soysauce-jpy-2027` / `soysauce-us-2027` |
| PPC 系 CSV が未整備 | 3 | `iphone` / `rice-japan-2027-2028`（＋バックアップ） |

**13ケースは `ga_market_aggregation.csv` 1本が足りないだけ**である。`ppc_node_cost_rule` / `ppc_edge_cost_rule` / `ppc_supplier_cost` / `ppc_tariff_rule` / `ppc_market_price` / `sc_tree_master` / `sku_master` / `ppc_transfer_price_rule` はすべて揃っている。

つまり、**全ケースを型で分類するのに必要なのは、ケースあたり CSV 1本の追加であって、大規模なデータ整備ではない。** これは本文書を書いて初めて見えた事実である。

`oil-global-2027`（marketing ノード21件）は、Phase 6-2 / 6-3（N市場化・階層化単体格子）が完了してからでないと格子スキャンが走らない（δ=0.05 で約1,378億点）。それ以外の12ケースは、CSV を1本足せば今日の実装で測れる。

---

## 5. パラメータ語彙

利益関数を配分量について**非線形にする仕組み**の一覧。実務に存在する機構をここに集める。

**型の分類（§2）は演繹で決まるが、この語彙は演繹では出てこない。** FTA の原産地規則に出会わなければ `preferential_threshold_lot` という列は思いつかない。ここは**ケースの蓄積でしか埋まらない**。

| 機構 | 型 | 実装状況 | 列 / 実装 | 見つかったケース |
|---|:--:|---|---|---|
| 閾値関税（FTA 原産地規則） | N | **実装済み** | `tariff_rate_preferential` / `preferential_threshold_lot`（`transmission.py`） | `s9_fta_cliff`（合成） |
| 市場参入の固定費（**腰高経営**） | F | 未実装 | — | ウィスキー輸出先の再配分（検討中） |
| 数量割引・ボリュームインセンティブ | N | 未実装 | — | — |
| 現地生産比率規制（LC率閾値） | N | 未実装 | — | `ev-thailand-2026`（未検証） |
| 能力の段階増設（ライン増設の固定費） | F | 未実装 | — | — |
| 学習曲線（累積生産量で単価が下がる） | ? | 未実装 | — | — |
| 為替ヘッジの帯（一定レンジ内は固定レート） | ? | 未実装 | — | — |
| （空欄） | | | | |

**空欄は空欄のまま残す。** 実務に存在する機構はおそらく6〜8種類で大半を覆うが、まだ確定していない。次のケースを定義するときは、この表を見て「この業界の非線形性はどれか」と問う。

**注意: TRQ（関税割当）は採らない。** 一定数量までは低税率、超過分は高税率——という構造は、閾値を超えると条件が**悪くなる**方向であり、利益関数を凹にする。凹な問題では貪欲法は正しく動くため、構造由来の取りこぼしを検出する題材にならない（Phase 5 設計書 §3.1 で検討し不採用とした）。

---

## 6. 測り方

```bash
python -m tools.demo_allocation_nonconcave --model-dir data/sample/<case>
```

任意のケースを測るスクリプトは未整備（Phase 7 以降の候補）。現時点では `true_continuous_optimum()` と `compare_with_grid(mo, surface, true_optimum=...)` を直接呼ぶ。

```python
from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import Scenario
from wom.allocation.grid import scan_surface
from wom.allocation.merit_order import (
    build_allocation_merit_order, compare_with_grid, true_continuous_optimum)
from tools.run_allocation_map import load_scenarios, _blocks_for

base, tp = derive_cost_blocks(model_dir)
s = {x["id"]: x for x in load_scenarios(model_dir)}["<scenario_id>"]
blocks = _blocks_for(base, s["tariff"], s.get("tariff_preferential"),
                     s.get("preferential_threshold"))
sc = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])

mo   = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)
surf = scan_surface(blocks, tp, sc, cap_wk)
topt = true_continuous_optimum(blocks, sc, cap_wk, transfer_price_usd=tp)
cmp  = compare_with_grid(mo, surf, true_optimum=topt)

cmp["structural_optimality_gap"]   # 0 なら L 型
cmp["gap_amt"]                     # 負なら N 型の疑い
cmp["residual_coverage"]           # 下界の質（L 型では None）
```

**`_blocks_for()` は4引数である。** cliff 列（`tariff_preferential` / `preferential_threshold`）を渡し忘れると、非凹ケースが L 型として測られてしまう。本文書の §4.1 を作る過程で実際にこの誤りを踏んだ。

---

## 7. この文書の更新ルール

- **新しいケースを定義したら、§4 に1行足す。** 測れない場合は「測れない理由」を書く
- **新しい非線形の機構を見つけたら、§5 に1行足す。** 実装前でも「見つかった」だけで記録する価値がある
- **型（§2）は簡単には増やさない。** L / N / F は利益関数の形による分類であり、業界や題材で増やすものではない。新しい型を立てるのは、既存3型のどれでも説明できない構造が見つかったときに限る
- **空欄を埋めるために憶測を書かない。** 「まだ分かっていない」が正しい記述であることは多い

---

## 関連文書

- `requests/Phase4_DesignMD_AllocationMeritRegime.md` — メリットオーダー曲線とレジーム地図、`expected_gap` と下界の考え方
- `requests/Phase5_DesignMD_NonConcaveTariff.md` — 数量依存関税（cliff 型）の導入と `structural_residual`
- `requests/Phase6_DesignMD_NMarketHierarchy.md` §3 — `true_optimum` の実計算方式
- `docs/design/ask_global_allocation_spec.md` — A系統の仕様
- note 記事「[利益地形図で読み解く事業計画](https://note.com/osuosu1123/n/nde1d9b686a6e)」 — 本文書の内容を経営者向けに解説したもの

---

## 改版履歴

- 2026-09-11 rev.2 — F 型（固定費・離散選択）を独立した型として維持することを確定（大杉さん判断）。実務用語「**腰高経営**」に対応する構造であり、N 型が「一定量を超えると条件が良くなる」のに対し F 型は「一定量に届かないと赤字」という、経営上まったく別の意味を持つため。貪欲法の失敗の仕方も異なる（N は1市場で閾値の手前に止まる、F は全市場で損益分岐点に届かない）ことを §2 に追記。型の表に「経営上の意味」列を追加
- 2026-09-11 初版 — Phase 6-1（`true_continuous_optimum()`）の実装により、ケースを型で測れるようになったことを受けて作成。`soysauce-jpy-2027-alloc` の9シナリオを実測し、外部環境の変化では型が変わらず、伝達式の構造を変えたときだけ型が変わることを確認。あわせて、18ケース中13ケースが `ga_market_aggregation.csv` 1本の不足だけで測定できない状態にあることを発見した

````
