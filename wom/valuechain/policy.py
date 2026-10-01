# -*- coding: utf-8 -*-
"""
費用の分け方（RequestLetter_StageD_Phase1 §1-4、設計 D-3）。**この表は、ここ 1 か所だけに置く。**

| 費用                                         | 扱い                                         |
|---|---|
| 外部からの仕入、法人間の仕入                 | 在庫原価（受け手の法人）                     |
| 運賃（グループの中の区間、グループに入る区間）| 在庫原価。受け手の法人が負担                  |
| 運賃（グループから外部へ販売する区間）       | 売り手の法人の、その週の販売費               |
| 関税・保険（国境の区間）                     | 在庫原価（輸入する受け手の法人）             |
| conversion_cost（加工・取扱・通関）          | 在庫原価                                     |
| warehouse_cost（保管）、sga_cost             | その週の費用                                 |
| 在庫の保有費用（D-5）                        | その週の費用。独立した項目。率が空欄なら未設定 |

取引条件（FOB・CIF など）による運賃の負担の分け方は、第 1 回では扱わない。
"""
from __future__ import annotations

# results of classify_*
INVENTORY = "inventory_cost"        # added to the lot's inventory cost (receiver / owner)
SELLING = "period_selling"          # seller's expense of the week
PERIOD = "period_expense"           # owner's expense of the week
HOLDING = "holding_cost"            # separate item (D-5)

# edge classes
EDGE_INTO_OR_IN_GROUP = "into_or_in_group"   # receiver is a group entity
EDGE_GROUP_TO_EXTERNAL = "group_to_external"  # seller group, receiver outside the group
EDGE_OUTSIDE_GROUP = "outside_group"          # neither side is a group entity

# The table (the only place). Keys: (cost family, edge class or "node").
COST_POLICY = {
    ("purchase", EDGE_INTO_OR_IN_GROUP): INVENTORY,       # external / intercompany purchase
    ("freight", EDGE_INTO_OR_IN_GROUP): INVENTORY,        # borne by the receiver
    ("freight", EDGE_GROUP_TO_EXTERNAL): SELLING,         # borne by the seller
    ("tariff", EDGE_INTO_OR_IN_GROUP): INVENTORY,         # importer = receiver
    ("tariff", EDGE_GROUP_TO_EXTERNAL): SELLING,          # (no such row in the subjects)
    ("insurance", EDGE_INTO_OR_IN_GROUP): INVENTORY,
    ("insurance", EDGE_GROUP_TO_EXTERNAL): SELLING,
    ("conversion_cost", "node"): INVENTORY,
    ("logistics_cost", "node"): INVENTORY,                # node-side freight (should not exist; see masters)
    ("warehouse_cost", "node"): PERIOD,
    ("sga_cost", "node"): PERIOD,
    ("marketing_cost", "node"): SELLING,
    ("holding", "node"): HOLDING,
}

EDGE_COST_FAMILY = {"logistics_cost": "freight", "insurance_cost": "insurance"}


def classify_edge_cost(family: str, edge_class: str) -> str:
    """'freight' / 'insurance' / 'tariff' / 'purchase' on an edge class. Costs on an
    edge between two outside parties are not the group's (None)."""
    if edge_class == EDGE_OUTSIDE_GROUP:
        return None
    return COST_POLICY[(family, edge_class)]


def classify_node_cost(cost_type: str) -> str:
    try:
        return COST_POLICY[(cost_type, "node")]
    except KeyError:
        raise ValueError(f"cost_type {cost_type!r} has no rule in wom/valuechain/policy.py "
                         f"COST_POLICY (add it there; no silent default)")


def policy_table_rows():
    """The table as rows, for the report / the run folder."""
    labels = {INVENTORY: "在庫原価", SELLING: "売り手のその週の販売費",
              PERIOD: "その週の費用", HOLDING: "その週の費用（独立した項目）"}
    return [{"cost": k[0], "where": k[1], "treatment": v, "treatment_ja": labels[v]}
            for k, v in COST_POLICY.items()]
