# -*- coding: utf-8 -*-
"""
tools/build_worldmap_ne.py — Natural Earth のシェープファイルを、WOM が実行時に読む小さな
numpy 配列（.npz）に変換する（RequestLetter_SimMgmt_WorldMapTrial Part 2）

    python -m tools.build_worldmap_ne                       # 手元のキャッシュから変換
    python -m tools.build_worldmap_ne --src <dir>           # シェープファイルのフォルダを指定
    python -m tools.build_worldmap_ne --download <dir>      # （使うときだけ）公式から取得して <dir> に置く

入力（Natural Earth、パブリックドメイン）。細かさ 3 段階 × 3 種類：
    physical/ne_{110m,50m,10m}_coastline              海岸線（線）
    cultural/ne_{110m,50m,10m}_admin_0_boundary_lines_land   陸の国境線（線）
    physical/ne_{110m,50m}_land                        陸地（塗りつぶし。10m は使わない）

出力（`data/worldmap_ne/`）：
    ne_110m.npz / ne_50m.npz / ne_10m.npz
        <layer>_xy    float32 (N,2)  経度・緯度（度）
        <layer>_off   int32   (P+1)  各部分の始まりの位置（最後は N）
        <layer>_bbox  float32 (P,4)  各部分の範囲 (lon0, lat0, lon1, lat1)
      線（coast・border）は、表示範囲で切り出しやすいように、1 つの部分を最大
      CHUNK 点に分ける（隣り合う部分は 1 点を共有するので、線は途切れない）。
      陸地（land）は多角形の外周のまま（分けると塗りつぶしが壊れるため）。
    SOURCE.json   出典（URL・版・取得日・ファイルのハッシュ・点の数・出力の大きさ）

シェープファイルを読むのは、この道具だけ（pyshp＝`shapefile`）。WOM の実行時（試作の
画面）は numpy だけで .npz を読む。

取得について：この PC には、cartopy が以前に Natural Earth から取ってきたキャッシュ
（~/.local/share/cartopy/shapefiles/natural_earth）があるので、既定ではそれを使い、
ネットワークには出ない。`--download` は、キャッシュの無い PC で 1 回だけ使う想定
（本件では実行していない）。
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.request
import zipfile

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(REPO, "data", "worldmap_ne")
DEFAULT_SRC = os.path.join(os.path.expanduser("~"), ".local", "share", "cartopy",
                           "shapefiles", "natural_earth")
SCALES = ("110m", "50m", "10m")
# layer -> (category, NE name, kind, scales)
LAYERS = {
    "coast":  ("physical", "coastline",                  "line", SCALES),
    "border": ("cultural", "admin_0_boundary_lines_land", "line", SCALES),
    "land":   ("physical", "land",                        "poly", ("110m", "50m")),
}
CHUNK = 256
# The official download location (the one cartopy uses). Version-less URL = the
# latest release at the time of download.
URL = "https://naturalearth.s3.amazonaws.com/{scale}_{category}/ne_{scale}_{name}.zip"
LANDING = "https://www.naturalearthdata.com/downloads/"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _parts(shape):
    pts = np.asarray(shape.points, dtype=np.float64)
    idx = list(shape.parts) + [len(pts)]
    for a, b in zip(idx[:-1], idx[1:]):
        if b - a >= 2:
            yield pts[a:b]


def _chunks(arr: np.ndarray, n: int):
    if len(arr) <= n:
        yield arr
        return
    i = 0
    while i < len(arr) - 1:
        yield arr[i:i + n]
        i += n - 1                      # share one point with the next chunk


def convert_layer(shp_base: str, kind: str):
    import shapefile                    # pyshp -- used by this tool only
    r = shapefile.Reader(shp_base)
    pieces = []
    n_src_parts = 0
    for shape in r.iterShapes():
        for part in _parts(shape):
            n_src_parts += 1
            if kind == "line":
                pieces.extend(_chunks(part, CHUNK))
            else:
                pieces.append(part)
    xy = np.concatenate(pieces).astype(np.float32) if pieces else np.zeros((0, 2), np.float32)
    off = np.zeros(len(pieces) + 1, dtype=np.int32)
    off[1:] = np.cumsum([len(p) for p in pieces])
    bbox = np.array([[p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max()] for p in pieces],
                    dtype=np.float32).reshape(-1, 4)
    return {"xy": xy, "off": off, "bbox": bbox}, {"features": len(r), "source_parts": n_src_parts,
                                                  "points": int(len(xy)), "stored_parts": len(pieces)}


def download(dest: str) -> None:
    """Fetch the zips from the official location into dest/<category>/ (run once)."""
    for scale in SCALES:
        for _layer, (cat, name, _kind, scales) in LAYERS.items():
            if scale not in scales:
                continue
            url = URL.format(scale=scale, category=cat, name=name)
            d = os.path.join(dest, cat)
            os.makedirs(d, exist_ok=True)
            zp = os.path.join(d, f"ne_{scale}_{name}.zip")
            print("GET", url)
            urllib.request.urlretrieve(url, zp)
            with zipfile.ZipFile(zp) as z:
                z.extractall(d)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", default=DEFAULT_SRC, help="natural_earth folder (physical/, cultural/)")
    ap.add_argument("--out", default=OUT_DIR)
    ap.add_argument("--download", metavar="DIR", default=None,
                    help="fetch from the official location into DIR first, then convert from it")
    a = ap.parse_args(argv)
    src = a.src
    if a.download:
        download(a.download)
        src = a.download
    os.makedirs(a.out, exist_ok=True)
    meta = {
        "title": "Natural Earth (public domain) -- converted for the WOM World Map trial",
        "license": "Public domain (https://www.naturalearthdata.com/about/terms-of-use/)",
        "landing_page": LANDING,
        "download_url_template": URL,
        "source_dir": src,
        "acquired_via": ("cartopy's download cache (cartopy fetched the zips from the URL template "
                         "above; this tool did not access the network)") if not a.download
                        else "tools/build_worldmap_ne.py --download",
        "version_note": ("The cached files carry no version record (cartopy keeps only "
                         ".shp/.shx/.dbf/.prj/.cpg, not the VERSION.txt/README of the zip); "
                         "the version is the Natural Earth release that was current on the "
                         "acquisition date below."),
        "converted_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "chunk_points": CHUNK,
        "coordinates": "lon/lat degrees, float32 (projection is done at run time with numpy)",
        "files": {},
        "outputs": {},
    }
    for scale in SCALES:
        arrays = {}
        for layer, (cat, name, kind, scales) in LAYERS.items():
            if scale not in scales:
                continue
            base = os.path.join(src, cat, f"ne_{scale}_{name}")
            shp = base + ".shp"
            if not os.path.exists(shp):
                print(f"missing: {shp}", file=sys.stderr)
                return 1
            d, stats = convert_layer(base, kind)
            for k, v in d.items():
                arrays[f"{layer}_{k}"] = v
            meta["files"][f"ne_{scale}_{name}"] = {
                "shp": shp.replace(os.path.expanduser("~"), "~"),
                "acquired": datetime.datetime.fromtimestamp(os.path.getmtime(shp)).isoformat(timespec="seconds"),
                "sha256_shp": _sha256(shp), "shp_bytes": os.path.getsize(shp), **stats,
            }
            print(f"{scale:>5} {layer:<6} {stats}")
        out = os.path.join(a.out, f"ne_{scale}.npz")
        np.savez_compressed(out, **arrays)
        meta["outputs"][os.path.basename(out)] = {"bytes": os.path.getsize(out)}
        print(f"-> {out}  {os.path.getsize(out):,} bytes")
    with open(os.path.join(a.out, "SOURCE.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
