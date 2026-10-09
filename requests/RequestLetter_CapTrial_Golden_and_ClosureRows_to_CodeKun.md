# Request Letter：cap_trial の golden 再生成と、休業の意図で入っていた小数値45行を supply_closure に戻す

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（**`wom-v1r5m0` のフォルダでは作業しない**）
- ブランチ：`wom-v1r5m1_cap_trial`（remote：`composite_node`）
- 基準：commit A（Explicit Closure 実装の基準 commit。大杉さんが commit・push 済み）
- 前提資料：
  - `docs/development/WOM_ExplicitClosure_v1r5m0_Report.md`（前回の実装報告）
  - `requests/RequestLetter_ExplicitClosure_v1r5m0_to_CodeKun.md`（前回の依頼書。D1〜D7・E1〜E4 は引き続き有効）

---

## 0. 進め方

作業は2つあり、**それぞれの後で大杉さんが commit します**。作業1の golden と作業2の変更を、同じ commit に混ぜないためです。

1. 作業1を実施して報告 → 大杉さんが commit B
2. 大杉さんの「作業2に進んで」を受けて作業2を実施し報告 → 大杉さんが確認 → commit C（golden の再生成が必要なら、それは確認後に別の commit）

commit・push は行わないでください。副作用が出ても実装は止めず、最後まで行って報告してください（前回の依頼書 §8 と同じ）。

## 1. 作業1：golden の再生成（前回の意図した変更の確定）

大杉さんは、前回の報告書 §6 の SE1・SE2・SE5 を `python -m main` で実機確認済みです。前回の §6.2 の変更を正として golden を確定します。

- 再生成するのは、前回変わった4モデルだけ：`Cookie-jp-2026`、`ev-europe-2026`、`ev-thailand-2026`、`smartx-2027-2029`
- 再生成の手順は、`tests/test_golden.py` などに書かれている既存の手順に従う。手順が見つからなければ、使った方法を報告に書く。
- 他の9モデルの golden は再生成しない。再生成前に一致していることを、全テストで確認する。

**受入条件**：全テストが緑（前回の 539 passed / 3 skipped / 5 failed のうち、失敗5件が解消される）。

**報告**：再生成したファイル名、テスト件数、golden の差分の要約（4モデルのどのフィールドが変わったか）。

## 2. 作業2：休業の意図で入っていた小数値の行を supply_closure に戻す

### 2.1 業務判断（大杉さん 2026-09-28）

- rice の 0.3 などの小数値は、以前のエンジンで「cap=0 が無制限になる」ことを避けるために、便宜的に入れた値だった。業務上の意図は休業である。
- oil の 1.0 と ev-thailand-2026_update の 5 も、同じく `effect=supply_closure, value=0` に設定する。副作用の有無を見てから扱いを決める。

value だけを 0 にすると `partial_capacity` の「能力0＝未設定」になってしまうので、**effect と value を一組で**変更してください。

### 2.2 対象行（45行）

| ファイル | 行 | 現在 | 変更後 |
|---|---|---|---|
| `data/sample/rice-japan-2027-2028/holiday_calendar.csv` | GW・OBON・NEWYEAR の全16行（DC_Higashi、DC_Nishi、Seihaku_E、Seihaku_W） | partial_capacity, 0.2〜0.5 | supply_closure, 0 |
| `data/sample/rice-japan-2027-2028_BK260613_1515/holiday_calendar.csv` | 同じ16行 | 同上 | 同上（`.gitignore` の対象なので diff には出ない） |
| `data/sample/smartphone-global-2026-2029/holiday_calendar.csv` | DIWALI_2027〜2029（Sensor_A_IN）3行 | partial_capacity, 0.5 | supply_closure, 0 |
| `data/sample/smartx-2027-2029/holiday_calendar.csv` | DIWALI_2026〜2030（SensorIN）5行 | partial_capacity, 0.5 | supply_closure, 0 |
| `data/sample/holiday_calendar.csv`（旧 root sample） | GW_2027・GW_2028（DAD_Japan）2行 | partial_capacity, 0.3 | supply_closure, 0 |
| `data/sample/oil-global-2027/holiday_calendar.csv` | Hormuz_Strait_Closure_2027（Refinery_Local_H）1行 | partial_capacity, 1.0 | supply_closure, 0 |
| `data/sample/ev-thailand-2026_update/holiday_calendar.csv` | GOLDEN_WEEK_2026・2027（Factory_Import_CN）2行 | partial_capacity, 5 | supply_closure, 0 |

**変更しない**：`partial_capacity` のまま残る16行（apparel-global 4、apparel-us 4、ev-thailand-2026_update の RAYONG 2（150）、oil の残り6行（30・25・45・500・500・1000））。

書き換えは前回の `migrate_holiday.py` と同じく、effect と value の欄だけを置き換え、改行・BOM・他の行は保持してください。

### 2.3 見込み（予測。確認は実測で）

GPT-6 Astra君の Trial-02 §5.1 では、rice・smartphone・smartx の上記の行は、休業週に活動がありませんでした。そのため PSI は変わらない見込みです。変わる可能性が高いのは次の2つです。

- **ev-thailand-2026_update の Factory_Import_CN（mom / push）**：これまで cap 5 だった週の実出荷が 0 になり、前回の ev-thailand の SE2 と同じ型の動き（休業前の出荷不足と、休業後の在庫の積み上がり）が出る可能性がある。
- **oil の Refinery_Local_H（mom / pull、60週）**：Backward の充填目標が 0 になる。

また、rice の DC・精白は pull の DAD ノードです。休業週に P が届けば、これまで実モデルで一度も発火していない E2（`closure_p_deferred`）が初めて発火します。発火したかどうかを必ず報告してください。

### 2.4 受入条件と報告

- 前回と同じ `probe_closure.py`／`compare.py` で、変更前（commit B）と変更後を、13 golden モデル＋ev-thailand-2026_update＋rice の BK について比較する。
- 変わったモデルは、前回の報告書 §4 と同じ形の差分表にする。変わらなかったモデルは「一致」と書く。
- 診断件数（`closure_p_deferred`・`closure_p_unplaced`・`closure_s_planned`・`mode4_closure_shifted`）をモデルごとに出す。
- 副作用は、前回の依頼書 §6.4 の形式（どこで／何が／なぜ（推定）／実機での見方／期待との差）で出す。
- PPC の売上・粗利の前後を出す。
- **golden は再生成しない**。大杉さんが差分を確認してから、別の依頼で行う。
- 報告書は `docs/development/WOM_CapTrial_ClosureRows_Report.md` に置く。
