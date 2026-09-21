---
tags: [wom, source]
---
# requests/Phase8-1_RequestLetter_to_CodeKun.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase8-1_RequestLetter_to_CodeKun.md) · [原文テキスト](../../90_Raw/requests/Phase8-1_RequestLetter_to_CodeKun.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Phase 8-1 実装 Request Letter — S1 Allocate（経営コックピットの最初の1画面）
- 概要
- 対象ファイル
- ⚠️ 絶対制約
- V1: `s1_view_model.py` — 画面に出す値を作る純関数（**本 Phase の要**）
- V1.1 結論行は木の全体を指す（設計書 rev.3 §4 S1 の要点(1)）
- V1.2 `plot_kind` の決め方（要点(2)(3)）
- V1.3 `surface` は再計算しない（要点の前提）
- V1.4 誤差は `P_opt − P_hier` で出す（要点(4)）
- V2: `allocation_panel.py` — 並べるだけ
- V2.1 レイアウト（設計書 rev.3 §4 S1）
- V2.2 「⚑ この配分で計画する」
- V2.3 Drill-down は1本だけ（枠組みの検証）
- V3: `app.py` への追加（**3行だけ**）
- V4: テスト仕様（新規6件）
- 成功基準
- 実装者への申し送り

## 関連する知識源

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/wom/gui/app.py|wom/gui/app.py]]
- [[80_Sources/tests/test_s1_view_model.py|tests/test_s1_view_model.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 8-1 実装 Request Letter — S1 Allocate（経営コックピットの最初の1画面）

**宛先**: Code君
**作成日**: 2026年9月12日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（GUI 刷新の最初の1歩。共通の枠組みをここで確定する）
**ブランチ**: `wom-v1r4m0`
**設計正典**: `requests/Phase8_DesignMD_CockpitGUI.md` rev.3 §3 / §4 S1
**前提**: Phase 7a 完了（`48f449b`、416件全PASS）

---

## 概要

経営コックピット（S0〜S5 の6画面）のうち、**S1 Allocate だけを作る。** 現行9タブは**1つも触らない**——**10枚目のタブとして足す**。

**なぜ1画面から始めるか。** 画面テンプレート・結論行・パンくず・Drill-down の開き方といった**共通の枠組み**を、1画面で検証してから横展開したい。6画面を一度に設計すると、枠組みの欠陥が6箇所に複製される。

**そして S1 は、大杉さんが挙げた「N市場の生産配分問題の可視化」そのものである。** Phase 6-3 で計算できるようになった階層化単体格子を、初めて画面にする。

```
現行:  Charts | KPI Table | At-Risk | Scenario Delta | Management | PPC | Network | World Map | Debug
本 Phase:                                                                                      ＋ Allocate
```

画面体系の入れ替え（S0〜S5 への再編）は **Phase 8-2 以降**。本 Phase では既存タブと**並存**させる。

### 対象ファイル

| ファイル | 扱い |
|---|---|
| `wom/gui/allocation_panel.py` | **新規**。`AllocationPanel(tk.Frame)` |
| `wom/gui/s1_view_model.py` | **新規**。画面に出す値を作る**純関数**（下記 V1） |
| `wom/gui/app.py` | **タブを1枚足すだけ**（`_build_right_panel` に3行）。既存パネルには一切触らない |
| `tests/test_s1_view_model.py` | 新規。**view model だけをテストする**（tkinter はテストしない） |
| 上記以外 | **無変更**（A系統・Planning Engine・PPC・禁足コア） |

---

## ⚠️ 絶対制約

- **C1**: matplotlib のみ（plotly 等の Web 系 GUI は情報セキュリティ上ありえない）
- **C2**: 新規依存なし（tkinter / matplotlib / 既存モジュールのみ）
- **C3**: 図の保存は `output/` 配下
- **C4（本 Phase で更新）**: **GUI 内の matplotlib は日本語可**。`app.py:31` で `matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]` が既に設定されている。**「図中テキストは全て英語」の制約は `tools/` の PNG 出力に対するもの**であり（`tools/plot_*.py` はフォントを設定していない＝豆腐化する）、GUI には及ばない。**GUI の軸ラベル・凡例・注記は日本語でよい**
- **C5**: 返却は Dict。**C6**: 禁足コア6ファイルに一切触れない
- **C7**: **乱数を使わない**
- **C8（本 Phase 固有）**: **既存9タブのコードを1行も変更しない。** `app.py` の変更は `_build_right_panel()` へのタブ追加3行のみ
- **C9（本 Phase 固有）**: **計算と描画を分ける。** 画面に出す値はすべて `s1_view_model.py` の純関数が作る。`allocation_panel.py` は**それを並べるだけ**。tkinter のコードの中で `scan_surface()` や `true_continuous_optimum()` を呼ばない

---

## V1: `s1_view_model.py` — 画面に出す値を作る純関数（**本 Phase の要**）

**tkinter は自動テストが難しい。だから「テストできる部分」と「できない部分」を先に切り分ける。**

```python
def build_s1_view(model_dir: str, *, scenario_id: str, cap_wk: float,
                  uom: Optional[str] = None,
                  node_path: Tuple[str, ...] = ()) -> dict:
    """S1 に出す値をすべて作る。tkinter に依存しない。

    node_path: 階層ドリルダウンでいま見ているノードへの経路。() はルート。
    """
```

返却:

```python
{
  "n_markets": 15,
  "mode": "hierarchy",              # "triangle"（N=3）| "hierarchy"（N>=4）

  "headline": {                     # 結論行。**木のどこにいても同じ**
    "recommended": {"JP": 0.10, "US": 0.45, "EU": 0.45},
    "profit": 135529822.5,
    "profit_source": "P_opt",
    "lines_ja": [                   # そのまま Label に流し込める日本語
      "推奨配分  US 45 / EU 45 / JP 10        利益 1.355 億（真の最適）",
      "格子の最良点との差 +340 万 = 全量が格子解像度。構造由来の取りこぼし 0",
      "ただし USD/JPY が 119 円を割ると EU 優先へ判断反転",
    ],
  },

  "levels": [                       # 補助パネル。**値の降順で並べ済み**
    {"name": "P_opt",    "value": 135529822.5, "highlight": False},
    {"name": "P_greedy", "value": 135529822.5, "highlight": False},
    {"name": "P_grid",   "value": 132133072.5, "highlight": False},
  ],
  "level_notes_ja": ["格子解像度の誤差 340 万", "構造由来の取りこぼし 0"],

  "breadcrumb": ["ALL", "JPY", "SP_Oil_Local"],   # mode=="triangle" なら []
  "node": {                         # いま見ているノード
    "name": "SP_Oil_Local",
    "children": ["KANTO", "KANSAI", "CHUBU"],
    "child_x": {"KANTO": 0.45, "KANSAI": 0.30, "CHUBU": 0.25},
    "cap_lots": 22314.0,            # 上位が確定したこの枝の能力
    "surface": [...],               # scan_hierarchical() の surfaces[node]
    "plot_kind": "triangle",        # "triangle"（子3）| "line"（子2）| "none"（子1）
  },

  "plateau_size": 1,
  "robust_point": {"x": (...), "worst_profit": ...},
  "reversal": {"axis": "fx_usd", "boundary": 119.0, "flips_to": "EU>US>JP"},
}
```

### V1.1 結論行は木の全体を指す（設計書 rev.3 §4 S1 の要点(1)）

**`node_path` を変えても `headline` と `levels` は変わらない。** 変わるのは `breadcrumb` と `node` だけである。

ノードを降りるたびに結論行の金額が変わると、**経営者が「いま見ている数字が全体なのか一部なのか」を見失う。** 居場所はパンくずが示す。

### V1.2 `plot_kind` の決め方（要点(2)(3)）

| 子の数 | `plot_kind` | 描くもの |
|---:|---|---|
| 3 | `"triangle"` | 直角三角図（231点）。従来の地形図 |
| 2 | `"line"` | **折れ線**。横軸 0→1（第2成分の比率）、縦軸 利益。21点 |
| 1 | `"none"` | 図を出さない。配分が一意 |

**子2を三角形に描かない。** 1次元単体を三角形に押し込むと潰れて読めない。`oil-global-2027` の15市場では **10ノード中6ノードが子2**——線分のほうが多数派である。

**子1のノードはパンくずに出さず素通りする**（`simplex_grid()` は `n_dim >= 2` しか作れない）。

### V1.3 `surface` は再計算しない（要点の前提）

`scan_hierarchical()` の返却の `surfaces[node_name]` を**そのまま渡す**。Phase 6-3 で `surfaces` を捨てずに保持したのは、この画面のためだった。**パネルの中で `scan_surface()` を呼ばない。**

`build_s1_view()` はモデル1つにつき**1回だけ** A系統を回し、結果をキャッシュしてよい（`node_path` が変わるたびに再計算しない）。

### V1.4 誤差は `P_opt − P_hier` で出す（要点(4)）

`mode == "hierarchy"` のとき、`level_notes_ja` に出すのは **`hierarchy_gap()["hierarchy_gap"]`**（常に 0 以上）である。

**`P_hier − P_flat` を画面に出さない。** 符号が定まらない（Phase 6-3 の15通り実測で勝ち6・分け3・負け6）。**符号の定まらない量を経営者に見せない。**

N≥7 では `P_flat` がそもそも計算できない（`hierarchy_gap()` が `None` を返す）。**`None` のときは行ごと出さない。**

---

## V2: `allocation_panel.py` — 並べるだけ

```python
class AllocationPanel(tk.Frame):
    def __init__(self, parent, app_ref=None, **kw): ...
    def _build(self): ...                 # ウィジェットの配置のみ
    def load(self, model_dir: str, scenario_id: str, cap_wk: float): ...
    def _render(self, view: dict): ...    # view を受け取って描くだけ
    def _on_breadcrumb_click(self, depth: int): ...
    def _on_child_click(self, child: str): ...
    def _on_commit(self): ...             # ⚑ この配分で計画する
```

### V2.1 レイアウト（設計書 rev.3 §4 S1）

```
┌ 結論行（tk.Label ×3・日本語・太字）──────────────────────────────────────┐
├ パンくず（mode=="hierarchy" のときだけ）─────────────────────────────────┤
│ ALL ▸ JPY ▸ SP_Oil_Local                            [▲ 1つ上へ]          │
├ 根拠（FigureCanvasTkAgg）────────────┬ 補助（tk.Frame）──────────────────┤
│  plot_kind に従って描く              │ 3つの利益水準（降順・levels）     │
│                                      │ 子ノード一覧（クリックで降りる）  │
│                                      │ このノードの能力 / 台地サイズ     │
├ 操作 ────────────────────────────────┴───────────────────────────────────┤
│ 配分: ◉ 真の最適(P_opt) ○ ロバスト点 ○ 手入力 [__/__/__]                  │
│       ⚑ この配分で計画する                                                │
└──────────────────────────────────────────────────────────────────────────┘
```

**既存パネルの見た目に合わせること**（`BG_DARK` / `BG_MID` / `FG_WHITE`、`font=("Segoe UI", 9)`）。日本語ラベルは `("Yu Gothic UI", 9)` を使ってよい。

### V2.2 「⚑ この配分で計画する」

押したら **Phase 7 の API を呼ぶだけ**。ここで新しいロジックを書かない。

```python
from wom.planning_state import new_state, save
state = new_state(case, scenario_id, allocation, profit_levels,
                  reversal=view["reversal"])
path = save(state)
```

**本 Phase では `demand_forecast_<id>.csv` の生成と Planning Engine の実行までは行わない。** `pre_plan` の Planning State を1本作って、パスをステータス行に出すところまで。**S2 以降の画面が無いのに層をまたいで走らせても、結果を見る場所が無い。**

### V2.3 Drill-down は1本だけ（枠組みの検証）

`[メリットオーダー曲線]` ボタンを1つだけ置き、**別ウィンドウ**（`tk.Toplevel` ＋ `FigureCanvasTkAgg`）で開く。設計書 R4 の「別ウィンドウを既定」を、ここで実際に確かめる。

**Regime Map / Merit Order Shift / Layers は Phase 8-2 に送る。** 1本で開き方の型が決まれば、残りは同じ型の繰り返しである。

---

## V3: `app.py` への追加（**3行だけ**）

```python
        self._alloc_panel = AllocationPanel(nb, app_ref=self)
        nb.add(self._alloc_panel, text="  \U0001f5fa Allocate  ")   # 絵文字は要相談
```

**置く位置は `Charts` の前**（第1層の画面なので先頭が理屈に合う）。ただし `nb.select(self._worldmap_panel)` の初期表示は**変えない**——既存利用者の体験を変えないため。

**それ以外の行に触らない（C8）。**

---

## V4: テスト仕様（新規6件）

**`tests/test_s1_view_model.py`。tkinter はテストしない。**

1. `test_view_triangle_mode_soysauce` — soysauce 3市場で `mode == "triangle"`、`breadcrumb == []`、`headline.profit == 135_529_822.5`（±1円）、`profit_source == "P_opt"`
2. `test_levels_sorted_desc` — `levels` が**値の降順**。soysauce `s1_base` で `P_opt ≥ P_greedy ≥ P_grid`、`s9_fta_cliff` で **`P_greedy` が最下段**に落ち `highlight == True` になること
3. `test_headline_is_invariant_across_nodes`（**最重要**）— oil 15市場で `node_path` を `()` → `("JPY",)` → `("JPY","SP_Oil_Local")` と変えても、**`headline` と `levels` が完全に同一**であること
4. `test_plot_kind_by_child_count` — oil 15市場の全10ノードで、子3→`"triangle"`、子2→`"line"`。**`"line"` が6ノード**であること
5. `test_no_flat_comparison_in_view` — 返却のどこにも `P_flat` との比較（`hier_minus_flat` 等）が**含まれない**こと。`level_notes_ja` の文字列にも「平坦」「格子全数」が出ないこと
6. `test_surface_is_not_recomputed` — `build_s1_view()` が `scan_surface` / `scan_hierarchical` を**1回しか呼ばない**こと（`unittest.mock` で回数を数える）

**回帰値は 1・2 以外は本書で指定しない。** 実装で決まるので、測って報告してもらい、それを正典とする。

---

## 成功基準

- [ ] 既存9タブのコードが1行も変わっていない
- [ ] soysauce（N=3）で三角図と結論行が出る
- [ ] `oil-global-2027`（`uom="KL"` の15市場）で階層ドリルダウンが動き、**降りても結論行が変わらない**
- [ ] 子2のノードが**線分**で描かれる
- [ ] 画面のどこにも `P_hier − P_flat` が出ない
- [ ] 「⚑ この配分で計画する」で `pre_plan` の Planning State が1本できる
- [ ] メリットオーダー曲線が別ウィンドウで開く
- [ ] golden 13ケース・Phase 4/5/6/7 の全回帰値が不変
- [ ] **422件全PASS**（既存416 + 新規6）

---

## 実装者への申し送り

**1. 計算と描画を分けること（C9）。**
tkinter のコードの中で A系統を呼び始めると、**テストできない場所にロジックが溜まる**。`build_s1_view()` が全部の値を作り、パネルは並べるだけ。本 Phase の価値の半分はこの切り分けにある。

**2. GUI の図中は日本語でよい（C4）。**
`app.py:31` で `Yu Gothic` が設定済みである。「図中テキストは全て英語」は `tools/` の PNG 出力に対する制約であって（`tools/plot_*.py` はフォント未設定＝豆腐化する）、GUI には及ばない。**この区別を docstring に書いておくこと**——次に触る人が GUI でも英語にしてしまわないように。

**3. 結論行の不変性はテストで固定すること（V4.3）。**
「降りても結論行が変わらない」は設計の要点であり、実装では**うっかり変えやすい**（ノードごとの利益を計算して出したくなる）。テストで杭を打つ。

**4. `P_flat` との比較を画面に出さないこと（V1.4）。**
実装していると「せっかく計算できるなら出したい」となるが、**符号が定まらない量**である。Phase 6-3 で15通り測って勝ち6・分け3・負け6だった。`gap_amt` で同じ落とし穴を踏んでいる。

**5. 本 Phase では層をまたがないこと（V2.2）。**
「⚑」で Planning State を1本作るまで。`demand_forecast_<id>.csv` の生成も Planning Engine の実行も Phase 8-2 以降。S2 以降の画面が無いのに走らせても、結果を見る場所が無い。

**6. 絵文字とタブ名は仮でよい。**
`Allocate` というタブ名も含め、大杉さんが実機で見てから決める。**実装を止めないこと。**

````
