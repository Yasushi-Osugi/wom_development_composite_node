# Request Letter：BS-SEAF 化粧品の金額試行 M0-PPC（金額の仮定を規則のファイルに置く）

- 版：v0.2（2026-10-30）。v0.1（Claude君、`4824673`）を置き換える
- 宛先：Code君（Claude Code）
- 起草：GPT君（WOMアーキテクチャ支援・レビュー。v0.2 の本文）、Claude君（設計レビューと §10 の修正）
- 依頼者・採否判断：大杉さん（WOM Project Owner）
- 設計の判断（Claude君、2026-10-30）：PPC の試行の完了（M0-PPC）と、Value Chain の観測（M0-VC）を分ける作業分割（§0.1）を採る。理由と修正は §10
- 対象：Yasushi-Osugi/wom_development_composite_node、wom-v1r5m1_cap_trial
- 読み取り基準：48246737ac4dd1d32ac84f7e730583a760f890b8
- 業務の仮定：requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md。ファイル名はv0.1だが、基準コミットの本文はv0.2で、§5.1に大杉さんのM1〜M8の判断がある。

## 0 今回お願いすること

既存の数量モデルC3b・C3aを写し、採用済みの価格・原価・費用・為替を設定して、PPCの金額試行を完了してください。標準の計画コード・PPC・Value Chainは変更しません。

今回の完了成果は、次の二つです。

1. M0・M0t・M0aのPPCについて、数量、売上、費用、試算利益を検証した結果。
2. 同じモデルを既存Value Chainでも実行し、PPCと一致しない意味・計算・費用負担を具体的な金額と出荷イベントで説明した対応表。

**PPCの試行完了と、Value Chainで業務定義を実現できたことを別々に判定します。** 既知のValue Chainの未対応事項を「合格」にせず、今回のPPC作業を完了した後の設計課題として残してください。

### 0.1 Claude君にレビューしてほしい作業分割

元の依頼書は、DataだけでPPCとValue Chainの両方を確かめる構成です。しかし現行Value Chainには、売上比率のノード費用と、外部代理店に関連する自社負担費用の表現上の不足があります。

そこで本依頼は、**先にDataだけでM0-PPCを完了し、M0-VCの機能追加は後続の別依頼にする**。この作業分割は、Claude君が設計レビューで採った（§10）。M1〜M8の数値や採用済み方針は変更しない。

### 0.2 元の依頼書からの具体的な修正

| 元の記述・問題 | 本依頼での実行方法 |
|---|---|
| EC配送費の費目をselling_costなどにする | 既存のsga_costに含める。§3.3の行をそのまま使う |
| 店舗運営費35%と販管費10%の置き方が未確定 | sga_costの売上比率45%の1行にまとめ、内訳35%＋10%を別表で保存する |
| ECに複数の販売費を置く | sga_costを売上比率15%＋1個3 SGD、marketing_costを売上比率15%とする |
| Value Chainでも同じ費用が入る想定 | 既存Value Chainの計算結果を観測し、未対応をG1〜G5で記録する。一致を今回の合格条件にしない |
| タイ関税の感度を1,821円とする | 現行PPCの試験期待値は美容液1,800円、クリーム1,500円。CIFとの差21円はG4に記録する |
| ⑤のLot数と売上を大まかに比較する | SKU×チャネル×実出荷週で照合し、M0との差額36,547,200 JPYを確かめる |

## 1 維持する業務の判断

M1〜M8は変更しません。特に次を守ってください。

- 1 lot＝24個。価格・原価・費用の単価は1個当たり。
- 原価の単価は原料1,500／1,300 JPY、加工700／600 JPYのまま。今回は1/0.97を掛けない。
- 数量計画のyield_rate＝0.97は維持する。歩留まり損の原価反映はPart Bの後続課題。
- 為替は期間中一定。1 SGD＝115 JPY、1 THB＝4.5 JPY、1 USD＝150 JPY。
- 店舗運営費は今回は売上35%で近似。固定費を実装した扱いにしない。
- 日本本社の研究開発・ブランド固定費は入れない。
- タイDCは日本本社の所属、代理店は外部のまま。金額を合わせるために法人・連結区分を変えない。
- タイ関税0%・30%は実験用シナリオ。現実のEPA適用可否や将来の税率を確認済みとは記録しない。
- GST・VATは、今回の採用済み税抜き価格・損益試行の対象外。税額や控除時期を評価した扱いにしない。
- 代理店の需要はsell-in。PPCでは当該leafの実出荷をsell-inの完了数量として評価する。Value Chainの既存のsell-out解釈との違いは§6に残す。

結果の名称は「**今回対象にした費用を控除したPPC試算利益**」としてください。既存出力のgross_profit_base等のキーは変えず、報告の表題・注記で意味を説明します。

## 2 元モデルを固定し写しを作る

### 2.1 着手時の記録

最初にdocs/WOM_Start_Here.md、AGENTS.md、本依頼書、金額仮定書§5.1を読み、着手時SHA・作業ツリーの状態・Python環境を記録してください。基準コミット以降に関係するコードが変わっていれば、差分を確かめ、以下の指定が適用できるかを先に判断してください。

元モデルは次の二つです。

- output/bsseaf_cosmetics/C3b
- output/bsseaf_cosmetics/C3a

両方について、同じコード・同じプラグインで数量だけの基準結果を取得します。期間、報告開始週、warmup、需要、木、能力、休業、cpu_size、実行プラグインを記録してください。金額追加後もこれらは変更しません。

元モデルや生成元が無い場合は、既存の作成手順・報告書から復元できるか確認し、復元した場合は由来を記録します。根拠なく似たモデルを作ってC3a・C3bと呼ばないでください。

### 2.2 写しと実行先

| モデルフォルダ | 元 | 変更 |
|---|---|---|
| output/bsseaf_cosmetics/M0 | C3b | §3の金額ファイルを追加・更新。関税0% |
| output/bsseaf_cosmetics/M0t | M0 | WH_JP_Released→DC_THの関税率だけを0→0.30へ |
| output/bsseaf_cosmetics/M0a | C3a | M0と同一の金額規則を追加・更新 |

各写しの数量入力CSVが元と同一であることをハッシュで確認します。実行時にwarmupを補完する場合は、元と写しに同じ補完処理を一度適用し、補完前・補完後を区別して比較してください。

元のC3a・C3bと既存標準コードを編集せず、生成・集計用スクリプトはoutput/bsseaf_cosmetics/money_m0_work/に置いてください。写しに古いPPC・Value Chainの出力が含まれている場合は入力だけを写し、今回の結果に混ぜないでください。

## 3 金額CSVをこの内容で作る

### 3.1 共通の書き方

- 製品IDはCOS_Serum・COS_Creamを想定する。木の実IDを確認し、SKUとノード名の対応表を保存する。名前が異なる場合はIDの対応だけ直し、数値・所属・数量を変えない。
- 以下の区間は物理の区間。仮想のsupply pointを運賃の区間に入れない。
- CSVの列名は同じコミットの既存ファイルとローダで確かめる。新しい費目名・列を標準機能が読むと仮定しない。
- 9個のPPC規則ファイルはすべてモデルフォルダ内に置く。共有の見本の規則に依存させない。利益ゾーン2ファイルは正しいヘッダを持つ空データでよい。
- 価格の有効開始週は、warmupを含む実際の計画開始週。為替は実際のweek_labelsの全週×4通貨を置く。既定の前年・見本の週からコピーしない。
- 試算利益を合わせるために単価・能力・需要を調整しない。

### 3.2 売価・仕入原価・価格の参照値

| ファイル・対象 | 美容液 | クリーム | 通貨・用途 |
|---|---:|---:|---|
| ppc_market_price.csv：SG_Store | 165 | 138 | SGD、税抜き |
| 同：SG_EC | 157 | 131 | SGD、値引き反映済み |
| 同：SG_Distributor | 74 | 62 | SGD、自社から代理店への卸売 |
| 同：TH_Distributor | 1,900 | 1,600 | THB、自社から代理店への卸売 |
| ppc_supplier_cost.csv：Materials_JP | 1,500 | 1,300 | JPY、今回は歩留まり損を上乗せしない |
| ppc_transfer_price_rule.csv：Factory_JP | 6,000 | 5,000 | JPY、method=fixed、margin_rate=0 |

Factory_JPの6,000／5,000は、現行PPCが関税計算で参照する価格です。タイDCとの法人間取引が存在するという意味を与えないでください。シンガポール向けの実際の法人間価格は、別の区間のvc_price_rule.csvに置きます（§3.6）。

### 3.3 ノード費用

ppc_node_cost_rule.csvに、SKUごとに以下を置きます。金額・率は両SKU共通とした行を含みます。同じノード×SKU×cost_typeの行を重複させないでください。

| ノード | cost_type | basis | rate | fixed_amount | currency |
|---|---|---|---:|---:|---|
| Materials_JP | conversion_cost | qty | 0 | 0 | JPY |
| Factory_JP（美容液） | conversion_cost | qty | 0 | 700 | JPY |
| Factory_JP（クリーム） | conversion_cost | qty | 0 | 600 | JPY |
| WH_JP_Released | warehouse_cost | qty | 0 | 30 | JPY |
| DC_SG | conversion_cost | qty | 0 | 0.50 | SGD |
| DC_TH | conversion_cost | qty | 0 | 12 | THB |
| SG_Store | sga_cost | revenue | 0.45 | 0 | SGD |
| SG_EC | sga_cost | revenue | 0.15 | 3.00 | SGD |
| SG_EC | marketing_cost | revenue | 0.15 | 0 | SGD |
| SG_Distributor | marketing_cost | revenue | 0.05 | 0 | SGD |
| TH_Distributor | marketing_cost | revenue | 0.05 | 0 | THB |

ここでのfixed_amountは期間の固定費ではなく、PPCが1個当たりに足す金額です。basis=qty・rate=0・fixed_amount=700なら、24個の1 lotの加工費は16,800 JPYです。

費用の内訳は、CSVのnoteと報告書で次のとおり維持します。

- SG_Storeの45%＝店舗運営費35%＋販社販管費10%。
- SG_ECのsga_cost＝決済・基盤手数料5%＋販社販管費10%＋1個当たり配送梱包3 SGD。
- SG_ECのmarketing_cost＝デジタル広告15%。
- 代理店のmarketing_cost＝自社が負担するMDF5%。シンガポール向けの負担者はシンガポール販社、タイ向けは日本本社。
- DC_SG・DC_THのconversion_costは取扱・通関等の1個当たりの仮定額。期間の在庫保有費を実装した意味にはしない。

SG_ECのsga_costは、PPCで1個当たり「0.15×そのSKUのEC売価＋3 SGD」と計算されます。例えば美容液は26.55 SGDです。selling_costを追加したり、配送費をノードのlogistics_costとして書いたりしないでください。

この集約は今回のPPC表現のためです。法人別の費用帰属や固定費の表現まで実現したとはしません。

上表に無い実在ノードが木にある場合は、その役割を確認します。費用なしと確認できれば、既存の許可された費目で明示の0行を置き、理由をnoteに残します。supply pointは費用行を置きません。

### 3.4 区間の運賃

ppc_edge_cost_rule.csvは、全行cost_type=logistics_cost、basis=qty、rate=0とし、次のfixed_amountをSKUごとに置きます。

| edge_id | fixed_amount | currency |
|---|---:|---|
| Materials_JP→Factory_JP | 0 | JPY |
| Factory_JP→WH_JP_Released | 20 | JPY |
| WH_JP_Released→DC_SG | 60 | JPY |
| WH_JP_Released→DC_TH | 70 | JPY |
| DC_SG→SG_Store | 0.30 | SGD |
| DC_SG→SG_EC | 0.30 | SGD |
| DC_SG→SG_Distributor | 0.30 | SGD |
| DC_TH→TH_Distributor | 8 | THB |

CSVのedge_idの区切りは既存仕様のASCIIの「->」にします。表示用の「→」をCSVに書かないでください。木に追加の物理区間があれば、費用の有無を確認して0または既存仮定の対応を記録します。

### 3.5 関税と為替

ppc_tariff_rule.csvは、日本→シンガポールと日本→タイの国境区間に、M0・M0aでは0%、M0tではタイだけ30%を置きます。タイの正の率の行はtariff_basis=transfer_priceです。

費用なしを明示するために置くその他の物理区間の0%行は、tariff_basis=material_costとします。原料の仕入価格は両SKUで設定済みです。これは税額0の行を安全に評価するための入力指定であり、国内輸送に課税取引があるという意味ではありません。仮想区間に関税行を作らないでください。適用されなかった0行と、必要なのに未設定の行は区別して記録します。

ppc_fx_rate.csvは、base_currency=JPYとして、計画の全週にJPY=1、SGD=115、THB=4.5、USD=150を置きます。

**M0tの今回の期待値は現行PPCの式に合わせて1個当たり1,800／1,500 JPYです。** CIFで6,000／5,000に海上運賃70を加えた仮定なら1,821／1,521 JPYとなるため、この21円の差をG4に残します。6,000を6,070に変更して差を隠さないでください。

### 3.6 Value Chain用の価格

既存のvc_config.csv、vc_entity.csv、vc_node_assignment.csvはそのまま維持します。vc_price_rule.csvにSKUごとに次を置きます。

| 区間 | price_type | 美容液 | クリーム | currency |
|---|---|---:|---:|---|
| WH_JP_Released→DC_SG | intercompany | 6,000 | 5,000 | JPY |
| DC_SG→SG_Distributor | wholesale | 74 | 62 | SGD |
| DC_TH→TH_Distributor | wholesale | 1,900 | 1,600 | THB |

PPC向けに卸価格を置いたppc_market_price.csvを、Value Chainでは外部代理店の消費者販売の観測にも使います。この観測値は実際の小売売価ではないため、販売実績・小売売上の参考値として使わないでください。G3として残します。

## 4 検証に使う期待値

### 4.1 M0の1個当たりの期待値

次はJPY、関税0%、丸め前の値です。金額仮定書§6の丸めた表より、この表を機械照合の基準にします。

| SKU | チャネル | 売上 | 費用 | PPC試算利益 |
|---|---|---:|---:|---:|
| COS_Serum | SG_Store | 18,975 | 10,940.75 | 8,034.25 |
| COS_Serum | SG_EC | 18,055 | 8,163.50 | 9,891.50 |
| COS_Serum | SG_Distributor | 8,510 | 2,827.50 | 5,682.50 |
| COS_Serum | TH_Distributor | 8,550 | 2,837.50 | 5,712.50 |
| COS_Cream | SG_Store | 15,870 | 9,243.50 | 6,626.50 |
| COS_Cream | SG_EC | 15,065 | 6,966.50 | 8,098.50 |
| COS_Cream | SG_Distributor | 7,130 | 2,458.50 | 4,671.50 |
| COS_Cream | TH_Distributor | 7,200 | 2,470.00 | 4,730.00 |

例：美容液ECの費用は、原料1,500＋加工700＋国内輸送20＋日本倉庫30＋海上60＋SG取扱57.5＋市内配送34.5＋EC販管費・手数料等5,416.5＋配送梱包345＝8,163.5 JPYです。

この表と§3の費目設定は、GPTが基準コミットから取得した既存PPCの計算関数に合成入力を渡し、8通りで一致を確認しています。化粧品モデル全体の実行結果ではないため、Code君はモデル全体で検証してください。

### 4.2 M0tの期待値

- 美容液TH_Distributor：M0より費用が1,800 JPY／個増え、利益は3,912.50 JPY／個。
- クリームTH_Distributor：同1,500 JPY／個増え、利益は3,230.00 JPY／個。
- 売上数量・売上単価はM0と同じ。
- シンガポール3チャネルの数量・単価・費用・利益はM0と同じ。
- 全体利益の減少＝美容液のタイ実出荷個数×1,800＋クリームのタイ実出荷個数×1,500。

### 4.3 M0aの期待値

元のC3aで報告された結果を、同じ条件で再確認します。

| 数量 | 期待値 |
|---|---:|
| 元需要① | 4,056 lot |
| 供給対象② | 4,056 lot |
| 未配分③ | 0 lot |
| 実出荷で満たした需要④ | 3,864 lot |
| 配分後の期末未充足⑤ | 192 lot |
| ⑤の内訳 | タイ・美容液104 lot、クリーム88 lot |

これは今回Management配分で需要を削らない試行です。⑤を③に読み替えないでください。

売上の対象は④×24＝92,736個です。PPCのtotal_lotsは週次集約レコードの件数であり、3,864との比較には使いません。market_revenueイベントのqtyを一度だけ合計するか、total_qty_unitsを使います。全費用イベントのqtyを合計しないでください。

M0との差額は、SKU別に次を確かめます。

- 美容液：104 lot×24個×1,900 THB×4.5＝21,340,800 JPY
- クリーム：88 lot×24個×1,600 THB×4.5＝15,206,400 JPY
- 合計：**36,547,200 JPY**

その前提として、M0とM0aの元需要が同一、M0は全需要を満たす、192 lot以外の実出荷総量は同じ、価格・為替は一定であることを確認します。前提が異なれば、数字を合わせず差分を報告します。

売上ゼロのLotの照合はPPCについての受入条件です。Value ChainのDC出荷で認識する売上には、同じ条件をそのまま当てはめず§6でイベントを照合してください。

## 5 Code君の作業順序

### 手順1 基準の固定と1 lotでの単位確認

C3a・C3bの入力と数量結果を保存します。別の小さな検証入力で、24個を評価すると売上と費用が§4.1の24倍になること、ECの3 SGDが1回だけ加算されることを確かめてください。合成入力は作業フォルダに残します。標準コードは変えません。

### 手順2 M0を作ってPPCを実行する

§3の指定で金額CSVを生成し、M0を実行します。次はリポジトリのルートから実行する例です。プラグインは元のrecommended_pluginsと同じ組を使い、実際の組を記録してください。

~~~text
python -m tools.run_headless_from_folder --model-dir output/bsseaf_cosmetics/M0 --out output/bsseaf_cosmetics/money_m0_work/M0_snapshot.json --ppc-out output/bsseaf_cosmetics/money_m0_work/M0_ppc --flow-check-out output/bsseaf_cosmetics/money_m0_work/flow_check --quiet
~~~

PPCの各イベントのamount_baseは1個当たりの金額、qtyは個数です。金額総計はamount_base×qtyで求めます。チャネル別集計はlot_reconciliation等の集約キーからSKU×チャネルを復元して行い、同じイベントを複数チャネルへ足さないでください。

PPCのlot_idは「PSI-製品-チャネル-週」の週次集約レコードIDです。需要Lot_IDと直接結合しません。SKU×チャネル×実出荷週ごとに、数量側の_actual_shipに含まれる需要Lot_ID数×24とPPCのmarket_revenueのqtyが一致することを確かめます。未充足192 lotは、数量側の要求IDと_actual_shipの集合差で確認し、その結果を週次集計の売上照合へつなぎます。SやCOの件数から売上を作りません。

生の台帳のcost_phase・node_id・edge_id・費目で、原料・加工・運賃・倉庫・チャネル費用を分け、§4.1と照合します。transfer_price_set、landed_cost_total、backward_allowable、mom_profitは、グループの外部売上・費用の再集計には加えません。

### 手順3 M0tとM0aを実行する

同じコマンドのモデル名・出力先をそれぞれM0t・M0aへ変えます。出力先はケースごとに分けてください。§4.2・§4.3を検証します。

Flow Check表2はSKU×市場の明細だけを集計し、製品・モデルの小計行を二重に足しません。表1の数量保存も確認します。最終週COや毎週COの合計を⑤に使わないでください。

### 手順4 同じ写しでValue Chainを観測する

~~~text
python -m tools.valuechain_run --model-dir output/bsseaf_cosmetics/M0 --out output/bsseaf_cosmetics/money_m0_work/M0_vc --plugins "<M0 の planning_config.csv の recommended_plugins と同じ組>"
~~~

M0t・M0aも同様に実行します。既存Value Chainの実行は計画も行うため、モデルのプラグイン・期間をPPC試行とそろえます。**`tools.valuechain_run` の `--plugins` の既定は「golden の組、無ければ safe」で、化粧品のモデルには golden が無いので safe になる**。必ず `--plugins` にモデルの `recommended_plugins` と同じ組を渡し、PPC 試行と計画が同じであること（Flow Check 表2 の明細の一致）を確かめてください。

VCの結果は、PPC向けにまとめた費用行がそのまま完全に反映されるとは仮定せず、issues・未評価・費用の除外・保存検査をすべて記録します。観測のためにcost_typeや法人所属を付け替えて結果を良く見せないでください。

### 手順5 報告と再現用データを残す

§7・§8の成果物を作ります。今回の出力フォルダがgit対象外でも、金額設定を再現できるよう、生成スクリプトの完全な内容・実行コマンド・金額CSVの内容・元モデルの由来を報告書の付録または追跡対象の資料フォルダに残します。ハッシュだけで再現できた扱いにはしません。

標準のコード・テスト・サンプルを変えない試行なので、全テストの実行は要りません。最後に `git status` で、`wom/`・`tools/`・`tests/`・`data/sample/` に変更が無いことを確かめて報告してください（変更があれば止めて報告）。標準コードを変えていない本試行を、保護対象コアの改修を検証した記録に読み替えないでください。

## 6 Value Chainとの違いをこの表で報告する

報告書の項目は、単なる問題名ではなく「今回の表現」「実行結果」「不足額・出来事」「後続の設計対象」を持たせます。

| ID | 今回の確認内容 | 今回の処理と後続設計の候補 |
|---|---|---|
| G1 売上比率の費用 | 店舗45%、EC等のrevenue行がVCのissuesに出て計算から外れるか。SKU×チャネル別にPPCの費用額と除外額を出す | 今回はVC未対応として残す。後続は売上イベントを基準に率×売上を計上し、受入時の二重計上を防ぐ仕様を設計する |
| G2 MDFの負担者 | 外部代理店ノードの費用がグループに入らないことを確認。PPCのMDF額をSG販社・日本本社の負担候補に分ける | 後続は外部取引・対象チャネル・支払法人・計上週を結ぶ販売費の表現を設計する。代理店を自社法人に変更しない |
| G3 sell-inの数量と売上週 | 各SKUで代表Lotを1本以上選び、DC実出荷週、代理店P受入週、代理店leaf実出荷週、両方式の売上週・単価を並べる。M0aの未充足Lotも調べる | 後続は代理店需要がsell-inかsell-outか、受渡点、売上イベント、価格用途を対応させる。今のleafの観測価格を消費者価格と呼ばない |
| G4 関税評価額 | 現行の1,800／1,500と、運賃込みの仮定1,821／1,521を並べる。税額差21円／個を示す。タイの化粧品の関税は CIF 価格に課される（JETRO の資料。仮定書 §4.3 の出典）ので、業務の定義は CIF、現行 PPC は振替価格だけ、という差として書く | 後続は法人間価格と税関評価額を別の概念として持ち、CIFを評価するなら運賃・保険の加算条件を定める。今回の入力単価を変えない |
| G5 CIFの運賃負担と期間 | 仮定では日本側がCIF運賃を負担するが、既存VCは内部区間の運賃を受け手の在庫原価にする。60円／個の帰属と期末在庫・期間費用の差を説明する | 後続は運賃の支払・負担法人と在庫原価への算入を区別して設計する。今の法人別損益をCIF前提の完成した損益と呼ばない |

この表は、既存の一般機能が無いと一括して断定するためのものではありません。基準コミット・今回の実行経路で確認した不足を記録し、別経路で既に表せると分かった場合は、入力・接続・根拠を提示してください。

Value Chainのconservation等が通っても、除外された費用を含む業務上の損益が正しいことの証明にはしません。既知の未対応として説明できたことと、業務要求を実現したことを分けます。

## 7 受入条件

### 7.1 M0-PPCの合格条件

すべて満たした場合だけ「M0-PPC完了」とします。

| ID | 合格条件 |
|---|---|
| A1 | M0・M0t・M0aでvaluation_statusが評価済み、excludedが空、価格・仕入原価のmissingと最初の価格以前の参照が0 |
| A2 | 金額入力の取得元は各モデル内。見本の規則・見本の販売・前回の出力を使っていない |
| A3 | 8通りの1個当たり売上・費用・利益が§4.1と一致。M0tはタイだけ§4.2の差、M0aは同じ単価 |
| A4 | 24個の1 lotに対して金額が24倍になり、EC配送費と各率の費用が一度だけ計上される |
| A5 | 外部売上−原料−加工−物理区間の費用−ノード費用−販売費＝PPC試算利益。台帳集計と全体KPIが一致する |
| A6 | 数量入力は元と同じ。Flow Check表1の保存と、表2の需要・出荷・未充足の明細が元のC3b・C3aと同じ |
| A7 | M0aの未充足はタイの104・88 lot、実出荷92,736個、M0との売上差36,547,200 JPY。代表Lotと集計の両方で確認 |
| A8 | M7の費用あり・明示0・仮想区間・未設定を対応表にし、必要なのに未設定の金額規則が残っていない |
| A9 | M3・M5・M6、関税評価額の仕様差、VC未完了を報告の結論と結果表に明記し、再現用データを保存 |

機械照合の許容差は、1個当たり金額は0.000001 JPY、総額はmax(0.01 JPY, 比較する期待額の絶対値×10^-9)とします。報告表示だけ小数2桁に丸め、丸めた値同士で検証しません。比率は0〜1と%表示を区別します。ゼロ出荷の行は単価を割り算で求めず対象外と明記します。

### 7.2 M0-VCの今回の終了条件

- 3ケースの実行の成否と、issues・未評価・保存検査の結果が記録されている。
- G1〜G5について、適用の有無、対象SKU・チャネル、数量・金額または代表Lot、根拠ファイルが示されている。
- 表せていないものは「未対応／追加設計が必要」と表示されている。
- Value Chainの全体利益とPPCの利益の一致、sell-inの業務定義への適合、法人別CIF損益の完成は、今回の合格に含めない。

これは「M0-VC観測完了」です。**M0-VCの業務要求を実現したという完了ではありません。**

### 7.3 止めて報告する場合と、そのまま記録する場合

PPC作業を止めるのは、入力基準が復元できない、数量が変わる、A1〜A8が満たせず入力や集計の誤りでも説明できない、標準コードの変更が必要になった場合です。原因・再現入力・期待と実際を報告し、コードは変更しません。

既知のG1〜G5はPPC作業を止める理由にしません。観測した不足をそのまま記録し、PPC試行を進めます。Value Chainの想定外の例外が出た場合も、PPC試行の検証を完了したうえで、VC観測が未完了であることを明記してください。

## 8 成果物と知識更新

### 8.1 報告書

docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.mdに次を残してください。

1. 冒頭の結論：「M0-PPC完了／未完了」「M0-VC観測完了／未完了」「M0-VC業務要求は未完了」を別々に記載。
2. SHA・環境・元モデルの由来・期間・プラグイン・数量入力のハッシュ。
3. M0・M0t・M0aのA1〜A9の結果。値は実行後に転記。
4. SKU×チャネル別の売上・費用・試算利益、全体KPIとの照合、店舗運営費35%の内訳額。
5. MDFの自社負担額、EC配送費の金額、関税の差額、M0aの売上差。
6. G1〜G5の表、出荷イベントの対応、後続の設計が必要な内容。
7. 金額CSVの完全な内容、生成・集計スクリプト、コマンド、再現方法。
8. BS-SEAF記録：再利用した知識、入口から辿った経路、Dataで済んだ範囲、追加設計が必要な範囲、予想と結果。

数値を「一般的な水準として妥当」と検証したことにはしません。今回の作業は、採用済みの架空の仮定をWOMが意図どおり評価するかの試行です。

### 8.2 Claude君へ返す知識更新案

Code君は実行根拠を報告し、以下はClaude君が整理してください。

- 今回の入力単価・為替・近似・期間・法人は化粧品事例の仮定として管理する。
- 単位、sell-in／sell-out、価格の用途、費用の負担者、固定費と数量比例費用の意味は、再利用可能な業務知識の更新候補にする。
- PPCとValue Chainの現行仕様・G1〜G5はWOMへの対応設計に記録する。
- Start Hereから「金額の業務定義→WOMへの対応→事例と実行根拠」を辿る索引案を作る。
- 採否と根拠の確認状態は別にする。本依頼の採用前に新しい会計方針を採用済みにしない。

### 8.3 変更範囲とgit

- 既存のwom/・tools/・tests/・data/sample/・goldenは変更しない。
- 保護対象コアの6ファイルは変更しない。
- 写し・実行結果・作業用スクリプトはoutput/に置く。
- gitに残すのは報告書と、再現に必要な付録資料。既存の未追跡ファイルをまとめて追加しない。
- commitメッセージの下書きだけを次の未使用番号のcommit_msg<N>.txtに用意し、commit・pushは大杉さんが行う。

## 9 次に進む条件

M0-PPCが完了したら、Claude君・大杉さんがG1〜G5をレビューし、Value Chainの金額層の拡張を別依頼にするか判断します。本依頼を根拠に標準の金額コードを改修しないでください。

P2の利益配分には自動的に進みません。P2の前に、評価する主体・利益の定義・固定費近似の扱い・未配分需要の扱い・SKU別の制約資源を確認し、利用できる評価範囲を決めます。店舗の35%近似をそのまま真の変動費とした貢献利益計算には使いません。

## 10 設計レビュー（Claude君、2026-10-30）

### 10.1 作業分割の判断：採る

v0.1 は、Data だけで PPC と Value Chain の両方を仮定どおりにできる、と前提していた。Claude君がコードで確かめた所、この前提は成り立たない。

| GPT君の指摘 | Claude君の確認（`4824673`） |
|---|---|
| Value Chain は `basis=revenue` のノード費用を計算しない | `wom/valuechain/ledger.py` `_node_costs()`：`revenue_based_node_cost_not_supported` を issues に足して `continue` |
| 外部の代理店のノードの費用はグループに入らない | 同：`rec.external` または持ち主がグループでなければ return |
| `selling_cost` は使えない費目 | `wom/valuechain/policy.py` `COST_POLICY` に無く、`classify_node_cost()` が `ValueError` |
| 関税の課税価格は振替価格だけ | `wom/ppc/ppc_tariff.py`：`tariff_basis` が `transfer_price` なら振替価格（運賃を足さない） |

これらは Value Chain の機能の追加（売上の率の費用、費用の負担者、sell-in の売上の時点、関税の課税価格）であり、Data では表せない。一方、PPC は既存の費目（`sga_cost`・`marketing_cost`）で仮定の 1 個当たりの損益を表せる（GPT君が既存の関数で 8 通りの一致を確かめた）。したがって：

1. **今回は M0-PPC を Data だけで完了する**。
2. **Value Chain は観測し、表せない所を G1〜G5 として金額と出来事で記録する**。一致を合格にしない。
3. **Value Chain の金額の層の拡張は、M0 の報告を見てから別の依頼にする**（Core ではない）。

### 10.2 Claude君の誤りの記録（BS-SEAF）

v0.1 は、既存の Value Chain が売上の率の費用と、代理店に置いた自社負担の費用を扱えると**確かめずに**前提した（B2 として「確かめる」と書いたが、置き方の表は扱える前提で書いた）。知識の適用条件（E1〜E3）とも、知識を見つけられなかった（E4）とも違い、「既存の機能の能力を、確かめる前に設計の前提にした」型である。化粧品設計書の BS-SEAF の記録に E5 として残す。

### 10.3 本文に足した修正

- §5 の手順 4：`tools.valuechain_run` の `--plugins` を明示（既定は safe になる）。
- §5 の手順 5：全テストの実行をやめ、`git status` で標準のファイルに変更が無いことを確かめる（Data だけの試行のため）。
- §6 の G4：タイの関税は CIF に課される（業務の定義）ことを根拠として足した。

### 10.4 受け入れた上での注意（申し送り）

- `SG_Store` の `sga_cost` 45% は、店舗の運営費 35%（固定費の近似、M5）と販社の販管費 10% を 1 行にまとめた。固定費を実装するとき（仮定書 §7）は 35% の部分だけを期間の費用に置き換えるので、内訳を note と報告書に必ず残す。
- 日本の中の区間の関税 0% の行の `tariff_basis=material_cost` は、評価のための入力の指定で、業務の意味は無い（R9：関税は国境を越える区間）。
- `SG_EC` の `sga_cost` に、決済の手数料・販管費（売上の率）と配送（1 個当たり）を混ぜた。Value Chain の拡張のときに費目を分けるかを決める。

## 参照した資料と確認の範囲

基準はいずれも48246737ac4dd1d32ac84f7e730583a760f890b8です。

- [Start Here](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/docs/WOM_Start_Here.md)
- [元の依頼書v0.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/requests/RequestLetter_BSSEAF_Cosmetics_Money_to_CodeKun.md)
- [金額仮定書 本文v0.2](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md)
- [C3a・C3bの数量試行報告](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md)
- [PPCのチャネル費用](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/wom/ppc/ppc_profit_zone.py)
- [PPCの関税](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/wom/ppc/ppc_tariff.py)
- [Value Chainの台帳](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/wom/valuechain/ledger.py)
- [Value Chainの費用方針](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/48246737ac4dd1d32ac84f7e730583a760f890b8/wom/valuechain/policy.py)

GPTの確認は文書・コードと合成入力による既存金額関数の確認です。C3a・C3b・M0のモデル全体、Windows GUI、golden、全テストをGPTが再実行したという記録ではありません。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-10-30 | Claude君の初版（`4824673`） |
| v0.2 | 2026-10-30 | GPT君の本文（PPCの具体的な費目設定と期待値、DataだけのM0-PPCと既存VCの観測・後続設計の分割）。Claude君の設計レビュー（§10）：作業分割を採る、Value Chain の `--plugins` を明示、全テストの代わりに `git status` の確認、G4 に CIF の根拠 |

