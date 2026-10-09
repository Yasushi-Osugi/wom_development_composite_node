# 決定記録：Lot_ID 中心の Forward Planning — 基本ルールと例外（2026-09-29）

- 決定者：大杉（WOM Project Owner）
- 記録：Claude君
- 位置づけ：大杉さんとの検討で**合意した内容の記録**。詳細設計書ではない。実装は、本書を前提にした Request Letter で行う。
- ブランチ：`wom-v1r5m1_cap_trial`（記録時の先頭 `17915af`）
- 根拠となった測定：
  - `docs/development/WOM_Bottling_Capacity_Trial_Report.md`（Trial-01、GPT-6 Astra君）
  - `docs/development/WOM_Capacity_Trial02_Report.md`（Trial-02、同）
  - `docs/development/WOM_ExplicitClosure_v1r5m0_Report.md`（Code君）
  - `docs/development/WOM_PPC_Entry_Measurement_Report.md`（Astra君）
  - `docs/development/WOM_LOVEM_StageAB_EVThailand_Report.md`（Code君、段階 A）

---

## 1. 基本ルール（正典）

### 1.1 Lot_ID の同一性

**Lot_ID の同一性を維持することを、Forward Planning の基本ルールとする。要求 X は、同じ ID の lot X が出荷された週に満たされる。**

前提：Forward の前処理で、Demand Layer で配分・配置された各週 [W] の S の Lot_ID は、そのまま Supply Layer にコピーされている。Supply Layer の S は「市場要求の位置（Demand Position）」を表す。

Lot_ID が表すのは**需要の単位**である。部材ノード（例：Battery_CN）にある同じ ID は、その需要に対応する部材であり、完成品と同じ物理的な個体ではない。部材から完成品への変換は、Kitting Gate の成立記録で裏付ける。

### 1.2 基本の動き（大杉さんの記述を正典とする）

> とある Lot_ID の立場に、自分の身をおいて考えると、あるplan_nodeの、ある週 [W] に配置（Demand Allocate）された Lot_ID：X は、
>
> 1. Demand Side の [S] の中にいて、まずは Supply Side の [P] と [I] を見て、ID match する X があれば、Supply Side の [I] を、次 node の [W+LT_offset] 週の [P] に copy 移動する。
> 2. Demand Side の [S] の中にいて、まずは Supply Side の [P] と [I] を見て、ID match する X がなければ、Demand Side の [S] を、自 node の次週 [W+1] の [CO] に copy 移動する。そして、Supply Side の次週以降での [P] 着荷を待っている。
> 3. 次週 [W+1] 以降の状態で、Lot_ID：X は、Demand Side の [CO] の中にいて、前述の 1 と 2 の動きと同様の考え方で、Supply Side の [P] と [I] を動かす。

この動きは、pull ノードの照合処理（`forward_planner._match_by_identity`）がすでに実装しているものと一致する。

### 1.3 状態の呼び方

| 状態 | 意味 |
|---|---|
| 当週出荷 | 要求週に同じ ID の lot が出荷された |
| 遅配 | 要求が CO に回り、後の週に同じ ID の lot が届いて出荷された |
| 期末注文残 | 計画期間の終わりに、要求が CO に残っている。「未達」とは呼ばない（計画期間の後に出荷される遅配。人気車種の「1年待ち」のように、経営上は想定内の場合がある） |
| 早出し | 基本ルールの下では起きない。要求週より前に届いた lot は、その要求が来るまで I で待つ。要求週は**各ノード自身の S の週**で判定する（市場の要求週ではない。上流が LT の分だけ先に出荷するのは正常）。push_sub は要求なしで先へ送る方式で、対象外 |
| I と CO に同じ ID | 物 X は届いているが、休業などで出荷できない週には、物 X は I に、要求 X は CO に残る。違反ではない。出荷した週に両方から同時に消える |

### 1.4 帰結：売上の数量

金額編（PPC）の販売数量は、**実際に出荷された lot の数**とする。予定の S（Demand Position）の数ではない。これは「出荷した Lot_ID の数 × Lot 単価」という原則と、1.1 の帰結である。

## 2. 例外1・例外2の扱い

2026-09-28〜29 の測定で、基本ルールに反する実装が2か所見つかった。

| | 場所 | 今の動き | 起きていたこと |
|---|---|---|---|
| 例外1 | push のバッファノード（Bottling_Noda、Factory_Import_CN など、`plan_mode=push` の MOM） | 届いた順に出荷し（`available[:total_cnt]`）、CO を持たない | 別の ID が出荷される（Trial-01：Bottling で早出し 24,696 ID）。遅配を ID で追えない |
| 例外2 | Outbound のデカップリング点より下流のノード（`_push_pull_node` の `pull_mode`） | 供給 P ＝ 需要 P のコピー | 上流で出荷されていない lot が下流に現れる（soysauce 9,293 ID、Cookie 10,868 ID）。上流の不足が市場と金額に届かない |

### D1　例外1：バッファも基本ルールで出荷する

push のバッファノードも、要求（S・CO）と供給（P・I）を Lot_ID で照合して出荷し、照合できない要求は CO に回す。push に固有の扱いとして残すのは、入荷（P）を能力で封印しないこと、休業週は入荷を受け入れて処理を止めること（Explicit Closure の D4）だけである。

### D2　例外2：下流は S だけをコピーし、P は親の実出荷とする

Outbound のデカップリング点より下流のノードでは、Demand Layer から Supply Layer へのコピーは **S だけ**とし、P のコピーを廃止する。P は、親ノードの実出荷が LT 後に届いたものとする。

**理由**：D1 と D2 により、バッファから Outbound の末端 leaf までは、Lot_ID の連鎖が途切れない閉じた系になる。Mode 4 の先行生産は需要の Lot_ID を保ったまま時期だけを動かすので、バッファでは ID で照合でき、下流の各ノードの S にも Backward が同じ ID を置いている。上流の不足は、下流の CO と市場の期末注文残として現れ、金額にも届く。

### D3　2つのソルバー

- **既定（新）**：D1・D2 による、Lot_ID の同一性に基づく計画。
- **旧方式（残す）**：「バッファは必ず足りる」前提の計画（例外1・2のまま）。バッファの必要量を見積もる用途など、業務上の意味がある場合があるため、設定で切り替えられるようにして残す。

## 3. Composite Node モデルと基本ルール

| モデル | 判断 |
|---|---|
| 1 Outbound Buffering Stock | **検討中。** なお、「先行生産の lot が、要求なしでバッファまで無条件に先送りされる」という例外は、すでに `plan_mode=push_sub`（例：smartx の WaferFab_TW）として実装されている。バッファでは D1 により基本ルールで出荷する |
| 2 DBR | **WOM の例外ではない。** 週の中で、かんばん（pull）で作るか MRP（push）で作るかは、週次バケットの中に含まれる処理方式の違いである。WOM が扱うのは「前週末に部材がそろっているか」であり、部材在庫の持ち方は 3 の Kitting モデルで表す |
| 3 Assembly Kitting | **基本ルールと整合している。** 同じ Lot_ID の部材が全品目そろうまで組み立てない（実装済みの Kitting Gate）。変更不要 |
| 4 Inbound のボトルネック | **PSI Planning エンジンより上位で扱う。** エンジンが動く時点では、ボトルネックの能力を考慮した需要量と Demand Lots が設定済みであるようにする。生産配分・優先市場の最適化と同じ層の処理とし、Inbound のスループット最大化の線形計画として定式化する案がある。能力の比較は、**Inbound Tree 全体で最大の能力を持つノードの能力を 1 とし、他のノードの能力を 0〜1 に正規化して行う**（大杉さんの案）。このとき、値が最も小さいノードがボトルネックである。比べる前に、能力を製品換算の同じ単位にそろえる。正規化は比較のための尺度であり、これだけでは最適化の問題は決まらない。定式化の際は、制約を「ノード×週ごとの能力」と「製品ごとの資源使用量（BOM 比率）」で持つ。上位で能力を考慮しても、部材の到着・休業・組立の成立週を含む実現可能性は、Forward で引き続き検査する。**今回の Lot 移動の修正とは別の設計とする** |

## 4. 期首在庫

- 事実（2026-09-29 確認）：PSI Planning エンジンは `inventory_master.csv` を読んでいない。`on_hand_qty` を使うのは、数量ベースの旧 Simulation の経路（`wom/engine/inventory.py`）だけである。Forward の期首在庫（`opening_inv`）に lot を入れているのは、rice の収穫プラグイン（`harvest_batch_plugin`、合成した ID）だけである。
  - **（2026-10-09 追記）解消**：rice は Rice Seasonal（収穫週と精米週を選ぶ上位の層）で identity に移り、`harvest_batch_plugin` は削除した。期首在庫に lot を入れるものは無くなった（`docs/development/WOM_RiceLegacyRetire_Report.md`）。
- **決定**：期首在庫を PSI で表す場合は、先行生産分を需要 Lot から計画して流し、期首に Lot_ID 付きの在庫として置く。受け皿は既存の warmup（計画準備期間。`docs/design/planning_warmup_and_reporting_horizon.md`）とする。需要に紐づかない匿名の期首在庫 lot は作らない。

## 5. push の Mode 1〜3

- 事実（2026-09-29 確認）：全モデルの `push_config.csv` のうち設定のある9行（apparel-global 2、ev-europe、ev-thailand、ev-thailand_update、smartx、soysauce 4モデル）は、すべて Mode 4（`push_lead_time_weeks` のみ設定）である。
- **決定**：Mode 1〜3（固定量・補充・時期別の push。需要に紐づかない匿名の Lot_ID を作る）は**非推奨**とし、使わない。設定された場合は警告を出す。コードの削除は急がない。

## 6. 未決・申し送り

| 項目 | 内容 |
|---|---|
| Inbound のデカップリング（push 以外）での P のコピー | `forward_planner` Phase 1 の「is_decoupling または in_pull_mode のノードで `psi4supply[w][P] = psi4demand[w][P]`」は、例外2と同じ形をしている。今回の決定の対象外。該当するモデルと影響の有無を先に測る |
| Buffering Stock（モデル1）の詳細 | rice の収穫プラグインが作る合成 ID の期首在庫も、ここで扱う（収穫期に作って在庫で持つという点で、同じ構造）。**（2026-10-09 解消：rice は Rice Seasonal で、収穫在庫に需要の Lot_ID を付けて計画する。合成 ID は作らない。`docs/development/WOM_RiceLegacyRetire_Report.md`）** |
| Backward の前倒しの上限 | 休業分を約1年前まで前倒しする（SE-A）、前倒しできずに past_due になる（SE1）。モデル4（ボトルネックを上位で解く）によって起きにくくなる見込み。上限の要否は後で判断 |
| partial_capacity を cap_soft へ | Explicit Closure の D6。部分操業は cap_soft を動かすのが正 |
| 中間ノードの金額 | PPC の中間ノードの数量は、自ノードの実出荷ではなく leaf の販売数量から導出されている（PPC 入口の実測 P4）。LOVEM 段階 D で扱う |
| rice の合成 ID の重複 | PPC の入口で、4地域が同じ channel に写像され、合成 ID が各4回重複する（PPC 入口の実測 P1）。**（2026-10-09 解消：HarvestBatch の削除で合成 ID は無くなった）** |
| identity でのデカップリング点の意味 | identity では、Outbound のデカップリング点の位置を変えても計画が変わらない（LotIdentityFlow の中間報告）。今の実装では、配置の効果が例外2（P のコピー）だけに依存していた。補充の指示・在庫の目標・投入の時期など、デカップリング点が本来変えるべきものを、identity でどう表すかを設計する |
| legacy の Step 0a の CO の重複 | legacy では、cap_hard を超えた生産の lot を CO に入れるため、同じ ID の要求が二重になり、CO に残り続ける（smartphone、smartx、ev_update、rice）。legacy は変えないので、既知の欠陥として残す。**（2026-10-09 追記：rice は identity に移ったので、rice についてはこの欠陥の対象外になった）** |

## 7. 追加の決定（2026-09-29、LotIdentityFlow の中間報告を受けて）

| # | 決定 |
|---|---|
| D4 | identity では、cap_hard を超えて作れなかった生産の lot を CO に入れない。ID を保ったまま翌週の生産の先頭に回す（休業週の E2 と同じ考え方）。そのノードの要求週に間に合えば遅配ではない |
| D5 | rice は、収穫在庫に需要の Lot_ID を付ける設計（§6 Buffering Stock）が決まるまで、legacy で動かす。暫定措置であり、rice の整合性を確かめたものではない。方式は計画の結果と LOVEM の manifest に記録する。**（2026-10-09 に解消。rice は Rice Seasonal〔収穫週と精米週を選ぶ上位の層〕で identity に移った。`data/sample/` に legacy で動くモデルは無い。legacy の方式と `tests/golden/legacy/` は D3 のとおり残す。`docs/development/WOM_RiceLegacyRetire_Report.md`）** |
| D6 | decouple の配置最適化は、legacy で参考候補を選び、選んだ配置を identity で評価し直して本計画を行う。legacy の評価値を identity の成果や最適性の証明として扱わない |
| D7 | （2026-09-30）期首在庫は warmup（`planning_config.csv` の `warmup_lt`）で作る（§4）。`warmup_lt` は、業務で分かりやすい暦の区切りにそろえる：13 週＝3 か月（四半期）を基本に、**標準は 17 週（約 4 か月の先行生産）**、17 週で足りないモデルは **26 週（半年）**。ev-thailand-2026・Cookie-jp-2026 は 17（試行での最小値は 14・15。16〜28 でも結果は同じ）、soysauce-jpy-2027 は今の 26 のまま（`docs/development/WOM_FlowCheck_WarmupTrial_Report.md` §5） |
| D7a | （2026-09-30）D7 の段階は **17 週と 26 週の2つだけ**とし、26 週で足りないモデルも 26 週にとどめる。26 週でも残る期末注文残は、能力の押し戻しが半年より深いことを示す情報として残す（先行生産で隠さない）。適用：oil-global-2027 は 26（残り 29 件：開始端 25・能力 4。52 週なら 0。観測結果：29 件はすべて Gasoline_Local_RedSea（当週出荷 465）。モデルの設定：製油所の能力 5 lot／週に対して需要 8 lot／週。業務上の解釈：モデルが意図した供給不足が見えている（29 件すべてを恒常的な能力不足だけに帰属させる意味ではない）。件数では 0.015% だが、1 lot がタンカー 1 隻分のため**売上では約 786 億円・4.8%**）、soysauce-jpy-2027-alloc は 26（P_opt/800 の 9,293 件は期末注文残として残す）、smartphone-global-2026-2029 は `capacity_plan.csv` の書式の都合で warmup 未適用（別の依頼で扱う）。各モデルの値は `docs/development/WOM_Warmup17_IdentityGolden_Report.md` |

---

| 版 | 日付 | 内容 |
|---|---|---|
| 1.0 | 2026-09-29 | 初版 |
| 1.1 | 2026-09-29 | Astra君のレビューを反映：Lot_ID は需要の単位（§1.1）、早出しの判定週と I・CO の併存（§1.3）、モデル4のボトルネックの判定（最大能力を 1 とする正規化）、Forward の能力検査を残すこと（§3） |
| 1.2 | 2026-09-29 | §6 に 2 項目、§7（D4〜D6、大杉さん同意済み）を追加。Astra君のレビューを反映 |
| 1.3 | 2026-09-30 | §7 に D7（warmup_lt の標準値：17 週、足りなければ 26 週）を追加 |
| 1.4 | 2026-09-30 | §7 に D7a（warmup の段階は 17・26 の2つ。oil・alloc は 26）を追加 |
