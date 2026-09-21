# Request Letter：apparel-us-2026 の `planning_config.csv` を正式化し golden を更新

**起票日**：2026-08-30
**起票者**：大杉
**種別**：サンプルデータ追加 ＋ golden 更新（**エンジンコードは無変更**）
**対象ブランチ**：`wom-v1r3m0`
**先行**：`requests/approval_mode4_fix.md` §2.2 で「別件」として除外した項目

---

## 0. 背景

`data/sample/apparel-us-2026/planning_config.csv` が**未追跡（untracked）のまま**残っており、
golden JSON はこのファイルが存在しない前提で生成されている。
そのため `pytest tests/` で apparel-us-2026 が1件失敗し続けている
（Mode4 修正の commit `44e67bf` 時点で 180 passed / 1 failed）。

**原因は planning period drift。** Code 君の調査で、`push_pull.py` を HEAD に戻しても
同じ失敗が再現することが確認済み。Mode4 修正とは無関係。

### 0.1 ファイルの内容

```
key,value
warmup_lt,52
planning_start,
```

### 0.2 このファイルが必要な理由

**① モデルを正しく動かすために必要**

2026-08-20 の検証で、apparel-us-2026 の実効オフセットは
`sc_tree_master.csv` の `lt_wks` 合計（約20週）より大きく、
`sku_master.csv` の `lead_time_wks`（12〜14週）が加算されるため、
**S1 には 40週以上の warm-up が必要**であることが判明している
（CLAUDE.md「apparel-us-2026：warm-up 未整備と GUI Planning Config の配線」節に記録済み）。

`warmup_lt=52` が無いと **S1〜S3 に起動ランプ由来の CO が全期間にわたって発生する。**
すなわちこのファイルは実験の残骸ではなく、**このモデルの正しい設定**である。

**② headless での全スイープがこの前提で取られている**

2026-08-27 以降に実施した全てのスイープ
（`apparel_s1.yaml` / `apparel_s1_pushlt.yaml` / `apparel_s1_horizon.yaml` /
`apparel_s1_holiday_lt8.yaml` / `apparel_s1_lt3.yaml`）は、
このファイルが存在する状態で実行されている。

headless では `warmup_lt` が正しく効くことも確認済み
（`warmup_confirmed_in_period=true`、`effective_start=2025-W02`）。

**このファイルを削除すると、蓄積した観測値が全て比較不能になる。**

---

## 1. 実施してほしいこと

### 1.1 ファイルの追跡開始

`data/sample/apparel-us-2026/planning_config.csv` を `git add` する。

### 1.2 golden の再生成

apparel-us-2026 の golden JSON を、このファイルが存在する状態で再生成する。

**再生成の前に、以下を確認して報告すること。**

- 再生成後の `period.start` と `n_weeks`
- **全ノードで CO がゼロになっているか**（`warmup_lt=52` が正しく効いていれば、
  S1〜S8 の全シーズンで起動ランプ由来の CO は出ないはず）
- CO が残るノード・SKU があれば、それを列挙すること

**CO が残る場合は、golden を更新せず報告すること。** その状態を正として固定すべきではない。

### 1.3 テスト全体の確認

`pytest tests/` を再実行し、**全件緑**になることを確認する。

前回は 180 passed / 1 failed だったので、**181 passed / 0 failed** になるはず。

### 1.4 コミット前の確認

**commit する前に `git diff --cached --stat` を提示すること。**

確認したいのは以下。

- `data/sample/apparel-us-2026/planning_config.csv`（新規）
- `tests/golden/apparel-us-2026.json`（更新）
- **上記2件のみ**であること。他のファイルが混ざっていないこと

`wom/` 配下のコードが含まれていたら異常。報告して止めること。

### 1.5 コミットメッセージ

```
fix(sample): track apparel-us-2026 planning_config.csv and regenerate golden

The file was left untracked since the 2026-08-20 warm-up investigation,
so the golden JSON was generated without it and the planning period drifted.
This is not a leftover from an experiment: apparel-us-2026 needs
warmup_lt=52 because the effective offset exceeds the sum of lt_wks in
sc_tree_master.csv -- sku_master.csv's lead_time_wks (12-14 weeks) is added
on top, so S1 requires 40+ weeks of warm-up. Without it, S1 through S3
carry startup-ramp CO across the whole horizon.

All headless sweeps from 2026-08-27 onward were run with this file present,
so removing it would make the accumulated observations incomparable.
```

### 1.6 コミット後

- `git status` で `data/sample/` に他の変更が無いことを確認して報告
- `Get-Process python` で孤立プロセスが無いことを確認
- **push はしないこと。** オーナーが手元で実施する

---

## 2. 本件に含めないこと

以下は範囲外。触らないこと。

| 項目 | 扱い |
|---|---|
| `mom_ref_node_id` が Mode4 で無視される | 別件 |
| `push_eol_week` が CSV から読まれていない | 別件 |
| `plan_mode` 既定値（`pull`）の是非 | 別件 |
| A1（multi-leaf_in × 需要段差の擬似 CO） | 別件 |
| smartx-2027-2029 の `holiday_calendar.csv` 文字化け | 別件 |
| `push_lead_time_weeks >= τ` の lint 項目化 | 別件 |
| `push_config_STOP.csv` / `sc_tree_master_scenario1.csv` などの実験残骸 | 別件（オーナーが整理する） |

---

## 3. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- golden テストは `planning_config.csv` を持つモデルに対して実ファイルへ warm-up 行を
  書き込む。実行後は必ず `git status -- data/sample/` を確認すること
- **`capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと**
  （WOM 起動時の自動追記であり、仕様。commit 対象外）
