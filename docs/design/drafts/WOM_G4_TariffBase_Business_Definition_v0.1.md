# G4 日本からタイへの社内移動の課税価格｜業務定義案 v0.1

2026-11-12 ・ GPT-MC ・ 採否待ち

日本本社の `WH_JP_Released` から同じ日本本社の `DC_TH` へ送るクリーム24個（`COS_Cream`、1ロット）を対象とする。輸入関税の試算額を求め、負担法人の在庫原価に計上する。両拠点の法人は `E_JP` であり、この区間の法人間売買は0件。`DC_TH → TH_Distributor` の外部卸売は後続の取引として照合する。G5との比較は[共通照合表](WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md)を参照。

## 1. 現行サンプルの前提とM0・M0tの観測

| 区分 | 確認した内容 |
| --- | --- |
| 現行サンプルの前提 | M8でタイDCは `E_JP`。関税設定は `tariff_basis=transfer_price`、タイ0%を明示。PPCの振替価格設定はクリーム5,000円／個、美容液6,000円／個。タイ向け区間費用は70円／個で、金額仮定書では輸出通関を含む海上費用。 |
| M0の試行条件 | タイ0%。この条件で得られる税額は、課税価格が120,000円でも121,680円でも0円。課税価格の検証には価格の内訳と合計額が必要。 |
| M0tの報告結果（T14） | 30%の感度試行では、PPC・Value Chainとも振替価格だけを基礎とし、タイ向け2品目16,536個で関税27,612,000円。Value Chainでは `E_JP` の `DC_TH` の取得原価に計上。 |
| T14の比較計算 | 70円／個を課税価格に含める仮定では27,959,256円。差347,256円は16,536個 × 70円 × 30%の比較値。 |

[金額仮定書（本文 v0.2） §§2.3・4.1・4.3・5.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md) ・ [M0報告書 §6・T14](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L482)

## 2. 課税価格の決め方（提案）

**試算上の課税価格＝数量 × 評価用商品単価 ＋ 課税対象のうち商品価額に未含有の費用。** 今回は、既存試行と比較できるよう、PPCの5,000円／個を運賃別の評価用商品単価として仮採用する。これはこの区間の課税試算に用途を限定した値で、法人別の在庫原価は当該ロットの原価の記録から引き継ぐ。

| 費用の状態 | 課税価格への反映 |
| --- | --- |
| 対象で、評価用価額に含有済み | 費用の種類と対象区間を照合し、追加額0円。運賃込みの単価を受け取る場合も同じ。 |
| 対象で、評価用価額と別 | 同じロットに帰属する確認済み金額を一度加える。試行ではタイの輸入港までに帰属する適格な運賃・保険・関連費用を対象とする。 |
| 対象外または明示のゼロ | 理由と根拠を残し、追加額0円。輸入地点より後の配送費は今回の課税価格の対象外。 |
| 金額・対象区間・包含が不明 | 該当する費用の判定と課税価格を保留。税率が0%と明示されていても、課税価格は未確認として表示する。 |

依頼書の代表例に限り、70円／個の全額を評価対象とし、保険・その他の追加額を明示の0円とする。実務へ適用する際は、運送・保険等の証憑で輸入地点までの対象額を確定する。70円にはモデル上の輸出通関費が含まれるため、実際に課税対象になる内訳は費目ごとに確認する。

### 実務に適用する前に確認する項目

| 項目 | 確認状況と根拠 |
| --- | --- |
| 取引形態と評価方法 | モデルでは同一法人の移送。WTO協定第1条の取引価額法は輸入国向けの輸出販売を前提とする。売買を伴わない実際の輸入では、タイ税関の評価方法の適用順に沿って評価方法と証拠を確認する。実際の評価額・評価方法は未確認。 |
| 加算費用 | WTO協定第8条第2項は輸入地点までの運賃・荷役等・保険の扱いを加盟国の法令に委ねる。実際の対象範囲と包含はタイ側の規則および証憑で確認する。 |
| 品目・原産地・適用時点 | `3304` はモデルの見出し。実物の詳細品目分類、原産地の適格性と証明、輸入時点の適用税率・為替・丸めは未確認。0%と30%はモデルの試行値。 |
| 輸入者と納税義務 | モデルでは `E_JP` に帰属。実際の輸入者名義、通関申告、納税義務の確定時点は未確認。 |

[タイ税関の課税評価資料](https://www.customs.go.th/content.php?ini_content=customs_valuation_01&ini_menu=menu_) ・ [WTO関税評価協定 第1〜8条](https://www.wto.org/english/docs_e/legal_e/20-val_01_e.htm)

## 3. 負担法人・計上週・件数（提案）

- **関税の確定週**に `E_JP` が負担する回収不能な輸入関税を、そのロットの取得原価に一度算入する。通関記録のうち、関税の負担額が確定した事象を使う。受入前なら輸送中在庫に算入し、受入時はその原価をDCへ振り替える。販売時に在庫の関税分を売上原価へ振り替える。支払週は納付記録で別途追跡する。[Value Chain設計 v1.0 §0.1 D-3・§2.3](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md#L11-L67)
- **受入週を代理にできる条件**は、通関確定週と受入週が同一ISO週になることを試行条件として大杉さんが採用し、その対応が当該ケースで確認できること。代理であることと受入記録を残す。週をまたぐ可能性が解消されないときは計上週を保留する。
- **1件**は、今回の1申告明細が1ロットに対応する場合の正額の関税取得原価明細を指す。出荷から区間と `Lot_ID` で通関申告・明細を照合する。同じ申告明細とロットの再取込は同一の関税として照合し、訂正は元明細を追える形にする。明示0%では評価記録を残し、正額の取得原価明細は0件。

## 4. 代表1ロットの手計算と週別期待結果

クリーム24個、JPY。保険・その他の追加0円。週は検証用の仮定で、2028-W28に日本出荷、2028-W30に通関確定・タイDC受入、W30末は未販売と置く。

| ケース | 単価 × 24 | 運賃の追加 | 課税価格 | 関税 0% | 関税 30% |
| --- | ---: | ---: | ---: | ---: | ---: |
| T14方式を1ロットで再計算（比較） | 5,000 × 24 | 0円 | 120,000円 | 0円 | 36,000円 |
| 評価用商品価額が運賃別（推奨） | 5,000 × 24 | 70 × 24＝1,680円 | **121,680円** | 0円 | **36,504円** |
| 同じ価額が運賃込み（照合例） | 5,070 × 24 | 0円 | **121,680円** | 0円 | **36,504円** |

推奨案とT14方式の関税差は、30%で504円／ロット、0%で0円。運賃込み5,070円／個に同じ70円／個を重ねた場合の123,360円・関税37,008円は、重複を検出する比較値。

| ISO週・事象 | 法人 | 関税の期待額と件数 |
| --- | --- | --- |
| 2028-W28 出荷、W29 輸送中 | `E_JP` | 関税の正額明細0件。 |
| 2028-W30 通関確定・受入、30% | `E_JP` | 取得原価に36,504円・1件。受入に伴う関税の追加0件。 |
| 2028-W30 通関確定・受入、0% | `E_JP` | 課税価格121,680円・税額0円の評価記録。正額明細0件。 |

この例で区間運賃1,680円が `E_JP` の適格な取得費用として確定した場合、運賃・関税を入れる直前のロット原価に対し、W30末の在庫原価増分は30%で38,184円、0%で1,680円。既計上の運賃は引き継ぎ、追加算入は0円。課税価格121,680円の用途は関税計算に限る。

## 5. 読取基準と設計への引継ぎ

入力とM0報告の参照版は依頼書指定の `9eefff8fee8d3807f6f5adffb254fd53b6f92e2d`。開発台帳 §4、M0報告書 §6・T14、金額仮定書（本文 v0.2） §§2.3・4.1・4.3・5.1、Value Chain設計 v1.0 §§0.1・1・2、下記サンプル入力を読んだ。M0/M0tの付録CSVでもタイ0%／30%と `transfer_price` を確認した。G2反映後の `ccf2b40` では Start Here §7・G2報告の完了記録を確認した。採用後の設計ではG2反映後の版を基準とする。下記のサンプル入力は指定版と一致する。

[M0関税入力（付録）](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0/ppc_tariff_rule.csv#L8-L9) ・ [M0t関税入力（付録）](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_appendix/money_csv/M0t/ppc_tariff_rule.csv#L8-L9)

[開発台帳 §4](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/requests/BSSEAF_Roadmap_Loop_Ledger_v0.1.md#L67-L81) ・ [法人割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv#L15-L20) ・ [数量設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/planning_config.csv#L4) ・ [Value Chain価格](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv#L2-L7) ・ [区間費用](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_edge_cost_rule.csv#L6-L9) ・ [関税設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_tariff_rule.csv#L6-L9) ・ [PPC振替価格設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_transfer_price_rule.csv#L2-L3) ・ [G2反映後のStart Here §7](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/ccf2b40c3dddbbaa60312b8ad2b80d2a064bca35/docs/WOM_Start_Here.md#L203) ・ [指定版との比較](https://github.com/Yasushi-Osugi/wom_development_composite_node/compare/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d...ccf2b40c3dddbbaa60312b8ad2b80d2a064bca35)

## 6. 大杉さんの採用判断と受入値

| 採用する条件 | 選択肢と推奨理由 |
| --- | --- |
| 評価用価額の基礎 | **試行は5,000円／個を運賃別の評価用価額として採用**。T14方式を比較用に残すと、運賃の算入効果を1ロットで確認できる。運賃込み5,070円／個の入力も同額になることを照合する。 |
| 算入範囲と試行料率 | **輸入地点までの対象費用を一度だけ算入**。代表例は運賃70円／個、保険・その他0円。0%と30%を両方使えば、課税価格の内訳と税額を独立に確認できる。 |
| 負担法人と計上週 | **`E_JP` の在庫原価に通関確定週で計上**。受入週を使うのは同一週の条件を採用した試行に限る。実際の週差を把握できる場合は、通関と受入をそれぞれの週で扱う。 |

**受入値**は、どちらの入力形態でも課税価格121,680円、30%で2028-W30に `E_JP` の関税取得原価36,504円・1件、0%で税額0円・正額明細0件。出荷・受入それぞれを起点とした重複は0件。`Lot_ID` と申告明細で照合する。

実際の通関・運送・保険・納付の原票、詳細品目分類と原産地、M0/M0tの実行時の `output/` のロット明細は未確認。週別の受入値は仮定に基づく手計算で、WOM実行による検証はこれから行う。大杉さんの採用後、Claude君へこの定義と[共通照合表](WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md)を渡す。
