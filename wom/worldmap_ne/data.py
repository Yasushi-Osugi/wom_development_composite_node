# -*- coding: utf-8 -*-
"""
地図データ：`data/worldmap_ne/ne_{110m,50m,10m}.npz`（`tools/build_worldmap_ne.py` が作る）

- 投影は Web メルカトル（今のタイルの地図と同じ見え方）。numpy で読み込み時に 1 回だけ計算する。
  x = 経度（度）、y = メルカトルの y を度の単位にしたもの（x と同じ尺度なので縦横比 1 で描ける）。
- 線（海岸線・国境線）は、変換の段階で最大 256 点ずつの部分に分けてあり、各部分の範囲（bbox）で
  表示範囲に入るものだけを選ぶ（10m を寄って描くときに効く）。
- 細かさはズームで切り替える（choose_lod：画面 1 ピクセルあたりの経度で決める）：引いた画面は
  110m、地域は 50m、寄ったときだけ 10m。
  陸地の塗りつぶしは 110m と 50m だけ（10m の範囲では 50m の陸地を使う）。
"""
from __future__ import annotations

import os
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(REPO, "data", "worldmap_ne")
SCALES = ("110m", "50m", "10m")
LAT_MAX = 85.05112878

# Level of detail by the SCALE on the screen: degrees of longitude per pixel of
# the map (so the choice does not depend on the window's shape or size).
#   > 0.15 deg/px   (the world: 360 deg over ~1400 px = 0.26)        -> 110m
#   0.015..0.15     (a region: Asia ~125 deg over 1400 px = 0.09)     -> 50m
#   < 0.015         (a country or a city: Thailand ~15 deg = 0.011)  -> 10m
LOD_WIDE, LOD_NARROW = 0.15, 0.015


def merc_y(lat):
    lat = np.clip(np.asarray(lat, dtype=np.float64), -LAT_MAX, LAT_MAX)
    return np.degrees(np.log(np.tan(np.pi / 4.0 + np.radians(lat) / 2.0)))


def inv_merc_y(y):
    return np.degrees(2.0 * np.arctan(np.exp(np.radians(np.asarray(y, dtype=np.float64)))) - np.pi / 2.0)


def project(lon, lat) -> Tuple[np.ndarray, np.ndarray]:
    return np.asarray(lon, dtype=np.float64), merc_y(lat)


def choose_lod(view_width_deg: float, width_px: float = 1400.0) -> str:
    dpp = view_width_deg / max(width_px, 1.0)
    if dpp > LOD_WIDE:
        return "110m"
    if dpp > LOD_NARROW:
        return "50m"
    return "10m"


class Layer:
    """One layer of one scale, projected. `parts` are views into one array."""

    def __init__(self, xy: np.ndarray, off: np.ndarray):
        pxy = np.empty(xy.shape, dtype=np.float64)
        pxy[:, 0] = xy[:, 0]
        pxy[:, 1] = merc_y(xy[:, 1])
        self.xy = pxy
        self.off = off
        self.parts: List[np.ndarray] = np.split(pxy, off[1:-1]) if len(off) > 2 else (
            [pxy] if len(pxy) else [])
        starts = off[:-1]
        if len(starts):                             # projected bbox of each part
            self.bbox = np.column_stack([np.minimum.reduceat(pxy[:, 0], starts),
                                         np.minimum.reduceat(pxy[:, 1], starts),
                                         np.maximum.reduceat(pxy[:, 0], starts),
                                         np.maximum.reduceat(pxy[:, 1], starts)])
        else:
            self.bbox = np.zeros((0, 4))
        self.n_points = int(len(pxy))

    def select(self, view: Optional[Tuple[float, float, float, float]] = None) -> List[np.ndarray]:
        """Parts whose bbox intersects view=(x0, y0, x1, y1) (projected); all if None."""
        if view is None:
            return self.parts
        x0, y0, x1, y1 = view
        b = self.bbox
        m = (b[:, 2] >= x0) & (b[:, 0] <= x1) & (b[:, 3] >= y0) & (b[:, 1] <= y1)
        idx = np.nonzero(m)[0]
        parts = self.parts
        return [parts[i] for i in idx]


class NEMap:
    """The map data of the scales loaded (each scale is loaded once)."""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.layers: Dict[str, Dict[str, Layer]] = {}
        self.load_seconds: Dict[str, float] = {}

    def available(self) -> List[str]:
        return [s for s in SCALES if os.path.exists(os.path.join(self.data_dir, f"ne_{s}.npz"))]

    def load(self, scales: Sequence[str] = SCALES) -> "NEMap":
        for s in scales:
            if s in self.layers:
                continue
            t0 = time.perf_counter()
            path = os.path.join(self.data_dir, f"ne_{s}.npz")
            with np.load(path) as z:
                names = sorted({k.rsplit("_", 1)[0] for k in z.files})
                self.layers[s] = {n: Layer(z[f"{n}_xy"], z[f"{n}_off"]) for n in names}
            self.load_seconds[s] = time.perf_counter() - t0
        return self

    def has(self, scale: str) -> bool:
        return scale in self.layers

    def lines(self, scale: str, layer: str, view=None) -> List[np.ndarray]:
        L = self.layers.get(scale, {}).get(layer)
        return L.select(view) if L is not None else []

    def land(self, scale: str, view=None) -> List[np.ndarray]:
        """Land polygons: 110m or 50m (the 10m view uses the 50m land)."""
        s = scale if scale in ("110m", "50m") else "50m"
        if s not in self.layers:
            s = "110m" if "110m" in self.layers else s
        L = self.layers.get(s, {}).get("land")
        return L.select(view) if L is not None else []

    def points(self) -> Dict[str, int]:
        return {f"{s}/{n}": L.n_points for s, d in self.layers.items() for n, L in d.items()}
