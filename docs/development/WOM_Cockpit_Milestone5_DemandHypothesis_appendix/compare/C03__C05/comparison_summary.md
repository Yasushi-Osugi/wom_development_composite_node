# 2 案の比較（C03 → C05）

- base（C03）：実行 `output/cockpit_m5/cos\C03\run`、モデル `output/cockpit_m5/cos\C03\model`
- alt（C05）：実行 `output/cockpit_m5/cos\C05\run`、モデル `output/cockpit_m5/cos\C05\model`
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
| COS_Cream:TH_Distributor | 299/312 | 299/299 | 0/0 | 0/0 | 0/13 |
| COS_Serum:SG_Distributor | 897/897 | 897/897 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_EC | 455/455 | 455/455 | 0/0 | 0/0 | 0/0 |
| COS_Serum:SG_Store | 546/546 | 546/546 | 0/0 | 0/0 | 0/0 |
| COS_Serum:TH_Distributor | 390/390 | 286/286 | 0/0 | 0/0 | 104/104 |

## 試算利益（消去後の連結、円。固定費の前）

| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |
|---|---|---:|---:|---:|---:|---:|---:|
| full | * | 1,134,943,680 | 1,134,943,680 | 0 | 617,591,208 | 617,591,208 | 0 |
| full | COS_Cream | 447,244,200 | 447,244,200 | 0 | 242,751,756 | 242,751,756 | 0 |
| full | COS_Serum | 687,699,480 | 687,699,480 | 0 | 374,839,452 | 374,839,452 | 0 |
| report | * | 1,133,817,600 | 1,133,817,600 | 0 | 616,860,840 | 616,860,840 | 0 |
| report | COS_Cream | 446,730,840 | 446,730,840 | 0 | 242,421,888 | 242,421,888 | 0 |
| report | COS_Serum | 687,086,760 | 687,086,760 | 0 | 374,438,952 | 374,438,952 | 0 |

PPC（全計画期間）：売上 base 1,134,943,680 / alt 1,134,943,680、試算利益 base 617,591,208 / alt 617,591,208
未評価の明細（連結の法人）：{'C03': 0, 'C05': 0}

## 在庫と年齢

週末の在庫の合計（lot・週）と期末の在庫：

- COS_Cream：lot・週 base 29754 / alt 28555、最大 base 256 / alt 256、期末 base 5 / alt 5
- COS_Serum：lot・週 base 36569 / alt 36569、最大 base 345 / alt 345、期末 base 7 / alt 7
- 年齢 C03 *：納品 3952、最大 28 週、52 週超 0
- 年齢 C03 COS_Cream：納品 1768、最大 27 週、52 週超 0
- 年齢 C03 COS_Serum：納品 2184、最大 28 週、52 週超 0
- 年齢 C05 *：納品 3952、最大 28 週、52 週超 0
- 年齢 C05 COS_Cream：納品 1768、最大 27 週、52 週超 0
- 年齢 C05 COS_Serum：納品 2184、最大 28 週、52 週超 0

## 差の出た週

- supply_by_request_week first：2028-W01（2）
- supply_by_request_week max：2029-W45（4）
- profit_r2_by_week first：2027-W50（720）
- profit_r2_by_week max：2029-W48（228,480）

代表の lot：`COS_Cream:TH_Distributor:2028-W01:00003`（supply first request week 2028-W01）、`COS_Cream:TH_Distributor:2029-W45:00002`（supply max request week 2029-W45）、`COS_Cream:TH_Distributor:2029-W48:00002`（profit max week 2029-W48）

## 計画の境界

- 2026-W37（first_week）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W51（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0
- 2029-W52（last_2_weeks）：期末の未充足 base 0 / alt 0、供給の差 0、試算利益の差 0

工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）：
- C03 COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- C03 COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）
- C05 COS_Cream：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 50 lot）
- C05 COS_Serum：2026-W37, 2029-W49, 2029-W50, 2029-W51, 2029-W52（未使用 計 65 lot）

## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）

- planned_output_raise：P0 base 616,860,840 / alt 616,860,840、ΔP0 0（COS_Cream: 0; COS_Serum: 0）、W base 88 / alt 88、ΔW 0 → 順位変化なし（発生週数が同じ）。両案同額（評価済み）

## 計画の生産量ちょうど作った週（有償の週の確かめ用。道具は有償の週を決めない）

- C03 COS_Cream（Factory_JP、上限 10,11）：最初 2026-W38・最後 2029-W48・その間 168 週（報告期間 152・外 16）、ちょうど作った週 168（報告期間 152）、下回った週 5
  - うち上限 10 の週（2026-W37〜2029-W52・85 週、報告期間 68・外 17）：ちょうど作った週 80（報告期間 64）、下回った週 5（報告期間 4）
  - うち上限 11 の週（2028-W11〜2029-W46・88 週、報告期間 88・外 0）：ちょうど作った週 88（報告期間 88）、下回った週 0（報告期間 0）
- C03 COS_Serum（Factory_JP、上限 13）：最初 2026-W38・最後 2029-W48・その間 168 週（報告期間 152・外 16）、ちょうど作った週 168（報告期間 152）、下回った週 5
- C05 COS_Cream（Factory_JP、上限 10,11）：最初 2026-W38・最後 2029-W48・その間 168 週（報告期間 152・外 16）、ちょうど作った週 168（報告期間 152）、下回った週 5
  - うち上限 10 の週（2026-W37〜2029-W52・85 週、報告期間 68・外 17）：ちょうど作った週 80（報告期間 64）、下回った週 5（報告期間 4）
  - うち上限 11 の週（2028-W11〜2029-W46・88 週、報告期間 88・外 0）：ちょうど作った週 88（報告期間 88）、下回った週 0（報告期間 0）
- C05 COS_Serum（Factory_JP、上限 13）：最初 2026-W38・最後 2029-W48・その間 168 週（報告期間 152・外 16）、ちょうど作った週 168（報告期間 152）、下回った週 5

