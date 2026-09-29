# WOM LOVEM 段階C 独立照合報告書

対象：ev-thailand-2026／依頼書 RequestLetter_LOVEM_StageC_to_Astra.md  
作成：2026-09-30（日本時間）／Astra独立照合  
範囲：観測ファイルの読み取り・照合のみ。core・CSV原本・golden・入力runの変更、commit／pushなし。

## 1. 結論と判定一覧

**identityは今回の独立照合で対象規則への違反を検出しなかった。legacyは例外1・2を検出した。段階Cの依頼範囲は完了。**
PASSは、下記の入力・モデル・観測範囲についての判定であり、他モデルや金額評価を認定するものではない。

| 検査 | legacy | identity | 根拠・限定 |
|---|---|---|---|
| Q01 観測範囲・区間復元 | PASS | PASS | 各37,856セルの全multiset一致。既知の未取得項目は§9 |
| Q02 元需要の保存 | PASS | PASS | 63,240要求の状態分割。物理的な供給元の証明とは別 |
| Q03 ノード内物量保存 | PASS | PASS | 各14node×104週=1,456セル、ID multisetで一致 |
| Q04 ノード間移動 | FAIL | PASS | legacyの市場P 5,020 IDに親の実出荷なし。到着記録なしは63,240 |
| Q05 出荷の根拠 | FAIL | PASS | legacyの5,020 IDは根拠のない同週Pから出荷。局所的な物量式だけなら両方式PASS |
| Q06 要求週と実出荷 | FAIL | PASS | legacy工場の早出し3,581、未出荷かつCOなし400 |
| Q07 CO連続性 | FAIL | PASS | legacyで次週CO不足3,981件。identityで重複・更新不整合0 |
| Q08 Kitting | NOT_APPLICABLE | NOT_APPLICABLE | stockyard／Kittingがないモデル |
| Q09 休業・能力 | PASS | PASS | 休業6 node週の実出荷0、操作別effective_limit超過0 |
| Q10・Q11 金額 | NOT_APPLICABLE | NOT_APPLICABLE | 段階D、今回の対象外 |
| Q12 観測非干渉 | PASS※ | PASS※ | 同梱OFF／ON証拠の全fingerprint一致 |

※Q12は**証拠の確認のみ**。独立環境でPlanning ON／OFFを再実行していない。
Q01のPASSも、state_digestsと原資料の内部整合を示す。観測器が実行時に記録しなかった事実まで証明しない。

## 2. 入力・基準の固定

依頼基準a43163fとrun生成3481fc5の差分は、段階C依頼書の追加だけ。コード・モデルデータは同一。
受領ZIPの取得commitは9d5e5f7。解析対象はZIP内に固定し、その後のブランチの状態を混ぜていない。

両runのmanifest：
- code_sha：`3481fc5b30ba88f8bb445d1ced888212b3221591`
- dirty：false。manifestのdirty判定対象はwom／tools／data、未追跡対象ファイルなし。
- lot_flow_mode：各ZIPと一致するlegacy／identity。
- SHA256SUMS.txt：各32ファイルすべて一致。終了時にも再確認し一致。
- 需要アンカー・入力21CSVのhashは両runで一致。
- 展開後demand_anchors JSONLのSHA-256：`25457b988522438e40256d69b80d0dec8a5aed2c92646e03cc67de836ca58f6a`
- 期間：2026-W02〜2027-W52、104週、14node、2製品。週ラベルはweeks.csvを正本とした。

両runはrun_idが同じ `ev-thailand-2026@3481fc5:obs`。集計キーをrun_C_legacy／run_C_identityで分離した。同じrun_idだけで結合していない。

| 入力ZIP | SHA-256 |
|---|---|
| handoff_ev-thailand-2026_C_legacy.zip | 52ee394db57d6f6b935bd8b7277e51668a6b2b0005b2041f410ef16233abafd7 |
| handoff_ev-thailand-2026_C_identity.zip | b8058ea3f6d467b4cda20b7c86629b5752281d15973069487411314370f8554b |

`input_verification.json`にファイル別hashとGit差分の確認結果を収録。補助読解に使ったsc_tree_master.csv等は、Git LF原本またはそのWindows CRLF表現のhashがmanifestと一致することを確認した。意味上の近似比較ではない。

## 3. 独立性・先行fixture

WOM／LOVEM／既存checkerの関数をimportせず、Python標準ライブラリだけで原データを読んだ。規則は需要IDの同一性、node自身の要求週、物量保存、実出荷に基づく到着、CO持越し。RELから経路を決めず、node tree・需要アンカー・LTから経路を作り、その経路にRELを照合した。

F1〜F8は実データの判定結果を見る前に実行し、8件成功した。これらは同じinterval/eventレコード形式の小さな規則テストであり、完全なWOMモデルや観測器runの再生成テストではない。

| Fixture | 検証した正解 | 結果 |
|---|---|---|
| F1 | 要求週と同ID実出荷が一致 | PASS |
| F2 | 後週の同ID出荷を遅配とする | PASS |
| F3 | 未出荷とCO持越しを表現 | PASS |
| F4 | node自身の要求より早い実出荷を検出 | PASS |
| F5 | 同数量・別IDを充足と扱わない | PASS |
| F6 | 親の出荷がない子Pを検出 | PASS |
| F7 | 休業時のIとCO併存を許し、充足後の残を0とする | PASS |
| F8 | 生産繰延べでも要求週に間に合えば当週出荷 | PASS |

**COの時間境界**：保存されたCO[w]は週へ持ち込まれた注文残。週末残は `CO[w]+S[w]−照合された実出荷[w]`、翌週COと比較する。出荷週の保存CO[w]にIDがあるだけでは違反としない。最終週の翌スロットはないので、期末残は式から導出する。依頼書F7の「出荷週に消える」は、この週末残に対する説明である。

## 4. SE2：168 lotの正体

| 方式・週 | 予定S | 実出荷 | 数量不足 | 要求IDと同週出荷の交差 | 別IDの出荷 |
|---|---:|---:|---:|---:|---:|
| legacy 2026-W38 | 150 | 132 | 18 | 0 | 132 |
| legacy 2026-W39 | 150 | 0 | 150 | 0 | 0 |
| identity 2026-W38 | 150 | 150 | 0 | 150 | 0 |
| identity 2026-W39 | 150 | 150 | 0 | 150 | 0 |

legacyの要求300 IDの全期間履歴は以下。**遅配0、未出荷0、早出し300**。

| 工場要求週 | 同じIDが実際に出荷された週 | ID数 |
|---|---|---:|
| W38 | W36 | 18 |
| W38 | W37 | 132 |
| W39 | W37 | 18 |
| W39 | W38 | 132 |

W38に代わりに出荷した132 IDは、工場W39の要求IDだった。168は18＋150という**二週の数量差**であり、遅配168 IDの集合ではない。数量の差とIDの未充足は同じものではない。

例：`EVmaker_Import:BKK:2026-W45:00001` は工場W38要求。legacyはW36、identityはW38に出荷。市場要求W45を上流の早出し判定に使っていない。

各runの `se2_weekly_reconciliation.csv` と `se2_id_reconciliation.jsonl` に全件を収録。legacy JSONLは要求300件＋別ID出荷132件の432行で、同一IDを異なる役割の行に含むため432ユニークIDではない。identityは要求300行。

## 5. 物量・移動・充足の照合

### 5.1 局所の保存と供給の根拠を分ける

両方式で、全node・全週の `前週I＋P＝当週I＋実出荷` がIDごとに一致。COは物量へ足していない。初週は期首物量0として照合し、残差はなかった。ただし独立したopening-inventoryイベントは入力にない。

legacy市場のP 63,240 IDすべてに到着イベントがない。そのうち58,220 IDは、親の実出荷・経路・LTから同じ入庫を独立に対応づけられる。残り**5,020 IDは親の実出荷がないのに市場Pと実出荷に現れる**。この二つの件数は重なっており足さない。

分類：Q04・Q05は**WOMの不整合／legacy例外2**。記録がないだけの63,240件と、物の裏付けもない5,020件を区別する。Demand Pのコピーによる入庫は、局所の物量式を成立させても供給の証拠にならない。

identityでは232,880件のRELをID・数量・経路・週で照合し、到着とPの不一致0。legacyは174,660件。差58,220件はleafへの実際の到着。両runとも期末の輸送中（期間外到着）0。

### 5.2 要求・CO

Factory_Import_CNの最終Demand Sは9,770要求。

| 状態 | legacy | identity |
|---|---:|---:|
| 当週出荷 | 5,789 | 9,370 |
| 早出し | 3,581 | 0 |
| 期末注文残 | 0 | 400 |
| 未出荷だがCO記録もない | 400 | 0 |
| 遅配 | 0 | 0 |

分類：legacyのQ06・Q07は**WOMの不整合／例外1**。Q07の次週CO不足は3,981 node週ID件。Q06の3,581／400と関連した別検査で、独立した追加不足として加算しない。両方式とも保存CO内の同ID重複は0。push_subは要求なしで送る契約のため早出し・要求CO検査から除外し、物量・移動は検査対象とした。

### 5.3 休業・能力

Factory_Local_THの2026/2027-W32、Factory_Import_CNの2026/2027-W40・W41、計6 node週で、実出荷は全IDで0。pushは実出荷を操作系列として比較し、休業週の入庫を能力違反にしなかった。他nodeはPとeffective_limitを比較し、超過0。raw_hard／raw_softの業務意味の再審議は今回の範囲外。

## 6. 期末注文残5,020 IDと工場400 ID

市場期末注文残はLocal 3,850、Import 1,170、合計5,020。全件について同製品7nodeの履歴、計35,140行を保存した。この5,020 IDはidentityの観測期間内にSupply Pがどのnodeにもなく、実出荷もない。Demand Pの存在と現物供給を区別した。

| 証拠による区分 | ID数 | 読み方 |
|---|---:|---|
| past_due記録あり、LTだけで必要上流週が期間前 | 4,090 | 開始端の説明と整合 |
| past_due記録あり、LT＋安全在庫週で期間前 | 730 | LTだけでは説明できない。DCの安全在庫offsetを含めると整合 |
| past_due記録なし、部材必要出荷週が期間内なのにSupply Pなし | 200 | 開始前だけでは説明できない。原因未確認 |

4,820件にはBackwardのpast_dueイベントがある。ただしイベントのweek_indexは**要求側の週**で、負の必要週そのものではない。上表の必要週はnodeのLTと、hash照合済sc_tree_masterのss_daysから別途算出した導出値。DC_Localの安全在庫1週、DC_Importの2週を考慮した。これは原因の完全な証明ではない。

Factory_Import_CNの400件は次の8群。部材Components_CNの輸送LT2週だけで逆算する。

| 工場要求週 | 市場週 | ID数 | 部材必要出荷index |
|---|---|---:|---:|
| W02 | W09 | 60 | -2 |
| W02 | W10 | 40 | -2 |
| W03 | W10 | 60 | -1 |
| W03 | W11 | 40 | -1 |
| W04 | W11 | 60 | 0 |
| W04 | W12 | 40 | 0 |
| W05 | W12 | 60 | 1 |
| W05 | W13 | 40 | 1 |

index0=2026-W02。200件は期間前、残り200件はW02/W03に部材が出荷されればLT上は間に合う。全400件のSupply P不在は確認したが、後半200件の生成・配置が欠ける原因は断定しない。Mode4等の詳細原因調査へ自動延長していない。

「400件が全期間CO」は厳密には、100件ずつ要求が立った後に持ち越される。保存COの初出はindex1/2/3/4（各100）、以後期末まで継続。初週から400件があるわけではない。また「市場W09〜W13のlotが作られない」は**この400 IDに限る**。同じ市場週の別IDまで全数未生産という意味ではない。

## 7. 同一アンカーでのrun比較

| legacy → identity 市場状態 | ID数 |
|---|---:|
| 当週出荷 → 当週出荷 | 58,220 |
| 当週出荷 → 期末注文残 | 5,020 |
| 遅配への変化 | 0 |

P／実出荷の履歴が変化したのは8,601ユニークID、12,182 node-ID組。市場状態が変わらなくても、工場／SPの早出しが是正された3,581 IDを含む。内訳は工場3,581、SP_Import3,581、市場leaf計5,020。

最初に観測される差の例：
- `EVmaker_Import:BKK:2026-W02:00001`：市場W02でlegacyはP・実出荷各1、identityは両方なし、注文残。
- `EVmaker_Local:BKK:2026-W02:00001`：同じく市場W02のP・実出荷が消え、注文残。
- `EVmaker_Import:BKK:2026-W45:00001`：工場legacy W36出荷がidentity W38へ。市場の当週出荷自体は維持。

全件はmarket_transitions、node_ID_differences、earliest_observed_differences。最小週の差は**観測上の最初の差**であり、因果上の根本原因とは呼ばない。I／CO差の全件比較は別のnode履歴を参照する。

## 8. reportedとの照合・止める理由

Code君の主なreported値（37,856復元、早出し3,581→0、SE2 132/0→150/150、工場残400、市場残5,020、leaf到着増58,220）は独立集計と一致。

**説明をそのまま採用すると誤読になる点**：
1. SE2の168を「後日回復した遅配168 ID」とする解釈は不成立。対象要求300 IDはlegacyで全件早出し。
2. 工場400件を一括して「必要部材出荷週が期間前」とする解釈は不成立。200件はLT逆算で期間内、原因未確認。
3. 「全期間CO400」「市場W09〜W13は生産されない」は対象IDと週境界を省くと過大な表現。
4. manifestの`cap_hard_sealed_lot_ids`説明に「COへ入る」が残るが、identityの決定D4は翌週Pへの繰延べ。説明の陳腐化として扱う。このモデルでのsealed ID観測を得たとは認定しない。

identityの段階C受入を止める新たな保存・移動の違反は検出しなかった。legacyの既知例外は検出成功。上記の説明を直さずに原因確定・供給成立と読み替えることは止める理由になる。core修正案は本報告に含めない。

## 9. 観測限界・段階Dへの申し送り

- demand_fulfilment_linkは未保存。本モデルではnode/ID要求が一意で、実出荷と対応可能だったため派生照合した。匿名在庫／同ID複数要求／BOMへは一般化しない。
- capacity封印・繰延べ対象IDの直接記録がない。F8は規則試験であり、実runの対象全IDを認定したものではない。
- `nodes.csv`に安全在庫・初期在庫offsetがない。今回の開始端読解では、固定SHAのCSVと静的コード説明を補足した。effectiveなBackward offsetの観測値そのものではない。
- within_week_orderは部分記録のみ。同じ週のPと実出荷の一致から日内の処理順序を断定しない。
- 初週前の実際の生産履歴は未取得。期間端の必要週は導出、観測は期間内とpast_dueに限る。
- inbound pullのPコピー、parentを持つinline push等のcoverage gapはmanifestのとおり。このモデルでQ04が通ることを全モデルの保証にしない。
- 段階Dでは全nodeの実出荷ID／週／数量とPPC入口の対応証拠が必要。今回のrunではPPC入口レコードは未取得、金額は未照合。Q12に含まれるPPCファイルhash一致は金額の正しさの認定ではない。
- Windows GUI・マウス操作・表示は今回未検査。Headless planningの再実行もしていない。ファイルcheckerだけをLinuxで実行。
- 実行環境・fixture結果はexecution.json、実行方法はtools/lovem_checker_c/README.md。

## 10. 成果物とhash

- Repository配置用ZIP：checker、fixture、報告書、checks.csv、SE2全件、小さな集計・証拠を元の相対pathで収録。
- RawData ZIP：1,000,000 byteを超えるCSV9件を別配布。これらをそのままgit addしない。
- 原入力ZIPは今回のブランチhandoffに保存済み。本配布に再複製していない。
- 全配布ファイルのhashはSHA256SUMS_STAGEC.txt、ZIP内部ファイルのhashはPAYLOAD_SHA256SUMS.txt。原入力検証はinput_verification.json。

### 大きいCSVの件数・SHA-256

| path（stageC/以下） | 行数 | SHA-256 |
|---|---:|---|
| comparison/backlog_boundary_evidence.csv | 5020 | `f52919f5fb555a845f439b0859e9b9c5fdde29080bea05baf4dc97ff4233e749` |
| comparison/market_transitions.csv | 63240 | `61dd717c1eb7a425fb054dfd3ad7a0ff580cef5061343cf7c09f7b1c59f6d634` |
| comparison/node_ID_differences.csv | 12182 | `11618e24326ccec2eff42231bdeb28865804ca819e5cfae7d2baaea7d979be81` |
| run_C_identity/backlog_histories.csv | 35140 | `3dc41eebb80a8828ac0fdf5ba399b79e7544f0a0791dbbf2390488bc08078176` |
| run_C_identity/market_states.csv | 63240 | `ea4b2eb17270f764e6ac2caab900a1962c66a1150b4b83750f22ee586861ad57` |
| run_C_identity/node_ID_states.csv | 295646 | `6822aede92849d9c0ba4257ba50e112cd56b79c89ddca112ca48826bcd5df2b9` |
| run_C_legacy/market_states.csv | 63240 | `a30c3563beea41dcfa22ba18770cba077f1c18252b771f29e7c71b4f0023cf3c` |
| run_C_legacy/node_ID_states.csv | 295646 | `7b3fb402800caf84834d00bb47c85160461537ca3cd0787a35bbcd0e25816cbc` |
| run_C_legacy/violations.csv | 81242 | `1b9706a553836c0d1912aeb9a440168953b793613b72201177fc5175cd16abce` |

### FAILの例（各検査最大5件、全件はviolations.csv）

| Q | 種別 | node | 週 | Lot_ID |
|---|---|---|---|---|
| Q04 | P_without_arrival_record | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00001 |
| Q04 | P_without_parent_shipment_at_LT | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00001 |
| Q04 | P_without_parent_shipment_at_LT | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00002 |
| Q04 | P_without_parent_shipment_at_LT | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00003 |
| Q04 | P_without_parent_shipment_at_LT | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00004 |
| Q05 | shipment_with_unbacked_same_week_receipt | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00001 |
| Q05 | shipment_with_unbacked_same_week_receipt | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00002 |
| Q05 | shipment_with_unbacked_same_week_receipt | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00003 |
| Q05 | shipment_with_unbacked_same_week_receipt | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00004 |
| Q05 | shipment_with_unbacked_same_week_receipt | OUT:leaf_out:BKK:EVmaker_Local | 2026-W02 | EVmaker_Local:BKK:2026-W02:00005 |
| Q06 | early | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W06 | EVmaker_Import:BKK:2026-W13:00001 |
| Q06 | unshipped_without_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W02 | EVmaker_Import:BKK:2026-W09:00001 |
| Q06 | unshipped_without_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W02 | EVmaker_Import:BKK:2026-W09:00002 |
| Q06 | unshipped_without_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W02 | EVmaker_Import:BKK:2026-W09:00003 |
| Q06 | unshipped_without_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W02 | EVmaker_Import:BKK:2026-W09:00004 |
| Q07 | missing_next_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W03 | EVmaker_Import:BKK:2026-W09:00001 |
| Q07 | missing_next_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W03 | EVmaker_Import:BKK:2026-W09:00002 |
| Q07 | missing_next_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W03 | EVmaker_Import:BKK:2026-W09:00003 |
| Q07 | missing_next_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W03 | EVmaker_Import:BKK:2026-W09:00004 |
| Q07 | missing_next_CO | IN:mom:Factory_Import_CN:EVmaker_Import | 2026-W03 | EVmaker_Import:BKK:2026-W09:00005 |
