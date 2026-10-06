#!/usr/bin/env python3
"""Independent CSV/JSON analysis of the fixed-SHA Rice DAL Trial.

This tool imports no WOM planner, LOVEM encoder/decoder or checker.
  python -m tools.analyze_rice_dal_trial analyze --out /absolute/output
  python -m tools.analyze_rice_dal_trial verify-lovem --out /absolute/output
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
from itertools import groupby
import json
from pathlib import Path
import sqlite3
import tempfile
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_SHA = "d848c5fa0565d70f6817c1a0257341067712deca"
CASES = ("baseline", "legacy_calendar", "dal_current", "dal_increased")
REPORT_START, REPORT_END = "2027-W01", "2028-W52"


def read_json(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def lines(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def csv_rows(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def cash_totals(path, start=None, end=None):
    d = pd.read_csv(path)
    if start:
        d = d[d.week.between(start, end)]
    revenue = float((d.qty * d.market_revenue_base).sum())
    cost = float((d.qty * d.forward_cost_base).sum())
    return dict(shipped_lots=int(d.qty.sum()), revenue_jpy=revenue, cost_jpy=cost,
                gross_profit_jpy=revenue - cost,
                gross_margin=(revenue - cost) / revenue if revenue else None,
                aggregate_sale_records=len(d))


def analyze(out):
    dst = out / "analysis"; dst.mkdir(exist_ok=True)
    sums, q4s, inventory, co_compare, examples, q1_year = [], [], [], [], [], []
    cache = {}
    for case in CASES:
        raw = out / "raw" / case
        man = read_json(raw / "run_manifest.json")
        assert man["baseline_sha"] == BASE_SHA and man["model_unchanged"]
        summary = read_json(raw / "summary.json")
        n = pd.read_csv(raw / "node_week.csv")
        ms = pd.read_csv(raw / "market_summary.csv")
        q = pd.read_csv(raw / "q1_field_placement.csv.gz")
        market = pd.read_csv(raw / "market_lot_status.csv.gz")
        ships = pd.read_csv(raw / "actual_shipments.csv.gz")
        fwd = read_json(raw / "forward_results.json.gz")
        bwd = read_json(raw / "backward_results.json.gz")
        cache[case] = n
        for scope in ("all", "report"):
            r = ms[ms.scope == scope]
            row = dict(case=case, scope=scope, demand=int(r.demand.sum()),
                       on_time=int(r.on_time.sum()), late=int(r.late.sum()),
                       early=int(r.early.sum()), not_shipped=int(r.not_shipped.sum()),
                       shipped_for_cohort=int(r.actual_shipped_for_cohort.sum()))
            assert row["demand"] == row["on_time"] + row["late"] + row["early"] + row["not_shipped"]
            row["on_time_fill_rate"] = row["on_time"] / row["demand"]
            row["cohort_fill_by_end"] = row["shipped_for_cohort"] / row["demand"]
            row["max_delay_weeks"] = int(r.max_delay_weeks.max())
            row["ppc"] = cash_totals(raw / "ppc/ppc_lot_reconciliation.csv",
                                     REPORT_START if scope == "report" else None, REPORT_END)
            # Cash revenue is by shipment week, not by the request cohort above.
            actual_leaf = ships[ships.node_id.str.startswith("OUT:leaf_out:")]
            if scope == "report": actual_leaf = actual_leaf[actual_leaf.week.between(REPORT_START, REPORT_END)]
            assert row["ppc"]["shipped_lots"] == len(actual_leaf)
            assert r.duplicate_shipped_ids.sum() == 0
            row["opening_inv_synthetic"] = summary["opening_inv_total"]
            sums.append(row)
        for (prod, node), g in n.groupby(["product", "node"]):
            inventory.append(dict(case=case, product=prod, node=node,
                                  peak_I=int(g.I.max()), lot_weeks_I=int(g.I.sum()),
                                  min_I=int(g.I.min()), first_I=int(g.I.iloc[0]), last_I=int(g.I.iloc[-1]),
                                  report_start_I=int(g[g.week == REPORT_START].I.iloc[0]),
                                  report_lot_weeks_I=int(g[g.week.between(REPORT_START, REPORT_END)].I.sum())))
        for prod, g in q.groupby("product"):
            for year, z in g.groupby(g.market_due_week.str[:4]):
                q1_year.append(dict(case=case, product=prod, market_year=year, field_P=len(z),
                    noncrop_P=int((~z.is_harvest_week).sum()), latest_crop_match=int(z.matches_latest_eligible_harvest.sum()),
                    no_prior_crop=int(z.no_prior_crop_in_horizon.sum())))
            before = pd.read_csv(raw / f"{prod}_post_backward_field_P.csv.gz")
            after = pd.read_csv(raw / f"{prod}_post_backward_hooks_field_P.csv.gz")
            assert len(before) == len(set(before.lot_id)) and len(after) == len(set(after.lot_id))
            if case.startswith("dal"):
                assert Counter(zip(before.week, before.lot_id)) == Counter(zip(after.week, after.lot_id))
                assert Counter(zip(after.week, after.lot_id)) == Counter(zip(g.field_P_week, g.lot_id))
            else:
                dropped = set(before.lot_id) - set(after.lot_id)
                co_compare.append(dict(case=case, product=prod, before_field_P=len(before),
                                       after_harvest_field_P=len(after), omitted_by_harvest=len(dropped)))
            result = fwd[prod]
            events = pd.DataFrame(result["cap_hard_events"], columns=["node_id", "week", "deferred_count"])
            for node in ("Seihaku_E", "Seihaku_W"):
                gg = n[(n["product"] == prod) & (n.node == node)]
                cap = gg.cap_hard.map(lambda x: int(x) if x > 0 else np.inf)
                over = gg.demand_P > cap
                ev = events[events.node_id == gg.node_id.iloc[0]]
                assert not (gg.supply_P > cap).any()
                q4s.append(dict(case=case, product=prod, node=node,
                               weekly_capacities=sorted(gg.cap_hard.unique().tolist()),
                               planned_P=int(gg.demand_P.sum()), actual_P=int(gg.supply_P.sum()),
                               actual_S=int(gg.actual_S.sum()), planned_over_capacity_weeks=int(over.sum()),
                               peak_planned_P=int(gg.demand_P.max()), max_realized_P=int(gg.supply_P.max()),
                               capacity_deferred_lot_weeks=int(ev.deferred_count.sum()),
                               capacity_deferred_weeks=len(ev)))
            if case == "dal_current":
                # One demand-anchored ID from each crop. Preserve every node's observed shipment.
                candidates = market[(market["product"] == prod) & (market.required_week == "2027-W01") &
                                    (market.status == "late")].sort_values("lot_id")
                selected = candidates.iloc[0].to_dict()
                lid = selected["lot_id"]
                actual = ships[ships.lot_id == lid][["node", "node_id", "week", "week_index", "sequence"]].to_dict("records")
                field = g[g.lot_id == lid].to_dict("records")
                examples.append(dict(product=prod, lot_id=lid, market=selected, field=field, actual_ships=actual))
        # A supply CO[n] is not stored. Derive final backlog from unmatched demand IDs;
        # show that missing IDs appear in the final/preceding CO or explicit period edge.
        for leaf, g in market.groupby("node_id"):
            pending = g[g.status == "not_shipped"]
            assert len(g) == g.lot_id.nunique()
            assert pending.lot_id.nunique() == len(pending)
    pd.DataFrame([{k:v for k,v in r.items() if k != "ppc"} | {"ppc_"+k:v for k,v in r["ppc"].items()}
                  for r in sums]).to_csv(dst / "case_comparison.csv", index=False)
    pd.DataFrame(q4s).to_csv(dst / "polishing_capacity.csv", index=False)
    pd.DataFrame(inventory).to_csv(dst / "node_inventory_summary.csv", index=False)
    pd.DataFrame(co_compare).to_csv(dst / "harvest_plugin_omissions.csv", index=False)
    pd.DataFrame(q1_year).to_csv(dst / "field_placement_by_market_year.csv", index=False)
    write_json(dst / "lot_examples.json", examples)
    write_json(dst / "analysis_summary.json", dict(cases=sums, polishing=q4s, legacy_harvest_omissions=co_compare))
    plots(dst, cache, examples)
    print("ANALYSIS_COMPLETE", len(sums), "case/window totals", flush=True)


def plots(dst, cache, examples):
    figdir = dst / "figures"; figdir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":9, "axes.titlesize":12})
    fig, axes = plt.subplots(1, 3, figsize=(15, 6), constrained_layout=True)
    max_i = max(cache["legacy_calendar"].I)
    for ax, case, title in zip(axes, CASES[1:], ("Calendar-aligned legacy + HarvestBatch", "DAL identity / current crop capacity", "DAL identity / increased crop capacity")):
        n = cache[case]; nodes = list(n[["product","node"]].drop_duplicates().itertuples(index=False, name=None))
        data = np.array([n[(n["product"] == p) & (n.node == node)].I.to_numpy() for p, node in nodes])
        im = ax.imshow(data, aspect="auto", origin="upper", vmin=0, vmax=max_i, cmap="YlOrRd", interpolation="nearest")
        ax.set_yticks(range(len(nodes)), [f"{p[:1]} / {node}" for p,node in nodes])
        labels = n.week.unique(); ticks = [i for i,x in enumerate(labels) if x.endswith("W01")]
        ax.set_xticks(ticks, [labels[i] for i in ticks], rotation=45)
        ax.set_title(title)
        if not data.any(): ax.text(0.5, 0.5, "I = 0 at every node and week", transform=ax.transAxes, ha="center", color="#174c79", bbox=dict(facecolor="white", edgecolor="#174c79"))
    fig.colorbar(im, ax=axes, label="End-of-week inventory (lots)", fraction=.025)
    fig.suptitle("Q2: inventory location — K=Koshihikari, Y=Yumepirika")
    fig.savefig(figdir / "inventory_node_week.png", dpi=160); plt.close(fig)
    n = cache["dal_current"]
    fig, axes = plt.subplots(2, 1, figsize=(13, 6), constrained_layout=True)
    for ax, prod, field in zip(axes, ("Koshihikari","Yumepirika"), ("Tanbo_Niigata","Tanbo_Hokkaido")):
        g = n[(n["product"] == prod)&(n.node == field)]
        ax.plot(g.week_index, g.demand_P, color="#bd4c38", label="Backward planned P")
        ax.plot(g.week_index, g.supply_P, color="#177758", label="Forward realized P")
        ax.plot(g.week_index, g.cap_hard.map(int), color="#344a67", linestyle="--", label="Integer crop capacity")
        ax.set_title(f"{prod}: crop-week production follows overdue demand")
        ax.set_ylabel("Lots / week"); ax.legend(loc="upper left", ncol=3)
        ticks=g[g.week.str.endswith("W01")]
        ax.set_xticks(ticks.week_index, ticks.week, rotation=0)
        ax.grid(alpha=.18)
    fig.savefig(figdir / "field_planned_vs_realized.png", dpi=160); plt.close(fig)
    fig, axes=plt.subplots(2,2,figsize=(13,7),constrained_layout=True)
    for row,prod in enumerate(("Koshihikari","Yumepirika")):
        for col,node in enumerate(("Seihaku_E","Seihaku_W")):
            ax=axes[row,col]; g=n[(n["product"]==prod)&(n.node==node)]
            ax.plot(g.week_index,g.demand_P,label="Planned P",color="#bd4c38")
            ax.plot(g.week_index,g.supply_P,label="Realized P",color="#177758")
            ax.plot(g.week_index,g.cap_hard,label="Capacity",ls="--",color="#344a67")
            ax.set_title(f"{prod} / {node}");ax.set_ylabel("Lots / week")
            ticks=g[g.week.str.endswith("W01")]; ax.set_xticks(ticks.week_index,ticks.week)
            ax.grid(alpha=.18)
            if row==0 and col==0:ax.legend(ncol=3)
    fig.savefig(figdir / "polishing_planned_vs_realized.png",dpi=160);plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(13,6),constrained_layout=True)
    for ax, ex in zip(axes,examples):
        ships=ex["actual_ships"]; labels=[r["node"] for r in sorted(ships,key=lambda r:r["week_index"],reverse=True)]
        ships=sorted(ships,key=lambda r:r["week_index"],reverse=True)
        xs=[r["week_index"] for r in ships]
        ax.plot(xs,range(len(xs)),marker="o",color="#d0aa00",lw=2)
        ax.set_yticks(range(len(xs)),labels);ax.invert_yaxis()
        due=int(ex["market"]["required_week_index"])
        ax.axvline(due,color="#bd4c38",ls="--",label="Market due week")
        lo=min([due]+xs)-2;hi=max([due]+xs)+2
        weeklabels={int(r.week_index):r.week for r in cache["dal_current"].itertuples()}
        ticks=sorted(set([due,min(xs),max(xs)]))
        ax.set_xticks(ticks,[weeklabels[i] for i in ticks],rotation=35)
        for yy,xx in enumerate(xs):
            ax.annotate(weeklabels[xx],(xx,yy),xytext=(9,0),textcoords="offset points",va="center",fontsize=8)
        ax.set_xlim(lo,hi+8);ax.set_title(f"{ex['product']} / market delay {int(ex['market']['delay_weeks'])} weeks")
        ax.set_xlabel(ex["lot_id"]);ax.grid(alpha=.18);ax.legend(loc="upper left")
    fig.savefig(figdir / "demand_anchored_lot_traces.png",dpi=160);plt.close(fig)


def digest_counter(c):
    def num(q):
        q=float(q);return str(int(q)) if q.is_integer() else repr(q)
    text="\n".join(f"{lot}\t{role}\t{num(q)}\t{m}" for (lot,role,q),m in sorted(c.items(),key=lambda x:(x[0][0],x[0][1])) if m)
    return hashlib.sha256(text.encode()).hexdigest()


def verify_lovem(out):
    """Exact shipment join and streaming multiset reconstruction. No WOM imports."""
    start=time.perf_counter();run=out/"lovem/run_dal_current";dst=out/"analysis"
    manifest=read_json(run/"manifest.json")
    assert manifest["code_sha"]==BASE_SHA and manifest["lot_flow_mode"]=="identity"
    assert manifest["model_unchanged_by_run"]
    assert "HarvestBatchPlugin" not in manifest["plugins"]
    off=read_json(out/"raw/dal_current/fingerprints.json")
    on=read_json(out/"raw/dal_observed/fingerprints.json")
    q12={key:off[key]==on[key] for key in off}
    assert all(q12.values()),q12
    print("Q12_MATCH", q12, flush=True)
    with tempfile.TemporaryDirectory(prefix="rice_lovem_verify_") as tmp:
        db=sqlite3.connect(str(Path(tmp)/"ships.db"))
        db.execute("PRAGMA journal_mode=OFF");db.execute("PRAGMA synchronous=OFF")
        db.execute("CREATE TABLE s (p TEXT,n TEXT,w INT,seq INT,lot TEXT,PRIMARY KEY(p,n,w,seq)) WITHOUT ROWID")
        batch=[];expected=0
        for r in csv_rows(out/"raw/dal_current/actual_shipments.csv.gz"):
            batch.append((r["product"],r["node_id"],int(r["week_index"]),int(r["sequence"]),r["lot_id"]))
            expected+=1
            if len(batch)==10000:
                db.executemany("INSERT INTO s VALUES (?,?,?,?,?)",batch);batch=[]
        if batch:db.executemany("INSERT INTO s VALUES (?,?,?,?,?)",batch)
        db.commit(); matched=0;bad=[];seen_counts=Counter()
        batch=[]
        for r in lines(run/"events.jsonl.gz"):
            if r["event_type"]!="actual_ship":continue
            assert r["quantity"]==1
            batch.append((r["product_id"],r["node_id"],int(r["week_index"]),int(r["sequence"]),r["lot_id"]))
            seen_counts[r["product_id"]]+=1
            if len(batch)==10000:
                before=db.total_changes
                db.executemany("DELETE FROM s WHERE p=? AND n=? AND w=? AND seq=? AND lot=?",batch)
                matched+=db.total_changes-before;batch=[]
        if batch:
            before=db.total_changes
            db.executemany("DELETE FROM s WHERE p=? AND n=? AND w=? AND seq=? AND lot=?",batch)
            matched+=db.total_changes-before
        remaining=db.execute("SELECT COUNT(*) FROM s").fetchone()[0];db.close()
        observed=sum(seen_counts.values())
        assert matched==observed==expected and remaining==0
    print("SHIPMENTS_MATCH",expected,flush=True)
    ds={};empty_hash=hashlib.sha256(b"").hexdigest()
    for r in lines(run/"state_digests.jsonl"):
        key=(r["snapshot_id"],r["product_id"],r["node_id"],r["layer"],r["bucket"],r["week_index"])
        assert key not in ds; ds[key]=r
    matched_d=interval_count=expanded=0;ranges=[];nonempty_seen=set()
    for snap in manifest["snapshots"]:
        path=run/snap["intervals_file"];nweeks=manifest["weeks"]["weeks"]
        first=last=None;file_count=0
        keyfun=lambda r:(r["snapshot_id"],r["product_id"],r["node_id"],r["layer"],r["bucket"])
        visited=set()
        for key, rows in groupby(lines(path),keyfun):
            assert key not in visited;visited.add(key)
            delta=defaultdict(list);last_end={}
            for r in rows:
                iid=int(r["interval_id"][2:]);file_count+=1
                if first is None:first=iid
                if last is not None:assert iid==last+1
                last=iid
                assert r["snapshot_id"]==snap["snapshot_id"]
                s,e=r["start_week_index"],r["end_week_index"]
                assert 0<=s<=e<nweeks and r["multiplicity"]>=1 and r["quantity"]>0
                if r["bucket"] in ("P","S"):assert s==e
                item=(r["lot_id"],r["role_id"],r["quantity"]);m=r["multiplicity"]
                assert s>last_end.get(item,-1);last_end[item]=e
                delta[s].append((item,m));delta[e+1].append((item,-m))
                expanded+=(e-s+1)*m
            active=Counter()
            for w in range(nweeks):
                for item,change in delta.get(w,()):
                    active[item]+=change
                    if active[item]==0:del active[item]
                    else:assert active[item]>0
                fullkey=(*key,w);r=ds[fullkey];nonempty_seen.add(fullkey)
                assert sum(active.values())==r["entry_count"]
                assert sum(k[2]*m for k,m in active.items())==r["total_quantity"]
                assert digest_counter(active)==r["multiset_sha256"],fullkey
                matched_d+=1
        interval_count+=file_count
        assert file_count==snap["n_intervals"]
        if first is not None:ranges.append((first,last))
        print("RESTORED",snap["snapshot_id"],file_count,"intervals",flush=True)
    for key,r in ds.items():
        if key in nonempty_seen:continue
        assert r["entry_count"]==0 and r["total_quantity"]==0 and r["multiset_sha256"]==empty_hash
        matched_d+=1
    ranges.sort()
    for a,b in zip(ranges,ranges[1:]):assert b[0]==a[1]+1
    assert matched_d==len(ds) and interval_count==manifest["counts"]["intervals"]
    result=dict(baseline_sha=BASE_SHA,code_sha=manifest["code_sha"],dirty=manifest["dirty"],
                dirty_explanation="Only untracked trial model/tools; tracked baseline files hash-verified unchanged",
                lot_flow_mode=manifest["lot_flow_mode"],plugins=manifest["plugins"],q12=q12,
                shipments_expected=expected,shipments_observed=observed,shipments_matched=matched,
                shipment_residual=remaining,shipment_counts_by_product=dict(seen_counts),
                digest_rows=len(ds),digest_rows_matched=matched_d,intervals=interval_count,
                expanded_occurrences=expanded,ordered_list_restoration="not claimed; intervals preserve multisets",
                elapsed_seconds=round(time.perf_counter()-start,3))
    write_json(dst/"lovem_independent_verification.json",result)
    print("INDEPENDENT_VERIFICATION_COMPLETE",result,flush=True)


def validate_raw(out):
    """Read every compressed raw file to its end; measure anchor coverage and final CO."""
    checks=[]
    for p in sorted((out/"raw").rglob("*.gz")):
        size=0
        with gzip.open(p,"rb") as f:
            while chunk:=f.read(1<<20):size+=len(chunk)
        checks.append(dict(file=p.relative_to(out).as_posix(),uncompressed_bytes=size,gzip_valid=True))
    run=out/"lovem/run_dal_current";man=read_json(run/"manifest.json")
    pre={r["lot_id"] for r in lines(run/"demand_anchors.jsonl.gz")}
    post={r["lot_id"] for r in csv_rows(out/"raw/dal_current/demand_anchors.csv.gz")}
    added=post-pre;removed=pre-post
    byproduct=lambda s:dict(Counter(lot.split(":")[2] if lot.startswith("HOL:") else lot.split(":",1)[0] for lot in s))
    # Independent final-week CO identity check, not just a count difference.
    w=man["weeks"]["weeks"]-1
    pending=defaultdict(set);co=defaultdict(set);due=defaultdict(set);ship=defaultdict(set)
    for r in csv_rows(out/"raw/dal_current/market_lot_status.csv.gz"):
        if r["status"]=="not_shipped":pending[r["node_id"]].add(r["lot_id"])
        if int(r["required_week_index"])==w:due[r["node_id"]].add(r["lot_id"])
    for r in csv_rows(out/"raw/dal_current/actual_shipments.csv.gz"):
        if r["node_id"].startswith("OUT:leaf_out:") and int(r["week_index"])==w:
            ship[r["node_id"]].add(r["lot_id"])
    for snapshot in man["snapshots"]:
        if snapshot["phase"]!="final":continue
        for r in lines(run/snapshot["intervals_file"]):
            if r["layer"]=="supply" and r["bucket"]=="CO" and r["node_id"].startswith("OUT:leaf_out:") and r["start_week_index"]<=w<=r["end_week_index"]:
                assert r["multiplicity"]==1
                co[r["node_id"]].add(r["lot_id"])
    for node in pending:
        assert pending[node]==(co[node]|due[node])-ship[node]
    result=dict(gzip_files=len(checks),gzip_checks=checks,
                anchors_before_holiday=len(pre),anchors_after_holiday=len(post),
                added_anchor_ids=len(added),removed_anchor_ids=len(removed),
                added_by_product=byproduct(added),removed_by_product=byproduct(removed),
                all_added_have_HOL_prefix=all(x.startswith("HOL:") for x in added),
                terminal_CO_exact_identity_match=True,
                terminal_CO_by_leaf={n:len(s) for n,s in pending.items()},
                terminal_CO_total=sum(map(len,pending.values())))
    write_json(out/"analysis/raw_validation.json",result)
    print("RAW_VALIDATION_COMPLETE",{k:v for k,v in result.items() if k!="gzip_checks"},flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action",choices=("analyze","verify-lovem","validate-raw"));ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args();out=a.out.resolve()
    if a.action=="analyze":analyze(out)
    elif a.action=="verify-lovem":verify_lovem(out)
    else:validate_raw(out)


if __name__=="__main__":main()
