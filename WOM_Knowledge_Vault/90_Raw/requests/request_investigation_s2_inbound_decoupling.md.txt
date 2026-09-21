# 調査依頼：InBound ノードに `buffering_stock_flag=1` を立てると CO が単調増加する（S2）

**依頼日**：2026-08-27
**依頼者**：大杉
**種別**：**調査のみ。コード変更は一切しないこと。**
**対象ブランチ**：`wom-v1r3m0`
**先行調査**：`requests/request_investigation_s1_push_pull_default.md`（PUSH/PULL 既定判定、報告受領済み）

---

## 0. この依頼で守ってほしいこと

- **コードを読んで事実を報告するだけ。修正・リファクタ・テスト追加は一切しない。**
- 保護対象コア6ファイル（`backward_planner.py` / `forward_planner.py` / `plan_copy.py` / `plan_node.py` / `sc_tree.py` / `push_pull.py`）は**読むのみ**。
- **推測と事実を明確に分けること。** 「〜と思われる」と「コードにこう書いてある（ファイル名:行番号）」を混ぜない。
- 分からなかったことは「分からなかった」と書く。**埋めないこと。**
- 該当箇所には必ず**ファイル名と行番号**を添える。
- 再現実行はしてよいが、**その際に変更した CSV は必ず元に戻すこと**（`git checkout` で確認）。

---

## 1. 背景と設計意図

### 1.1 設計上の考え方（大杉、2026-08-27）

InBound tree（`leaf_in → MOM → supply_point`）における decoupling point は、
**MOM ノード（最終完成組立工場）に置くのが自然**である。

理由：インバウンド・サプライチェーン全体の能力設計が適切に行われていれば、
最終出荷工程の能力にインバウンド供給能力が律速されているはずであり、
生産設備の能力設計・配置の時点でそう設計されていると考えるのが妥当。
もしボトルネックが MOM 以外のノード X にあるなら、decoupling point として X を指定すればよい。

**期待される挙動**：MOM の足元に「部材の在庫」が滞留する。
Tier-2/3（熱処理・長時間切削など）は工程特性から MOM と同期生産できず、
先行生産による在庫滞留が必然的に発生する。それを可視化したい。

なお、完成品自体は MOM から即座に出荷されるため**工場出荷在庫は発生せず**、
輸送時間を経て DC 在庫（DAD）に流れる。すなわち
「ボトルネック吸収用の MOM 足元の部材在庫」と
「需要変動吸収用の DAD の完成品在庫」の**両方にバッファが立つのが自然な姿**である。

### 1.2 S1 調査で判明していたこと

前回調査（S1）の Q5 で、以下が報告されている。

- InBound 側で S=P・I=0 になるのは、`is_decoupling` が一つも立たないため
  Forward Phase1 の Demand-S copy 分岐（`forward_planner.py:150`）に到達せず、
  全ノードが `_propagate_to_parent`（物理伝播経路）を通るから
- 「`buffering_stock_flag=1` を InBound ノードに立てたら在庫が立つのか」は
  **未実行・未検証**として残されていた

---

## 2. 実測結果（2026-08-27、大杉が GUI で実施）

### 2.1 再現手順（CSV 1文字）

`data/sample/apparel-us-2026/sc_tree_master.csv` の以下1行のみ変更：

```
変更前: Factory_Import_CN,,Apparel_Outsourced_S1,mom,inbound,8,1,CN,0,0,契約工場 (Pre-Spring / 初春物)
変更後: Factory_Import_CN,,Apparel_Outsourced_S1,mom,inbound,8,1,CN,0,1,契約工場 (Pre-Spring / 初春物)
                                                                    ↑ buffering_stock_flag: 0 → 1
```

- 対象は **`Apparel_Outsourced_S1` の1 SKU のみ**
- この MOM の leaf_in は **`Fabric_CN` の1つだけ**（multi-leaf_in ではない）
- `push_config.csv` は該当行なし（`plan_mode` は既定の `"pull"` のまま）
- Planning Config: Start Week=2025-W02 / #Weeks=126

### 2.2 観測された症状

| 項目 | BEFORE (flag=0) | AFTER (flag=1) |
|---|---|---|
| MOM (`Factory_Import_CN`) の I | 0（全週） | **0（変わらず）** |
| MOM の CO | 0 | **大量発生。単調増加し最大 25,000 付近まで積み上がり解消しない** |
| DAD (`DC_Import_Buffer`) の I | 正常な山（需要期に立ち上がり収束） | 山は残る |
| DAD の CO | 0 | **大量発生（MOM と同規模、25,000 付近）** |
| PPC GM (SKU: All) | 41.6%（S1 単体） | 41.5%（All）。**trust_events 0 → 156（Tariff Shock > 20%）** |
| PPC Lots | — | 312 |

### 2.3 warm-up 不足ではないことの確認

Start Week を `2025-W02` → `2024-W02`（52週さらに遡る）に変更して再実行したが、
**同じ CO パターンが横にシフトしただけ**で、症状は消えなかった。
CO の発生位置は需要位置に固定されている。**計画期間の不足が原因ではない。**

### 2.4 期待と実際の乖離

- **期待**：MOM の I（部材在庫）が立つ
- **実際**：I は立たず、代わりに CO が単調増加する。さらに下流（DAD）にも CO が伝播する

---

## 3. 調査してほしいこと

### Q1. Phase1 の Demand-S copy が InBound ノードで発火したとき何が起きるか

`forward_planner.py:150` の分岐
（`node.is_decoupling and node.plan_mode != "push"` → Demand-S copy）が
**InBound ノード（node_type=mom）で発火した場合**の具体的な処理を追ってほしい。

1. `P` はどの週の、何で上書きされるか（`psi4demand[w][P]` か、別の値か）
2. その際、Lot_ID は**既存のものが再利用されるか、新規採番されるか**
3. `S` はどうなるか。`copy_demand_to_supply` で複製された需要計画値のままか
4. この分岐が発火したノードは、`_propagate_to_parent` /
   `_propagate_to_child` を**通るのか通らないのか**
5. **この分岐は OutBound ノード（dad）を想定して書かれたものか、
   InBound ノードでも動作することを想定して書かれたものか。**
   コード・コメント・変数名から読み取れる範囲で判断し、根拠とともに述べること

### Q2. なぜ unmatched_demand（CO）が生じるのか

`_process_node` の identity matching
（`_match_by_identity(demand_lots=CO+S, available=I_prev+P)`）において、

1. Demand-S copy 後の `P` と、`S`（需要計画値）の **Lot_ID は一致するか**
2. 一致しないなら、**なぜ一致しないのか**（週のずれか、新規採番か、集合の違いか）
3. unmatched_demand が CO[w+1] へ carry-back され、
   **単調増加して解消しない**メカニズムを説明すること
4. I（unmatched_supply）が 0 のままなのはなぜか。
   「需要が余る（CO）のに供給も余らない（I=0）」という状態が
   どういう計算で成立するのか

### Q3. 【最重要】このコードパスは golden で検証されているか

1. **golden 12ケースおよび `data/sample/` 配下の全モデルについて、
   `sc_tree_master.csv` の InBound 側ノード（side=inbound、
   node_type が leaf_in / mom / supply_point）に
   `buffering_stock_flag=1` が設定されているものがあるか。**
   全件を機械的に調べ、該当があればケース名とノード名を列挙すること
2. 同様に、`push_config.csv` の `node_id` が InBound ノードを指しているケースはあるか
   （`PushProductionPlanner.setup()` が `is_decoupling=True` を強制上書きするため）
3. **もし該当が1件も無ければ、`forward_planner.py:150` の
   InBound 側での動作は一度も実行されたことがない**ことになる。
   その判断が正しいか、他に到達経路がないかを確認すること
4. `tests/` 配下に、InBound ノードの `is_decoupling=True` を扱う
   Unit / Integration テストは存在するか

### Q4. A1（multi-leaf_in × 需要段差の擬似 CO）との関係

CLAUDE.md 末尾に記録されている既知バグ A1
（Multi-leaf_in BOM × MOM 週次 demand.S の段差 → 擬似 CO が固定発生）と、
今回の症状の関係を確認してほしい。

1. 両者は**同じコードパス**を通っているか、別経路か
2. A1 の原因仮説は「`_propagate_to_parent` の重複 extend ＋
   Step 0a（CapHard シーリング）」だったが、
   今回は **single leaf_in** かつ **`is_decoupling=True`** という異なる条件である。
   共通する部分はどこか
3. **今回の症状の方が再現条件が単純（CSV 1文字、single leaf_in）である。**
   A1 の原因究明に、今回のケースを最小再現例として使えるか

### Q5. 設計意図とのギャップ

1. §1.1 の設計意図（MOM 足元に部材在庫を滞留させる）を実現するには、
   現行の実装のどこが不足しているか
2. `is_decoupling` は本来 OutBound 専用の概念として実装されているのか、
   それとも InBound / OutBound 共用として設計されているのか。
   コードから読み取れる範囲で述べること
3. `sc_tree_master.csv` の `buffering_stock_flag` 列は、
   **InBound ノードに設定してよい列なのか。** ドキュメント・コメント・
   スキーマ定義から読み取れる制約があれば報告すること

---

## 4. 参考資料（リポジトリ内）

- `CLAUDE.md` 冒頭「禁足ルール（Planning Engine 保護対象コア）」
- `CLAUDE.md` 末尾「ForwardPlanner: 複数Tier-1部材（Multi-leaf_in BOM）× holiday_calendar 閉鎖の
  組み合わせで擬似COが発生（既知バグ、未修正、2026-08-20）」および 2026-08-21 追記
- `CLAUDE.md`「Backward の Demand Allocation が"親心"で全部やる。
  Forward Planning は `I(W)=I(W-1)+P−S` を前へ回すだけで、決して時間を遡及しない」
- `docs/design/three_layer_production_allocation.md` §5（`lt_wks` はエッジ属性、
  `parent_node` が空の MOM の `lt_wks` は無視される）
- `requests/request_investigation_s1_push_pull_default.md` および その調査報告

---

## 5. 報告してほしい形式

```
## Q1. Demand-S copy が InBound で発火したときの処理
（事実）ファイル名:行番号 とともに記述
（不明）分からなかった点

## Q2. CO が生じるメカニズム
...

## Q3. golden での検証状況
（機械的に全ケースを調べた結果を表で）

## Q4. A1 との関係

## Q5. 設計意図とのギャップ

## 所見（推測として明示）
事実と分けて記述すること

## 追加で気づいた点
依頼範囲外だが報告すべきと判断したもの
```

---

## 6. この調査の後の流れ（Code 君は関与不要、参考まで）

1. 報告をもとに、大杉が**「InBound の decoupling は未実装なのか、実装されているが不具合なのか」**を判定する
2. 修正・実装が必要と判断した場合は、別途 Request Letter を起票
   （禁足コア変更 → 3層テスト緑 ＋ オーナー差分レビューが条件）
3. 本調査の段階では**一切変更しない**

---

## 7. 補足：現在の CSV の状態

再現実験に使った `buffering_stock_flag=1` は**既に 0 に戻してある**（大杉、2026-08-27）。
`data/sample/apparel-us-2026/` はリポジトリと同一の状態。
調査のために再現が必要な場合は、上記 §2.1 の1文字変更で再現できる。
**実施した場合は必ず `git checkout` で元に戻すこと。**
