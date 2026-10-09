# Request Letter — Rice：精米の前倒しを 1 週まで許す（追加の依頼）

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-09
- 元の依頼：`requests/RequestLetter_RiceSeasonal_Implementation_to_CodeKun.md`（§8.1-5 を書き換えた）
- 前提：Code君の報告 `docs/development/WOM_RiceSeasonal_Implementation_Report.md` §9.2-3。作業ツリーは未コミットのまま、その上で続ける。

## 1. 決定

精米の前倒しを **0 週 → 1 週まで** に変える（Owner の決定、2026-10-09）。
理由：GW・お盆・年末年始の休業の前後で、複数の要求週が同じ開いている精米週に集まり、共用の精米センターの上限に当たる（不足 22 lot、市場への配分の偏り）。休業の前に精米しておくのは実務でも普通。
前倒しは 5 段の解法の 4 段目で最小にしているので、使うのは必要な週だけのはず。ほかの値（§8.1・§8.2）は変えない。

### 1.1 解く順番（2026-10-09、Code君の確認への回答）

今の順番のまま（割当数 → 要求週の早い順 → 週内の比例 → 精米の前倒し → 玄米 kg 週）。比例配分（決定 2）を優先し、前倒しは 1 週の範囲で使ってよい。
報告書に残すもの：0 週と 1 週の比較、前倒しの量（約 19,400 lot、精米後の在庫 6,591 → 31,623 lot・週）、順番を変えた場合の参考値（前倒しを 2 段目にすると 4,913 lot・週、比例のずれ 2,992 → 7,542 lot）。

## 2. 作業

1. `tools/gen_rice_seasonal_migration.py` の `max_polish_advance_weeks` を `1` にし、note を「精米の前倒し 1 週まで（§8.1-5、2026-10-09 変更）」にする。移行用コピーを作り直す。CSV を手で直さない。
2. 照合を作り直す：`tools.rice_seasonal_check`（付表 `docs/development/rice_seasonal/` 一式、`shortage_decomposition.json` を含む）、`tools.rice_seasonal_lovem_check`、`tools.lovem_interval_check`、`tools.gui_generation_line_check`（GUI と headless の一致）。
3. 値を固定しているテスト（`tests/test_rice_seasonal_layer.py`）を新しい結果に合わせる。**変える前と後の値を報告に並べる。** 手計算の 1 ID（scenario.json）は変えない（試作の検算用の方針のまま）。
4. 報告書 §0・§5・§9.2・§10 の数字と、CLAUDE.md の Rice の節の数字を直す。Start Here は Claude君が直すので触らない。
5. **報告の開始週を一か所にする（Owner の実機確認で見つかった）。** 移行用コピーの World Map の帯は「報告の開始週 2026-W01（最初の非ゼロ需要週）」と出る。WOM の報告の開始週は `vc_config.csv` の `report_start`（`wom/worldmap_ne/flows.py` の `report_start_index`、Value Chain も同じ）で、Rice は `rice_seasonal_config.csv` に別に持っているため。同じ意味の値を二か所に置かない。`vc_config.csv` の `report_start` を正典にして、Rice の層もそれを読むか、二つが違えば止める。`vc_config.csv` を置くとほかの `vc_*` が要るなど副作用があれば、案を報告してから進める。World Map の帯が 2027-W01（vc_config.csv）になること。
6. **Flow Check の表 2 で助走と報告期間を分けて見せる。** Owner は実機で注文残 80,741 は確かめられたが、内訳（助走 52,163＋報告 28,578）は画面で判別できず、コンソールの警告の行でしか分からない。報告の開始週があるモデルでは、表 2 の当週出荷・期末注文残に「うち報告期間」を足す（列を足すか、行を分ける。見やすい方）。報告の開始週が無いモデルの表は今のまま。

## 3. 報告してほしいこと

| 項目 | 内容 |
|---|---|
| 結果の比較 | 当週出荷・注文残（助走／報告期間、品目別）・遅配・早出しを 0 週と 1 週で並べる |
| 精米による不足 | 22 lot が何 lot になったか。残るなら理由 |
| 前倒しの使われ方 | 前倒しした lot 数と週（休業の前後だけか）。精米後に DC・市場で待つ在庫（lot・週）が増えた分 |
| 市場の早出し | 0 のままであること（前倒しで市場に早く着いても、出荷は要求週） |
| 照合 | flow identity の誤り 0、資源の超過 0、LOVEM の区間と actual_ship の一致 |
| 画面 | World Map の帯の報告の開始週、Flow Check の表 2 の「うち報告期間」。§10 の手順に足す |
| テスト | Rice のテスト、Flow Check・World Map の関係するテスト、`tests/test_lovem_interval_check.py`、`tests/test_golden.py`（plugin OFF なので不変のはず） |

commit・push はしない。終わったら報告書 §10 の期待値も新しい値にして、大杉さんの実機確認に渡す。
