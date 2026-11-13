# 2 案の比較（early_noalloc → A_early）

- base（early_noalloc）：実行 `output/cockpit_cmp1/run_early`、モデル `output/cockpit_cmp1/model_early`
- alt（A_early）：実行 `output/cockpit_cmp2/run_A_early`、モデル `output/cockpit_cmp2/A_early_m`
- 計画の週：2026-W37〜2029-W52（173 週）

## 入力の表の違い

（違いなし）

## 需要（lot、全計画期間）

| 鍵 | base | alt | 差 |
|---|---:|---:|---:|
| COS_Cream:SG_Distributor | 754 | 588 | -166 |
| COS_Cream:SG_EC | 299 | 299 | +0 |
| COS_Cream:SG_Store | 416 | 416 | +0 |
| COS_Cream:TH_Distributor | 377 | 377 | +0 |
| COS_Serum:SG_Distributor | 897 | 825 | -72 |
| COS_Serum:SG_EC | 455 | 455 | +0 |
| COS_Serum:SG_Store | 546 | 546 | +0 |
| COS_Serum:TH_Distributor | 390 | 358 | -32 |

## 供給（Lot_ID で要求週へ戻した合計。Flow Check の表 2 と一致を確認済み）

| 鍵 | 需要 base/alt | 当週 base/alt | 遅配 base/alt | 早出し base/alt | 期末の未充足 base/alt |
|---|---|---|---|---|---|
| COS_Cream:SG_Distributor | 754/588 | 754/588 | 0/0 | 0/0 | 0/0 |
| COS_Cream:SG_EC | 299/299 | 299/299 | 0/0 | 0/0 | 0/0 |
| COS_Cream:SG_Store | 416/416 | 416/416 | 0/0 | 0/0 | 0/0 |
| COS_Cream:TH_Distributor | 377/377 | 211/377 | 0/0 | 0/0 | 166/0 |
| COS_Serum:SG_Distributor | 897/825 | 897/825 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/358 | 286/358 | 0/0 | 0/0 | 104/0 |

## 数量配分（① 元の需要 ＝ ② 供給の対象 ＋ ③ 未配分、② ＝ 当週 ＋ 早出し ＋ 遅配 ＋ ⑤ 配分後の未充足）

| 鍵 | ① base/alt | ② base/alt | ③ base/alt | 当週 base/alt | 遅配 base/alt | ⑤ base/alt |
|---|---|---|---|---|---|---|
| COS_Cream:SG_Distributor | 754/754 | 754/588 | 0/166 | 754/588 | 0/0 | 0/0 |
| COS_Cream:SG_EC | 299/299 | 299/299 | 0/0 | 299/299 | 0/0 | 0/0 |
| COS_Cream:SG_Store | 416/416 | 416/416 | 0/0 | 416/416 | 0/0 | 0/0 |
| COS_Cream:TH_Distributor | 377/377 | 377/377 | 0/0 | 211/377 | 0/0 | 166/0 |
| COS_Serum:SG_Distributor | 897/897 | 897/825 | 0/72 | 897/825 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 455/455 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 546/546 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 390/358 | 0/32 | 286/358 | 0/0 | 104/0 |

（数量配分の結果を渡した案は、金額の実行の出荷と鍵 × 要求週で一致を確認済み）

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,119,737,280 | 1,120,085,280 | 348,000 | 607,601,448 | 607,886,352 | 284,904 |
| full | COS_Cream | 432,037,800 | 432,316,680 | 278,880 | 232,761,996 | 232,995,060 | 233,064 |
| full | COS_Serum | 687,699,480 | 687,768,600 | 69,120 | 374,839,452 | 374,891,292 | 51,840 |
| report | * | 1,118,611,200 | 1,118,959,200 | 348,000 | 606,871,080 | 607,155,984 | 284,904 |
| report | COS_Cream | 431,524,440 | 431,803,320 | 278,880 | 232,432,128 | 232,665,192 | 233,064 |
| report | COS_Serum | 687,086,760 | 687,155,880 | 69,120 | 374,438,952 | 374,490,792 | 51,840 |

PPC（全計画期間）：売上 base 1,119,737,280 / alt 1,120,085,280、試算利益 base 607,601,448 / alt 607,886,352
未評価の明細（連結の法人）：{'early_noalloc': 0, 'A_early': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 21491 / alt 23787、最大 base 255 / alt 255、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 early_noalloc *：納品 3864、最大 28 週、52 週超 0
- 年齢 early_noalloc COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 early_noalloc COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 A_early *：納品 3864、最大 28 週、52 週超 0
- 年齢 A_early COS_Cream：納品 1680、最大 27 週、52 週超 0
- 年齢 A_early COS_Serum：納品 2184、最大 28 週、52 週超 0

## 差の出た週

- supply_by_request_week first：2028-W20（4）
- supply_by_request_week max：2029-W26（24）
- profit_r2_by_week first：2028-W17（1,440）
- profit_r2_by_week max：2028-W45（226,392）

代表の lot：`COS_Cream:SG_Distributor:2028-W20:00004`（supply first request week 2028-W20）、`COS_Cream:SG_Distributor:2029-W26:00004`（supply max request week 2029-W26）、`COS_Cream:SG_Distributor:2028-W45:00004`（profit max week 2028-W45）

## 計画の境界

- 2026-W37（first_week）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W51（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W52（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0

工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）：
- A_early COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- A_early COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- early_noalloc COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- early_noalloc COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）

- TH_cream_channel_fee：P0 base 606,871,080 / alt 607,155,984、ΔP0 284,904（COS_Cream: 233,064; COS_Serum: 51,840）、W base 130 / alt 130、ΔW 0 → 順位変化なし（発生週数が同じ）（評価済み）

