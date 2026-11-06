---
handoff:
  case_id: BSSEAF-COS-LOOP4
  task_id: NEWAGENT-MINIMUM-SUPPLY-VERIFY-001
  role_from: verify            # 段階 7：試行を行っていない、別の担当（Claude Code、Claude Opus 5.5）
  role_to: owner
  target_commit: 7a6755103ad935a319fea00f9f598871d9265c68
  acceptance:
    ref: "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md §6"
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_Report.md
    - docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_appendix/
  decisions_used:
    - "H3（2026-11-06）：TH70 を化粧品の計画として採用"
    - "H4（2026-11-06）：段階 7 の確認は、試行を行った担当とは別の担当が行う"
  result: "V1 7 項目・V2 8 項目すべて一致。不一致 0、確かめられない 0（V2 の 7 は先入れ先出しの数え方そのものは道具に依存、§3）"
  open_items:
    - "TH70 の採用（H3）を見直す理由は見つからなかった。段階 8（知識の更新）へ進めるかは大杉さんの判断"
  stop_reasons: []
  next: owner
---

# 確認の報告書：BS-SEAF 化粧品 TH70 の試行の独立の確認（段階 7）

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_ThaiCream_Minimum70_Stage7_Verify.md` v1.0
- 確かめた対象：報告書 `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Report.md`、付録 `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/`
- 実施：試行の会話に加わっていない Claude Code（Claude Opus 5.5）、2026-11-06
- 時刻（端末の時計）：始め **08:50:42**、V1 の実行 08:51〜08:52、V2 の実行 08:53〜08:55、終わり **08:58**
- 実行した場所：`output/bsseaf_cosmetics_th70_verify/`（git の対象外）の写しだけ。試行の出力 `output/bsseaf_cosmetics_th70/` は開いていない
- 付録：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_appendix/`（V2 のスクリプト 2 本、結果の JSON、V1 の T1 の照合）

## 0. 結論

**報告書の数字と結論は、V1（付録のスクリプトの再実行）でも V2（スクリプトに頼らない別の道筋）でも、すべて一致した。不一致は無い。TH70 の採用（H3）を見直す理由は見つからなかった。**

- V1：T0〜T3 の出力（入力 3 ファイル、ハッシュ、台帳 5 つ×2 案、`udp_plan.json`×2、年齢の要約×2、比べる表と集計 4 ファイル）は、付録とバイト単位で一致した。
- V2：入力を自分のコードで作り直し（数量枠は別の P2-a2 のファイルから）、道具を直接実行し、集計も自分で書いた。台帳 5 つ×2 案は付録とバイト単位で一致し、報告書の 8 つの主張はすべて同じ値になった。
- 書き方の小さな点が 2 つある（§4）。結論には影響しない。

## 1. 使った環境

- Python 3.12.3（`C:\Users\ohsug\anaconda3\python.exe`）。`python` は Windows のストアの別名で動かなかったので、Anaconda を明示した。`PYTHONIOENCODING=utf-8`。
- commit `7a67551`。`udp_plan.json` の `code_dirty` は false（`wom`・`tools`・`data` に差分なし。`git_state()` の範囲は `wom/lovem/observer.py`）。

## 2. V1：付録のスクリプトの再実行

付録の `scripts/th70_trial.py` と `scripts/th70_measure.py` を `output/bsseaf_cosmetics_th70_verify/work/` に写し、`OUT` の 1 行だけを `output/bsseaf_cosmetics_th70_verify` に変えた（`diff` で差はこの 1 行だけ）。リポジトリの根から T0 → T1 → T2 → measure の順に実行した。

| # | 確かめたこと | 結果 | 根拠 |
|---|---|---|---|
| V1-1 | T0 の入力（`allocation_qty_TH70.csv`・`udp_policy_MS50TH70.csv`・`knowledge.json`） | **一致** | 付録 `inputs/` と `cmp` でバイト一致 |
| V1-2 | T0 のハッシュ（入力 6 つ＋写しの `capacity_plan.csv` 2 つ、`2ca7cf34…`） | **一致** | `t0_hashes.json` のハッシュ値 8 つが同じ（鍵の出力先の文字列だけ違う） |
| V1-3 | T1：MS50 の台帳 5 つが MinimumSupply の付録 `udp/MS50/` とバイト一致 | **一致** | 道具の終了コード 0、`T1 MATCH`。`output_hashes`・`input_hashes` も同じ。違う鍵は `code_dirty`・`knowledge_used`・`owner_decisions`・`target_commit`（付録 `records/t1_compare.json` と同じ 4 つ） |
| V1-4 | T1：MS50 の `udp_plan.json` が付録 `udp/MS50_reproduced/` と同じ | **一致** | 全鍵が等しい |
| V1-5 | T2：TH70 の台帳 5 つと `udp_plan.json` | **一致** | 終了コード 0。台帳 5 つはバイト一致、`udp_plan.json` は全鍵が等しい |
| V1-6 | 年齢の要約（MS50・TH70） | **一致** | `shelf_life_summary.csv` がバイト一致 |
| V1-7 | T3 の出力（`report_tables.md`・`th70_all.csv`・`cream_factory_stock_by_week.csv`・`measure.json`）と `*_pre.json` | **一致** | 4 ファイルはバイト一致。`*_pre.json` は出力先の文字列を含む行を除いて一致 |

V1 は、試行のスクリプトが同じ入力で同じ出力を出すことを確かめただけで、スクリプトの誤りは見つけられない（依頼書 §3）。それは V2 で確かめた。

## 3. V2：スクリプトに頼らない確認

試行のスクリプトは使わず、自分で書いた 2 本で確かめた（付録 `scripts/`）。

- `v2_run.py`：サンプルを写し、能力を `docs/scenarios/cosmetics.md` の C3a の表（美容液 17・14、クリーム 13・11）で書き直す。数量枠は **AllocationP2a の付録の `allocation_qty_P2a2.csv`**（試行が使った U4 の付録の写しとは別のファイル。`quota_source` 列が無く、値は同じ）から作り、作業計画 §5.1 のとおりクリームの SG を 666・TH を 299 にした。方針は `udp_policy_MS50.csv` の TH クリームの比率だけを 0.7 にした（`reason` は変えていない）。`tools.run_quantity_allocation` と `tools.shelf_life_check` を直接実行した（`--knowledge-file`・`--decision-ref` なし。引数は `--help` で確かめた）。
- `v2_check.py`：台帳を自分で読み、恒等式・最低供給量（比率から自分で切り上げ）・区間・充足率を数える。工場の生産と作り置きは、自分で書いた取り出しのプラグインで計画の木から数える。評価の額は P2-a の `make_allocation.py` の `CM` の表だけを読んで計算する。

| # | 報告書の主張 | 結果 | 根拠（`records/v2_check.json`） |
|---|---|---|---|
| V2-1 | T1：基準 MS50 の台帳 5 つが MinimumSupply の付録 `udp/MS50/` とバイト一致 | **一致** | 別の数量枠のファイル・知識の欄なしで実行しても、台帳 5 つはバイト一致。TH70 の台帳 5 つも付録 `udp/TH70/` とバイト一致 |
| V2-2 | TH70 の入力：クリーム SG 666・TH 299（合計は MS50 と同じ）、TH クリームの最低 0.7、ほかは MS50 と同じ | **一致** | `diff`：数量枠は 2 行だけ違い、691＋274＝666＋299＝965。方針の比率・端数・種類は TH クリームの 0.7 以外同じ。違うのは `policy_id`（MS50 → MS50TH70）と `reason` の文（§4 の 2） |
| V2-3 | 全行で ①＝②＋③、②＝④＋⑤。③ 192・④ 3,864・⑤ 0 | **一致** | 両案 1,384 行、違反 0。① 4,056、② 3,864、③ 192、④ 3,864（すべて当週、早出し・遅配 0）、⑤ 0 |
| V2-4 | タイのクリームは 104 週すべて当週に全量。ほかの最低のある鍵で下回る週 0 | **一致** | TH70：需要のある 104 週すべて当週 ④＝①（合計 299）。4 鍵とも、比率から切り上げた最低を、選んだ ② でも当週の ④ でも下回る週 0。週の最低の充足率 美容液 50%・50%、クリーム SG 60%、TH 100%（MS50 は TH 66.7%、104 週中 79 週が全量） |
| V2-5 | 変わったのは SG・TH のクリームだけ。SG クリームの減らす区間 2029-W07〜W50（44 週）、前半の当週の充足率 95.3％ | **一致** | 要求週ごとの全項目を比べ、違う鍵は `COS_Cream｜SG_Distributor` と `COS_Cream｜TH_Distributor` だけ。SG：③ 63 → 88、区間 2029-W19〜W50（32 週）→ 2029-W07〜W50（44 週、すべて 5 中 3）、前半 99.49% → 95.29%、後半 62.5% で同じ |
| V2-6 | 工場の週の生産は 173 週すべて MS50 と同じ。作り置きの lot・週は＋3.4％ | **一致** | 期間 2026-W37〜2029-W52（173 週）。MOM の P はクリーム・美容液とも違う週 0（クリーム 1,680、美容液 2,184）。supply point の I：クリームの最大 205（2027-W20）で同じ、lot・週 18,568 → 19,199（＋3.40％）、違う週は 2029-W03〜W45 の 43 週で TH70 が少ない週は 0、多い分の最大 25。美容液は全週同じ |
| V2-7 | 先入れ先出しの年齢の最大 28 週、52 週超 0 | **一致** | `shelf_life_check` を直接実行：両案とも納品 3,864、最大 28、52 週超 0。納品ごとのファイルから、週の番号の差で年齢を数え直して列と一致。納品週ごとの納品数が、台帳の要求週ごとの当週の ④ と一致。**注**：先入れ先出しの数え方そのもの（物の在る所ごとの待ち行列）は道具の実装で、独立には作り直していない |
| V2-8 | 評価の額の差 ＋35,100 円 | **一致** | 納品×24×単位の貢献の合計：821,460,960 → 821,496,060（差 35,100）。固定の 213,719,220 円を引くと 607,741,740 → 607,776,840。報告書の説明（(4,730 − 4,671.5)×24×25＝35,100）とも合う |

報告書のほかの数字も、V2 の結果で確かめられた範囲は一致した：Lot_ID の滞留の最大 144 → 169（参考の列）、作り置きの最大の週、TH クリームの MS50 の減らす区間 2029-W26〜W50（25 週）、MS50 の SG の減らす週のうち W19 だけ 5 中 4。

## 4. 書き方の気づき（結論には影響しない）

1. **数量枠のファイルの場所の書き方が 2 通り**：報告書 §1 の表は `--allocation-file inputs/allocation_qty_TH70.csv`、その下のコマンドは `output/bsseaf_cosmetics_th70/work/allocation_qty_TH70.csv`。中身は同じ（V1-1）なので、表の方は「付録 `inputs/` の写し」と分かるように書くと誤解が無い。
2. **「ほかの鍵の方針は MS50 と同じ」の範囲**：比率・端数・種類は同じだが、`reason` の文は全行で書き換わっている（「大杉さん P-2、2026-11-03」→「MS50 のまま」）。計画には効かない（V2 では `reason` を変えずに実行して、台帳がバイト一致した）。ただ、元の判断の参照先（P-2）が方針のファイルから消えるので、正式なサンプルへ反映するときは元の文を残す方がよい。
3. 参考：報告書 §7 の 3（`allocation_qty_P2a2.csv` が 2 つあること）は、V2 で両方とも同じ台帳を出すことを確かめた（入力のハッシュは違う）。知識の更新の材料として使える。

## 5. 変えたもの・変えていないもの

- 変えたもの（新しく作ったもの）：本書、付録 `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_appendix/`、commit メッセージの下書き `commit_msg_verify.txt`（`.gitignore` の対象）。実行の写しと出力は `output/bsseaf_cosmetics_th70_verify/`（git の対象外）。
- 変えていないもの：正式なサンプル、コード、golden、保護対象のコア、試行の報告書・付録・作業計画。`git diff --stat HEAD -- wom tools data tests` は空。git の操作はしていない。

## 6. 大杉さんに決めてほしいこと

| # | 一言の決定 | 中身 | 推奨と理由 |
|---|---|---|---|
| 1 | **TH70 の採用（H3）をそのまま保つ** | 確認で不一致は無かった | 推奨。V1・V2 とも全項目一致 |
| 2 | **段階 8（知識の更新）へ進める** | 試行の報告書 §7 の 6 つの候補に、本書 §4 の 2（`reason` の文）を足して Claude君へ渡す | 推奨。採用が確定したので、正式なサンプルへの反映の依頼と一緒にするとよい |

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-06 | 初版 |
