"""設計書 WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3 §4 の小例の参照計算（Claude君、2026-11-18）。

エンジンではない。規則の意味を固定するための素朴な実装。単体テストの期待値はこの出力に合わせる。
lot = (市場キー, 要求週の番号, 連番)。処理は Backward と同じ順（計画の最後の週から最初の週へ）に与える。
"""
from fractions import Fraction as F


def pick_within(lots_m, k):
    """市場の中で押し戻す lot：要求週の遅いものから、同じ週は連番の大きいものから（行の順に依らない）。"""
    return sorted(lots_m, key=lambda l: (-l[1], -l[2]))[:k]


def split_proportional_week(week_lots, n, st):
    """案 C：その週の市場の lot の数に比例。端数は累積の丸め誤差（累積の丸め前の割当 − 累積の実際の押し戻し）で配る。"""
    mk = sorted({l[0] for l in week_lots})
    cnt = {m: sum(1 for l in week_lots if l[0] == m) for m in mk}
    tot = sum(cnt.values())
    raw = {m: F(n * cnt[m], tot) for m in mk}
    for m in mk:
        st["raw"][m] = st["raw"].get(m, 0) + raw[m]
    need = {m: st["raw"][m] - st["act"].get(m, 0) for m in mk}
    alloc = {m: min(cnt[m], max(0, int(need[m]))) for m in mk}
    rem = n - sum(alloc.values())
    while rem > 0:
        cand = [m for m in mk if alloc[m] < cnt[m]]
        # 同点：累積の不足の大きい順 → その週の丸め前の大きい順 → 市場キーの文字の順
        m = sorted(cand, key=lambda m: (-(need[m] - alloc[m]), -raw[m], m))[0]
        alloc[m] += 1
        rem -= 1
    for m in mk:
        st["act"][m] = st["act"].get(m, 0) + alloc[m]
    return alloc


def split_balance_burden(week_lots, n, st):
    """案 C_a2：累積押戻負担率（延べの押し戻し ÷ 処理済みの週に現れた lot の数〔重複なし〕）が小さい市場から 1 lot ずつ。
    同点：その週の lot の多い順 → 市場キーの文字の順。"""
    mk = sorted({l[0] for l in week_lots})
    for l in week_lots:
        if l not in st["seen"]:
            st["seen"].add(l)
            st["den"][l[0]] = st["den"].get(l[0], 0) + 1
    avail = {m: [l for l in week_lots if l[0] == m] for m in mk}
    alloc = {m: 0 for m in mk}
    for _ in range(n):
        cand = [m for m in mk if alloc[m] < len(avail[m])]
        m = sorted(cand, key=lambda m: (F(st["num"].get(m, 0) + alloc[m] + 1, st["den"][m]), -len(avail[m]), m))[0]
        alloc[m] += 1
    for m in mk:
        st["num"][m] = st["num"].get(m, 0) + alloc[m]
    return alloc


POLICIES = {"proportional_week": split_proportional_week, "balance_cut_ratio": split_balance_burden}


def new_state():
    return {"raw": {}, "act": {}, "seen": set(), "den": {}, "num": {}}


def run(policy, rounds, caps, order=None):
    """rounds：処理の順の週ごとの {市場: 新しい lot の数}。caps：その週の能力（0 は休業と同じ扱い）。
    押し戻した lot は次に処理する週の並びに入る。最後の週（計画の最初）で残った lot は落ちる。
    order：市場を足す順（行の順の代わり）。結果がこれに依らないことを確かめる。"""
    st = new_state()
    carry, pushed, seq = [], {}, {}
    for i, (new, c) in enumerate(zip(rounds, caps)):
        lots = []
        for m in (order or sorted(new)):
            for _ in range(new.get(m, 0)):
                seq[m] = seq.get(m, 0) + 1
                lots.append((m, i, seq[m]))
        lots = lots + carry
        n = max(0, len(lots) - c)
        carry = []
        if n == 0:
            continue
        alloc = POLICIES[policy](lots, n, st)
        for m, k in alloc.items():
            pushed[m] = pushed.get(m, 0) + k
            carry += pick_within([l for l in lots if l[0] == m], k)
    lost = {}
    for l in carry:
        lost[l[0]] = lost.get(l[0], 0) + 1
    return pushed, lost, sorted(carry)


def independent_weeks(policy, weeks):
    """押し戻しを次の週に入れない（端数の規則だけを見る）。weeks：[({市場: lot}, 押し戻す数), ...]"""
    st, tot = new_state(), {}
    for i, (lots_by_m, n) in enumerate(weeks):
        lots = [(m, i, j) for m, k in lots_by_m.items() for j in range(k)]
        for m, k in POLICIES[policy](lots, n, st).items():
            tot[m] = tot.get(m, 0) + k
    return tot


if __name__ == "__main__":
    print("例1 C", independent_weeks("proportional_week", [({"A": 3, "B": 1}, 2)] * 4))
    print("例2 C 並び替え", independent_weeks("proportional_week", [({"B": 1, "A": 3}, 2)] * 4))
    print("例3 C", independent_weeks("proportional_week", [({"A": 10, "B": 1}, 2)] * 10))
    print("例3 C_a2", independent_weeks("balance_cut_ratio", [({"A": 10, "B": 1}, 2)] * 10))
    r = [{"A": 3, "B": 1}] * 6
    for p in POLICIES:
        print("例4 休業", p, run(p, r, [3, 3, 0, 3, 3, 3])[:2])
        print("例5 連続の不足", p, run(p, r, [3] * 6)[:2])
        a = run(p, r, [3, 3, 0, 3, 3, 3], order=["A", "B"])
        b = run(p, r, [3, 3, 0, 3, 3, 3], order=["B", "A"])
        print("例6 行の順の入れ替え", p, "同じ" if a == b else "違う")
