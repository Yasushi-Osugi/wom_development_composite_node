# -*- coding: utf-8 -*-
"""段 3 §3.2：新しい既定で変わるモデルの差（tail を明示した写しとの比較）。

    python output/roworder_stage3/scripts/golden_diff3.py

出力：output/roworder_stage3/golden_diff3.md・golden_diff3.json
- 19 件（golden 16・legacy 3）の一致・不一致
- 変わったモデル：変わった欄、市場別の当週・遅配・期末の注文残（tail → 既定）、総納品・注文残の合計、
  PPC の売上・粗利、series_md5 が変わったノード、段 2 の proportional_week の snapshot と同じか
"""
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
G = os.path.join(REPO, "output", "roworder_stage3", "golden")
S2 = os.path.join(REPO, "output", "roworder_stage2", "golden")
SUB = "Σ"


def load(kind, m):
    p = os.path.join(G, kind, m + ".json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def totals(market):
    rows = [r for r in market if not str(r["leaf"]).startswith(SUB) and r["leaf"]]
    return {"demand": sum(r["demand"] for r in rows),
            "delivered": sum(r["on_time"] + r["early"] + r["late"] for r in rows),
            "on_time": sum(r["on_time"] for r in rows), "late": sum(r["late"] for r in rows),
            "backlog_end": sum(r["backlog_end"] for r in rows)}, rows


def main():
    out = {"all": [], "changed": {}}
    md = ["# 段 3：新しい既定（proportional_week）で golden を回した結果", "",
          "| 種類 | モデル | golden と一致 | 違う欄 |", "|---|---|---|---|"]
    for kind in ("default", "legacy"):
        for f in sorted(os.listdir(os.path.join(G, kind))):
            m = f[:-5]
            d = load(kind, m)
            out["all"].append({"kind": kind, "model": m, "match": d["golden_match"], "diff": d["golden_diff_keys"]})
            md.append(f"| {kind} | {m} | {'一致' if d['golden_match'] else '**違う**'} | "
                      f"{', '.join(d['golden_diff_keys']) or '—'} |")
    for m in [r["model"] for r in out["all"] if r["kind"] == "default" and not r["match"]]:
        d, t = load("default", m), load("tail", m)
        td, trows = totals(t["market"])
        dd, drows = totals(d["market"])
        mk = []
        tmap = {(r["product"], r["leaf"]): r for r in trows}
        for r in drows:
            a = tmap[(r["product"], r["leaf"])]
            if any(a[k] != r[k] for k in ("on_time", "early", "late", "backlog_end")):
                mk.append({"product": r["product"], "leaf": r["leaf"], "demand": r["demand"],
                           **{f"{k}_tail": a[k] for k in ("on_time", "late", "backlog_end")},
                           **{f"{k}_default": r[k] for k in ("on_time", "late", "backlog_end")}})
        sp, gp = d["snapshot"], t["snapshot"]
        ppc = {k: (gp["ppc"].get(k), sp["ppc"].get(k)) for k in sp["ppc"] if sp["ppc"].get(k) != gp["ppc"].get(k)}
        md5 = [f"{p}/{n}" for p in sp["psi"] for n in sp["psi"][p]
               if sp["psi"][p][n] != gp["psi"].get(p, {}).get(n)]
        s2p = os.path.join(S2, f"{m}_proportional_week.json")
        same_s2 = None
        if os.path.exists(s2p):
            s2 = json.load(open(s2p, encoding="utf-8"))["snapshot"]
            same_s2 = all(s2.get(k) == sp.get(k) for k in ("period", "products", "forward", "backward", "ppc", "psi"))
        out["changed"][m] = {"diff_keys": d["golden_diff_keys"], "totals_tail": td, "totals_default": dd,
                             "markets": mk, "ppc": ppc, "psi_nodes_changed": md5,
                             "same_as_stage2_proportional_week": same_s2,
                             "past_due_total": (t["past_due_total"], d["past_due_total"]),
                             "cap_dropped_total": (t["cap_dropped_total"], d["cap_dropped_total"])}
        md += ["", f"## {m}", "",
               f"- 違う欄：{', '.join(d['golden_diff_keys'])}。段 2 の proportional_week と snapshot が同じ：{same_s2}",
               f"- 合計（tail → 既定）：総納品 {td['delivered']:,} → {dd['delivered']:,}、当週 {td['on_time']:,} → "
               f"{dd['on_time']:,}、遅配 {td['late']:,} → {dd['late']:,}、期末の注文残 {td['backlog_end']:,} → "
               f"{dd['backlog_end']:,}（需要 {td['demand']:,}）",
               f"- 計画の前に落ちた lot（past_due）：{t['past_due_total']:,} → {d['past_due_total']:,}"
               f"（うち工場の能力で {t['cap_dropped_total']:,} → {d['cap_dropped_total']:,}）",
               f"- series_md5 などが変わったノード（{len(md5)}）：{', '.join(md5)}", "",
               "| PPC の項目 | tail | 既定 |", "|---|---|---|"]
        md += [f"| {k} | {a} | {b} |" for k, (a, b) in ppc.items()]
        md += ["", "| 製品 | 市場 | 需要 | 当週 tail → 既定 | 遅配 tail → 既定 | 期末の注文残 tail → 既定 |",
               "|---|---|---|---|---|---|"]
        md += [f"| {r['product']} | {r['leaf']} | {r['demand']:,} | {r['on_time_tail']:,} → {r['on_time_default']:,} | "
               f"{r['late_tail']:,} → {r['late_default']:,} | {r['backlog_end_tail']:,} → {r['backlog_end_default']:,} |"
               for r in mk]
        if not mk:
            md.append("| （市場別の数は 3 つとも同じ） | | | | | |")
    with open(os.path.join(REPO, "output", "roworder_stage3", "golden_diff3.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(REPO, "output", "roworder_stage3", "golden_diff3.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
