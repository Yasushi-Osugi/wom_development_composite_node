# Request Letter：BS-SEAF 化粧品の適用実験 — 第4段階（試行 2）：B2（店頭在庫・平準化）と変更課題⑤

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-25）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `75dff83`。着手時の SHA を報告書に記録する）
- 前提：
  - 設計書 `requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.3.md`（以下「設計書」。§6 D6〜D10、§8）
  - 前回の試行 `docs/development/WOM_BSSEAF_Cosmetics_Trial_Report.md`（以下「前回の報告書」）と、その写し・道具 `output/bsseaf_cosmetics/`（`gen_models.py`・`run_trial.py`・`shelf_life_check.py`）
- 種別：**コードを変えない試行**（前回と同じ）。`wom/`・`tools/`・`tests/`・`data/sample/` は変えない。写しと道具は `output/bsseaf_cosmetics/` に置く。テストは回さない。
- 範囲外：PPC の黙った見本への切り替え（設計書 D8）は別の依頼書にする。今回も金額は置かない（前回と同じく、金額のファイルは見出しの行だけ）。

---

## 0. 前回の試行を受けた大杉さんの決定（2026-10-25）

| # | 決定 |
|---|---|
| D6 | 店頭在庫を要件として残し、`init_stock_days`（X2）を `SG_Store` に置く（14 日＝2 週分） |
| D7 | 工場（`Factory_JP`）の `demand_envelope` を soft にする（大杉さんの定義 Ship_Qty ＝ Production_Qty（cap_soft）× 歩留まり に合わせる） |
| D9 | 残存期間の判定の道具は、まだ `output/` に置く |
| D10 | B2 を回してから、変更課題 ⑤ → ① → ② → ③ の順に進める。**今回は B2 と ⑤ まで** |

前回の試行は、設計書 v0.2 の誤り 2 つ（開店時の在庫が warmup では作られない、envelope が定義と合っていない）を見つけた（設計書 §8.2）。今回はそれを直した基準ケースで回し直す。

## 1. 作る写し

前回の `gen_models.py` を拡張して作ってよい（B0・B1 は消さずに残す）。

| 写し | B0 からの違い | 目的 |
|---|---|---|
| **B2**（新しい基準ケース） | (1) `sc_tree_master.csv` の `SG_Store` の行（2 SKU とも）に `init_stock_days`＝14。(2) `Factory_JP` の行（2 SKU とも）に `demand_envelope`＝soft | D6・D7 を入れた基準ケース |
| **B3**（変更課題⑤） | B2 の `Factory_JP` の `yield_rate` を 0.97 → **0.90**（それ以外は B2 と同じ） | 歩留まりで平準化の上限が需要を下回ったときの動き |

ほかの値（需要・能力・木・法人・warmup 17）は前回の B0 と同じ。

**予想（Claude君の手計算。合わなくても写しを予想に合わせて直さず、違いとして報告する）**：

- B2：工場の平準化の良品の上限は floor（cap_soft × 0.97）＝ Serum 13・Cream 10 で、ピーク週の需要と同じなので、工場の前倒しは起きない。`SG_Store` の lot は需要週の 2 週前に店に着き、I に並ぶ。定常の店頭在庫は Serum 8 lot・Cream 6 lot（2 週分）。直営店の lot の滞留は 6 週、ほかのチャネルは 4 週のまま。
- B3：平準化の良品の上限は floor（14 × 0.90）＝ 12（Serum）、floor（11 × 0.90）＝ 9（Cream）で、定常の週の需要（13・10）を毎週 1 lot 下回る。Backward が不足分を前の週の余裕へ押し戻し続けるので、**押し戻しが立ち上げの期間と warmup まで遡り、そこで作った lot が長い間待つ**。前倒しには上限が無い（Start Here §7）ので、滞留が許容の 52 週を大きく超える lot が出る見込み。押し戻しが計画の最初の週を越える分は past due（期末注文残）になりうる。cap_hard の良品の上限（floor（17 × 0.9）＝ 15、floor（13 × 0.9）＝ 11）は超えない。

## 2. 確かめること（B2・B3 の両方）

前回と同じ道具（`run_trial.py`・Flow Check・`shelf_life_check.py`）で回す。

| ID | 確かめること | 報告する値 |
|---|---|---|
| V01 | Flow Check の表 1：全ノードの数量の保存 | 全ノード OK か |
| V02 | `SG_Store` の 2027-W14 より前の実出荷 | 0 か |
| V03 | 開店直前（2027-W13）の `SG_Store` の I：lot 数と、すべて需要の Lot_ID 付きか（出どころの無い lot が 0 か） | SKU 別の lot 数 |
| V04 | 残存期間の判定（前回の §4.3 と同じ式。起点は工場の出荷週、比較として supply point の出荷週を起点にした値も） | 滞留の最小・最大・分布、52 週を超える lot の数。SKU 別・チャネル別。B3 では、52 週を超える lot がどの週に作られ、どこ（supply point・DC など）で待ったか |
| V05 | 全 lot が `WH_JP_Released` を通る | 前回と同じ |
| V06 | 工場の週の P の最大を **hard と soft に分けて**（設計書 §4 V06 v0.3）：(a) floor（cap_hard × y）以下か、(b) floor（cap_soft × y）を超えた週の数と `cap_soft_violation`・Backward の `cap_soft_envelope` の件数 | (a)・(b) を別々に |
| V07 | チャネル別の当週出荷・遅配・期末注文残（報告期間） | 表。B3 では past due の数も |
| V08・V09 | 前回と同じ | 前回と変わらないか |
| 在庫 | ノード別の在庫（I）の合計・最大。特に `SG_Store`（店頭在庫）、supply point（工場の作り置き、前回の報告書 Q5） | B2・B3 |
| 直販比率 | 数量基準（前回と同じ式） | B2・B3 |

あわせて、**B2 と B3 の違い**と、**B0 と B2 の違い**を短い表にする（どの値が、なぜ変わったか）。

## 3. BS-SEAF の記録

### 3.1 B2：前回の誤りを直した結果

設計書 §8.2 の E1（店頭在庫）・E2（envelope）について、直した後の Mapping が設計書 v0.3 §3.1 のとおりに表せたか、表せなかったら何が違ったかを書く。特に：

- X2 を leaf_out（`SG_Store`）に置いて、店頭在庫として I に立つか（X2 を leaf_out に置いたのは、どのサンプルモデルにも無い使い方）。
- 店頭在庫を「開店前から常に 2 週分」と読めるか。定常で減らないか、開店の前後でどう立ち上がるか。

### 3.2 変更課題⑤：知識の再利用と手間

前回の報告書 §5.3（手間の基準）と比べて：

- 変えた所（ファイル・行・値の数）と、かかった手間。
- 使った既存の知識（設計書 §2.4 の行、歩留まり Part A、前回の報告書の Q5 など）。
- 追加で確かめる必要があったこと。
- 対応の手段（Data／Parameter／Core）。Core の変更が要りそうな所があれば、変えずに報告する（例：前倒しの上限が無いことが、残存期間の業務の要件とぶつかる場合）。

## 4. 報告書

`docs/development/WOM_BSSEAF_Cosmetics_Trial_B2_Report.md` に次を書く：

1. 着手時の SHA。コードを変えていないこと（`git status`）。
2. 作った写し（B2・B3）と、§1 から外れた所。
3. §2 の結果（B2・B3）と、B0→B2・B2→B3 の違い。§1 の予想と合ったか（合わなければどこが違ったか）。
4. §3 の BS-SEAF の記録。
5. 第5段階で大杉さんに決めてほしいこと（例：B3 で前倒しが残存期間を割る場合の業務の扱い、次の変更課題①に進む前に直すこと）。

## 5. commit

この依頼書（`docs(request): …`）と報告書を別の commit にする。`output/` は commit しない。git は大杉さんが Windows で行う。commit メッセージの下書きは `commit_msg*.txt`（空いている番号を使う）。
