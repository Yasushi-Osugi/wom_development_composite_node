# 2 案の比較（B_late → B_early）

- base（B_late）：実行 `output/cockpit_cmp2/run_B_late`、モデル `output/cockpit_cmp2/B_late`
- alt（B_early）：実行 `output/cockpit_cmp2/run_B_early`、モデル `output/cockpit_cmp2/B_early`
- 計画の週：2026-W37〜2029-W52（173 週）

## 入力の表の違い

- COS_Cream:TH_Distributor `launch_week`：2028-W01 → 2027-W27

## 需要（lot、全計画期間）

| 鍵 | base | alt | 差 |
|---|---:|---:|---:|
| COS_Cream:SG_Distributor | 754 | 754 | +0 |
| COS_Cream:SG_EC | 299 | 299 | +0 |
| COS_Cream:SG_Store | 416 | 416 | +0 |
| COS_Cream:TH_Distributor | 299 | 377 | +78 |
| COS_Serum:SG_Distributor | 897 | 897 | +0 |
| COS_Serum:SG_EC | 455 | 455 | +0 |
| COS_Serum:SG_Store | 546 | 546 | +0 |
| COS_Serum:TH_Distributor | 390 | 390 | +0 |

## 供給（Lot_ID で要求週へ戻した合計。Flow Check の表 2 と一致を確認済み）

| 鍵 | 需要 base/alt | 当週 base/alt | 遅配 base/alt | 早出し base/alt | 期末の未充足 base/alt |
|---|---|---|---|---|---|
| COS_Cream:SG_Distributor | 754/754 | 754/754 | 0/0 | 0/0 | 0/0 |
| COS_Cream:SG_EC | 299/299 | 299/299 | 0/0 | 0/0 | 0/0 |
| COS_Cream:SG_Store | 416/416 | 416/416 | 0/0 | 0/0 | 0/0 |
| COS_Cream:TH_Distributor | 299/377 | 299/377 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Distributor | 897/897 | 897/897 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 286/286 | 0/0 | 0/0 | 104/104 |

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,134,943,680 | 1,148,422,080 | 13,478,400 | 617,591,208 | 626,445,768 | 8,854,560 |
| full | COS_Cream | 447,244,200 | 460,722,600 | 13,478,400 | 242,751,756 | 251,606,316 | 8,854,560 |
| full | COS_Serum | 687,699,480 | 687,699,480 | 0 | 374,839,452 | 374,839,452 | 0 |
| report | * | 1,133,817,600 | 1,147,296,000 | 13,478,400 | 616,860,840 | 625,715,400 | 8,854,560 |
| report | COS_Cream | 446,730,840 | 460,209,240 | 13,478,400 | 242,421,888 | 251,276,448 | 8,854,560 |
| report | COS_Serum | 687,086,760 | 687,086,760 | 0 | 374,438,952 | 374,438,952 | 0 |

PPC（全計画期間）：売上 base 1,134,943,680 / alt 1,148,422,080、試算利益 base 617,591,208 / alt 626,445,768
未評価の明細（連結の法人）：{'B_late': 0, 'B_early': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 26989 / alt 31340、最大 base 246 / alt 297、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 B_late *：納品 3952、最大 28 週、52 週超 0
- 年齢 B_late COS_Cream：納品 1768、最大 24 週、52 週超 0
- 年齢 B_late COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 B_early *：納品 4030、最大 29 週、52 週超 0
- 年齢 B_early COS_Cream：納品 1846、最大 29 週、52 週超 0
- 年齢 B_early COS_Serum：納品 2184、最大 28 週、52 週超 0

## 差の出た週

- supply_by_request_week first：2027-W27（4）
- supply_by_request_week max：2027-W40（6）
- profit_r2_by_week first：2027-W24（1,440）
- profit_r2_by_week max：2027-W50（342,000）

代表の lot：`COS_Cream:TH_Distributor:2027-W27:00001`（supply first request week 2027-W27）、`COS_Cream:TH_Distributor:2027-W40:00001`（supply max request week 2027-W40）、`COS_Cream:TH_Distributor:2027-W50:00001`（profit max week 2027-W50）

## 計画の境界

- 2026-W37（first_week）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W51（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W52（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0

工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）：
- B_early COS_Cream：2026-W37, 2029-W47, 2029-W48, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 57 lot）
- B_early COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- B_late COS_Cream：2026-W37, 2026-W38, 2026-W39, 2026-W40, 2026-W41, 2026-W42, 2026-W43, 2026-W44, 2026-W45, 2029-W47, 2029-W48, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 135 lot）
- B_late COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）

- TH_cream_channel_fee：P0 base 616,860,840 / alt 625,715,400、ΔP0 8,854,560（COS_Cream: 8,854,560; COS_Serum: 0）、W base 104 / alt 130、ΔW 26 → f* = ΔP0 ÷ ΔW（f が小さければ alt が上、等しければ同額、大きければ base が上）：**340,560 円／週**（評価済み）

