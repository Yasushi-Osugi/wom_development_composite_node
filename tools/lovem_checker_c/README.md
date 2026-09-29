# LOVEM Stage C independent checker

Scope: ev-thailand-2026, 3481fc5 (code/data identical to a43163f), legacy and identity.
Python 3.10+ standard library only. No WOM, LOVEM, viewer or Code-kun checker imports.
All inputs are read-only. Outputs must be outside input run directories. No planning execution.

## Reproduction

Extract both original ZIPs below a directory INPUTS:
`INPUTS/legacy/handoff_ev-thailand-2026_C_legacy/run/` and the corresponding identity path.
Use a clean checkout containing the original handoff ZIPs and the matching model CSVs.
From the repository root (replace INPUTS and REPO with actual paths):

```text
python tools/lovem_checker_c/verify_inputs.py --repo REPO --inputs INPUTS --out docs/development/lovem/stageC/input_verification.json
python tools/lovem_checker_c/fixtures.py
python tools/lovem_checker_c/check.py --run INPUTS/legacy/handoff_ev-thailand-2026_C_legacy/run --out docs/development/lovem/stageC/run_C_legacy
python tools/lovem_checker_c/check.py --run INPUTS/identity/handoff_ev-thailand-2026_C_identity/run --out docs/development/lovem/stageC/run_C_identity
python tools/lovem_checker_c/finalize_checks.py --base docs/development/lovem/stageC
python tools/lovem_checker_c/compare.py --base docs/development/lovem/stageC --inputs INPUTS --model-dir REPO/data/sample/ev-thailand-2026
```

`finalize_checks.py` is REQUIRED: local Q05 availability is insufficient if its P has no parent shipment. It combines independently determined Q04 provenance with same-node/week shipment histories. It is idempotent. This is evidence composition, not an exception allowing legacy failures.

`compare.py` checks all 21 model hashes, accepting exact raw bytes OR exact Windows CRLF rendering of Git LF bytes; other differences abort. The extra CSV is needed because nodes.csv omits ss_wks. LT+SS calculations are explicitly derived, not recorded events. No cross-node causal root is inferred merely from the first timestamp difference.

## Rules and limitations

- Fixtures F1–F8 are small component fixtures serialized as lovem-a1 interval/event records, not executable WOM models or full observer run bundles. They test classification, multiset differences, CO convention, interval reading and capacity-deferral timing. Do not claim an independent full-WOM simulation test.
- The initial eight fixtures passed before real-run checker results. Subsequent reporting combines Q04 and Q05 evidence without changing the no-phantom-stock rule of F6.
- Role is `-`, quantity=1 and node-level request IDs are unique in these inputs. Do not generalize chronological occurrence matching to anonymous stock, repeated requests or BOM roles. The actual run reports any repeated-ID ambiguity.
- CO[w] is incoming backlog. Closing CO = CO[w]+S[w] minus matching actual shipments; CO[w+1] is compared to this. At final week, closing is derived because no next-week slot exists.
- Node S requirement weeks come from final demand S; supply S is used for weekly CO recurrence and SE2. push_sub is excluded from requirement/early tests, not physical checks.
- Physical opening inventory is zero for this model as checked by weekly balance; an independent opening-inventory event is not supplied.
- Q04 routes are derived from node topology, anchor market route, transit LT and MOM-to-SP bridge. Observed REL is audited against that independently computed route, not treated as the route authority.
- Q03 local physical equality and Q05 local availability can both hold with copied P. Full Q05 must include Q04 evidence (see finalizer).
- Demand conservation Q02 is a partition of market requests, not proof of physical sourcing.
- Q12 compares all supplied OFF and ON fingerprints, not just the `identical` boolean; no independent ON/OFF planning rerun.
- Missing demand-fulfilment links are reconstructed by unique node/ID and explicitly remain derived. Weekly equality cannot establish intra-week event order.
- Read report and RAW_DATA_INDEX.csv before adding files to git. CSV files larger than 1,000,000 bytes are in the separate raw-data ZIP, not the repository payload.
