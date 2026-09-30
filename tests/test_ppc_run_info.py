# -*- coding: utf-8 -*-
"""
tests/test_ppc_run_info.py — RequestLetter_StalePPC_Units_KittingView P1・P2・P3

P1  PPC の出力が「今のモデル・今の計画の結果」かを、識別の印（ppc_run_info.json）で確かめる。
    一致しないときは、前の値を読まない（Management の P&L Summary・Landed Cost・Node P&L）。
P2  「Load Model Folder」で、すべての入力欄がそのフォルダのファイルに置き換わる
    （フォルダに無いファイルの欄は空になる。前のモデルのファイルを残さない）。
P3  PPC が PSI の販売記録を使ったか、サンプルの販売データに差し替えたかを記録する。
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.ppc import ppc_run_info as R

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL = os.path.join(REPO, "data", "sample", "bom-test-2026")


# ---------------------------------------------------------------------------
# P1  識別子と、出力の確認（Tk なし）
# ---------------------------------------------------------------------------

def test_run_id_is_unique_and_names_the_model():
    a = R.new_run_id(r"C:\x\data\sample\iphone_global")
    b = R.new_run_id(r"C:\x\data\sample\iphone_global")
    assert a != b and a.endswith("__iphone_global") and b.endswith("__iphone_global")
    assert R.new_run_id("").endswith("__no-model")


def _stamp(out, run_id="RUN-1", model_dir=r"C:\models\A", sales_source="psi"):
    R.write_run_info(str(out), {"run_id": run_id, "model_dir": model_dir, "sales_source": sales_source})


def test_check_states_before_the_ppc_result_exists(tmp_path):
    _stamp(tmp_path)                       # 前の計画の出力がフォルダに残っている
    assert R.check_ppc_output(str(tmp_path), None) == (False, "PPC 未実行")
    for state, label in ((R.STATE_NONE, "PPC 未実行"), (R.STATE_RUNNING, "PPC 計算中"),
                         (R.STATE_FAILED, "PPC 失敗")):
        ctx = R.make_context(state, "RUN-1", r"C:\models\A")
        assert R.check_ppc_output(str(tmp_path), ctx) == (False, label)


def test_check_accepts_only_the_current_plan_and_model(tmp_path):
    out = str(tmp_path)
    ctx = R.make_context(R.STATE_DONE, "RUN-1", r"C:\models\A")
    # 印が無い（headless や古い出力）
    ok, label = R.check_ppc_output(out, ctx)
    assert not ok and "識別の印が無い" in label
    # 一致
    _stamp(tmp_path)
    assert R.check_ppc_output(out, ctx) == (True, "PPC 台帳（今の計画）")
    # フォルダの書き方の違い（大文字小文字・区切り・末尾の区切り）は同じモデル
    assert R.check_ppc_output(out, R.make_context(R.STATE_DONE, "RUN-1", "c:/models/a/"))[0]
    # 別の計画
    ok, label = R.check_ppc_output(out, R.make_context(R.STATE_DONE, "RUN-2", r"C:\models\A"))
    assert not ok and "別の計画" in label
    # 同じ識別子でも別のモデル
    ok, label = R.check_ppc_output(out, R.make_context(R.STATE_DONE, "RUN-1", r"C:\models\B"))
    assert not ok and "別のモデル" in label
    # 識別子が空の計画は、どの出力とも一致させない
    assert not R.check_ppc_output(out, R.make_context(R.STATE_DONE, "", r"C:\models\A"))[0]
    # サンプルの販売データ（P3）：今の計画の値としては使わない
    _stamp(tmp_path, sales_source="sample")
    ok, label = R.check_ppc_output(out, ctx)
    assert not ok and "サンプル" in label
    # 壊れた印
    with open(os.path.join(out, R.RUN_INFO_FILE), "w", encoding="utf-8") as f:
        f.write("{not json")
    assert not R.check_ppc_output(out, ctx)[0]


# ---------------------------------------------------------------------------
# P1・P3  PPC の入口（ppc_runner）が、印を消して・書く
# ---------------------------------------------------------------------------

def _planned_tree(tmp_path):
    """bom-test-2026 のコピーを headless で計画し、(sc_tree, モデルのフォルダ, PPC の出力) を返す。"""
    import tools.run_headless_from_folder as rh
    model = str(tmp_path / "bom-test-2026")
    shutil.copytree(MODEL, model)
    out = str(tmp_path / "ppc_headless")
    os.makedirs(out)
    _stamp(out, run_id="OLD-RUN", model_dir=r"C:\other\model")   # 前の計画の印が残っている
    store = {}
    o_sig = rh._psi_signature

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    rh._psi_signature = sig
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        rh.run(model, plugins_spec="safe", output_ppc_dir=out, verbose=False)
    finally:
        os.chdir(cwd)
        rh._psi_signature = o_sig
    return store["tree"], model, out


def test_runner_clears_the_old_mark_and_writes_a_new_one_only_for_an_identified_run(tmp_path):
    from wom.ppc.ppc_runner import run_ppc_from_psi
    tree, model, out_headless = _planned_tree(tmp_path)
    # headless（run_info なし）：前の印は消える。新しい印は書かない
    assert R.read_run_info(out_headless) is None
    assert R.RUN_INFO_FILE not in os.listdir(out_headless)
    ctx = R.make_context(R.STATE_DONE, "OLD-RUN", r"C:\other\model")
    assert not R.check_ppc_output(out_headless, ctx)[0]     # 前の計画の結果として読まれない

    # GUI と同じ呼び方（run_info あり）
    out = str(tmp_path / "ppc_gui")
    run_id = R.new_run_id(model)
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        kpi = run_ppc_from_psi(sc_tree=tree, weeks=list(tree.week_labels), data_dir=model,
                               output_dir=out, base_currency="USD", use_node_name=True,
                               run_info={"run_id": run_id, "model_dir": model})
    finally:
        os.chdir(cwd)
    info = R.read_run_info(out)
    assert info["run_id"] == run_id and R.normalize_dir(info["model_dir"]) == R.normalize_dir(model)
    assert info["sales_source"] == "psi" and info["n_weeks"] == len(tree.week_labels)
    assert kpi["_psi_mode"] is True and kpi["sales_source"] == "psi"           # P3
    assert R.check_ppc_output(out, R.make_context(R.STATE_DONE, run_id, model))[0]
    # 別のモデルを読み込んだ後の計画からは、この出力は読まれない
    assert not R.check_ppc_output(out, R.make_context(R.STATE_DONE, R.new_run_id("x"), "x"))[0]

    # 印は PPC の結果そのものを変えない：JSON・CSV は headless の出力と同じ
    for fn in sorted(os.listdir(out_headless)):
        with open(os.path.join(out_headless, fn), "rb") as a, open(os.path.join(out, fn), "rb") as b:
            assert a.read() == b.read(), fn
    assert sorted(os.listdir(out)) == sorted(os.listdir(out_headless) + [R.RUN_INFO_FILE])
    with open(os.path.join(out, "ppc_kpi_summary.json"), encoding="utf-8") as f:
        assert "_psi_mode" not in json.load(f)


def test_sample_fallback_is_recorded_and_not_used_as_the_plans_result(tmp_path):
    """P3：計画の製品・市場が PPC のマスターに無いと、サンプルの販売データに差し替わる。"""
    from wom.ppc.ppc_runner import run_ppc_from_psi
    tree, model, _out = _planned_tree(tmp_path)
    out = str(tmp_path / "ppc_sample")
    run_id = R.new_run_id(model)
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        # data/ppc（既定のマスター）には、このモデルの製品が無い。
        # 既定の為替表は 2026-W01 から始まるので、その範囲の週だけを渡す
        # （それより前の週では、サンプルへの差し替え自体が為替の欠落で失敗する＝PPC 失敗）。
        weeks = [w for w in tree.week_labels if w >= "2026-W01"]
        kpi = run_ppc_from_psi(sc_tree=tree, weeks=weeks, data_dir="data/ppc",
                               output_dir=out, run_info={"run_id": run_id, "model_dir": model})
    finally:
        os.chdir(cwd)
    assert kpi["_psi_mode"] is False and kpi["sales_source"] == "sample"
    assert R.read_run_info(out)["sales_source"] == "sample"
    ok, label = R.check_ppc_output(out, R.make_context(R.STATE_DONE, run_id, model))
    assert not ok and "サンプル" in label


# ---------------------------------------------------------------------------
# 2 つの計画を、PPC が終わる前に続けて実行する（PPCRunGate）
# ---------------------------------------------------------------------------

def _fake_ppc(out, run_id, model_dir, log, started=None, release=None):
    """PPC の代わり：出力フォルダに結果と印を書く。release を待ってから書く。"""
    def fn():
        if started is not None:
            started.set()
        if release is not None:
            assert release.wait(10)
        log.append(("write", run_id))
        R.clear_run_info(out)
        with open(os.path.join(out, "ppc_kpi_summary.json"), "w", encoding="utf-8") as f:
            json.dump({"run": run_id}, f)
        R.write_run_info(out, {"run_id": run_id, "model_dir": model_dir, "sales_source": "psi"})
        return {"run": run_id}
    return fn


def test_late_ppc_of_the_previous_plan_is_not_shown_and_does_not_overwrite(tmp_path):
    """計画 A の PPC が終わる前に、計画 B を実行する。A の PPC が後から終わっても、
    (a) A の結果は画面に受け取られず、(b) 出力フォルダには B の結果が残る。"""
    import threading
    out = str(tmp_path)
    gate, log, shown = R.PPCRunGate(), [], []
    a_started, a_release = threading.Event(), threading.Event()

    def worker(run_id, model_dir, **kw):
        res = gate.run(run_id, _fake_ppc(out, run_id, model_dir, log, **kw))
        log.append(("skipped" if res is R.PPCRunGate.SKIPPED else "finished", run_id))
        if res is not R.PPCRunGate.SKIPPED and gate.is_current(run_id):   # 画面の側の受け取り
            shown.append(run_id)

    gate.set_current("RUN-A")
    ta = threading.Thread(target=worker, args=("RUN-A", r"C:\m\A"),
                          kwargs={"started": a_started, "release": a_release})
    ta.start()
    assert a_started.wait(10)                 # A の PPC は実行中（まだ書いていない）

    gate.set_current("RUN-B")                 # 計画 B を実行した
    tb = threading.Thread(target=worker, args=("RUN-B", r"C:\m\B"))
    tb.start()
    time.sleep(0.3)
    assert ("write", "RUN-B") not in log      # B の PPC は、A が終わるまで書かない（同時に書かない）
    # この間、画面は B の「PPC 計算中」。フォルダに何があっても読まない
    assert R.check_ppc_output(out, R.make_context(R.STATE_RUNNING, "RUN-B", r"C:\m\B")) == (False, "PPC 計算中")

    a_release.set()                           # A の PPC が「後から」終わる
    ta.join(10); tb.join(10)
    assert log == [("write", "RUN-A"), ("finished", "RUN-A"), ("write", "RUN-B"), ("finished", "RUN-B")]
    assert shown == ["RUN-B"]                 # A の結果は画面に出ない
    assert R.read_run_info(out)["run_id"] == "RUN-B"          # フォルダには B の結果が残る
    assert R.check_ppc_output(out, R.make_context(R.STATE_DONE, "RUN-B", r"C:\m\B"))[0]
    assert not R.check_ppc_output(out, R.make_context(R.STATE_DONE, "RUN-A", r"C:\m\A"))[0]


def test_ppc_of_a_plan_that_is_no_longer_current_is_not_started(tmp_path):
    """順番が来たときに、もう今の計画でない PPC は、実行しない（フォルダに書かない）。"""
    out = str(tmp_path)
    gate, log = R.PPCRunGate(), []
    gate.set_current("RUN-B")
    assert gate.run("RUN-A", _fake_ppc(out, "RUN-A", "A", log)) is R.PPCRunGate.SKIPPED
    assert log == [] and R.read_run_info(out) is None
    # モデルを読み込み直した後（今の計画なし）は、どの PPC も始めない・受け取らない
    gate.set_current("")
    assert gate.run("RUN-B", _fake_ppc(out, "RUN-B", "B", log)) is R.PPCRunGate.SKIPPED
    assert not gate.is_current("RUN-B") and not gate.is_current("")
    assert log == []
    # 今の計画の PPC は実行する
    gate.set_current("RUN-C")
    assert gate.run("RUN-C", _fake_ppc(out, "RUN-C", "C", log)) == {"run": "RUN-C"}
    assert R.read_run_info(out)["run_id"] == "RUN-C"


# ---------------------------------------------------------------------------
# P2  モデルのフォルダ → 入力欄
# ---------------------------------------------------------------------------

def test_model_folder_file_map_replaces_every_entry(tmp_path):
    pytest.importorskip("tkinter")
    from wom.gui.app import model_folder_file_map, MODEL_FILE_MAP
    a, b = tmp_path / "model_a", tmp_path / "model_b"
    a.mkdir(); b.mkdir()
    for fn in ("sc_tree_master.csv", "edge_cost_master.csv", "route_master.csv", "push_config.csv",
               "sku_master.csv", "demand_forecast.csv"):
        (a / fn).write_text("x\n", encoding="utf-8")
    for fn in ("sc_tree_master.csv", "sku_master.csv", "demand_forecast.csv"):
        (b / fn).write_text("x\n", encoding="utf-8")

    fa, fb = model_folder_file_map(str(a)), model_folder_file_map(str(b))
    assert set(fa) == set(fb) == {attr for attr, _ in MODEL_FILE_MAP}
    # A：SC Tree Master・Edge Cost Master・Route Master は A のフォルダのファイル
    for attr, fn in (("_f_sc_tree", "sc_tree_master.csv"), ("_f_edge_cost", "edge_cost_master.csv"),
                     ("_f_route", "route_master.csv")):
        assert fa[attr] == os.path.join(str(a), fn)
    # B に読み込み直す：B にあるものは B のファイル、B に無いものは空（A のファイルを残さない）
    assert fb["_f_sc_tree"] == os.path.join(str(b), "sc_tree_master.csv")
    assert fb["_f_edge_cost"] == "" and fb["_f_route"] == "" and fb["_f_push"] == ""
    assert all(p == "" or os.path.dirname(p) == str(b) for p in fb.values())


def test_outside_work_root_is_flagged(tmp_path):
    pytest.importorskip("tkinter")
    from wom.gui.app import is_outside_work_root, describe_model_dir, work_root
    assert os.path.normcase(work_root()) == os.path.normcase(REPO)
    inside = os.path.join(REPO, "data", "sample", "iphone_global")
    assert not is_outside_work_root(inside)
    assert describe_model_dir(inside) == os.path.abspath(inside)          # フルパス
    # 別のフォルダにある同じ名前のモデル（古いコピーなど）
    other = str(tmp_path / "old_copy" / "data" / "sample" / "iphone_global")
    assert is_outside_work_root(other)
    assert describe_model_dir(other).startswith("⚠ 作業フォルダの外：") and other in describe_model_dir(other)
    # 名前が作業フォルダで始まるだけの別のフォルダは、外
    assert is_outside_work_root(REPO + "_old")
    assert describe_model_dir("") == "（モデル未読み込み）"


# ---------------------------------------------------------------------------
# P1  Management のパネルが、一致しない出力を読まない（Tk）
# ---------------------------------------------------------------------------

def _new_tk_root(tk, tries=8):
    last = None
    for _ in range(tries):                # このマシンの Tcl の初期化は時々失敗する（既知）
        try:
            return tk.Tk()
        except tk.TclError as exc:
            last = exc
            time.sleep(0.4)
    pytest.skip(f"tk.Tk() could not be created on this machine: {last}")


def test_management_panel_reads_ppc_only_for_the_current_plan(tmp_path):
    tk = pytest.importorskip("tkinter")
    import wom.gui.app as A
    out = str(tmp_path / "ppc")
    os.makedirs(out)
    with open(os.path.join(out, "ppc_kpi_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"base_currency": "THB", "total_revenue_base": 319119580000.0,
                   "total_cost_base": 138830903750.0, "gross_profit_base": 180288676250.0,
                   "gross_margin_pct": 0.565}, f)
    with open(os.path.join(out, "ppc_node_pl_summary.csv"), "w", encoding="utf-8") as f:
        f.write("node_id,product_id,revenue_base,cost_base,tariff_base,gross_profit_base,"
                "gross_margin_pct,lot_events\nSales_TH_BKK,EVmaker_Local,100,40,0,60,0.6,1\n")
    _stamp(out, run_id="RUN-EV", model_dir=r"C:\m\ev-thailand-2026")   # ev-thailand の計画の出力

    root = _new_tk_root(tk)
    try:
        root.geometry("900x600+-3000+-3000")
        panel = A.ManagementCockpitPanel(root)
        panel._node_pl_output_dir = out
        node_rows = lambda: [panel._node_pl_tree.item(i)["values"] for i in panel._node_pl_tree.get_children()]

        # 計画なし：読まない
        assert panel._ledger_pl_for_sku(None) is None and panel._base_ccy() == ("", "")
        # iphone を読み込んで計画した直後（iphone の PPC は計算中）：ev-thailand の値を読まない
        iphone = R.make_context(R.STATE_RUNNING, "RUN-IPHONE", r"C:\m\iphone_global")
        panel.set_ppc_context(iphone)
        panel._refresh_node_pl_table()
        assert panel._ledger_pl_for_sku(None) is None
        assert panel._ledger_pl_for_sku("EVmaker_Local") is None
        assert node_rows() == [["（PPC 計算中）", "", "", "", "", "", ""]]
        assert "PPC 計算中" in panel._ppc_banner_var.get()
        assert "表示しません" in panel._ppc_banner_var.get()
        # iphone の PPC が「終わった」ことになっても、フォルダの出力が ev-thailand のものなら読まない
        panel.set_ppc_context(R.make_context(R.STATE_DONE, "RUN-IPHONE", r"C:\m\iphone_global"))
        assert panel._ledger_pl_for_sku(None) is None
        # PPC 失敗
        panel.set_ppc_context(R.make_context(R.STATE_FAILED, "RUN-IPHONE", r"C:\m\iphone_global"))
        assert panel._ledger_pl_for_sku(None) is None and "PPC 失敗" in panel._ppc_banner_var.get()
        # 出力が今の計画のもの：読む
        panel.set_ppc_context(R.make_context(R.STATE_DONE, "RUN-EV", r"C:\m\ev-thailand-2026"))
        panel._refresh_node_pl_table()
        assert panel._ledger_pl_for_sku(None)[0] == 319119580000.0
        assert panel._base_ccy()[0] == "THB"
        assert node_rows()[0][0] == "Sales_TH_BKK"
        assert "PPC 台帳（今の計画）" in panel._ppc_banner_var.get()
        # P&L Summary・Landed Cost・チャート：PPC の結果が無い間は空欄で、状態だけを出す
        import pandas as pd
        from wom.data.schema import Cols

        class _Mgr:                       # money の値を持つ、最小の代わり
            scenario_money_kpi = pd.DataFrame([{Cols.SCENARIO: "Planning", Cols.REVENUE: 416331210.0,
                                                Cols.COGS: 183688370.0, Cols.GROSS_PROFIT: 232642840.0,
                                                Cols.GROSS_MARGIN: 0.559, Cols.INV_VALUE_COST: 56071.0,
                                                Cols.CCC_WKS: -14.0, Cols.AR_VALUE: 1.0, Cols.AP_VALUE: 2.0,
                                                "units": 10.0}])
            summary_money = None
            lc_comparison_df = pd.DataFrame([{"wom_scenario": "Planning", "lc_scenario": "Base",
                                              "revenue": 416331210.0, "customs_duty": 0.0,
                                              "freight_total": 1.0, "landed_gross_margin": 0.5,
                                              "margin_impact_pp": 0.0, "tariff_burden_pct": 0.0}])
            lc_scens, route_idx, strategic_kpi, sc_tree, model_dir = {}, {}, None, None, ""

        pl_rows = lambda: [[str(v) for v in panel._pl_tree.item(i)["values"]] for i in panel._pl_tree.get_children()]
        lc_rows = lambda: [panel._lc_tree.item(i)["values"] for i in panel._lc_tree.get_children()]
        for state, label in ((R.STATE_RUNNING, "PPC 計算中"), (R.STATE_FAILED, "PPC 失敗"),
                             (R.STATE_NONE, "PPC 未実行")):
            panel.set_ppc_context(R.make_context(state, "RUN-IPHONE", r"C:\m\iphone_global"))
            panel.load(_Mgr())
            assert pl_rows() == [["Planning"] + [""] * 8 + [label]]          # money の値を出さない
            assert lc_rows() == []
            assert panel._lc_narrative.get("1.0", "end").startswith(label)
            assert [t.get_text() for t in panel._gp_fig.axes[0].texts] == [label]
            assert [t.get_text() for t in panel._ccc_fig.axes[0].texts] == [label]
            assert "416" not in str(pl_rows()) and "319" not in str(pl_rows())
        # 今の計画の PPC の結果があるとき：PPC の値
        panel.set_ppc_context(R.make_context(R.STATE_DONE, "RUN-EV", r"C:\m\ev-thailand-2026"))
        panel.load(_Mgr())
        assert pl_rows()[0][1] == "319,119,580,000" and pl_rows()[0][-1] == "PPC 台帳（今の計画）"
        assert len(lc_rows()) == 1

        # モデルを読み込み直す：前の計画の表を消す
        panel.on_model_loaded(r"C:\m\iphone_global")
        assert node_rows() == [] and panel._ledger_pl_for_sku(None) is None
        assert "Planning Engine を実行してください" in panel._ppc_banner_var.get()
    finally:
        root.destroy()
