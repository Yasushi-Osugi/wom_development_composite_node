# -*- coding: utf-8 -*-
"""
test_golden.py — E2E ゴールデン回帰テスト（Anti-Degrade / Phase 1a）
=================================================================
`tests/golden/<case>.json` に固定した各ケースの KPI スナップショットと、
現行エンジンの実行結果を突き合わせ、**挙動が勝手に変わっていない事**を assert する。

仕組み:
  - golden JSON には run_headless_from_folder が出力した ppc（GM/Revenue/Cost/Tariff/trust）と
    psi（各ノードの P/S/I/CO 集計＋週次系列 md5）が入っている。
  - 本テストは各 golden について、記録された plugins で同ケースを再実行し、`ppc`/`psi` を厳密比較。
  - エンジン改修（cap_soft / 操業カレンダー等）が既存ケースを**意図せず**変えた瞬間に赤くなる。

golden の作り方（オーナーが Windows で実行して commit）:
  python -m tools.run_headless_from_folder --model-dir data/sample/<case> --out tests/golden/<case>.json --quiet
  ※ rice は --plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin
    （2026-10-09 に HarvestBatchPlugin を削除し、rice は Rice Seasonal で identity に移った）。

意図的に挙動を変えたときは、golden を**意識的に再生成して commit**（差分が監査証跡）。
golden が1つも無ければ本テストは skip される（ハーネスだけ先に入れても CI が赤にならない）。

2 つのフォルダ（RequestLetter_Warmup17_IdentityGolden §3）:
  tests/golden/*.json         各モデルの planning_config.csv の方式で作った golden
                              （rice は legacy、それ以外は identity。方式は config に記録）
  tests/golden/legacy/*.json  旧方式（決定記録 D3 で残した legacy）を守る網。
                              planning_config.csv の指定によらず、必ず legacy で実行して比べる。
  legacy の golden の作り方:
  python -m tools.run_headless_from_folder --model-dir data/sample/<case> --lot-flow-mode legacy
         --out tests/golden/legacy/<case>.json --quiet
"""
import glob
import json
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(HERE, "golden")
LEGACY_GOLDEN_DIR = os.path.join(GOLDEN_DIR, "legacy")
REPO_ROOT = os.path.dirname(HERE)
SAMPLE_DIR = os.path.join(REPO_ROOT, "data", "sample")

_golden_files = sorted(glob.glob(os.path.join(GOLDEN_DIR, "*.json")))
_cases = [os.path.splitext(os.path.basename(p))[0] for p in _golden_files]
_legacy_cases = [os.path.splitext(os.path.basename(p))[0]
                 for p in sorted(glob.glob(os.path.join(LEGACY_GOLDEN_DIR, "*.json")))]


@pytest.mark.skipif(not _cases, reason="no golden snapshots yet (tests/golden/*.json)")
@pytest.mark.parametrize("case", _cases)
def test_golden_matches(case, tmp_path):
    """記録した golden と現行エンジンの ppc/psi が一致する事。"""
    # Forward の方式は golden の config に記録された値で比較する
    # （RequestLetter_LotIdentityFlow C1）。記録の無い golden は legacy。
    _check_golden(os.path.join(GOLDEN_DIR, case + ".json"), case, tmp_path, forced_mode=None)


@pytest.mark.skipif(not _legacy_cases, reason="no legacy golden snapshots (tests/golden/legacy/*.json)")
@pytest.mark.parametrize("case", _legacy_cases)
def test_legacy_golden_matches(case, tmp_path):
    """旧方式（legacy）の解き方が壊れていない事（決定記録 D3）。"""
    _check_golden(os.path.join(LEGACY_GOLDEN_DIR, case + ".json"), case, tmp_path,
                  forced_mode="legacy")


def _check_golden(golden_path, case, tmp_path, forced_mode=None):
    from tools.run_headless_from_folder import run

    with open(golden_path, encoding="utf-8") as f:
        golden = json.load(f)

    plugins = ",".join(golden.get("config", {}).get("plugins", [])) or "none"
    model_dir = os.path.join(SAMPLE_DIR, case)
    assert os.path.isdir(model_dir), f"model dir not found: {model_dir}"

    lot_flow_mode = forced_mode or golden.get("config", {}).get("lot_flow_mode", "legacy")
    snap = run(model_dir, plugins_spec=plugins,
               output_ppc_dir=str(tmp_path / "ppc"), verbose=False,
               lot_flow_mode=lot_flow_mode)

    # 期間・製品・プラグインの前提が一致している事（データ改変も検知）
    assert snap["period"] == golden["period"], f"{case}: planning period drift"
    assert snap["products"] == golden["products"], f"{case}: product set drift"
    assert snap["config"] == golden["config"], f"{case}: plugin config drift"

    # Forward 能力挙動（cap_hard seal 数・cap_soft 違反数）— flag-only 挙動の退行検知。
    # 旧 golden（forward 無し）とは互換：golden に有る時だけ厳密比較する。
    if "forward" in golden:
        assert snap["forward"] == golden["forward"], (
            f"{case}: forward capacity drift\n  now={snap['forward']}\n  golden={golden['forward']}")

    # Backward cap_soft envelope（計画段階の残業帯）— Slice 2 の flag-only 挙動を固定。
    if "backward" in golden:
        assert snap["backward"] == golden["backward"], (
            f"{case}: backward capacity drift\n  now={snap['backward']}\n  golden={golden['backward']}")

    # 財務 KPI（単一 Lot_ID 台帳）— 挙動が変わっていない事
    assert snap["ppc"] == golden["ppc"], (
        f"{case}: PPC KPI drift\n  now={snap['ppc']}\n  golden={golden['ppc']}")

    # PSI 形状（各ノードの P/S/I/CO 集計＋週次系列 md5）— timing ドリフト検知
    assert snap["psi"] == golden["psi"], f"{case}: PSI signature drift (per-node)"
