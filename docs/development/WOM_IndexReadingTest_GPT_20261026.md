# 索引の読解試験 v0.1 の結果 — GPT君（新しい会話）、2026-10-26

- 試験：`requests/BSSEAF_IndexReadingTest_v0.1.md`（問 1〜10）
- 受けた AI：GPT君（新しい会話。§2 の本文を貼り付けて渡した）。GPT君はこの知識の整備のレビューを担当していたので、モデルとしては経緯に触れている（会話としては新しい）
- 対象の版：`02e4210`（GitHub。Start Here「改4」）
- 採点：Claude君（2026-10-26）、採点の表 `requests/BSSEAF_IndexReadingTest_v0.1_AnswerKey.md`

## 1. 採点

| 問 | 判定 | Start Here から | 気づいたこと |
|---|---|---|---|
| 1 | ○ | 辿れた | 「いつ届けるかの決定は見つからない」と、見つからないことを正しく書いた |
| 2 | ○ | 辿れた | 受渡点・判定時点・単位をそろえること |
| 3 | ○ | 辿れた | |
| 4 | ○ | 辿れた | (b) 確かめることを入力・条件・接続と観測に分けて挙げ、受渡点の確認まで。(c) 3 点（原価・利益評価、二重計上と今の停止の検査、104 週） |
| 5 | ○ | 辿れた | |
| 6 | ○ | 辿れた | 境界の効果まで |
| 7 | ○ | 辿れた | 大杉さんの判断（P0P1 の報告書 §7.1）と、②3,864・④3,860・⑤4 の数 |
| 8 | ○ | 辿れた | コード（アダプター・プラグイン）まで読んだ |
| 9 | ○ | 辿れた | 確認の範囲（数量配分と ①〜⑤ の計測）と、自分は再実行していないことを書いた |
| 10 | △ | 辿れた | 意味体系の U1〜U4 と、③ の記録は U1 を待たないこと。化粧品の事例の未決は挙げていない |

**合格**：E4 に関わる問（3・4(b)・5・8）はすべて ○。○ 9・△ 1・× 0。10 問とも Start Here から辿れた。

## 2. 見つかった食い違いと扱い

| # | GPT君が見つけた食い違い | 扱い |
|---|---|---|
| 1 | 意味体系 README §6 の「化粧品での実行確認は未確認」（Code君も指摘） | 直した（`WOM_IndexReadingTest_ClaudeCode_20261026.md` §2 の 1） |
| 2 | 旧対応表 v0.1 の「二重計上が黙って通る」と、今の停止の検査 | v0.1 は「v0.2 で置き換えた」と冒頭に書いてある当時の記録。直さない |
| 3 | 変更課題①②③の報告書 §4.2 の「市場優先の機能が無い」「能力不足では warmup を延ばさない」と、後の訂正 | 報告書 §4.2 の冒頭に訂正の注記を足した（README §4 の 5「古い記述には訂正先への案内を付ける」の漏れ） |

## 3. 三つの AI の比較

| | Claude Code（新しいセッション） | Grok | GPT君（新しい会話） |
|---|---|---|---|
| 判定 | ○ 10 | ○ 9・△ 1 | ○ 9・△ 1 |
| Start Here から | 10 問 | 10 問 | 10 問 |
| 読んだファイル | 9 | 8 | 13（コード 5 を含む） |
| 見つけた文書の食い違い | 2（README §6、三層設計 MD の front matter） | 0 | 3（README §6、旧対応表、変更課題の報告書 §4.2） |

三つとも §0.1 の表の順（意味体系 → 三層設計 MD → 対応表・報告書）に、迷わずに辿った。E4（知識はあるのに見つけられない）への打ち手は効いている。問 10 の △ は、意味体系の未決（U1〜U4）と事例の未決（化粧品設計書 §9 の H9・H10 など）が別の文書にあるためで、問いの「供給配分について」が意味体系の範囲と読める書き方だった。索引の直しは要らない。

## 4. 回答（原文）

[`docs/WOM_Start_Here.md`](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/wom-v1r5m1_cap_trial/docs/WOM_Start_Here.md)（2026-10-26・改4）の§0.1から、意味体系→設計→対応表→報告書→コードへ辿りました。WOMのコード・テストは実行していません。

**問1．未配分は50、配分後の未充足は0です。**

元需要200のうち供給対象は150、その150はすべて届いています。Bの残り50は供給対象から外した量です。**その50をいつ届けるかの決定は見つからない**。後で供給するかどうかは、配分とは別の判断です。

根拠：`docs/semantics/supply_allocation.md` §2「用語の定義」、§4「例1」、§5 U1。

**問2．期間中の出荷量を、そのまま実納品にはできません。**

期間中の出荷には、前の期間の需要に対する納品が混ざることがあります。対象需要を元の要求期間で固定し、その需要ごとに引渡しの完了を照合します。

また、出荷地点と受渡点の間に輸送期間があれば、出荷週と納品完了週が異なります。受渡点・判定時点・単位もそろえる必要があります。

根拠：`docs/semantics/supply_allocation.md` §2「受渡点・実納品」、§3.1〜3.2、§4「例3」。

**問3．192 lotは、供給対象だったが期末までに届かなかった量です。**

C3aは元需要のまま計画しており、**未配分③は0、配分後の未充足⑤が192 lot**です。内訳は美容液104 lot、クリーム88 lotで、すべてタイ代理店向けです。

どの要求が残ったかはBackwardの押し戻し順による結果であり、経営がタイを供給対象から外した結果ではありません。

根拠：`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §1 Q01・Q02・Q05、`docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md` §3.4。

**問4．(a) 金額は不要です。(b) 数量配分モードがあります。(c) 旧比率経路には適用上の問題があります。**

**(a)** 人が供給数量を指定する判断には、価格・原価は要りません。必要なのは対象SKU・市場／チャネル・期間・指定数量です。利益によって配分を選ぶ場合には金額情報が必要です。

根拠：`docs/semantics/supply_allocation.md` §6。

**(b)** `tools/run_quantity_allocation.py` が既存の入口です。`sku_id, region, alloc_lots` の配分CSVを使い、金額なしで配分→計画→結果保存まで進め、財務は「未評価」と記録します。

使う前には、次を確認します。

- **入力**：SKU×チャネルを区別し、数量をlot単位の非負整数で指定する。元需要を超えず、必要なキーの欠落・重複がないこと。
- **条件**：identityモードを使い、元需要から定めた計画期間・warmup・能力・操業条件を固定する。化粧品のSKU別能力を一つに合算しないこと。
- **接続と観測**：配分済み需要が実際に計画へ渡ること、プラグイン設定、各チャネルの受渡点を確認する。①〜⑤をFlow Check表2で照合する。

配分の期間合計は元の週次需要の形に比例して配られます。どの週を優先するかまで人が指定する仕組みではありません。

根拠：`docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md` §3.1・§6、`wom/allocation/handoff.py` の `write_demand_for_quantity_allocation()`、`tools/run_quantity_allocation.py` の `run_quantity_allocation()`。

**(c)** 旧比率経路には、主に三つの問題があります。

- 明示的に比率を渡しても原価導出を呼び、従来の計画ループでは利益評価も行います。化粧品には必要な`ga_*`や金額データがそろっていません。
- SKUを区別せず地域×週で数量を扱うため、同じ地域名を使う2 SKUでは二重計上になります。**現行コードには、この条件を検出して停止する検査が追加されています。**
- 旧計画ループの104週という前提が、化粧品の156週＋warmupと一致しません。

根拠：`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §1 Q03・Q04・Q09、`docs/development/WOM_QuantityAllocationMode_Report.md` §3.4、`wom/allocation/handoff.py` の `write_demand_for_allocation()`。

**問5．Flow Check表2の `backlog_end` を使います。**

要求SのLot_IDと、leaf_outの実出荷 `_actual_ship` を照合し、計画期間内に一度も出荷されなかった要求を数えます。報告期間で絞る場合も、要求週に基づく対象需要をそろえます。

**最終週のCOは使えません。** 当週中に出荷済みとなった繰越要求が残る一方、最終週に新しく発生した未充足は、翌週のバケットがないため入りません。

**毎週のCOの合計も使えません。** 同じ要求を複数週で数えるため、単位はlot数ではなく **lot×週の滞留量**です。

根拠：`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §0の1・§1 Q05、`wom/engine/flow_check.py` 冒頭「Table 2」・`compute_flow_check()`の表2処理。

**問6．期末に不足が残っただけでは、恒常的な能力不足とは言えません。**

文書が示す確認項目は、次のとおりです。

- 継続する需要水準と、歩留まり・休業を反映した有効能力の関係。
- LTを考慮した各週までの累計能力と累計需要の関係。
- 先行生産に必要な在庫量・保管場所・保管期間・FIFOで測る製品年齢の許容範囲。
- 計画開始端の原料未到着や、終了端で能力を使えない境界の影響。

一時的な需要の山や計画期間の切り方による不足を、恒常的な不足と区別します。

根拠：`docs/semantics/supply_allocation.md` §7、`docs/WOM_Start_Here.md` §4.3の12。

**問7．P1の4 lotは、業務の欠品として扱いません。**

大杉さんが2026年10月26日に、**計画の境界の効果として受け入れる**と判断しています。記録上は供給対象3,864 lot、実納品3,860 lot、未充足4 lotです。

残った理由は二つです。

1. **終了側**：直営店向けを店頭在庫のため2週早く作るので、工場の2029-W47・W48に余裕が残ります。期間外の後続需要がなく、Backwardは前の週へしか押し戻さないため、その余裕を使えません。
2. **開始側**：超過分が最初の週2026-W37へ押し戻されますが、原料のLTが1週あるためForwardでは作れません。

美容液・クリーム各2 lotで、すべてタイ代理店の2029-W50の要求です。単に量が小さいから欠品から除いた、という判断ではありません。

根拠：`docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md` §3.2〜3.4・§4・**§7.1「大杉さんの判断」**。

**問8．Capacity Layerの `unallocated` は、意味体系の「未配分」と異なります。**

Capacity Layerでは、設定した能力・前倒し窓の下で、**内部の計画へ配置できなかった量**です。経営が対象外にした③でも、Forward後の未充足⑤でもありません。配置できてもForwardで届かない場合があります。

化粧品へ適用する前には、次を確認します。

- 木が対応条件の「直列Inbound・leaf_in一つ・分岐なし・`bom_qty=1`」を満たすか。
- 既定OFFのプラグインの有効化と、必須の`max_advance_weeks`。
- 能力の層が使う **cap_hard側の良品上限**と、化粧品の **cap_softによる平準化**の条件をどうそろえるか。
- 市場優先は目的に含まれていないこと。配置結果を適用した後の納品可否はForwardで確認すること。

根拠：`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §1.1 Q10、`wom/plugins/capacity_layer.py` の `CapacityLayerPlugin`、`wom/capacity_layer/serial_adapter.py` の `SerialLineAdapter.from_tree()`・`expand()`・`apply_positions()`。

**問9．定義は採用済みで、化粧品での実行確認も記録されています。**

採用者は**大杉さん、判断日は2026年10月26日**です。採用範囲は意味体系の§2「用語の定義」と§3「数量の関係・成立条件」で、対応表のJ1に記録されています。

実行確認は、Code君による数量配分モードのC3a写しでのV09、およびP0・P1試行です。P1では未配分192 lotと配分後の未充足4 lotが別々に記録されています。確認範囲は数量配分と①〜⑤の計測です。今回、私は実行報告書を確認し、再実行はしていません。

根拠：`docs/semantics/supply_allocation.md` §0、`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §4 J1、`docs/development/WOM_QuantityAllocationMode_Report.md` §5 V09、`docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md` §3.2。

**問10．一般的な業務方針として、U1〜U4が未決・保留です。**

| 項目 | 未決・保留の内容 |
|---|---|
| U1 未配分需要の扱い | 供給しない予測需要として扱うか、受注として保持して後で供給するか |
| U2 納期延期 | 延期の可否、許容期間、延期する順序 |
| U3 配分の判断基準 | 人の指定・規則・利益などのどれを採るか。利益なら率か単位当たり利益額か |
| U4 配分の時間粒度 | 対象期間の合計だけ決めるか、どの週の需要を対象外にするかまで決めるか |

化粧品ではU1を「当該期間は供給対象にしない予測需要」という試行上の仮定にしています。実際に失われた販売と断定してはいません。**③未配分の数量記録は、U1の決定を待たずに行います。**

根拠：`docs/semantics/supply_allocation.md` §5、`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` §4 J2。

**読解で迷った箇所**

今回はすべてStart Hereから辿れました。別入口からの検索はしていません。ただし、次の記述の差を確認する必要がありました。

- 意味体系READMEの§6には「化粧品での実行確認は未確認」が残っています。本文` supply_allocation.md`の§0と具体的な実行報告書には確認記録があります。
- 旧対応表には二重計上が黙って通る可能性の記述がありますが、現行コード・数量配分モード報告書には停止検査があります。
- C3a報告書§4.2には「市場優先の機能がない」「能力不足ではwarmupを延ばさない」という説明があります。三層設計MDの§5・§8.2では、既存機能の確認と、累計能力・在庫条件による再検討を案内しています。試行結果と、その後に訂正された解釈を分けて読みました。

**今回読んだファイルを、読んだ順に示します。**

1. `docs/WOM_Start_Here.md` — §0.1を今回の入口として使用。
2. `docs/semantics/README.md`
3. `docs/semantics/supply_allocation.md`
4. `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md`
5. `requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md`
6. `docs/development/WOM_QuantityAllocationMode_Report.md`
7. `docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md`
8. `docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md`
9. `wom/allocation/handoff.py`
10. `tools/run_quantity_allocation.py`
11. `wom/engine/flow_check.py` — 冒頭の定義と`compute_flow_check()`の表2部分。
12. `wom/plugins/capacity_layer.py`
13. `wom/capacity_layer/serial_adapter.py`