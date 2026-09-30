# Request Letter：iPhone warmup・EV update Kitting・S2実出荷評価の整合化

- 宛先：Claude Code君（実装担当）
- 依頼者：大杉（WOM Project Owner）
- 起草：Astra／2026-09-30
- レビュー・改訂：Claude君／2026-09-30（改訂箇所は末尾「改訂の要点」）
- 状態：実装依頼。大杉さんから本書を渡された時点で、以下の範囲に着手する。
- リポジトリ：Yasushi-Osugi/wom_development_composite_node
- ブランチ：wom-v1r5m1_cap_trial
- 基準SHA：`979cf7afb669a5eba17318ad81ff4f4525dd7641`
- 基準の報告値：593 passed／3 skipped。これは再実行済みの認定ではなく、Code君の報告値。
- commit・push・mergeはしない。最終diffは大杉さんが確認する。

## 1. 目的と終了条件

次の三件を、原因・変更・測定結果が対応する形で完了する。

| 区分 | 対象 | 目標 |
|---|---|---|
| A：残課題1 | iphone_global | 旧capacity CSV書式でもwarmupを適用でき、17／26週の結果から設定を決め、残存注文残を再分類する |
| B：残課題4 | ev-thailand-2026_update | 二つの部材をKittingで一つの完成需要へ変換し、同IDの部材を完成品Pとして二重計上する構造を解消する |
| C：S2 | FlowCheck報告書§6 S2 | identityの充足・販売実績の計算を実出荷に整合させ、要求・計画の表示と区別する |

S2は `docs/development/WOM_FlowCheck_WarmupTrial_Report.md` の「S（要求）を『充足・売上』として使っている計算が残っている」を指す。CockpitのS2 PlaceやWarmup報告書の副作用S2とは別である。

全テストの成功、意図したgolden差分と残課題の説明、Windows GUI確認の結果または未確認項目を報告して終了する。注文残・遅配をすべてゼロにすることは終了条件ではない。

## 2. 最初に読むもの・作業の分離

1. `CLAUDE.md`、`AGENTS.md`、関係ディレクトリの指示。
2. `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md` v1.4、特に基本ルール・D4・D5・D7・D7a。
3. `docs/development/WOM_Warmup17_IdentityGolden_Report.md`（基準commit版）。
4. `docs/development/WOM_FlowCheck_WarmupTrial_Report.md` §3.4・§6 S2。
5. `docs/development/WOM_LotIdentityFlow_Report.md`、既存Stockyard／Kittingの設計・テスト。
6. `docs/design/planning_warmup_and_reporting_horizon.md`、LOVEM v0.2設計の数量・金額境界。

作業前にHEAD、対象ファイルの差分、実行環境を記録する。HEADが進んでいたら基準との差分を読み、今回と重なる変更を混ぜない。Obsidian Vaultの未commit変更・個人ファイルを変更、退避、削除しない。

A→B→Cの順に進め、各段階の出力を別ディレクトリへ保存する。結果を累積させる場合もAのみ、A+B、A+B+Cの差が説明できるようにする。大杉さんのWindowsを正本golden更新・最終GUI確認に使う。適合確認済み独立Linuxでのコード作業・Headless・pytestは既存許可の範囲でよい。

## 3. 共通の数量・評価契約

- Supply Sは要求位置。実出荷と同一視しない。
- 要求Xは、同じnode・需要IDの実出荷Xにより充足する。部材の同IDは完成品と同じ物理個体ではない。
- Iは物、COは要求。休業等でIとCOに同IDが併存すること自体をエラーにしない。
- 物量保存はnode・役割を区切り、前週I＋入庫＝実出荷＋当週Iを照合する。組立境界は部材消費と完成品生成を別に照合する。
- 週別の要求数量差、要求IDの当週充足、遅配、期末注文残を別に記録する。COの週初／週末の定義を明示する。
- 正常に観測された実出荷0を「データなし」と扱わない。記録欠損と0を区別し、欠損を予定Sで無言に補完しない。
- warmup期間の生産量、実需要開始時の在庫、報告期間の出荷量を別の列にする。

## 4. A：iphone_globalのwarmup対応

### A1 原因確認と修正方式

基準ではcapacity_plan.csvの見出しが `sku_id,region,week,max_supply,cap_pieces,source` で、warmup生成がnode_nameを必須として失敗すると報告されている。

実際のロード経路を確認し、旧書式がSKU・地域・nodeのどの単位の能力を表しているかを記録する。**空のnode_nameを足す、全nodeへ同じ能力を配る、regionを無根拠にnode名へ置換する修正は禁止。**

第一選択は、既存loaderが受理している旧書式をwarmup生成側でも扱い、書式と能力の帰属を保存する最小修正。SKU／region／node等の元の能力キーごとに、既存仕様と同じ元週から助走能力行を生成する。製品・地域を混ぜない。明確な対応を作れない場合は、CSV移行の対応表と影響を具体化し、その箇所だけ未決として報告する。対応を推測して本番CSVを書き換えない。

実需要期間の行・値、cap_hard／cap_softの意味、単位、元の販売価格・需要量は変えない。新書式のwarmup挙動も維持する。

### A2 試行と採用

修正後、複写モデルでwarmupなし／17／26を同じ設定で測る。52週は今回の採用候補に含めない。

- 17で期末注文残0なら17。
- 17で残る場合は26も測定し、期末注文残が減れば26、同数なら17を採用する。
- 26で増える・分類が矛盾する等の非単調結果は、入力差と原因を確認し、自動採用しない。
- 26でも残る注文残は残す。需要削減・能力引上げ・匿名期首在庫で消さない。

上の採用手順は本依頼で提示する実装方針であり、「warmup後も65,274件が必ず残る」とは仮定しない。基準の97,834＝能力分類65,274＋開始端32,560は比較対象として再計測する。

各条件で要求ID集合、当週出荷・遅配・期末注文残、最初に配置／供給が成立しなかったnodeと週、必要週の算出根拠を残す。原因分類は排他的な集計ルールを明記し、複数要因があるIDは補足列に残す。単に消えた件数を「開始端だった」と断定しない。

### A3 テスト

旧書式の複数SKU・地域、新書式の複数node、生成対象0行、必須キー欠損を含む小さな単体テスト。CSV→warmup→実loaderの結合テスト。再実行で同じ生成結果となり、既存の実需要期間行を変えないことを検査する。

採用した入力をiphone原本へ反映し、iphoneのidentity goldenをWindowsで再生成する。変更理由・前後数量・金額を報告する。他モデルのgoldenを一括更新しない。

## 5. B：ev-thailand-2026_updateの組立モデル修正

### B1 再現

FlowCheck報告では、Factory_Local_THにPlatform_Unit_AssyとMotor_Unit_Assy（ともにassembly）が直接接続され、各部材の同IDが工場Pへ追加されている。集合照合で片方が消え、保存差52,400が出る。

これは基準前の報告値なので、現在のwarmup17付き基準で再現し、P・実出荷・期末I・重複のnode週ID・到着元を保存する。最終市場が満たされることだけを正しさの根拠にしない。

### B2 実装方針

**このサンプルの二つのassembly部材について、既存Stockyard／Kitting Gateの標準構成を適用する。** 各部材の到着・在庫・払出を区別し、必要な同IDの部材がそろったときに完成品Pを1件だけ作る。

- Stockyard挿入前後の経路LT合計、休業、能力、需要、BOMの意味を保存する。既存のStockyardモデルの設定規則に従い、前後の対応表を作る。
- CSV参照が必要なnode／edge／route／cost／capacity等は整合を確認し、必要な行だけ追加・調整する。新しい置場を追加して原価や能力を二重計上しない。
- 部材欠品・遅着なら、そろった部材は在庫として残り、完成品を作らず、出荷要求は注文残となる。
- 部材がそろった後の回復、組立能力による繰延べ、休業を既存ルールで扱う。

`set()`によるPの重複削除、IDの改名、assembly→confluenceへの変更、Flow CheckのNGを対象外へ移すだけの処置は禁止。二つの部材が一つの完成品になる変換を観測可能にする。

既存Gateだけでは必要条件を満たさないと判明した場合は、最小再現と必要なcore差分を示す。本書は一般的なForward／Backward solverの再設計を承認するものではない。

### B3 受入

- 各部材の入庫・払出・残高の保存が成立する。
- Gate成立による完成IDとFactory Pが一致し、1需要セットから完成品が二重生成されない。
- 片方の部材を遅らせた複写ケースで、早い部材が消えず、部材がそろう前の完成・出荷が0。回復後は同じIDで充足する。
- 基準モデルのFlow Checkの既知NGが解消する。組立境界が汎用チェックの対象外でも、専用の部材消費・完成照合で全件を裏付ける。
- 変更後の市場充足、期末在庫、注文残、原価差を報告する。旧市場数量に合わせるために不足を隠さない。
- ev_update専用の回帰テスト／期待結果を追加する。既存のev-thailand正常系・SE2再現fixture・ev-europeを壊さない。

### B4 同じIDの重複を黙って捨てない（記録だけ）

`_match_by_identity` は供給を集合として照合するため、供給側（前週I＋当週P）に同じIDが2件以上あると、1件を出荷し、残りを在庫にも残さずに消す（FlowCheck報告書 §3.4）。B2でev_updateの構成を直しても、ほかのモデルやこれからのモデルで同じ形が起きうる。

- identity・legacyの両方で、供給側に同じIDが2件以上あった週を、ノード・週・ID・件数でForwardPlanResultに**記録だけ**する（計画は1ビットも変えない。LotIdentityFlowの`ot_in_transit_at_end`と同じ扱い）。
- Flow Checkの表1に、その件数の列を加え、1件以上ならNGとして理由を表示する。
- headlessの実行ログに警告を1行出す（件数と最初の例）。
- 受入：B2の修正前のev_updateで件数が出て、修正後に0になる。13 goldenのモデルでは0件（0でなければ報告する）。legacyのgolden 3件とriceのgoldenは変わらない。

`forward_planner.py`はAGENTSの保護対象だが、記録の追加だけなので、これまでの記録用フィールドの追加と同じ条件（legacyのバイト一致、テスト）で行う。

## 6. C：S2の要求・実出荷・評価の分離

### C1 利用箇所の棚卸し

以下を起点として利用先を追い、変更前後の「数量源／計算式／画面ラベル／適用方式／対象期間」を一覧化する。

- `wom/engine/sc_tree_to_df.py`：demand_fulfilled、fill_rate、stockout_qty、ship_qty。
- `wom/engine/money.py`：Revenue、COGSと利用画面。
- Management／KPI、`_draw_cost_from_plan_node`。
- ChartsのHarvest Input。

Harvest Input等が本来「需要」を表す場合はDemand Sを維持し、需要であると明示する。Sを読む箇所すべてを機械的に実出荷へ変えない。

### C2 計算契約

identityの実現供給に基づく評価では、各nodeの実出荷数量を、そのnodeに対応する既存の価格・原価ルールへ渡す。対象は市場leafだけではない。予定売上を残す場合は要求ベースと明示し、実出荷ベースと同じ名称で上書きしない。

- `ship_qty`：当該node・当該週の実出荷数量。遅配分の出荷も含む。
- 当週充足数量：当週要求IDと当週実出荷IDの対応数量。過去のCOを出荷しても当週要求の充足へ付け替えない。
- 当週充足率：当週充足数量／当週要求数量。要求0の扱いは既存契約を確認し、未定ならN/Aとして明示する。単純なship_qty/Sで100%超を作らない。
- 当週未充足、週末CO、期末注文残は別の量として扱う。欠品件数をCOの全期間和と混同しない。
- Revenue／COGS：実出荷数量と対応する既存単価・単位換算を使う。会計ルール・費用配賦・価格マスター自体を今回は改訂しない。

PPCによる画面値の上書きがあっても、変換前のmoney値と数量源を測定し、不一致を隠さない。PPCの中間nodeはleaf数量から導出される既知の別契約があるため、両者が必ず一致するとは要求しない。台帳ごとの根拠と未対応範囲を報告する。

legacyの計算は比較用として保存し、要求ベースの旧評価であることを識別可能にする。共有APIを変える場合は方式を明示的に渡し、legacy試走へidentityが混入しないことを確認する。

- **legacyの計画・評価の結果は変えない。** legacyのgolden 3件とriceのgoldenがバイト一致すること。
- 今のgoldenの項目（period／products／config／forward／backward／ppc／psi）には、money.pyやKPIの値は入っていない見込みである。**Cでidentityのgoldenが変わる場合は、変わった項目と理由を一覧にし、意図した変化かどうかを示す**（不意の差分を再生成で消さない）。

### C3 受入ケース

1. 要求2 ID・実出荷1 ID：出荷1、当週充足1、残1、そのnodeの売上は1 lot分。
2. 前週CO 1 IDだけを今週出荷し、今週要求1 IDは未充足：出荷1、当週充足0、週末CO1。総量だけで充足判定しない。
3. 実出荷0は売上数量0。実出荷未取得は不明として扱い、要求Sへfallbackしない。
   - 注意：今のPPCブリッジ（`wom/ppc/ppc_psi_bridge.py`）は、`node._actual_ship`が無いとき（古い呼び出しの経路）はSの件数を使う（LotIdentityFlow報告書 §8.1）。この経路が実際に使われている呼び出し元があるかを洗い出す。identityで`_actual_ship`が無い場合は、Sへ黙って戻さず、警告を出して「不明」と分かるようにする。legacyの結果は変えない。
4. 複写モデルで上流能力を減らし、実出荷変化が対象nodeの数量・money評価へ到達することを確認する。原本の能力は変更しない。
5. Demand Layer／Harvest Inputの需要表示は要求のまま。Planning前の画面も、未計算を実出荷0と誤表示しない。
6. 通貨・lot単位・cpu_size等の既存換算を維持し、同一基準の比較であることを確認する。

### C4 文書の更新

- `CLAUDE.md` の KPI の表（Fill Rate・Sell-through・販売チャネル Revenue）の定義を、C2で実装した定義に合わせて直す。その下にある「実装はまだ S（要求）ベースのまま（§6 S2、未対応）」という注記は、実装が済んだ範囲について削除し、残った未対応があればその範囲だけを書く。
- `docs/development/WOM_FlowCheck_WarmupTrial_Report.md` §6 S2 に、本依頼で対応したことを1行追記する。

## 7. 変更範囲・golden・保護

- 対象：warmup互換処理、iphoneの設定・生成行、ev_updateのKitting構成と必要マスター、S2の数量変換・評価・表示、関連テスト・報告書。
- allocのwarmup26、oilのwarmup26、smartxの能力、riceのlegacy指定を変えない。alloc9,293やsmartx遅配16,073を解消する作業は対象外。
- Inboundの一般的なPコピー廃止、匿名在庫binding、最適化solver、PPC全node台帳の再設計は対象外。
- AGENTSのprotected coreは原則変更不要の範囲を優先する。必要なら原因と最小差分を具体化し、既存承認条件に従う。非coreの対象作業まで止めない。
- goldenは挙動の証明後に、Windowsで意図的に変化したものだけ更新する。更新対象・差分・理由を一覧化し、不意の差分を再生成で消さない。
- 見込み：Aでiphoneのgoldenだけが変わる。ev-thailand-2026_updateはgoldenの対象外なので、Bの結果は報告書と専用の回帰テストで示す。B4とCでは、goldenは変わらない見込み（変わる場合は理由を示す）。
- legacy golden3件、rice golden、無関係なモデルの計画結果を保つ。Cの意図した表示／評価差が既存goldenへ入る場合は、影響項目を限定して説明する。
- SE2はwarmupなし・legacyの再現ケースとして168を維持する。通常のev-thailandはwarmup17付きの正常系として維持する。

## 8. 実施順序と最終検査

1. 基準と既知現象を確認し、前測定を保存する。
2. Aの書式対応・試行・設定・テストを完了する。
3. Bの構成修正・部材遅着試験・全件照合を完了する。
4. Cの棚卸し・計算／表示整合・境界試験を完了する。
5. 関連単体・CSV結合・E2E goldenの三層を検査し、全pytestを実行する。失敗をlegacy固定や期待値更新だけで隠さない。
6. Windows GUIでiphone読み込み、ev_updateのPSI／Flow Check、Management／KPI／node Cost/Revenue、需要表示を確認する。人手確認と自動確認を区別する。マウス操作が要る確認は、大杉さんが `python -m main` で行えるよう、モデル・タブ・ノード・週と、期待する表示を報告書に表で書く。
7. 最終報告・diff・証拠一式を渡して終了。commit・pushはしない。

途中で見つかった副作用は、範囲内なら原因とともに対応する。設計判断が必要なものは、実装案・差分・影響を具体化して未決事項に残し、検査済みと混ぜない。

## 9. 成果物

- `docs/development/WOM_iPhoneWarmup_EVUpdateKitting_S2_Report.md`
- 再実行可能な測定スクリプト、回帰テスト。
- `docs/development/iphone_evupdate_s2/`：小さな比較表・入力schema対応表・node経路対応表・S2利用箇所一覧・実行条件。
- 全件ID履歴・前後出力等の大きな生データは別ZIP。SHA-256一覧を付け、報告書から対応づける。

報告書では「観測結果／コードから分かった仕組み／業務上の解釈／未確認」を分ける。iphoneの残数は修正後の測定値を載せる。ev_updateは部材と完成品の保存を別々に示す。全テスト緑でも残る注文残・遅配・対象外を明示する。

受入サマリーにはA・B・Cの各合否、全テスト結果、更新golden、未確認GUI操作、次段階へ持ち越す事項をまとめる。これを提出した時点で今回の作業を終える。

---

## 改訂の要点（Claude君、2026-09-30）

1. 状態を「レビュー用」から「実装依頼」に改めた。
2. **B4を追加**：供給側の同じIDの重複を黙って捨てず、ForwardPlanResultへの記録・Flow Checkの列・ログの警告で見えるようにする（記録だけ。計画は変えない）。ev_updateの構成を直しても、ほかのモデルで同じ形が起きうるため。
3. C2に、legacyの結果を変えないこと（legacy golden 3件・riceのバイト一致）と、identityのgoldenが変わる場合の扱いを明記した。
4. C3の3に、今のPPCブリッジがSへ戻す経路を持っていることと、その扱いを書き加えた。
5. **C4を追加**：CLAUDE.mdのKPIの表と「未対応」の注記、FlowCheck報告書 §6 S2を、実装に合わせて更新する。
6. §7に、goldenが変わる見込みの範囲（Aのiphoneだけ）を書いた。
7. §8の6に、マウス操作が要るGUI確認を大杉さんに引き継ぐ形を書いた。
