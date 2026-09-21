# Kitting List と Stock Yard：InBound 組立工程のモデリング設計

**設計文書（2026-09-01、Rev 2）。実装なし。**

InBound Tree における組立工程（複数の異なる部材が揃って初めて完成品になる構造）を
どうモデル化するかを定める。

**Rev 2 での変更**：部材ストックヤードをノードとして導入する方針を追加。
段階3を 3a（Yard + kit complete）に絞り、カンバン方式は WOM の対象外と確定した。

---

## 0. 要約

```
問題    supply_role=assembly は名前に反して合流と同じ挙動であり、
        部材が欠品しても完成品が作られたことになる。実証済み

方針    Lot_ID とその集合演算には触らない
        「誰がいつ届けたか」を Kitting List で横に持つ
        止めた部材は Stock Yard ノードの I に滞留させる

段階1   記録するだけ      kitting を作り、揃／不揃を判定して記録
                          PSI も CO も変えない。golden 無変化
段階2   可視化            不足部材を GUI / auto-debug で示す
段階3a  Yard + gate       Stock Yard ノードを導入し、kit complete で払い出す
                          挙動が変わる。golden も変わる

対象外  カンバン方式      日・時・分の実行系。WOM の粒度の外（§6）
```

---

## 1. 問題：欠品が完全に隠蔽される（実証済み）

### 1.1 実測（2026-09-01、`tools/sweep_specs/bom_test_shortage.json`）

`data/sample/bom-test-2026` で `Battery_Supply` の供給能力を絞った。

| | base | battery_short（cap 2） | battery_zero（cap 1） |
|---|---|---|---|
| Battery_Supply P_sum | 100 | **40** | **20** |
| Battery_Supply CO_sum | 0 | **1,620** | **2,160** |
| Tire_Supply（無制約） | — | **無変化** | **無変化** |
| **Vehicle_Assy P_sum** | 200 | **140** | **120** |
| **Vehicle_Assy S_sum** | 100 | **100** | **100** |
| **Vehicle_Assy CO_sum** | **0** | **0** | **0** |
| 下流（SP / DC / Dealer） | — | **`series_md5` 完全一致** | **完全一致** |
| PPC Revenue | $3,200,000 | **$3,200,000** | **$3,200,000** |

**バッテリーが需要の1/5しか供給できていないのに、車両は週5台売れ続け、
売上も利益も1ドルも変わらない。**

`Battery_Supply` 自身は CO=2,160 を正しく記録している。**欠品は検知されている。**
しかしそれが1ビットも下流に伝わらない。

### 1.2 原因

```
① Demand Anchored 設計により、Lot_ID は leaf_out で一度だけ発番される
② _propagate_to_children の assembly 分岐は、全ロットを各子へフルコピーする
   → Tire も Battery も「完全に同一の」Lot_ID を持つ
③ _propagate_to_parent は各子が独立に parent.psi4supply[w][P] へ extend する
④ _match_by_identity は supply_set = set(supply_lots) で重複を1つに吸収する
   → Tire が単独で全ロットを届けていれば「揃っている」と判定される
```

**`set()` を通った瞬間に、「同一部材の重複」と「異なる2部材が揃ったもの」が
区別できなくなる。**

### 1.3 性質：未実装であり、かつ静かに誤る

| 側面 | 内容 |
|---|---|
| **未実装** | all-or-nothing の待ち合わせロジックが存在しない。意図的に作られなかった領域 |
| **静かに誤る** | `supply_role=assembly` という**名前**が「組立部材の依存関係を表現する機能」という期待を与えるが、実装は合流と同じ。欠品してもエラーにも警告にもならず、PPC の金額まで含めて**完全に正常に見える結果**を返す |

`supply_role` は 2026-08-30 に本プロジェクトで命名した。
「合流と組立を区別する」という判断は正しかったが、
**`assembly` 側に実体が無いまま名前だけが先に付いた**状態である。

### 1.4 影響範囲

| モデル | golden | ノード | 子 |
|---|---|---|---|
| `ev-europe-2026` | **対象** | Factory_Import_HU | Battery_HU / Motor_HU / ECU_HU |
| `ev-europe-2026` | **対象** | Factory_Local_DE | Battery_DE / Motor_DE / ECU_DE |
| `ev-thailand-2026_update` | 対象外 | Factory_Local_TH | Platform_Unit_Assy / Motor_Unit_Assy |
| `bom-test-2026` | **対象** | Vehicle_Assy | Tire_Supply / Battery_Supply |

**実運用の2ケースが同じ隠蔽を起こしうる。**
そして `bom-test-2026` は既に golden に入っており、**この挙動が「正解」として固定されている。**

---

## 2. 方針：Lot_ID に触らない

### 2.1 触ってはならない理由

`_match_by_identity` が `set()` で潰す問題を Lot_ID 側で解こうとすると、

- lot_id のスキーマに部材の枝番を足す
- identity matching の集合演算を全面的に見直す
- Demand Anchored の「1つの需要 = 1つの Lot_ID」という原則が崩れる

**複雑性が一気に上がり、泥沼になる。**

2026-08-30 の A1 修正（`39bcb44`）と Mode4 修正（`44e67bf`）で、
**Lot_ID の重複が何を引き起こすか**は既に痛感している。ここには触らない。

### 2.2 Kitting List：横に別構造を持つ

```
psi4supply[w][P]      今まで通り。Lot_ID の文字列リスト（変更しない）
kitting[assembly_week][lot_id] = {child_node_name: arrival_week}
```

判定は単純である。

```
required = supply_role != "confluence" の子ノードの集合
arrived  = set(kitting[w][lot_id].keys())

揃った    arrived ⊇ required   → 組立可能
揃わない  arrived ⊂ required   → 部材待ち
不足部材  required − arrived   → 何が足りないかが直接わかる
```

**「Battery が遅れたのか Tire が遅れたのか判別できない」という問題も同時に解ける。**

### 2.3 格納先：`PlanNode` の属性

**`ForwardPlanner` の内部辞書ではなく `PlanNode` に持たせる。**

`_actual_s` は `ForwardPlanner` の内部にあるためプランナーが消えると失われ、
**GUI から一切参照できない**（2026-09-01 確認）。

`plan_node.kitting` であれば、Network パネルが既に行っている
「`product_name` と `plan_node` で InBound tree を root から辿る」という
同じ経路で読める。**新しい配線が不要。**

---

## 3. 【Rev 2 で追加】Stock Yard：止めた部材の行き場

### 3.1 kitting だけでは質量保存が崩れる

gate keeping で止めた部材は、**どこにも行き場がない。**

```
Tire が届いた、Battery が届かない
  → lot_C は親の P に入れない（gate keeping）
  → では、届いた Tire はどこにある？
```

`kitting` は「届いたという記録」であって**在庫ではない。**
PSI の I バケットには現れない。したがって、

- 物理的に存在するタイヤが、モデル上どこにも無い
- 在庫評価にも CCC にも乗らない
- **plan space 全体の Lot_ID 総数の整合性が崩れる**

### 3.2 Stock Yard をノードとして持つ

**親ノードの足元に、部材ごとのストックヤードをノードとして置く。**

```
現在   Tire_Supply ────────┐
                            ├→ Vehicle_Assy
       Battery_Supply ─────┘

Rev 2  Tire_Supply ──→ Tire_Yard ────┐
                                       ├→ Vehicle_Assy
       Battery_Supply → Battery_Yard ─┘
                        ↑ ここに滞留が現れる
```

**既存の PSI 機構がそのまま使える。**

```
Tire_Yard
  P: Tire_Supply からの着荷
  S: 組立への払い出し（kit complete の週のみ）
  I: I(w-1) + P − S    ← 恒等式が自然に部材待ち在庫を作る
```

**新しい在庫機構を作る必要がない。**

### 3.3 「ノードとして持つ」を選ぶ理由

| 案 | 評価 |
|---|---|
| **中間ノード（Yard）を挟む** | **採用。** CSV でモデル定義できる。既存の PSI がそのまま働く。モデル定義者が明示的にストックヤードを置く |
| 親ノード内の新バケット（`P_pending` 等） | スキーマ変更が必要。暗黙の挙動が増える |

**「黙って解く黒箱にしない」という WOM の一貫した方針**に沿う。

### 3.4 運用上の余裕は `ss_days` で表現できる

「stock_yard には常に1週間分の在庫を確保する」という運用は、
**既存の機構でそのまま書ける。**

```
Tire_Supply に ss_days=7 を設定
  → Tire_Supply が1週早く納入する
  → Tire_Yard の I に1週分が滞留する
```

2026-09-01 に実測で確認済み（`docs/design/inbound_safety_stock.md`）。

- `ss_days` は**供給元の子ノード**に設定する
- 在庫は**供給先（Yard）の I バケット**に現れる
- `ss_wks = ceil(ss_days / 7)`。1週未満は表現できない

**エンジン変更は不要。CSV の一行で表現できる。**

### 3.5 kitting との整合

```
Tire_Supply → Tire_Yard → Vehicle_Assy
              ↑ ss_days で余裕     ↑ kit complete で払出
```

**Yard の S が、kitting の判定結果そのものである。**

```
kit complete   → Yard[w]["S"] に払い出す → Vehicle_Assy の P へ
kit incomplete → Yard[w]["S"] を立てない → Yard の I に残る
```

PSI の恒等式が、**自動的に部材待ち在庫を作る。**
そして Lot_ID 総数の整合性も保たれる。

**§3.1 で挙げた「質量保存が崩れる」問題と、
「ロット総数のカウントが合わなくなる」問題は、同じ問題の表と裏であり、
Stock Yard の導入によって同時に解ける。**

---

## 4. 三段階

### 段階1：記録するだけ

**既存の計画結果を一切変えない。**

- `_propagate_to_parent` で親の P へ extend するとき、
  **どの子がいつ届けたかを `kitting` に記録する**
- `required` / `arrived` / `missing` / `is_complete` を判定する
- **PSI（P / S / I / CO）は変更しない**。揃わない Lot_ID も従来通り P に入れる
- golden は無変化

**この段階だけで「静かに誤る」性質は消える。** 欠品が観測可能になるため。

切り替えフラグ（`KITTING_GATE_ENABLED = False`）をコード内の定数として置き、
段階3a で `True` にする。

### 段階2：可視化

- GUI（PSI List / Network パネル）で不足部材と滞留週数を示す
- auto-debug の判定ルールに追加する
  （`design_memo_confluence_assembly_autotuning.md` §C.3）

```
[組立] supply_role=assembly の子に CO があるのに、親ノードの CO がゼロである
       → 部材欠品が隠蔽されている。【異常】

[組立] kitting で arrived ⊂ required の lot が存在するのに、親の S が減っていない
       → 同上。【異常】
```

**段階1・2で既存の計画結果は変わらない。** golden は無変化。

### 段階3a：Stock Yard + gate keeping

**【前提条件】`push_pull.py` Mode4 の `supply_role` 無視を先に修正すること。**

Mode4（`push_lead_time_weeks`）は `decoupling_node.walk_preorder()` 配下の
全 leaf_in を無条件に「同種の並行供給者」として扱い、
親の lot リストを **重複なし・disjoint な 1/n スライス**に分割して各子へ書き込む。
`supply_role` 導入（`39bcb44`）以前に書かれたコードであり、**一切参照していない。**

段階1の実測（2026-09-03、`ev-europe-2026` Import 側）：

```
Factory_Import_HU（Mode4 decoupling node、3部材）
  kitting complete = 0 / 7,945 件
  全件が「3部材中ちょうど2部材が欠けている」
  Battery_HU 34件 / Motor_HU 33件 / ECU_HU 33件
  3者の積集合は常に空。和集合は親需要100件と一致
```

**BOM 部材が「車両1台分の全部材」ではなく「全体需要の 1/3 ずつ」しか
生産されていない。** 車両1台に必要な3部品のうち、実際に揃うのは常に高々1つ。

MOM ノード自身の P 合計は数量として正しく（3スライスが過不足なく分割されるため）、
`_match_by_identity` の集合演算が「どの子が実際に供給したか」を隠蔽していたため、
これまで観測できなかった。
**まさに kitting 段階1が可視化するために作られた種類の欠陥である。**

**この状態で gate keeping を有効にすると、`ev-europe-2026` Import 側は
全ロットが部材不足となり、生産が完全に停止する。**

別タスクとして登録済み（`task_fdcb95f8`）。
段階3a の Request Letter を起票する前に、こちらを解決すること。

---

**ここで初めて挙動が変わる。**

- 各サンプルモデルに Yard ノードを追加する（CSV のモデル定義）
- `KITTING_GATE_ENABLED = True` にする
- Yard の S を kit complete の週にのみ立てる
- 揃わない部材は Yard の I に滞留する
- 親の P に入らない Lot_ID は需要側に残り、CO になる
- 下流の S が減り、PPC の売上も減る

**golden が変わる。** 特に `ev-europe-2026`（実運用）と `bom-test-2026`。
変化の内容を精査してから golden を更新する。

**段階3a は独立した Request Letter として起票する。**

---

## 5. 設計上の論点

### 5.1 `arrival_week` の定義

子ノードの出荷週 + LT_offset。すなわち親への着荷週。

```
arrival_week = 子の psi4supply[ship_week]["S"] の週 + LT_offset
```

実装時に、既存コードのどの値を使うのが正確かを確認すること。

### 5.2 `required` の決め方

`supply_role != "confluence"` の子の集合。

**`bom_qty` との関係**：1 set rule により **1ロット = N 個のセット**なので、
「Tire が1ロット届いた」で足りる。個数ではなくロット単位で揃えばよい。

### 5.3 部分供給の扱い

**ロット単位で「揃った lot」と「揃わない lot」に分かれる。**
`kitting` が lot_id をキーにするため自然に扱える。

```
lot_A  arrived={Tire, Battery}  → 揃った
lot_B  arrived={Tire, Battery}  → 揃った
lot_C  arrived={Tire}           → Battery 待ち
lot_D  arrived={Tire}           → Battery 待ち
lot_E  arrived={Tire}           → Battery 待ち
```

### 5.4 `confluence` との関係

`supply_role=confluence` の子は **kitting の対象外**とする。
合流は「同種のものが複数経路から集まる」型であり、「揃う」概念が無い。

### 5.5 未決事項

**段階3a の前提条件（先に解決すること）**

| 項目 | 状態 |
|---|---|
| **`push_pull.py` Mode4 が `supply_role` を無視し、assembly の部材を 1/n 分割する** | **段階3a の前提条件。**`ev-europe-2026` Import 側で complete=0（7,945件全部が3部材中2部材欠け）。詳細は §4 の段階3a を参照。別タスク `task_fdcb95f8` |
| PUSH decoupling ノード自身の inline extend 経路（`forward_planner.py` 158-169行）が kitting 未対応 | 段階3a で対応が必要。該当箇所にコメントで明記済み（2026-09-03）。現行モデルに `is_decoupling + push` な assembly 兄弟が存在しないため段階1のスコープ外とした |

**未検証の観測（段階1で判明）**

| 項目 | 状態 |
|---|---|
| `ev-europe-2026` Local 側の 500件が `missing={ECU_DE}` のみ | **未検証。**`ECU_DE` だけ `lt_wks=2`（他2部材は1）による境界週の取りこぼしと推定。complete は 41,475/41,975（98.8%）。**段階3a で 1.2% が不当に止まる可能性がある** |
| `kitting_fallback_events` の発生源 | Demand Anchored 経路を通らずに親の P へ入る lot（`opening_inv` 由来等）。**実測では全ケース0件。**Mode4 は既存 lot_id を再利用するのみで新規発番しないため、発生源にならない |

**段階3a で決めること**

| 項目 | 状態 |
|---|---|
| Yard ノードを既存モデルにどう追加するか（ノード数が増える） | 未決 |
| Yard の `node_type` をどうするか（新しい型か、既存の型か） | 未決 |
| Yard に原価・PPC ルールをどう与えるか | 未決 |
| `bom-test-2026` / `ev-europe-2026` の golden をどう扱うか | 未決 |

**未検討**

| 項目 | 状態 |
|---|---|
| 多段の組立（子自身が組立ノードの場合） | 未検討 |

## 6. 【Rev 2 で追加】カンバン方式は WOM の対象外

### 6.1 カンバンが要求するもの

```
カンバン   stock_yard の部材にカンバンが付いている
           払い出しでカンバンが外れる
           外れたカンバンが、上流への納入指示として機能する
```

**払出という Forward の事象が、上流の計画を変える。**

### 6.2 WOM の設計原則に抵触する

CLAUDE.md に記録されている確立した設計原則：

> Backward の Demand Allocation が"親心"で全部やる。
> **Forward Planning は `I(W)=I(W-1)+P−S` を前へ回すだけで、決して時間を遡及しない。**

カンバンは**遡及そのもの**である。
そして Forward 側に遡及処理を入れて soysauce のお盆デモが破綻した経緯がある
（`_apply_operating_calendar_shift` で cap_hard を超えるスパイクが発生し、撤回）。

### 6.3 そもそも粒度が違う

**カンバンが働くのは、ある一週間の中での日・時・分の単位のオペレーションである。**

2026-09-01 に確認した通り、WOM は週次未満の事象を表現できない
（`docs/design/inbound_safety_stock.md` §3）。

### 6.4 判断：WOM の外に置く

**WOM Forward Planner で全体の整合性を確保した中で、
現場の日・時・分の単位のオペレーションとして、
カンバンで運用するか否かは、選択的な現場の問題として WOM の計画系の外に置く。**

これは実装対象外であり、「未実装」ではない。

### 6.5 同型の判断が既にある

`docs/design/global_oil_model_three_steps.md` で、
石油精製のコプロダクト・歩留まり・単位変換を **WOM の外**に置いた。

```
石油精製    WOM に機能を足すのではなく、モデルを三段階に分けて外に置いた
カンバン    WOM に遡及を入れるのではなく、実行系として外に置く
```

**「WOM に何を入れないか」という判断が、二度続けて設計を単純にしている。**

そして 2026-08-21 に確定した市場境界とも一致する。

| | 対象 | 粒度 | 意思決定の段階 |
|---|---|---|---|
| SCM 実行系 | 動いている業務の効率化 | 日・時・分 | 実行 |
| **WOM** | **まだ決まっていない事業構造の評価** | **週** | **投資・構造決定** |

---

## 7. 他の設計判断との関係

### 7.1 `design_memo_confluence_assembly_autotuning.md` §B

同文書 §B の三つの論点への回答：

| §B の論点 | 本書での回答 |
|---|---|
| 揃わなかった部材はどうなるか | **Stock Yard ノードの I に滞留する**（§3） |
| 組立後の Lot_ID をどう決めるか | **決めない。Lot_ID には触らない**（§2.1） |
| 部材構成比（BOM 数量）をどこに置くか | **解決済み。**`bom_qty` 列（`12cab50`） |

**「Lot_ID をどう決めるか」という最も難しい論点を、
触らないことで回避したのが本書の要点である。**

### 7.2 `inbound_safety_stock.md`

Yard の運用上の余裕は、同文書で確定した `ss_days` の機構で表現できる（§3.4）。
**エンジン変更不要。**

### 7.3 auto-debug

段階2の判定ルールは、`design_memo_confluence_assembly_autotuning.md` §C.3 の
判定ルール群に加わる。

---

## 8. ステータス

- **段階1**：**実装済み**（2026-09-03、`45d6eac`）
  - `plan_node.kitting[assembly_week][lot_id] = {child_node_name: arrival_week}`
  - `KITTING_GATE_ENABLED = False`。P への extend は無条件のまま
  - golden 13ケース無変化、249 passed、fallback 0件
  - `bom-test-2026` で欠品 60件・80件を可視化
  - **`ev-europe-2026` Import 側の重大な欠陥を発見**（§4 段階3a の前提条件）
- 段階2（可視化）：未起票
- 段階3a（Stock Yard + gate keeping）：未起票。**前提条件あり**（§4）
- **カンバン方式**：WOM の対象外と確定（§6）

**段階1は「記録するだけ」の機能だが、実運用の golden ケースで
これまで見えなかった欠陥を、実装したその日に暴いた。**
段階2・3a に進む前に、その欠陥（`task_fdcb95f8`）を解決する必要がある。
