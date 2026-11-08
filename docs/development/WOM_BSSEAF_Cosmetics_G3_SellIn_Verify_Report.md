---
handoff:
  case_id: BSSEAF-COS-G3
  task_id: G3-T1-verify-sellin-recognition
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  target_commit: aac46b4
  knowledge_used:
    - id: G3 業務定義（GPT-MC）
      version: v0.1
      applicability: "§4 期待結果、§5 重複防止の条件。代表 Lot COS_Cream:SG_Distributor:2028-W29:00002"
    - id: WOM-SEM-SUPPLY-ALLOCATION-001
      version: "0.7"
      applicability: "受渡点・実納品の意味（実出荷＝vc_shipments の ship_week、受入＝その arrival_week）"
  acceptance:
    ref: "requests/RequestLetter_BSSEAF_Cosmetics_G3_SellIn_Verify_to_CodeKun.md §5"
    result: "S1〜S5 すべて合格"
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/verify_g3.py
    - docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/verify_g3_result.json
    - docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_money_lines.csv
    - docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/rep_lot_shipments.csv
  status: "合格（コードの変更なし）"
  open_items:
    - "PPC は代理店の leaf の出荷の週（W29）に売上を立てる。D-2 にそろえるかは別の判断"
    - "「記録の欠落で未確認」は計画から作る出荷には無い。実績の取り込みのときの論点"
  stop_reasons: []
  next: owner
---

# 報告書：G3 業務定義（sell-in の売上の計上週）を、今の WOM で満たすかの検証

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_G3_SellIn_Verify_to_CodeKun.md` v0.1（2026-11-08）
- 業務定義：`docs/design/drafts/WOM_G3_SellIn_Business_Definition_v0.1.md`（GPT-MC、大杉さんの採用判断 D-2 を反映）
- 実施：Code君（Claude Code、Windows）、2026-11-08
- 付録（再現用、git の追跡対象）：`docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/`
- 種別：検証だけ。コード・正式なサンプル・golden・保護対象のコアは変えていない

## 0. 結論

**今の Value Chain は、改修なしで G3 業務定義（D-2：DC の実出荷の週に、シンガポール販社が卸売の売上を 1 件だけ計上する）を満たす。** 合格の条件 S1〜S5 はすべて合格。止める理由には当たらなかった。

| # | 条件 | 結果 |
|---|---|---|
| S1 | サンプルが書き換わらない・代表 Lot の週が前提と同じ（B1〜B3） | **合格** |
| S2 | 代表 Lot（L1〜L4、業務定義 §4） | **合格**：2028-W28 に 1 件・1,488 SGD、2028-W29 は 0 件 |
| S3 | 全部の卸売（A1〜A5、業務定義 §5 の 1・2） | **合格**：2,340 件の出荷すべてで売上の行が 1 件、週・金額が一致、合計 443,922,960 円 |
| S4 | 再取込・再計算（R1・R2、業務定義 §5 の 3） | **合格**：明細の中身が 3 回とも完全に同じ（97,682 行） |
| S5 | コード・サンプル・golden・コアの変更なし | **合格**：`git status --untracked-files=all` に出るのは報告書と付録 4 ファイルだけ（commit の下書き `commit_msg195.txt` は git の対象外で表示されない） |

残る差は 2 つで、どちらも申し送り（§5）：PPC は leaf の出荷の週（W29）に売上を立てる別の方式のまま。「記録の欠落で未確認」は計画から作る出荷には無い。

## 1. 着手時の記録

- **着手時の SHA**：`aac46b4`（依頼書の commit。依頼書の `target_commit` は `7777b2a`）。`7777b2a..aac46b4` は文書の追加だけ（業務定義・役割の定義・この依頼書）で、`wom/`・`tools/`・`data/sample/` に差分は無い。
- **作業ツリー**：着手時 clean。
- **環境**：Windows 11、Python 3.12.3（Anaconda）、pandas 2.2.2、numpy 1.26.4。PATH の `python` は Windows Store の入口だけで動かないため、Anaconda の python を PATH の先頭に置いて実行した。
- **時刻**：始め 11:38、終わり 11:45 前後（2026-11-08、端末の時計）。Value Chain の実行は 1 回 約 12 秒。

## 2. 先に確かめたこと（B1〜B3）

| # | 結果 |
|---|---|
| B1 | `data/sample/cosmetics-sg-th-2027-2029` は M0 をそのまま正式なサンプルにしたもの（README）で、`vc_*.csv` 4 本（価格・法人・ノードの割り当て・設定）を持つ。3 回の実行の前後で、28 ファイルすべての sha256 が同じ（`output/g3_verify/sample_hash_before.txt` と照合）。`tools/valuechain_run.py` はモデルを一時フォルダに複写して計画する作り |
| B2 | 引数：`--model-dir`（必須）、`--out`（必須）、`--plugins`（既定＝golden の組）、`--lovem-run`（任意）。出力：`vc_money_lines.csv.gz`、`vc_shipments.csv.gz`、`vc_v1/v2/v3_weekly.csv`、`vc_observation_weekly.csv`、`vc_ppc_comparison.csv`、`ppc/` ほか。実行の表示は 3 回とも conservation OK・外部売上の恒等式 True・価格の欠落 0・未評価 0・issues 2,470（M0 の G1 の販売費が入らない件。G3 とは無関係） |
| B3 | 代表 Lot `COS_Cream:SG_Distributor:2028-W29:00002`：DC の出荷 **2028-W28**、受入（その出荷の到着の週）**2028-W29**、leaf の出荷 **2028-W29**。業務定義の前提と同じ |

## 3. 再現の手順

```powershell
python -m tools.valuechain_run --model-dir data\sample\cosmetics-sg-th-2027-2029 --out output\g3_verify\run_1
Copy-Item output\g3_verify\run_1 output\g3_verify\run_1_first -Recurse
python -m tools.valuechain_run --model-dir data\sample\cosmetics-sg-th-2027-2029 --out output\g3_verify\run_1
python -m tools.valuechain_run --model-dir data\sample\cosmetics-sg-th-2027-2029 --out output\g3_verify\run_2
python docs\development\WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix\verify_g3.py --g3-dir output\g3_verify --sample-dir data\sample\cosmetics-sg-th-2027-2029 --out docs\development\WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix
```

サンプルのハッシュは、1 回目の前に `sha256sum` で `output/g3_verify/sample_hash_before.txt` に取った。検証のスクリプトは出力のファイルとサンプルの `vc_price_rule.csv` を読むだけで、WOM のコードを import しない。依頼書が付録として挙げた `scripts/verify_g3.py` は依頼書に同梱されていなかったので、Code君が書き、付録に置いた。

## 4. 照らした明細

### 4.1 代表の Lot（業務定義 §4）

この Lot の明細は全部で 24 行（付録 `rep_lot_money_lines.csv`）。卸売の区間 `DC_SG → SG_Distributor` に関係する行：

| week | kind | scope | family | price_type | entity | counterparty | node | amount_orig | currency_orig | src_id |
|---|---|---|---|---|---|---|---|---:|---|---|
| 2028-W28 | **revenue** | **external** | sale | wholesale | E_SG | EXT_CH_SG_DIST | DC_SG | **1488** | SGD | `ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6` |
| 2028-W28 | cogs | external | sale | wholesale | E_SG | EXT_CH_SG_DIST | DC_SG | 122820（v1）・122820（entity）・48900（group） | JPY | 同上 |
| 2028-W28 | expense | selling | freight／tariff | logistics_cost／tariff_cost | E_SG | EXT_CH_SG_DIST | DC_SG | 7.2 SGD／0 | | 同上 |
| 2028-W29 | observation_sale | observation | sale | market | EXT_CH_SG_DIST | CONSUMER:SG_Distributor | SG_Distributor | 1488 | SGD | `ship:COS_Cream:OUT:leaf_out:SG_Distributor:COS_Cream:97:1` |

| # | 期待 | 結果 |
|---|---|---|
| L1 | revenue・external が 1 行、W28・DC_SG・E_SG・外部代理店・wholesale・1,488 SGD | **1 行**。すべて一致（counterparty は `EXT_CH_SG_DIST`＝代理店（シンガポール）） |
| L2 | 2028-W29 の revenue が 0 行 | **0 行** |
| L3 | observation_sale が 1 行（W29、SG_Distributor）、売上に入らない | **1 行**。scope=`observation`、basis=`obs`（v1・entity・group のどの集計にも入らない） |
| L4 | 出荷・受入・leaf の出荷が同じ Lot_ID でたどれ、L1 の src_id が出荷の ID と一致 | `vc_shipments` の `DC_SG → SG_Distributor`（ship_id `…DC_SG:COS_Cream:96:6`、ship 2028-W28、arrival 2028-W29）と leaf の `consumer_sale`（ship 2028-W29）が同じ Lot_ID。L1 の src_id ＝ その ship_id |

注：WOM の出荷の記録に「受入」という別の行は無い。受入は、出荷の行の `arrival_week`（＝受け手の P の週）として表される。業務定義の「代理店の受入（P）」はこの列に対応させた。

### 4.2 全部の卸売（業務定義 §5 の 1・2）

| # | 期待 | 結果 |
|---|---|---|
| A1 | 代理店への出荷 1 件ごとに revenue・external が 1 行 | 出荷 **2,340 件**（SG 1,651・TH 689）、**全件 1 行**。外部代理店を相手にした売上の行で、代理店への出荷以外から立ったものは 0 |
| A2 | 行の週 ＝ 出荷の週 | 2,340 件すべて一致 |
| A3 | 受入の週・leaf の出荷の週に、その Lot の revenue の行が 0 | 2,340 Lot（leaf の出荷 2,340 件）で **0 行**（scope を問わず数えた） |
| A4 | 金額 ＝ 個数 × 卸価格（SKU・区間）、通貨も一致 | 2,340 件すべて一致（SGD 62／74、THB 1,600／1,900） |
| A5 | 合計 ＝ M0 T13 の 443,922,960 円 | **443,922,960 円**（差 0）。内訳：SG クリーム 129,024,480、SG 美容液 183,203,280、TH クリーム 51,667,200、TH 美容液 80,028,000 |

### 4.3 再取込・再計算（業務定義 §5 の 3）

| # | 結果 |
|---|---|
| R1 | 同じ場所への 2 回目の実行の後も 97,682 行で、解凍した中身の sha256 が 1 回目と同じ（`ddb065b2…`）。追記されず、書き直されている |
| R2 | 別の場所の `run_2` も 97,682 行・同じ sha256（`line_id` を含めて完全一致） |

### 4.4 参考（合否に使わない）

- **PPC**：同じ Lot を含む PPC の記録は `PSI-COS_Cream-SG_Distributor-2028-W29`（週 **2028-W29**、`market_revenue`、qty 120 個＝5 lot、単価 62 SGD、記録の合計 7,440 SGD、この Lot の分 1,488 SGD）。PPC の記録は Lot ごとではなく、週・leaf ごとにまとめた 1 件である。Value Chain の明細に PPC 由来の行は無い（src_id が `PSI-` で始まる行 0）。
- **週の差**：代理店への出荷 2,340 件すべてで、PPC の売上週 − Value Chain の売上週 ＝ **1 週**（SG クリーム 754・SG 美容液 897・TH クリーム 299・TH 美容液 390）。M0 T13 の分布と同じ。代理店の売上の全期間の合計は PPC も 443,922,960 円。
- `vc_ppc_comparison.csv` は全期間の合計だけを持ち、週の差の列は無い。週の差は検証のスクリプトで出荷と PPC の記録を突き合わせて数えた。

## 5. 止める理由と申し送り

**止める理由**：無し（B3 の週は同じ、L1・A1 の売上の行は全件 1 件、R1 で行は増えない）。

**申し送り**：

1. **PPC は代理店の leaf の出荷の週に売上を立てる**（業務定義の D-2 と違う方式。§4.4 のとおり全件で 1 週遅い）。全期間の合計は同じで、週の配分だけが違う。PPC をそろえるかは別の判断。そろえないなら、PPC の代理店の売上は「leaf の観測の週の参考値」と呼ぶのがよい。
2. **「記録の欠落で出荷を確かめられないときは未確認として保留」は、計画から作る出荷には無い**。WOM の出荷は計画が作るので、欠落という状態が起きない。実績の出荷の記録を取り込むときに、欠落の表し方（保留の明細、または出荷の行が無い＝0 件のどちらか）を決める論点。
3. （気づいた点）観測の明細の `price_type` は `market` だが、単価は卸価格（62 SGD）。M0 の G3 の注記のとおり、PPC 向けに `ppc_market_price.csv` に卸価格を置いたため。消費者価格・小売の売上の参考値と読まないこと。

## 6. BS-SEAF の記録

- **時刻**：始め 11:38、終わり 11:45 前後（2026-11-08、端末の時計）。
- **人の橋渡し**：大杉さんが依頼書を commit し、Code君に渡した 1 回。作業中の問い合わせは無し。
- **再利用した知識**：G3 業務定義 v0.1（§4・§5 を検証の条件にそのまま使った）、M0 報告書 T13（A5 の期待値、PPC の記録名の付け方 `PSI-{SKU}-{leaf}-{週}`）、WOM-SEM-SUPPLY-ALLOCATION-001（実出荷＝ship_week、受入＝arrival_week）。
- **業務の専門家の役（GPT-MC）が書いた定義を、そのまま検証の条件に使えたか**：**使えた**。§4 の表（週・件数・金額）と §5 の 3 条件は、依頼書の L1〜L4・A1〜A5・R1〜R2 に 1 対 1 で落ち、判定に迷う所は無かった。足りない情報・読み違えやすい所は次の 4 点：
  1. **「卸売明細」と WOM の明細の粒度**：WOM は 1 回の出荷で、売上（revenue）1 行のほかに原価（cogs、v1・entity・group の 3 行）と販売費（expense）を立てる。「明細は最大 1 件」を「その Lot の行は 1 行」と読むと誤る。**`kind=revenue`・`scope=external` に絞って 1 件**、が正しい読み方（依頼書はそう書いていた）。
  2. **同じ Lot に、別の取引の revenue がある**：この Lot には工場の管理会計の売上（W25、scope=management）と、日本本社 → シンガポール販社の法人間の売上（W26、scope=intercompany）も立つ。これらは別の取引で、「同じ卸売」ではない。§5 の「売り手・買い手・区間・Lot_ID の組」で照らすと正しく区別できる。組の 4 つのうち Lot_ID だけで照らすと誤る。
  3. **「受入」が独立の事象として記録されていない**：定義は受入を「別々の物流事象」と書くが、WOM では出荷の行の到着の週である。照合に困りはしないが、実績の取り込みでは受入の記録が独立に来るので、そのとき対応付けが要る。
  4. **PPC の記録は Lot ごとではない**：定義は「PPC は照合に使う」と書くが、PPC の記録は週・leaf ごとにまとめた 1 件（この週は 5 lot）。Lot 単位の照合は、記録名と数量の按分で行う必要がある。
- **作業の変化**：依頼書の付録 `scripts/verify_g3.py` は同梱されていなかったので、Code君が書いた（判定の内容は依頼書 §4 のとおり）。

## 7. 大杉さんに決めてほしいこと

| 一言の決定 | 中身 |
|---|---|
| G3 を Value Chain について閉じてよいか | Value Chain は D-2 を改修なしで満たした（S1〜S5 合格）。M0 報告書の「M0-VC 業務要求 未完了」のうち、G3 の項を「Value Chain は業務定義どおり」と書き換えてよいか |
| PPC をそろえるか（申し送り 1） | PPC の代理店の売上を DC の出荷の週に移すか、leaf の観測の週の参考値として残すか。移すなら PPC の実装の仕様が要る |
| 「未確認の保留」をいつ扱うか（申し送り 2） | 実績の取り込みの設計まで保留でよいか |

## 8. 付録

`docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/`

| ファイル | 中身 |
|---|---|
| `verify_g3.py` | 検証のスクリプト（出力を読むだけ） |
| `verify_g3_result.json` | B1・B3・L1〜L4・A1〜A5・R1・R2 の結果と、参考（PPC） |
| `rep_lot_money_lines.csv` | 代表 Lot の明細 24 行（依頼書 §4.1 の列） |
| `rep_lot_shipments.csv` | 代表 Lot の出荷の記録 6 行 |

実行の出力（`output/g3_verify/`）は git の対象外。
