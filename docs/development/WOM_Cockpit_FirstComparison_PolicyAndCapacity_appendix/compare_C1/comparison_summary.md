# 2 案の比較（A_late → A_early）

- base（A_late）：実行 `output/cockpit_cmp2/run_A_late`、モデル `output/cockpit_cmp2/A_late_m`
- alt（A_early）：実行 `output/cockpit_cmp2/run_A_early`、モデル `output/cockpit_cmp2/A_early_m`
- 計画の週：2026-W37〜2029-W52（173 週）

## 入力の表の違い

- COS_Cream:TH_Distributor `launch_week`：2028-W01 → 2027-W27

## 需要（lot、全計画期間）

| 鍵 | base | alt | 差 |
|---|---:|---:|---:|
| COS_Cream:SG_Distributor | 666 | 588 | -78 |
| COS_Cream:SG_EC | 299 | 299 | +0 |
| COS_Cream:SG_Store | 416 | 416 | +0 |
| COS_Cream:TH_Distributor | 299 | 377 | +78 |
| COS_Serum:SG_Distributor | 825 | 825 | +0 |
| COS_Serum:SG_EC | 455 | 455 | +0 |
| COS_Serum:SG_Store | 546 | 546 | +0 |
| COS_Serum:TH_Distributor | 358 | 358 | +0 |

## 供給（Lot_ID で要求週へ戻した合計。Flow Check の表 2 と一致を確認済み）

| 鍵 | 需要 base/alt | 当週 base/alt | 遅配 base/alt | 早出し base/alt | 期末の未充足 base/alt |
|---|---|---|---|---|---|
| COS_Cream:SG_Distributor | 666/588 | 666/588 | 0/0 | 0/0 | 0/0 |
| COS_Cream:SG_EC | 299/299 | 299/299 | 0/0 | 0/0 | 0/0 |
| COS_Cream:SG_Store | 416/416 | 416/416 | 0/0 | 0/0 | 0/0 |
| COS_Cream:TH_Distributor | 299/377 | 299/377 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Distributor | 825/825 | 825/825 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 358/358 | 358/358 | 0/0 | 0/0 | 0/0 |

## 数量配分（① 元の需要 ＝ ② 供給の対象 ＋ ③ 未配分、② ＝ 当週 ＋ 早出し ＋ 遅配 ＋ ⑤ 配分後の未充足）

| 鍵 | ① base/alt | ② base/alt | ③ base/alt | 当週 base/alt | 遅配 base/alt | ⑤ base/alt |
|---|---|---|---|---|---|---|
| COS_Cream:SG_Distributor | 754/754 | 666/588 | 88/166 | 666/588 | 0/0 | 0/0 |
| COS_Cream:SG_EC | 299/299 | 299/299 | 0/0 | 299/299 | 0/0 | 0/0 |
| COS_Cream:SG_Store | 416/416 | 416/416 | 0/0 | 416/416 | 0/0 | 0/0 |
| COS_Cream:TH_Distributor | 299/377 | 299/377 | 0/0 | 299/377 | 0/0 | 0/0 |
| COS_Serum:SG_Distributor | 897/897 | 825/825 | 72/72 | 825/825 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 455/455 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 546/546 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 358/358 | 32/32 | 358/358 | 0/0 | 0/0 |

（数量配分の結果を渡した案は、金額の実行の出荷と鍵 × 要求週で一致を確認済み）

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,119,954,240 | 1,120,085,280 | 131,040 | 607,776,840 | 607,886,352 | 109,512 |
| full | COS_Cream | 432,185,640 | 432,316,680 | 131,040 | 232,885,548 | 232,995,060 | 109,512 |
| full | COS_Serum | 687,768,600 | 687,768,600 | 0 | 374,891,292 | 374,891,292 | 0 |
| report | * | 1,118,828,160 | 1,118,959,200 | 131,040 | 607,046,472 | 607,155,984 | 109,512 |
| report | COS_Cream | 431,672,280 | 431,803,320 | 131,040 | 232,555,680 | 232,665,192 | 109,512 |
| report | COS_Serum | 687,155,880 | 687,155,880 | 0 | 374,490,792 | 374,490,792 | 0 |

PPC（全計画期間）：売上 base 1,119,954,240 / alt 1,120,085,280、試算利益 base 607,776,840 / alt 607,886,352
未評価の明細（連結の法人）：{'A_late': 0, 'A_early': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 27466 / alt 23787、最大 base 256 / alt 255、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 A_late *：納品 3864、最大 28 週、52 週超 0
- 年齢 A_late COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 A_late COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 A_early *：納品 3864、最大 28 週、52 週超 0
- 年齢 A_early COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 A_early COS_Serum：納品 2184、最大 28 週、52 週超 0

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
- A_early COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- A_early COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- A_late COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- A_late COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）

- TH_cream_channel_fee：P0 base 607,046,472 / alt 607,155,984、ΔP0 109,512（COS_Cream: 109,512; COS_Serum: 0）、W base 104 / alt 130、ΔW 26 → f* = ΔP0 ÷ ΔW（f が小さければ alt が上、等しければ同額、大きければ base が上）：**4,212 円／週**（評価済み）

