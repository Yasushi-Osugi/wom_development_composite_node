---
handoff:
  case_id: STRATEGY-CONVERT-L2b
  task_id: launch-convert-slice2b-protect-fix
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  acceptance:
    ref: "この依頼書 §3"
  status: "試行可能"
  stop_reasons: []
  next: implement
---

# Request Letter：投入週の 2 本目の補い — 守る供給の判定の二重の差し引きを直す、案の名前を直す

- 宛先：Code君／起草：Claude君（2026-11-27）／版：v0.1
- 範囲：`wom/strategy/compare.py`（守る供給の判定）・`tools/strategy_compare.py`・テスト。エンジン・PPC・Value Chain・正式なサンプル・golden は変えない

## 一言で

2 本目の報告書 §4 のとおり、守る供給の判定は、対象の鍵の需要の増分を、下限にした案の分まで含めて二重に引いていました（タイのクリームが「未達 −78」）。下限にした案の増分を差し引くように直し、誤読を防ぐ名前に直してください（判断票 N4）。

## 1. 直すこと

1. **守る供給の表に任意の列 `floor_case`**（下限の数量を取った案の ID）を足す。対象の鍵では、引く増分を「その案の増分 − `floor_case` の増分」（要求週ごと、変更の記録の週別の `quantity` の行から）にする。`floor_case` が空なら今と同じ（増分を全部引く。販促の試行の表はこのまま同じ結果になる）。
2. 出力の列名 `promo_increment_net`・`promo_weeks_raised`・`promo_weeks_full_on_time`・`promo_increment_delivered` を、需要の増分を表す名前（例 `demand_increment_net` …）に直す（投入週でも使うため）。関連の文書・テスト・付録のスクリプトで、この列名を参照している所をまとめて直す。
3. テスト：`floor_case` が増分を含む案のとき、納品が下限と同じなら「達成」で差 0。空のときは今と同じ。
4. 作業 `output/strategy_launch1/ws` の C07 の名前を `EARLY_RAISE167` に直す（案の名前だけ。計画の結果は変えない）。
5. 2 本目の守る供給（C04 → C06、C05 → C07）を、`floor_case` を入れた表で作り直し、報告書 §4 の「道具の表示について」を、直した結果に差し替える（数字の本文は変わらない見込み）。

## 2. 書き方の注意

販促の試行（1〜4b）の報告書の数字は変えない（`floor_case` が空の経路）。列名の変更は、過去の報告書の本文は直さず、付録の CSV の列名が古いことを注記するだけでよい。

## 3. 合格の条件

| # | 条件 |
|---|---|
| S1 | 2 本目の守る供給が、C06・C07 とも 8／8 で、タイのクリームの差が 0 |
| S2 | `floor_case` が空の経路で、販促の試行のテストが今と同じ結果 |
| S3 | `quick_check --changed` が通る。エンジン・正式なサンプル・golden が変わっていない |

commit メッセージの下書きを 1 つ（`commit_msg247.txt`）。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-27 | 初版 |
