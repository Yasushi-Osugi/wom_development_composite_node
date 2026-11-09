---
handoff:
  case_id: BSSEAF-COS-G2
  task_id: G2-D1-mapping
  role_from: design            # Claude君
  role_to: owner
  target_commit: f994f11
  knowledge_used:
    - id: G2 業務定義案（GPT-MC）
      version: v0.1
      applicability: "§1 適用範囲、§3 算定と計上週（案 A）、§4 代表 1 ロットと判定の例、§5 照合。大杉さんが 2 件とも採用（2026-11-09）"
    - id: G1 対応表・G1 報告書
      version: "v0.1 / 2026-11-08"
      applicability: "設定で表せる部分と改修を分ける作法、vc_sales_cost_rule.csv（C1〜C4）の仕組み"
    - id: G3 検証報告
      version: "2026-11-08"
      applicability: "代表の出荷 ID、外部卸売 2,340 件・443,922,960 円（付録 verify_g3_result.json の A1・A5）"
  acceptance:
    ref: "大杉さんの依頼（2026-11-09）：G2 の対応表"
  evidence:
    - docs/design/drafts/WOM_G2_Distributor_MDF_Business_Definition_v0.1.md
    - "コード確認（f994f11）：wom/valuechain/ledger.py _transfer・_price・_edge_costs・_consumer・_node_costs、masters.py load_sales_cost_rule、policy.py"
    - "G3 付録：docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_money_lines.csv（19 行目）、verify_g3_result.json"
  status: "判断済み（大杉さん 2026-11-09、§6 の 2 件とも推奨どおり）"
  open_items: []
  stop_reasons: []
  handover_notes:
    - "PPC は MDF を代理店の leaf の出荷の週（1 週遅い）に立てる。週は照合に使わず、金額の合計で照合する（G3 と同じ扱い）"
  next: implement   # requests/RequestLetter_BSSEAF_Cosmetics_G2_MDF_to_CodeKun.md
---

# G2（代理店向けの販促協賛金、MDF）業務定義案 v0.1 と、今の WOM の対応

- 版：v0.1（2026-11-09）
- 作成：Claude君（設計担当）
- 前提：G2 業務定義案 v0.1（GPT-MC）。**大杉さんの採用（2026-11-09）**：
  - **「初回は、卸売が成立した週に負担も確定すると置く」**（案 A）
  - **「税抜の卸売額の 5% を販促費として試算する」**（負担 1 件の金額は小数第 3 位を四捨五入して小数第 2 位まで）

---

## 0. 一言で

**卸売の売上は、もう正しい週・正しい法人に立っている。足りないのは、その同じ事象に「売上 × 5%」の販促費を 1 行添える処理だけで、G1 の仕組み（`vc_sales_cost_rule.csv`）を外部の卸売にも使えるように広げれば足りる。** コードを変えない検証も、写しのモデルで先にできる。

## 1. 今の WOM で分かったこと（コード）

| # | 事実 | 確かめ方 |
|---|---|---|
| F1 | 外部の代理店への卸売は、DC の出荷の週の **1 つの事象**（`_transfer`、`scope=external`・`price_type=wholesale`）。売り手は出荷するノードの法人（SG 向けは `E_SG`、TH 向けは `DC_TH` の法人 `E_JP`）、相手は外部の代理店。**業務定義の負担法人・受取先と同じ組** | `ledger._transfer`・`_price`、`vc_node_assignment.csv` |
| F2 | 代表の lot の卸売の行は 1 件：2028-W28、`E_SG` → `EXT_CH_SG_DIST`、1,488.0 SGD、`src_id` ＝ `ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6` | G3 付録 `rep_lot_money_lines.csv` 19 行目 |
| F3 | 外部卸売は全期間 2,340 件（SG 1,651・TH 689）、1 件の出荷に売上の行がちょうど 1 行、合計 443,922,960 円 | G3 付録 `verify_g3_result.json` の A1・A5 |
| F4 | 卸売の後、lot の記録は「グループの外」（`rec.external`）になる。代理店のノードの費用（`_node_costs`）は入荷の週に呼ばれるが、**外部の記録は最初の行で戻る**。そのため `ppc_node_cost_rule.csv` の MDF の行（`SG_Distributor`・`TH_Distributor`、`marketing_cost`、`basis=revenue`、5%）は、**計上もされず、issues にも出ない**。M0 で「費用にも一覧にも出なかった」理由 | `ledger._node_costs` の先頭 |
| F5 | 代理店から消費者への販売は「観測」（`observation_sale`）で、グループの売上ではない。G1 の売上比率の費用の処理は、グループの法人が売る分岐の中にだけあり、**観測の分岐では費用を立てない** | `ledger._consumer` |
| F6 | 区間の費用（`ppc_edge_cost_rule.csv`）で、グループ → 外部の区間の行は、**売り手の出荷の週の販売費**として計上される（例：`DC_SG->SG_Distributor` の運賃 0.3 SGD/個）。ただし額は「（率 ＋ 固定額）× 個数」で、**売上に率を掛ける計算は無い**。種類も運賃・保険・配送梱包だけ | `ledger._edge_costs`、`policy.EDGE_COST_FAMILY` |
| F7 | G1 の表 `vc_sales_cost_rule.csv` は「直販の leaf × SKU × 費目」で、読み込み時に **`channel_type` が `own`・`online` でなければ止める**。費目は `policy.SALES_COST_ITEMS` の 4 つ。PPC の行との率の突き合わせ（C4）が付いている | `masters.load_sales_cost_rule` |
| F8 | PPC は MDF を、代理店の leaf の出荷の週（代表の lot は 2028-W29）に、leaf の市場価格（62 SGD ＝ 卸価格と同じ）× 5% で集計している。全期間の額は Value Chain の外部卸売 × 5% と同じ 22,196,148 円 | `ppc_market_price.csv`、M0 報告書 T12、G1 報告書 §11 |
| F9 | 卸価格は SKU・区間ごとに 1 行ずつで、全期間一定（SG：クリーム 62・美容液 74 SGD、TH：クリーム 1,600・美容液 1,900 THB） | `vc_price_rule.csv` |

## 2. 対応表

### 2.1 代表の 1 ロット（業務定義 §4、案 A）

| 業務条件 | 現行の入力 | 根拠事象 | 現行の出力 | 満たせる範囲と差分 | 確認方法 |
|---|---|---|---|---|---|
| 対象は外部卸売。負担は売り手の自社法人、受取先は外部の代理店 | `vc_node_assignment.csv` | DC の出荷（`_transfer`、外部） | 卸売の行の `entity`＝売り手、`counterparty`＝代理店 | **満たす**（F1） | 代表の lot の卸売の行 |
| 算定基準 ＝ 税抜の卸売額 | `vc_price_rule.csv`（62 SGD） | 同上 | 卸売の行 1,488.0 SGD | **基準の金額はある**（F2） | 同上 |
| 負担 1 件・74.40 SGD を 2028-W28 に、`E_SG` の販売費として | `ppc_node_cost_rule.csv` の MDF 行（PPC 用） | 計上されない（F4） | 行なし。issues も無し | **差分（改修が要る）**：卸売の事象で「卸売額 × 率」を立てる処理が無い（F6・F7） | 改修後：費目 `distributor_mdf` の行が 1 件、`src_id` ＝ 卸売の出荷 ID |
| W29 の代理店の受入・代理店の出荷では追加 0 件 | — | 受入（`_receipt`）、観測の販売（`_consumer`） | 費用の行なし | **満たす**（F4・F5）。改修後も、観測の分岐で費用を立てないことを確かめる | 代表の lot の W29 に MDF の行が 0 |
| タイ：`E_JP` が 1,920.00 THB を 2029-W02 に | 同上 | `DC_TH` の出荷（外部） | 卸売の行（`E_JP` → `EXT_CH_TH_DIST`） | 売上は満たす。MDF は上と同じ差分 | タイの代表の lot で 1 件・1,920.00 THB（`E_JP` の機能通貨 JPY に換算した額も記録） |

### 2.2 判定の例（業務定義 §4 の表）

| 判定 | 今の WOM | 扱い |
|---|---|---|
| 対象外（直販の売上、グループ内の売上、代理店の消費者への販売の観測、代理店自身の費用） | それぞれ別の事象・別の分岐（F1・F5） | 改修は外部卸売の分岐だけに入れるので、自然に対象外になる。確認で数える |
| 負担なしと確認（明示の 0%） | 表に率 0 の行を書ける | 0 円の行が 1 件立つ（「確定額 0」として区別できる） |
| 判定保留（卸価格が無いなど） | 卸価格が無ければ、卸売の行が未評価（NaN）になり、未設定価格の一覧に出る | MDF の行も未評価（NaN）にする。0 円にしない（G1 と同じ） |
| 案 B の「承認前」 | 承認の記録は計画データに無い | **今回は扱わない**（大杉さんの採用は案 A） |

### 2.3 照合（業務定義 §5）

| 業務条件 | 確認する出力 | 確かめ方 |
|---|---|---|
| 同じ協賛負担は 1 件 | `vc_money_lines.csv.gz` の `kind=expense`・`scope=selling`・`price_type=distributor_mdf` | 卸売の出荷 ID（`src_id`）× 費目で数えて、すべて 1 行。件数 2,340 |
| 負担法人と受取先 | 同上の `entity`・`counterparty` | SG 1,651 件は `E_SG` → `EXT_CH_SG_DIST`、TH 689 件は `E_JP` → `EXT_CH_TH_DIST` |
| 計上の週 ＝ 卸売の週 | 卸売の行と MDF の行の `week` | 2,340 件すべて同じ週 |
| 金額 ＝ 卸売額 × 5% | 卸売の行と MDF の行の `amount_orig` | 2,340 件すべて一致（丸めの後） |
| 全期間の合計 | MDF の行の円の合計 | **22,196,148 円**（SG クリーム 6,451,224・SG 美容液 9,160,164・TH クリーム 2,583,360・TH 美容液 4,001,400） |
| PPC と比べる | `vc_ppc_comparison.csv` の利益の差（Value Chain − PPC） | **22,196,148 円 → 0 円**。差が残れば止める理由。PPC は 1 週遅い週に立てるので、週ごとの一致は条件にしない |
| 再計算でも同じ | 同じ入力で 2 回実行 | 明細のハッシュが同じ |

## 3. 最小の改修（差分だけ）

G1 の仕組みを外部卸売にも使えるようにする。新しい表は作らない。

| # | 変更 | 中身 |
|---|---|---|
| D1 | **費目を一つ足す** | `policy.SALES_COST_ITEMS` に `distributor_mdf`（代理店向け販促協賛費（MDF））。PPC での種類は `marketing_cost` |
| D2 | **表を外部の代理店の leaf にも使えるようにする** | `vc_sales_cost_rule.csv` の読み込みで、`channel_type=external` の leaf も受け付ける。その場合だけ、費目は `distributor_mdf` に限る。通貨は、その leaf に入る卸売の区間の卸価格（`vc_price_rule.csv`）の通貨と同じであることを確かめる（直販は今どおり市場価格の通貨）。PPC の行との率の突き合わせ（C4）はそのまま使う（`SG_Distributor` の `marketing_cost` 5% ＝ 表の 5%） |
| D3 | **卸売の週に計上する** | `_transfer` で、外部チャネルへの卸売の売上の行の直後に、受け手の leaf の表の行ごとに「卸売額 × 率」を、**売り手の販売費**（`kind=expense`・`scope=selling`、`family=marketing_cost`、`price_type=distributor_mdf`、相手＝代理店、`src_id`＝卸売の出荷 ID）として 1 行ずつ立てる。金額は取引通貨で小数第 2 位に四捨五入（大杉さんの採用）。卸売額が未評価なら NaN。`node` は売り手の出荷ノード（`DC_SG`・`DC_TH`。今の区間の販売費と同じ）にし、`note` に販促の対象の leaf を書く |
| D4 | **黙って落ちないようにする** | 外部チャネルの leaf に `ppc_node_cost_rule.csv` の `basis=revenue` の行があり、表に行が無いときは、issues に `revenue_based_cost_on_external_channel_not_booked`（ノード・SKU・種類ごとに 1 件）を出す。表があれば出さない。今のサンプルで当たるのは化粧品だけ（`data/ppc` の売上比率の行はスマートフォンの製品で、Value Chain のマスターを持つモデルに無い） |

変えないもの：PPC のコードと規則のファイル、保護対象のコア、golden（Planning と PPC の snapshot）、ほかのサンプル（表が無いので今の動き）。G1 の直販の行の結果は 1 行も変わらないこと（MDF の行と `line_id` の列を除いた明細で確かめる）。

取らなかった案：
- **区間の費用の行で表す案**（`DC_SG->SG_Distributor` の 1 個当たりの額に 3.10 SGD を足す）：卸価格が一定の今は額が合うが、価格が変われば合わなくなり、名前も運賃になる。PPC も区間の行を読むので、PPC に MDF が二重に入る。検証（T1）にだけ使う。
- **G2 用に別の表を作る案**：「売上比率の費用は、その売上の週に、売り手の販売費として費目ごとに 1 行」という意味は G1 と同じで、PPC との突き合わせ（C4）も共通に使える。表が二つになると、同じ PPC の行を二か所で照らすことになる。

## 4. 最小の試行案

| 段 | 中身 | コード | 合格 |
|---|---|---|---|
| T0 | 今の正式なサンプルで Value Chain を実行し、基準を記録（代表の 2 lot の明細、issues、利益の差 22,196,148 円） | 変えない | G1 の段階 6 の結果と同じ |
| T1 | **写し**のモデルで、`DC_SG->SG_Distributor` と `DC_TH->TH_Distributor` の既存の運賃の行（`logistics_cost`）の 1 個当たりの額に、卸価格の 5% を足して実行（SG：0.3 → クリーム 3.40・美容液 4.00 SGD、TH：8 → クリーム 88・美容液 103 THB）。同じ区間・同じ種類の行を 2 行書くと読み込みで止まるため、行は足さない | 変えない | その区間の販売費の行が、T0 より代表の lot で 74.40 SGD、タイの代表の lot で 1,920 THB 増え、どちらも卸売の週の 1 件のまま。全期間の増加は 2,340 件・22,196,148 円。**PPC の出力は比べない**（PPC も区間の行を読むので変わる） |
| T2 | D1〜D4 を入れ、写しのモデルに表の 4 行を足して実行 | 改修 | §2.3 の全項目。D4：表が無い写しでは issues が 4 件、表があれば 0 件。MDF の行と `line_id` の列を除くと、明細は T0 と同じ（行が増えると `line_id` の番号がずれる）。PPC の出力は T0 とバイト単位で同じ。テストと golden が通る |
| 段階 6 | 正式なサンプルに表の 4 行を足す（G1 と同じ流れ） | — | 利益の差 0 円。README の「既知の限界」の G2 を解決済みに |

表に足す 4 行（案）：

```
SG_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05,SGD,代理店向け販促協賛費 5%（負担：シンガポール販社）
SG_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,SGD,代理店向け販促協賛費 5%（負担：シンガポール販社）
TH_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05,THB,代理店向け販促協賛費 5%（負担：日本本社）
TH_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,THB,代理店向け販促協賛費 5%（負担：日本本社）
```

## 5. 先に確かめたことと、Code君に確かめてもらうこと

- 確かめた（コードを読んだ）：F1〜F9。区間の費用の行は「区間・SKU・種類」で一意で、同じ種類を 2 行書くと読み込みで止まる（`masters.py`）。
- Code君に確かめてもらう：
  - 卸売の行を立てる箇所で、受け手の leaf の名前（`s.to`）と、その表の行を取れること。
  - `views.py` のノード別・法人別の集計で、`node=DC_SG` に置いた MDF の行が `E_SG` の販売費に入ること（区間の運賃の販売費と同じ扱い）。
  - 丸めは今のサンプルの値では差が出ない（卸価格 × 24 × 0.05 はどれも小数第 2 位までで割り切れる）。丸めの処理そのものは単体テストで確かめる。

## 6. 大杉さんに決めてほしいこと

| 一言で | 中身 | 推奨 |
|---|---|---|
| **G2 の費目は G1 と同じ表に書く** | `vc_sales_cost_rule.csv` を外部の代理店の leaf にも使えるようにし、費目 `distributor_mdf` を足す（§3 の D1〜D3）。「売上比率の費用は、その売上の週に、売り手の販売費」という意味が同じで、PPC との率の突き合わせも共通に使える | 推奨 |
| **黙って落ちる売上比率の費用は、一覧に出す** | 外部の代理店の leaf に PPC の売上比率の行があり、Value Chain の表が無いとき、issues に出す（D4）。今は計上もされず一覧にも出ない（M0 で見つけにくかった理由）。当たるのは化粧品だけ | 推奨。黙った既定値を作らない原則と同じ |

**決定（大杉さん 2026-11-09）：2 件とも推奨どおり。** Code君への依頼書：`requests/RequestLetter_BSSEAF_Cosmetics_G2_MDF_to_CodeKun.md`

## 7. 申し送り

- G1 の直販の行には丸めの規則が無い（G2 だけ小数第 2 位）。今のサンプルの値ではどちらも差が出ない。揃えるかは、実績の取り込みで端数が出る段階で決める。
- 案 B（販促の実施・承認で確定）は、承認の記録の入力が要る。実績の取り込みの論点として残す。
- 売上の割戻しとして扱う契約（業務定義 §3.1）は、売上の減額の行になる別の設計。今回は扱わない。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-09 | 初版。同日、§6 の 2 件の決定を記入 |
