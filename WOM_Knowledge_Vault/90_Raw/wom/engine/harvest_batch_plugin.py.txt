"""
wom/engine/harvest_batch_plugin.py
HarvestBatchPlugin -- Capacity-aware BatchBackwardPlanning + Opening Inventory injection

HOOK: HOOK_POST_BACKWARD

Step 1 -- P-bucket rescheduling (leaf_in)
  - Finds harvest weeks where cap_hard integer part > 0
  - Collects ALL P-lots from every week (full annual demand)
  - Re-places lots into harvest weeks, respecting CapHard ceiling
  - Sets plan_mode = "push_sub" so ForwardPlanner pushes burst upstream

Step 2 -- Opening inventory injection (inbound MOM ancestors)
  Walk from leaf_in up through its ancestor chain.
  For each ancestor compute the pre-harvest gap and generate synthetic
  opening-inventory lot IDs.  Store in self.opening_inv for caller to
  pass as ForwardPlanner(sc_tree, opening_inv=plugin.opening_inv).

  Gap formula:
    Direct parent of leaf_in:  gap = min(harvest_wks) + leaf_in.lt_wks
    Higher ancestors:           gap = child.lt_wks

Result:
  Tanbo      P[W40]     ~15,500 lots  (harvest batch)
  JA_Niigata I[W01-W40] depletes from ~45,000 to 0  (prior-year carryover)
  JA_Niigata I[W41-W44] spikes to ~57,000            (harvest accumulation)
  JA_Niigata I[W45+]    depletes ~1,153/week          (seasonal draw-down)
"""

from __future__ import annotations
from wom.engine.plugin_base import WOMPlugin
from wom.model.plan_node    import S

P = 3  # PSI bucket index for Production


class HarvestBatchPlugin(WOMPlugin):
    """
    Re-batches leaf_in production JIT -> harvest-week bursts and
    injects opening inventory for inbound MOM nodes (prior-year carryover).

    Usage:
        plugin = HarvestBatchPlugin()
        for pn in sc_tree.products:
            bp.run(pn)
            plugin.on_post_backward(sc_tree, pn, weeks, {})
        copy_demand_to_supply_all(sc_tree)
        fp = ForwardPlanner(sc_tree, opening_inv=plugin.opening_inv)
    """

    name        = "harvest_batch"
    label       = "\u53ce\u7a6b\u671f\u30d0\u30c3\u30c1\u751f\u7523 (Harvest Batch)"
    description = (
        "Capacity-aware backward scheduling: batches annual demand lots "
        "into harvest-week P-buckets; sets push_sub on leaf_in nodes; "
        "injects opening inventory for MOM nodes (prior-year carryover)."
    )

    def __init__(self):
        # {node_id: [lot_id_string, ...]} populated by on_post_backward
        self.opening_inv: dict = {}

    # -----------------------------------------------------------------------
    # Hook
    # -----------------------------------------------------------------------

    def on_post_backward(self, sc_tree, prod_nm: str,
                         weeks: list, config: dict, **kw) -> None:
        n_weeks = len(weeks)

        for node in sc_tree.iter_all_nodes(prod_nm):
            if node.node_type != "leaf_in":
                continue

            # 1a. Identify harvest weeks (cap_hard integer part > 0)
            harvest_wks = [
                w for w in range(n_weeks)
                if int(node.cap_hard(w)) > 0
            ]
            if not harvest_wks:
                continue

            # 1b. Collect all P-lots across the entire horizon
            all_lots = []
            for w in range(n_weeks):
                all_lots.extend(node.psi4demand[w][P])
                node.psi4demand[w][P] = []

            if not all_lots:
                continue

            # 1c. Re-place lots into harvest weeks (greedy, earliest first)
            h_idx      = 0
            cap_remain = int(node.cap_hard(harvest_wks[h_idx]))
            for lot in all_lots:
                while cap_remain == 0:
                    h_idx += 1
                    if h_idx >= len(harvest_wks):
                        break
                    cap_remain = int(node.cap_hard(harvest_wks[h_idx]))
                if h_idx >= len(harvest_wks):
                    break
                node.psi4demand[harvest_wks[h_idx]][P].append(lot)
                cap_remain -= 1

            # 1d. Switch plan_mode to push_sub
            node.plan_mode = "push_sub"

            total_sched = sum(len(node.psi4demand[w][P]) for w in harvest_wks)
            print(
                f"[HarvestBatch] {node.node_id}: "
                f"{len(all_lots)} lots -> {total_sched} scheduled "
                f"across {len(harvest_wks)} harvest weeks "
                f"(shortfall: {len(all_lots) - total_sched})"
            )

            # 2. Compute opening inventory for inbound MOM ancestors
            self._inject_opening_inv(node, harvest_wks)

    # -----------------------------------------------------------------------
    # Opening inventory helper
    # -----------------------------------------------------------------------

    def _inject_opening_inv(self, leaf_in_node, harvest_wks: list) -> None:
        """
        Walk up the inbound chain and compute opening_inv for each ancestor.

        Direct parent of leaf_in:
            No supply before harvest burst arrives.
            gap = min(harvest_wks) + leaf_in.lt_wks
        Higher ancestors (child has opening inv so ships from w=0):
            gap = child.lt_wks
        """
        child           = leaf_in_node
        first_gap_width = min(harvest_wks) + leaf_in_node.lt_wks
        is_direct       = True

        parent = leaf_in_node.parent
        while parent is not None:
            gap = first_gap_width if is_direct else child.lt_wks
            is_direct = False

            n_opening = sum(
                len(parent.psi4demand[w][S]) for w in range(gap)
            )

            if n_opening > 0:
                synthetic = [f"OI_{parent.node_id}_{i}" for i in range(n_opening)]
                existing  = self.opening_inv.get(parent.node_id, [])
                if len(synthetic) > len(existing):
                    self.opening_inv[parent.node_id] = synthetic
                print(
                    f"[HarvestBatch] Opening inv: {parent.node_name} "
                    f"<- {n_opening} lots (gap={gap} wks)"
                )

            child  = parent
            parent = parent.parent
