"""
tests/test_step10_hooks.py
───────────────────────────
Unit tests for HookBus + WOM plugins (Step 10).
"""

import pytest
from wom.engine.hook_bus import (
    HookBus,
    HOOK_PRE_PLAN, HOOK_POST_BACKWARD,
    HOOK_POST_COPY, HOOK_POST_FORWARD, HOOK_POST_PLAN,
    ALL_HOOKS,
)
from wom.engine.plugin_base import WOMPlugin


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_bus() -> HookBus:
    return HookBus()


# ── HookBus basics ────────────────────────────────────────────────────────────

class TestHookBus:
    def test_fire_calls_listener(self):
        bus = _make_bus()
        calls = []
        bus.register(HOOK_PRE_PLAN, lambda **kw: calls.append(kw))
        bus.fire(HOOK_PRE_PLAN, sc_tree=None, weeks=[], config={})
        assert len(calls) == 1
        assert calls[0]["sc_tree"] is None

    def test_multiple_listeners_same_hook(self):
        bus = _make_bus()
        order = []
        bus.register(HOOK_POST_BACKWARD, lambda **kw: order.append("A"))
        bus.register(HOOK_POST_BACKWARD, lambda **kw: order.append("B"))
        bus.fire(HOOK_POST_BACKWARD, sc_tree=None, prod_nm="X", weeks=[], config={})
        assert order == ["A", "B"]

    def test_unregister(self):
        bus = _make_bus()
        calls = []
        fn = lambda **kw: calls.append(1)
        bus.register(HOOK_POST_COPY, fn)
        bus.unregister(HOOK_POST_COPY, fn)
        bus.fire(HOOK_POST_COPY, sc_tree=None, prod_nm="X", weeks=[], config={})
        assert calls == []

    def test_clear(self):
        bus = _make_bus()
        calls = []
        bus.register(HOOK_POST_FORWARD, lambda **kw: calls.append(1))
        bus.register(HOOK_POST_PLAN,    lambda **kw: calls.append(2))
        bus.clear()
        for h in ALL_HOOKS:
            bus.fire(h, sc_tree=None, weeks=[], config={}, prod_nm=None)
        assert calls == []

    def test_invalid_hook_raises(self):
        bus = _make_bus()
        with pytest.raises(ValueError):
            bus.register("no_such_hook", lambda **kw: None)

    def test_listener_exception_is_non_fatal(self):
        """A crashing listener should not prevent other listeners from running."""
        bus = _make_bus()
        calls = []
        bus.register(HOOK_POST_PLAN, lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
        bus.register(HOOK_POST_PLAN, lambda **kw: calls.append("ok"))
        bus.fire(HOOK_POST_PLAN, sc_tree=None, weeks=[], config={})
        assert "ok" in calls

    def test_listener_count(self):
        bus = _make_bus()
        bus.register(HOOK_PRE_PLAN, lambda **kw: None)
        bus.register(HOOK_PRE_PLAN, lambda **kw: None)
        assert bus.listener_count(HOOK_PRE_PLAN) == 2
        assert bus.listener_count(HOOK_POST_PLAN) == 0


# ── WOMPlugin base ────────────────────────────────────────────────────────────

class TestWOMPlugin:
    def test_register_adds_listeners(self):
        bus = _make_bus()
        plugin = WOMPlugin()
        plugin.register(bus)
        for h in ALL_HOOKS:
            assert bus.listener_count(h) == 1

    def test_default_callbacks_are_noop(self):
        """Calling default hooks must not raise."""
        plugin = WOMPlugin()
        plugin.on_pre_plan(sc_tree=None, weeks=[], config={})
        plugin.on_post_backward(sc_tree=None, prod_nm="X", weeks=[], config={})
        plugin.on_post_copy(sc_tree=None, prod_nm="X", weeks=[], config={})
        plugin.on_post_forward(sc_tree=None, prod_nm="X", weeks=[], config={})
        plugin.on_post_plan(sc_tree=None, weeks=[], config={})


# ── DemandSmoothingPlugin ─────────────────────────────────────────────────────

class TestDemandSmoothingPlugin:
    def _make_sc_tree_with_demand(self, demand_per_week: list):
        """
        Build a minimal sc_tree mock where get_in_root() returns a node
        whose psi4demand[w][S] has the specified lot counts.
        """
        from wom.model.plan_node import (
            PlanNode, S,
            NODE_TYPE_MOM,
        )

        n = len(demand_per_week)
        weeks = [f"2024-W{w:02d}" for w in range(n)]
        node = PlanNode(
            node_id="MOM:test",
            node_name="Mother Plant",
            product="test",
            side="inbound",
            node_type=NODE_TYPE_MOM,
            tier=0,
            lt_wks=2,
            plan_mode="pull",
            is_decoupling=True,
        )
        node.init_psi(weeks)
        for w, qty in enumerate(demand_per_week):
            node.psi4demand[w][S] = [f"L{w}_{i}" for i in range(qty)]

        class FakeSCTree:
            products = ["test"]
            def get_in_root(self, prod_nm):
                return node

        return FakeSCTree(), node

    def test_smoothing_reduces_spike(self):
        from wom.plugins.demand_smoothing import DemandSmoothingPlugin
        from wom.model.plan_node import S

        # Week 2 is a spike (100), weeks 0,1,3,4 are 10
        demand = [10, 10, 100, 10, 10]
        sc_tree, node = self._make_sc_tree_with_demand(demand)

        plugin = DemandSmoothingPlugin()
        plugin.on_post_backward(
            sc_tree=sc_tree, prod_nm="test",
            weeks=[f"2024-W{i:02d}" for i in range(len(demand))],
            config={})

        # After smoothing, week 2 lot count should be < 100 (spike reduced)
        smoothed_w2 = len(node.psi4demand[2][S])
        assert smoothed_w2 < 100, f"Expected smoothed < 100, got {smoothed_w2}"

    def test_smoothing_preserves_total(self):
        from wom.plugins.demand_smoothing import DemandSmoothingPlugin
        from wom.model.plan_node import S

        demand = [5, 20, 3, 15, 7]
        total_before = sum(demand)
        sc_tree, node = self._make_sc_tree_with_demand(demand)

        plugin = DemandSmoothingPlugin()
        plugin.on_post_backward(
            sc_tree=sc_tree, prod_nm="test",
            weeks=[f"2024-W{w:02d}" for w in range(len(demand))],
            config={})

        total_after = sum(len(node.psi4demand[w][S]) for w in range(len(demand)))
        # Total should be ≤ original (rounding may lose at most 1 per week)
        assert abs(total_after - total_before) <= len(demand)


# ── CapacityOverridePlugin ────────────────────────────────────────────────────

class TestCapacityOverridePlugin:
    def test_no_file_no_crash(self, tmp_path):
        from wom.plugins.capacity_override import CapacityOverridePlugin

        plugin = CapacityOverridePlugin()
        # Should silently skip when cap_override.csv doesn't exist
        plugin.on_pre_plan(
            sc_tree=None,
            weeks=["2024-W01"],
            config={"cap_path": str(tmp_path / "capacity_plan.csv")})

    def test_applies_override(self, tmp_path):
        import pandas as pd
        from wom.plugins.capacity_override import CapacityOverridePlugin
        from wom.model.plan_node import PlanNode

        # Write cap_override.csv
        override_csv = tmp_path / "cap_override.csv"
        pd.DataFrame([
            {"sku_id": "SKU-A", "week": "2024-W01", "cap_hard": 999.0}
        ]).to_csv(override_csv, index=False)

        node = PlanNode(
            node_id="MOM:SKU-A",
            node_name="Mother Plant",
            product="SKU-A",
            side="inbound",
            node_type="mom",
            tier=0,
            lt_wks=2,
            plan_mode="pull",
            is_decoupling=True,
        )
        node.init_psi(["2024-W01", "2024-W02"])

        class FakeSCTree:
            products = ["SKU-A"]
            def get_in_root(self, prod_nm):
                return node

        plugin = CapacityOverridePlugin()
        plugin.on_pre_plan(
            sc_tree=FakeSCTree(),
            weeks=["2024-W01", "2024-W02"],
            config={"cap_path": str(tmp_path / "capacity_plan.csv")})

        assert node.cap_hard(0) == 999.0
