---
tags: [wom, source]
---
# requests/Phase8-1b_Addendum_MaterialPrice_to_CodeKun.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase8-1b_Addendum_MaterialPrice_to_CodeKun.md) · [原文テキスト](../../90_Raw/requests/Phase8-1b_Addendum_MaterialPrice_to_CodeKun.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Phase 8-1b Addendum — oil-global-2027 の原料単価
- 0. なぜこれを先にやるか
- 1. 結論
- 2. 根因 —— soysauce 定数が dataclass の既定値として置かれている
- 3. 実測（すべて確認済み・Code君は追試してよい）
- 3.1 ppc_supplier_cost.csv は A系統の結果に一切効かない
- 3.2 読んでいるのは行0だけ
- 3.3 直しても配分は1点も動かない
- 3.4 粗利率
- 3.5 golden 13ケースは影響を受けない
- 3.6 家族の掃き出し
- 4. 作業
- B1. データ修正
- B2. テスト定数の分離
- B3. 既定値の撤去 —— 同じ漏出を二度起こさせない
- B4. 不変条件テストの新設
- 5. スコープ外（今回やらないこと）
- 5.1 uom="KL100KBBL" の原料単価
- 5.2 `tools/run_allocation_map.py:68` の `market == "US"`
- 5.3 oil に s2 以降のシナリオを足すこと
- 6. 完了条件
- 7. 測って報告してほしいこと

## 関連する知識源

- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/wom/allocation/regime_map.py|wom/allocation/regime_map.py]]
- [[80_Sources/tests/test_allocation_hierarchical.py|tests/test_allocation_hierarchical.py]]
- [[80_Sources/tests/test_allocation_nmarket.py|tests/test_allocation_nmarket.py]]
- [[80_Sources/tools/run_allocation_map.py|tools/run_allocation_map.py]]
- [[80_Sources/tools/run_planning_loop.py|tools/run_planning_loop.py]]
- [[80_Sources/tools/plot_allocation_merit_regime.py|tools/plot_allocation_merit_regime.py]]
- [[80_Sources/tools/run_headless_from_folder.py|tools/run_headless_from_folder.py]]
- [[80_Sources/tests/test_allocation_grid.py|tests/test_allocation_grid.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 8-1b Addendum — oil-global-2027 の原料単価

宛先: Code君
差出: Claude君
前提: Phase 8-1 完了（90194d8、422件全PASS）
種別: データ修正 + 既定値の撤去 + 不変条件テストの新設

---

## 0. なぜこれを先にやるか

Phase 8-2（GUI の残り）に入る前に、**oil の数値を直しておきたい**。
直った数値の上で画面を直したいからである。逆順にすると、画面を直した直後に
数値が動いて、どちらの変更が何を起こしたのか分からなくなる。

発端は大杉さんが S1 Allocate を実機で動かし、oil をドリルダウンした
スクリーンショットである。**画面そのものに粗利率は出ていない**（後述 §5）。
画面に出ていたのは配分と利益であり、そこから私が独立に単位経済を計算して
初めて「ガソリン1 kL の粗利率 87%」という値に行き当たった。

---

## 1. 結論

`data/sample/oil-global-2027/ga_scenario_master.csv` の
`material_price_usd = 6.00` は誤りである。**soysauce の値である。**

| | ga_scenario_master.csv の宣言値 | ppc_supplier_cost.csv 由来の実測 |
|---|---|---|
| soysauce-jpy-2027-alloc | 6.00 | 6.00 ✔ |
| oil-global-2027 (uom=KL) | 6.00 | **500.00 ✘** |
| oil-global-2027 (uom=KL100KBBL) | 6.00 | **7,800,000.00 ✘**（§4 で据え置き） |

醤油1ケース $6 という量を、ガソリン1 kL に当てている。

---

## 2. 根因 —— soysauce 定数が dataclass の既定値として置かれている

これは Code君の書き間違いではない。**コードの既定値が漏れ出している。**

```
wom/allocation/transmission.py:52   material_usd: float = 6.0
wom/allocation/transmission.py:85   material_usd_base: float = 6.0
wom/allocation/regime_map.py:101    Scenario(fx_usd=150.0, material_usd=6.0)
tests/test_allocation_hierarchical.py:38  SC = Scenario(fx_usd=150.0, material_usd=6.0)
tests/test_allocation_nmarket.py:32       SC = Scenario(fx_usd=150.0, material_usd=6.0)
```

6.0 は「汎用の既定値」ではなく soysauce 固有の値である。それが汎用クラスの
既定値の席に座っているので、新しいモデルを足すたびに黙って複写される。

**Phase 6 で潰した4件と同じ家族である**——region の上書き / 価格の最後勝ち /
経路未到達のゼロ原価 / `market == "US"`。いずれも soysauce では偶然正しく、
他のモデルで黙って壊れた。今回もそうである。

---

## 3. 実測（すべて確認済み・Code君は追試してよい）

### 3.1 ppc_supplier_cost.csv は A系統の結果に一切効かない

`usd_eff = cb.usd − cb.material_usd_base + sc.material_usd` であり、
`leaf_block()` は `blk["USD"] += mat_usd` で **同じ `mat_usd` を全 leaf に足し**、
`material_usd_base` にも同じ `mat_usd` を入れている。つまり**完全に相殺する**。

実測: oil の `ppc_supplier_cost.csv` の原油価格を 500 → 9999 に変えても、

```
  P_opt 変化なし: True   18,666,203,880 vs 18,666,203,880
  推奨配分 変化なし: True
  levels 変化なし: True
```

**A系統の原料費は `ga_scenario_master.csv` の数字1個で全部決まる。**
`material_usd_base` はコスト入力ではなく、regime_map が原料軸を掃くための
相殺装置である。だから2つのファイルの間に照合が無く、6.00 が居座れた。

### 3.2 読んでいるのは行0だけ

```
wom/gui/s1_view_model.py:66    material = float(rows[0]["material_price_usd"])
tools/run_allocation_map.py:70 material = float(rs[0]["material_price_usd"])
```

15行のうち行0しか見ない。他の14行を直しても何も起きない。
A2 で潰した「最後勝ち」の裏返しの「最初勝ち」である。

### 3.3 直しても配分は1点も動かない

私は前便で「メリットオーダーが変わる可能性がある」と書いたが、**測ったら
変わらなかった**。原料費は全市場に同額で乗る定数だからである。

```
Δmargin が全市場で一定か: {74100}     ← 494 USD × 150 ちょうど。15市場すべて同じ
メリットオーダー 一致: True
cap=   20,000  推奨一致=True  child_x一致=True
cap=   60,000  推奨一致=True  child_x一致=True
cap=  200,000  推奨一致=True  child_x一致=True
```

動くのは**利益の水準だけ**である（cap=60,000 で 30,668,808,980 →
16,555,648,880、差 −14,113,160,100 = 74,100 × 総需要190,461ロット）。

mat=500 では赤字になる市場は無い。だから配分は厳密に不変である。

### 3.4 粗利率

| 市場 | 売上(JPY換算) | mat=6.00 | | mat=500.00 | |
|---|---:|---:|---:|---:|---:|
| Retail_EU_NL | 307,800 | 269,640 | 87.6% | 195,540 | 63.5% |
| Retail_EU_DE | 283,500 | 245,340 | 86.5% | 171,240 | 60.4% |
| Retail_Import_KANTO_I | 165,000 | 146,021 | 88.5% | 71,921 | 43.6% |
| Retail_Local_KANTO | 170,000 | 133,100 | 78.3% | 59,000 | 34.7% |
| Retail_US_CA | 157,500 | 116,100 | 73.7% | 42,000 | 26.7% |
| Retail_US_TX | 135,000 | 93,600 | 69.3% | 19,500 | 14.4% |

（`unit_pnl()` の `margin` / `rev` は **JPY 建て**である。`price_local` は
現地通貨なので、両者を割り算に混ぜないこと——私は一度混ぜて 14,191% という
値を出した。）

### 3.5 golden 13ケースは影響を受けない

`ga_scenario_master.csv` を読むのは A系統だけである:

```
wom/gui/s1_view_model.py / tools/run_allocation_map.py
tools/run_planning_loop.py / tools/plot_allocation_merit_regime.py
```

PPC の `tools/run_headless_from_folder.py` は読まない。**golden は不変のはず。**
これは Code君に確認してほしい（私は当 VM に pytest が無く回せていない）。

### 3.6 家族の掃き出し

`ga_scenario_master.csv` を持つ sample case は**2件しかない**
（soysauce-jpy-2027-alloc と oil-global-2027）。soysauce は一致、oil は不一致。
掃き出し範囲はこれで全部である。

---

## 4. 作業

### B1. データ修正

`data/sample/oil-global-2027/ga_scenario_master.csv` の
`material_price_usd` を **6.00 → 500.00**（15行すべて。行0しか読まれないが、
残り14行を放置すると次に読み方を直したときに矛盾が出る）。

`note` 列にも根拠を書いてほしい: 原油 $500/kL は同モデルの
`ppc_supplier_cost.csv` の `Crude_ME, Gasoline_Local, 2027-W01, 500, USD` と
一致する値である、と。

### B2. テスト定数の分離

`tests/test_allocation_hierarchical.py:38` の `SC` は soysauce のテスト
（113〜209行）と oil のテスト（309・314・328行）で共用されている。

`SC_OIL = Scenario(fx_usd=150.0, material_usd=500.0)` を新設し、
**oil のテストだけ**を差し替える。soysauce 側の `SC` は 6.0 のまま
（そちらは正しい）。

`test_oil_uom_split_and_hierarchy` の回帰値2つ

```
r["profit"]        == 18_166_679_186.0
g["hierarchy_gap"] ==    499_524_694.0
```

は**測り直して報告してほしい**。私は letter に新しい値を書かない——書くと
Code君が合わせにいってしまい、独立の測定でなくなる。`nodes == 10` /
`points == 1_050` は構造なので不変のはずである。

### B3. 既定値の撤去 —— 同じ漏出を二度起こさせない

```
wom/allocation/transmission.py:52   material_usd: float = 6.0        → 既定値を削除
wom/allocation/transmission.py:85   material_usd_base: float = 6.0   → 既定値を削除
```

**本体コードへの影響は無い**（実測）。`wom/` `tools/` の `Scenario(...)` は
全箇所が `material_usd=` を明示しており、`CostBlock(...)` の生成2箇所
（`cost_block.py:359` / `hierarchical_simplex.py:311`）も
`material_usd_base=` を明示している。

既定値に頼っているのは `tests/test_allocation_grid.py` の4箇所
（69・70・78・86行の `Scenario(fx_usd=150)`）だけである。ここは
`material_usd=6.0` を明示に書き換える（BLOCKS は soysauce 由来なので値は同じ、
回帰値は動かないはず）。

dataclass のフィールド順の都合で既定値を外せない場合は、その旨を報告して
`= None` + 明示チェックなど別の形にしてよい。要件は「**書き忘れが黙って
soysauce の値になる、という状態を無くす**」ことである。

`regime_map.py:101` の `Scenario(fx_usd=150.0, material_usd=6.0)` は
呼び出し側が渡さなかったときのフォールバックなので、既定値ではなく
**引数必須**に変えるか、少なくとも「soysauce 固有の値である」とコメントを
残すこと。判断は Code君に委ねる。

### B4. 不変条件テストの新設

**これが本 Phase の本体である。** B1 は1回限りの手当てだが、B4 は次の
sample case でも効く。

`tests/` に1件追加:

> `data/sample/*/ga_scenario_master.csv` を持つ全モデルについて、
> base シナリオ（行0）の `material_price_usd` が、
> `derive_cost_blocks(model_dir, uom=<そのモデルの主 uom>)` が返す
> `material_usd_base` と一致すること。

§3.1 のとおり、この2ファイルの間には現在**何の照合も無い**。このテストが
唯一の橋になる。新しいモデルを足した人が原料単価を書き忘れたら、ここで落ちる。

uom が複数あるモデル（oil）の扱いは Code君の判断でよい。主 uom だけを
検査する / uom ごとに検査して既知の例外を明示的に skip する、どちらでもよい。
**KL100KBBL を無言で通さない**ことだけ守ってほしい。

---

## 5. スコープ外（今回やらないこと）

### 5.1 uom="KL100KBBL" の原料単価

正しい値は 7,800,000 だが、`ga_scenario_master.csv` に `uom` 列が無く、
1モデル1値しか持てない。これは Phase 6-3c Addendum A9-3 で
「`sc.material_usd`（kL スケールの量）をタンカーロットに適用することになる
ため、利益・感度分析は意味を持たない」として既に申し送り済みである。
状態は今回も変わらない（6.00 でも 500.00 でも間違いであることは同じ）。

CSV に `uom` 列を足してローダで絞る、というのが正しい形だと考えるが、
それは `ga_scenario_master.csv` のスキーマ変更であり、読み手も2箇所ある。
**単位軸（仕様書 v0r5 §2.6）の話として独立に扱いたい。**

### 5.2 `tools/run_allocation_map.py:68` の `market == "US"`

Phase 8-2 に回す（Phase 8-1 のコミットメッセージで申し送り済み）。

### 5.3 oil に s2 以降のシナリオを足すこと

現在 oil には `s1_base` しか無い。しかし同じモデルの
`ppc_supplier_cost.csv` は 2027-W20 に原油 650、W45 に 680 を持っている。
測ったところ:

```
  mat=560: 赤字 0市場
  mat=650: 赤字 1市場 ['US_TX']
  mat=700: 赤字 2市場 ['US_TX', 'US_NY']
```

**原油が上がると米国市場が順に脱落する**——市場を選ぶかどうかが利益の
符号で決まる、L/N/F でいう N型（閾値）の教材がここに埋まっている。
soysauce の `s3_material_shock` に相当するシナリオを oil にも足すと、
S1 Allocate の Regime Map が意味を持ち始める。

ただしこれは**サンプルケースの拡充作業**であり、本 Phase（欠陥の修正）とは
別種である。大杉さんの整理に従い、`scotch-whisky-2027` の F型と同じ列に置く。

---

## 6. 完了条件

- `ga_scenario_master.csv` (oil) の `material_price_usd` が 500.00
- `SC_OIL` が新設され、oil のテストがそれを使っている
- `transmission.py` の2つの既定値が撤去され、書き忘れが型エラーになる
- §4 B4 の不変条件テストが存在し、oil を 6.00 に戻すと落ちる
  （**これを一度確かめて報告してほしい**——落ちないテストは無いのと同じ）
- golden 13ケースが不変であること
- 全テスト PASS。件数と、B2 の測り直した回帰値2つを報告

---

## 7. 測って報告してほしいこと

1. `test_oil_uom_split_and_hierarchy` の `profit` と `hierarchy_gap` の新しい値
2. golden 13ケースが本当に不変か（§3.5 の推論の検証）
3. B3 で `tests/test_allocation_grid.py` 以外に既定値に頼っていた箇所があったか
4. B4 のテストを oil=6.00 に戻して走らせたとき、実際に落ちるか
5. 最終テスト件数

回帰値は本書に書いていない。Code君が測った値を正典とする。

````
