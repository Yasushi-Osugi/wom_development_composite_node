"""BS-SEAF 検証報告（化粧品）の図を作る。

使い方：python docs/development/WOM_BSSEAF_Verification_Cosmetics_Report_figures/make_figures.py
数字は各報告書の値を写したもの（この図で計算し直さない）。
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))

_JA = ["Noto Sans CJK JP", "Yu Gothic", "Meiryo", "MS Gothic", "IPAexGothic"]
_have = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = [f for f in _JA if f in _have] or ["sans-serif"]

STAGES = ["1 要件", "2 意味モデル\n検索・作成", "3 差分分析", "4 試行",
          "5 人の選択", "6 適用・実行", "7 独立検証", "8 知識・根拠"]

# 周回：(名前, 日付, {段階: 中身}, [(段階, 誤りの印)])
ROUNDS = [
    ("① 品質と残存期間", "10-24〜25",
     {1: "品質・残存", 2: "COS-R01〜", 3: "対応表", 5: "D1〜D7", 4: "B0・B1",
      6: "歩留まり\nPart A", 8: "§2.4 適用条件"}, [(3, "E1・E2")]),
    ("② 店頭在庫と平準化", "10-25",
     {1: "店頭在庫", 3: "X2 の置き場", 4: "B2・B3", 5: "D12〜D14",
      6: "warmup\ncap_soft 等", 8: "R18"}, [(3, "E3")]),
    ("③ 変更課題①〜③", "10-25",
     {1: "海上・開店\n・タイ", 3: "Data のみ", 4: "C1〜C3b", 8: "報告書"}, [(2, "E4")]),
    ("④ 供給配分の意味", "10-26",
     {2: "①〜⑤\n三層設計", 3: "ALC-Q01〜", 5: "J1〜J4", 6: "数量配分\nモード",
      7: "GPT君\n読解試験", 8: "Start Here\n§0.1・R21"}, []),
    ("⑤ 配分 P0・P1・D8", "10-26",
     {4: "P0・P1", 5: "D21〜D24", 6: "D8", 7: "GPT君", 8: "境界の効果\nR22"}, []),
    ("⑥ 金額", "10-30",
     {1: "金額", 3: "置き方", 5: "M1〜M8", 4: "M0", 7: "GPT君", 8: "G1〜G5"}, [(3, "E5")]),
    ("⑦ 利益による配分", "10-30",
     {2: "U3", 3: "コードで\n先に確認", 5: "U3 採用", 4: "P2-a", 7: "GPT君\nP0 の行",
      8: "§7 有効な能力"}, []),
    ("⑧ 正式なモデルへ", "10-30",
     {5: "M0 を採用", 6: "data/sample\n登録", 7: "大杉さん\nGUI", 8: "Start Here\n§4.1"}, []),
]


def fig_loop(path):
    fig, ax = plt.subplots(figsize=(13, 6.8))
    n = len(ROUNDS)
    for r, (name, date, cells, errs) in enumerate(ROUNDS):
        y = n - 1 - r
        for s in range(1, 9):
            on = s in cells
            ax.add_patch(plt.Rectangle((s - 0.47, y - 0.42), 0.94, 0.84,
                                       facecolor="#cfe3f5" if on else "#f4f4f4",
                                       edgecolor="#9db8d0" if on else "#e2e2e2"))
            if on:
                ax.text(s, y, cells[s], ha="center", va="center", fontsize=7.5)
        for s, lab in errs:
            ax.add_patch(plt.Rectangle((s - 0.47, y - 0.42), 0.94, 0.84, fill=False,
                                       edgecolor="#c0392b", linewidth=2.2))
            ax.text(s + 0.44, y + 0.38, lab, ha="right", va="top", fontsize=7.5,
                    color="#c0392b", fontweight="bold")
        ax.text(0.4, y, f"{name}\n{date}", ha="right", va="center", fontsize=8.5)
    ax.set_xlim(-1.9, 8.6)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks(range(1, 9))
    ax.set_xticklabels(STAGES, fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title("図1 8 つの検討の反復（青：その反復で通った段階、赤枠：誤りの型の段階）", fontsize=11, pad=34)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_alloc(path):
    # P2-a 報告書 T9（評価の額の P2-a1 との差、円）と ⑤（lot、2 SKU 合計）
    cases = ["P2-a1\n利益の順", "P2-a2\n僅差は比例", "P1\nタイから減らす", "P0\n配分しない"]
    rule = [0, -58_140, -198_432, 0]
    boundary = [0, -501_240, 0, 0]
    p0 = [0, 0, 0, 302_808]
    fifth = [4, 8, 4, 192]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [3, 2]})
    x = range(len(cases))
    a1.bar(x, rule, color="#5b8db8", label="配分の規則による差")
    a1.bar(x, boundary, bottom=rule, color="#e08a3c", label="追加の ⑤（境界の効果）による差")
    a1.bar(x, p0, color="#7aa974", label="P0 の純差額（境界 +501,240、規則 −198,432）")
    for i, v in enumerate([0, -559_380, -198_432, 302_808]):
        a1.text(i, v + (15_000 if v >= 0 else -15_000), f"{v:+,}" if v else "基準",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    a1.axhline(0, color="#555", linewidth=0.8)
    a1.set_xticks(list(x))
    a1.set_xticklabels(cases, fontsize=9)
    a1.set_ylabel("P2-a1 との差（円、3 年）")
    a1.set_ylim(-700_000, 450_000)
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    a1.legend(fontsize=8, loc="upper left")
    a1.set_title("評価の額の差（P2-a1・P2-a2・P1 の 3 案は売上の 0.05% 未満、\nP0 を含む 4 案の最大は約 0.075%）", fontsize=10)
    a2.bar(x, fifth, color="#b0b0b0")
    for i, v in enumerate(fifth):
        a2.text(i, v + 3, str(v), ha="center", fontsize=9)
    a2.set_xticks(list(x))
    a2.set_xticklabels(cases, fontsize=9)
    a2.set_ylabel("⑤ 配分後の未充足（lot、2 SKU）")
    a2.set_title("⑤（P0 は押し戻しの順でタイが残る）", fontsize=10)
    fig.suptitle("図2 配分の試行の比較（評価の額は営業利益ではない。P2-a 報告書 T9）", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    fig_loop(os.path.join(HERE, "fig1_loop_rounds.png"))
    fig_alloc(os.path.join(HERE, "fig2_allocation_comparison.png"))
    print("written")
