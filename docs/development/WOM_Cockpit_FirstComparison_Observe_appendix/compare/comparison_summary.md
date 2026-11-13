# 2 案の比較（late → early）

- base（late）：実行 `output/cockpit_cmp1/run_late`、モデル `output/cockpit_cmp1/model_late`
- alt（early）：実行 `output/cockpit_cmp1/run_early`、モデル `output/cockpit_cmp1/model_early`
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
| COS_Cream:TH_Distributor | 299/377 | 211/211 | 0/0 | 0/0 | 88/166 |
| COS_Serum:SG_Distributor | 897/897 | 897/897 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 286/286 | 0/0 | 0/0 | 104/104 |

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,119,737,280 | 1,119,737,280 | 0 | 607,601,448 | 607,601,448 | 0 |
| full | COS_Cream | 432,037,800 | 432,037,800 | 0 | 232,761,996 | 232,761,996 | 0 |
| full | COS_Serum | 687,699,480 | 687,699,480 | 0 | 374,839,452 | 374,839,452 | 0 |
| report | * | 1,118,611,200 | 1,118,611,200 | 0 | 606,871,080 | 606,871,080 | 0 |
| report | COS_Cream | 431,524,440 | 431,524,440 | 0 | 232,432,128 | 232,432,128 | 0 |
| report | COS_Serum | 687,086,760 | 687,086,760 | 0 | 374,438,952 | 374,438,952 | 0 |

PPC（全計画期間）：売上 base 1,119,737,280 / alt 1,119,737,280、試算利益 base 607,601,448 / alt 607,601,448
未評価の明細（連結の法人）：{'late': 0, 'early': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 26821 / alt 21491、最大 base 256 / alt 255、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 late *：納品 3864、最大 28 週、52 週超 0
- 年齢 late COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 late COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 early *：納品 3864、最大 28 週、52 週超 0
- 年齢 early COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 early COS_Serum：納品 2184、最大 28 週、52 週超 0

## 差の出た週

- supply_by_request_week first：2027-W27（4）
- supply_by_request_week max：2027-W40（6）
- profit_r2_by_week first：2027-W24（1,440）
- profit_r2_by_week max：2029-W19（342,720）

代表の lot：`COS_Cream:TH_Distributor:2027-W27:00001`（supply first request week 2027-W27）、`COS_Cream:TH_Distributor:2027-W40:00001`（supply max request week 2027-W40）、`COS_Cream:TH_Distributor:2029-W19:00001`（profit max week 2029-W19）

## 計画の境界

- 2026-W37（first_week）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W51（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W52（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0

工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）：
- early COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- early COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- late COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- late COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（仮）

- COS_Cream の報告期間の試算利益の差：0 円、分母 26 週 → （the alternative does not exceed the base even before fixed cost （早期案は固定費の前でも上回らない））

