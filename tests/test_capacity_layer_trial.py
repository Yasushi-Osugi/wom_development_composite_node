"""Hand-calculated counterexamples and frozen smartx adapter integration."""
from pathlib import Path
import csv
import pytest

from wom.capacity_layer import Request,Option,Problem,solve_greedy,solve_lp,validate_solution


def test_greedy_loss_is_structural_resource_usage():
    # Earliest A consumes two units for one lot; later B can make two lots.
    p=Problem([Request("A","A","M",0,1),Request("B","B","M",1,2)],
        [Option("a","A",0,(("machine",0,2.),)),Option("b","B",0,(("machine",0,1.),))],
        {("machine",0):2.})
    g,l=solve_greedy(p),solve_lp(p)
    assert g.served==1 and g.unmet["B"]==2
    assert l.served==2 and l.unmet["A"]==1 and l.relaxation_upper_bound==2


@pytest.mark.parametrize("solver",[solve_greedy,solve_lp])
def test_seasonal_capacity_zero_is_zero_and_demand_is_not_lost(solver):
    p=Problem([Request("crop","Rice","M",5,4)],
        [Option(f"p{w}","crop",w,(("field",w,1.),)) for w in range(6)],
        {("field",w):3. if w==3 else 0. for w in range(6)})
    s=solver(p)
    assert s.served==3 and s.unmet=={"crop":1}
    assert [(x.option_key,x.quantity) for x in s.allocations]==[("p3",3)]
    assert s.advance_lot_weeks==6


def test_bom_coefficient_consumes_physical_capacity():
    p=Problem([Request("r","Vehicle","M",2,3)],
        [Option("o","r",1,(("tyres",1,4.),))],{("tyres",1):8.})
    s=solve_lp(p); assert s.served==2 and s.unmet["r"]==1
    assert validate_solution(p,s)["resource_load"][("tyres",1)]==8.


def test_fractional_relaxation_is_not_called_integer_optimum():
    p=Problem([Request("r","A","M",0,3)],[Option("o","r",0,(("m",0,2.),))],{("m",0):3.})
    s=solve_lp(p)
    assert s.relaxation_upper_bound==1.5 and s.served==1 and s.unmet["r"]==2
    assert s.fractional_cells==1 and s.fractional_remainder==.5


def test_missing_capacity_is_error_explicit_none_is_allowed():
    r=Request("r","P","M",1,2);o=Option("o","r",1,(("m",1,1.),))
    with pytest.raises(ValueError,match="Missing capacity"): solve_greedy(Problem([r],[o],{}))
    assert solve_greedy(Problem([r],[o],{("m",1):None})).served==2


def test_late_service_option_cannot_hide_original_due_date():
    with pytest.raises(ValueError,match="on-time/prebuild"):
        solve_greedy(Problem([Request("r","P","M",1,1)],[Option("o","r",2,())],{}))


def test_resource_after_original_due_cannot_be_labelled_on_time():
    with pytest.raises(ValueError,match="by the original due week"):
        solve_lp(Problem([Request("r","P","M",3,1)],
            [Option("o","r",2,(("harvest",4,1.),))],{("harvest",4):1.}))


def test_shared_work_center_is_not_sum_of_product_profiles():
    # One machine week: either 100 A, 200 B, or a mix, not both maxima.
    p=Problem([Request("a","A","M",0,100),Request("b","B","M",0,200)],
        [Option("oa","a",0,(("shared",0,.01),)),Option("ob","b",0,(("shared",0,.005),))],
        {("shared",0):1.})
    assert solve_greedy(p).served==100
    s=solve_lp(p);assert s.served==200 and s.unmet["a"]==100


def test_serial_adapter_preserves_market_id_and_independent_forward_checks(tmp_path):
    """A planned one-week advance creates market I rather than an early sale."""
    import pandas as pd
    from wom.model.sc_tree import SCTree
    from wom.model.plan_node import PlanNode,S,P,I
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    from wom.capacity_layer.smartx_trial import SmartxAdapter
    weeks=[f"2027-W{w:02d}" for w in range(1,11)]
    rows=[{"node_name":"SP","parent_node":"","product_name":"A","node_type":"supply_point","side":"outbound","lt_wks":0,"region":""},
        {"node_name":"Market","parent_node":"SP","product_name":"A","node_type":"leaf_out","side":"outbound","lt_wks":1,"region":"JP"},
        {"node_name":"Factory","parent_node":"","product_name":"A","node_type":"mom","side":"inbound","lt_wks":1,"region":""},
        {"node_name":"Source","parent_node":"Factory","product_name":"A","node_type":"leaf_in","side":"inbound","lt_wks":1,"region":""}]
    tree=build_sc_tree_from_master(pd.DataFrame(rows),weeks)
    nodes=[]; states=[]
    for n in tree.iter_all_nodes("A"):
        nodes.append({"product":"A","node_id":n.node_id,"node_name":n.node_name,"node_type":n.node_type,
            "side":n.side,"plan_mode":"pull","parent_id":n.parent.node_id if n.parent else "",
            "lt_wks":n.lt_wks,"transit_lt_wks":n.transit_lt_wks,"ss_wks":0,"bom_qty":1})
        states.extend({"node_id":n.node_id,"week":w,"week_index":i,"processing_limit":"1",
            "is_open":"True"} for i,w in enumerate(weeks))
    for name,data in [("nodes.csv",nodes),("node_week.csv",states)]:
        with open(tmp_path/name,"w",newline="") as f:
            wr=csv.DictWriter(f,list(data[0]));wr.writeheader();wr.writerows(data)
    a=SmartxAdapter(tmp_path,missing_capacity_policy="explicit_engine_unbounded",push_leads={})
    market=next(n for n in tree.iter_all_nodes("A") if n.node_type=="leaf_out")
    lot="A:JP:2027-W07:00001";market.psi4demand[6][S]=[lot];market.psi4demand[6][P]=[lot]
    assignments=[{"product":"A","market":"Market","status":"assigned","plan_index":5,"original_lot_id":lot}]
    a.apply_positions(tree,"A",assignments)
    assert market.psi4demand[6][S]==[lot] and market.psi4demand[5][S]==[]
    copy_demand_to_supply(tree,"A");r=ForwardPlanner(tree,lot_flow_mode="identity").run("A")
    assert market.psi4supply[5][I]==[lot] and market._actual_ship[5]==[]
    assert market._actual_ship[6]==[lot] and r.cap_hard_deferred_lots==0
