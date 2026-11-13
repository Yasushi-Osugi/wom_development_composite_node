# 2 案の比較（late_soft11 → B_late）

- base（late_soft11）：実行 `output/cockpit_cmp1/run_late`、モデル `output/cockpit_cmp1/model_late`
- alt（B_late）：実行 `output/cockpit_cmp2/run_B_late`、モデル `output/cockpit_cmp2/B_late`
- 計画の週：2026-W37〜2029-W52（173 週）

## 入力の表の違い

（違いなし）

## 需要（lot、全計画期間）

| 鍵 | base | alt | 差 |
|---|---:|---:|---:|
| COS_Cream:SG_Distributor | 754 | 754 | +0 |
| COS_Cream:SG_EC | 299 | 299 | +0 |
| COS_Cream:SG_Store | 416 | 416 | +0 |
| COS_Cream:TH_Distributor | 299 | 299 | +0 |
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
| COS_Cream:TH_Distributor | 299/299 | 211/299 | 0/0 | 0/0 | 88/0 |
| COS_Serum:SG_Distributor | 897/897 | 897/897 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 286/286 | 0/0 | 0/0 | 104/104 |

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,119,737,280 | 1,134,943,680 | 15,206,400 | 607,601,448 | 617,591,208 | 9,989,760 |
| full | COS_Cream | 432,037,800 | 447,244,200 | 15,206,400 | 232,761,996 | 242,751,756 | 9,989,760 |
| full | COS_Serum | 687,699,480 | 687,699,480 | 0 | 374,839,452 | 374,839,452 | 0 |
| report | * | 1,118,611,200 | 1,133,817,600 | 15,206,400 | 606,871,080 | 616,860,840 | 9,989,760 |
| report | COS_Cream | 431,524,440 | 446,730,840 | 15,206,400 | 232,432,128 | 242,421,888 | 9,989,760 |
| report | COS_Serum | 687,086,760 | 687,086,760 | 0 | 374,438,952 | 374,438,952 | 0 |

PPC（全計画期間）：売上 base 1,119,737,280 / alt 1,134,943,680、試算利益 base 607,601,448 / alt 617,591,208
未評価の明細（連結の法人）：{'late_soft11': 0, 'B_late': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 26821 / alt 26989、最大 base 256 / alt 246、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 late_soft11 *：納品 3864、最大 28 週、52 週超 0
- 年齢 late_soft11 COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 late_soft11 COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 B_late *：納品 3952、最大 28 週、52 週超 0
- 年齢 B_late COS_Cream：納品 1768、最大 24 週、52 週超 0
- 年齢 B_late COS_Serum：納品 2184、最大 28 週、52 週超 0

## 差の出た週

- supply_by_request_week first：2029-W21（2）
- supply_by_request_week max：2029-W22（6）
- profit_r2_by_week first：2029-W18（720）
- profit_r2_by_week max：2029-W48（342,720）

代表の lot：`COS_Cream:TH_Distributor:2029-W21:00003`（supply first request week 2029-W21）、`COS_Cream:TH_Distributor:2029-W22:00001`（supply max request week 2029-W22）、`COS_Cream:TH_Distributor:2029-W48:00001`（profit max week 2029-W48）

## 計画の境界

- 2026-W37（first_week）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W51（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W52（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0

工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）：
- B_late COS_Cream：2026-W37, 2026-W38, 2026-W39, 2026-W40, 2026-W41, 2026-W42, 2026-W43, 2026-W44, 2026-W45, 2029-W47, 2029-W48, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 135 lot）
- B_late COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- late_soft11 COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- late_soft11 COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）

- TH_cream_channel_fee：P0 base 606,871,080 / alt 616,860,840、ΔP0 9,989,760（COS_Cream: 9,989,760; COS_Serum: 0）、W base 104 / alt 104、ΔW 0 → 順位変化なし（発生週数が同じ）（評価済み）

