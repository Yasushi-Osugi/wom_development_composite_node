"""
ask_global_allocation 地形プロトタイプ（修正版）

修正点: WOM は Demand Anchored のため、需要を超えて生産しない。
        production[m] = min(x[m] * Capacity, Demand[m])
        → 売れ残りは発生せず、余った能力は遊休となる。
"""
import numpy as np

TRANSFER_PRICE_USD = 16.0 * 1.1   # ppc_transfer_price_rule.csv: cost_plus 10%
WEEKS = 104

CHANNELS = {
    "JP": dict(usd=6.0 + 1.1 + 1.0 + 1.0, eur=0.0, jpy=750+750+75+150,
               tariff=0.0,   price=3840.0, ccy="JPY", qty=30150),
    "US": dict(usd=6.0 + 1.1 + 4.25 + 2.3 + 2.0, eur=0.0, jpy=750+750+75,
               tariff=0.125, price=40.0,   ccy="USD", qty=35176),
    "EU": dict(usd=6.0 + 1.1 + 6.0 + 1.5, eur=1.4+0.75, jpy=750+750+75,
               tariff=0.08,  price=38.0,   ccy="EUR", qty=35175),
}
MARKETS = ["JP", "US", "EU"]
DEMAND = {m: CHANNELS[m]["qty"] for m in MARKETS}
TOTAL_DEMAND = sum(DEMAND.values())


def rates(fx):
    return {"JPY": 1.0, "USD": fx, "EUR": fx * 1.08}


def unit(m, fx, mat=6.0):
    c = CHANNELS[m]; r = rates(fx)
    usd = c["usd"] - 6.0 + mat + c["tariff"] * TRANSFER_PRICE_USD
    cost = usd * r["USD"] + c["eur"] * r["EUR"] + c["jpy"]
    rev = c["price"] * r[c["ccy"]]
    fcost = usd * r["USD"] + c["eur"] * r["EUR"]
    frev = rev if c["ccy"] != "JPY" else 0.0
    return dict(rev=rev, cost=cost, margin=rev - cost, fcost=fcost, frev=frev)


def evaluate(x, cap_wk, fx, mat=6.0):
    cap = cap_wk * WEEKS
    ue = {m: unit(m, fx, mat) for m in MARKETS}
    q = {m: min(xi * cap, DEMAND[m]) for m, xi in zip(MARKETS, x)}
    rev = sum(q[m] * ue[m]["rev"] for m in MARKETS)
    cost = sum(q[m] * ue[m]["cost"] for m in MARKETS)
    fcost = sum(q[m] * ue[m]["fcost"] for m in MARKETS)
    frev = sum(q[m] * ue[m]["frev"] for m in MARKETS)
    FCR = fcost / cost if cost else 0
    FRR = frev / rev if rev else 0
    return dict(profit=rev - cost, rev=rev, q=q,
                used=sum(q.values()), idle=cap - sum(q.values()),
                unmet={m: DEMAND[m] - q[m] for m in MARKETS},
                FCR=FCR, FRR=FRR, FXB=FCR / FRR if FRR > 0 else float("inf"))


def grid(delta=0.05):
    n = int(round(1 / delta)); pts = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            pts.append(((n - i - j) / n, i / n, j / n))
    return pts


def analyze(cap_wk, fx, mat=6.0, label=""):
    pts = grid()
    res = [(x, evaluate(x, cap_wk, fx, mat)) for x in pts]
    profits = np.array([r["profit"] for _, r in res])
    best = profits.max()
    # 台地の大きさ = 最大値の 0.1% 以内にある格子点数
    plateau = int((profits >= best - abs(best) * 0.001).sum())
    argmax = [x for x, r in res if r["profit"] >= best - abs(best) * 0.001]

    cap = cap_wk * WEEKS
    print(f"\n{'='*70}\n{label} | 能力 {cap_wk}/週 | USD {fx}円 | 原料 ${mat}")
    print('='*70)
    print(f"総能力 {cap:,} / 総需要 {TOTAL_DEMAND:,} = 充足率 {cap/TOTAL_DEMAND:6.1%}")
    print("\n単位マージン(JPY/lot):")
    order = sorted(MARKETS, key=lambda m: -unit(m, fx, mat)["margin"])
    for rank, m in enumerate(order, 1):
        u = unit(m, fx, mat)
        print(f"  {rank}位 {m}: 売価{u['rev']:8,.0f} 原価{u['cost']:8,.0f} "
              f"マージン{u['margin']:8,.0f} ({u['margin']/u['rev']:6.1%})")

    print(f"\n利益   最大 {best/1e6:9,.1f} / 最小 {profits.min()/1e6:9,.1f} 百万円"
          f"  レンジ {(best-profits.min())/1e6:,.1f}")
    print(f"最適点 台地サイズ = {plateau} / 231 格子点", end="")
    if plateau == 1:
        print("   → ★一意（意思決定が意味を持つ）")
    elif plateau <= 5:
        print("   → 準一意")
    else:
        print("   → ☓ 台地（意思決定が不定・地図が無意味）")
    bx = argmax[0]
    bv = evaluate(bx, cap_wk, fx, mat)
    print(f"  配分 JP={bx[0]:.2f} US={bx[1]:.2f} EU={bx[2]:.2f}"
          f"   遊休能力 {bv['idle']:,.0f} lot")
    print(f"  未充足: " + "  ".join(f"{m}={bv['unmet'][m]:,.0f}" for m in MARKETS))
    print(f"  FCR={bv['FCR']:.3f} FRR={bv['FRR']:.3f} FXB={bv['FXB']:.3f}")

    # 折れ線（尾根）の位置
    print(f"\n  需要天井（尾根線の位置）: " +
          "  ".join(f"x_{m}={DEMAND[m]/cap:.3f}" for m in MARKETS)
          + f"   合計={sum(DEMAND.values())/cap:.3f}")
    return res, plateau, best


if __name__ == "__main__":
    print("#"*70)
    print("# ask_global_allocation 地形プロトタイプ（Demand Anchored 版）")
    print("#"*70)

    cases = [
        (1500, 150, 6.0, "A 現状（能力1500・非拘束）"),
        (1000, 150, 6.0, "B 能力1000"),
        ( 800, 150, 6.0, "C 能力800（推奨）"),
        ( 800, 200, 6.0, "D 能力800・円安"),
        ( 800, 200, 8.0, "E 能力800・円安×原油"),
        ( 800, 115, 6.0, "F 能力800・円高115"),
        ( 800, 110, 6.0, "G 能力800・円高110"),
    ]
    summary = []
    for cap, fx, mat, lbl in cases:
        _, pl, best = analyze(cap, fx, mat, lbl)
        summary.append((lbl, cap, fx, mat, pl, best))

    print("\n\n" + "#"*70)
    print("# サマリ")
    print("#"*70)
    print(f"{'ケース':28s} {'台地':>6s} {'判定':>10s} {'最大利益(百万)':>14s}")
    for lbl, cap, fx, mat, pl, best in summary:
        v = "一意" if pl == 1 else ("準一意" if pl <= 5 else "台地・不定")
        print(f"{lbl:28s} {pl:4d}点 {v:>10s} {best/1e6:14,.1f}")

    # 優先順位の反転点を探す
    print("\n\n" + "#"*70)
    print("# 市場優先順位の反転点（切替点）")
    print("#"*70)
    prev = None
    for fx in range(100, 221, 1):
        order = tuple(sorted(MARKETS, key=lambda m: -unit(m, fx)["margin"]))
        if order != prev:
            m = {k: unit(k, fx)["margin"] for k in MARKETS}
            print(f"  USD {fx:3d}円 で順位 → {' > '.join(order)}"
                  f"   (JP {m['JP']:,.0f} / US {m['US']:,.0f} / EU {m['EU']:,.0f})")
            prev = order
