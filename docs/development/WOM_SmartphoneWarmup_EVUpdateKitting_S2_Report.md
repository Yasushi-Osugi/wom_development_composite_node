# Smartphone の warmup・ev_update の Kitting・S2（実出荷の評価）　報告

- 依頼書：`requests/RequestLetter_SmartphoneWarmup_EVUpdateKitting_S2_to_CodeKun.md`
- 前提：決定記録 `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md` v1.4（基本ルール、D4・D5・D7・D7a）
- 実装：Code君（Claude Code, Windows）、2026-09-30
- ブランチ：`wom-v1r5m1_cap_trial`
- 基準 SHA：`979cf7a`。**着手時の HEAD：`b6d5482`**（基準＋依頼書 1 ファイル。コード・サンプル・golden は基準と同じ）
- **commit・push・merge はしていない。**
- 付表・実行条件：`docs/development/smartphone_evupdate_s2/`（`README.md` に一覧）
- 生データ：`output/smartphone_evupdate_s2/smartphone_evupdate_s2_rawdata.zip`（293 ファイル、SHA-256 は `docs/development/smartphone_evupdate_s2/rawdata_sha256.txt`）

本書は、節ごとに「観測結果／コードから分かった仕組み／業務上の解釈／未確認」を分けて書く。

---

## 0. 受入のまとめ

| 区分 | 合否 | 要点 |
|---|---|---|
| A：smartphone-global-2026-2029 の warmup | **合** | 旧書式の `capacity_plan.csv` でも warmup が働く。17 週で 68,534 件、26 週で 56,834 件が残るので、**26 週**を採用。残る 56,834 件は残した（需要・能力・期首在庫は変えていない） |
| B：ev-thailand-2026_update の組立 | **合** | 2 部材に置場（Stockyard）を入れ、既存の Kitting Gate で 1 完成品にする。Flow Check の NG（保存差 52,400）が消えた。エンジンのコードは変えていない |
| B4：同じ ID の重複の記録 | **合** | 記録だけ。置場を外した構成で 52,400 件、今の構成で 0 件。13 golden のモデル・legacy の 3 件・alloc で 0 件 |
| C：S2（要求と実出荷の分離） | **合**（残りは §5） | identity の充足・売上・原価・充足率が実出荷ベースになった。legacy の評価は、15 モデルで基準の評価と全列一致 |
| 全テスト | **617 passed／3 skipped／1 failed**（全 621 件。1 回の実行）。失敗した 1 件を流し直すと通るので、**621 件のうち通らないテストは無い**（618 passed／3 skipped） | 失敗の 1 件は、前から知られている Tk の初期化の不安定（`test_merit_order_plot.py::test_plot_regime_matrix`、`init.tcl` が読めない）で、今回の変更とは関係が無い（§6）。「1 回の実行で全件が緑」は観測していない |
| 更新した golden | `tests/golden/smartphone-global-2026-2029.json` だけ | rice・legacy の 3 件・ほかの 11 件は 1 バイトも変わっていない |
| GUI | 実アプリの窓を自動で動かして確認（§7.1）。マウス操作が要る確認は未実施（§7.2 に表） | |

次へ持ち越すこと（§5 に詳しく）：

1. smartphone の残り 56,834 件（すべて EMS_A の能力の押し戻しが元）。
2. money の `units`（Landed Cost の運賃に使う lot 数）が、DAD の行も合計している（今回の前から）。
3. money と PPC の売上が、もともと別の台帳で、一致しないモデルがある（今回の前から）。
4. Flow Check の表 3（Kitting の照合）は、CSV と表 1 の理由欄に出す。画面に表としては出していない。

---

## 1. 変更したもの

| 区分 | ファイル | 内容 |
|---|---|---|
| A | `wom/engine/warmup.py` | 旧書式（`node_name` 列なし）の `capacity_plan.csv` の助走行。必須の列が無いときの分かるエラー |
| A | `data/sample/smartphone-global-2026-2029/planning_config.csv`（新規） | `warmup_lt,26` |
| A | `data/sample/smartphone-global-2026-2029/capacity_plan.csv`・`demand_forecast.csv` | 助走行の追加だけ（52 行・156 行）。実需要期間の行は変えていない |
| A | `tests/golden/smartphone-global-2026-2029.json` | 作り直し（§2.5） |
| A | `tests/test_warmup_materialize.py` | 5 件を追加 |
| A | `tools/warmup_trial.py`（新規） | warmup の試行と、期末注文残の ID ごとの分類（測定だけ） |
| B | `data/sample/ev-thailand-2026_update/sc_tree_master.csv` | 置場 2 行の追加、部材 2 行の親の付け替え |
| B | `wom/engine/flow_check.py` | 表 3（Kitting の照合）`compute_kitting_check`、`flow_check_kitting.csv`、表 1 の理由欄への反映 |
| B | `tests/test_ev_update_kitting.py`（新規） | 8 件 |
| B | `tools/ev_update_kitting_trial.py`（新規） | 前後と、部材の遅着の測定 |
| B4 | `wom/engine/forward_planner.py`（**保護対象**） | 記録の追加だけ：`ForwardPlanResult.supply_duplicate_ids`・`record_supply_duplicates`、`_process_node` の 1 か所（27 行の追加、削除なし） |
| B4 | `wom/engine/flow_check.py`・`wom/gui/app.py` | 表 1 の列「同一ID重複」、1 件以上は NG、要約行 |
| B4 | `tools/run_headless_from_folder.py` | 警告を 1 行出す |
| C | `wom/engine/sc_tree_to_df.py`・`wom/data/schema.py` | 方式ごとの評価の列（§4.2） |
| C | `wom/engine/money.py` | 数量の基準（`qty_basis`）を運ぶ。不明は NaN。式は変えていない |
| C | `wom/engine/strategic_kpi.py` | 充足率を ID で判定（identity）。引数 `lot_flow_mode` |
| C | `wom/ppc/ppc_psi_bridge.py` | identity で実出荷の記録が無いとき、要求へ戻さず警告 |
| C | `tools/run_headless_from_folder.py`・`wom/gui/app.py` | ツリーに方式の印（`sc_tree.lot_flow_mode`）を付ける |
| C | `wom/gui/app.py` | Cost/Revenue チャート、PSI チャートの棒、Harvest Input の言葉、充足率のカード、ステータス行（計画の完了の行。すぐ後に PPC の完了の行で上書きされるので、ふつうは見えない） |
| C | `tests/test_s2_actual_shipment_eval.py`（新規） | 12 件 |
| C | `tools/s2_eval_compare.py`（新規） | 基準の評価と今の評価の比較（測定だけ） |
| C4 | `CLAUDE.md`、`docs/development/WOM_FlowCheck_WarmupTrial_Report.md` | KPI の表と注記、§6 S2 への追記 1 行 |

変えていないもの：

- 保護対象の 6 ファイルのうち、`forward_planner.py` 以外（Backward・plan_copy・plan_node・sc_tree・push_pull）。
- `forward_planner.py` の計画の動き（記録の追加だけ）。
- alloc の warmup 26、oil の warmup 26、smartx の能力、rice の legacy 指定。
- Obsidian Vault の未 commit の変更。

---

## 2. A：smartphone-global-2026-2029 の warmup

### 2.1 原因（コードから分かった仕組み）

- `capacity_plan.csv` の見出しは `sku_id,region,week,max_supply,cap_pieces,source`（`node_name` 列なし）。
- 実ローダ（`capacity_sealer.load_capacity_dataframe`）は、この書式を受け入れる。読み方は「(製品, 週) ごとに `max_supply` を合計し、その製品の InBound root（最初の MOM）の能力にする」。`region`・`cap_pieces`・`source` は読まない。
- warmup の生成（`warmup._build_warm_lines`）だけが `node_name` を必須にしていて、`ValueError` で止まっていた。
- smartphone では、能力が付くのは EMS_A_CN（Phone16）、EMS_A_CN_i15（Phone15）、EMS_A_CN_i17（Phone17）。Phone16 のもう 1 つの MOM（EMS_A_IN）には能力の行が無い（未設定）。
- 対応表：`docs/development/smartphone_evupdate_s2/A_capacity_schema_mapping.md`

### 2.2 直し方

- 旧書式では、**最初の実週の各行を、`week` だけ替えてそのままコピーする**。
  - (製品, 週) の合計＝ローダが見る能力が、最初の実週と同じになる。
  - `region`・`cap_pieces`・`source` を保つ。見出しは変えない。
  - 同じ製品に複数の行があっても、混ぜない。
  - 最初の実週に行が無い製品（後から発売される Phone17）には、助走行を作らない（新書式と同じ規則）。
- 空の `node_name` を足す、全ノードへ配る、`region` をノード名に読み替える、はしていない。
- 新書式の動きは変えていない（テストで固定）。
- `sku_id`・`week`・`max_supply` のどれかが無いときは、列名を示して `ValueError`。

### 2.3 試行（観測結果。コピーで測定、identity）

| | warmup なし | 17 週 | **26 週（採用）** |
|---|---:|---:|---:|
| 計画の開始・週数 | 2027-W01・156 | 2026-W37・173 | 2026-W28・182 |
| 需要（要求 ID） | 470,924 | 470,924 | 470,924 |
| 当週出荷 | 373,090 | 402,390 | 414,090 |
| 遅配 | 0 | 0 | 0 |
| **期末注文残** | **97,834** | **68,534** | **56,834** |
| うち Phone16／Phone15／Phone17 | 59,787／38,047／0 | 38,987／29,547／0 | 31,787／25,047／0 |
| 主因：能力 | 65,274 | 55,834 | 44,134 |
| 主因：計画期間の端（開始） | 32,560 | 12,700 | 12,700 |
| 助走週の生産量（MOM root の P） | 0 | 15,200 | 26,900 |
| 実需要の開始時の在庫（全ノード） | 0 | 7,020 | 16,240 |
| 報告期間の市場の出荷 | 373,090 | 402,390 | 414,090 |
| PPC 売上（円） | 583.3 兆 | 625.7 兆 | 641.0 兆 |
| PPC 粗利率 | 41.09% | 41.10% | 41.19% |
| 助走週の日付の PPC イベント | 0 | 0 | 0 |
| Flow Check の NG | 0 | 0 | 0 |

- warmup なしの 97,834 ＝ 65,274 ＋ 32,560 は、基準の報告値と同じ（再計測で確かめた）。
- 採用の手順（依頼書 A2）：17 週で残る → 26 週も測る → 減った（68,534 → 56,834）→ **26 週**。非単調な結果は無い。52 週は試していない。

### 2.4 残る 56,834 件の分類

**集計の規則**（`tools/warmup_trial.py` の冒頭に明記）：市場 leaf で出荷されていない要求 ID ごとに、上流へたどって「その ID を要求していて出荷していない、最も上流のノード」を**止まったノード**とする。主因は排他で、上から順に最初に当てはまった 1 つ（期間の終わり → Forward の能力の繰り延べ → 休業 → Backward の能力の押し戻し → 開始端 → ID の照合不能）。主因の順序によらず当てはまった条件は、補足列 `all_flags` にすべて残す。

| 主因 | 件数 | 止まったノード | 最初に置けなかったノード（Backward） | 当てはまった条件（`all_flags`） |
|---|---:|---|---|---|
| 能力 | 44,134 | SP_Phone16 24,587、SP_Phone15 19,547 | EMS_A_CN 24,587、EMS_A_CN_i15 19,547 | `past_due_cap` |
| 計画期間の端（開始） | 12,700 | EMS_A_CN 5,600、EMS_A_CN_i15 4,500、Foundry_A_TW 1,600、Foundry_A_TW_i15 1,000 | Foundry_A_TW 5,600、Foundry_A_TW_i15 4,500、SiliconWafer_TW 1,600、SiliconWafer_TW_i15 1,000 | `past_due_lt`＋**`mom_cap_pushback`**＋`before_first_supply` |

- **能力 44,134 件**（観測）：Backward が EMS_A の能力で生産を前の週へ押し戻し、計画の第 0 週を越えた（`past_due`）。市場の要求週は 2027-W21〜2029-W35。
- **開始端 12,700 件は、開始端「だけ」ではない**（観測）：12,700 件すべてに `mom_cap_pushback` が付く。つまり、EMS_A の能力で 20〜50 週前へ押し戻されて計画の最初の 9 週（2026-W28〜W36）に置かれ、そこから上流（Foundry_A：LT 6＋安全在庫 1 週など）へさかのぼる余地が無かった。足りなかった週数は 1〜9 週（1 段分の下限）。
  - warmup なしの 32,560 件には `mom_cap_pushback` が付かない（市場の要求週 2027-W01〜W17 の、本来の開始端）。17 週・26 週では、この本来の開始端は 0 件になった。
  - 17 週と 26 週で件数が同じ 12,700 なのは、「計画の最初の 9 週は、上流の LT の分だけ生産できない」という形が、開始週を動かしても同じだけ残るためである（コードから分かった仕組み）。
- **まとめ（解釈）**：26 週で残る 56,834 件は、元をたどるとすべて EMS_A の能力の押し戻しである。能力は Phone16 が 800／週、Phone15 が 500／週（後半は下がる）。
- **必要週の根拠（観測からの計算）**：17 週 → 26 週の 9 週で 11,700 件減った。1 週あたり 1,300 件＝ 800＋500（2 つの MOM の能力）。残り 56,834 件を同じ割合で消すには、あと約 44 週（合計で約 70 週）の助走が要る。D7a の上限（26 週）を大きく超えるので、**26 週にとどめて残す**。52 週以上は測っていない（未確認）。
- 遅配は 0 件。Forward の `cap_hard_deferred_lots` は 55,413 件で、warmup によらず同じ（能力の繰り延べはあるが、市場の要求週には間に合っている）。

### 2.5 原本への反映と golden

- `planning_config.csv`（`warmup_lt,26`）を新しく置き、助走行を生成した。

  | ファイル | 全行数 | 助走行 | 週の範囲 |
  |---|---:|---:|---|
  | `demand_forecast.csv` | 1,326 | 156 | 2026-W28〜2026-W53（Phone16・15 × 3 地域、数量 0） |
  | `capacity_plan.csv` | 442 | 52 | 2026-W28〜2026-W53（`Phone16,CN,<週>,800,,EMS_A_CN` と `Phone15,CN,<週>,500,,EMS_A_CN`） |

- `git diff` は追加だけ（実需要期間の行は変わらない）。
- golden（identity）の前後：

  | | 前（warmup なし） | 後（warmup 26） |
  |---|---|---|
  | period | 2027-W01・156 週 | 2026-W28・182 週 |
  | 市場：当週出荷／期末注文残 | 373,090／97,834 | 414,090／56,834 |
  | PPC 売上 | 583,304,347,994,200 | 641,014,134,734,200 |
  | PPC 粗利／粗利率 | 239,671,166,835,788／41.09% | 264,062,890,895,023／41.19% |
  | PPC lot 数／trust event | 1,047／366 | 1,127／390 |
  | forward | `cap_hard_deferred` 55,413／55,413 | 同じ |
  | backward | 0 | 同じ |
  | psi の変わったノード | — | 32／32（週の並びが変わるため） |

  - 例：Retail_AMER（Phone16）P 93,106・CO（のべ）1,090,800 → P 100,306・CO 0。EMS_A_CN：P 98,333 → 119,133。
  - 参考：legacy（warmup なし）の売上は 713.3 兆円（470,924 件をすべて出荷したことにしていた）。
- ほかのモデルの golden は更新していない。

### 2.6 テスト（A3）

`tests/test_warmup_materialize.py` に 5 件：旧書式の複数 SKU・地域（行ごとのコピー、後発の SKU は対象外、引用符つきの欄、実週の行が 1 バイトも変わらない）、再実行で同じ結果と取り除き（生成 0 行）、新書式の複数ノード（動きは同じ）、必須の列の欠損、CSV → warmup → 実ローダの結合（助走週の能力が最初の実週と同じ）。

---

## 3. B：ev-thailand-2026_update の組立

### 3.1 再現（観測結果。warmup 17 付きの基準の構成。置場を外したコピーで測定）

| | identity | legacy |
|---|---:|---:|
| Factory_Local_TH の P（のべ／異なる ID） | 105,400／52,700 | 105,100／52,700 |
| 実出荷 | 52,700 | 52,700 |
| 期末 I／期末 CO | 300／0 | 0／300 |
| 保存差 | **52,400** | **52,400** |
| 供給側の同じ ID の重複（ノード・週・ID） | **52,400** | **52,400** |
| 市場（需要＝当週出荷） | 63,240＝63,240 | 同じ |
| PPC 売上／原価 | 3,191.2 億／1,388.3 億 THB | 同じ |

- 重複は、すべて Factory_Local_TH の、同じ週に同じ ID が 2 件。例：2025-W50 の `EVmaker_Local:PRO:2026-W02:00001`（到着元は Platform_Unit_Assy と Motor_Unit_Assy）。全件は生データの `B/before_identity__supply_duplicates.csv`。
- identity の期末 I の 300 件は、保守週（2026-W32・2027-W32、能力 150）で 2 件目が別の週に届き、要求がすでに満たされていて在庫に残ったもの（のべ 13,950 lot 週の、実在しない在庫）。
- 市場は満たされ、PPC の金額も正しい値と同じになる。**市場が満たされることは、正しさの根拠にならない**（依頼書 B1 のとおり）。

### 3.2 直し方（サンプルの構成だけ。エンジンは変えていない）

- 2 つの部材に置場（`Platform_Unit_Assy_Yard`・`Motor_Unit_Assy_Yard`、`stockyard`、LT 0）を入れ、部材の親を置場に付け替えた。既存の置場モデル（ev-europe-2026・bom-test-2026）と同じ規則。
- 置場は `sc_tree_master.csv` だけに書く。能力・原価・地図の行は持たせない（二重計上を避ける）。
- 経路の LT の合計（4、1）、休業、能力、需要、BOM の意味は同じ。前後の対応表：`docs/development/smartphone_evupdate_s2/B_ev_update_node_path_mapping.md`
- していないこと：`set()` による P の重複の削除、ID の改名、assembly → confluence への変更、Flow Check の NG を対象外へ移すだけの処置。
- 既存の Gate で足りた。core の差分は要らなかった。

### 3.3 受入（観測結果）

| 受入 | 結果 |
|---|---|
| 各部材の入庫・払出・残高の保存 | 置場ごとに、入庫 52,700 ＝ 払出 52,700 ＋ 期末 I 0（表 3） |
| 完成 ID ＝ Factory の P、二重生成なし | Factory の P は 52,700 件・異なる ID 52,700。各置場の払出の ID の並びは、Factory の P と同じ |
| 片方の部材の遅着 | 下の表 |
| Flow Check の既知の NG | **解消**（NG 0、同一ID重複 0）。Factory_Local_TH は表 1 では「対象外（Kitting）」、理由欄に「表 3 の照合は一致」 |
| 市場・在庫・注文残・原価 | 市場 63,240＝63,240、期末注文残 0。Factory の期末 I 300 → 0。PPC 売上・原価は前と同じ |
| 回帰テスト | `tests/test_ev_update_kitting.py`（8 件）。ev-thailand 正常系・SE2 の再現・ev-europe のテストは緑 |

**片方の部材の遅着**（コピーで、モーターの能力を 2026-W20〜W22 の 3 週だけ 100／週に絞る。identity）：

| 項目 | 値 |
|---|---:|
| モーターがプラットフォームより遅く届いた ID | 1,400 |
| うち、モーターが届く前に完成した ID | **0** |
| うち、モーターが届く前に工場から出荷した ID | **0** |
| うち、回復後に同じ ID で完成した ID | **1,400**（全件） |
| プラットフォームが置場で待った週数（最大） | 3 |
| プラットフォームの置場の在庫（最大） | 1,200 |
| モーターの置場の在庫（最大） | 0 |
| 工場の CO（最大／期末） | 1,200／0 |
| 市場：当週出荷／遅配／期末注文残 | 62,440／800／0 |
| Flow Check の NG／同一ID重複／表 3 | 0／0／一致 |
| PPC 売上 | 3,191.2 億 THB（全件を期間内に出荷したので同じ） |

- 早い部材（プラットフォーム）は消えず、置場の在庫に残る。部材がそろうまで完成品は作られず、工場の出荷要求は CO（注文残）になる。
- ID ごとの履歴（両部材の到着週・完成週・出荷週）は、生データの `B/delay_identity__late_kits.csv`。
- 組立の能力による繰り延べと休業は、既存の Gate の規則のまま（保守週の能力 150 は、Backward が前倒しで吸収し、Forward での繰り延べは起きていない）。

### 3.4 表 3：Kitting の照合（今回加えた検査）

組立ノード（子がすべて置場）は、表 1 の到着差の検査では「対象外」になる（部材 N 個が完成品 1 個になるので、「向けて出荷した数」と「受け取った数」が設計上ちがう）。その境界を、部材と完成品に分けて照合する。

- 置場の行：入庫 ＝ 払出 ＋ 期末 I。払い出したのに完成していない ID が無いこと。
- 組立の行：完成品の二重生成が 0、すべての置場から払い出されていない完成が 0、最後の部材の到着より前の完成が 0。
- 結果は `flow_check_kitting.csv` と、表 1 の理由欄に出る。不一致なら、その組立ノードは NG。
- 既存の置場モデル：bom-test-2026（1 組立）、ev-europe-2026（2 組立）とも一致。「対象外」の件数（1、2）は前と同じ。

### 3.5 B4：同じ ID の重複を黙って捨てない（記録だけ）

- `ForwardPlanResult.supply_duplicate_ids`：（ノード, 週, Lot_ID, 件数）。供給側（前週 I ＋ 当週 P）に同じ ID が 2 件以上あった週を、両方式で記録する。
- **計画は変えない**：`_process_node` に、判定と記録の 3 行を足しただけ。legacy の golden 3 件と rice の golden は 1 バイトも変わらない。
- Flow Check 表 1 に列「同一ID重複」。1 件以上なら NG、理由に件数と最初の例。要約行にも合計を出す。
- headless：`[Headless] WARNING <製品>: 供給側に同じ Lot_ID が 2 件以上 N 件…` を 1 行（`--quiet` でも出す）。snapshot には入れない。
- 受入：

  | 対象 | 件数 |
  |---|---:|
  | ev_update の修正前の構成（identity／legacy） | 52,400／52,400 |
  | ev_update の今の構成 | 0 |
  | 13 golden のモデル（各モデルの方式） | すべて 0 |
  | legacy の golden 3 件（Cookie・ev-thailand・soysauce-jpy） | すべて 0 |
  | soysauce-jpy-2027-alloc | 0 |

  一覧：`docs/development/smartphone_evupdate_s2/B4_duplicates_all_models.csv`

---

## 4. C：S2（要求・実出荷・評価の分離）

### 4.1 棚卸し

`docs/development/smartphone_evupdate_s2/C_s2_usage_inventory.md` に、箇所ごとの「数量の元／計算式／画面のラベル／方式／対象の期間」の前後を表にした。

### 4.2 計算の決まり（実装したもの）

方式は、引数 `lot_flow_mode` → ツリーの印 `sc_tree.lot_flow_mode`（GUI と headless が付ける）→ どちらも無ければ要求ベース（これまでどおり）、の順に決める。

| 列 | identity | legacy・方式の指定なし |
|---|---|---|
| `qty_basis` | `actual_ship`（実出荷の記録が無ければ `unknown`） | `request` |
| `request_qty` | 当週の要求（supply S）× cpu | 同じ |
| `ship_qty` | 当週の実出荷 × cpu（遅配分の出荷を含む） | 同じ（記録なしは 0。前と同じ） |
| `demand_fulfilled` | **＝ `ship_qty`**（売上・原価の数量） | 要求 × cpu（前と同じ） |
| `on_time_qty`（当週充足） | 当週の要求 ID のうち、当週に出荷された ID | 計算しない（NaN） |
| `fill_rate`（当週充足率） | 当週充足 ÷ 当週要求。要求 0 は 1.0 | 要求 ÷ 需要（前と同じ） |
| `stockout_qty`（当週未充足） | 当週要求 − 当週充足 | max(0, 需要 − 要求)（前と同じ） |
| `co_qty` | **週初**の CO（その週に持ち越された要求） | 同じ |
| `co_end_qty` | **週末**の CO（CO＋S のうち、その週に出荷されなかった ID） | 計算しない（NaN） |

- 前の週から繰り越した要求を今週出荷しても、今週の充足には数えない。`ship_qty ÷ S` の形で 100% を超えることは無い。
- 当週未充足を期間で合計すると、遅配＋期末注文残になる（各 ID を 1 回ずつ）。CO の全期間の合計とは別の量。
- **要求 0 の週の充足率**は、この列のこれまでの決まり（1.0）を保った（既存の決まりがあるので、N/A にはしていない）。
- **実出荷 0 の記録は 0。実出荷の記録が無いのは「不明」**：数量・売上・原価・充足率は NaN、`qty_basis=unknown`、警告を出す。要求 S では代用しない。
- Revenue・COGS（`money.py`）：式は前と同じ（`demand_fulfilled × 価格`）。identity では数量が実出荷になる。価格・原価・通貨・`cpu_size`・`bom_qty` の換算は変えていない。
- ノードの Cost/Revenue チャート：identity では、**そのノードの実出荷** × そのノードの価格（市場 leaf に限らない）。題に基準を書く。
- Strategic KPI の充足率：identity では、市場の「当週充足 ÷ 要求」を ID で判定。
- PPC ブリッジ（C3-3）：identity で実出荷の記録が無いノードは、売上の行を作らず警告を出す。legacy・方式の指定なしは、これまでどおり S へ戻す。
  - この経路を通る呼び出し元：`ppc_runner.run_ppc_from_psi` の 1 か所（GUI と headless から）。どちらも `ForwardPlanner.run` の後に呼ぶので、実際に記録が無くなることは無い。テストで合成して確かめた。
- Demand レイヤー・Harvest Input は要求のまま。Harvest Input は、題と軸の言葉を「需要」に直した（数量は変えていない）。

### 4.3 legacy が変わらないこと（観測結果）

`tools/s2_eval_compare.py`：基準 commit（`979cf7a`）の `sc_tree_to_df.py`・`money.py`・`strategic_kpi.py` を取り出し、同じ計画結果に、基準の評価と今の評価を両方当てた。

- **legacy：15 モデル（13 golden ＋ ev_update ＋ alloc）のすべてで、元からある 18 列と、money の集計の全列が一致**（`legacy_identical=True`）。
- golden（period／products／config／forward／backward／ppc／psi）には、money や KPI の値は入っていない。**C で変わった golden は無い**（legacy の 3 件、rice、identity の 12 件とも。smartphone の golden の変化は A によるもの）。
- 方式の指定が無い呼び出し（サンプル内の `verify`・`exercises` のスクリプトなど）は、これまでどおり要求ベース。

### 4.4 identity で変わる値（観測結果。基準の評価 → 今の評価）

| モデル | 要求 | 実出荷 | 当週充足 | 当週未充足（前→後） | money 売上（前→後） | 充足率（Strategic KPI、前→後） | PPC 売上 |
|---|---:|---:|---:|---|---|---|---:|
| smartphone-global-2026-2029 | 470,924 | 414,090 | 414,090 | 0 → 56,834 | 463.5 → 416.3（百万） | 100% → 87.9% | 641.0 兆 |
| oil-global-2027 | 191,058 | 191,029 | 191,029 | 0 → 29 | 1.6209 兆 → 1.5423 兆 | 100% → 99.98% | 1.5711 兆 |
| smartx-2027-2029 | 709,811 | 709,811 | 693,738 | 0 → 16,073 | 702.3 → 702.3（百万、同じ） | 100% → 97.7% | 702.3 百万 |
| soysauce-jpy-2027-alloc | 100,501 | 75,291 | 75,291 | 0 → 25,210 | 543.4 → 390.4（百万） | 100% → 74.9% | 428.0 百万 |
| Cookie-jp-2026 ほか、期末注文残も遅配も無い 9 モデル | — | ＝要求 | ＝要求 | 0 → 0 | 同じ | 100% → 100% | — |

- smartx は、遅配 16,073 件がある。実出荷の合計は要求と同じなので売上は変わらず、当週充足率だけが下がる（総量では判定しない、の実例）。
- 全モデル×2 方式の表：`docs/development/smartphone_evupdate_s2/C_s2_compare.csv`

### 4.5 受入ケース（C3）

| # | ケース | 結果 | テスト |
|---|---|---|---|
| 1 | 要求 2 ID・実出荷 1 ID | 出荷 1、当週充足 1、残 1、売上は 1 lot 分 | `test_c3_1_…` |
| 2 | 前週の CO 1 ID だけを今週出荷、今週の要求 1 ID は未充足 | 出荷 1、当週充足 0、週末 CO 1、充足率 0%（`ship÷S` なら 100%） | `test_c3_2_…` |
| 3 | 実出荷 0 は 0。記録なしは不明 | 0 と NaN を区別。要求へ戻さない。PPC ブリッジも同じ（legacy は前と同じ） | `test_c3_3_…`（2 件） |
| 4 | コピーで上流の能力を減らす | ev-thailand-2026 のコピーで Components_CN の能力を絞ると、市場・DC の実出荷、money の売上、充足率、PPC の売上が下がる。原本は変えていない。legacy の同じコピーは要求ベースのまま | `test_c3_4_…` |
| 5 | Demand レイヤー・Harvest Input は要求のまま | `demand_fcst`・`request_qty` は方式によらず同じ。Planning 前は「未実行」「—」の表示（変えていない） | `test_demand_layer_columns_stay_the_request`、§7 |
| 6 | 通貨・lot・`cpu_size` の換算を保つ | `cpu_size` 12・`bom_qty` 4 で、どの列も同じ換算 | `test_c3_6_…` |

### 4.6 文書（C4）

- `CLAUDE.md`：KPI の表（Fill Rate・Sell-through・販売チャネル Revenue）を実装した定義に直し、「未対応」の注記を、実装した範囲と残った未対応に書き換えた。
- `WOM_FlowCheck_WarmupTrial_Report.md` §6 S2：対応したことを 1 行追記した。

---

## 5. 副作用・未決事項

検査済みのことと、判断が要ることを分けて書く。

### 5.1 観測した副作用（今回の変更によるもの）

| # | どこで | 何が | なぜ | 実機での見方 |
|---|---|---|---|---|
| S1 | smartphone-global-2026-2029 | 計画の開始が 2027-W01 → 2026-W28、182 週になる。期末注文残は 97,834 → 56,834 | warmup 26 | 読み込むと Start Week が 2026-W28、# Weeks が 182。Flow Check の要約行に期末注文残 56834 |
| S2 | identity のモデルの Charts（Fill Rate・Stockout）、KPI Table、Strategic KPI の充足率 | 期末注文残・遅配のあるモデルで、100% より下がる | 実出荷ベースになったため（§4.4） | smartphone：Management の「需要充足率」が 87.9%（⚠ WARN） |
| S3 | At-Risk SKUs のタブ | identity で、充足率が 95% 未満の週が「リスク」に出るようになる | `fill_rate` を読むため | 未確認（値の元は検査済み。画面は見ていない） |
| S4 | `plan_df`・money の表の列 | 列が増える（`qty_basis`・`request_qty`・`on_time_qty`・`co_end_qty`）。Export to CSV／Excel にも出る | 基準を見分けるため | Export した CSV の列 |
| S5 | Flow Check の表 1 | 列「同一ID重複」が増える。Kitting の組立の理由欄が長くなる | B4・B3 | Network → Flow Check |
| S6 | headless の出力先 | Kitting のあるモデルで `flow_check_kitting.csv` が増える | 表 3 | `output/flow_check/<モデル>/` |

### 5.2 前からあって、今回見つけたもの（変えていない）

| # | どこで | 何が | 影響 | 案 |
|---|---|---|---|---|
| P1 | `money.py` の `total_units` → `units` | 市場 leaf の行だけでなく、DAD の行の数量も合計する。DAD が 1 段なら 2 倍、2 段なら 3 倍になる（例：ev_update で市場 63,240 に対して `units` 126,480、Cookie で 141,990 に対して 362,910） | Landed Cost の運賃（Freight、情報列）が過大になる | `units` を市場 leaf の行だけで合計する。legacy の値が変わるので、今回は変えていない |
| P2 | money と PPC の売上 | 価格の元が違う（`sku_master` の価格 と `ppc_market_price`×為替）。ev-europe・ev-thailand・smartphone・rice などで桁が違う | Management の P&L は PPC の台帳で上書きするので画面は PPC の値。money の値は運転資本・Landed Cost の運賃に使われる | 依頼書 C2 のとおり、一致は求めていない。未対応の範囲として記録 |
| P3 | GUI のステータス行 | `PPC complete (sample data)` と出る。`_psi_mode` というキーを読むが、どこも書いていないので、いつも sample data と表示される | 表示だけ | キーを PPC の結果に入れるか、表示を直す |
| P4 | Phone16 の EMS_A_IN | 能力の行が無い（未設定＝制限なし）。旧書式の能力は最初の MOM だけに付く | モデルの設定 | 新書式へ移すなら、EMS_A_IN の能力を決める必要がある（対応表 §1） |

### 5.3 判断を仰ぎたいこと（未決）

1. **smartphone の残り 56,834 件**：D7a のとおり 26 週で残した。約 70 週の助走で消える見込み（計算。測っていない）。残すのでよいか。
2. **`units` の二重計上（P1）**：直すと、legacy を含めて Landed Cost の Freight の値が変わる。別の依頼で扱うか。
3. **表 3 を画面の表にするか**：今は CSV と表 1 の理由欄だけ。Flow Check のタブに 3 つ目の表として出すこともできる。
4. **PPC の台帳の中間ノード**：市場の販売数量から経路をたどって導く決まりのままで、各ノードの実出荷は使っていない（依頼書 C2 の「別契約」）。ノードの Cost/Revenue チャート（実出荷 × `node_cost_master`）とは、別の台帳である。

### 5.4 未確認

- 52 週以上の smartphone の warmup（依頼書により対象外）。
- GUI のマウス操作による確認（§7.2）。
- At-Risk SKUs・Scenario Delta のタブの表示（値の元の `plan_df` は検査済み）。
- 独立 Linux での実行（今回は Windows だけで作業した）。

---

## 6. テスト・golden

| 項目 | 結果 |
|---|---|
| 全テスト（`python -m pytest tests/ -q -p no:cacheprovider`） | **617 passed／3 skipped／1 failed**（全 621 件、13 分 13 秒） |
| 失敗の 1 件 | `tests/test_merit_order_plot.py::test_plot_regime_matrix`：`_tkinter.TclError: Can't find a usable init.tcl`。Tk の初期化の不安定で、前の 2 回の報告でも同じものが出ている。今回の変更とは関係が無い。**単独（plot・golden・GUI パネルの 3 ファイル）で 95 passed／3 skipped** |
| 増えたテスト | 25 件（warmup 5、ev_update の Kitting 8、S2 12）。596 → 621 |
| 三層 | Unit：合成ツリー（S2 の C3-1〜3・6、重複の記録）。Integration：CSV → warmup → 実ローダ、CSV → headless → Flow Check／`plan_df`／money。E2E：golden 13 件＋legacy の golden 3 件 |
| golden | 更新は `smartphone-global-2026-2029.json` だけ（意図した変化、§2.5）。ほかの 12 件と legacy の 3 件は、`git status` に出ない（1 バイトも変わっていない） |
| legacy の評価 | 15 モデルで基準と全列一致（§4.3） |
| 保護対象 | `forward_planner.py` に 27 行の追加（記録だけ、削除なし）。ほかの 5 ファイルは変えていない |

全テストの出力は、生データの `pytest_full.txt`。

後の確認（2026-10-02）：

- 全テストの実行（2026-09-30 21:07 に終了）より後に、`wom/`・`tests/`・`tools/`・`data/sample/` のコード・入力・golden は変えていない（更新時刻と `git status` で確かめた）。その後に動かしたのは、失敗した 1 件を含む 3 ファイルの流し直し（95 passed／3 skipped）、GUI の自動確認、報告書と付表の作成だけである。そのため、全テストは流し直していない。
- テストの Python のプロセスは残っていない（`python`・`bash`・`sleep` のプロセスは 0 件）。
- 大杉さんが止めた「pytest の要約行を待つ」背景タスクは、前の依頼（Warmup17）のときに仕掛けた待ち受けで、読む相手のファイル（`pytest_all.txt`）が作られないまま残っていたもの。テストそのものではなく、結果には関係しない。止め忘れは Code君の不手際である。
- 全テストの終わりの時刻に、`data/sample/apparel-us-2026`・`bom-test-2026` の一部のファイルの更新時刻が新しくなっている。既存のテストが同じ内容で書き戻すためで（`WOM_FlowCheck_WarmupTrial_Report.md` §6 S7、今回の前から）、`git status` に差分は出ない。

---

## 7. GUI の確認

### 7.1 自動で確かめたこと（実アプリの窓を動かした）

`wom.gui.app.WOMApp` を起動し、モデルのコピーを読み込み、Run Planning Engine を押したのと同じ処理（GUI 自身のスレッド）を動かして、PPC の完了まで待ち、画面の値を読んだ。窓の画像は Win32 の PrintWindow で取った（画面全体の取り込みはしていない）。スクリプトと画像・値は、生データの `gui/`。

| モデル | 確かめた値（画面の部品から読んだもの） |
|---|---|
| ev-thailand-2026_update（identity） | Start Week 2025-W37・121 週。Flow Check 要約「ノード 17（NG 0・対象外 1・同一ID重複 0・Kitting の照合 1 組立（NG 0））、需要 63240 ＝ 当週出荷 63240 ＋ … ＋ 期末注文残 0」。Factory_Local_TH の理由「対象外（Kitting）。表 3 の照合は一致（完成 52700、期末に置場で待つ部材 0）」。表 1 の見出しに「同一ID重複」。充足率のカード 100.0% ✅。Cost/Revenue の題「Cost / Revenue（実出荷ベース）─ IN:mom:Factory_Local_TH:EVmaker_Local」。Network の図に置場 2 つが出る |
| smartphone-global-2026-2029（identity） | Start Week **2026-W28**・**182** 週（エラーなし）。Flow Check 要約「需要 470924 ＝ 当週出荷 414090 ＋ … ＋ 期末注文残 56834」。`plan_df` の基準 `actual_ship`、市場の実出荷 414,090、当週未充足 56,834。充足率のカード **87.9% ⚠ WARN**。SP_Phone16 の Cost/Revenue の題「（実出荷ベース）」、数量は実出荷 219,439（要求は 251,226） |
| smartphone-global-2026-2029（コピーに `lot_flow_mode,legacy`） | ツリーの印 `legacy`、`plan_df` の基準 `request`、市場の数量 470,924、当週未充足 0、充足率のカード 100.0% ✅、Cost/Revenue の題「（要求 S ベース（legacy））」。identity が混ざらない |

3 回とも、エラーは 0 件。

### 7.2 大杉さんに確かめてほしいこと（マウス操作。未実施）

`python -m main` を起動し直してから、モデルのフォルダを読み込み、Run Planning Engine を押す。

| # | モデル | タブ・操作 | 見るもの | 期待する表示 |
|---|---|---|---|---|
| 1 | smartphone-global-2026-2029 | 読み込み直後の Planning Config | Start Week・# Weeks | 2026-W28・182（エラーが出ない） |
| 2 | smartphone-global-2026-2029 | Network → ✔ Flow Check | 要約行 | 需要 470924 ＝ 当週出荷 414090 ＋ 早出し 0 ＋ 遅配 0 ＋ 期末注文残 56834。NG 0 |
| 3 | smartphone-global-2026-2029 | Network → 図の EMS_A_CN をクリック → PSI Chart | 2026-W28〜W53 | 助走週に P（800／週）が立つ。上流の LT の分、最初の数週は立たない |
| 4 | smartphone-global-2026-2029 | Management → Strategic KPI | 需要充足率のカード | 87.9%、⚠ WARN。式の説明「当週出荷 / 要求（市場）」 |
| 5 | smartphone-global-2026-2029 | Charts → Fill Rate／Stockout（シナリオ Planning） | 線・棒 | 充足率が 100% を下回る週がある。Stockout に当週未充足が出る（合計 56,834） |
| 6 | smartphone-global-2026-2029 | Network → 図の SP_Phone16 をクリック | 下の Cost/Revenue の題と、PSI の棒・線 | 題「Cost / Revenue（実出荷ベース）」。PSI の青い棒（S: Request）より、紫の線（Ship）が低い週がある |
| 7 | ev-thailand-2026_update | Network（製品 EVmaker_Local） | 図 | Platform_Unit_Assy → Platform_Unit_Assy_Yard → Factory_Local_TH、Motor も同じ形 |
| 8 | ev-thailand-2026_update | Network → ✔ Flow Check | 表 1 | 赤い行（NG）が無い。Factory_Local_TH は灰色（対象外）で、理由に「表 3 の照合は一致（完成 52700…）」。列「同一ID重複」はすべて 0 |
| 9 | ev-thailand-2026_update | Network → 📋 PSI List → `IN:mom:Factory_Local_TH:EVmaker_Local` | Σ 行 | P 52700、S 52700、Ship 52700（前は P 105400） |
| 10 | ev-thailand-2026_update | 同上 → `IN:stockyard:Platform_Unit_Assy_Yard:…` | Σ 行 | P 52700、Ship 52700、I（期末）0 |
| 11 | ev-thailand-2026_update | Flow Check → CSV 書き出し | 出力先 | `flow_check_kitting.csv` ができる（完成品 1 行＋置場 2 行、すべて OK） |
| 12 | rice-japan-2027-2028 | Charts → Harvest Input | 題と縦軸 | 「週次の収穫要求量（需要：Demand レイヤーの S。実出荷ではない）」「Lots requested (demand)」。棒の形は前と同じ |
| 13 | rice-japan-2027-2028（legacy） | Management・Network のノードの Cost/Revenue | 充足率・題 | 充足率は前と同じ値。題「Cost / Revenue（要求 S ベース（legacy））」 |
| 14 | 任意 | Planning Engine を実行する前 | Management・Charts の Harvest Input・PSI List | 「Planning Engine 未実行」「Planning Engine を実行してください」「—」。実出荷 0 とは出ない |

注意：フォルダを切り替えただけだと、前のモデルの `output/ppc` が残る（既知）。モデルを替えるときは、`python -m main` を起動し直す。

---

## 8. 成果物

| 種類 | 場所 |
|---|---|
| 報告書 | 本書 |
| 付表 | `docs/development/smartphone_evupdate_s2/`（`README.md`、A：試行表・ノード別・書式の対応表、B：前後の対応表・PSI・表 3・重複の一覧、C：棚卸し・比較表） |
| 測定スクリプト | `tools/warmup_trial.py`、`tools/ev_update_kitting_trial.py`、`tools/s2_eval_compare.py` |
| 回帰テスト | `tests/test_warmup_materialize.py`（追加）、`tests/test_ev_update_kitting.py`、`tests/test_s2_actual_shipment_eval.py` |
| 生データ | `output/smartphone_evupdate_s2/smartphone_evupdate_s2_rawdata.zip`（4.8 MB、293 ファイル。A：条件ごとのモデルのコピー・市場 leaf の全 ID の結果・期末注文残の ID ごとの分類。B：前後・遅着の出力、重複の全件、遅れた ID の履歴。C：比較表。gui：画面の画像と読んだ値。全テストの出力）。SHA-256 は `docs/development/smartphone_evupdate_s2/rawdata_sha256.txt` |

差分の確認：`git status`、`git diff --stat`、`git diff -- wom/engine/forward_planner.py`（記録の追加だけ）、`git diff -- data/sample/smartphone-global-2026-2029`（追加だけ）。
