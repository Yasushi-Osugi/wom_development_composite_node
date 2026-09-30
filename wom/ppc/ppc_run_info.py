# -*- coding: utf-8 -*-
"""
wom/ppc/ppc_run_info.py — PPC の出力が「どのモデル・どの計画の結果か」の識別
（RequestLetter_StalePPC_Units_KittingView P1・P3）

背景
----
PPC の出力フォルダ（既定 `output/ppc`）は、どのモデルを計画しても同じ場所に上書きされる。
画面（Management の P&L Summary・Landed Cost、PPC タブ）は、そこにあるファイルを読むだけで、
そのファイルが今のモデル・今の計画のものかを確かめていなかった。そのため、前に計画した
モデルの PPC の値が、今のモデルの値として表示されることがあった。

仕組み
------
- 計画の実行ごとに **識別子（run_id）** を作る（時刻＋乱数＋モデル名）。
- PPC の入口（`ppc_runner.run_ppc_from_psi`）は、実行の**最初に**出力フォルダの印
  （`ppc_run_info.json`）を消し、すべての出力を書き終えた**最後に**印を書く。
  印があるのは「そのフォルダの全ファイルが、その 1 回の実行で書かれた」ときだけである。
  呼び出し側が `run_info` を渡さない実行（headless・テスト・`python -m wom.ppc`）は、
  印を書かない（消すだけ）。出力ファイルは、これまでと 1 バイトも変わらない。
- 画面は、読む前に `check_ppc_output()` で、印の run_id・モデルのフォルダが、今の計画と
  一致するかを確かめる。一致しなければ、前の値を出さない。

Tk に依存しない（GUI とテストの両方から使う）。
"""
from __future__ import annotations

import datetime
import json
import os
import threading
import uuid
from typing import Callable, Optional, Tuple

RUN_INFO_FILE = "ppc_run_info.json"

# PPC の状態（画面の側が持つ）
STATE_NONE = "none"          # このモデルでは、まだ PPC を実行していない
STATE_RUNNING = "running"    # PPC を計算中
STATE_DONE = "done"          # PPC が終わった
STATE_FAILED = "failed"      # PPC が失敗した

# 販売記録の出所（P3）
SALES_PSI = "psi"            # 計画（PSI）の市場 leaf の実出荷から作った
SALES_SAMPLE = "sample"      # PSI と PPC のマスターが対応せず、サンプルの販売データに差し替えた


def normalize_dir(path: str) -> str:
    """フォルダの比較用の形（絶対パス・大文字小文字と区切りをそろえる）。空は空。"""
    if not path:
        return ""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def new_run_id(model_dir: str = "") -> str:
    """計画の実行ごとの識別子：時刻（ミリ秒）＋乱数 6 桁＋モデルのフォルダ名。"""
    now = datetime.datetime.now()
    name = os.path.basename(os.path.normpath(model_dir)) if model_dir else "no-model"
    return f"{now:%Y%m%d-%H%M%S}.{now.microsecond // 1000:03d}-{uuid.uuid4().hex[:6]}__{name}"


def clear_run_info(output_dir: str) -> None:
    """出力フォルダの印を消す（PPC の実行の最初に呼ぶ）。無ければ何もしない。"""
    try:
        os.remove(os.path.join(output_dir, RUN_INFO_FILE))
    except OSError:
        pass


def write_run_info(output_dir: str, info: dict) -> str:
    """印を書く（PPC のすべての出力を書き終えた後に呼ぶ）。"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, RUN_INFO_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def read_run_info(output_dir: str) -> Optional[dict]:
    path = os.path.join(output_dir, RUN_INFO_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


class PPCRunGate:
    """2 つの計画を続けて実行したときの、PPC の実行と結果の受け取りの門番。

    1 つの画面につき 1 つ持つ。決まりは 2 つ：

    - **今の計画だけが有効**（`set_current(run_id)`）。モデルを読み込み直したときは
      `set_current("")` で、どの計画も有効でなくする。
    - **PPC の実行は 1 つずつ**（`run()`）。出力フォルダは 1 つなので、2 つの実行が同時に
      書かないようにする。順番が回ってきたとき、その計画がもう今の計画でなければ、
      **実行しない**（`SKIPPED` を返す）。

    こうすると、前の計画の PPC が後から終わっても、(a) その結果は `is_current()` が False
    なので画面に出ず、(b) 出力フォルダには、最後に今の計画の PPC が書くので、今の計画の
    結果が残る（前の計画の PPC が、今の計画の出力を上書きしない）。
    """

    SKIPPED = object()

    def __init__(self):
        self._lock = threading.Lock()
        self._current = ""

    @property
    def current(self) -> str:
        return self._current

    def set_current(self, run_id: str) -> None:
        self._current = run_id or ""

    def is_current(self, run_id: str) -> bool:
        return bool(run_id) and run_id == self._current

    def run(self, run_id: str, fn: Callable[[], object]):
        """PPC を実行する（ワーカーのスレッドから呼ぶ）。前の実行が終わるまで待つ。
        順番が来たときに run_id が今の計画でなければ、fn を呼ばずに SKIPPED を返す。"""
        with self._lock:
            if not self.is_current(run_id):
                return self.SKIPPED
            return fn()


def make_context(state: str = STATE_NONE, run_id: str = "", model_dir: str = "",
                 error: str = "") -> dict:
    """画面が持つ「今の計画」の情報。"""
    return {"state": state, "run_id": run_id or "", "model_dir": model_dir or "",
            "error": error or ""}


def check_ppc_output(output_dir: str, ctx: Optional[dict]) -> Tuple[bool, str]:
    """出力フォルダの PPC の結果を、今の計画の結果として使ってよいか。

    返り値 (使ってよいか, 状態の表示)。表示は、使えないときの理由を兼ねる：
      「PPC 未実行」「PPC 計算中」「PPC 失敗」
      「PPC の出力が今の計画のものではない」（印が無い・run_id かモデルのフォルダが違う）
      「PPC はサンプルの販売データ」（PSI と対応していない。今の計画の値としては使わない）
    """
    if not ctx:
        return False, "PPC 未実行"
    state = ctx.get("state", STATE_NONE)
    if state == STATE_RUNNING:
        return False, "PPC 計算中"
    if state == STATE_FAILED:
        return False, "PPC 失敗"
    if state != STATE_DONE:
        return False, "PPC 未実行"
    info = read_run_info(output_dir)
    if info is None:
        return False, "PPC の出力が今の計画のものではない（識別の印が無い）"
    if not ctx.get("run_id") or info.get("run_id") != ctx.get("run_id"):
        return False, "PPC の出力が今の計画のものではない（別の計画の結果）"
    if normalize_dir(info.get("model_dir", "")) != normalize_dir(ctx.get("model_dir", "")):
        return False, "PPC の出力が今の計画のものではない（別のモデルの結果）"
    if info.get("sales_source") != SALES_PSI:
        return False, "PPC はサンプルの販売データ（計画の数量と対応していない）"
    return True, "PPC 台帳（今の計画）"
