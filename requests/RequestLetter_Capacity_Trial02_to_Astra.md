# Request Letter：Capacity Trial-02 — 休業の表現と能力値の意味を確定するための追加検査

- 宛先：GPT-6 Astra君
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（大杉さんのレビュー後に送付）
- 種別：読み取り・測定のみ（実装なし）
- 前提資料：`WOM_Bottling_Capacity_Trial_Report.md`（Trial-01, WOM-CAPACITY-TRIAL-01）
- 測定基準：`4ed2f145dfb30b95058c0d274665eca64e4fc4c4`（Trial-01 と同じ。ブランチが進んでいても混ぜない）

---

## 1. この依頼の目的

Trial-01 は、Bottling_Noda の W17「予定S=686／実出荷=0」が遅配ではなく早出しの結果であること、同週数量差と Lot_ID 単位の未達が別の集合であることを、Lot_ID の追跡で示しました。この結論は受け入れます。

Trial-01 が「業務判断」として残した項目のうち、**休業（閉鎖）の表現**については、既に決まっている内容があります。今回はその決定を前提として、実装依頼に進む前に必要な事実を測ってください。

**問いは「どう直すか」ではなく、「既存の修正設計が現行コードにそのまま当てはまるか、当てはまらない所はどこか」です。**

## 2. 合意済みの前提（今回は議論の対象にしない）

| 項目 | 内容 | 出所 |
|---|---|---|
| cap_hard の意味 | 工程設備の物理的な処理能力の上限。特定の週だけ 0 になるものではない | 大杉さん 2026-09-27 |
| cap_soft の意味 | Planning Engine が使う計画上の操業能力。休業週は数値の 0 | 大杉さん 2026-09-27 |
| 休業の表現 | 能力値の特殊値ではなく、週の状態として表す | `docs/design/holiday_calendar_and_capacity_semantics.md` §3.1・§12 |
| `value=0.1` | 原因確認用の epsilon workaround。本番仕様にしてはならない | 同 §7 |
| 修正設計 | `docs/codex_requests/holiday_explicit_closure_engine_request.md`（Status: Ready for implementation、未実装） | 同ファイル |
| 操業カレンダー | `shifts == 0` を休業とする | `capacity_sealer.load_operating_calendar` docstring（2026-07-31 合意） |

補足：soysauce 4モデルの `value=0.1` は、Claude君が commit `2fc7f4b` で 1500 から変更したものです。上記 §7 が禁じている workaround を本番データへ広げたもので、今回戻す対象になります。

## 3. 現時点で Claude君が静的読解から立てている仮説

**以下は未確認の仮説です。検査で否定されれば、否定の方を記録してください。**

- **H1（脆い連鎖）**：2027/2028-W18 に Backward が S=0 を置くのは、休業を認識しているからではない。次の偶然の連鎖による。
  1. `_apply_supply_closure` が `set_capacity(w, cap_hard=0.1)` を呼ぶ。
  2. 既定引数によって cap_soft が 686 から 0（＝無制限）に上書きされる。
  3. `_apply_mom_cap_backward` の `demand_envelope == "soft" and cs > 0` が偽になる。
  4. `int(cap_hard) = int(0.1) = 0` の分岐に落ちる。
  - 補足：operating_calendar では W18 = 18直（開）。`is_closed` は op_shifts だけを見るため偽。explicit_closures は `_offset_week` でしか使われない。
- **H2（効いていない休業）**：`supply_closure` の `value=0.0`（Cookie / ev-europe / ev-thailand / iphone_global / smartx）は `cap_hard=0`＝無制限として扱われる。MOM ノードでは、Backward の充填目標でも Forward の封印でも休業が効いていない。leaf_in ノードは `on_post_backward` の P シフトで一部効いている可能性がある。
- **H3（value の多義）**：`supply_closure` の value が、モデルごとに異なる意味で使われている。
  - 完全休業：0.0 / 0.1
  - 絶対能力：150 / 700 / 1500 / 30
  - 割合らしきもの：rice の 0.3。ただしエンジンは 0.3 lot と読み、int で 0 になる。
  - 長期の実質停止：oil の 1.0
- **H4（1週差）**：Mode 4 の `push_lead_time_weeks=7` と、実伝播 LT（2+4=6）の差は、Bottling 自身の lt=1w を含めたかどうかの差である。push ノードの Forward は入庫週に出荷するため、全 lot が d−1 で出荷される。

## 4. 検査項目

### T2-1　H1 の反事実検査（Bottling_Noda × soysauce-jpy-2027-alloc）

1. 次の2条件で、Bottling_Noda の各週について Backward 後の Demand S/P、cap_hard、cap_soft、`is_closed`、充填目標（cap_int）を並べる。
   - (a) baseline
   - (b) 作業コピー上の monkeypatch のみで、休業適用時に cap_soft を上書きしない条件
2. (b) で W18 の S が 686 になれば H1 を支持する。0 のままなら、何が 0 にしているかを特定する。
3. Trial-01 と同じく、P_opt/800 と原需要の条件で行う。

### T2-2　休業の実効性の全数調査（H2・H3）

`holiday_calendar.csv` に `supply_closure` を持つ全モデル・全行について、次の表を作ってください。

| モデル | holiday_id | node | node_type | plan_mode | value | 適用後 cap_hard / cap_soft | 休業週の Backward S・P | 休業週の Forward P・実出荷（push は S−shortfall） | post_backward シフトの有無 | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|

- 判定欄は、**効いている／効いていない／部分的／判定不能** のいずれか。「効いている」の根拠は、そのノードの処理系列（push は実出荷、それ以外は P）が休業週に 0 であること。
- value が「休業」「部分操業」「割合」のどれを意図したものかは、推測で埋めないでください。`holiday_name` などの記述と数値だけを並べ、分類は大杉さんが行います。

### T2-3　能力値を読む全箇所の棚卸しと、既存修正設計との差分

1. `4ed2f14` で `cap_hard(` / `cap_soft(` を読む本番コードの全箇所（テスト・`.claude/` 配下を除く）について、次を1行ずつ記述する。
   - 0 の解釈（無制限／ゼロ／その他）
   - 休業を何で知るか（cap_hard の epsilon／op_shifts／explicit_closures／知らない）
   - push で skip するか
   - 結果の利用先
   - 参考：Claude君が数えた範囲では、backward_planner 2箇所、forward_planner 3箇所、capacity_sealer 3箇所、harvest_batch_plugin 3箇所、holiday_calendar_plugin 1箇所、strategic_kpi 1箇所、gui/app.py 4箇所、run_headless_from_folder 1箇所。
2. `holiday_explicit_closure_engine_request.md` の §3 Confirmed Current Behavior（基準 `2169bf6`）が `4ed2f14` でも成り立つか、項目ごとに成立／不成立／変化ありで答える。
   - 基準コミット以降の変化として、少なくとも Phase 2 の op_shifts、Kitting 回復（`7d6c7d7`）、S3 の処理量表示（`1bd6c44`）がある。
3. 同 §4 Decision D（Forward は休業週の production/receipt を通さない）が push ノードに当てはまるか。
   - Bottling_Noda の P は入庫、S は瓶詰・出荷の処理量です（Trial-01 §4）。
   - 休業週の P を止めた場合と、S だけを止めた場合で PSI がどう違うかを、作業コピーで比較してください。
   - どちらを採るかは大杉さんが決めます。

### T2-4　Mode 4 の週位置（H4）

1. push_config を持つ全モデルの push ノードについて、次を並べる：`push_lead_time_weeks`、経路 LT の合計、ノード自身の lt、観測した「要求週 d に対する入庫週・出荷週」のずれ。
2. `docs/design/push_production_lead_time.md` と `holiday_calendar_push_lead_time_and_planning_horizon.md` が、`push_lead_time_weeks` にノード自身の lt を含めると定義しているかを引用で示す。

### T2-5　E2E 未供給と PPC（Trial-01 §6 の続き）

1. soysauce-jpy-2027-alloc の `planning_config.csv` に warmup／reporting horizon の設定があるか。あれば、Trial-01 の 4,491（期間前への繰り戻し）と 4,802（Mode 4 の期間端）が報告期間の内か外かを分ける。
2. PPC が計上する 83,200 lot のうち、Bottling で一度も実出荷されない ID に対応する件数と、その売上・粗利の額を示す。
3. 評価をどう変えるべきかの提案は不要です。数字だけを出してください。

## 5. 成果物

1. 報告書 `WOM_Capacity_Trial02_Report.md`。Trial-01 と同じ体裁で、**観測／原因仮説／業務判断が必要** を分けて書く。
2. 測定スクリプト `tools/probe_capacity_trial02.py`。commit はせず、commit できる状態で渡す。`tools/probe_composite_baseline.py` と同様に、基準 SHA を照合し、core を変更しない。
3. 生データ（JSON/CSV）一式。**Trial-01 は生データが消失しました。** 今回は作業終了前に ZIP にまとめて大杉さんへ渡し、報告書に各ファイルのハッシュを記載してください。

## 6. 禁止事項と終了条件

- core・サンプル CSV 原本・golden を変更しない。反事実や置換は、作業コピー上の monkeypatch または複写データで行う。
- commit・push・PR をしない。
- 実装案や Request Letter の草案は書かない（次の段階で Claude君が既存 codex request を改訂する）。
- 検査できなかった項目は「未確認」とし、推測で埋めない。
- T2-1〜T2-5 の報告と生データの受け渡しで終了する。調査を自動的に延長しない。

## 7. 優先順位

時間が限られる場合は、**T2-1 → T2-3 → T2-2 → T2-4 → T2-5** の順で進めてください。

T2-1 と T2-3 は、次の実装依頼の前提になります。T2-5 は評価の数字に関わりますが、今回の休業修正とは独立です。
