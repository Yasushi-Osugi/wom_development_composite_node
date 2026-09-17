# -*- coding: utf-8 -*-
"""
tests/test_gui_panel_invariants.py — Gate 0: GUI の Anti-Degrade 網
================================================================================
正典: requests/Gate0_RequestLetter_GuiSmokeTests_to_CodeKun.md

`AllocationPanel`（S1 Allocate タブ）を headless に近い形で実体化し、代表的な
6状態を通しながら**構造として壊れていないか**だけを検査する（条件7のみ、
描画結果の警告を見る例外——Phase 8-3a 追補参照）。

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
