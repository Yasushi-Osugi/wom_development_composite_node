# Request Letter：BS-SEAF 化粧品 — 金額の仮定を規則のファイルに置く（M0）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-30）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `60ca059`。この依頼書は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：`requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md`（以下「仮定」。大杉さんの判断 M1〜M8、2026-10-30）、判断 J4 の (3)、D8 の実装 `7cfc857`
- 種別：**コードは変えない**（Data だけ）。写しは `output/bsseaf_cosmetics/`（git の対象外）。コードの変更が要ると分かったら、変える前に止めて報告する

---

## 0. 目的

仮定の金額を、化粧品のモデルの規則のファイルに置き、**PPC が `評価済み` になり、1 個当たりの損益が仮定 §6 の表と合う**ことを確かめる。合わなければ、どの費用・どの区間で違うかを説明する（PPC・Value Chain の計算の仕方が仮定と違うのか、置き方が違うのか）。

金額の値は仮定のとおりに置き、**数字を合わせるために値を変えない**。

## 1. 写し

| 写し | 元 | 変えるもの | 目的 |
|---|---|---|---|
| **M0** | `output/bsseaf_cosmetics/C3b`（タイあり、能力を足した案。注文残 0） | 規則のファイル（§2）を置く。タイの関税 0% | 金額の流れの確かめ（注文残の影響を受けない） |
| **M0t** | M0 | タイの関税（`WH_JP_Released → DC_TH`）を 30% に | 仮定 M4 の感度 |
| **M0a** | `output/bsseaf_cosmetics/C3a`（能力そのまま。注文残 192） | M0 と同じ規則のファイル | 注文残があるときの金額（届かなかった lot に売上が立たないこと） |

写しは `gen_models.py` の `build()` に金額の引数を足して作ってよい（前回までと同じやり方）。元の C3a・C3b は変えない。

## 2. 置くもの（値は仮定のとおり。単位は 1 個当たり）

| ファイル | 中身 | 仮定の節 |
|---|---|---|
| `ppc_fx_rate.csv` | JPY 1.0・SGD 115・THB 4.5・USD 150（基準通貨 JPY）。**計画期間の全ての週に行を置く**（Value Chain の為替は週が一致する行を引き、表の後の週は未評価になる。R11） | §1 |
| `ppc_market_price.csv` | 直営店 SGD 165／138、EC SGD 157／131、代理店（シンガポール）SGD 74／62、代理店（タイ）THB 1,900／1,600。週は計画の最初の週から | §2.2 |
| `vc_price_rule.csv` | `wholesale`：`DC_SG→SG_Distributor` SGD 74／62、`DC_TH→TH_Distributor` THB 1,900／1,600。`intercompany`：`WH_JP_Released→DC_SG` JPY 6,000／5,000 | §2.2・§2.3 |
| `ppc_supplier_cost.csv` | `Materials_JP` JPY 1,500／1,300 | §3 |
| `ppc_transfer_price_rule.csv` | `Factory_JP`：`fixed`、JPY 6,000／5,000（関税の課税価格に使う。タイの関税の感度の基準） | §2.3・§4.3 |
| `ppc_node_cost_rule.csv` | `Factory_JP` 加工費 JPY 700／600、`WH_JP_Released` JPY 30、`DC_SG` SGD 0.50、`DC_TH` THB 12、`SG_Store` 運営費 売上の 35%・販社の販管費 売上の 10%、`SG_EC` 手数料 5%・販管費 10%・デジタル広告 15%・配送 SGD 3.00、代理店 2 か所 MDF 売上の 5%。**費用の無い実在のノードにも 0 の行**（M7） | §3・§4.2 |
| `ppc_edge_cost_rule.csv` | 区間の運賃（仮定 §4.1）。`Materials_JP→Factory_JP` は 0 の行 | §4.1 |
| `ppc_tariff_rule.csv` | `WH_JP_Released→DC_SG` 0%、`WH_JP_Released→DC_TH` 0%（M0t は 30%）。課税の基準は `transfer_price`。日本の中の区間にも 0% の行を置くかは §3 の B3 で確かめて決める | §4.3 |
| `ppc_profit_zone_rule.csv`・`ppc_node_profit_zone.csv` | 置かない（見出しの行だけ）。損益の帰属の表示用で、今回の確かめに要らない。`評価済み` の判定に要るなら、止めて報告する | — |

**置き方の約束**：

- 1 個当たりの費用は、意味の取り違えの無い基準で書く。PPC の `per_lot` は、名前に反して**物量当たり**（1 個当たり）に効く（R7。`ppc_backward.py` の `per_lot / fixed` は `fixed_amount` をそのまま使い、PPC が数量 × `cpu_size` を掛ける）。§3 の B2 で `qty` と `per_lot` の意味を確かめ、1 個当たりを表すのに誤読の少ない方を使う。
- `SG_EC` の配送費は leaf の先の区間が無いのでノードに置くが、`cost_type` を `logistics_cost` にしない（Value Chain のローダは、ノードに運賃があると止まる。R8）。`selling_cost` などの販売費にする。
- 区間・ノードの ID は、木（`sc_tree_master.csv`）と、既存のモデル（Cookie）の書き方から確かめる。
- 直営店の運営費 35% は**近似**（M5）。報告書・結果の表に「近似（固定費を売上の率で置いた）」と明記する。

## 3. 先に確かめること（コードを読んで。違えば止めて報告）

| # | 確かめること |
|---|---|
| B1 | PPC の市場価格と、Value Chain の価格の関係。代理店（外部のチャネル）の leaf の `ppc_market_price.csv` の行（PPC の売上になる）と、`vc_price_rule.csv` の `wholesale` の行（Value Chain の販社の売上になる）が、同じ値で矛盾なく読まれるか。Value Chain が外部のチャネルの leaf の市場価格を何に使うか |
| B2 | ノード・区間の費用の `basis`（`per_lot`・`qty`・`revenue`・`fixed`）の意味を、PPC（`ppc_backward.py`・`ppc_forward.py`）と Value Chain（`wom/valuechain/ledger.py`）の両方で。`revenue` の売上が、どの価格（leaf の市場価格か、区間の価格か）を指すか |
| B3 | PPC の連結の利益（KPI）が、どう組み立てられるか。とくに `ppc_transfer_price_rule.csv` の振替価格が、原料・加工の費用と二重に数えられないか（Cookie の例で、売上 − 原価の積み上げが KPI と合うか）。関税の行が無い区間の扱い（0% の行を置くべきか） |
| B4 | `評価済み` の判定（D8）が、化粧品の全ての製品 × 市場 × 週で通るか（`price_before_first_rule_week` が 0 になるように、規則の週を計画の最初の週から置く） |

## 4. 確かめること

| # | 確かめること | 出どころ |
|---|---|---|
| V1 | M0・M0t・M0a で PPC が `評価済み`。`excluded` が空、`price_before_first_rule_week` が 0 | `ppc_kpi_summary.json` |
| V2 | **1 個当たりの損益**：チャネル × SKU ごとに、PPC の台帳から売上・費用・利益を 1 個当たりに直し、仮定 §6 の表（グループ連結、関税 0%）と並べる。差があれば費用の項目ごとに分けて理由を書く | PPC の台帳（`ppc_event_ledger.csv` など） |
| V3 | **Value Chain**（`python -m tools.valuechain_run`）：保存の検査 OK。連結（V3）の外部の売上が PPC の売上と合う。法人の損益（V2）で、シンガポール販社の仕入れ（グループ内の価格 6,000／5,000 円）と日本本社のグループ内の売上が対になり、連結で消える。代理店（タイ）の売上は日本本社に立つ。`compare_with_ppc()` の差を項目ごとに説明 | Value Chain の出力 |
| V4 | 費用の規則の行が当たらない組合せ（D8 の `lookup_log`、報告書 §6.1 と同じ数え方）が、仮想のノード（supply point）だけ | 道具で数える |
| V5 | M0t：タイの代理店の 1 個当たりの利益が、関税のぶん下がる（美容液 約 1,821 円 ＝ 30% ×（6,000 ＋ 70）。課税価格の決まり方が仮定と違えば、その違いを書く）。ほかのチャネルは M0 と同じ | PPC の台帳 |
| V6 | M0a：届かなかった lot（⑤ 192）に売上が立たない。売上の lot 数が ④（3,864）と合う。M0 との売上の差が、⑤ の lot × 単価で説明できる | Flow Check 表2、PPC |
| V7 | 数量の結果（Flow Check 表2）が、元の C3b・C3a と同じ | Flow Check |
| V8 | 年の売上の規模（定常の 1 年、シンガポール）が、仮定 §6 の「週に約 SGD 61,000」と同じ程度 | PPC |

まとめの表（報告書 §3）：チャネル × SKU の 1 個当たりの 売上・費用・利益・利益率（PPC の値と仮定 §6 の値を並べる）、全体の売上・利益（JPY）、直営店の運営費の額（近似と明記）、M0t の差、M0a の差。

## 5. 止める理由と申し送り

報告では、**止める理由**（動き・数字・誤読に関わる。先に直す）と**申し送り**（記録して進む）を分ける。些細なものは往復させずに直して報告だけにする。

止める理由に当たるもの：

- §3 の確かめで、仮定のとおりに置けないもの（PPC・Value Chain に表す方法が無い、二重に数える）。コードを変える前に報告する
- V1 で `評価済み` にならない
- V2 の差が、費用の項目で説明できない

申し送りの例：`per_lot` の名前の誤読（物量当たりに効く）を全体で直すかどうか、固定費（仮定 §7）を実装するときに要るもの。

## 6. BS-SEAF の記録（報告書 §4）

前回までの表と同じ形で：変えたファイル・行・値の数、かかった手間（迷った所）、使った既存の知識（Start Here の R7・R8・R11・R12・R22、Cookie の README など）、追加で確かめたこと、手段（Data／Parameter／Core／道具）、見込みどおりか。どの文書から置き方に辿り着いたかも書く。

## 7. 報告書と commit

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md`。着手時の SHA、§3 の結果、置いた規則のファイルの中身（付録に表で）、§4 の結果（実行した後の数を書く）、止める理由と申し送り、大杉さんに決めてほしいこと（あれば）。
- 写し・道具の出力は `output/` に置き、commit しない。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に書く。git の操作は大杉さんが行う。

## 8. この後

M0 で金額が流れたら、配分の試行 P2（利益で配分を選ぶ。判断 J4 の (4)）に進む。その前に、配分の判断の基準（意味体系 U3：利益率か額か、貢献利益で比べるか）を大杉さんと決める。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-10-30 | 初版 |
