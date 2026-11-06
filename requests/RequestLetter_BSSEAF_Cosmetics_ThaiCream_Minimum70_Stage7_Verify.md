---
handoff:
  case_id: BSSEAF-COS-LOOP4
  task_id: NEWAGENT-MINIMUM-SUPPLY-VERIFY-001
  role_from: owner
  role_to: verify            # 段階 7：試行を行っていない、別の担当
  target_commit: 7a6755103ad935a319fea00f9f598871d9265c68   # 試行のときの commit。報告書・付録は未 commit の場合がある
  acceptance:
    ref: "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md §6（比べる項目と受入の条件）"
  decisions_used:
    - "H3（2026-11-06）：TH70 を化粧品の計画として採用"
    - "H4（2026-11-06）：段階 7 の確認は、試行を行った担当とは別の担当が行う"
  next: verify
---

# 依頼書：BS-SEAF 化粧品 TH70 の試行の独立の確認（段階 7）

- 版：v1.0（2026-11-06）
- 依頼：大杉さん（Owner）。下書き：試行を行った担当（Claude Code）

## 1. 目的

タイ向けクリームの最低 7 割（TH70）の試行の報告書が、主張している数字と結論を、**試行を行っていない担当**が自分で実行して確かめる。TH70 は採用済み（H3）。確認の結果で、採用を見直す必要があるかどうかを大杉さんが判断する。

## 2. 確かめる対象

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Report.md`（§0 結論、§2 比べる表、§3 受入の条件）
- 付録：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/`（入力、台帳、スクリプト）
- 受入の条件：作業計画 `requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md` §6

## 3. してほしいこと

### V1. 付録のスクリプトの再実行

付録の `scripts/th70_trial.py`（T0〜T2）と `scripts/th70_measure.py`（T3）を、**別の出力先**で実行する。スクリプトの出力先は `OUT = "output/bsseaf_cosmetics_th70"` と書いてあるので、写しを作って、その写しの出力先を `output/bsseaf_cosmetics_th70_verify` に変えて使う（元のスクリプトと付録は変えない）。結果の台帳と表が、付録と一致するかを照らす。

### V2. スクリプトに頼らない確認

試行のスクリプトの誤りは V1 では見つからない。報告書の次の主張を、道具（`tools/run_quantity_allocation`、`tools/shelf_life_check` など。引数は実物で確かめる）や自分で書いた短い集計で、別の道筋から確かめる。

1. T1：基準 MS50 の台帳 5 つが `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/udp/MS50/` とバイト単位で一致する。
2. TH70 の入力：数量枠はクリーム SG 666・TH 299（合計は MS50 と同じ）、方針は TH クリームの最低 0.7。ほかの鍵の枠・方針は MS50 と同じ。
3. 数量の恒等式：①＝②＋③、②＝④＋⑤ がすべての行で成り立つ。③ 192・④ 3,864・⑤ 0。
4. タイのクリームは 104 週すべてで当週に全量。ほかの最低のある鍵で、最低を下回る週は 0。
5. 変わった鍵は SG・TH のクリームだけ。SG クリームの減らす区間は 2029-W07〜W50（44 週）、前半の当週の充足率は 95.3％。
6. 工場の週の生産は 173 週すべて MS50 と同じ。作り置きの lot・週は +3.4％。
7. 先入れ先出しの年齢の最大は 28 週、52 週超は 0。
8. 評価の額の差は +35,100 円（比べるための値で、営業利益ではない）。

一致しないもの、確かめられなかったもの、報告書の書き方が誤解を招くものは、そのまま書く。直すのは報告書を書いた担当の役目なので、試行の報告書・付録は変えない。

## 4. 守ってほしいこと

- 正式なサンプル（`data/sample/cosmetics-sg-th-2027-2029`）、コード、golden、保護対象のコア、既存の報告書・付録は変えない。実行は `output/` の下の写しだけで行う。
- 試行の出力 `output/bsseaf_cosmetics_th70/` は根拠に使わない（照らす相手は、git の対象の付録）。
- ファイル名・関数名・CLI の引数は、実物で確かめてから書く。
- **commit はしない**（git の操作は大杉さんが行う）。commit メッセージの下書きを `commit_msg_verify.txt` に書く。
- 始めと終わりの時刻を記録する。

## 5. 出してほしいもの

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_Report.md`（冒頭に引き継ぎの欄。V1・V2 の項目ごとに「一致／不一致／確かめられない」と根拠）
- 付録（必要なら）：`docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_appendix/`
- 大杉さんに決めてほしいことがあれば、一言の決定と中身を並べて書く。

| 版 | 日付 | 内容 |
|---|---|---|
| v1.0 | 2026-11-06 | 初版 |
