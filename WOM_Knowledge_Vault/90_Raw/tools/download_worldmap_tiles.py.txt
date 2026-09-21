#!/usr/bin/env python
"""
WOM World Map Tile Pre-downloader
==================================
OpenStreetMap タイルを SQLite データベースに事前ダウンロードするスクリプト。
インターネット接続がある環境で一度実行しておくと、
以降の WOM 起動はオフライン環境でも世界地図が表示されます。

使い方
------
    python tools/download_worldmap_tiles.py           # デフォルト zoom 1-5
    python tools/download_worldmap_tiles.py --zoom 6  # zoom 6 まで追加
    python tools/download_worldmap_tiles.py --zoom 5 --db path/to/custom.db

保存先
------
    <project-root>/data/worldmap_cache.db

データベーススキーマ（tkintermapview v1.29 互換）
-------------------------------------------------
    tiles (zoom INTEGER, x INTEGER, y INTEGER, tile_image BLOB, server TEXT)
    ※ tkintermapview は server カラムで tile_server URL を照合するため、
      ダウンロード URL と WOM の tile_server 設定を一致させる必要がある。
"""
from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("requests が必要です: pip install requests")


# ── Tile server URL（app.py の set_tile_server と必ず一致させること）─────────
# OSM はデフォルト User-Agent "TkinterMapView" をブロックするため CARTO を使用。
# DB の server カラムにこの値が保存され、オフライン時の DB ルックアップで照合される。
OSM_SERVER = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"

HEADERS = {
    "User-Agent": "WOM-OfflineMapCache/1.0 (supply-chain-planning-tool; "
                  "contact: github.com/Yasushi-Osugi/wom_v1r0m0)"
}


# ── タイル座標計算 ────────────────────────────────────────────────────────────

def _tile_xy(lat: float, lon: float, zoom: int) -> tuple:
    """緯度経度 → タイル (x, y) 変換（Web Mercator）"""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    # lon=180 等で範囲外になるケースをクランプ
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def _bbox_tile_range(lat_min, lat_max, lon_min, lon_max, zoom):
    x0, y1 = _tile_xy(lat_min, lon_min, zoom)
    x1, y0 = _tile_xy(lat_max, lon_max, zoom)
    return min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)


# ── ダウンロード対象リージョン ──────────────────────────────────────────────

FOCUS_REGIONS = [
    (-60,  75, -180,  180, "World"),        # zoom 1-4 のみ
    ( 30,  47,  129,  146, "Japan"),
    ( 21,  27,  119,  123, "Taiwan"),
    ( 32,  49, -126, -114, "US-WestCoast"),
    ( 47,  56,   -6,   11, "W-Europe"),
    ( 17,  21,   72,   76, "India-Pune"),
    (  0,   3,  102,  105, "Singapore"),
    ( 28,  41,  108,  123, "China-Zhengzhou"),
]


# ── DB 初期化（tkintermapview v1.29 互換スキーマ）────────────────────────────

def _init_db(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # テーブル名・カラム名は tkintermapview の request_image() に合わせる
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiles (
            zoom       INTEGER,
            x          INTEGER,
            y          INTEGER,
            tile_image BLOB,
            server     TEXT,
            UNIQUE (zoom, x, y, server)
        )
    """)
    conn.commit()
    return conn, cursor


# ── タイルダウンロード ─────────────────────────────────────────────────────────

def _download_region(cursor, conn, zoom, lat_min, lat_max, lon_min, lon_max,
                     desc, server_url, delay=0.05):
    x_min, x_max, y_min, y_max = _bbox_tile_range(lat_min, lat_max, lon_min, lon_max, zoom)
    total = (x_max - x_min + 1) * (y_max - y_min + 1)
    print(f"  z{zoom} {desc}: {total} tiles", flush=True)

    new = cached = failed = 0
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            cursor.execute(
                "SELECT 1 FROM tiles WHERE zoom=? AND x=? AND y=? AND server=?",
                (zoom, x, y, server_url))
            if cursor.fetchone():
                cached += 1
                continue

            url = server_url.replace("{z}", str(zoom)).replace("{x}", str(x)).replace("{y}", str(y))
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                if r.status_code == 200:
                    cursor.execute(
                        "INSERT OR REPLACE INTO tiles (zoom, x, y, tile_image, server)"
                        " VALUES (?,?,?,?,?)",
                        (zoom, x, y, r.content, server_url))
                    new += 1
                    if new % 200 == 0:
                        conn.commit()
                        print(f"    … {new + cached}/{total}", flush=True)
                else:
                    failed += 1
                    if failed <= 5:
                        print(f"    HTTP {r.status_code}: {url}", flush=True)
            except Exception as exc:
                failed += 1
                if failed <= 5:
                    print(f"    WARN {url}: {exc}", flush=True)
            time.sleep(delay)

    conn.commit()
    print(f"    → new:{new}  cached:{cached}  failed:{failed}", flush=True)
    return new, cached, failed


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="WOM 世界地図タイルを事前ダウンロードしてオフライン利用を可能にする")
    parser.add_argument("--zoom", type=int, default=5,
                        help="最大ズームレベル (デフォルト: 5)")
    parser.add_argument("--db", type=str, default=None,
                        help="SQLite DB パス (デフォルト: <project>/data/worldmap_cache.db)")
    parser.add_argument("--delay", type=float, default=0.05,
                        help="タイルリクエスト間隔（秒）(デフォルト: 0.05)")
    args = parser.parse_args()

    script_dir   = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    default_db   = os.path.join(project_root, "data", "worldmap_cache.db")
    db_path      = args.db or default_db

    print("=" * 60)
    print("WOM World Map Tile Downloader")
    print(f"  DB     : {db_path}")
    print(f"  Server : {OSM_SERVER}")
    print(f"  Zoom   : 1 - {args.zoom}")
    print(f"  Delay  : {args.delay}s / tile")
    print("=" * 60)

    conn, cursor = _init_db(db_path)
    total_new = total_cached = total_failed = 0

    for zoom in range(1, args.zoom + 1):
        print(f"\n── Zoom {zoom} ──────────────────────────")
        for region in FOCUS_REGIONS:
            lat_min, lat_max, lon_min, lon_max, desc = region
            if zoom <= 4:
                if desc != "World":
                    continue
            else:
                if desc == "World":
                    continue
            n, c, f = _download_region(
                cursor, conn, zoom,
                lat_min, lat_max, lon_min, lon_max, desc,
                server_url=OSM_SERVER, delay=args.delay)
            total_new += n; total_cached += c; total_failed += f

    cursor.execute(
        "SELECT zoom, COUNT(*) FROM tiles WHERE server=? GROUP BY zoom ORDER BY zoom",
        (OSM_SERVER,))
    rows = cursor.fetchall()
    grand_total = sum(r[1] for r in rows)
    db_mb = os.path.getsize(db_path) / 1024 / 1024

    print("\n" + "=" * 60)
    print("Summary")
    for z, cnt in rows:
        print(f"  zoom {z:2d}: {cnt:6d} tiles")
    print(f"  TOTAL : {grand_total} tiles")
    print(f"  DB    : {db_mb:.1f} MB")
    print(f"  新規DL: {total_new}  キャッシュ済み: {total_cached}  失敗: {total_failed}")
    print("=" * 60)
    print("完了。次回 WOM 起動からオフラインで世界地図が表示されます。")
    conn.close()


if __name__ == "__main__":
    main()
