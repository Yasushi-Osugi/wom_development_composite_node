# 化粧品 G4・G5 関税と海上運賃の業務定義依頼 v0.1

- 宛先：GPT-MC君（業務定義担当）
- 依頼者：大杉
- 引継先：Claude君（設計担当）
- 日付：2026-11-12
- 状態：依頼書ドラフト
- 参照基準：`wom-v1r6m0_BS-SEAF`、コミット `9eefff8fee8d3807f6f5adffb254fd53b6f92e2d`

## 1. 依頼する成果物

G2の実装・検証と並行して、化粧品の週次経営シミュレーションで使うG4・G5の業務定義案を作成してください。**G4はタイ向けの課税価格、G5はシンガポール向けの運賃負担と在庫原価**です。それぞれクリーム24個（1ロット）から始め、採用条件と手計算の期待結果を示してください。

| 成果物 | 記載すること |
| --- | --- |
| `WOM_G4_TariffBase_Business_Definition_v0.1.md` | 日本→タイの社内移動で使う試算上の課税価格、税額、負担法人、計上週 |
| `WOM_G5_CIF_FreightResponsibility_Business_Definition_v0.1.md` | 日本→シンガポールの法人間取引での運賃負担、法人別・連結の原価、計上週 |
| `WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md` | 二つの取引を並べ、価格に何が含まれ、何を別に加算・計上するかを確認する共通表。両定義書から参照する。 |

今回の成果物は業務定義と期待結果です。大杉が採用する前提を記録し、G2の反映後の基準版を確認したうえで、Claude君がWOMに対応付けます。

## 2. 確認する資料

| 確認すること | 参照先 |
| --- | --- |
| G4・G5の範囲とM0の観測 | [開発台帳 §4](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/requests/BSSEAF_Roadmap_Loop_Ledger_v0.1.md#L67)・[M0報告書 §6](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L429-L435)・[T14・T15](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md#L474-L491) |
| 取引、価格、試行条件 | [金額仮定書 §§2.3・4.1・4.3・5.1](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md)・[法人割当](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/vc_node_assignment.csv)・[Value Chain価格](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/vc_price_rule.csv) |
| 入力にある運賃と関税 | [区間費用](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_edge_cost_rule.csv#L6-L9)・[関税設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_tariff_rule.csv#L6-L9)・[PPCの振替価格設定](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/9eefff8fee8d3807f6f5adffb254fd53b6f92e2d/data/sample/cosmetics-sg-th-2027-2029/ppc_transfer_price_rule.csv) |

M0・M0tの結果は**観測**、サンプルに採用された条件は**現行のモデル前提**、今回の計上方法は**提案**として区別してください。読んだ版・箇所と、原本を確認できなかったものを示してください。

## 3. G4 日本からタイへの社内移動

`WH_JP_Released → DC_TH` の両端は日本本社 `E_JP` の拠点です。M0tではPPCの振替価格設定（クリーム5,000円/個、美容液6,000円/個）を計算に使いました。**タイのDCへの移動に法人間売買を置くという意味ではありません。** タイDCから外部代理店への卸売とも区別します。

**最初の照合例**：クリーム24個、輸送費70円/個。M0tの比較に合わせ、この例だけは保険その他の追加額を0と置き、30%は感度試算の料率とします。

| 試算ケース | 1ロットの課税価格（試算） | 30%での関税 |
| --- | ---: | ---: |
| M0tの現行計算：5,000円/個だけを基準にする | 120,000円 | 36,000円 |
| 運賃別の評価用商品価額5,000円/個に70円/個を加える案 | 121,680円 | 36,504円 |
| 同じ価額を運賃込み5,070円/個として与える確認例：70円を再加算しない | 121,680円 | 36,504円 |

- **業務判断**：この社内移動で使う評価用商品価額の根拠、輸送費・保険等のうちどこまで課税価格に含めるか、すでに含む項目の扱いを提案してください。70円はモデルの区間費用で、実際の課税対象の費目内訳が確認済みという意味ではありません。
- **計上の判断**：誰が輸入時の関税を負担し、どの事象の週に何件計上し、在庫原価に算入するかを示してください。通関の記録を使えない場合は、受入週等で近似できる条件をモデル上の仮定として明記してください。
- **確認の境界**：M0の0%では税額の差が出ないので、課税価格そのものも照合してください。追加額が明示の0である場合と、必要な金額・包含関係が不明な場合を区別します。1ロットの差504円とT14の全期間差347,256円は、運賃を加える前提での比較値です。
- **実務上の根拠**：0%・30%は試行条件です。現実の評価方法・税率を記載するなら、[タイ税関の課税評価資料](https://www.customs.go.th/content.php?ini_content=customs_valuation_01&ini_menu=menu_)と[WTO関税評価協定](https://www.wto.org/english/docs_e/legal_e/20-val_01_e.htm)を出発点に、取引形態、品目分類、原産地、適用時点、根拠を別欄に示してください。確認できない点は未確認としてください。

## 4. G5 日本本社からシンガポール販社への法人間取引

`WH_JP_Released → DC_SG` は、日本本社 `E_JP` からシンガポール販社 `E_SG` への取引です。金額仮定書では、日本本社が海上運賃を負担し、運賃を含む法人間価格を設定しています。M0のValue Chainでは、区間費用60円/個をその価格にさらに加え、`E_SG` の在庫原価に入れたと報告されています（T15、全期間4,848,480円）。

**最初の照合例**：クリーム24個、運賃込みの法人間価格5,000円/個、海上運賃60円/個。この例の比較は当該取引と運賃に限り、ほかの取得費用を含めません。

| 観点 | 1ロットの照合値と判断してほしいこと |
| --- | --- |
| 日本本社 `E_JP` | 外部の運送業者への負担は **1,440円（24 × 60）**。支払先、負担が確定する事象、どの週の費用または原価にするかを示す。 |
| シンガポール販社 `E_SG` | 法人間価格の部分は **120,000円（24 × 5,000）**。この中に同じ運賃が含まれるので、1,440円を重ねて121,440円にしない。輸送中を含めてどの週から在庫原価を認識し、どの週に売上原価へ振り替えるかを示す。 |
| グループ連結 | 法人間の売買を消去した後、外部運賃1,440円がどこに残るかを示す。期末に未販売のときと販売後を分け、在庫・売上原価・期間費用のどれで追うかを明記する。 |

**海上運賃を誰が支払うか、契約上誰が負担するか、誰の在庫原価にいつ入るか**を分けてください。例えばW28に船積み、W29に受入、W31に外部販売と仮定し、W30末の在庫とW31の費用・原価を照合します。支払週は計上週と区別します。

価格に運賃を含めず、買い手が別途負担する取引は対照例とし、今回のCIF前提と何が変わるかを示してください。[ICCのCIF解説](https://academy.iccwbo.org/incoterms/article/incoterms-2020-cip-or-cif/)は費用負担等の契約条件の確認に使い、在庫の認識時点と計上方法は当該モデルの前提と根拠を別に示してください。

## 5. 共通照合表と提出時の確認

以下の形で二つの区間を並べてください。**同じ運賃を課税価格の算定と帳簿で参照することは用途が異なります。** 照合するのは、同一の課税価格や同一の在庫原価の中で、含有済みの運賃を重ねていないことです。

| 照合欄 | G4 日本→タイ | G5 日本→シンガポール |
| --- | --- | --- |
| 区間・法人・取引の種類 | `E_JP → E_JP`、社内移動 | `E_JP → E_SG`、法人間取引 |
| 数量・通貨・価格の用途 | 24個、JPY、評価用商品価額 | 24個、JPY、運賃込みの法人間価格 |
| 運賃・保険等と価格への包含 | 70円/個、別・込み・不明を区別 | 60円/個、運賃は価格に含む。その他の費用は根拠を確認 |
| どの金額に、何を一度だけ入れるか | 課税価格・税額 | 法人別の取得原価・費用と連結で残る外部費用 |
| 誰が、どの週に記録するか | 負担法人、通関・受入等の根拠、費目・件数 | 運送業者への支払法人、費用・原価の帰属、出荷・受入・販売等の根拠、費目・件数 |
| 証拠と未決事項 | 入力値・仮定・不足情報、追加が0か判定保留か | 入力値・仮定・不足情報、運賃を別請求する場合や保険が不明な場合の扱い |

各定義書の最後に、**大杉が採用する条件、選択肢と推奨理由、代表1ロットの期待額・法人・週・件数、確認できない範囲**をまとめてください。後続の検証で元の出荷・費用を追えるよう、区間・Lot_ID・費用の根拠記録をどう照合するかを示します。PPCとValue Chainの全期間合計が一致しても、課税価格の内訳や法人別の負担・計上週はこの表で個別に確認します。
