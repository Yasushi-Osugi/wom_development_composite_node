# CapTrial 作業2 報告：休業の意図で入っていた小数値45行を supply_closure に戻す

- 依頼書：`requests/RequestLetter_CapTrial_Golden_and_ClosureRows_to_CodeKun.md`（作業2）
- 実装：Code君（Claude Code, Windows）、2026-09-28
- 作業フォルダ／ブランチ：`wom-v1r5m1_cap_trial`
- 変更前の基準：commit B ＝ `5f898aa`（`test(golden): Explicit Closure で休業が効き始めた4モデルの golden を再生成`、remote と同期済み）
- **commit・push はしていない。golden は再生成していない**（依頼書 §2.4）
- 付属：`docs/development/captrial_closure_rows/`（前後比較の生出力、移行・計測・比較スクリプト）

---

## 0. 要約

1. 45行すべてを `supply_closure, 0` に変えた。effect と value の欄の文字だけを置き換え、残す16行は変えていない。
2. **PSI が変わったのは ev-thailand-2026_update だけ。** 13 の golden モデル、alloc の2条件、rice の BK はすべて「一致」（PSI・forward・backward・PPC）。
3. **PPC の売上・粗利は、全17ケースで前後一致。**
4. **E2（`closure_p_deferred`）は今回も発火しなかった。** rice の DC・精白ノードは、休業週に P も需要も持っていない。
5. 予測との違い：
   - ev-thailand-2026_update では、SE2 型の症状（休業前の出荷不足、休業後の在庫の積み上がり）は**出なかった**。代わりに、休業週の需要が満杯の週を遡って約1年前まで前倒しされた（SE-A）。
   - oil の Refinery_Local_H は、休業期間中に需要が無く、PSI は変わらなかった。
6. テスト：**544 passed / 3 skipped / 0 failed**（golden は据え置きのまま全部通る）。

---

## 1. 変更内容（データのみ。コードの変更なし）

| ファイル | 行 | 変更 |
|---|---:|---|
| `data/sample/rice-japan-2027-2028/holiday_calendar.csv` | 16 | partial_capacity 0.2〜0.5 → supply_closure 0 |
| `data/sample/rice-japan-2027-2028_BK260613_1515/holiday_calendar.csv` | 16 | 同上（`.gitignore` の対象なので diff には出ない） |
| `data/sample/iphone_global/holiday_calendar.csv` | 3 | DIWALI_2027〜2029（BoschSensor_IN）0.5 → supply_closure 0 |
| `data/sample/smartx-2027-2029/holiday_calendar.csv` | 5 | DIWALI_2026〜2030（SensorIN）0.5 → supply_closure 0 |
| `data/sample/holiday_calendar.csv`（旧 root sample） | 2 | GW_2027・GW_2028（DAD_Japan）0.3 → supply_closure 0 |
| `data/sample/oil-global-2027/holiday_calendar.csv` | 1 | Hormuz_Strait_Closure_2027（Refinery_Local_H）1.0 → supply_closure 0 |
| `data/sample/ev-thailand-2026_update/holiday_calendar.csv` | 2 | GOLDEN_WEEK_2026・2027（Factory_Import_CN）5 → supply_closure 0 |
| 計 | **45** | |

- 対象行は、値ではなく `holiday_id`＋`node_name` で指定した。
- 書き換え前に、どの行も `partial_capacity` であることを確認した（`captrial_closure_rows/migrate_closure_rows.py`）。
- `partial_capacity` のまま残る16行には触れていない（apparel-global 4、apparel-us 4、ev-thailand-2026_update の RAYONG 2、oil 6）。
- 旧 root sample は `sc_tree_master.csv` を持たず、headless で実行できないため、比較の対象外。

---

## 2. 前後比較

commit B と変更後のそれぞれで、モデルフォルダの**複写**に対して headless 計画＋PPC を実行した。対象は依頼書の 13 golden モデル＋ev-thailand-2026_update＋rice BK で、参考に soysauce-jpy-2027-alloc（原需要・P_opt/800）も加えた。全ノード・全週の P／S／実出荷／I／CO／Demand S・P、cap、is_open を比べている。全文は `captrial_closure_rows/probe_before_after_diff.txt`。

| モデル | PSI | PPC 売上／粗利（前後同じ） | 変化したもの（PSI 以外） |
|---|---|---|---|
| Cookie-jp-2026 | 一致 | 4,259,700,000／686,229,000 | なし |
| apparel-global-2028-2029 | 一致 | 10,387,986.16／3,994,720.41 | なし |
| apparel-us-2026 | 一致 | 12,209,428.00／5,182,154.67 | なし |
| bom-test-2026 | 一致 | 3,200,000／2,393,000 | なし |
| ev-europe-2026 | 一致 | 366,508,230,000／192,334,774,500 | なし |
| ev-thailand-2026 | 一致 | 319,119,580,000／180,288,676,250 | なし |
| **ev-thailand-2026_update** | **変化**（§3） | 319,119,580,000／180,288,676,250 | strategic_kpi |
| iphone_global | 一致 | 713,310,634,579,400／296,225,445,796,167.4 | BoschSensor_IN の休業週：cap_hard 0.5 → 0、is_open → False。strategic_kpi |
| oil-global-2027 | 一致 | 1,649,727,940,180／579,538,174,893 | Refinery_Local_H の 2027-W15〜2028-W26（64週）：cap_hard 1.0 → 8.0（capacity_plan の値）、is_open → False。strategic_kpi |
| rice-japan-2027-2028 | 一致 | 1,829,200,000／705,096,313 | DC・精白の休業週：cap_hard 0.2〜0.5 → DC は 0（未設定）、精白は capacity_plan の値（900／700／400／300）。is_open → False。strategic_kpi |
| rice-japan-2027-2028_BK260613_1515 | 一致 | 1,829,200,000／705,096,313 | rice と同じ |
| smartx-2027-2029 | 一致 | 702,250,439／634,628,759.84 | SensorIN の休業週：cap_hard 0.5 → capacity_plan の値（995・879・648・367・148）、is_open → False。strategic_kpi |
| soysauce-eu／jpy／us-2027、alloc（2条件） | 一致 | 変化なし | なし |

Backward の past_due 件数は、全ケースで前後同じ。

### 診断件数（前 → 後）

| モデル | closure_p_deferred | closure_p_unplaced | closure_s_planned | mode4_closure_shifted |
|---|---:|---:|---:|---:|
| smartx-2027-2029 | 0 → 0 | 0 → 0 | 0 → 0 | 8 → 8 |
| その他全ケース | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0（Mode 4 の無いモデルは対象外） |

**E2（`closure_p_deferred`）は発火しなかった。** rice の DC_Higashi・DC_Nishi・Seihaku_E・Seihaku_W（dad / pull）は、休業週（GW・OBON・NEWYEAR）の P・S・Demand S がいずれも 0 で、繰り延べる P が無かった。休業週の需要が 0 である理由は調べていない。Trial-02 §5.1 の「活動なし」と同じ観測である。

---

## 3. 差分表：ev-thailand-2026_update

| 行 | node | 休業週の処理（前→後） | 移った先 |
|---|---|---|---|
| GOLDEN_WEEK_2026（2026-W40・W41） | Factory_Import_CN / mom / push | 実出荷 5・5 → **0・0**。入庫 105・105 は受け入れて I へ（I 105・210） | 休業週の需要 10 lot は、cap 105 で満杯の週を遡り、2025-W46 の需要（65 → 76）へ。これに合わせて Components_CN の生産が 2025-W42 に、入庫が 2025-W44 に移る。休業直前の入庫 2026-W38・W39 は 5・5 → 0・0 |
| GOLDEN_WEEK_2027（2027-W40・W41） | 同上 | 実出荷 5・5 → **0・0**。入庫は受け入れて I へ | 需要は 2026-W51・W52（100・101 → 105・105）へ。入庫は 2026-W49・W50。2027-W38・W39 の入庫 5・5 → 0・0 |

- 総量は Factory_Import_CN・Components_CN・SP_EV_Import とも前後同じ（P・S・実出荷 10,540、shortfall 0、CO 0）。leaf_out の S も同じ。
- Factory_Import_CN の I 合計（lot-週）も同じ 21,080。休業後の I は変更前と同じ 210 に戻る。
- SP_EV_Import の I 合計は 12,310 → 13,253（+943 lot-週）。

---

## 4. 副作用（依頼書 §6.4 の形式）

### SE-A　ev-thailand-2026_update：休業週の需要が約1年前まで前倒しされ、supply_point に在庫として滞留する

| 項目 | 内容 |
|---|---|
| どこで | ev-thailand-2026_update / EVmaker_Import。Factory_Import_CN（2025-W44〜W46、2026-W38〜W41、2026-W49〜W52、2027-W38〜W41）、Components_CN、SP_EV_Import（2025-W46〜2027-W41） |
| 何が | 2026 年の休業分のうち 11 lot が 2025-W46 の需要へ移り、Factory の入庫・出荷が 65 → 76 になる。SP_EV_Import の I が 2025-W46〜2026-W41 は +11、2027-W01〜W41 は +10 lot 多い（I 合計 +943 lot-週）。実出荷の総量・不足・CO は変わらない |
| なぜ（推定） | Backward の前倒し（`_apply_mom_cap_backward`）は、溢れた分を1週ずつ前へ送る。2025-W47〜2026-W39 はどの週も需要が cap_hard 105 ちょうどで空きが無いため、空きのある最初の週（2025-W46、需要 65）まで遡った。2027 年の休業分は、空きのある 2026-W51・W52 に入った。前倒しで早く作った lot は、supply_point（pull）で本来の需要週まで待つ |
| 実機での見方 | `python -m main` → `data/sample/ev-thailand-2026_update` → Run Planning Engine → Network → Factory_Import_CN（EVmaker_Import）→ PSI List（Demand）の 2025-W46（S 76）、2026-W40・W41（S —、行は灰色）。SP_EV_Import の PSI List（Supply）の I 列が 2025-W46 以降、変更前より 10〜11 多い |
| 期待との差 | 依頼書 §2.3 は、前回の SE2 と同じ型（休業前の出荷不足、休業後の在庫の積み上がり）を予測していた。実際にはどちらも**出なかった**。Factory_Import_CN は休業前から 210 の在庫を持っており、休業週の入庫もその範囲で吸収された。代わりに、少量（計約20 lot）が長期間（約1年）前倒しされるという別の形の変化が出た |

### SE-B　休業週の CapHard 表示と strategic_kpi が変わる（PSI は不変）

| 項目 | 内容 |
|---|---|
| どこで | rice（DC_Higashi・DC_Nishi・Seihaku_E・Seihaku_W）、iphone（BoschSensor_IN）、smartx（SensorIN）、oil（Refinery_Local_H）の休業週 |
| 何が | cap_hard が、holiday の小数値から capacity_plan の値に戻る。capacity_plan に行が無いノード（rice の DC、iphone の BoschSensor_IN）は 0（未設定）になる。PSI List の CapHard 列は「0.3」などから「—」または設備能力の値に変わり、CapSoft 列は「0」、行は灰色（休業）になる。strategic_kpi：rice は n_constrained_nodes 10 → 6、avg_cap_utilization 0.4021 → 0.4266。iphone は 4 → 3、0.8849 → 0.8917。oil は avg_cap_utilization 0.3973 → 0.4188。smartx は 0.4938 → 0.4954。ev-thailand-2026_update は 0.3741 → 0.3687 |
| なぜ（推定） | E1（休業は週の状態であり、能力値を書き換えない）の直接の結果。以前は小数の cap_hard（P／0.3 など）が稼働率の集計に入っていたが、休業週は `processing_limit` で集計から外れる |
| 実機での見方 | rice-japan-2027-2028 → Network → DC_Higashi（Koshihikari）→ PSI List の 2027-W18・W19：CapHard「—」、CapSoft「0」、行が灰色。Seihaku_E の同じ週は CapHard「900」 |
| 期待との差 | PSI 不変という予測（§2.3）どおり。表示と KPI の変化は、予測に書かれていなかったので報告する |

### SE-C　予測した変化が出なかったもの

| 項目 | 内容 |
|---|---|
| どこで | oil-global-2027 / Gasoline_Local_Hormuz / Refinery_Local_H（2027-W15〜2028-W26）、rice の DC・精白 |
| 何が | oil：休業期間の P・Demand S・実出荷はいずれも前後 0。P の総量 60 は休業期間より前の週にある。rice：E2 は発火しなかった（§2） |
| なぜ（推定） | oil：Hormuz ルートの需要は、Refinery_Local_H のレベルでは休業開始より前に終わっている（LT のオフセットによる）。rice：休業週にもともと需要が無い |
| 実機での見方 | oil-global-2027 → Network → Refinery_Local_H → PSI List の 2027-W15 以降：P・S は「—」、行は灰色、CapHard は 8 |
| 期待との差 | 依頼書 §2.3 は「Backward の充填目標が 0 になる」と予測していた。充填目標は確かに 0 になるが、置くべき需要が無いため、PSI には現れない |

---

## 5. テスト

| | 結果 |
|---|---|
| 作業2の後の全テスト | **544 passed / 3 skipped / 0 failed** |

golden は据え置いた。変わった ev-thailand-2026_update には golden が無いため、全テストがそのまま通る。

---

## 6. 再現方法

```powershell
# 変更前後の計測（モデルは一時フォルダへ複写して実行。原本は触らない）
python docs\development\captrial_closure_rows\probe_closure.py . <出力dir>
python docs\development\captrial_closure_rows\compare.py <変更前dir> <変更後dir>
# データ移行（--apply なしならドライラン）
python docs\development\captrial_closure_rows\migrate_closure_rows.py . --apply
```
