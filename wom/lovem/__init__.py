# -*- coding: utf-8 -*-
"""
wom/lovem — LOVEM on WOM: observation (stage A) and viewing (stage B).

Design (source of truth): docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md
Request: requests/RequestLetter_LOVEM_StageAB_EVThailand_to_CodeKun.md
Data dictionary: docs/development/lovem/DATA_DICTIONARY.md

This package only READS planning results. It never changes the plan:
the observer wraps a few planner call boundaries for the duration of one
observed run (read + copy only) and restores them afterwards.
"""

SCHEMA_VERSION = "lovem-a1"
OBSERVER_VERSION = "0.1.0"
