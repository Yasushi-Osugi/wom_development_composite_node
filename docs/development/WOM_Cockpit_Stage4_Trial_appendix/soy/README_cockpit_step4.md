# 段 4 の試し：醤油の写し（soy_model）

`data/sample/soysauce-jpy-2027-alloc` の写し（2026-11-17、RequestLetter_Cockpit_Stage4_Trial A0）。正式なサンプルは変えていない。

## 変えた所

| ファイル | 変えたこと | 理由 |
|---|---|---|
| `vc_config.csv` | `report_start` を空欄 → `2027-W01` | 経営コックピットの作業は、報告の開始週が無いと止まる（黙った既定値を作らない） |
| `capacity_plan.csv` | 列 `cap_soft` を足した。`Bottling_Noda` の全行（助走を含む）を `max_supply=1000`・`cap_soft=800`、`Brewing_Noda` の全行を `max_supply=1000`・`cap_soft` 空欄。`Materials_JP` は今のまま | 瓶詰（`demand_envelope=soft`）を計画の生産量 800 で平準化させ、その値を案ごとに変えて比べるため（判断票の冒頭の欄）。醸造は設備の上限 1,000 だけにして律速にしない |

## 試した結果、意図どおりには動かなかった（報告書 §2）

`operating_calendar.csv`（変えていない）が `Bottling_Noda` に 18 直（2028-W33 だけ 0 直）を与えている。計画の読み込みは、直の数が 0 より大きい週の `cap_soft` を `round(直の数 × max_supply ÷ 21)` で**上書きする**（`wom/engine/capacity_sealer.load_operating_calendar`）。

- この写し：`round(18 × 1000 ÷ 21)` ＝ **857**。`cap_soft` に 800 と書いても 900 と書いても、計画は 857 で平準化する（2 案は同じ結果）
- 正式なサンプル：`round(18 × 800 ÷ 21)` ＝ **686**（設備の上限 800 ではなく、686 で平準化していた）
