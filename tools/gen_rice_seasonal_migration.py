# -*- coding: utf-8 -*-
"""
tools/gen_rice_seasonal_migration.py — 通常 Rice の移行用コピーを作る
（RequestLetter_RiceSeasonal_Implementation C、§8.1・§8.2 の Owner の決定）

    python -m tools.gen_rice_seasonal_migration \
        [--src data/sample/rice-japan-2027-2028] [--dst data/trial/rice-japan-2027-2028-seasonal]

元の Rice（legacy の比較用）は変えない。コピーだけを、次のように変える：

  planning_config.csv   lot_flow_mode = identity（元は legacy）
  capacity_plan.csv     稲作田の非収穫週 0.1 → 0（能力ゼロを明示）。精米センターは品目共用の
                        設備なので、エンジンの品目別の上限を共用の値（東 1,300・西 1,000）にする
                        （品目の合計は上位の層が一つの resource_id で守る）。計画期間の最後の週
                        2028-W52 の行を足す（元は 2028-W51 まで＝W52 は上限なしだった）
  node_cost_master.csv  精米センターから先の 16 行（§8.2）。ほかの行は変えない
  sku_master.csv        unit_cost＝地域の DC の売価、selling_price＝小売の売価（§8.2）
  vc_config.csv（新規） report_start = 2027-W01 だけ（報告の開始週の正典。§8.1-6）
  rice_*.csv（新規）    上位の層（RiceSeasonalPlugin）の入力：方針・レシピ・資源・資源の割当・
                        週の能力と収穫カレンダー・年産上限
  README.md（新規）

値は §8.1：1 lot＝精米 3 t、歩留まり 0.9、玄米の保存 52 週、収穫への遡及 52 週＋経路の LT、
精米の前倒し 1 週まで（2026-10-09 変更）、報告の開始 2027-W01、精米センター東 1,300・西 1,000 lot/週（品目共用）、
玄米倉庫は上限なし。収穫は今の capacity_plan.csv の収穫週の値（データは直さない）。
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NOTE = "1 lot＝精米 3 t、2026年産の店頭 約500円/kg から逆算（仮置き）"
SHARED_MILL = {"Seihaku_E": 1300, "Seihaku_W": 1000}
FIELDS = {"Koshihikari": ("Tanbo_Niigata", "NIIGATA"), "Yumepirika": ("Tanbo_Hokkaido", "HOKKAIDO")}
NODE_COST = [  # §8.2 (JPY/lot)
    ("Koshihikari", "Seihaku_E", 1100000, 970000), ("Koshihikari", "Seihaku_W", 1130000, 985000),
    ("Koshihikari", "DC_Higashi", 1200000, 1110000), ("Koshihikari", "DC_Nishi", 1230000, 1140000),
    ("Koshihikari", "Retail_KANTO", 1500000, 1200000), ("Koshihikari", "Retail_TOHOKU", 1410000, 1200000),
    ("Koshihikari", "Retail_KANSAI", 1550000, 1230000), ("Koshihikari", "Retail_KYUSHU", 1450000, 1230000),
    ("Yumepirika", "Seihaku_E", 1010000, 900000), ("Yumepirika", "Seihaku_W", 1030000, 920000),
    ("Yumepirika", "DC_Higashi", 1100000, 1020000), ("Yumepirika", "DC_Nishi", 1120000, 1040000),
    ("Yumepirika", "Retail_KANTO", 1310000, 1100000), ("Yumepirika", "Retail_TOHOKU", 1220000, 1100000),
    ("Yumepirika", "Retail_KANSAI", 1360000, 1120000), ("Yumepirika", "Retail_KYUSHU", 1270000, 1120000),
]
SKU = {  # §8.2 (sku_id, region) -> (unit_cost, selling_price)
    ("Koshihikari", "KANTO"): (1200000, 1500000), ("Koshihikari", "TOHOKU"): (1200000, 1410000),
    ("Koshihikari", "KANSAI"): (1230000, 1550000), ("Koshihikari", "KYUSHU"): (1230000, 1450000),
    ("Yumepirika", "KANTO"): (1100000, 1310000), ("Yumepirika", "TOHOKU"): (1100000, 1220000),
    ("Yumepirika", "KANSAI"): (1120000, 1360000), ("Yumepirika", "KYUSHU"): (1120000, 1270000),
}


def _read(path):
    raw = open(path, "rb").read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    header = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))).fieldnames)
    return header, rows, nl


def _write(path, header, rows, nl="\n"):
    buf = io.StringIO()
    w = csv.DictWriter(buf, header, lineterminator=nl)
    w.writeheader()
    w.writerows(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())


def build(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    j = lambda n: os.path.join(dst, n)
    _write(j("planning_config.csv"), ["key", "value"], [{"key": "lot_flow_mode", "value": "identity"}])

    # capacity_plan.csv
    header, rows, nl = _read(j("capacity_plan.csv"))
    harvest = []
    for r in rows:
        if r["node_name"].startswith("Tanbo_"):
            if r["max_supply"] == "0.1":
                r["max_supply"] = "0"
                r["source"] = "稲作田_非収穫期（能力ゼロ。元の 0.1 は legacy の回避策）"
            else:
                harvest.append((r["sku_id"], r["node_name"], r["week"], r["max_supply"]))
        elif r["node_name"] in SHARED_MILL:
            r["max_supply"] = str(SHARED_MILL[r["node_name"]])
            r["source"] = "精米センター（品目共用の設備の値。品目の合計は上位の層が守る）"
    last = sorted({r["week"] for r in rows})[-1]
    if last == "2028-W51":
        for r in [r for r in rows if r["week"] == "2028-W51"]:
            x = dict(r)
            x["week"] = "2028-W52"
            rows.append(x)
    _write(j("capacity_plan.csv"), header, rows, nl)

    # node_cost_master.csv / sku_master.csv (§8.2)
    header, rows, nl = _read(j("node_cost_master.csv"))
    table = {(s, n): (sp, uc) for s, n, sp, uc in NODE_COST}
    hit = set()
    for r in rows:
        k = (r["sku_id"], r["node_name"])
        if k in table:
            r["selling_price_per_lot"], r["unit_cost_per_lot"] = map(str, table[k])
            r["note"] = NOTE
            hit.add(k)
    if hit != set(table):
        raise SystemExit(f"node_cost_master.csv: rows not found {sorted(set(table) - hit)}")
    _write(j("node_cost_master.csv"), header, rows, nl)
    header, rows, nl = _read(j("sku_master.csv"))
    if "note" not in header:
        header.append("note")
    for r in rows:
        k = (r["sku_id"], r["region"])
        r["unit_cost"], r["selling_price"] = map(str, SKU[k])
        r["note"] = NOTE
    _write(j("sku_master.csv"), header, rows, nl)

    # the Rice upper-layer inputs
    _write(j("rice_seasonal_config.csv"), ["key", "value", "note"], [
        {"key": "harvest_lookback_weeks", "value": "52", "note": "収穫への遡及＝52 週＋経路の LT（§8.1-5）"},
        {"key": "max_brown_storage_weeks", "value": "52", "note": "玄米の保存は最長 52 週（§8.1-5）"},
        {"key": "max_polish_advance_weeks", "value": "1",
         "note": "精米の前倒し 1 週まで（§8.1-5、2026-10-09 変更）"},
    ])
    # The reporting period starts in vc_config.csv (one place for the World Map, Value Chain,
    # Flow Check and the Rice layer; RequestLetter_RiceSeasonal_PolishAdvance1 work 5).
    # Only report_start is written: the other vc_* masters are not prepared for Rice, so
    # the Value Chain ledger stays off (it needs all four vc_* files).
    _write(j("vc_config.csv"), ["key", "value"], [{"key": "report_start", "value": "2027-W01"}])
    _write(j("rice_recipe.csv"), ["product", "white_kg_per_lot", "milling_yield", "note"], [
        {"product": p, "white_kg_per_lot": "3000", "milling_yield": "9/10",
         "note": "1 lot＝精米 3 t、歩留まり 0.9。残り（ぬか等）は物量だけ（§8.1-3・4）"} for p in FIELDS])
    res, rmap, cap, crop = [], [], [], []
    for p, (field, reg) in FIELDS.items():
        res += [
            {"resource_id": f"FIELD_{reg}", "kind": "raw_kg_week", "capacity_unit": "lot", "default_capacity": "0",
             "note": "収穫（非収穫週は 0）。週の値は rice_resource_capacity.csv"},
            {"resource_id": f"COLLECT_{reg}", "kind": "raw_kg_week", "capacity_unit": "unlimited",
             "default_capacity": "", "note": "集荷（今のデータに能力が無い。上限なしを明示）"},
            {"resource_id": f"STORE_RECEIPT_{reg}", "kind": "raw_kg_week", "capacity_unit": "unlimited",
             "default_capacity": "", "note": "玄米倉庫の受入れ（上限なしを明示）"},
            {"resource_id": f"BROWN_STORE_{reg}", "kind": "brown_stock_kg", "capacity_unit": "unlimited",
             "default_capacity": "", "note": "玄米倉庫（上限なしを明示、§8.1-7）"},
        ]
        wh = "Genmai_Souko_Niigata" if reg == "NIIGATA" else "Genmai_Souko_Hokkaido"
        rmap += [{"product": p, "node_name": field, "role": "harvest", "resource_id": f"FIELD_{reg}"},
                 {"product": p, "node_name": f"Sanchiku_{reg.title()}", "role": "collection",
                  "resource_id": f"COLLECT_{reg}"},
                 {"product": p, "node_name": wh, "role": "store_receipt", "resource_id": f"STORE_RECEIPT_{reg}"},
                 {"product": p, "node_name": wh, "role": "storage", "resource_id": f"BROWN_STORE_{reg}"}]
        seasons = set()
        for sku, node, week, val in harvest:
            if sku == p:
                cap.append({"resource_id": f"FIELD_{reg}", "week": week, "capacity": str(int(float(val))),
                            "crop_season": week[:4], "note": "収穫週（今の capacity_plan.csv の値、lot/週）"})
                seasons.add(week[:4])
        for s in sorted(seasons):
            total = sum(int(float(v)) for sku, _n, w, v in harvest if sku == p and w[:4] == s)
            crop.append({"resource_id": f"FIELD_{reg}", "crop_season": s, "limit": str(total), "unit": "lot",
                         "note": "年産上限＝収穫週の能力の合計（データは直さない、§8.1-1。別の業務値は未定）"})
    res += [{"resource_id": "MILL_E", "kind": "raw_kg_week", "capacity_unit": "lot", "default_capacity": "1300",
             "note": "精米センター東（品目共用、品目別の値 900+400 の合計、§8.1-7）"},
            {"resource_id": "MILL_W", "kind": "raw_kg_week", "capacity_unit": "lot", "default_capacity": "1000",
             "note": "精米センター西（品目共用、700+300 の合計、§8.1-7）"},
            {"resource_id": "DC_HIGASHI", "kind": "white_kg_week", "capacity_unit": "unlimited",
             "default_capacity": "", "note": "今のデータに能力が無い。上限なしを明示"},
            {"resource_id": "DC_NISHI", "kind": "white_kg_week", "capacity_unit": "unlimited",
             "default_capacity": "", "note": "同上"}]
    for m in ("KANTO", "TOHOKU", "KANSAI", "KYUSHU"):
        res.append({"resource_id": f"MARKET_{m}", "kind": "white_kg_week", "capacity_unit": "unlimited",
                    "default_capacity": "", "note": "市場（上限なしを明示）"})
    for p in FIELDS:
        for mill, rid in (("Seihaku_E", "MILL_E"), ("Seihaku_W", "MILL_W")):
            rmap.append({"product": p, "node_name": mill, "role": "polish", "resource_id": rid})
        for dc, rid in (("DC_Higashi", "DC_HIGASHI"), ("DC_Nishi", "DC_NISHI")):
            rmap.append({"product": p, "node_name": dc, "role": "dc", "resource_id": rid})
        for m in ("KANTO", "TOHOKU", "KANSAI", "KYUSHU"):
            rmap.append({"product": p, "node_name": f"Retail_{m}", "role": "market", "resource_id": f"MARKET_{m}"})
    _write(j("rice_resources.csv"), ["resource_id", "kind", "capacity_unit", "default_capacity", "note"], res)
    _write(j("rice_resource_map.csv"), ["product", "node_name", "role", "resource_id"], rmap)
    _write(j("rice_resource_capacity.csv"), ["resource_id", "week", "capacity", "crop_season", "note"], cap)
    _write(j("rice_crop_limit.csv"), ["resource_id", "crop_season", "limit", "unit", "note"], crop)
    with open(j("README.md"), "w", encoding="utf-8", newline="") as f:
        f.write(README)
    return dst


README = """# rice-japan-2027-2028-seasonal（通常 Rice の移行用コピー）

`tools/gen_rice_seasonal_migration.py` が `data/sample/rice-japan-2027-2028`（legacy、比較用、変えない）から作る。
手で直さず、道具を直して作り直すこと。依頼書：`requests/RequestLetter_RiceSeasonal_Implementation_to_CodeKun.md`
（§8.1・§8.2 の Owner の決定）。報告書：`docs/development/WOM_RiceSeasonal_Implementation_Report.md`。

## 計画の仕方

- lot_flow_mode = identity。HarvestBatch は使わない。
- プラグイン：Holiday Calendar（＋ Capacity Override・Buffering Stock は入力が無く何もしない）と
  **Rice Seasonal（収穫・玄米保管・精米）**。Rice Seasonal は既定 OFF なので、GUI の Plugins で ON にする。
  headless：`--plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin`
- Rice Seasonal は、市場の需要 ID（要求週・ID はそのまま）を、過去の収穫 → 玄米倉庫 → 要求に近い週の精米に割り当て、
  内部の計画の位置だけを渡す。割り当てられない ID は市場の注文残として残る（消さない）。

## 元の Rice から変えたもの

| ファイル | 変更 |
|---|---|
| planning_config.csv | lot_flow_mode = identity（元は legacy） |
| capacity_plan.csv | 稲作田の非収穫週 0.1 → **0**（能力ゼロを明示）。精米センターのエンジンの上限を品目共用の値（東 1,300・西 1,000）に。2028-W52 の行を追加 |
| node_cost_master.csv | 精米センターから先の 16 行（§8.2、1 lot＝精米 3 t、店頭 約500円/kg から逆算、仮置き） |
| sku_master.csv | unit_cost＝地域の DC の売価、selling_price＝小売の売価（§8.2）、note 列を追加 |

## 上位の層の入力（新規）

| ファイル | 内容 |
|---|---|
| rice_seasonal_config.csv | 収穫への遡及 52 週（＋経路の LT）、玄米の保存 最長 52 週、精米の前倒し 1 週まで（2026-10-09 変更） |
| vc_config.csv | `report_start` = 2027-W01 だけ。**報告の開始週の正典**（World Map・Value Chain・Flow Check・Rice の層が同じ値を読む）。ほかの vc_* マスターは無いので、Value Chain の台帳は作られない |
| rice_recipe.csv | 1 lot＝精米 3,000 kg、歩留まり 0.9（玄米 3,333.3 kg）。残りは「その他の産出」として物量だけ |
| rice_resources.csv | 資源と単位（玄米 kg／週・精米 kg／週・玄米の在庫 kg）。精米センター東 1,300・西 1,000 lot／週は**品目共用の一つの資源**。玄米倉庫・集荷・DC・市場は「上限なし」を明示 |
| rice_resource_map.csv | 品目×ノード×役割 → 資源 |
| rice_resource_capacity.csv | 収穫週と週の収穫能力（今の capacity_plan.csv の収穫週の値）、作期 |
| rice_crop_limit.csv | 作期ごとの年産上限＝収穫週の能力の合計（データは直さない。別の業務値は未定） |

## 結果の読み方（Owner の決定）

- 2026 年は助走の年。2025 年産の収穫は計画期間の外なので、2026 年の収穫が届くまでの需要は注文残になる（報告とは別に数える）。
- コシヒカリは年産の収穫能力（46,500 lot）が需要（約 59,903 lot）より少ない。不足は市場の注文残として見せる（データは直さない）。
- 不足は要求週の早い順に配り、同じ週の中では市場の要求量に比例（最大剰余法）。
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", default=os.path.join(REPO, "data", "sample", "rice-japan-2027-2028"))
    ap.add_argument("--dst", default=os.path.join(REPO, "data", "trial", "rice-japan-2027-2028-seasonal"))
    a = ap.parse_args(argv)
    print(build(a.src, a.dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
