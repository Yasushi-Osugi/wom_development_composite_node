---
handoff:
  case_id: BSSEAF-COS-LOOP4
  task_id: NEWAGENT-MINIMUM-SUPPLY-TRIAL-001
  role_from: implement          # 新しいセッションの Claude Code（作業計画を書いた担当が、続けて試行）
  role_to: owner
  target_commit: 7a6755103ad935a319fea00f9f598871d9265c68
  knowledge_used:
    - id: WOM-SEM-SUPPLY-ALLOCATION-001
      version: "0.6"
      applicability: "①〜⑤（§3）、最低供給量の二段階の確認と衝突（§6.1）"
    - id: WOM-DESIGN-UPPER-DEMAND-PLAN-001
      version: "0.3"
      applicability: "§3.1 trim_to_capacity_latest、§3.2 最低供給量、§4 診断（参考値）"
    - id: WOM-KB-BSSEAF-001
      version: "v0.5"
      applicability: "8 段階（段階 4 の試行）、一巡の記録"
    - id: 作業計画 TH70
      version: "v0.1"
      applicability: "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md §5・§6"
  acceptance:
    ref: "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md §6（比べる項目と受入の条件）"
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Report.md
    - docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/
  status: "TH70 採用・段階 7 確認済み（独立性は弱い）。段階 8 は設計担当の Claude君へ。この担当の作業は終了（2026-11-06）"
  decisions_used:
    - "H1（2026-11-06）：タイのクリームの 7 割・切り上げは全量（299 lot を減らさない）の意味で進める"
    - "H2（2026-11-06）：試行 T0〜T3 は同じ担当が写しで行う"
    - "H3（2026-11-06）：TH70 を化粧品の計画として採用する（§6 の 1）"
    - "H4（2026-11-06）：段階 7 の確認は別の担当（設計担当の Claude君）が行う（§6 の 2）"
    - "H5（2026-11-06）：段階 8（知識の更新）は設計担当の Claude君が行う。§7 の候補はそのまま渡す（§6 の 3）"
  stage7:
    by: "設計担当の Claude君"
    method: "付録の台帳から独立に数え直し"
    result: "報告と一致：届いた 3,864・届かない 0、タイのクリームは全週で全量、最低供給量を下回った週 0、シンガポールのクリームの減らす区間 2029-W07〜W50、ほかの鍵は基準（MS50）と同じ"
    independence: "弱い。試行の担当と確認の担当が同じ系統のモデル（Claude）"
    pending: "GPT君の再集計を追加で行う場合は、その結果を後で記録する"
  stage8:
    by: "設計担当の Claude君"
    handover: "§7 の 6 つの候補をそのまま渡す"
  open_items:
    - "（任意）GPT君の再集計を行った場合、その結果の記録"
  stop_reasons: []
  handover_notes:
    - "T1：基準 MS50 は、今の commit で付録の台帳 5 つとバイト単位で一致した。止める条件には当たらなかった"
    - "T2：TH70 は終了コード 0。タイのクリームは 104 週すべて当週に全量。⑤ 0、年齢の最大 28 週（52 週超 0）"
    - "変わったのはシンガポールの代理店のクリームだけ：減らす区間が 2029-W19 → W07 に広がった（作業計画の近似と一致）"
    - "正式なサンプル・コード・golden・保護対象のコアは変えていない。試行は output/ の写しだけ"
  next: owner
---

# 報告書：BS-SEAF 化粧品 — タイ向けクリームの最低 7 割（TH70）の試行

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_MinimumSupply_Reallocation_to_NewAgent.md` v1.0、作業計画 `requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md` §6（T0〜T3）、大杉さんの決定 H1・H2（2026-11-06）
- 実施：新しいセッションの Claude Code（Claude Opus 5.5）、2026-11-06
- 時刻：始め **06:45:12**、終わり **06:52**（端末の時計。T0〜T3 の実行は 06:45〜06:49、そのあと付録と本書）
- 付録（git の追跡対象）：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/`

## 0. 結論

**一言で：タイ向けのクリームを全量守る案（TH70）は、工場の能力を増やさず、未充足 0・年齢 52 週以内のまま成り立った。代わりに、シンガポールの代理店のクリームの減らし始めが 12 週早まる（2029-W19 → W07）。**

1. **基準の再現（T1）**：今の commit（`7a67551`）で MS50 を実行し直した。選択の台帳・要求週ごとの結果・最低供給量の確認・時間の可否の診断・供給 0 の連続の 5 つは、付録 `WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/udp/MS50/` と**バイト単位で一致**した。`udp_plan.json` の `output_hashes`・`input_hashes` も一致した。違ったのは `target_commit`・`code_dirty`・`knowledge_used`・`owner_decisions` の 4 つで、実行の記録の欄である。
2. **TH70（T2）**：終了コード 0（衝突なし・未達なし）。① 4,056 ＝ ② 3,864 ＋ ③ 192。② ＝ ④ 3,864（すべて当週）＋ ⑤ 0。**タイのクリームは 104 週すべてで、当週に元の需要の全量（299 lot）を届けた**。ほかの 3 つの代理店の鍵は、最低 5 割を下回る週 0（計画の時・実行の結果とも）。
3. **変わったもの**：数量・選択・結果が変わったのは、クリームの SG・TH の代理店の 2 つの鍵だけ。直営店・公式 EC・美容液は、要求週ごとにすべて MS50 と同じ。
   - シンガポールの代理店のクリーム：③ 63 → 88。減らす区間は 2029-W19〜W50（32 週）→ **2029-W07〜W50（44 週）**。減らす週はすべて 5 lot 中 3 lot（60％）。前半（2027-W01〜2029-W20）の当週の充足率は 99.5％ → 95.3％。後半は 62.5％で同じ。
   - これは作業計画 §5.2 の手の近似（W07〜W50、44 週、60％）と**完全に一致**した。
4. **工場と在庫**：工場のクリームの週ごとの生産は、173 週すべて MS50 と同じ（合計 1,680）。作り置き（工場の完成品倉庫）の最大は 205 lot（2027-W20）で同じだが、2029-W03〜W45 に最大 25 lot 多く残る（lot・週の合計 18,568 → 19,199、＋3.4％）。年齢（先入れ先出し）の最大は 28 週で同じ、52 週超 0。
5. **比べるための評価の額**：607,741,740 円 → 607,776,840 円（＋35,100 円）。25 lot が SG から TH へ移った分（単位の貢献の差 4,730 − 4,671.5 円 × 24 個 × 25 lot）。営業利益ではない。

## 1. 何をしたか（T0〜T3）

| 段 | 中身 | 結果 |
|---|---|---|
| T0 | サンプルを `output/bsseaf_cosmetics_th70/MS50`・`TH70` に写し、C3a の能力（美容液 17・14、クリーム 13・11）を書いた。TH70 の数量枠と方針を作った | 写しの `capacity_plan.csv` のハッシュ `2ca7cf34…` は、MS50 の元の実行の `input_hashes` と同じ |
| T1 | MS50 を `run_quantity_allocation` で実行し、付録と比べた | 終了コード 0。台帳 5 つがバイト一致（`records/t1_compare.json`） |
| T2 | TH70 を同じ手順で実行（`--allocation-file inputs/allocation_qty_TH70.csv`、`--policy-file inputs/udp_policy_MS50TH70.csv`） | 終了コード 0 |
| T3 | 両案の台帳・計画の記録・年齢・作り置き（headless で木を取り出して数えた）・評価の額を比べた | §2〜§4 |

実行のコマンド（T2。T1 は数量枠・方針を MS50 のものに、判断の参照先を MS50 の元の参照と H2 にしたもの）：

```
python -m tools.run_quantity_allocation --model-dir output/bsseaf_cosmetics_th70/TH70
  --allocation-file output/bsseaf_cosmetics_th70/work/allocation_qty_TH70.csv
  --week-rule trim_to_capacity_latest
  --policy-file output/bsseaf_cosmetics_th70/work/udp_policy_MS50TH70.csv
  --udp-out output/bsseaf_cosmetics_th70/udp
  --knowledge-file output/bsseaf_cosmetics_th70/work/knowledge.json
  --out-dir output/bsseaf_cosmetics_th70/_planning_state
  --unallocated-note "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
  --decision-ref "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md §7 H1（…）"
  --decision-ref "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md §7 H2（…）"
python -m tools.shelf_life_check --model-dir output/bsseaf_cosmetics_th70/TH70 --max-age-weeks 52
  --demand-file demand_forecast_Q01.csv --warmup-real-start 2027-W01 --out output/bsseaf_cosmetics_th70/shelf/TH70
```

使った知識の版と判断の参照先は、両案の `udp_plan.json` の `knowledge_used`・`owner_decisions` に入っている。プラグインは `--plugins` を省いたので、モデルの推奨の組（`HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin`）。

## 2. 比べる表（`records/report_tables.md` から）

| 項目 | MS50（再現） | TH70 |
|---|---:|---:|
| 終了コード | 0 | 0 |
| ③ 外す量 | 192 | 192 |
| ④ 実納品（すべて当週） | 3,864 | 3,864 |
| ⑤ 未充足 | 0 | 0 |
| 週の最低の充足率 美容液 代理店（SG／TH） | 50%／50% | 50%／50% |
| 週の最低の充足率 クリーム 代理店（SG） | 60% | 60% |
| 週の最低の充足率 クリーム 代理店（TH） | 67% | **100%** |
| 最低供給量を下回った週（計画の時／実行の結果） | 0／0 | 0／0 |
| 時間の可否の参考値（美容液／クリーム、試行の前） | 0／0 | 0／0 |
| 年齢の最大（週）／52 週超 | 28／0 | 28／0 |
| Lot_ID の滞留の最大（参考。物の年齢ではない） | 144 | 169 |
| 作り置きの最大 クリーム | 205（2027-W20） | 205（2027-W20） |
| 作り置きの lot・週の合計 クリーム | 18,568 | 19,199 |
| 比べるための評価の額（円） | 607,741,740 | 607,776,840 |

クリームの代理店の鍵：

| 鍵 | 案 | ① | ② | ③ | ④ | ⑤ | 減らす区間 | 減らす週 | 週の最大 |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| 代理店（SG） | MS50 | 754 | 691 | 63 | 691 | 0 | 2029-W19〜W50 | 32 | 2 |
| 代理店（SG） | TH70 | 754 | 666 | 88 | 666 | 0 | **2029-W07〜W50** | 44 | 2 |
| 代理店（TH） | MS50 | 299 | 274 | 25 | 274 | 0 | 2029-W26〜W50 | 25 | 1 |
| 代理店（TH） | TH70 | 299 | 299 | 0 | 299 | 0 | — | — | — |

代理店の当週の充足率（前半 2027-W01〜2029-W20、後半 2029-W21〜W52）：

| 鍵 | 案 | 前半 | 後半 |
|---|---|---:|---:|
| クリーム 代理店（SG） | MS50 | 99.5% | 62.5% |
| クリーム 代理店（SG） | TH70 | 95.3% | 62.5% |
| クリーム 代理店（TH） | MS50 | 100.0% | 74.0% |
| クリーム 代理店（TH） | TH70 | 100.0% | 100.0% |

美容液・直営店・公式 EC の全行と、SKU・チャネル別の年齢は `records/report_tables.md`。

## 3. 受入の条件ごとの確かめ（作業計画 §6）

| 観点 | 結果 | 根拠 |
|---|---|---|
| 固定する条件 | 満たす。入力のハッシュの差は数量枠と方針のファイルだけ。期間は両案とも 2026-W37 から 173 週。能力・需要は同じハッシュ | `measure.json` の `input_hash_diff`・`period`、`inputs/t0_hashes.json` |
| 数量 | 満たす。要求週ごとの全行で ①＝②＋③、②＝④＋⑤（スクリプトで assert）。道具の照合も終了コード 0 | `th70_measure.py` の `load()`、`records/TH70_stdout.txt` |
| 最低供給量 | 満たす。タイのクリームは 104 週すべて当週 ④ ＝ ①。ほかの 3 鍵は下回る週 0 | `udp/TH70/udp_min_supply_check.csv`、`udp_plan.json` の `min_supply_summary` |
| 時間の制約 | 参考値は試行の前に記録して 0／0。実行の結果も ⑤ 0、早出し・遅配 0 | `records/TH70_pre.json`、`measure.json` |
| ほかの市場 | シンガポールのクリームだけ変わった（§0 の 3）。直営店・EC・美容液は要求週ごとに同じ | `measure.json` の `keys_with_any_change` |
| 在庫・年齢 | 満たす。年齢の最大 28 週、52 週超 0（COS-R05）。作り置きは最大が同じで、合計が 3.4％増える | `shelf/TH70/shelf_life_summary.csv`、`records/cream_factory_stock_by_week.csv` |
| 金額 | 比べるための評価の額 ＋35,100 円（付録 `measure.py` と同じ比べ方） | `measure.json` の `eval` |
| 根拠 | commit `7a67551`、`code_dirty` false、入力と方針のハッシュ、知識の版、判断の参照先 | 両案の `udp_plan.json` |

## 4. 読み方の注意

- **シンガポールの減らし始めが早まる理由**：SG と TH の代理店は工場までの週が同じ（4 週）。MS50 で TH が減らしていた 2029-W26〜W50 の週は、SG が既に最低 5 割まで減っていて余地が無い。だから道具は、最低で止まった分を前の週へ繰り越し、SG を 2029-W07〜W18 にも 2 lot ずつ減らした。工場の生産は変わらず、前の週で空いた分は作り置きとして後の週の TH へ回る。作り置きが 2029-W03〜W45 に最大 25 lot 多いのはこのため。
- **年齢**：先入れ先出しの年齢の最大は変わらない（28 週）。Lot_ID の滞留の最大は 144 → 169 週に延びるが、Lot_ID は需要の単位で物の個体ではないので、物の年齢として読まない（Start Here R18）。
- **評価の額**は配分を比べるための値で、数量配分の経路は「財務は未評価」。0 円や営業利益として読まない。
- **確かめた範囲**：化粧品の C3a の 1 ケース。未達（終了コード 4）の経路は、この試行では出ていない。

## 5. 変えたもの・変えていないもの

- 変えたもの：本書、付録、作業計画の H2 の記録（次の版で）、commit メッセージの下書き。試行の写し・出力は `output/bsseaf_cosmetics_th70/`（git の対象外）。
- 変えていないもの：正式なサンプル `data/sample/cosmetics-sg-th-2027-2029`、コード、golden、保護対象のコア、既存の付録。`git status` で、変わったのは上の 2 つの新しい場所（と作業計画）だけであることを確かめた。

## 6. 大杉さんに決めてほしいこと

**1 は決定済み**（H3、2026-11-06）：大杉さんが TH70 を化粧品の計画として採用した。正式なサンプル `data/sample/cosmetics-sg-th-2027-2029` への反映（数量枠・方針の CSV、golden の要否）は、まだ行っていない。反映は別の依頼で行う。

**2 も決定済み**（H4、2026-11-06）：段階 7 の確認は設計担当の Claude君が行った。付録の台帳から独立に数え直し、報告と一致した（届いた 3,864・届かない 0、タイのクリームは全週で全量、最低供給量を下回った週 0、シンガポールのクリームの減らす区間 2029-W07〜W50、ほかの鍵は MS50 と同じ）。**試行の担当と同じ系統のモデルなので、独立性は弱い。** GPT君の再集計を追加で行う場合は、その結果を後で記録する。（この担当が下書きした依頼書 `requests/RequestLetter_BSSEAF_Cosmetics_ThaiCream_Minimum70_Stage7_Verify.md` は、この決定では使っていない。）

**3 も決定済み**（H5、2026-11-06）：段階 8 の知識の更新は設計担当の Claude君が行う。§7 の候補はそのまま渡す。

| # | 一言の決定 | 中身 | 推奨と理由 |
|---|---|---|---|
| 1 | **TH70 を化粧品の計画として採用する** | タイのクリームを全量守り、その 25 lot をシンガポールの代理店のクリームから回す。シンガポールは減らし始めが 2029-W07 に早まる（前半の充足率 99.5％ → 95.3％、週の最低 60％は同じ）。未充足 0、年齢 52 週以内、工場の生産は同じ | 推奨（業務の要求の文のまま成り立ち、受入の条件をすべて満たす）。シンガポールの代理店に、減らし始めが早まることを受け入れてもらえるかが判断の中身 |
| 2 | **段階 7 の確認は別の担当に頼む** | 付録のスクリプトと入力で、T1〜T3 を独立に再実行して数字を照らす | 推奨。今回は計画を書いた担当が試行もしたので、独立性が無い |
| 3 | **知識の更新を段階 8 で反映する** | §7 の候補を Claude君へ渡す | 推奨。採否（1）と一緒に反映するとよい |

## 7. 知識の更新の候補（段階 8）

作業計画 §7 の 4 つに、試行で分かった 2 つを足す。

1. （計画から）Start Here から年齢の許容 52 週の業務の根拠（化粧品設計書 v0.5 の A6・COS-R05）への導線。
2. （計画から）意味体系 §6.1 に「lot が粗いと、比率と切り上げで最低が元の需要と同じになる」適用条件。化粧品のタイのクリーム：7 割＝10 割。
3. （計画から）`allocation_qty_P2a2.csv` が 2 つあること。最低供給量の試行と本試行は U4 の付録の方（`udp_plan.json` の `input_hashes` が一致するのはこちら）。
4. （計画から）依頼書の `knowledge_used` の版と正本の版の差。
5. （試行から）**最低で止まった削りは、同じ工場の週を使うほかの鍵の前の週へ繰り越される**。ある鍵の最低を上げると、ほかの鍵の減らし始めが早まり、作り置きが増える（化粧品 TH70：SG クリームが 12 週早まり、作り置きの lot・週が＋3.4％）。意味体系 §6.1 か R23 の例に。
6. （試行から）コードが変わっても（`6e4a534` → `7a67551`）、MS50 の台帳はバイト単位で再現した。再現の手順（付録の `th70_trial.py T1`）は、ほかの試行の基準の確認に使える。

## 8. BS-SEAF の記録

| 項目 | 中身 |
|---|---|
| 段階 | 段階 4（試行）。作業計画（段階 2〜3）を書いた担当が、大杉さんの決定 H2 で続けた |
| 時間 | 始め 06:45:12。T0 06:45、T1 06:47（1 回目は終わりの表示で文字コードの例外。道具の実行は済んでいたが、表示を直してやり直した）、T2 06:48、T3 06:49。付録と本書、commit メッセージの下書きを書き終えたのが 06:52 |
| 手戻り | T1 の表示の例外 1 回（Windows の端末の文字コード。`PYTHONIOENCODING=utf-8` で解消）。計画の中身の手戻りは無し |
| 誤り | 無し（作業計画 §9 の誤りは前の段階） |
| 人の橋渡し | 転記・連絡 0。git の操作 0（commit は大杉さん）。業務の判断：§6 の 3 件 |
| 根拠 | git の対象のファイルと、自分で実行した `output/bsseaf_cosmetics_th70/` の出力だけ。読まないでほしいと指定された 3 つのファイルは開いていない |

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-06 | 初版 |
| v0.1（追記） | 2026-11-06 | 大杉さんの決定 H3（TH70 の採用）を記録。§6 の 1 を決定済みに |
| v0.1（追記 2） | 2026-11-06 | 大杉さんの決定 H4（段階 7 は別の担当）を記録。段階 7 の依頼書を足した |
| v0.1（追記 3） | 2026-11-06 | 段階 7 の結果（設計担当の Claude君、報告と一致、独立性は弱い）と H5（段階 8 は設計担当の Claude君）を記録。この担当の作業は終了 |
