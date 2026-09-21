# 承認通知：Mode4 二重計上バグ修正の差分レビュー完了

**発行日**：2026-08-30
**発行者**：大杉（オーナー）
**対象**：`requests/request_fix_mode4_double_count.md`
**種別**：**禁足コア変更の承認とコミット指示**

---

## 1. 差分を承認します

`requests/request_fix_mode4_double_count.md` §0 の承認条件を、以下により満たしたと判断します。

- [x] Request Letter 起票
- [x] 3層テスト（Unit / Integration / golden）実施と報告
- [x] **オーナーによる差分レビュー — 本書をもって承認**
- [x] golden 差分が「正しくなった結果」であることの確認

### 1.1 承認の根拠

**① 修正の範囲が適切**

`push_pull.py` の `is_lt_shifted_mode()` 分岐に25行の追加のみ。対象は `leaf_in_nodes`
（Mode4 がこれから書き込む leaf_in）に限定され、Mode1〜3・他ノードには一切触れていない。
`mode_only` の早期 return より後、ループより前という配置も妥当。

**② §3 の突合と golden 差分が完全に符合**

| 状況 | 該当ケース | 結果 |
|---|---|---|
| `τ = LT`（一致） | apparel-global-2028-2029（Offshore / Vertical の2製品） | **無変化** ✓ |
| `τ ≠ LT`（不一致） | ev-europe-2026 / ev-thailand-2026 / smartx-2027-2029 / soysauce-eu・jpy・us-2027 | **変化** ✓ |
| Mode4 不使用 | Cookie-jp-2026 / iphone_global / oil-global-2027 / rice-japan-2027-2028 | **無変化** ✓ |

判定表の「異常（過剰修正）」枠に該当なし。

**③ GUI での目視確認（オーナー実施、2026-08-30）**

`soysauce-jpy-2027` を、修正前（`wom-v1r3m0`）と修正後（`wom-v1r3m0_DEMO`）の
両環境で同時に起動し、`FG_WH_Noda` の PSI Chart を並べて比較した。

| | 修正前 | 修正後 |
|---|---|---|
| PSI Chart 凡例 | P / S / **CO** / I | **P / S / I**（CO の系列が消滅） |
| 末尾の CO バー | 赤で表示 | **なし** |
| 在庫のピーク | 約 1,200 | **約 1,000** |
| 末尾の挙動 | 急落後に CO 発生 | 滑らかに消化して着地 |

**CO が「減った」のではなく、系列そのものが発生しなくなった。**
また在庫のピークが 1,200 → 1,000 に下がったことから、
二重計上分が「幻の在庫」として積み上がっていたことが目視でも確認できた。
これは Code 君の報告（`P 102,087 → 100,501`）と整合する。

**④ 新たに判明した制約の扱いが適切**

`LT < τ`（今回は LT=2 < τ=3）で修正後も CO が残る件について、
「これは二重計上バグではなく、`LT < τ` という設定自体が物理的に不可能な計画である」
という判断は正しい。これを隠さず報告し、境界を明示するテスト
（`test_mode4_lt_below_tau_shows_genuine_shortage`）を追加した対応も適切。

**この制約は別途、静的 lint の項目として起票する。**

---

## 2. 実施してほしいこと

### 2.1 golden JSON の更新（6ケース）

以下の6ケースのみ更新すること。

```
ev-europe-2026
ev-thailand-2026
smartx-2027-2029
soysauce-eu-2027
soysauce-jpy-2027
soysauce-us-2027
```

### 2.2 apparel-us-2026 の golden は更新しないこと【重要】

apparel-us-2026 の golden 失敗は、**本修正とは無関係**であることが
Code 君自身の調査（`push_pull.py` を HEAD に戻しても同じ失敗が再現）で確認済み。

原因は未 commit の `data/sample/apparel-us-2026/planning_config.csv` であり、
golden JSON 生成時にこのファイルが存在しなかったための計画期間のズレ。

**別件として扱う。本 commit には含めないこと。**

### 2.3 テスト再実行

`pytest tests/` を再実行し、**apparel-us-2026 以外が全て緑**になることを確認すること。

### 2.4 コミット対象

以下の3種を漏れなく含めること。

| 対象 | 現状 |
|---|---|
| `wom/engine/push_pull.py` | modified |
| `tests/test_push_pull_mode4_double_count.py` | **untracked。add を忘れないこと** |
| golden JSON 6件 | 更新後 |

**`git commit -am` は使わないこと**（untracked のテストファイルが漏れる）。
明示的に `git add` すること。

### 2.5 コミット前の確認

**commit する前に `git diff --cached --stat` を提示すること。**

確認したいのは以下。

- golden JSON が **6件ちょうど**であること（7件以上なら取り違え）
- `data/sample/` のファイルが含まれていないこと
- `tests/test_push_pull_mode4_double_count.py` が含まれていること

### 2.6 コミットメッセージ

```
fix(push_pull): clear leaf_in P before Mode4 LT-shift to stop double counting

Mode4 wrote only the weeks it touched, leaving copy_demand_to_supply's
natural copy in the untouched weeks. When push_lead_time_weeks != the
leaf_in's own tau (lt_wks + ss_wks), the two week sets differ and the same
lots were counted twice.

Effect before fix (apparel-us-2026 / Apparel_Outsourced_S1, tau=3):
  LT=3 (== tau)  P_sum 23,884  CO 0        <- accidental no-op
  LT=4           P_sum 26,184  CO 32,650
  LT=8           P_sum 46,868  CO 303,050

Fix: clear psi4supply[w][P] on the target leaf_in nodes for all weeks
before Mode4 writes. Scope is limited to leaf_in_nodes; Mode1-3 unchanged.

Golden updated for 6 cases where LT != tau (ev-europe-2026,
ev-thailand-2026, smartx-2027-2029, soysauce-eu/jpy/us-2027).
soysauce-jpy-2027 phantom CO disappears entirely (FG_WH_Noda 6,385 -> 0).
apparel-global-2028-2029 (LT == tau) is unchanged, as predicted.

Verified in the GUI: the CO series disappears from FG_WH_Noda entirely
(legend goes from P/S/CO/I to P/S/I) and the inventory peak drops from
about 1,200 to 1,000 -- the double-counted lots were showing up as
phantom inventory.

Known constraint discovered: push_lead_time_weeks must be >= the leaf_in's
tau. LT < tau is physically infeasible and correctly produces CO.
```

### 2.7 コミット後

- `git status` で `data/sample/` が clean であることを確認して報告すること
- `Get-Process python` で孤立プロセスが無いことを確認すること
- **push はしないこと。** オーナーが手元で実施する

---

## 3. 本 commit に含めないこと（別途起票）

以下は本件の範囲外。**触らないこと。**

| 項目 | 扱い |
|---|---|
| apparel-us-2026 の `planning_config.csv` と golden のズレ | 別件として起票 |
| `mom_ref_node_id` が Mode4 で無視される（docstring との不整合） | 別件 |
| `push_eol_week` が GUI 本番／headless で CSV から読まれていない | 別件 |
| `plan_mode` 既定値（`pull`）の是非 | 別件（S1 調査済み） |
| A1（multi-leaf_in × 需要段差の擬似 CO） | 別件（未解決） |
| smartx-2027-2029 の `holiday_calendar.csv` の文字化け | 別件 |
| `push_lead_time_weeks >= τ` の lint 項目化 | 別件 |

---

## 4. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- golden テストは `planning_config.csv` を持つモデルに対して実ファイルへ warm-up 行を
  書き込む（sweep_flags.py のようなガードが無い）。実行後は必ず
  `git status -- data/sample/` を確認すること

---

## 5. 記録

本件は、以下の一連の調査を経て原因が確定したものである。次に読む者のために経緯を残す。

```
2026-08-27  S1 調査   PUSH/PULL 既定判定ロジックの把握
            S2 調査   InBound decoupling で CO が単調増加する機構の特定
            sweep     tools/sweep_flags.py を実装、4条件を比較
2026-08-30  sweep     push_lead_time_weeks を 1/2/4/8 で振る → 非単調と判明
            sweep     warmup_lt を 52/78/104 → horizon 端の欠落仮説を棄却
            sweep     holiday_calendar の有無 → 閉鎖との衝突仮説を棄却
            調査      Mode4 が「触った週だけ上書き」する加算的処理と判明
            sweep     LT=3（= τ）で P_sum が base に戻る → 仮説成立
            修正      本件
```

**棄却された仮説も記録に値する。** 同じ道を再度歩まないために。
