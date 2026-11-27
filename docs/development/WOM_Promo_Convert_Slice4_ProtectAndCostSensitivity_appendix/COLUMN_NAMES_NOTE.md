# 列名の注記（2026-11-27、投入週の 2 本目の補い）

この付録の比較の道具の出力（`compare_*/protect_check.csv`・`protect_need.csv`）は、列名を直す前のものです。値は変わりません。

| この付録の列名（古い） | 今の列名 |
|---|---|
| `promo_increment_net` | `demand_increment_net` |
| `promo_weeks_raised` | `demand_weeks_raised` |
| `promo_weeks_full_on_time` | `demand_weeks_full_on_time` |
| `promo_increment_delivered` | `demand_increment_delivered` |

- 投入週でも使うため、販促に限らない需要の増分の名前にしました（`requests/RequestLetter_Launch_Convert_Slice2b_ProtectFix_to_CodeKun.md`）。
- 今の道具は、守る供給の表に任意の列 `floor_case` があるときだけ引く増分が変わります。この付録の表には無いので、結果は今の道具でも同じです。
- `scripts/exec_table.py` は新しい列名を読むように直しました。この付録の CSV（古い列名）を読み直すときは、列名を読み替えてください。
