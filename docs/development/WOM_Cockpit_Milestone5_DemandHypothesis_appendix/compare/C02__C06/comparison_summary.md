# 2 案の比較（C02 → C06）

- base（C02）：実行 `output/cockpit_m5/cos\C02\run`、モデル `output/cockpit_m5/cos\C02\model`
- alt（C06）：実行 `output/cockpit_m5/cos\C06\run`、モデル `output/cockpit_m5/cos\C06\model`
- 計画の週：2026-W37〜2029-W52（173 週）

## 入力の表の違い

- COS_Cream:TH_Distributor `ramp_ratio`：0.5 → 1.0
- COS_Cream:TH_Distributor `basis_note`：docs/scenarios/cosmetics.md Demand assumptions → 発売直後の需要が想定より強い場合（立ち上がりの倍率 0.5→1.0）。到達点 5 の試行の仮説

## 需要（lot、全計画期間）

| 鍵 | base | alt | 差 |
|---|---:|---:|---:|
| COS_Cream:SG_Distributor | 754 | 754 | +0 |
| COS_Cream:SG_EC | 299 | 299 | +0 |
| COS_Cream:SG_Store | 416 | 416 | +0 |
| COS_Cream:TH_Distributor | 299 | 312 | +13 |
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
| COS_Cream:TH_Distributor | 299/312 | 299/312 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Distributor | 897/897 | 897/897 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 286/286 | 0/0 | 0/0 | 104/104 |

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,134,943,680 | 1,137,190,080 | 2,246,400 | 617,591,208 | 619,066,968 | 1,475,760 |
| full | COS_Cream | 447,244,200 | 449,490,600 | 2,246,400 | 242,751,756 | 244,227,516 | 1,475,760 |
| full | COS_Serum | 687,699,480 | 687,699,480 | 0 | 374,839,452 | 374,839,452 | 0 |
| report | * | 1,133,817,600 | 1,136,064,000 | 2,246,400 | 616,860,840 | 618,336,600 | 1,475,760 |
| report | COS_Cream | 446,730,840 | 448,977,240 | 2,246,400 | 242,421,888 | 243,897,648 | 1,475,760 |
| report | COS_Serum | 687,086,760 | 687,086,760 | 0 | 374,438,952 | 374,438,952 | 0 |

PPC（全計画期間）：売上 base 1,134,943,680 / alt 1,137,190,080、試算利益 base 617,591,208 / alt 619,066,968
未評価の明細（連結の法人）：{'C02': 0, 'C06': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 26989 / alt 27873、最大 base 246 / alt 259、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 C02 *：納品 3952、最大 28 週、52 週超 0
- 年齢 C02 COS_Cream：納品 1768、最大 24 週、52 週超 0
- 年齢 C02 COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 C06 *：納品 3965、最大 28 週、52 週超 0
- 年齢 C06 COS_Cream：納品 1781、最大 25 週、52 週超 0
- 年齢 C06 COS_Serum：納品 2184、最大 28 週、52 週超 0

## 差の出た週

- supply_by_request_week first：2028-W01（2）
- supply_by_request_week max：2028-W01（2）
- profit_r2_by_week first：2027-W50（720）
- profit_r2_by_week max：2028-W11（114,240）

代表の lot：`COS_Cream:TH_Distributor:2028-W01:00003`（supply first request week 2028-W01）、`COS_Cream:TH_Distributor:2028-W11:00003`（profit max week 2028-W11）

## 計画の境界

- 2026-W37（first_week）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W51（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W52（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0

工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）：
- C02 COS_Cream：2026-W37, 2026-W38, 2026-W39, 2026-W40, 2026-W41, 2026-W42, 2026-W43, 2026-W44, 2026-W45, 2029-W47, 2029-W48, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 135 lot）
- C02 COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- C06 COS_Cream：2026-W37, 2026-W38, 2026-W39, 2026-W40, 2026-W41, 2026-W42, 2026-W43, 2029-W47, 2029-W48, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 122 lot）
- C06 COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）

- planned_output_raise：P0 base 616,860,840 / alt 618,336,600、ΔP0 1,475,760（COS_Cream: 1,475,760; COS_Serum: 0）、W base 173 / alt 173、ΔW 0 → 順位変化なし（発生週数が同じ）（評価済み）

## 計画の生産量ちょうど作った週（有償の週の確かめ用。道具は有償の週を決めない）

- C02 COS_Cream（Factory_JP、上限 11）：最初 2026-W46・最後 2029-W46・その間 158 週（報告期間 150・外 8）、ちょうど作った週 158（報告期間 150）、下回った週 15
- C02 COS_Serum（Factory_JP、上限 13）：最初 2026-W38・最後 2029-W48・その間 168 週（報告期間 152・外 16）、ちょうど作った週 168（報告期間 152）、下回った週 5
- C06 COS_Cream（Factory_JP、上限 11）：最初 2026-W44・最後 2029-W46・その間 160 週（報告期間 150・外 10）、ちょうど作った週 160（報告期間 150）、下回った週 13
- C06 COS_Serum（Factory_JP、上限 13）：最初 2026-W38・最後 2029-W48・その間 168 週（報告期間 152・外 16）、ちょうど作った週 168（報告期間 152）、下回った週 5

