---
tags: [wom, code]
---
# tests/test_gui_panel_invariants.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_gui_panel_invariants.py) · [原文テキスト](../../90_Raw/tests/test_gui_panel_invariants.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## モジュール説明（docstring原文）

```text
tests/test_gui_panel_invariants.py — Gate 0: GUI の Anti-Degrade 網
================================================================================
正典: requests/Gate0_RequestLetter_GuiSmokeTests_to_CodeKun.md

`AllocationPanel`（S1 Allocate タブ）を headless に近い形で実体化し、代表的な
6状態を通しながら**構造として壊れていないか**だけを検査する（条件7のみ、
描画結果の警告を見る例外——Phase 8-3a 追補参照。条件8は Phase 8-3b 追補の
追補で追加、view とパネルの描画整合を見る）。

**この網は意味を判定しない。** 「この数字が経営者にどう読めるか」は対象外。
検査するのは汎用の不変条件だけであり、特定の市場名・特定の node_path を
「あるべきもの」として名指ししない——次の画面（S3/S4/S5）でも同じテストが
そのまま鳴ることが、この網の価値である。

## Tk のウィンドウ表示について

`root.withdraw()` だけでは pack 済み子ウィジェットの実サイズが計算されない
（Windows で実測: 幅・高さが 1 のまま返る）。かといって画面中央に実際に表示すると
テスト実行のたびにウィンドウがちらつく。そこで、ウィンドウを**画面外の座標へ配置
した状態で実際に mapped（表示）にする**——`geometry("WxH+-3000+-3000")`。
これで実サイズが正しく計算され、リサイズに追従する `<Configure>` ハンドラも
実際に発火する（`root.withdraw()` 後は Configure が発火しないことを実測で確認済み）。

## `tk.Tk()` 生成の不安定さについて（実機で確認・本ファイル固有の対処ではない）

このマシン(Windows・anaconda3 の Tcl/Tk)では、同一プロセス内で `tk.Tk()` を
2回連続で作るだけで、時々（実測で 5 回に 4 回程度）
`Can't find a usable init.tcl` という `TclError` が出ることを、6状態を1個の
module-scope フィクスチャで使い回す実装を試した際に確認した。10行程度の
再現コード（`tk.Tk()` を1回 作って `destroy()` し、直後にもう一度 `tk.Tk()` を
作るだけ）でも同じ頻度で再現したため、**この網の作りが悪いのではなく、この
マシンの Tcl 初期化そのものがレースを持っている**と判断した（おそらく
`init.tcl` を含むフォルダがクラウド同期等で間欠的に読めなくなる類のもの）。

そのため、状態ごとに `tk.Tk()` を作り直す設計は変えず(このほうが1個の root を
使い回すよりも実測で安定した)、`tk.Tk()` の生成だけをリトライする
`_new_tk_root()` でくるむ。**アプリ本体側のコードは一切変更しない**——これは
テストの生成ヘルパー内だけの対処であり、`wom/` `tools/` には触れない。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_new_tk_root` | 77 | `tk.Tk()` をリトライ付きで作る(このマシン固有の init.tcl レース対策。 |
| FunctionDef | `_display_available` | 94 | docstringなし（下のコード参照） |
| FunctionDef | `_build_view` | 145 | docstringなし（下のコード参照） |
| FunctionDef | `_make_panel` | 153 | view を描いた `AllocationPanel` を、画面外に mapped した Tk root ごと返す。 |
| FunctionDef | `_iter_widgets` | 176 | docstringなし（下のコード参照） |
| FunctionDef | `test_fits_within_default_window` | 187 | docstringなし（下のコード参照） |
| FunctionDef | `test_headline_lines_not_too_long` | 226 | docstringなし（下のコード参照） |
| FunctionDef | `test_info_panels_not_empty` | 246 | docstringなし（下のコード参照） |
| FunctionDef | `test_descendable_rows_are_bound` | 270 | 「子を出すなら」が条件——「USD の子を出せ」ではない(Request Letter §2-4)。 |
| FunctionDef | `test_wraplength_follows_resize` | 305 | docstringなし（下のコード参照） |
| FunctionDef | `test_renders_without_exception` | 329 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_has_no_missing_glyph_warnings` | 350 | docstringなし（下のコード参照） |
| FunctionDef | `test_levels_block_matches_view` | 374 | docstringなし（下のコード参照） |
| FunctionDef | `_make_panel_for_navigation` | 410 | `load()` を使って遷移を実際に歩かせるためのパネル生成。 |
| FunctionDef | `_children_frame_y` | 428 | docstringなし（下のコード参照） |
| FunctionDef | `_assert_levels_block_consistent` | 432 | 条件8を遷移の上で再掲する部分（Request Letter §M2 の (1)(2)）。 |
| FunctionDef | `test_children_frame_position_is_stable_across_navigation` | 444 | docstringなし（下のコード参照） |
| FunctionDef | `s3_run_result` | 501 | docstringなし（下のコード参照） |
| FunctionDef | `_make_s3_panel` | 523 | `RunPanel` を作り、view を注入して描かせる（`_make_panel()` と同じ形）。 |
| FunctionDef | `test_s3_fits_within_default_window` | 546 | 条件1: そのまま効く。 |
| FunctionDef | `test_s3_headline_lines_not_too_long` | 566 | 条件2: 一部だけ効く。結論行3行の文字数上限は S3 にも意味があるが、 |
| FunctionDef | `test_s3_evidence_panel_not_empty` | 578 | 条件3: そのまま効く（根拠パネル側のみ——補助パネルの「実行の結果」は |
| FunctionDef | `test_s3_node_rows_are_bound` | 594 | 条件4の類型: そのまま同じ形で効く。S3 には木のドリルダウンは無いが、 |
| FunctionDef | `test_s3_renders_without_exception` | 610 | 条件6: そのまま効く。 |
| FunctionDef | `test_s3_plot_has_no_missing_glyph_warnings` | 621 | 条件7: そのまま効く。 |
| FunctionDef | `test_s3_result_block_matches_view` | 633 | 条件8の類型: そのまま同じ形で効く。S1 の「levels/level_notes_ja が |
| FunctionDef | `_assert_no_row_looks_clickable_without_bind` | 676 | docstringなし（下のコード参照） |
| FunctionDef | `test_children_rows_do_not_look_descendable_without_bind` | 687 | Q1 が直す前は triangle_n3 でこれが落ちる（fg=FG_ACC・cursor=hand2 だが |
| FunctionDef | `test_s3_node_rows_do_not_look_clickable_without_bind` | 699 | 条件10の S3 への移植。S3 の能力ノード一覧は全行が実際に選択操作を |
| FunctionDef | `test_s3_axis_labels_follow_declared_series_kind` | 722 | docstringなし（下のコード参照） |
| FunctionDef | `test_s3_shortfall_line_follows_selected_node` | 754 | 供給不足で処理量が凹んだ週は、図の上では能力で縛られた凹みと同じ形に |

## 関連する知識源

- [[80_Sources/requests/Gate0_RequestLetter_GuiSmokeTests_to_CodeKun.md|requests/Gate0_RequestLetter_GuiSmokeTests_to_CodeKun.md]]
- [[80_Sources/wom/gui/app.py|wom/gui/app.py]]
- [[80_Sources/wom/cockpit/s1_view_model.py|wom/cockpit/s1_view_model.py]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]
- [[80_Sources/wom/cockpit/s3_view_model.py|wom/cockpit/s3_view_model.py]]
- [[80_Sources/wom/cockpit/s3_run.py|wom/cockpit/s3_run.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
tests/test_gui_panel_invariants.py — Gate 0: GUI の Anti-Degrade 網
================================================================================
正典: requests/Gate0_RequestLetter_GuiSmokeTests_to_CodeKun.md

`AllocationPanel`（S1 Allocate タブ）を headless に近い形で実体化し、代表的な
6状態を通しながら**構造として壊れていないか**だけを検査する（条件7のみ、
描画結果の警告を見る例外——Phase 8-3a 追補参照。条件8は Phase 8-3b 追補の
追補で追加、view とパネルの描画整合を見る）。

**この網は意味を判定しない。** 「この数字が経営者にどう読めるか」は対象外。
検査するのは汎用の不変条件だけであり、特定の市場名・特定の node_path を
「あるべきもの」として名指ししない——次の画面（S3/S4/S5）でも同じテストが
そのまま鳴ることが、この網の価値である。

## Tk のウィンドウ表示について

`root.withdraw()` だけでは pack 済み子ウィジェットの実サイズが計算されない
（Windows で実測: 幅・高さが 1 のまま返る）。かといって画面中央に実際に表示すると
テスト実行のたびにウィンドウがちらつく。そこで、ウィンドウを**画面外の座標へ配置
した状態で実際に mapped（表示）にする**——`geometry("WxH+-3000+-3000")`。
これで実サイズが正しく計算され、リサイズに追従する `<Configure>` ハンドラも
実際に発火する（`root.withdraw()` 後は Configure が発火しないことを実測で確認済み）。

## `tk.Tk()` 生成の不安定さについて（実機で確認・本ファイル固有の対処ではない）

このマシン(Windows・anaconda3 の Tcl/Tk)では、同一プロセス内で `tk.Tk()` を
2回連続で作るだけで、時々（実測で 5 回に 4 回程度）
`Can't find a usable init.tcl` という `TclError` が出ることを、6状態を1個の
module-scope フィクスチャで使い回す実装を試した際に確認した。10行程度の
再現コード（`tk.Tk()` を1回 作って `destroy()` し、直後にもう一度 `tk.Tk()` を
作るだけ）でも同じ頻度で再現したため、**この網の作りが悪いのではなく、この
マシンの Tcl 初期化そのものがレースを持っている**と判断した（おそらく
`init.tcl` を含むフォルダがクラウド同期等で間欠的に読めなくなる類のもの）。

そのため、状態ごとに `tk.Tk()` を作り直す設計は変えず(このほうが1個の root を
使い回すよりも実測で安定した)、`tk.Tk()` の生成だけをリトライする
`_new_tk_root()` でくるむ。**アプリ本体側のコードは一切変更しない**——これは
テストの生成ヘルパー内だけの対処であり、`wom/` `tools/` には触れない。
"""
from __future__ import annotations

import os
import sys
import time
import warnings
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

tk = pytest.importorskip("tkinter")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SAMPLE_DIR = os.path.join(REPO_ROOT, "data", "sample")
ALLOC_DIR = os.path.join(SAMPLE_DIR, "soysauce-jpy-2027-alloc")
OIL_DIR = os.path.join(SAMPLE_DIR, "oil-global-2027")

# 現行の実測値: lines_ja 最大 98 文字、full_allocation_ja 最大 224 文字
# （実測、2026-09-17。oil-global-2027・15市場相当）。
# 「同じ検査にかける」（Request Letter §2 条件2）にあたり、両者は役割が違うため
# 同一の閾値は使わない——full_allocation_ja は Phase 8-2・C3.3 で「畳まず全市場を
# 出す控え」として意図的に設計されており、lines_ja より長くなるのが正しい。
# それぞれに実測値へ十分な余裕を持たせた閾値を設ける。
_HEADLINE_MAX_CHARS = 160
_FULL_ALLOCATION_MAX_CHARS = 480

_GEOMETRY = "1280x820"
_OFFSCREEN = "+-3000+-3000"   # 画面外に配置し、ちらつかせずに実サイズを得る
_TK_CREATE_RETRIES = 5
_TK_CREATE_RETRY_DELAY_SEC = 0.2


def _new_tk_root(geometry: str = _GEOMETRY):
    """`tk.Tk()` をリトライ付きで作る(このマシン固有の init.tcl レース対策。
    モジュール docstring 参照)。"""
    last_err = None
    for _ in range(_TK_CREATE_RETRIES):
        try:
            root = tk.Tk()
        except tk.TclError as e:   # noqa: PERF203 — リトライ自体が目的
            last_err = e
            time.sleep(_TK_CREATE_RETRY_DELAY_SEC)
            continue
        root.geometry(geometry + _OFFSCREEN)
        return root
    raise RuntimeError(
        f"tk.Tk() failed after {_TK_CREATE_RETRIES} retries: {last_err}")


def _display_available() -> bool:
    try:
        probe = _new_tk_root()
    except RuntimeError:
        return False
    probe.destroy()
    return True


if not _display_available():
    pytest.skip("no display available for tkinter", allow_module_level=True)


# ---------------------------------------------------------------------------
# 6状態（Request Letter §2 の表そのもの）
# ---------------------------------------------------------------------------

STATES = [
    pytest.param(
        dict(model_dir=ALLOC_DIR, scenario_id="s1_base", cap_wk=800.0,
             uom=None, node_path=()),
        id="triangle_n3",
    ),
    pytest.param(
        dict(model_dir=OIL_DIR, scenario_id="s1_base", cap_wk=800.0,
             uom="KL", node_path=()),
        id="hierarchy_root",
    ),
    pytest.param(
        dict(model_dir=OIL_DIR, scenario_id="s1_base", cap_wk=800.0,
             uom="KL", node_path=("EUR",)),
        id="hierarchy_mid",
    ),
    pytest.param(
        dict(model_dir=OIL_DIR, scenario_id="s1_base", cap_wk=800.0,
             uom="KL", node_path=("USD",)),
        id="hierarchy_zero_alloc_branch",
    ),
    pytest.param(
        dict(model_dir=OIL_DIR, scenario_id="s1_base", cap_wk=800.0,
             uom="KL", node_path=("JPY", "SP_Oil_Local", "Retail_Local_KANTO")),
        id="leaf_shipped",
    ),
    pytest.param(
        dict(model_dir=OIL_DIR, scenario_id="s1_base", cap_wk=800.0,
             uom="KL", node_path=("USD", "SP_Oil_US_Local", "Retail_US_TX")),
        id="leaf_zero_shipped",
    ),
]


def _build_view(state: dict) -> dict:
    from wom.cockpit.s1_view_model import build_s1_view

    return build_s1_view(
        state["model_dir"], scenario_id=state["scenario_id"], cap_wk=state["cap_wk"],
        uom=state["uom"], node_path=state["node_path"])


def _make_panel(view: dict):
    """view を描いた `AllocationPanel` を、画面外に mapped した Tk root ごと返す。

    呼び出し側は必ず `root.destroy()` すること。
    """
    from wom.cockpit.s1_allocate import AllocationPanel

    root = _new_tk_root()
    panel = AllocationPanel(root)
    panel.pack(fill="both", expand=True)
    # AllocationPanel.load() はモデルをファイルから読み直すため、ここでは
    # 呼び出し側が計算済みの view を直接描かせる（_render_children() の
    # hierarchy 判定が self._view を読むため、先にセットしておく）。
    panel._view = view
    panel._render(view)
    # 実測: オフスクリーン配置直後の1回の update() だけでは、深くネストした
    # ウィジェット（matplotlib canvas 配下等）の実ジオメトリが確定しないことが
    # あった。2回呼ぶことで安定する。
    root.update()
    root.update_idletasks()
    return root, panel


def _iter_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _iter_widgets(child)


# ---------------------------------------------------------------------------
# 条件1: 既定サイズに収まる（D3 class）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_fits_within_default_window(state):
    view = _build_view(state)
    root, panel = _make_panel(view)
    try:
        # 座標は root ではなく panel を基準にする(root.winfo_rootx/y() は
        # 実機で OS のウィンドウ配置が非同期に反映されるため、root と個々の
        # 子ウィジェットの rootx/y を別々の瞬間の値として比較すると、オフ
        # スクリーン配置直後にまれに数千px ずれた値になることを実測で確認した。
        # panel 自身は `pack(fill="both", expand=True)` で root の全クライアント
        # 領域を占めるので、「panel の原点からの相対座標」で見れば window の
        # 内側に収まっているかどうかを同じ基準で判定できる)。
        win_w = panel.winfo_width()
        win_h = panel.winfo_height()
        assert win_w > 1 and win_h > 1, "panel did not receive real geometry"
        for w in _iter_widgets(panel):
            if w is panel:
                continue
            if not w.winfo_ismapped():
                # pack_forget() 済みのウィジェット（triangle モードの
                # breadcrumb_frame 等）は画面に出ていないので対象外
                # ——出ていないものは「窓からはみ出す」対象になり得ない。
                continue
            x = w.winfo_rootx() - panel.winfo_rootx()
            y = w.winfo_rooty() - panel.winfo_rooty()
            width = w.winfo_width()
            height = w.winfo_height()
            assert x + width <= win_w + 2, (
                f"{w} extends right of window: x={x} width={width} win_w={win_w}")
            assert y + height <= win_h + 2, (
                f"{w} extends below window: y={y} height={height} win_h={win_h}")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件2: 結論行・全市場控え欄が長すぎない（C3 class）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_headline_lines_not_too_long(state):
    view = _build_view(state)
    lines = view["headline"]["lines_ja"]
    assert lines, "headline lines_ja is empty"
    for line in lines:
        assert len(line) <= _HEADLINE_MAX_CHARS, (
            f"headline line too long ({len(line)} chars, limit {_HEADLINE_MAX_CHARS}): "
            f"{line!r}")

    full = view["headline"]["full_allocation_ja"]
    assert len(full) <= _FULL_ALLOCATION_MAX_CHARS, (
        f"full_allocation_ja too long ({len(full)} chars, "
        f"limit {_FULL_ALLOCATION_MAX_CHARS}): {full!r}")


# ---------------------------------------------------------------------------
# 条件3: 情報欄が空でない（C4 class）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_info_panels_not_empty(state):
    view = _build_view(state)
    root, panel = _make_panel(view)
    try:
        # 補助パネル（node_info_label 相当）
        assert panel._node_info_label.cget("text") != "", (
            "node_info_label is empty")

        # 根拠パネル（図または代替メッセージ）: axes に何らかの描画要素があること
        axes = panel._fig.get_axes()
        assert axes, "figure has no axes after render"
        ax = axes[0]
        has_content = bool(ax.texts) or bool(ax.lines) or bool(ax.patches) \
            or bool(ax.collections) or bool(ax.containers)
        assert has_content, "plot axes has no text/lines/patches/collections"
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件4: 降りられる枝にはバインドがある（D1 class）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_descendable_rows_are_bound(state):
    """「子を出すなら」が条件——「USD の子を出せ」ではない(Request Letter §2-4)。

    triangle モードは元々ドリルダウンが無い(N=3 で全体が最初から見えている)ため
    対象外。hierarchy モードで、いま見ているノードが葉でない(children を持つ)
    ときだけ、children_frame の中のどこかに Button-1 バインドがあることを検査する。
    is_unallocated (配分ゼロの枝)でも、Phase 8-2a・D1 の設計どおり降りる手段は
    残っているはずなので、is_unallocated の有無では条件を変えない。
    """
    view = _build_view(state)
    if view["mode"] != "hierarchy":
        pytest.skip("triangle mode has no drill-down to bind")
    node = view["node"]
    if not node["children"]:
        pytest.skip("leaf node has no children to descend into")

    root, panel = _make_panel(view)
    try:
        bound = False
        for row in panel._children_frame.winfo_children():
            for w in _iter_widgets(row):
                if w.bind("<Button-1>"):
                    bound = True
        assert bound, (
            f"hierarchy node {node['name']!r} has children but no descendable "
            f"(Button-1 bound) row")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件5: リサイズに追従する（D2 class）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", STATES)
def test_wraplength_follows_resize(state):
    view = _build_view(state)
    root, panel = _make_panel(view)
    try:
        before = panel._full_allocation_label.cget("wraplength")
        root.geometry("900x820" + _OFFSCREEN)
        root.update()
        after = panel._full_allocation_label.cget("wraplength")
        assert after != before, (
            f"full_allocation_label wraplength did not follow resize "
            f"(before={before}, after={after})")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件6: 例外なく描ける
# ---------------------------------------------------------------------------
# 上の各テストが _build_view()/_make_panel() を呼ぶ時点で例外が出れば pytest が
# 失敗として報告するため、専用のアサーションは不要——ここでは「全状態を1回ずつ
# 通しても例外が出ない」ことだけを独立したテストとして明示する(既存テストが
# 個別に落ちても、この統合テストの意図が読み取れるようにするため)。

@pytest.mark.parametrize("state", STATES)
def test_renders_without_exception(state):
    view = _build_view(state)
    root, panel = _make_panel(view)
    try:
        assert panel._view is view
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件7: 日本語を含む図が豆腐にならない（Phase 8-3a 追補）
# ---------------------------------------------------------------------------
# コックピット移設直後、日本語フォント設定（`matplotlib.rcParams["font.family"]`）
# を `wom/gui/app.py` の import 時設定に頼ったまま持ち出しており、`app.py` を
# import しないコックピットでは効かず、図中の日本語が豆腐化していた
# （`UserWarning: Glyph ... missing from font(s) DejaVu Sans`）。この欠陥は
# 描画結果を見て初めて分かるもので、既存の6条件（構造だけを見る）では鳴らない
# ——matplotlib が glyph 不足を検出すると必ず `UserWarning` を出すことを使い、
# 描画時の警告を捕まえる形で検査する。

@pytest.mark.parametrize("state", STATES)
def test_plot_has_no_missing_glyph_warnings(state):
    view = _build_view(state)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        root, panel = _make_panel(view)
        try:
            pass
        finally:
            root.destroy()
    tofu = [str(w.message) for w in caught if "missing from font" in str(w.message)]
    assert not tofu, f"glyph(s) missing from configured font (tofu): {tofu}"


# ---------------------------------------------------------------------------
# 条件8: view の levels と、描画された行数が一致する（Phase 8-3b 追補の追補）
# ---------------------------------------------------------------------------
# Phase 8-3b 追補・K2 で「levels はルートだけが持ち、子ノードでは空にする」
# という分岐を入れた。これは条件1〜7のどれも見ていない盲点だった——将来
# うっかり「根でも隠す」ように壊しても、既存条件は何も鳴らない。
# 「view が levels を返すならパネルにその行が描かれる。返さないなら描かれない」
# という、特定の画面を名指ししない汎用の整合性検査を足す（条件4「子を出すなら
# バインドを持つ」と同じ形）。S3 以降で似た分岐が増えても、この条件はそのまま効く。

@pytest.mark.parametrize("state", STATES)
def test_levels_block_matches_view(state):
    view = _build_view(state)
    root, panel = _make_panel(view)
    try:
        rendered_rows = len(panel._levels_frame.winfo_children())
        expected_rows = len(view["levels"])
        assert rendered_rows == expected_rows, (
            f"panel rendered {rendered_rows} levels row(s) but view provided "
            f"{expected_rows}")
        assert panel._levels_header_visible == bool(view["levels"]), (
            f"levels_header_visible={panel._levels_header_visible} but "
            f"view['levels'] has {len(view['levels'])} entries")
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件9: 遷移を通す（Phase 8-3b-3・M2）
# ---------------------------------------------------------------------------
# 条件1〜8はすべて「新しいパネルを作って1回だけ描く」形だった。K2（Phase 8-3b
# 追補）が入れた `_levels_header_visible` の状態機械は、根→子→根と実際に
# 遷移して初めて両方の経路（pack_forget と pack(before=...)）を通る——
# 条件8は「回帰で示された」と一度判断されたが、それも1回描いたときの整合しか
# 見ておらず、実際には塞げていなかった（Request Letter §0）。
#
# 実機で起きたのは、条件つき（利益水準ブロック）を常時ブロック（子ノード欄）の
# 上に置いていたため、利益水準が消えるたびにクリック対象が約200px 跳ね上がり、
# 「ドリルダウン機能が削除された」と誤解されたことだった。本条件は
# 「ドリルダウンしてもクリック対象(子ノード欄)は動かない」という不変条件を、
# 実際に load() → _on_child_click() → _on_up_click() で歩かせて検査する。
#
# 特定の市場名・特定の node_path は名指ししない——children[0] を辿るだけに
# する。triangle モードはドリルダウンが無いので対象外（hierarchy のみ）。
# 期待する y の値は書かない（画面が変われば変わる値を正典にしない）——
# 「最初の段で得た値と同じであり続ける」ことだけを見る。

def _make_panel_for_navigation(model_dir: str, scenario_id: str, cap_wk: float,
                               uom: Optional[str] = None):
    """`load()` を使って遷移を実際に歩かせるためのパネル生成。

    `_make_panel()`（view を直接注入して1回だけ描く、条件1〜8用）とは別にする
    ——既存条件の挙動を動かさないため（Request Letter §M2「対象」）。
    """
    from wom.cockpit.s1_allocate import AllocationPanel

    root = _new_tk_root()
    panel = AllocationPanel(root)
    panel.pack(fill="both", expand=True)
    panel.load(model_dir, scenario_id, cap_wk, uom=uom)
    root.update()
    root.update_idletasks()
    return root, panel


def _children_frame_y(panel) -> int:
    return panel._children_frame.winfo_rooty() - panel.winfo_rooty()


def _assert_levels_block_consistent(panel, ctx: str) -> None:
    """条件8を遷移の上で再掲する部分（Request Letter §M2 の (1)(2)）。"""
    rendered_rows = len(panel._levels_frame.winfo_children())
    expected_rows = len(panel._view["levels"])
    assert rendered_rows == expected_rows, (
        f"[{ctx}] panel rendered {rendered_rows} levels row(s) but view provided "
        f"{expected_rows}")
    assert panel._levels_header_visible == bool(panel._view["levels"]), (
        f"[{ctx}] levels_header_visible={panel._levels_header_visible} but "
        f"view['levels'] has {len(panel._view['levels'])} entries")


def test_children_frame_position_is_stable_across_navigation():
    root, panel = _make_panel_for_navigation(OIL_DIR, "s1_base", 800.0, uom="KL")
    try:
        _assert_levels_block_consistent(panel, "root")
        y0 = _children_frame_y(panel)

        # 根から、常に先頭の子を選んで葉まで降りる
        depth = 0
        while panel._view["node"]["children"]:
            first_child = panel._view["node"]["children"][0]
            panel._on_child_click(first_child)
            root.update()
            root.update_idletasks()
            depth += 1
            y = _children_frame_y(panel)
            assert y == y0, (
                f"[down depth={depth}] children_frame y jumped: first={y0} now={y}")
            _assert_levels_block_consistent(panel, f"down depth={depth}")
            if depth > 10:   # 無限降下の暴走防止（実ツリーは数段のはず）
                raise AssertionError("descended more than 10 levels; tree may be malformed")
        assert depth > 0, "oil model should have at least one level to descend into"

        # 葉から根まで、実際に1つ上へを繰り返して戻る
        for step in range(depth):
            panel._on_up_click()
            root.update()
            root.update_idletasks()
            y = _children_frame_y(panel)
            assert y == y0, (
                f"[up step={step + 1}] children_frame y jumped: first={y0} now={y}")
            _assert_levels_block_consistent(panel, f"up step={step + 1}")

        assert panel._node_path == (), "should be back at ALL after walking all the way up"
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# S3 Run（Phase 8-3c・N8）: 2枚目の画面で、条件1〜9が本当に汎用かを確かめる
# ---------------------------------------------------------------------------
# 条件1〜9は「特定の画面を名指ししない汎用の不変条件」として書いてきたが、
# それが本当かどうかは2枚目の画面が出るまで分からなかった（Request Letter
# §N8）。**効かない条件があってもそれ自体は失敗ではない**——S1 固有の前提が
# 混じっていたという発見であり、黙って S3 だけ除外しない（下の一覧表で報告する）。
#
# `run_s3()` は 4〜9秒かかる（headless の Planning+PPC が大半）ため、
# module 内で**1回だけ**計算し、複数の条件テストで使い回す（`s3_run_result`
# フィクスチャ）。副作用ファイル（`demand_forecast_<id>.csv` が実際のサンプル
# モデルフォルダに書かれる）は teardown で削除する。

S3_ALLOC_DIR = ALLOC_DIR   # soysauce（triangle）で足りる——S3 はモデルの木の形を見ない
S3_SCENARIO_ID = "s1_base"
S3_CAP_WK = 800.0
S3_TEST_ALLOCATION_ID = "GATE0S3PROBE"


@pytest.fixture(scope="module")
def s3_run_result():
    from wom.cockpit.s1_view_model import build_s1_view, evaluate_allocation
    from wom.cockpit.s3_view_model import run_s3
    import wom.planning_state as planning_state

    v = build_s1_view(S3_ALLOC_DIR, scenario_id=S3_SCENARIO_ID, cap_wk=S3_CAP_WK)
    allocation = dict(v["headline"]["recommended"])
    profit_levels = dict(v["profit_levels"])
    profit_levels["source"] = "P_opt"
    plan_eval = evaluate_allocation(S3_ALLOC_DIR, S3_SCENARIO_ID, S3_CAP_WK, allocation)
    pre_plan_state = planning_state.new_state(
        os.path.basename(S3_ALLOC_DIR), S3_SCENARIO_ID, allocation, profit_levels,
        plan_eval, allocation_id=S3_TEST_ALLOCATION_ID, reversal=v["reversal"])

    result = run_s3(S3_ALLOC_DIR, S3_SCENARIO_ID, S3_CAP_WK, pre_plan_state)
    yield pre_plan_state, result

    demand_csv = os.path.join(S3_ALLOC_DIR, f"demand_forecast_{S3_TEST_ALLOCATION_ID}.csv")
    if os.path.exists(demand_csv):
        os.remove(demand_csv)


def _make_s3_panel(pre_plan_state: dict, run_result):
    """`RunPanel` を作り、view を注入して描かせる（`_make_panel()` と同じ形）。"""
    from wom.cockpit.s3_run import RunPanel
    from wom.cockpit.s3_view_model import build_s3_view

    root = _new_tk_root()
    panel = RunPanel(root)
    panel.pack(fill="both", expand=True)
    panel._model_dir = S3_ALLOC_DIR
    panel._scenario_id = S3_SCENARIO_ID
    panel._cap_wk = S3_CAP_WK
    panel._pre_plan_state = pre_plan_state
    panel._run_result = run_result
    view = build_s3_view(pre_plan_state, run_result)
    if run_result is not None:
        panel._selected_node_key = view["default_node_key"]
    panel._render(view)
    root.update()
    root.update_idletasks()
    return root, panel


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_fits_within_default_window(s3_run_result, run_after):
    """条件1: そのまま効く。"""
    pre_plan_state, run_result = s3_run_result
    root, panel = _make_s3_panel(pre_plan_state, run_result if run_after else None)
    try:
        win_w = panel.winfo_width()
        win_h = panel.winfo_height()
        assert win_w > 1 and win_h > 1, "panel did not receive real geometry"
        for w in _iter_widgets(panel):
            if w is panel or not w.winfo_ismapped():
                continue
            x = w.winfo_rootx() - panel.winfo_rootx()
            y = w.winfo_rooty() - panel.winfo_rooty()
            assert x + w.winfo_width() <= win_w + 2, f"{w} extends right of window"
            assert y + w.winfo_height() <= win_h + 2, f"{w} extends below window"
    finally:
        root.destroy()


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_headline_lines_not_too_long(s3_run_result, run_after):
    """条件2: 一部だけ効く。結論行3行の文字数上限は S3 にも意味があるが、
    S1 の `full_allocation_ja`（全市場控え）に相当する控えラベルが S3 には
    無い——結論行だけ検査する。"""
    pre_plan_state, run_result = s3_run_result
    from wom.cockpit.s3_view_model import build_s3_view
    view = build_s3_view(pre_plan_state, run_result if run_after else None)
    for line in view["conclusion_lines_ja"]:
        assert len(line) <= _HEADLINE_MAX_CHARS, f"S3 conclusion line too long: {line!r}"


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_evidence_panel_not_empty(s3_run_result, run_after):
    """条件3: そのまま効く（根拠パネル側のみ——補助パネルの「実行の結果」は
    未実行のとき正しく空になるのが仕様〔K2 と同じ規律〕なので対象外）。"""
    pre_plan_state, run_result = s3_run_result
    root, panel = _make_s3_panel(pre_plan_state, run_result if run_after else None)
    try:
        axes = panel._fig.get_axes()
        assert axes, "S3 figure has no axes after render"
        ax = axes[0]
        has_content = bool(ax.texts) or bool(ax.lines) or bool(ax.patches) \
            or bool(ax.collections) or bool(ax.containers)
        assert has_content, "S3 plot axes has no text/lines/patches/collections"
    finally:
        root.destroy()


def test_s3_node_rows_are_bound(s3_run_result):
    """条件4の類型: そのまま同じ形で効く。S3 には木のドリルダウンは無いが、
    「クリックで切り替えられる一覧を出すなら、その行はバインドを持つ」という
    同じ構造の不変条件は能力ノード一覧にそのまま当てはまる。"""
    pre_plan_state, run_result = s3_run_result
    root, panel = _make_s3_panel(pre_plan_state, run_result)
    try:
        rows = panel._nodes_frame.winfo_children()
        assert rows, "S3 ran with capacity nodes but none rendered"
        bound = any(w.bind("<Button-1>") for row in rows for w in _iter_widgets(row))
        assert bound, "capacity node rows have no Button-1 binding"
    finally:
        root.destroy()


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_renders_without_exception(s3_run_result, run_after):
    """条件6: そのまま効く。"""
    pre_plan_state, run_result = s3_run_result
    root, panel = _make_s3_panel(pre_plan_state, run_result if run_after else None)
    try:
        assert panel._view is not None
    finally:
        root.destroy()


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_plot_has_no_missing_glyph_warnings(s3_run_result, run_after):
    """条件7: そのまま効く。"""
    pre_plan_state, run_result = s3_run_result
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        root, panel = _make_s3_panel(pre_plan_state, run_result if run_after else None)
        root.destroy()
    tofu = [str(w.message) for w in caught if "missing from font" in str(w.message)]
    assert not tofu, f"S3: glyph(s) missing from configured font (tofu): {tofu}"


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_result_block_matches_view(s3_run_result, run_after):
    """条件8の類型: そのまま同じ形で効く。S1 の「levels/level_notes_ja が
    空なら見出しごと隠す」（K2）と同じ構造が S3 の「実行の結果」ブロックにも
    ある（`view["has_run"]` が見出しの可視性と一致するはず）。"""
    pre_plan_state, run_result = s3_run_result
    from wom.cockpit.s3_view_model import build_s3_view
    view = build_s3_view(pre_plan_state, run_result if run_after else None)
    root, panel = _make_s3_panel(pre_plan_state, run_result if run_after else None)
    try:
        assert panel._result_header_visible == view["has_run"], (
            f"result_header_visible={panel._result_header_visible} but "
            f"view['has_run']={view['has_run']}")
        info_text = panel._result_info_label.cget("text")
        assert bool(info_text) == view["has_run"], (
            f"result_info_label text={info_text!r} but view['has_run']={view['has_run']}")
    finally:
        root.destroy()


# 条件5（リサイズに追従する・D2）と条件9（遷移を通す・M2）は S3 には移植しなかった。
# 理由（黙って除外しないための記録）:
#   条件5: S1 の対象は「全市場の配分」控えラベルの動的 wraplength（D2）。S3 には
#     窓幅に応じて折返し幅を変える動的ラベルが無い——この条件が検査する具体的な
#     機構そのものが S3 に存在しない（S1 固有の前提だったと判明した1例）。
#   条件9: S1 で問題になったのは「条件つきブロック（利益水準）を、常時ブロック
#     （子ノード欄）より上に置いていた」という並び順の欠陥だった。S3 は最初から
#     M1 の原則（常に在るものを上、条件つきを下）で組んだため、同じ形の欠陥が
#     構造的に発生しない。条件9を S3 に移植する意味があるとすれば「S1<->S3の
#     画面遷移でどこかのウィジェットが動くか」だが、これは S3 固有の内部遷移
#     ではなく骨格（frame.py）の話であり、本 Phase では手動の smoke test
#     （report参照）で確認済み・自動テスト化は次回以降の課題とする。


# ---------------------------------------------------------------------------
# 条件10: 降りられない行は、降りられるように見えない（条件4の鏡・Addendum Q2）
# ---------------------------------------------------------------------------
# 条件4は「子を出すなら（hierarchy かつ children がある）バインドがある」を見て
# おり、triangle モードは対象外として skip する——だから「バインドが無いのに
# 押せるように見える」（Q1 が見つけた欠陥）は条件4のどれにも掛からなかった。
# 条件10 はその鏡: 「バインドが無い行は cursor が hand2 でない」を、6状態＋S3
# の全状態に当てる。特定の画面・市場名・node_path を名指ししない汎用条件——
# S4/S5 が増えてもそのまま効く。

def _assert_no_row_looks_clickable_without_bind(container) -> None:
    for row in container.winfo_children():
        for w in _iter_widgets(row):
            if not w.bind("<Button-1>"):
                cursor = w.cget("cursor")
                assert cursor != "hand2", (
                    f"{w} has no Button-1 bind but cursor='hand2' "
                    f"(looks clickable but isn't)")


@pytest.mark.parametrize("state", STATES)
def test_children_rows_do_not_look_descendable_without_bind(state):
    """Q1 が直す前は triangle_n3 でこれが落ちる（fg=FG_ACC・cursor=hand2 だが
    バインド無し）。Q1 適用後は全6状態で緑になるはず。"""
    view = _build_view(state)
    root, panel = _make_panel(view)
    try:
        _assert_no_row_looks_clickable_without_bind(panel._children_frame)
    finally:
        root.destroy()


@pytest.mark.parametrize("run_after", [False, True], ids=["s3_before_run", "s3_after_run"])
def test_s3_node_rows_do_not_look_clickable_without_bind(s3_run_result, run_after):
    """条件10の S3 への移植。S3 の能力ノード一覧は全行が実際に選択操作を
    持つ（クリックで図を切替）ため、この条件は構造的に自明に緑になる——
    それでも「押せるように見えるものは押せる」という不変条件そのものは
    画面によらず適用できることを確認しておく。"""
    pre_plan_state, run_result = s3_run_result
    root, panel = _make_s3_panel(pre_plan_state, run_result if run_after else None)
    try:
        _assert_no_row_looks_clickable_without_bind(panel._nodes_frame)
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 条件11: 図の軸ラベルが、view が宣言した系列に対応している（Phase 8-3c-4・X3）
# ---------------------------------------------------------------------------
# 条件1〜10 のどれも「軸ラベルと、実際に描いている系列の対応」を見ていなかった
# ——だから「図が入庫（P）を描いているのに、処理能力と比べる図として名乗って
# いた」欠陥が素通りした。この条件は特定の画面・ノード名を名指ししない: view の
# 各ノードが宣言する `series_label_ja` / `title_ja` が、図に実際に出ていること、
# そして系列の種類（series_kind）が違えば軸ラベルも違うこと、だけを見る。
# 種類→語の対応表はテストに持たない（K1: 語は view_model の1箇所だけ）。

def test_s3_axis_labels_follow_declared_series_kind(s3_run_result):
    pre_plan_state, run_result = s3_run_result
    from wom.cockpit.s3_view_model import build_s3_view
    view = build_s3_view(pre_plan_state, run_result)
    nodes = view["capacity_nodes"]
    assert nodes, "no capacity nodes to check"

    root, panel = _make_s3_panel(pre_plan_state, run_result)
    try:
        label_by_kind = {}
        for n in nodes:
            panel._on_node_click((n["product"], n["name"]))
            root.update_idletasks()
            ax = panel._fig.get_axes()[0]
            assert ax.get_ylabel() == n["series_label_ja"], (
                f"{n['label']}: series_kind={n['series_kind']!r} declares "
                f"series_label_ja={n['series_label_ja']!r} but the figure shows "
                f"ylabel={ax.get_ylabel()!r}")
            assert ax.get_title() == n["title_ja"], (
                f"{n['label']}: declared title_ja={n['title_ja']!r} but the "
                f"figure shows title={ax.get_title()!r}")
            label_by_kind.setdefault(n["series_kind"], set()).add(n["series_label_ja"])

        kinds = list(label_by_kind)
        assert all(len(v) == 1 for v in label_by_kind.values()), (
            f"one series_kind maps to several axis labels: {label_by_kind}")
        assert len({next(iter(v)) for v in label_by_kind.values()}) == len(kinds), (
            f"different series_kind share one axis label: {label_by_kind}")
    finally:
        root.destroy()


def test_s3_shortfall_line_follows_selected_node(s3_run_result):
    """供給不足で処理量が凹んだ週は、図の上では能力で縛られた凹みと同じ形に
    見える。だから、選択中のノードにそれがあるときだけ補助パネルに出る
    （あれば1行増え、無ければ増えない）ことを、語を持たずに行数だけで見る。"""
    pre_plan_state, run_result = s3_run_result
    from wom.cockpit.s3_view_model import build_s3_view
    nodes = build_s3_view(pre_plan_state, run_result)["capacity_nodes"]

    root, panel = _make_s3_panel(pre_plan_state, run_result)
    try:
        seen = set()
        for n in nodes:
            panel._on_node_click((n["product"], n["name"]))
            root.update_idletasks()
            n_lines = panel._result_info_label.cget("text").count("\n") + 1
            has = bool(n["shortfall_weeks"])
            seen.add(has)
            assert n_lines == 3 + (1 if has else 0), (
                f"{n['label']}: shortfall_weeks={len(n['shortfall_weeks'])} but the "
                f"result block has {n_lines} lines")
        assert seen == {True, False}, (
            f"fixture should contain nodes both with and without shortfall, got {seen}")
    finally:
        root.destroy()

````
