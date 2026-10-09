"""Small static comparison from the full measured PSI, without thinning IDs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def plot(evidence_dir, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from .probe_rice_seasonal_definition import FIXTURE, week_labels

    spec = json.loads((FIXTURE / "scenario.json").read_text())
    weeks = week_labels(spec["start_week"], spec["end_week"])
    names = ["Retail_KANSAI", "DC_Nishi", "Seihaku_W", "Genmai_Souko_Niigata",
             "SP_Kome", "Sanchiku_Niigata", "Tanbo_Niigata"]
    labels = ["Market", "DC", "Milling", "Brown-rice warehouse", "SP (virtual)", "Collection", "Field"]
    figure, axes = plt.subplots(2, 1, figsize=(12, 7.2), sharex=True)
    for ax, kind, title in zip(axes, ("serial", "seasonal"),
                              ("Current serial adapter: early milling, stock at market",
                               "Rice two-date adapter: brown stock, milling close to demand")):
        snap = json.loads((Path(evidence_dir) / f"{kind}_full_PSI.json").read_text())
        for y, name in enumerate(names):
            node = snap[name]
            for w, row in enumerate(node["supply"]):
                if row[2]:
                    color = "#198754" if name == "Genmai_Souko_Niigata" else "#e68a00"
                    ax.plot([w - 0.42, w + 0.42], [y, y], color=color, lw=7,
                            solid_capstyle="butt")
                if row[3]:
                    ax.scatter(w - 0.12, y, marker="o", s=65, facecolors="none",
                               edgecolors="#6f42c1", linewidth=1.5, zorder=5)
                if node["actual_ship"].get(str(w)):
                    ax.scatter(w + 0.12, y, marker=">", s=60, c="#1769aa", zorder=6)
        # Physical relations end at P (arrival), not the next node's later S.
        # The virtual supply point is omitted from physical transportation.
        for sender, receiver, lt in (
            ("Tanbo_Niigata", "Sanchiku_Niigata", 1),
            ("Sanchiku_Niigata", "Genmai_Souko_Niigata", 1),
            ("Genmai_Souko_Niigata", "Seihaku_W", 2),
            ("Seihaku_W", "DC_Nishi", 1),
            ("DC_Nishi", "Retail_KANSAI", 1),
        ):
            for wstr, lots in snap[sender]["actual_ship"].items():
                w = int(wstr)
                if lots:
                    arrival = w + lt
                    assert all(lot in snap[receiver]["supply"][arrival][3] for lot in lots)
                    ax.plot([w + 0.12, arrival - 0.12],
                            [names.index(sender), names.index(receiver)],
                            "--", c="#8a939d", lw=1, zorder=0)
        ax.set_yticks(range(len(names)), labels)
        ax.set_ylim(len(names) - 0.6, -0.8)
        ax.set_title(title, loc="left", fontsize=12)
        ax.grid(axis="x", alpha=0.2)
    axes[-1].set_xticks(range(len(weeks)), [w.replace("2026-", "") if w != "2027-W01" else w
                                           for w in weeks], rotation=35, ha="right")
    axes[-1].set_xlabel("ISO week (includes 2026-W53)")
    legend = [Line2D([0], [0], color="#198754", lw=6, label="End-week brown inventory"),
              Line2D([0], [0], color="#e68a00", lw=6, label="End-week white inventory"),
              Line2D([0], [0], marker="o", markerfacecolor="none", markeredgecolor="#6f42c1",
                     linestyle="", label="Receipt / production P"),
              Line2D([0], [0], marker=">", color="#1769aa", linestyle="", label="Actual shipment")]
    figure.legend(handles=legend, loc="lower center", ncol=4, fontsize=9)
    figure.suptitle("One original demand ID — same market due week, different stock placement", fontsize=13)
    figure.tight_layout(rect=(0, 0.06, 1, 0.94))
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plot(args.evidence, args.out)
