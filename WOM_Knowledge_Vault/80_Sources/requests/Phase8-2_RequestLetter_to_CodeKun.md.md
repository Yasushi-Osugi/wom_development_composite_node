---
tags: [wom, source]
---
# requests/Phase8-2_RequestLetter_to_CodeKun.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase8-2_RequestLetter_to_CodeKun.md) · [原文テキスト](../../90_Raw/requests/Phase8-2_RequestLetter_to_CodeKun.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Phase 8-2 Request Letter — S1 Allocate を仕上げる
- 0. 本 Phase の位置づけ
- 1. いま画面がどうなっているか（実測・すべて oil, uom=KL, 能力800/週）
- 2. 作業
- C1. 結論行と子パネルが、別々の配分を無印で並べている（最優先）
- C2. 配分ゼロのノードが、意味の無い比率を「推奨」として出している
- C3. 15市場の結論行が右端で切れ、切れた部分が答えだった
- C4. 葉ノードが空白の箱になる
- C5. 階層化の誤差を2項に分解する
- C6. 整形の粗2件
- s1_view_model.py:181-183
- s1_view_model.py:283（N=3 経路のみ）
- 3. スコープ外
- 3.1 `best_point()` の `chosen = plateau[0]`（申し送り・本 Phase では触らない）
- 3.2 `tools/plot_allocation_merit_regime.py` の原料軸の範囲
- 3.3 `tools/run_allocation_map.py:68` の `market == "US"`
- 3.4 S2〜S5、⚑ からの Planning Engine 実行、残りの Drill-down
- 4. 制約（Phase 8-1 から継続）
- 5. 完了条件
- 6. 測って報告してほしいこと

## 関連する知識源

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/tools/plot_allocation_merit_regime.py|tools/plot_allocation_merit_regime.py]]
- [[80_Sources/tools/run_allocation_map.py|tools/run_allocation_map.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 8-2 Request Letter — S1 Allocate を仕上げる

宛先: Code君
差出: Claude君
前提: Phase 8-1b 完了（4d0ef1c、426件全PASS）
設計正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §4 S1

---

## 0. 本 Phase の位置づけ

S1 Allocate は動いた。大杉さんが oil-global-2027 を実機でドリルダウンし、
**画面を見て初めて分かった問題が6件出た**。本 Phase はその6件を直す。

S2〜S5 の画面、⚑ からの Planning Engine 実行、Regime Map 等の
Drill-down は **Phase 8-3 以降**。まだ1画面を仕上げていないうちに
横展開すると、同じ欠陥が5箇所に複製される（Phase 8-1 §0 と同じ理由）。

内訳: **大杉さんが実機で見つけたもの 4件**（C1・C3・C4・C6）、
**Claude君が測って見つけたもの 2件**（C2・C5）。

---

## 1. いま画面がどうなっているか（実測・すべて oil, uom=KL, 能力800/週）

```
結論行 headline.recommended : {'Retail_EU_DE': 0.3129, ..., 'Retail_US_TX': 0.0}   ← P_opt
子パネル node.child_x       : {'JPY': 0.25, 'EUR': 0.75, 'USD': 0.0}               ← 階層格子の点
⚑ が計画する配分            : headline.recommended （allocation_panel.py:385）
```

```
node_path = ()                          plateau=  1  cap_lots=83,200.0
node_path = ('JPY','SP_Oil_Local')      plateau=  1  cap_lots=11,440.0
node_path = ('USD',)                    plateau= 21  cap_lots=     0.0   ← 全21点が同値0
node_path = ('USD','SP_Oil_US_Local')   plateau=231  cap_lots=     0.0   ← 全231点が同値0
```

```
結論行 line1（実物・右端が画面から溢れている）
推奨配分  Retail_EU_DE 31 / Retail_EU_FR 20 / Retail_EU_NL 10 /
Retail_EU_Import_DE_I 9 / Retail_Local_CHUBU 8 / Retail_Import_KANTO_I 7 /
Retail_EU_Import_FR_I 5 / Retail_Local_KANTO 5 / Retail_Import_KANSAI_I 5 /
Retail_Local_KANSAI 0 / Retail_US_TX 0 / Retail_US_CA 0 / Retail_US_NY 0 /
Retail_US_Import_MW_I 0 / Retail_US_Import_NE_I 0        利益 125.011 億（真の最適）
```

---

## 2. 作業

### C1. 結論行と子パネルが、別々の配分を無印で並べている（最優先）

同じ画面に2つの配分が出ていて、**どちらにもラベルが無い**。上は P_opt
（真の連続最適）、下は階層走査が選んだ格子点。**両方とも正しい**が、
見た人は「同じ配分のはずなのに数字が違う」と読む。

`line1` は末尾に「（真の最適）」を持っているが、これは**利益に付いていて
配分に付いていない**（`… 利益 125.011 億（真の最適）`）。しかも配分の
文字列から遠く離れている。

さらに **⚑「この配分で計画する」は結論行のほう（P_opt）を計画する**
（`allocation_panel.py:385`）。**子パネルの比率は決して計画されない。**
これが画面のどこにも書かれていない。

直すこと:

1. 結論行の先頭を `推奨配分（連続最適）` にする。ラベルを配分に付ける
2. 子パネルの見出しを付ける: `このノードの走査結果（階層格子 δ=0.05）`
3. ⚑ ボタンの近くに1行: `計画するのは上の推奨配分です`

**格子点を消してはいけない。** 「地形のどこを走査したか」の情報であり、
消すと階層走査の中身が見えなくなる。区別が付くようにするだけでよい。

### C2. 配分ゼロのノードが、意味の無い比率を「推奨」として出している

`USD` を降りると **利益が全点 0 の平坦な線**が出て、側面に
`SP_Oil_US_Local 100% / SP_Oil_US_Import 0%`、さらに降りると
`Retail_US_TX 100%` が出る。大杉さんはこれを「不自然」と報告された。

**計算は正しい。** 能力 800/週 = 83,200 lot に対し総需要は 190,461 lot
——**能力は需要の 43.7% しかない**。メリットオーダー上位から詰めると
9位の `Retail_Local_KANTO` の途中で能力が尽き、10位以下（関西と米国5市場）
には1ロットも回らない。**P_opt も同じく USD 系5市場に 0% を与えている**
（階層化の近似のせいではない。この能力では米国は取らないのが最適）。

`US_TX 100%` はタイブレークの先頭である。`best_point()` は

```python
best = max(r["profit"] for r in surface)                                  # = 0.0
plateau = [r for r in surface if r["profit"] >= best - abs(best) * 0.001] # 許容幅も 0
```

で **231点すべてを台地**とし、`chosen = plateau[0]` が格子の第1点
`(1.0, 0, 0)` ——第1子に100%——を返す。推奨されたのではない。

副作用として「台地サイズ 231点」の意味も反転している。普通これは
「配分の自由度が高い」と読むが、ここでの意味は逆で「**この枝は
使われていない**」である。

直すこと（`cap_lots == 0`（または極小）のノードで）:

1. `child_x` を画面に出さない
2. 図を描かない
3. 台地サイズを出さない
4. 代わりに1行:
   `この枝には配分されていません（0 lot）。上位ノードで <親> の比率が 0 のため、ここから下の比率に意味はありません。`

`build_s1_view()` の返り値に `node["is_unallocated"]: bool` を足し、
判定を view 側に置くこと（パネルで `cap_lots == 0` を書かない。
**計算と描画の分離**は Phase 8-1 の設計の柱である）。

### C3. 15市場の結論行が右端で切れ、切れた部分が答えだった

**これが C2 の「不自然さ」の本当の犯人である。** 画面外に落ちていたのは
まさに `Retail_Local_KANSAI 0 / Retail_US_TX 0 / …` の部分——
**画面は答えを持っていたのに、右端で捨てていた。**

だから「入りきらないので削る」のではなく「**要約する**」ように直す。
0配分の市場を黙って落とすと、同じ事故をもう一度起こす。

直すこと:

1. 結論行 line1 は上位4市場 + 残りの要約に畳む。形の案:
   `推奨配分（連続最適） EU_DE 31 / EU_FR 20 / EU_NL 10 / EU_Import_DE_I 9 / 他5市場 計30 / 配分ゼロ 6市場   利益 125.011 億`
2. **配分ゼロの市場数を必ず出す。** 0 のときは「配分ゼロ なし」でよい
3. 全市場の配分は根拠パネルに全文を出す（折り返し可・幅に余裕がある）

市場名の前置き `Retail_` は画面では落としてよい（`node["children"]` の
表示にも同じ整形を使うこと。2箇所で別々に整形しないこと——**A5/A8 で
踏んだ「フィルタを2箇所に置く」と同じ家族**）。

### C4. 葉ノードが空白の箱になる

`Retail_Local_KANTO` まで降りると `配分が一意（描画なし）` の大きな空白
（`allocation_panel.py:342`）。設計書の「子1のノードは図を出さない」を
そのまま実装した結果で指示どおりではあるが、**ドリルダウンの終点が
何も見せないのは行き止まりである。**

葉には配分の余地が無いかわりに**単位経済が確定している**。そこを出す。

実測で、葉ノードに必要な値はすべて手元にある:

```
Retail_Local_KANTO
   cap_lots=5,148.00  demand=22,314  出荷=min(cap_lots, demand)=5,148.00
   （scan_hierarchical の q と完全一致することを確認済み）
   price_local=170,000 JPY  tariff=0.000  rev=170,000  cost=111,000  margin=59,000 (34.7%)
Retail_US_TX
   cap_lots=0.00  demand=34,006  出荷=0.00
   price_local=900 USD  tariff=0.000  rev=135,000  cost=115,500  margin=19,500 (14.4%)
```

直すこと（`node["plot_kind"] == "none"` かつ葉のとき）:

`build_s1_view()` が `node["leaf_economics"]` を返す。中身:

| 項目 | 出どころ |
|---|---|
| 販売通貨・現地売価 | `cb.ccy` / `cb.price_local` |
| 売上（JPY/lot） | `unit_pnl_at_quantity(cb, sc, 出荷量, tp)["rev"]` |
| 原価（JPY/lot） | 同 `["cost"]` |
| 単位マージンと率 | 同 `["margin"]`、`margin / rev` |
| **全市場中の順位** | 単位マージン降順。`15市場中 9位` の形 |
| 需要・配分・出荷 | `cb.demand_qty` / `cap_lots` / `min()` |
| 関税率 | `cb.tariff_rate` |

**単位マージン率（%）は現在 GUI のどこにも出ていない。** これを出すこと
自体が本 Phase の価値の一つである——Phase 8-1b で見つけた原料単価の
誤り（粗利率 87%）は、画面に率が出ていれば大杉さんが即座に気づけた。

順位と出荷0が並ぶと C2 の説明が自動的に立つ:
`15市場中 15位 / 出荷 0 lot（能力が9位で尽きたため）`。

**マージンと売上は JPY 建て、`price_local` は現地通貨である。混ぜないこと**
——私は一度混ぜて 14,191% という値を出した。docstring に残すこと。

図は任意。出すなら 売上 → 原価 → マージン の横棒1本で足りる。
表が本体である。

### C5. 階層化の誤差を2項に分解する

結論行の2行目が、修正前後でこう動いた。

```
mat=6   : 階層化の誤差 -5.00億（-2.68%）
mat=500 : 階層化の誤差 -3.65億（-2.92%）
```

**絶対額は下がり、率は上がる。** 読んだ人は「5億から3.65億に改善した」
と思う。改善していない。実測すると、

```
未出荷ロット = 1,800.45 lot  ← mat=6 でも mat=500 でも完全に同一
```

**物理的な取りこぼしは1ロットも変わっていない。** 単価が下がったので
円が縮んだだけである。円だけを見せると必ず読み違える。

Phase 7a で `gap_vs_plan_pct` という単一の比率を葬り、3項分解に
置き換えたのと同じ問題である（設計書 rev.3 §2.4）。今度は階層化誤差で
同じことが起きている。**割り算1個で語らない。**

直すこと: `hierarchy_gap` を2項に分ける。

```
階層化の誤差 = 配分ズレ + 数量
  配分ズレ : 同じ総量を最適に配った場合との差（階層化の構造的な誤差）
  数量     : 出し切れなかった分（未出荷ロット × 限界市場の単位マージン）
```

実装:

```python
q_hier_total = sum(hier["q"].values())
same = true_continuous_optimum(blocks, sc, cap_wk=q_hier_total / WEEKS,
                               transfer_price_usd=tp)
mix = same["profit"] - hier["profit"]      # 配分ズレ
vol = to["profit"]   - same["profit"]      # 数量
unshipped = sum(to["q"].values()) - q_hier_total
```

**固定してほしい恒等式が2本ある**（テストで杭を打つこと）:

1. `hierarchy_gap == mix + vol`（±1円）
2. `vol == unshipped × 限界市場の単位マージン`（±1円）
   ——限界市場は「メリットオーダー上、能力が尽きた市場」。
   oil（能力800/週）では `Retail_Local_KANTO`

**回帰値は本書に書かない。** 2本の恒等式が成立することと、
`unshipped` が原料単価を変えても不変であることを測って報告してほしい。

結論行2行目の形の案:

```
階層化の誤差 -3.65億 = 配分ズレ -2.59億 ＋ 出し切れず -1.06億（未出荷 1,800 lot）
```

「上位で確定した配分が下位の事情を見ていない」という現在の説明文は
**配分ズレのほうにだけ付く**。数量項は別の理由（下位の需要上限で能力が
余った）なので、同じ説明を両方に被せないこと。

### C6. 整形の粗2件

```python
# s1_view_model.py:181-183
f"ただし {axis_ja} が {reversal['boundary']:.0f} 円を{verb}と"
f"{leader} 優先へ判断反転"
```
→ `…を上回るとRetail_EU_NL 優先へ` とスペースが欠ける。`と` の後に
半角スペースを入れる。

```python
# s1_view_model.py:283（N=3 経路のみ）
f"構造由来の取りこぼし {cmp['structural_optimality_gap'] / 1e4:+.0f}万"
```
→ 0 のとき `構造由来の取りこぼし +0万`。0 のときは
`構造由来の取りこぼしなし` にする。

---

## 3. スコープ外

### 3.1 `best_point()` の `chosen = plateau[0]`（申し送り・本 Phase では触らない）

C2 の根っこはここにある。許容幅 `abs(best) * 0.001` が**相対値**なので、
利益水準が変わるだけで採用点が動く。実測（同一の地形・同一の総量11,440 lot）:

```
SP_Oil_Local  mat=6   : 台地=3  KANTO 0.50 / KANSAI 0.00 / CHUBU 0.50
              mat=500 : 台地=1  KANTO 0.45 / KANSAI 0.00 / CHUBU 0.55
```

また `plateau[0]` は「格子順の先頭」= `(1.0, 0, …)` =**第1子に全部**への
偏りを持つ。格子の真の最良点に替えると `+2,187,558円`（mat=6）/
`+1,025,033円`（mat=500）——P_hier の 0.01% 程度なので実損は小さい。

**本 Phase では `best_point()` も `hierarchical_simplex.py` も触らない。**
直すと P_hier 系の回帰値が全部動き、GUI の修正と混ざって切り分けが
できなくなる。A系統だけの独立した小 Phase にしたい。

本 Phase でやるのは C2 の**表示側の手当て**だけである。

### 3.2 `tools/plot_allocation_merit_regime.py` の原料軸の範囲

```python
mat_values = [4.0 + 0.5 * i for i in range(13)]        # 4.0..10.0
mark_points=[(150.0, 6.0, "base"), (200.0, 8.0, "shock")]
```

`--model-dir` を取る汎用ツールなのに、原料軸のレンジとマーカーが
soysauce スケールで固定されている。oil に向けると軸が丸ごと2桁ずれる。
Phase 8-1b で Code君が直したのは「どの値を使うか」で、残っているのは
「どの範囲を描くか」。GUI ではなく tools 側なので本 Phase の外に置く。

### 3.3 `tools/run_allocation_map.py:68` の `market == "US"`

Phase 8-1 から持ち越し。A系統に触る Phase でまとめて直す。

### 3.4 S2〜S5、⚑ からの Planning Engine 実行、残りの Drill-down

Phase 8-3 以降。

---

## 4. 制約（Phase 8-1 から継続）

- **計算と描画を分ける。** 判定・整形・数値はすべて `s1_view_model.py`
  （純関数・テスト対象）。`allocation_panel.py` は view を受け取って
  並べるだけ。パネルの中で `cap_lots == 0` を判定しない、
  `unit_pnl()` を呼ばない、市場名を整形しない
- **既存9タブは1行も触らない。** `app.py` の差分は 0 行のはず
- **GUI の図中は日本語でよい**（`app.py:31` でフォント設定済み）。
  「図中テキストは全て英語」は `tools/` の PNG 出力に対する制約であって
  GUI には及ばない
- `P_flat` / `P_hier − P_flat` / 「平坦」の語を view に入れない
  （符号が定まらない・Phase 6-3 実測で勝ち6分け3負け6）
- **結論行と levels は `node_path` を変えても変わらない**（V1.1）。
  C3 で結論行を畳んでも、この性質は保つこと

---

## 5. 完了条件

- C1〜C6 が実装されている
- `cap_lots == 0` の判定が view 側にあり（`node["is_unallocated"]`）、
  パネルに `== 0` の比較が無い
- 葉ノードで単位マージン率（%）と全市場中の順位が出る
- 恒等式2本がテストで固定されている（§2 C5）
- `unshipped` が原料単価に依存しないことを測って報告
- 結論行が 15市場で1行に収まり、**配分ゼロの市場数が出ている**
- 既存9タブ無変更、golden 13ケース不変、全テスト PASS（件数を報告）

## 6. 測って報告してほしいこと

1. §2 C5 の2本の恒等式が成立するか。成立するなら `mix` / `vol` /
   `unshipped` の値
2. `unshipped` は原料単価（6.00 と 500.00）で本当に同一か
3. 限界市場の判定をどう実装したか（メリットオーダーの何位で切れたか）
4. 15市場の結論行が実際に何文字になったか
5. 最終テスト件数

回帰値は本書に書いていない。Code君が測った値を正典とする。

````
