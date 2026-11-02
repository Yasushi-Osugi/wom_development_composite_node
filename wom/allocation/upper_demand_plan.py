# -*- coding: utf-8 -*-
"""
wom/allocation/upper_demand_plan.py — 上位 Demand Plan のモード 1（数量枠を固定）
================================================================================
RequestLetter_BSSEAF_Cosmetics_UpperDemandPlan_U4、
RequestLetter_BSSEAF_Cosmetics_CapacityAwareWeekRule_U4、
詳細設計 docs/design/drafts/WOM_Upper_Demand_Plan_DetailDesign_v0.1.md（v0.3）§2〜§5。

従来の Demand Plan（需要 CSV）の上位の計画。元の需要を台帳に残し、数量枠の中でどの要求週を
残すかを規則で選び（選択の台帳）、実行用の需要 CSV はその派生物として書く。計画の後に、
納品と未充足を元の要求週へ戻して照合する。

    source_demand_ref ＝ sku_id|region|request_week（segment を使うときは |segment を足す）

数量の意味は wom/allocation/handoff.py と同じ：① q1 ＝ ② q2 ＋ ③ q3、② ＝ ④ ＋ ⑤。
時間の可否の診断（time_phased_check）は**参考値**で、期末の未充足の予測値ではない。
⑤ は Forward の後の照合（reconcile_by_request）で確定する。

Backward／Forward は週別の規則を参照して lot を選び直さない。規則は ②③ の選択にだけ効く。
エンジンのコードには触らず、計画の後の木は読むだけ。
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from math import ceil
from fractions import Fraction
from typing import Dict, List, Optional

from wom.allocation.handoff import (DEMAND_COLUMNS, QuantityAllocationError, _largest_remainder,
                                    check_quantity_quota, read_quantity_allocation)
from wom.model.plan_node import S

DEFAULT_WEEK_RULE = "proportional_early_tie"
CUT_REASON = {"proportional_early_tie": "quota_cut_proportional",
              "proportional_even": "quota_cut_even",
              "earliest_first": "quota_cut_latest_first",
              "trim_to_capacity_latest": "quota_cut_trim_to_capacity"}
WEEK_RULES = frozenset(CUT_REASON)
CAPACITY_RULE = "trim_to_capacity_latest"
TIE_KEY = "request_week"
REF_NOTE = "参考値：要求時期までに満たせない量。期末の未充足の予測値ではない"
SS_LEAD_LABEL = "店頭在庫（ss_days）"
FIRST_WEEK_LABEL = "原料の区間（最初の週）"


def approx_conditions(first_week_unusable: bool = False, ss_lead: bool = False) -> str:
    """診断の近似の条件の文字列。入れた条件は「入れた：」に書く。既定は従来の文字列。"""
    on = [x for x, f in ((SS_LEAD_LABEL, ss_lead), (FIRST_WEEK_LABEL, first_week_unusable)) if f]
    off = [x for x, f in ((SS_LEAD_LABEL, ss_lead), (FIRST_WEEK_LABEL, first_week_unusable)) if not f]
    text = ("近似の条件：単一の資源（SKU ごとの工場）、固定の LT、作り置きに上限なし、遅れての生産をしない、"
            + "・".join(off + ["休業"]) + "は入れない")
    return text + ("。入れた：" + "・".join(on) if on else "")


APPROX_CONDITIONS = approx_conditions()
RUN_RULE = "数えない週：その leaf の最初の需要の週より前、元の需要が 0 の週、休業の週（連続は切らない）"
NOT_SPECIFIED = "未指定"          # 実行時に指定されなかった知識の版・判断の参照先（古い値を書かない）


class ReconcileError(ValueError):
    """要求週ごとの照合が Flow Check の表2 や選択の台帳と合わない。"""


def _ref(sku: str, region: str, week: str, segment: str = "") -> str:
    return "|".join((sku, region, week) + ((segment,) if segment else ()))


def _week_key(week: str) -> tuple:
    y, _, w = week.partition("-W")
    return (int(y), int(w))


def _read(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_demand_ledger(model_dir: str, demand_file: str = "demand_forecast.csv",
                        demand_nature: str = "forecast") -> List[dict]:
    """元の需要の台帳。需要 0 の週も行を持つ。鍵・要求週の順（CSV の行の順に頼らない）。"""
    path = os.path.join(model_dir, demand_file)
    rows = _read(path)
    missing = [c for c in DEMAND_COLUMNS if rows and c not in rows[0]]
    if missing:
        raise QuantityAllocationError(f"{path}: missing column(s) {missing}")
    out, seen = [], set()
    for r in rows:
        ref = _ref(r["sku_id"], r["region"], r["week"])
        if ref in seen:
            raise QuantityAllocationError(f"{path}: {ref} appears twice (the ledger key must be unique)")
        seen.add(ref)
        out.append({"source_demand_ref": ref, "sku_id": r["sku_id"], "region": r["region"],
                    "request_week": r["week"], "segment": "", "q1": int(float(r["quantity"] or 0)),
                    "demand_nature": demand_nature})
    out.sort(key=lambda x: (x["sku_id"], x["region"], _week_key(x["request_week"])))
    return out


def _proportional_early_tie(d: Dict[str, int], a: int) -> Dict[str, int]:
    return _largest_remainder({w: float(q) for w, q in d.items()}, a, tie_key=_week_key)


def _proportional_even(d: Dict[str, int], a: int) -> Dict[str, int]:
    """floor の後の残りを、端数の大きい集団から集団の全週へ。残りが集団より少なくなった最後の
    集団だけ、要求週の順の等間隔の位置 i_j ＝ floor((j＋0.5)·n／R') に置く（詳細設計 §3）。
    端数は分数で比べる（同じ端数の週の集まりを、浮動小数の誤差で割らない）。"""
    total = sum(d.values())
    if total <= 0 or a <= 0:
        return {w: 0 for w in d}
    s = {w: a * q // total for w, q in d.items()}
    groups = defaultdict(list)
    for w, q in d.items():
        frac = Fraction(a * q, total) - s[w]
        if frac > 0:
            groups[frac].append(w)
    rest = a - sum(s.values())
    for frac in sorted(groups, reverse=True):
        weeks = sorted(groups[frac], key=_week_key)
        n = len(weeks)
        if rest >= n:
            for w in weeks:
                s[w] += 1
            rest -= n
        else:
            for j in range(rest):
                s[weeks[(2 * j + 1) * n // (2 * rest)]] += 1
            rest = 0
        if rest == 0:
            break
    return s


def _earliest_first(d: Dict[str, int], a: int) -> Dict[str, int]:
    s, left = {}, a
    for w in sorted(d, key=_week_key):
        s[w] = min(d[w], left)
        left -= s[w]
    return s


_RULE_FN = {"proportional_early_tie": _proportional_early_tie,
            "proportional_even": _proportional_even,
            "earliest_first": _earliest_first}


def select_mode1(ledger: List[dict], quota_file: str, week_rule: str = DEFAULT_WEEK_RULE,
                 tie_key: str = TIE_KEY) -> List[dict]:
    """鍵（SKU × region）ごとに s(w) を決める。数量枠は固定。a ＝ Σd の鍵はそのまま。
    止める理由は handoff と同じ（数量枠が元の需要を超える、鍵が無いなど）。"""
    if week_rule == CAPACITY_RULE:
        raise ValueError(f"{CAPACITY_RULE} reads the model: use select_mode1_capacity()")
    if week_rule not in WEEK_RULES:
        raise ValueError(f"week_rule={week_rule!r}: use one of {sorted(WEEK_RULES)}")
    if tie_key != TIE_KEY:
        raise ValueError(f"tie_key={tie_key!r}: mode 1 uses {TIE_KEY}")
    alloc = read_quantity_allocation(quota_file)
    by_key: Dict[tuple, List[dict]] = defaultdict(list)
    for r in ledger:
        by_key[(r["sku_id"], r["region"])].append(r)
    q1 = {k: sum(r["q1"] for r in rows) for k, rows in by_key.items()}
    check_quantity_quota(alloc, q1, "the demand ledger", quota_file)
    stem = os.path.basename(quota_file)
    out = []
    for k in sorted(by_key):
        rows, a = by_key[k], alloc.get(k, 0)
        d = {r["request_week"]: r["q1"] for r in rows}
        s = d if a == q1[k] else _RULE_FN[week_rule](d, a)
        if sum(s.values()) != a or any(not 0 <= s[w] <= d[w] for w in d):
            raise QuantityAllocationError(f"{k}: rule {week_rule} gave an impossible selection")
        for r in rows:
            q2 = s[r["request_week"]]
            q3 = r["q1"] - q2
            reason = ("no_demand" if r["q1"] == 0 else CUT_REASON[week_rule] if q3 else "kept_full")
            out.append({"source_demand_ref": r["source_demand_ref"], "q1": r["q1"], "q2": q2, "q3": q3,
                        "week_rule": week_rule, "tie_key": tie_key, "reason_code": reason,
                        "quota_ref": f"{stem}:{k[0]}|{k[1]}={a}", "policy_ref": "",
                        "sku_id": k[0], "region": k[1], "request_week": r["request_week"]})
    return out


def write_engine_demand(selection: List[dict], model_dir: str, out_path: str,
                        demand_file: str = "demand_forecast.csv") -> dict:
    """選択の台帳から、今と同じ形の需要 CSV を書く（列と行の順は元のまま、数量が変わらない鍵の
    行はそのまま）。読み戻して鍵ごとの合計を照合する。戻り値は handoff と同じ形。"""
    src = os.path.join(model_dir, demand_file)
    with open(src, "r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        fieldnames = list(rd.fieldnames or [])
        dem_rows = list(rd)
    by_ref = {x["source_demand_ref"]: x for x in selection}
    q1, q2 = Counter(), Counter()
    for x in selection:
        q1[(x["sku_id"], x["region"])] += x["q1"]
        q2[(x["sku_id"], x["region"])] += x["q2"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for r in dem_rows:
            x = by_ref[_ref(r["sku_id"], r["region"], r["week"])]
            k = (x["sku_id"], x["region"])
            w.writerow(r if q2[k] == q1[k] else dict(r, quantity=str(x["q2"])))
    back = Counter()
    for r in _read(out_path):
        back[(r["sku_id"], r["region"])] += int(float(r["quantity"] or 0))
    bad = [f"{k}: written {back.get(k, 0)} != selected {v}" for k, v in sorted(q2.items())
           if back.get(k, 0) != v]
    if bad:
        raise QuantityAllocationError("write_engine_demand(): read-back mismatch: " + "; ".join(bad))
    keys = [{"sku_id": k[0], "region": k[1], "q1_original": q1[k], "q2_in_supply_scope": q2[k],
             "q3_not_in_supply_scope": q1[k] - q2[k]} for k in sorted(q1)]
    totals = {c: sum(r[c] for r in keys)
              for c in ("q1_original", "q2_in_supply_scope", "q3_not_in_supply_scope")}
    return {"path": out_path, "keys": keys, "totals": totals}


def time_phased_rows(need: List[int], cap: List[int]) -> tuple:
    """週の列の need・cap から (cum_need, cum_cap, cum_excess の列, ontime_short_ref)。
    ontime_short_ref ＝ max(0, max_t cum_excess(t))（詳細設計 §4）。"""
    cn, cc, ce, n, c = [], [], [], 0, 0
    for a, b in zip(need, cap):
        n += a
        c += b
        cn.append(n)
        cc.append(c)
        ce.append(n - c)
    return cn, cc, ce, max([0] + ce)


def _sku_resources(model_dir: str, skus: List[str], weeks: List[str], first_week_unusable: bool = False,
                   ss_lead: bool = False) -> Dict[str, dict]:
    """SKU ごとの資源。{"cap": 週の良品の能力, "lead": region → 工場までの週} か、適用外なら {"na": 理由}。
    first_week_unusable は計画の最初の週の能力を 0 に、ss_lead は leaf の要求を ceil(ss_days／7) 週早める。"""
    tree = _read(os.path.join(model_dir, "sc_tree_master.csv"))
    cap_rows = _read(os.path.join(model_dir, "capacity_plan.csv"))
    idx = {w: i for i, w in enumerate(weeks)}
    out = {}
    for sku in skus:
        nodes = {r["node_name"]: r for r in tree if r["product_name"] == sku}
        moms = [r for r in nodes.values() if r["node_type"] == "mom"]
        if len(moms) != 1:
            out[sku] = {"na": f"工場（mom）が {len(moms)} 個"}
            continue
        mom = moms[0]
        lead = {}
        for r in nodes.values():
            if r["node_type"] == "leaf_out":
                x, total = r, 0
                while x is not None and x["node_type"] != "supply_point":
                    total += int(float(x.get("lt_wks") or 0))
                    x = nodes.get(x.get("parent_node", ""))
                if ss_lead:
                    total += ceil(float(r.get("ss_days") or 0) / 7)
                lead[r.get("region") or r["node_name"]] = total
        rows = [r for r in cap_rows if r["sku_id"] == sku
                and r.get("node_name", mom["node_name"]) == mom["node_name"]]
        soft = (mom.get("demand_envelope") or "hard").strip() == "soft"
        cols = "cap_soft" if soft and rows and "cap_soft" in rows[0] else "max_supply"
        yld = float(mom.get("yield_rate") or 1.0)
        cap = [0] * len(weeks)
        for r in rows:
            if r["week"] in idx and (r.get(cols) or "") != "":
                cap[idx[r["week"]]] = int(float(r[cols]) * yld + 1e-9)
        if not rows:
            out[sku] = {"na": "能力の行が無い"}
            continue
        if first_week_unusable and cap:
            cap[0] = 0
        out[sku] = {"cap": cap, "lead": lead}
    return out


def time_phased_check(model_dir: str, selection: List[dict], first_week_unusable: bool = False,
                      ss_lead: bool = False) -> List[dict]:
    """時間の可否の診断（参考値）。SKU ごとに工場を一つの資源とみなす。工場が一つでない SKU、
    能力の行が無い SKU は適用外の 1 行を返す。計画の最初の週より前の need はその週に寄せる。
    条件の選択肢の既定は入れない（詳細設計 §4）。使った条件は approx_conditions の列に書く。"""
    weeks = sorted({x["request_week"] for x in selection}, key=_week_key)
    idx = {w: i for i, w in enumerate(weeks)}
    skus = sorted({x["sku_id"] for x in selection})
    res = _sku_resources(model_dir, skus, weeks, first_week_unusable, ss_lead)
    cond = approx_conditions(first_week_unusable, ss_lead)
    out = []
    for sku in skus:
        if "na" in res[sku]:
            out.append({"sku_id": sku, "week": "", "need_good_lots": "", "cap_good_lots": "", "cum_need": "",
                        "cum_cap": "", "cum_excess": "", "ontime_short_ref": "",
                        "note": f"適用外：{res[sku]['na']}", "approx_conditions": cond})
            continue
        cap, lead = res[sku]["cap"], res[sku]["lead"]
        need = [0] * len(weeks)
        for x in selection:
            if x["sku_id"] == sku and x["q2"]:
                need[max(0, idx[x["request_week"]] - lead[x["region"]])] += x["q2"]
        cn, cc, ce, ref = time_phased_rows(need, cap)
        for i, w in enumerate(weeks):
            out.append({"sku_id": sku, "week": w, "need_good_lots": need[i], "cap_good_lots": cap[i],
                        "cum_need": cn[i], "cum_cap": cc[i], "cum_excess": ce[i],
                        "ontime_short_ref": ref, "note": REF_NOTE, "approx_conditions": cond})
    return out


def select_mode1_capacity(ledger: List[dict], quota_file: str, model_dir: str, first_week_unusable: bool = True,
                          ss_lead: bool = True, tie_key: str = TIE_KEY) -> List[dict]:
    """trim_to_capacity_latest（詳細設計 §3.1）。SKU ごとに工場の週を後ろから前へたどり、必要が
    良品の能力を超える分 e(p) を、対応する要求週の、減らす量の残っている鍵から減らす。鍵の間は
    残りの減らす量に比例（同順位は region の名前の順）。残った減らす量は proportional_even で配る。
    台帳の形は select_mode1 と同じ。policy_ref に診断の条件と残りの量を書く。"""
    if tie_key != TIE_KEY:
        raise ValueError(f"tie_key={tie_key!r}: mode 1 uses {TIE_KEY}")
    alloc = read_quantity_allocation(quota_file)
    by_key: Dict[tuple, List[dict]] = defaultdict(list)
    for r in ledger:
        by_key[(r["sku_id"], r["region"])].append(r)
    q1 = {k: sum(r["q1"] for r in rows) for k, rows in by_key.items()}
    check_quantity_quota(alloc, q1, "the demand ledger", quota_file)
    weeks = sorted({r["request_week"] for r in ledger}, key=_week_key)
    idx = {w: i for i, w in enumerate(weeks)}
    skus = sorted({k[0] for k in by_key})
    res = _sku_resources(model_dir, skus, weeks, first_week_unusable, ss_lead)
    s = {k: {r["request_week"]: r["q1"] for r in rows} for k, rows in by_key.items()}
    rest = {}
    for sku in skus:
        keys = [k for k in sorted(by_key) if k[0] == sku]
        left = {k: q1[k] - alloc.get(k, 0) for k in keys}
        if not any(left.values()):
            rest.update(left)
            continue
        if "na" in res[sku]:
            raise QuantityAllocationError(f"{sku}: {CAPACITY_RULE} needs one capacity resource: {res[sku]['na']}")
        cap, lead = res[sku]["cap"], res[sku]["lead"]
        need = [0] * len(weeks)
        at_p = defaultdict(lambda: defaultdict(list))        # 工場の週 → 鍵 → 要求週（遅い順）
        for k in keys:
            for w in sorted(s[k], key=_week_key, reverse=True):
                p = max(0, idx[w] - lead[k[1]])
                need[p] += s[k][w]
                at_p[p][k].append(w)
        for p in range(len(weeks) - 1, -1, -1):
            e = need[p] - cap[p]
            while e > 0:
                room = {k: min(left[k], sum(s[k][w] for w in ws)) for k, ws in at_p[p].items()}
                room = {k: v for k, v in room.items() if v > 0}
                if not room:
                    break
                region_of = {k[1]: k for k in room}
                give = _largest_remainder({r: float(left[k]) for r, k in region_of.items()},
                                          min(e, sum(room.values())))
                for r, k in region_of.items():
                    take = min(give[r], room[k])
                    left[k] -= take
                    need[p] -= take
                    e -= take
                    for w in at_p[p][k]:
                        cut = min(take, s[k][w])
                        s[k][w] -= cut
                        take -= cut
            if not any(left.values()):
                break
        for k in keys:
            rest[k] = left[k]
            if left[k]:
                s[k] = _proportional_even(s[k], sum(s[k].values()) - left[k])
    stem = os.path.basename(quota_file)
    out = []
    for k in sorted(by_key):
        rows, a = by_key[k], alloc.get(k, 0)
        d = {r["request_week"]: r["q1"] for r in rows}
        if sum(s[k].values()) != a or any(not 0 <= s[k][w] <= d[w] for w in d):
            raise QuantityAllocationError(f"{k}: rule {CAPACITY_RULE} gave an impossible selection")
        policy = (f"capacity_check:first_week_unusable={int(first_week_unusable)},"
                  f"ss_lead={int(ss_lead)},rest_lots={rest[k]}")
        for r in rows:
            q2 = s[k][r["request_week"]]
            q3 = r["q1"] - q2
            reason = "no_demand" if r["q1"] == 0 else CUT_REASON[CAPACITY_RULE] if q3 else "kept_full"
            out.append({"source_demand_ref": r["source_demand_ref"], "q1": r["q1"], "q2": q2, "q3": q3,
                        "week_rule": CAPACITY_RULE, "tie_key": tie_key, "reason_code": reason,
                        "quota_ref": f"{stem}:{k[0]}|{k[1]}={a}", "policy_ref": policy,
                        "sku_id": k[0], "region": k[1], "request_week": r["request_week"]})
    return out


def capacity_rule_detail(model_dir: str, selection: List[dict], first_week_unusable: bool = True,
                         ss_lead: bool = True) -> dict:
    """udp_plan.json に書く：診断の条件、残って均等に配った量、減らした後の参考値（条件あり・なし）。"""
    def refs(*flags):
        rows = time_phased_check(model_dir, selection, *flags)
        return {r["sku_id"]: r["ontime_short_ref"] for r in rows}

    rest = {}
    for x in selection:
        rest[f"{x['sku_id']}|{x['region']}"] = int(x["policy_ref"].rpartition("rest_lots=")[2])
    return {"first_week_unusable": first_week_unusable, "ss_lead": ss_lead, "rest_lots_by_key": rest,
            "rest_lots_total": sum(rest.values()),
            "ontime_short_ref_with_conditions": refs(first_week_unusable, ss_lead),
            "ontime_short_ref_without_conditions": refs(False, False)}


def _leaves(sc_tree):
    """(product, leaf node, demand-CSV region)。node_id は OUT:leaf_out:<region>:<product>。"""
    for prod in sc_tree.products:
        for nd in sc_tree.iter_all_nodes(prod):
            if nd.node_type == "leaf_out":
                parts = nd.node_id.split(":")
                yield prod, nd, parts[2] if len(parts) >= 4 else nd.node_name


def reconcile_by_request(sc_tree, selection: List[dict], flow_check_market: List[dict]) -> List[dict]:
    """leaf の lot ごとに s_week と最初の実出荷の週を照合する（表2 と同じ方法を木から行う）。
    leaf ごとの合計が表2 と、要求の lot の数が選択の台帳の q2 と合わなければ止める。"""
    labels = list(sc_tree.week_labels)
    res = {x["source_demand_ref"]: {"source_demand_ref": x["source_demand_ref"], "q2": 0, "on_time": 0,
                                    "early": 0, "late": 0, "q5": 0, "first_ship_weeks": ""}
           for x in selection}
    ships = defaultdict(set)
    errors, leaf_sum = [], {}
    for prod, leaf, region in _leaves(sc_tree):
        s_week, count = {}, 0
        for w in range(len(labels)):
            for lot in leaf.psi4supply[w][S]:
                s_week.setdefault(lot, w)
                count += 1
        if count != len(s_week):
            errors.append(f"{prod}/{leaf.node_name}: {count - len(s_week)} Lot_ID(s) repeated in S")
        first = {}
        for w in sorted(getattr(leaf, "_actual_ship", None) or {}):
            for lot in leaf._actual_ship[w]:
                first.setdefault(lot, w)
        t = Counter()
        for lot, sw in s_week.items():
            ref = _ref(prod, region, labels[sw])
            if ref not in res:
                errors.append(f"{ref}: a lot with no row in the selection ledger")
                continue
            r = res[ref]
            r["q2"] += 1
            w = first.get(lot)
            col = "q5" if w is None else "on_time" if w == sw else "early" if w < sw else "late"
            r[col] += 1
            t[col] += 1
            if w is not None:
                ships[ref].add(w)
        leaf_sum[(prod, leaf.node_name)] = {"demand": len(s_week), "on_time": t["on_time"], "early": t["early"],
                                            "late": t["late"], "backlog_end": t["q5"]}
    for x in selection:
        got = res[x["source_demand_ref"]]["q2"]
        if got != x["q2"]:
            errors.append(f"{x['source_demand_ref']}: {got} request lot(s) != selected q2 {x['q2']}")
    table2 = {(r["product"], r["leaf"]): r for r in flow_check_market}
    for k, v in leaf_sum.items():
        r = table2.get(k)
        if r is None:
            errors.append(f"{k}: not in table 2")
            continue
        bad = [f"{c} {v[c]} != table 2 {r[c]}" for c in v if int(r[c]) != v[c]]
        if bad:
            errors.append(f"{k}: " + ", ".join(bad))
    if errors:
        raise ReconcileError("; ".join(errors))
    for ref, r in res.items():
        r["first_ship_weeks"] = ";".join(labels[w] for w in sorted(ships[ref]))
    return [res[x["source_demand_ref"]] for x in selection]


def supply_runs(sc_tree, selection: List[dict]) -> List[dict]:
    """実際の出荷の週で、leaf ごとの供給 0 の週の数と最長の連続。要求週ごとの未充足とは別の集計。"""
    labels = list(sc_tree.week_labels)
    dem = defaultdict(dict)
    for x in selection:
        dem[(x["sku_id"], x["region"])][x["request_week"]] = x["q1"]
    out = []
    for prod, leaf, region in _leaves(sc_tree):
        d = dem[(prod, region)]
        ship = getattr(leaf, "_actual_ship", None) or {}
        first = next((i for i, w in enumerate(labels) if d.get(w, 0) > 0), None)
        zero, run, best, best_from, start = 0, 0, 0, "", ""
        for i in range(first if first is not None else len(labels), len(labels)):
            if d.get(labels[i], 0) <= 0 or not leaf.is_open(i):
                continue
            if ship.get(i):
                run = 0
                continue
            zero += 1
            run += 1
            if run == 1:
                start = labels[i]
            if run > best:
                best, best_from = run, start
        out.append({"sku_id": prod, "region": region, "zero_supply_weeks": zero, "longest_zero_run": best,
                    "longest_zero_run_from": best_from, "excluded_weeks_rule": RUN_RULE})
    return sorted(out, key=lambda r: (r["sku_id"], r["region"]))


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def input_file_hashes(model_dir: str, demand_file: str, quota_file: str) -> Dict[str, str]:
    """計算に使う入力のファイルだけ（生成した需要 CSV と数量枠の写しは除く）。"""
    quota = os.path.basename(quota_file)
    gen = re.compile(r"^demand_forecast_.+\.csv$")
    out = {"quota:" + quota: _sha256(quota_file)}
    for f in sorted(os.listdir(model_dir)):
        if f.endswith(".csv") and f != quota and (f == demand_file or not gen.match(f)):
            out[f] = _sha256(os.path.join(model_dir, f))
    return out


def write_plan_json(path: str, *, plan_id: str, scenario_id: str, week_rule: str, period: dict,
                    report_start: str, input_hashes: Dict[str, str], outputs: Dict[str, str],
                    quota_sources: List[str], commit: Optional[str], code_dirty: bool,
                    totals: dict, rule_detail: Optional[dict] = None,
                    knowledge_used: Optional[List[dict]] = None,
                    owner_decisions: Optional[List[str]] = None) -> dict:
    body = {"plan_id": plan_id, "scenario_id": scenario_id, "mode": "mode1_fixed_quota",
            "horizon": {"start": period["start"], "end": period["end"], "weeks": period["weeks"]},
            "judgement_week": period["end"], "report_start": report_start,
            "week_rule": week_rule, "tie_key": TIE_KEY, "input_hashes": input_hashes,
            "output_hashes": outputs, "quota_sources": quota_sources,
            "target_commit": commit, "code_dirty": code_dirty,
            "knowledge_used": knowledge_used or NOT_SPECIFIED,
            "owner_decisions": owner_decisions or NOT_SPECIFIED, "totals": totals,
            "calc_status": "計算済み", "consistency_status": "整合",
            "target_status": "未判定", "owner_status": "未判断"}
    if rule_detail is not None:
        body["week_rule_detail"] = rule_detail
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return body


def _write_csv(path: str, columns: List[str], rows: List[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, columns, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_plan_outputs(udp_out: str, plan_id: str, *, model_dir: str, ledger, selection, capacity_check,
                       by_request, supply_runs, demand_file: str, allocation_file: str, generated_csv: str,
                       period: dict, commit: Optional[str], totals: dict, repo: str,
                       rule_detail: Optional[dict] = None,
                       knowledge_used: Optional[List[dict]] = None,
                       owner_decisions: Optional[List[str]] = None) -> str:
    """<udp_out>/<plan_id>/ に 6 ファイルを書く。上書きする（同じ plan_id は同じ入力の再実行）。"""
    from wom.lovem.observer import git_state
    d = os.path.join(udp_out, plan_id)
    os.makedirs(d, exist_ok=True)
    tables = {
        "udp_demand_ledger.csv": (["source_demand_ref", "sku_id", "region", "request_week", "segment",
                                   "q1", "demand_nature"], ledger),
        "udp_selection_ledger.csv": (["source_demand_ref", "q1", "q2", "q3", "week_rule", "tie_key",
                                      "reason_code", "quota_ref", "policy_ref"], selection),
        "udp_capacity_check.csv": (["sku_id", "week", "need_good_lots", "cap_good_lots", "cum_need", "cum_cap",
                                    "cum_excess", "ontime_short_ref", "note", "approx_conditions"],
                                   capacity_check),
        "udp_result_by_request.csv": (["source_demand_ref", "q2", "on_time", "early", "late", "q5",
                                       "first_ship_weeks"], by_request),
        "udp_supply_runs.csv": (["sku_id", "region", "zero_supply_weeks", "longest_zero_run",
                                 "longest_zero_run_from", "excluded_weeks_rule"], supply_runs),
    }
    for name, (cols, rows) in tables.items():
        _write_csv(os.path.join(d, name), cols, rows)
    outputs = {name: _sha256(os.path.join(d, name)) for name in tables}
    outputs["generated_demand_csv"] = _sha256(generated_csv)
    vc = os.path.join(model_dir, "vc_config.csv")
    report = next((r["value"] for r in _read(vc) if r["key"] == "report_start"), "") if os.path.exists(vc) else ""
    alloc_rows = _read(allocation_file)
    sources = sorted({(r.get("quota_source") or "").strip() for r in alloc_rows} - {""})
    write_plan_json(os.path.join(d, "udp_plan.json"), plan_id=plan_id, scenario_id=os.path.basename(model_dir),
                    week_rule=selection[0]["week_rule"] if selection else DEFAULT_WEEK_RULE, period=period,
                    report_start=report, input_hashes=input_file_hashes(model_dir, demand_file, allocation_file),
                    outputs=outputs, quota_sources=sources, commit=commit,
                    code_dirty=git_state(repo)["dirty"], totals=totals, rule_detail=rule_detail,
                    knowledge_used=knowledge_used, owner_decisions=owner_decisions)
    return d
