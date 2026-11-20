# -*- coding: utf-8 -*-
"""
能力を超えた分の押し戻し方（overflow policy）。

RequestLetter_M6_RowOrder_Stage1_OverflowPolicy、設計書
requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §3。

Backward の ``_apply_mom_cap_backward`` が、工場（in-root MOM）の能力を超えた週に
「どの市場のどの lot を前の週へ回すか」を決める規則。

- ``tail``（既定）           ：今の動き。並びの末尾から n 個（このモジュールは並びを決めない。
                               Backward が今のコードの経路をそのまま通す）。
- ``proportional_week``      ：その週の市場ごとの lot の数に比例（§3.1）。端数は累積の丸め誤差
                               （累積の丸め前の割当 − 累積の実際の押し戻し）の大きい市場へ。
- ``balance_cut_ratio``      ：累積押戻負担率（延べの押し戻し ÷ 処理済みの週に現れた lot の数）を
                               そろえる（§3.2）。1 lot ずつ、足した後の負担率が一番小さい市場から。

市場の中で押し戻す lot（両方式）：要求週の遅いものから、同じ要求週は連番の大きいものから（§3.3）。
新しい二つの方式では、残す lot と押し戻す lot を「要求週 → 市場キー → 連番」の順に並べ直して返す
（下流に CSV の行の順を持ち込まないため）。

市場キー＝Lot_ID の region、要求週＝Lot_ID の週、連番＝Lot_ID の連番（``LotIDGenerator.parse``）。
状態（``OverflowTracker``）は工場 × 製品ごと、Backward の実行ごとに新しく作る。

保護対象のコアではない（Backward からは呼び出しだけ）。
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Dict, List, Optional, Sequence, Tuple

from wom.model.lot_generator import LotIDGenerator

TAIL = "tail"
PROPORTIONAL_WEEK = "proportional_week"
BALANCE_CUT_RATIO = "balance_cut_ratio"
POLICIES: Tuple[str, ...] = (TAIL, PROPORTIONAL_WEEK, BALANCE_CUT_RATIO)


class OverflowPolicyError(ValueError):
    """知らない overflow_policy の値（黙って tail にしない）。"""


def resolve_overflow_policy(value: Optional[str], source: str = "") -> str:
    """None・空欄＝tail。3 つ以外の値は止める（値・使える値・直し方を出す）。"""
    v = (value or "").strip()
    if not v:
        return TAIL
    if v not in POLICIES:
        where = f"{source}: " if source else ""
        raise OverflowPolicyError(
            f"{where}overflow_policy の値 {v!r} は使えません。"
            f"使える値: {', '.join(POLICIES)}（空欄・キーなし＝tail）。"
            f"直し方: planning_config.csv の overflow_policy の値を上のどれかにするか、行を消してください。")
    return v


# ---------------------------------------------------------------------------
# 工場 × 製品ごとの状態
# ---------------------------------------------------------------------------

class OverflowTracker:
    """工場 × 製品 × 1 回の Backward の状態。

    - 延べの押し戻し（市場ごと）と母数（処理済みの週に現れた lot の数、同じ Lot_ID は 1 回）は
      どの方式でも数える（報告・画面の比較用。並びは変えない）。
    - proportional_week：累積の丸め前の割当 R_m と累積の実際の押し戻し A_m。
    """

    def __init__(self, policy: str = TAIL) -> None:
        self.policy = resolve_overflow_policy(policy)
        self._ord: Dict[str, Tuple[str, str, int]] = {}   # lot_id -> (week, region, seq)（並べ替えのキー）
        self._mkt: Dict[str, str] = {}                     # lot_id -> region
        self._seen: set = set()
        self.den: Dict[str, int] = {}       # 母数
        self.pushed: Dict[str, int] = {}    # 延べの押し戻し（= A_m）
        self._raw: Dict[str, Fraction] = {}  # R_m（proportional_week）
        self.stats_ok = True                 # tail で Lot_ID が読めないとき False（数えるのをやめる）
        self._carried = 0                    # 次に見る週の並びの末尾にある、押し戻した lot の数
        self._carried_counts: Dict[str, int] = {}
        self._week_counts: Optional[Dict[str, int]] = None
        self._carried_ends: Tuple = (None, None)
        self._carried_by_m: Dict[str, List[str]] = {}
        self._carried_runs: Optional[Dict[str, List[str]]] = None
        self._observed_len, self._orig_len = -1, 0

    # -- Lot_ID ------------------------------------------------------------
    def _learn(self, lot_id: str) -> str:
        _sku, region, week, seq = LotIDGenerator.parse(str(lot_id))
        self._ord[lot_id] = (week, region, seq)
        self._mkt[lot_id] = region
        return region

    def market(self, lot_id: str) -> str:
        m = self._mkt.get(lot_id)
        return self._learn(lot_id) if m is None else m

    # -- 母数 --------------------------------------------------------------
    def observe(self, week_lots: Sequence[str]) -> None:
        """処理する週の並び（前の週から押し戻されて来た lot も含む）を母数に入れる。

        tail では数えるだけ（並びに関係しない）なので、Lot_ID が読めなければ数えるのをやめ、
        計画は今のまま続ける（``stats_ok`` が False）。新しい方式では止める。"""
        if not self.stats_ok:
            return
        try:
            self._observe(week_lots)
        except ValueError:
            if self.policy != TAIL:
                raise
            self.stats_ok = False

    def _observe(self, week_lots: Sequence[str]) -> None:
        # Backward は週を後ろから処理し、押し戻した lot を前の週の並びの末尾に足す。だから並びの
        # 末尾の self._carried 個は、前に処理した週で押し戻した lot（見た後）。それより前だけを見る。
        # 末尾が本当にその押し戻しか（最初と最後の lot が同じもの）を確かめ、違えば全部を見る。
        n_all = len(week_lots)
        k = n_all - self._carried
        carried_ok = (self._carried > 0 and k >= 0
                      and week_lots[k] is self._carried_ends[0]
                      and week_lots[n_all - 1] is self._carried_ends[1])
        if not carried_ok:
            k = n_all
        part = week_lots[:k] if k < n_all else week_lots
        get = self._mkt.get
        counts: Dict[str, int] = dict(self._carried_counts) if carried_ok else {}
        new = set(part) - self._seen
        for lot in part:
            m = get(lot)
            if m is None:
                m = self._learn(lot)
            counts[m] = counts.get(m, 0) + 1
        self._week_counts = counts          # この週の並びの市場ごとの数（押し戻しを数えるのに使う）
        self._carried, self._carried_counts = 0, {}
        # split() 用：この週の並びの長さ、末尾より前の lot の数、末尾の押し戻しの市場ごとの並び
        self._observed_len, self._orig_len = n_all, k
        self._carried_runs = self._carried_by_m if carried_ok else None
        self._carried_by_m = {}
        if not new:
            return
        self._seen |= new
        den = self.den
        for lot in new:
            m = get(lot)
            den[m] = den.get(m, 0) + 1

    def record_tail(self, within: Sequence[str], overflow: Sequence[str]) -> None:
        """tail の経路で押し戻された lot を数える（並びは変えない）。"""
        if not self.stats_ok:
            return
        try:
            self._record_tail(within, overflow)
        except ValueError:
            self.stats_ok = False

    def _record_tail(self, within: Sequence[str], overflow: Sequence[str]) -> None:
        # 押し戻しの市場ごとの数：短い方を数える（週の並びの数 − 残す数 ＝ 押し戻す数）
        if len(overflow) <= len(within) or self._week_counts is None:
            cnt = Counter(map(self.market, overflow))
        else:
            kept = Counter(map(self.market, within))
            cnt = {m: c - kept.get(m, 0) for m, c in self._week_counts.items() if c - kept.get(m, 0) > 0}
        self._push_done(len(overflow), cnt)
        self._push_ends(overflow)

    def _push_done(self, n: int, cnt) -> None:
        p = self.pushed
        for m, k in cnt.items():
            p[m] = p.get(m, 0) + k
        self._carried, self._carried_counts = n, dict(cnt)
        self._week_counts = None

    def _push_ends(self, overflow: Sequence[str]) -> None:
        self._carried_ends = (overflow[0], overflow[-1]) if len(overflow) else (None, None)

    # -- 新しい二つの方式 ----------------------------------------------------
    def split(self, week_lots: Sequence[str], n: int) -> Tuple[List[str], List[str]]:
        """週の並び week_lots から n 個を押し戻す。戻り値 (残す lot, 押し戻す lot)。
        どちらも「要求週 → 市場キー → 連番」の順。"""
        by_m: Dict[str, List[str]] = {}
        get = self._mkt.get
        # observe() で末尾が前の週の押し戻しと分かっていれば、その市場ごとの並び（並べ替え済み）を
        # 使い、それより前の lot だけを市場に分ける（速さのため。結果は同じ）
        runs = self._carried_runs if len(week_lots) == self._observed_len else None
        head = week_lots[:self._orig_len] if runs is not None else week_lots
        for lot in head:
            m = get(lot)
            if m is None:
                m = self._learn(lot)
            lst = by_m.get(m)
            if lst is None:
                by_m[m] = [lot]
            else:
                lst.append(lot)
        if runs is not None:
            for m, run in runs.items():
                lst = by_m.get(m)
                by_m[m] = list(run) if lst is None else lst + run
        self._carried_runs = None
        if self.policy == PROPORTIONAL_WEEK:
            alloc = self._alloc_proportional(by_m, n)
        elif self.policy == BALANCE_CUT_RATIO:
            alloc = self._alloc_balance(by_m, n)
        else:  # pragma: no cover - tail は Backward が今の経路で処理する
            raise ValueError("split() is not used for tail")
        # 並べ替えのキー (要求週, 市場キー, 連番)。市場の中では市場キーが同じなので (要求週, 連番) の順
        order = self._ord.__getitem__
        keep: List[str] = []
        push: List[str] = []
        push_by_m: Dict[str, List[str]] = {}
        for m, lots in by_m.items():
            k = alloc.get(m, 0)
            if not k:
                keep.extend(lots)
                continue
            # 市場の中：要求週の遅いもの → 連番の大きいものから押し戻す
            lots.sort(key=order)
            cut = len(lots) - k
            keep.extend(lots[:cut])
            run = lots[cut:]
            push.extend(run)
            push_by_m[m] = run
        self._push_done(len(push), {m: k for m, k in alloc.items() if k})
        keep.sort(key=order)
        push.sort(key=order)
        self._push_ends(push)
        self._carried_by_m = push_by_m
        return keep, push

    def _alloc_proportional(self, by_m: Dict[str, List[str]], n: int) -> Dict[str, int]:
        """§3.1。"""
        mk = sorted(by_m)
        cnt = {m: len(by_m[m]) for m in mk}
        tot = sum(cnt.values())
        raw = {m: Fraction(n * cnt[m], tot) for m in mk}
        for m in mk:
            self._raw[m] = self._raw.get(m, Fraction(0)) + raw[m]
        need = {m: self._raw[m] - self.pushed.get(m, 0) for m in mk}
        alloc = {m: min(cnt[m], max(0, int(need[m]))) for m in mk}   # floor（負は 0）
        rem = n - sum(alloc.values())
        if rem < 0:
            # その週に lot の無い市場の累積の不足が負のとき、floor の合計が n を超えうる
            # （参照計算の例には現れない）。超えた分を、配る順の逆（不足の小さい市場）から戻す。
            while rem < 0:
                cand = [m for m in mk if alloc[m] > 0]
                m = sorted(cand, key=lambda m: (need[m] - alloc[m], raw[m], _rev(m)))[0]
                alloc[m] -= 1
                rem += 1
        while rem > 0:
            cand = [m for m in mk if alloc[m] < cnt[m]]
            # 同点：累積の不足の大きい順 → その週の丸め前の大きい順 → 市場キーの文字の順
            m = sorted(cand, key=lambda m: (-(need[m] - alloc[m]), -raw[m], m))[0]
            alloc[m] += 1
            rem -= 1
        return alloc

    def _alloc_balance(self, by_m: Dict[str, List[str]], n: int) -> Dict[str, int]:
        """§3.2。負担率の比較は整数の掛け算（a/b < c/d ⇔ a·d < c·b、b,d > 0）。"""
        mk = sorted(by_m)
        avail = {m: len(by_m[m]) for m in mk}
        num = {m: self.pushed.get(m, 0) for m in mk}
        den = {m: self.den[m] for m in mk}       # その週の lot は observe() 済み → 1 以上
        alloc = self._balance_prefix(mk, avail, num, den, n)
        for _ in range(n - sum(alloc.values())):
            best = None
            for m in mk:
                if alloc[m] >= avail[m]:
                    continue
                if best is None:
                    best = m
                    continue
                a, b = num[m] + alloc[m] + 1, den[m]
                c, d = num[best] + alloc[best] + 1, den[best]
                lhs, rhs = a * d, c * b
                if lhs < rhs or (lhs == rhs and (avail[m] > avail[best]
                                                 or (avail[m] == avail[best] and m < best))):
                    best = m
            alloc[best] += 1
        return alloc

    @staticmethod
    def _balance_prefix(mk, avail, num, den, n) -> Dict[str, int]:
        """1 lot ずつの選び方と同じ結果になる、まとめての割り当て（速さのため）。

        市場 m の k 回目の押し戻し（k = 1..avail_m）の「足した後の負担率」は (num_m + k) / den_m で、
        週の中では avail が変わらないので、1 lot ずつの選び方は全市場の (m, k) を
        （負担率 → その週の lot の多い順 → 市場キー）の順に並べた先頭 n 個を取るのと同じ。
        ある値 V 以下の (m, k) を全部取ると、同じ値のものも全部入るので、その集まりは並びの先頭になる。
        V を浮動小数で見つけ、整数で数え直して n を超えない V だけを使う（残りは 1 lot ずつ）。
        """
        zero = {m: 0 for m in mk}
        target = n - 2 * len(mk)
        if target <= 0:
            return zero

        def count(v: float) -> int:
            return sum(min(avail[m], max(0, int(v * den[m]) - num[m])) for m in mk)

        lo, hi = 0.0, max((num[m] + avail[m]) / den[m] for m in mk)
        for _ in range(60):
            mid = (lo + hi) / 2
            if count(mid) <= target:
                lo = mid
            else:
                hi = mid
        base = {m: min(avail[m], max(0, int(lo * den[m]) - num[m])) for m in mk}
        picked = [Fraction(num[m] + base[m], den[m]) for m in mk if base[m] > 0]
        if not picked:
            return zero
        V = max(picked)
        exact = {m: min(avail[m], max(0, (V.numerator * den[m]) // V.denominator - num[m])) for m in mk}
        if sum(exact.values()) > n:
            return zero
        return exact

    # -- 報告 --------------------------------------------------------------
    def summary(self) -> Dict[str, Dict[str, int]]:
        """市場ごとの {pushed: 延べの押し戻し, denominator: 母数}。数えられなかったときは空。"""
        if not self.stats_ok:
            return {}
        out: Dict[str, Dict[str, int]] = {}
        for m in sorted(set(self.den) | set(self.pushed)):
            out[m] = {"pushed": self.pushed.get(m, 0), "denominator": self.den.get(m, 0)}
        return out


def _rev(s: str) -> Tuple[int, ...]:
    """文字の順の逆の並べ替えキー。"""
    return tuple(-ord(c) for c in s) + (0,)


__all__ = [
    "TAIL", "PROPORTIONAL_WEEK", "BALANCE_CUT_RATIO", "POLICIES",
    "OverflowPolicyError", "OverflowTracker", "resolve_overflow_policy",
]
