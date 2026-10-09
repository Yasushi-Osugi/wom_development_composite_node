"""
wom/plugins/selection.py — which plugins a plan uses（RequestLetter_PublicReadiness_Plugins）

* Every plugin name given anywhere (headless ``--plugins``, a model's
  ``recommended_plugins``) must be a built-in plugin: its class name
  (``HolidayCalendarPlugin``) or its short name (``holiday_calendar``). An
  unknown name stops the run with the list of valid names -- it is never
  silently skipped (e.g. the removed ``HarvestBatchPlugin``).
* A model may recommend its plugin set in ``planning_config.csv``::

      key,value
      recommended_plugins,"HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"

  The GUI applies it when the model folder is loaded, and the headless runner
  uses it when ``--plugins`` is not given -- so the GUI default, the headless
  default and the golden (same set) give the same plan. An empty value means
  "no plugins".
"""
from __future__ import annotations

import csv
import os
from typing import List, Optional

CONFIG_FILE = "planning_config.csv"
KEY = "recommended_plugins"


class UnknownPluginError(ValueError):
    """A plugin name is not a built-in plugin."""


def catalog():
    """[(class_name, short_name, class)] of the built-in plugins, in registration order."""
    from wom.plugins import ALL_BUILTIN_PLUGINS
    return [(c.__name__, c().name, c) for c in ALL_BUILTIN_PLUGINS]


def valid_names_text() -> str:
    return ", ".join(f"{cn} ({sn})" for cn, sn, _c in catalog())


def to_class_names(names, source: str) -> List[str]:
    """Class names for the given class or short names; stops on an unknown name."""
    by = {}
    for cn, sn, _c in catalog():
        by[cn] = cn
        by[sn] = cn
    unknown = [n for n in names if n not in by]
    if unknown:
        raise UnknownPluginError(
            f"{source}: 知らないプラグインの名前があります：{', '.join(unknown)}。"
            f"使える名前：{valid_names_text()}")
    out = []
    for n in names:
        if by[n] not in out:
            out.append(by[n])
    return out


def read_recommended_plugins(model_dir: str) -> Optional[List[str]]:
    """The model's recommended plugin class names, or None when the key is absent."""
    path = os.path.join(model_dir or "", CONFIG_FILE)
    if not model_dir or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("key") or "").strip() == KEY:
                names = [x.strip() for x in (row.get("value") or "").split(",") if x.strip()]
                return to_class_names(names, f"{path} {KEY}")
    return None
