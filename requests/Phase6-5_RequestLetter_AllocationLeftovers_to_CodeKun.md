# Phase 6-5 Request Letter — A系統の積み残し3件

宛先: Code君
差出: Claude君
前提: Phase 8-2a 完了（fb6b2cb、442件全PASS）
種別: A系統（`wom/allocation/` `tools/`）のみ。GUI は触らない

※ 番号について: A系統は Phase 6 系列（6-1 / 6-2 / 6-2a / 6-3 / 6-3b / 6-3c）。
6-4 は「データ不足」という私の誤診で撤回済みなので欠番のまま、6-5 とする。

---

## 0. なぜ 8-3 の前にやるか

3件とも **S2〜S5 に相続される**。S1 だけのうちに直せば直す場所は1つ、
4画面に複製してから直すと5つになる。Phase 8-1 で「6画面を一度に設計すると
欠陥が6箇所に複製される」と書いたのと同じ理屈である。

そして3件とも**測定済み・設計の曖昧さゼロ**である。だから本 Phase は
「大杉さんが依頼書を読まずに回す」試験台にもなっている（Gate 0 の網が
効いているかも、ここで見える）。

---

## E1. 採用点が「格子順の先頭」への偏りを持つ

### 何が起きているか

```python
# wom/allocation/grid.py:168
def best_point(surface, plateau_tol: float = 0.001):
    best = max(r["profit"] for r in surface)
    plateau = [r for r in surface if r["profit"] >= best - abs(best) * plateau_tol]
    return best, plateau
```

呼び出し側は軒並み `chosen = plateau[0]` を採る。`plateau` はグリッド順なので
**先頭は `(1.0, 0, …)`＝第1子に全部**である。

実測（S1・oil・能力800/週）:

```
USD ノード（cap_lots = 0・全点が利益0）
  best = 0.0 -> 許容幅 abs(0.0) * 0.001 = 0 -> 231点すべてが台地
  plateau[0] = (1.0, 0, 0) -> 画面に「US_TX 100%」
```

これが Phase 8-2 の C2（大杉さんが「不自然」と指摘した画面）の根っこだった。
GUI 側では表示を手当てしたが、**根は A系統に残っている。**

### 台地の中身も、利益水準だけで動く

許容幅が `abs(best) * 0.001` という**相対値**なので、地形が同じでも
利益水準が変わると台地の広さが変わり、採用点が動く。実測（同一の地形・
同一の総量 11,440 lot・原料単価だけ変更）:

```
SP_Oil_Local  mat=6   : 台地=3  KANTO 0.50 / KANSAI 0.00 / CHUBU 0.50
              mat=500 : 台地=1  KANTO 0.45 / KANSAI 0.00 / CHUBU 0.55
```

このノードは総量が固定なので、原料費を全市場に同額乗せても**最適配分は
動かないはず**である。動いたのは許容幅が縮んだからにすぎない。

### 実損

格子の真の最良点に替えたときの差（実測）:

```
oil・cap_wk=800  mat=6   : P_hier +2,187,558 円
                 mat=500 : P_hier +1,025,033 円
```

P_hier の 0.01% 程度。**小さい。** だから急ぐ話ではないが、意味の無い
基準で配分が決まっている状態は残したくない。

### 直すこと

**`best_point()` のシグネチャと返り値は変えない。** 台地は「意思決定の
自由度」の報告用として正しく、`plateau` の長さを assert しているテストも
ある（`test_allocation_grid.py:71-72`）。**壊す必要が無い。**

代わりに「**採用する1点**」を明示的な規則で選ぶ関数を足し、
**点を選んでいる呼び出し側だけ**をそちらに移す。

```
選ぶ規則: 格子の真の最良点（profit の argmax）
```

台地の重心を採る案もあるが、格子点でなくなるうえ「なぜその点か」の
説明が増える。**最良点なら説明が要らない**ので、まずこれで良い。

移す対象（`chosen = plateau[0]` 相当の箇所）:

```
wom/allocation/hierarchical_simplex.py:355      _descend() の chosen
wom/gui/s1_view_model.py:157 / 389 / 478        _walk_hierarchy / triangle / node
tools/run_planning_loop.py:131
tools/run_allocation_map.py:186 / 248
tools/plot_allocation_map.py:101 / 121 / 148 / 185
wom/allocation/merit_order.py:408
```

**全部が「点を選んでいる」とは限らない**——`plateau` の長さだけ使っている
箇所もある。Code君が1箇所ずつ見て、**選んでいる箇所だけ**を移すこと。
判断に迷うものがあれば、移さずに報告してほしい。

`s1_view_model.py` は GUI だが、ここは「計算」側（純関数）なので対象に含める。
`allocation_panel.py`（描画）は触らない。

### 回帰値

P_hier 系の値が動く。本書には新しい値を書かない。**測って報告してほしい。**

```
tests/test_allocation_hierarchical.py:171   hierarchy_gap 461,857.5
tests/test_allocation_hierarchical.py:329   hierarchy_gap 364,967,349.0
tests/test_allocation_hierarchical.py:325   r["profit"]   12,136,116,531.0
```

**`nodes == 10` / `points == 1_050` は構造なので不変のはず。**
golden 13ケースも不変のはず（A系統は PPC に効かない）——確認してほしい。

### 申し送りにすること（本 Phase では直さない）

`plateau_tol` が相対値なので、**台地サイズはシナリオ間で比較できない**
（同じ地形でも利益水準で 3 -> 1 と変わる）。S1 は台地サイズを画面に出して
いるので、これは表示の意味の問題でもある。**どう見せるかは Gate 1 で
大杉さんに聞く**——本 Phase では `plateau_tol` を触らないこと。

---

## E2. `tools/run_allocation_map.py:68` の `market == "US"`

```python
usd_rows = [r for r in rs if r["market"] == "US"]     # 3市場固定の決め打ち
```

USD の為替を引くために市場名 "US" を直接見ている。oil-global-2027 のように
`market_group` が leaf_out ノード名（`Retail_US_TX` 等）になる N市場モデルでは
一致しない。

**Phase 6 で潰した4件と同じ家族**——soysauce で偶然成立していたため露見
しなかった N市場非対応。Phase 8-1 で Code君が発見し、A系統「無変更」の制約下
だったため `s1_view_model.py` に `currency == "USD"` で引く独立ローダを
書いてもらった経緯がある。

### 直すこと

`run_allocation_map.py` の `load_scenarios()` を **`currency == "USD"`** 基準に
直す。既存の3市場サンプルとは後方互換のはず（soysauce は `market == "US"` の
行が `currency == "USD"` でもあるため）。

そのうえで、**`s1_view_model.py` の独立ローダを消すかどうかを判断してほしい。**
同じ処理が2箇所にある状態は、A5/A8 で潰した「フィルタを2箇所に置く」と
同じ家族である。ただし依存の向き（GUI が tools を import する）に問題が
無いか確認したうえで決めること。**消さない判断でもよい**——その場合は
理由を報告してほしい。

---

## E3. `tools/plot_allocation_merit_regime.py` の原料軸レンジ

```python
mat_values  = [4.0 + 0.5 * i for i in range(13)]        # 4.0..10.0
mark_points = [(150.0, 6.0, "base"), (200.0, 8.0, "shock")]
```

`--model-dir` を取る汎用ツールなのに、**原料軸のレンジとマーカーが
soysauce スケールで固定**されている。oil（基準 $500/kL）に向けると軸が
丸ごと2桁ずれた地図が描かれる。

Phase 8-1b で Code君が直したのは「どの値を使うか」（`base_scenario=sc` を
渡す）で、残っているのは「**どの範囲を描くか**」である。

### 直すこと

レンジとマーカーを**モデルの基準値から作る**。例えば基準
`sc.material_usd` の ±N% を13点、マーカーは基準点そのもの、という形。
倍率・点数は Code君の判断でよい。

soysauce（基準 6.0）で現行の 4.0..10.0 に近い範囲が出れば、既存の
`test_cli_demo_generates_all` は通るはずである。**通らなければ、範囲の
取り方を変えるか、テストの期待を更新するかを判断して報告してほしい。**

`fx_values = range(100, 221, 2)` は USD/JPY なのでモデル非依存。触らなくてよい。

---

## 1. 制約

- **GUI（`wom/gui/allocation_panel.py`）は触らない。** `s1_view_model.py` は
  計算側なので E1 の対象に含むが、描画側は対象外
- 禁足コア6ファイルは触らない
- golden 13ケース不変（A系統は PPC に効かないはず——確認してほしい）
- E1 / E2 / E3 は互いに独立。**1つずつ commit できる形にしてよい**

## 2. 完了条件

- 採用点が明示的な規則（格子の最良点）で選ばれ、`best_point()` は無変更
- `plateau` の長さを使っているだけの箇所は変えていない
- `run_allocation_map.py` が N市場モデルで動く
- 原料軸のレンジがモデルの基準値から作られる
- golden 13ケース不変、全テスト PASS（件数を報告）

## 3. 報告してほしいこと

1. E1 で「点を選んでいる」と判断した箇所と、「台地の長さだけ使っている」と
   判断した箇所の一覧。迷ったものがあればそれも
2. 動いた回帰値（3つ以上あるはず）
3. `s1_view_model.py` の独立ローダを消したか、残したか。その理由
4. E3 のレンジをどう作ったか。既存テストは通ったか
5. 最終テスト件数

回帰値は本書に書いていない。Code君が測った値を正典とする。
