# Codex Request: Explicit Holiday Closure Engine

- **Request file**: `docs/codex_requests/holiday_explicit_closure_engine_request.md`
- **Target repository**: `Yasushi-Osugi/wom_v1r0m0`
- **Target branch**: `wom-v1r2m0`
- **Base commit at request creation**: `2169bf6`
- **Request status**: Ready for implementation
- **Implementation order**: Run this request before `planning_warmup_reporting_horizon_request.md`
- **Owner policy**: Do not commit, push, merge, or create a release tag unless the repository owner explicitly instructs you to do so.

---

## 1. Request Summary

Implement formal `explicit_closure` semantics for WOM Holiday Calendar processing.

The current temporary scenario workaround uses:

```csv
effect=supply_closure,value=0.1
```

because the current capacity logic treats:

```text
cap_hard <= 0
```

as:

```text
capacity not configured
= unconstrained
```

The workaround has confirmed that the holiday planning path can visibly move production before the closed week. It must not become the production specification.

The formal implementation must distinguish:

```text
cap_hard <= 0
    unset / unconstrained capacity

explicit_closure
    explicitly closed supply week
    effective capacity = 0

cap_hard > 0
    finite weekly capacity
```

A `supply_closure` must be recognized from its `effect`, independently of the numeric `value`.

---

## 2. Read Before Coding

Read and follow these files as sources of truth:

```text
AGENTS.md
README.md
docs/development/README.md
docs/architecture/README.md
docs/architecture/planning_engine.md
docs/design/README.md
docs/design/holiday_calendar_push_lead_time_and_planning_horizon.md
docs/design/holiday_calendar_and_capacity_semantics.md
docs/design/scenario_modeling_principles.md
data/sample/soysauce-us-2027/README.md
```

Inspect the current implementation, especially:

```text
wom/engine/holiday_calendar_plugin.py
wom/engine/backward_planner.py
wom/engine/forward_planner.py
wom/gui/app.py
wom/model/plan_node.py
tests/test_step7_capacity.py
tests/test_step7b_mom_constrained.py
tests/test_step10_hooks.py
data/sample/soysauce-us-2027/holiday_calendar.csv
data/sample/soysauce-us-2027/capacity_plan.csv
data/sample/soysauce-us-2027/sc_tree_master.csv
```

Search all constructor call sites for:

```python
BackwardPlanner(...)
ForwardPlanner(...)
```

before changing public signatures.

---

## 3. Confirmed Current Behavior

The current code already performs part of the required work.

### 3.1 HolidayCalendarPlugin

`HolidayCalendarPlugin.on_pre_plan()`:

1. reads `holiday_calendar.csv`;
2. calls `_apply_supply_closure()` for `effect == "supply_closure"`;
3. currently writes the CSV `value` into `node.cap_hard`;
4. builds:

```python
config["explicit_closures"] = {
    node_name: {week_index, ...}
}
```

The current implementation therefore mixes two different meanings:

```text
holiday event state
capacity numeric value
```

### 3.2 BackwardPlanner

`BackwardPlanner` already reads:

```python
config["explicit_closures"]
```

and `_offset_week()` skips closed weeks during LT offset calculation.

However, `_apply_mom_cap_backward()` currently does only:

```python
cap_w = node.cap_hard(w)

if cap_w <= 0.0:
    continue
```

It does not treat an explicit MOM closure as effective capacity zero.

### 3.3 Holiday post-backward processing

`HolidayCalendarPlugin.on_post_backward()` currently moves P lots only for:

```python
NODE_TYPE_LEAF_IN
```

The soy sauce closure node is:

```text
Bottling_Noda
node_type = mom
```

Therefore this post-hook does not formally solve the MOM closure.

### 3.4 ForwardPlanner

`ForwardPlanner` currently has no `explicit_closures` constructor input.

Its normal CapHard sealing condition is based on:

```python
cap_hard > 0
```

and push-mode nodes may skip ordinary CapHard sealing.

A formal explicit closure must take precedence over both conditions.

---

## 4. Required Design Decisions

Implement the following decisions exactly.

### Decision A: Keep zero-capacity backward compatibility

Do not globally redefine:

```text
cap_hard = 0
```

as a factory closure in this request.

For a week that is not explicitly closed:

```text
cap_hard <= 0
    remains unset / unconstrained
```

This protects existing WOM scenarios and tests.

### Decision B: A closure is event state, not a capacity sentinel

For:

```csv
effect=supply_closure
```

the week is closed regardless of whether the CSV `value` is:

```text
0
0.1
1500
blank
```

The numeric value must not determine whether a complete closure exists.

### Decision C: MOM closure is resolved before inbound propagation

For a closed MOM week:

```text
closure recognition
→ MOM demand/P capacity handling
→ carry production request to an earlier week
→ propagate the adjusted plan to upstream children
```

Do not move a MOM production plan only after upstream propagation.

### Decision D: Forward planning is a safety check

Backward Planning should produce the correct pre-build plan.

Forward Planning must independently prevent actual production/receipt from passing through an explicitly closed week if an inconsistent P bucket still reaches that week.

### Decision E: Preserve Lot ID identity

No closure handling may regenerate anonymous replacement lots.

The same Demand Anchored Lot IDs must remain traceable across:

```text
original requested week
pre-build week
upstream propagation
forward fulfillment
inventory
CO
```

---

## 5. Required Code Changes

### 5.1 HolidayCalendarPlugin

Update:

```text
wom/engine/holiday_calendar_plugin.py
```

Required behavior:

1. Continue loading all existing holiday effects.
2. For `effect == "supply_closure"`:
   - register the week indices in `config["explicit_closures"]`;
   - do not rely on `value` to create the closure;
   - do not overwrite normal finite capacity as the mechanism for representing full closure.
3. Keep `demand_multiplier` behavior unchanged.
4. Keep leaf-in post-backward handling unless tests demonstrate that a safer shared engine path fully replaces it.
5. Avoid double-moving the same lots.
6. Improve the log so that it reports event semantics rather than a misleading numeric capacity.

Recommended log form:

```text
[HolidayCalendar] Explicit supply closure:
Bottling_Noda 2027-W18..2027-W18
```

Do not log:

```text
cap_hard=1500
```

as the defining closure fact.

### 5.2 BackwardPlanner

Update:

```text
wom/engine/backward_planner.py
```

In `_apply_mom_cap_backward()`:

1. obtain the node closure set from `self._explicit_closures`;
2. when `w` is explicitly closed, set the effective capacity for that planning decision to zero;
3. otherwise preserve current capacity behavior;
4. process closure weeks in the existing backward loop so cascading carry-back remains deterministic;
5. update `S` and `P` consistently before `_in_propagate()`;
6. preserve existing `CO` and `past_due_lots` conventions unless a focused test proves a correction is necessary.

Conceptual rule:

```python
closure_set = self._explicit_closures.get(node.node_name, set())

for w in range(n_weeks - 1, -1, -1):

    if w in closure_set:
        cap_int = 0
    else:
        cap_w = node.cap_hard(w)

        if cap_w <= 0.0:
            continue  # unset = unconstrained

        cap_int = int(cap_w)

    # use existing MOM carry-back flow
```

Important:

- If the preceding week is also closed, the existing backward loop should continue carrying the lots toward the nearest earlier open week.
- Week 0 closure overflow must remain visible as past due or another existing explicit shortfall record; do not silently drop it.
- Do not change `push_lead_time_weeks` in this request.

### 5.3 ForwardPlanner

Update:

```text
wom/engine/forward_planner.py
```

Add a backward-compatible optional constructor argument:

```python
explicit_closures: Optional[Dict[str, set]] = None
```

Store it as an empty mapping when omitted.

In `_process_node()`:

1. determine whether the current node/week is explicitly closed;
2. explicit closure must take precedence over:
   - `cap_hard <= 0`;
   - normal CapHard logic;
   - the ordinary push-mode exemption from sealing;
3. a closed node/week must not produce or pass actual P as successful production/receipt;
4. preserve Lot IDs;
5. use existing result/CO/capacity-event conventions where possible;
6. do not silently delete lots.

The implementation may use a small helper such as:

```python
def _effective_hard_capacity(node, week) -> Optional[int]:
    ...
```

only if it makes the semantics clearer and remains local to the planning engine.

### 5.4 Planner orchestration

Update all active GUI/CLI planning call sites so that the same closure mapping is passed to `ForwardPlanner`.

The GUI planning sequence must remain:

```text
HOOK_PRE_PLAN
BackwardPlanner
HOOK_POST_BACKWARD
copy_demand_to_supply
HOOK_POST_COPY
PushProductionPlanner
ForwardPlanner
HOOK_POST_FORWARD
HOOK_POST_PLAN
```

Do not reorder hooks in this request.

### 5.5 Soy sauce scenario data

After the formal engine behavior is implemented, update:

```text
data/sample/soysauce-us-2027/holiday_calendar.csv
```

to use readable formal values:

```csv
holiday_id,holiday_name,start_week,end_week,node_name,effect,value
GW_2027,Japan Golden Week factory closure 2027,2027-W18,2027-W18,Bottling_Noda,supply_closure,0
GW_2028,Japan Golden Week factory closure 2028,2028-W18,2028-W18,Bottling_Noda,supply_closure,0
```

The engine must still interpret closure from `effect`, not from `value`.

Update the scenario README only if execution instructions or known limitations change.

---

## 6. Test Requirements

Add focused automated tests. Prefer extending the closest existing test files unless a dedicated file makes the intent clearer.

A dedicated file name is acceptable:

```text
tests/test_holiday_explicit_closure.py
```

### Test 1: Plugin registers closure independently of value

Use at least two values:

```text
value=0
value=1500
```

Expected for both:

```python
config["explicit_closures"]["Bottling_Noda"] == {closed_week_index}
```

Do not require numeric capacity mutation to prove closure.

### Test 2: Zero without closure remains unconstrained

Given:

```text
cap_hard=0
no explicit closure
```

Expected:

- current unlimited behavior remains;
- no hard-cap sealing is introduced;
- legacy capacity tests remain green.

### Test 3: MOM explicit closure produces zero P in the closed week

Create a minimal MOM scenario with demand in a closed week.

Expected:

```text
closed week MOM demand-side P = 0
closed week MOM demand-side S = 0 after constrained allocation
same Lot IDs moved to earlier week S/P
```

Use assertions on identity, not only quantity.

### Test 4: Consecutive closure weeks carry to the nearest earlier open week

Example:

```text
W05 closed
W06 closed
demand at W06
```

Expected:

- no production at W05/W06;
- lots are carried toward W04 if capacity allows;
- no duplicate Lot IDs.

### Test 5: MOM adjustment precedes upstream propagation

For:

```text
Materials_JP → Brewing_Noda → Bottling_Noda
```

Expected:

- closed Bottling_Noda week has no P;
- Brewing_Noda and Materials_JP receive the adjusted earlier timing;
- upstream child timing is not based on the original closed-week plan.

### Test 6: ForwardPlanner blocks inconsistent closed-week P

Seed P into an explicitly closed MOM week after copy.

Expected:

- no actual shipment from that closed node/week;
- no bridge shipment sourced from that closed production;
- Lot IDs remain visible in an existing deferred/CO/result record;
- no silent deletion.

### Test 7: No-closure regression

Run equivalent planning with an empty closure map.

Expected:

- output is unchanged from the current behavior;
- existing capacity and push/pull tests remain green.

### Test 8: Existing leaf-in closure behavior

Verify that current leaf-in closure support does not regress and does not double-move lots after the new MOM logic.

---

## 7. Manual Scenario Verification

Run the soy sauce model:

```text
python -m main
Load Model Folder:
data/sample/soysauce-us-2027
Run Planning
```

Verify both:

```text
2027-W18
2028-W18
```

Expected at `Bottling_Noda`:

```text
P = 0 in the closed week
P and/or I increases before closure
S remains supportable when buffer inventory is sufficient
```

Also inspect:

```text
Brewing_Noda P
Materials_JP P
FG_WH_Noda I
DC_US_SF I / CO
DC_US_NY I / CO
Rest_US_West S
Rest_US_East S
```

A smooth final-market S is not a failure if inventory absorbs the holiday.

Capture the relevant log lines and summarize the observed PSI pattern.

---

## 8. Required Validation Commands

At minimum run:

```bat
python -m pytest tests/test_step7_capacity.py -q
python -m pytest tests/test_step7b_mom_constrained.py -q
python -m pytest tests/test_step10_hooks.py -q
python -m pytest tests/test_holiday_explicit_closure.py -q
```

Then run the full suite:

```bat
python -m pytest -q
```

If the full suite has pre-existing failures, report:

```text
pre-existing failure
new failure
not run / blocked
```

separately.

Do not claim success without showing the actual test summary.

---

## 9. Non-goals

Do not implement the following in this request:

```text
capacity enum redesign
None/Unlimited/Zero/Finite model-wide migration
partial_capacity or capacity_override CSV effect
Planning Warm-up Period
Reporting Horizon
Push Config redesign
push_lead_time_weeks change
PPC accounting redesign
GUI visual redesign
```

Do not change:

```text
push_lead_time_weeks=7
```

for the soy sauce model.

---

## 10. Definition of Done

This request is complete only when all of the following are true:

- [ ] `supply_closure` is interpreted as explicit event state.
- [ ] Closure does not depend on the numeric CSV value.
- [ ] `cap_hard=0` without closure remains unconstrained.
- [ ] A closed MOM week has zero planned/actual production.
- [ ] Closed-week MOM lots move earlier before inbound propagation.
- [ ] Upstream timing follows the adjusted MOM plan.
- [ ] ForwardPlanner prevents closed-week actual flow.
- [ ] Lot IDs are preserved without duplication or silent loss.
- [ ] Existing no-closure scenarios remain compatible.
- [ ] Soy sauce holiday values are restored from `0.1` workaround to formal `0`.
- [ ] Focused tests pass.
- [ ] Full test results are reported.
- [ ] Manual soy sauce PSI verification is summarized.

---

## 11. Required Completion Report

Return a concise report containing:

```text
1. Files changed
2. Design decisions implemented
3. Exact behavior before and after
4. Tests added
5. Test commands and results
6. Soy sauce manual verification
7. Remaining limitations
8. git diff --stat
9. Recommended commit message
```

Recommended commit message:

```text
Implement explicit holiday closure semantics
```

Suggested body:

```text
Treat supply_closure as explicit event state, enforce MOM closures in backward
and forward planning, preserve zero-capacity unlimited semantics, add focused
tests, and restore the soy sauce holiday calendar to formal zero values.
```
