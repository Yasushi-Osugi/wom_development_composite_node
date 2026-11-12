# -*- coding: utf-8 -*-
"""
費用の分け方（RequestLetter_StageD_Phase1 §1-4、設計 D-3）。**この表は、ここ 1 か所だけに置く。**

| 費用                                         | 扱い                                         |
|---|---|
| 外部からの仕入、法人間の仕入                 | 在庫原価（受け手の法人）                     |
| 運賃（グループの中の区間、グループに入る区間）| 在庫原価。受け手の法人が負担                  |
| 運賃（グループから外部へ販売する区間）       | 売り手の法人の、その週の販売費               |
| 運賃（法人間の区間、取引条件で売り手負担・価格に含む〔vc_trade_terms.csv の seller・1、CIF 型〕）| 売り手の、法人間売上に対応する原価。受け手の法人の原価に足さない。グループの原価には足す |
| 関税・保険（国境の区間）                     | 在庫原価（輸入する受け手の法人）             |
| conversion_cost（加工・取扱・通関）          | 在庫原価                                     |
| warehouse_cost（保管）、sga_cost             | その週の費用                                 |
| 在庫の保有費用（D-5）                        | その週の費用。独立した項目。率が空欄なら未設定 |
| 直販の売上比率の費用（vc_sales_cost_rule.csv）| 売り手の、販売の週の販売費（費目ごとに 1 行）|
| 外部の代理店への卸売の売上比率の費用（vc_sales_cost_rule.csv の external の leaf）| 売り手の、卸売の週の販売費 |
| 消費者向けの配送・梱包（delivery_packing_cost）| 運賃と同じ（グループから外部へ＝売り手の販売費）|

取引条件による運賃の負担は、vc_trade_terms.csv で宣言した法人間の区間だけ分ける（G5。ledger._cif_freight）。
表せるのは seller・1（CIF 型）と buyer・0（今の動き）だけ。表に無い区間は上の表のとおり（受け手が負担）。
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

# delivery_packing_cost: the consumer delivery and packing of a direct sale (edge "<leaf>->CONSUMER").
# Same treatment as freight: group -> external is the seller's selling expense (G1, C5).
EDGE_COST_FAMILY = {"logistics_cost": "freight", "insurance_cost": "insurance",
                    "delivery_packing_cost": "freight"}

# Sales-based costs of a direct sale (vc_sales_cost_rule.csv, G1 C1). Every line is the seller's
# selling expense of the sale week (kind=expense, scope=selling), whatever its PPC cost type.
# cost_item -> label. An item not in this table stops the load (no silent default).
# distributor_mdf (G2 D1): the only item of an external distributor leaf; booked at the wholesale
# week as the seller's selling expense (rate x the wholesale revenue).
SALES_COST_ITEMS = {
    "hq_sga_allocation": "販社販管費",
    "payment_platform_fee": "決済・EC 基盤手数料",
    "digital_ad": "デジタル広告費",
    "store_operating": "店舗運営費",
    "distributor_mdf": "代理店向け販促協賛費（MDF）",
}
# the items of an external distributor leaf (G2 D2); every other item is for direct-sales leaves
EXTERNAL_SALES_COST_ITEMS = ("distributor_mdf",)
# the PPC cost types the items are summed into (ppc_node_cost_rule.csv)
SALES_COST_PPC_TYPES = ("sga_cost", "marketing_cost")


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
