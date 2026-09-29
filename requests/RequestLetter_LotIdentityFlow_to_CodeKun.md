# Request Letter：Forward を Lot_ID の同一性で一貫させる（例外1・例外2の修正）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`
- 着手の時期：**LOVEM 段階 B（viewer）を終えて、大杉さんが commit した後**。着手時の SHA を報告書に記録する。
- 種別：core 変更を含む実装（AGENTS.md の保護対象 `forward_planner.py`・`push_pull.py`）
- 決定の正本：`docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md`（以下「決定記録」）。本書は決定記録の D1〜D3 と §5 を実装するためのもの。食い違いがあれば決定記録を正とし、報告する。

---

## 1. 目的

Forward Planning を、**Lot_ID の同一性**（要求 X は同じ ID の lot X が出荷された週に満たされる）で一貫させる。基本の動きは決定記録 §1.2 にある大杉さんの記述を正典とする。

現在、これに反している箇所は2つある（決定記録 §2）。

- **例外1**：push のバッファノード（`plan_mode=push` の MOM。Bottling_Noda、Factory_Import_CN など）が、届いた順に出荷し（`available[:total_cnt]`）、CO を持たない。
- **例外2**：Outbound のデカップリング点より下流で、供給 P を需要 P のコピーで作っている（`_push_pull_node` の `pull_mode`）。上流で出荷されていない lot が下流に現れる（soysauce 9,293 ID、Cookie 10,868 ID。`docs/development/WOM_PPC_Entry_Measurement_Report.md` §4.3・§4.4）。

## 2. 変更内容

### C1　2つのソルバーの切り替え（決定記録 D3）

- 設定 `lot_flow_mode` を新設する。値は `"identity"`（既定、新方式）と `"legacy"`（旧方式。今の動きを1ビットも変えずに残す）。
- 設定の入口：`ForwardPlanner` の引数、`planning_config.csv` のキー、headless（`tools/run_headless_from_folder.py`）のオプション。GUI（`wom/gui/app.py`・cockpit）は `planning_config.csv` から読めればよく、切り替えの画面部品は作らない。
- golden の比較は、各 golden の config に記録された方式で行えるようにする（既存の golden は `legacy` として扱い、`identity` の golden は大杉さんの確認後に別途作る）。

### C2　例外1の修正：push のバッファも Lot_ID で照合する（決定記録 D1）

`lot_flow_mode="identity"` のとき、`_process_node` の push の分岐（`is_push_mode`）を次のように変える。

- 出荷：要求（CO＋当週 S）と供給（前週 I＋当週 P）を `_match_by_identity` で照合し、一致した ID だけを出荷する。一致しない供給は I、一致しない要求は翌週の CO に回す。つまり、通常のノードと同じ動きにする。
- push に固有の扱いとして残すもの：
  - Step 0a（cap_hard による P の封印）をしない（入荷は封印しない）
  - 休業週は、入荷を受け入れて処理（出荷）を止める（Explicit Closure の D4・E4）。identity では、休業週の入荷と前週の I はすべて I に残り、当週の要求（CO＋S）はすべて翌週の CO に回る。このため、**同じ ID が I（物）と CO（要求）に同時にある状態**が生じる。これは違反ではない（K2）。
  - 開いている週は、一致した ID をすべて出荷する（今の push と同じく、処理量の上限では切らない）。
  - Step 0b（cap_soft）は実出荷と比較する（超過を記録するだけ）
- `_push_shortfall[w]` は、その週に一致しなかった要求の件数とする（CO に回った件数）。
- S3 と「P vs Capacity Limits」の push の処理量の系列は、`len(S) − _push_shortfall` ではなく、**実出荷の件数（`len(_actual_s[node][w])`）** を直接使う。legacy では両者が一致するので、legacy の表示は変わらないはずである。確かめて報告する。
- CO を持たせる理由と懸念：旧コードのコメントに「CO cascade caused exponential snowball」とある。Lot_ID で照合する CO は ID ごとに1件で、届けば解消するので、雪だるまにはならない見込みである。§4 の K4 で確かめる。

### C3　例外2の修正：下流の P は親の実出荷とする（決定記録 D2）

`lot_flow_mode="identity"` のとき、Outbound（`_run_ot_push_pull` → `_push_pull_node`）を次のように変える。

- デカップリング点を含むすべてのノードで、子へは `_propagate_to_child`（親の実出荷を、LT 後の子の P へ、Lot_ID の経路で振り分ける）で供給する。
- `pull_mode` による `psi4supply[w][P] = psi4demand[w][P]` の上書きをしない。
- S は、前処理（`copy_demand_to_supply`）でコピーされた需要 S のまま使う（Demand Position）。
- `_pull_subtree` は、呼び出し元が無いように見える。使われていないことを確かめ、使われていなければ触らない（削除もしない）。
- 計画期間の外（`target_w >= n_weeks`）に届く lot は、今は黙って捨てられている。件数を「期末の輸送中」として result に記録する（legacy でも記録だけ行い、計画は変えない）。

### C4　PPC の販売数量を実出荷にする（決定記録 §1.4）

- `ppc_psi_bridge.psi_to_sales_records` が leaf_out から読む数量を、`psi4supply[w][S]` の件数から、**その週の実出荷（`_actual_s`）の件数**に変える。`_actual_s` を bridge へ渡す経路は、既存の呼び出し（`ppc_runner.py` l.55 付近）に合わせて最小限に作る。
- legacy では leaf の S と実出荷が全週・全 ID で一致している（PPC 入口の実測 P2）。したがって legacy の PPC は変わらないはずである。これを受入条件にする。
- 両方式で同じ実装を使い、方式ごとに分岐させない。
- **C4 の範囲は、市場 leaf の販売数量（PPC の入口）までとする。** 中間ノードの数量と金額（各ノードの実出荷に対応する売上・原価・利益）は、PPC がまだ leaf の販売数量から導出しており（PPC 入口の実測 P4）、今回は直さない（LOVEM 段階 D）。報告書でも、C4 で「全ノードの数量と金額の対応」が済んだとは書かない。
- identity での金額の差は、C4 そのものからではなく、C3 によって上流の不足が市場 leaf の実出荷まで届くことで生じる見込みである。

### C5　push の Mode 1〜3 を非推奨にする（決定記録 §5）

- `push_pull.py` の設定読み込みで、`push_qty_per_week`・`buffer_lots`・`pre_build_qty_per_week`・`pre_build_end_week` のいずれかが設定されていたら、警告を出す。文言：「push の Mode 1〜3 は非推奨です（需要に紐づかない Lot_ID を作るため）。Mode 4（push_lead_time_weeks）を使ってください」。
- 動作は変えない（止めない・削除しない）。今のサンプルでは警告は1件も出ないはずである。

### C6　観測だけ：Inbound の P のコピー（決定記録 §6、今回は直さない）

Phase 1（Inbound）の「is_decoupling または in_pull_mode のノードで `psi4supply[w][P] = psi4demand[w][P]`」は、例外2と同じ形をしているが、今回の対象外である。**コードは変えずに**、どのモデルのどのノードがこの経路を通るか、そこで「子の実出荷に無い ID」が P に現れる件数を、モデルごとに報告する。

## 3. 守ること

- `legacy` の結果を1ビットも変えない。
- core の変更は C1〜C5 に必要な範囲に限る。
- 旧コードの説明コメントは消さずに、`identity` との違いを追記する。
- 副作用が出ても実装は止めずに最後まで行い、報告書に書く（これまでと同じ）。
- 本書どおりに実装できないコードの事実を見つけた場合も、止めずに決定記録の意図に最も近い形で実装し、変えた点と理由を報告する。
- golden は再生成しない。commit・push はしない。
- 今回の受入は、**Outbound の親子間の移動**と push バッファの照合の整合性を確かめるものである。Inbound の P のコピー（C6）は残るので、「ネットワーク全体の物の整合性が証明された」とは書かない。

## 4. 受入条件

### 4.1 legacy が変わらないこと

- 13 golden モデルが、`legacy` で psi・forward・backward・ppc とも完全一致する。
- 全テストが緑（現在の件数＋新規）。

### 4.2 identity での検査（全13モデル＋soysauce-jpy-2027-alloc の P_opt/800＋ev-thailand-2026_update）

モデルごと・検査ごとに件数を表にする。0 でないものは、ノード・週・ID の例を示す。

| # | 検査 | 期待 |
|---|---|---|
| K1 | Outbound の親子間の移動（C3 の対象）で、子の P に届いた lot ごとに、(a) 同じ ID が親の実出荷にあり、(b) 到着週が「親の出荷週＋`_propagate_to_child` が使う LT」と一致し、(c) 親の1回の出荷が、複数の子や複数の週に重複して届いていない。あわせて、ノード・週ごとに「親の実出荷の件数＝子への到着の件数＋期末の輸送中（C3）」が成り立つ | 0 件（件数の保存は差 0） |
| K2 | 同じノード・同じ週に、同じ ID が I と CO の両方にある | 出荷が打ち切られた週（今の実装では push バッファの休業週）以外は 0 件。打ち切られた週の件数は、理由（休業など）を付けて別に示す。さらに、その ID が後で出荷された週に、I と CO の両方から同時に消えること（片方だけ残る件数 0） |
| K3 | 需要に紐づかない ID（どの需要の Lot_ID でもない ID）が PSI にある | rice の収穫プラグインの分を除いて 0 件。rice の分は件数を別に示す |
| K4 | 各ノード・各週の CO に同じ ID が2回以上ある、または CO の件数がその時点で未充足の固有の需要 ID 数を超える | 0 件 |
| K5 | 出荷した ID が、**そのノード自身の**当週の要求（そのノードの S＝Demand Position、または CO）に無い（早出し）。市場の要求週ではなく、各ノードの要求週で判定する（上流が LT の分だけ先に出荷するのは正常）。対象は push バッファと Outbound の全ノード。push_sub は要求なしで先へ送る方式なので対象外とし、件数だけ示す | 0 件 |
| K6 | 休業週（`processing_limit(w)=0`）の実出荷が、全ノード・全 ID で 0。C2 で push の分岐を書き換えるので、Explicit Closure の E4 を identity でも確かめる | 0 件 |

### 4.3 identity と legacy の差の報告

モデルごとに次を出す。

- 市場 leaf の実出荷の合計、CO の期末値（期末注文残）、遅配の件数（CO を経て出荷された ID 数）
- PPC の売上・原価・粗利（legacy との差）
- soysauce-jpy-2027-alloc（P_opt/800）では、Trial-02・PPC 入口の実測で見つかった 9,293 ID が、市場でどう扱われるようになったか（期末注文残・遅配など）
- Cookie では、Factory_GP_CN の不足（SE1 の 1,450 lot を含む）が市場に届いたか
- ev-thailand-2026 の SE2（2026-W38・W39、予定 S 150・150、実出荷 132・0）が、identity でどうなるか
- golden が変わるモデルの一覧と、変わったフィールド（再生成はしない）
- 実行時間の変化

### 4.4 LOVEM の観測

- `tools/lovem_observe.py` で、ev-thailand-2026 を `identity` で観測し、新しい run フォルダ（例 `run_B_identity`）を作る。Q12（観測 ON／OFF の一致）と区間の復元が通ること。
- 観測用のラッパーが差し込む関数が変わった場合は、観測側を直し、その内容を報告する。
- 段階 A の run（legacy）と比べて、Outbound の下流ノードに `arrival`（親の実出荷との対応）が現れることを確かめる。
- 大杉さんが段階 B の viewer で見た ID `EVmaker_Local:ONL:2026-W34:00032` について、変更前後を比べる。変更前は Sales_TH_ONL の入庫が `P_unk`（出所の記録なし）である。変更後は、DC_EV_Local の実出荷と**同じ ID が、1件だけ、LT どおりの週に一度だけ**届き、関係（REL）でつながることを示す。viewer のスクリーンショット（変更前・変更後）を報告書に入れる。

## 5. 成果物

1. コードの変更（C1〜C5）と、C6 の観測結果
2. テスト：2つの方式の切り替え、K1〜K6 を小さな合成ツリーで確かめるユニットテスト、legacy の不変
3. 報告書 `docs/development/WOM_LotIdentityFlow_Report.md`
   - §4 の受入結果と差の表、C6 の観測、副作用（どこで／何が／なぜ（推定）／実機での見方／期待との差）、本書と変えた点
   - 大杉さんが `python -m main` で確かめる画面（モデル・ノード・週）の案内
4. golden が変わるモデルの一覧（再生成しない）

## 6. 対象外

- Inbound の P のコピーの修正（C6 は観測だけ）
- Buffering Stock の詳細（決定記録 §3 モデル1）、rice の合成 ID の扱い
- ボトルネックを上位で解く最適化（決定記録 §3 モデル4）
- 中間ノードの PPC の数量の起点（LOVEM 段階 D）
- partial_capacity を cap_soft へ移すこと
- Backward の前倒しの上限
