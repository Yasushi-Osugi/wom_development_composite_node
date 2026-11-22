# -*- coding: utf-8 -*-
"""段 3：既定の押し戻し方を DEFAULT_POLICY（proportional_week）にする機械的な書き換え。"""
import os
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def sub(path, old, new, count=1):
    p = os.path.join(REPO, path)
    s = open(p, encoding="utf-8", newline="").read()
    if "\r\n" in s:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    if old not in s:
        raise SystemExit(f"missing in {path}: {old[:60]!r}")
    s = s.replace(old, new) if count == 0 else s.replace(old, new, count)
    open(p, "w", encoding="utf-8", newline="").write(s)


p = "wom/engine/overflow_policy.py"
sub(p, """POLICIES: Tuple[str, ...] = (TAIL, PROPORTIONAL_WEEK, BALANCE_CUT_RATIO)
""", """POLICIES: Tuple[str, ...] = (TAIL, PROPORTIONAL_WEEK, BALANCE_CUT_RATIO)

# 既定の押し戻し方（1 か所。RequestLetter_M6_RowOrder_Stage3_DefaultProportional、2026-11-22）。
# 空欄・None・planning_config.csv のファイルやキーが無い・Backward の config に無いとき、すべてこれ。
DEFAULT_POLICY = PROPORTIONAL_WEEK
""")
sub(p, '"""知らない overflow_policy の値（黙って tail にしない）。"""',
    '"""知らない overflow_policy の値（黙って既定にしない）。"""')
sub(p, '"""None・空欄＝tail。3 つ以外の値は止める（値・使える値・直し方を出す）。"""',
    '"""None・空欄＝既定（``DEFAULT_POLICY``）。3 つ以外の値は止める（値・使える値・直し方を出す）。"""')
sub(p, """    if not v:
        return TAIL""", """    if not v:
        return DEFAULT_POLICY""")
sub(p, "（空欄・キーなし＝tail）。", "（空欄・キーなし＝{DEFAULT_POLICY}）。")
sub(p, "def __init__(self, policy: str = TAIL) -> None:",
    "def __init__(self, policy: Optional[str] = None) -> None:")
sub(p, '"TAIL", "PROPORTIONAL_WEEK", "BALANCE_CUT_RATIO", "POLICIES",',
    '"TAIL", "PROPORTIONAL_WEEK", "BALANCE_CUT_RATIO", "POLICIES", "DEFAULT_POLICY",')

p = "wom/engine/backward_planner.py"
sub(p, "    TAIL as _OVERFLOW_TAIL, OverflowTracker, resolve_overflow_policy,",
    "    TAIL as _OVERFLOW_TAIL, DEFAULT_POLICY as _OVERFLOW_DEFAULT,\n"
    "    OverflowTracker, resolve_overflow_policy,")
sub(p, "    overflow_policy: str = _OVERFLOW_TAIL\n", "    overflow_policy: str = _OVERFLOW_DEFAULT\n")
sub(p, '        # capacity week. "tail" (default) = the current code path, unchanged.',
    '        # capacity week. Missing/blank = DEFAULT_POLICY (proportional_week since\n'
    '        # Stage 3, 2026-11); "tail" = the stage-0 code path, unchanged.')

p = "wom/engine/warmup.py"
sub(p, """    前の週へ回すか：``tail``（今の動き）／``proportional_week``／``balance_cut_ratio``。
    ファイル・キーが無い、または値が空なら ``tail``。3 つ以外の値は止める
    （``OverflowPolicyError``：ファイル・値・使える値・直し方。黙って tail にしない）。""",
    """    前の週へ回すか：``proportional_week``（既定）／``tail``／``balance_cut_ratio``。
    ファイル・キーが無い、または値が空なら既定（``DEFAULT_POLICY``）。3 つ以外の値は止める
    （``OverflowPolicyError``：ファイル・値・使える値・直し方。黙って既定にしない）。""")
sub(p, "from wom.engine.overflow_policy import TAIL, resolve_overflow_policy",
    "from wom.engine.overflow_policy import DEFAULT_POLICY, resolve_overflow_policy")
sub(p, "        return TAIL\n", "        return DEFAULT_POLICY\n", 0)
sub(p, "    return TAIL\n", "    return DEFAULT_POLICY\n")

p = "tools/run_headless_from_folder.py"
sub(p, "                                   read_lot_flow_mode, read_overflow_policy)\n",
    "                                   read_lot_flow_mode, read_overflow_policy)\n"
    "    from wom.engine.overflow_policy import DEFAULT_POLICY as DEFAULT_OVERFLOW_POLICY\n")
sub(p, "    # RequestLetter_M6_RowOrder_Stage1: Backward overflow policy (tail = current behaviour).",
    "    # RequestLetter_M6_RowOrder_Stage1/3: Backward overflow policy (blank = DEFAULT_POLICY).")
sub(p, '    if verbose and overflow_policy != "tail":',
    '    if verbose and overflow_policy != DEFAULT_OVERFLOW_POLICY:')
sub(p, """                   # only when not the default (tail), so the golden config is unchanged
                   **({} if overflow_policy == "tail" else {"overflow_policy": overflow_policy}),""",
    """                   # only when not the default (DEFAULT_POLICY), so the golden config is unchanged
                   **({} if overflow_policy == DEFAULT_OVERFLOW_POLICY
                      else {"overflow_policy": overflow_policy}),""")

p = "wom/gui/app.py"
sub(p, "        # overflow_policy; none/blank = tail = current behaviour; unknown value stops).",
    "        # overflow_policy; none/blank = DEFAULT_POLICY (proportional_week); unknown value stops).")
sub(p, """        from wom.engine.warmup import read_overflow_policy
        _cfg["overflow_policy"] = read_overflow_policy(getattr(self, "_model_dir", "") or "")
        if _cfg["overflow_policy"] != "tail":""", """        from wom.engine.warmup import read_overflow_policy
        from wom.engine.overflow_policy import DEFAULT_POLICY as _DEF_OVF
        _cfg["overflow_policy"] = read_overflow_policy(getattr(self, "_model_dir", "") or "")
        if _cfg["overflow_policy"] != _DEF_OVF:""")
print("ok")
