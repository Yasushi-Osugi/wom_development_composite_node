# Request Letter：Stage 3a-2 — Kitting Gate（stock_yard の I 積集合による払出制御）

**起票日**：2026-09-04
**起票者**：大杉（設計：`docs/chat_memo/260904_0919Assemble_kitting_Stockyardのモデル化.docx`、`docs/chat_memo/260904_2317...`(該当があれば) の会話に基づく。Letter起草：Code君）
**種別**：**禁足コア変更**（`wom/engine/forward_planner.py`。場合により `wom/model/plan_node.py`）
**対象ブランチ**：`wom-v1r3m0`
**前提条件**：
- `requests/request_fix_mode4_supply_role_semantics.md`（Mode4 WHO/WHEN分離）— 実装・テスト完了・大杉承認済み・**未commit（golden保留中）**
- `requests/request_stage3a1_stockyard_passthrough.md`（stockyard node_type・素通り配線）— 実装・テスト完了・**未commit（golden保留中。ev-europe-2026／bom-test-2026とも本Letter完了後に一括で確定させる方針）**
- 上記2件は本Letterと**同じコミットにまとめるか、別々にコミットするかを⑦で相談する**（大杉さんの過去の指示：「今回のMode4変更と新規testはそのままworking treeに保持してください」）

**本Letterで、Stage 3a（組立工程のモデル化）の中核が完成する。** gate keeping が有効化され、golden が実際に変わる最初のLetterとなる。

---

## 0. 禁足ルールに基づく承認事項

- [x] Request Letter 起票（本書）
- [ ] **§4 の事前調査（実装アーキテクチャの選定）を実施し報告**（実装前に一度停止）
- [ ] Unit test で修正前（gate無効時と同じ挙動）を確認 → gate有効化で red→green の遷移を確認
- [ ] Lot_ID 総数の整合性（質量保存）を検証するテストを追加
- [ ] Unit / Integration / golden の3層テストを実施
- [ ] `ev-europe-2026`・`bom-test-2026` の Kitting／PSI を再診断し、P二重化が解消されたことを確認
- [ ] オーナー（大杉）による `git diff` レビュー
- [ ] 承認後にのみ golden 更新・commit

**上記が揃うまでcommitしないこと。**

---

## 1. 背景・トリガー

Stage 3a-1（素通り配線）実装後、GUIで`bom-test-2026`・`ev-europe-2026`を確認した大杉さんが、Vehicle_Assy／Factory_Import_HU の PSI で **P（Supply Receipt）が S（Sales/Fulfilled）の部材数倍になっている**ことを発見した。

```
bom-test-2026   Vehicle_Assy      P=10/週  S=5/週   （部材2種 → 2倍）
ev-europe-2026  Factory_Import_HU P_sum=23,835  実需要=7,945（部材3種 → 3倍）
```

原因は、Stage 3a-1が意図的に**素通り**のままにしているため（gate keeping未実装）、各Yardが**それぞれ独立に**同じLot_IDの全量を組立ノードのPへ`extend()`しているためである。

```
Tire_Yard.S    = [lot_A, lot_B, ...]
Battery_Yard.S = [lot_A, lot_B, ...]
                     ↓ 両方が無条件にextend
Vehicle_Assy.P = [lot_A, lot_A, lot_B, lot_B, ...]   ← 同じLot_IDが部材数分重複
```

大杉さんの提案：

> kitting completeした後に、各stock_yard nodeの"S"（複数Lot_ID）から、assemble nodeの"P"に、**kittingされた一つのLot_IDのみ**が入るというモデル表現とすること

これは `260904_0919` のdocx会話で既に確定していた設計と一致する。本Letterはそれを正式に実装する。

---

## 2. 確定した設計（docxより。`request_stage3a1_stockyard_passthrough.md` §2.4 の再掲・正式化）

### 2.1 判定：Lot_ID の積集合（∩）

```
組立可能な Lot = Battery_Yard.I[w] ∩ Motor_Yard.I[w] ∩ ECU_Yard.I[w]

揃わない Lot   = (∪ すべての Yard) − (∩ すべての Yard)
```

**数量判定（DBR的min）ではなく、Lot_ID 単位の集合演算を採用する。** 理由（docxより）：数量判定は「Lot_Aのバッテリーx2 + Lot_Bのモーターx2で2台組める」という誤りを許してしまう。Demand Anchored 設計の核心（同一 Lot_ID が全ツリーを貫通する）を守るため、A1・Mode4と同じ「Lot_ID を真実源とする」原則を維持する。

### 2.2 処理の駆動軸：組立ノード自身の需要

```
for w in weeks:
    for lot_id in Assembly_node.psi4demand[w]["S"]:   # 組立ノードが必要とする順
        if lot_id in (∩ すべての Yard の I[w]):
            # 払い出し：各Yardから lot_id を S として払出、組立ノードの P へ 1 回だけ
        else:
            # 揃わない：各Yardの I に残る。組立ノードは CO。kitting_list に missing 記録
```

**組立ノード自身の`psi4demand[w]["S"]`を軸にすることで、safety stock（需要に無い先行納入分）と待ちLot（需要にあるが未着分）が、特別なフラグ無しに自然に区別される：**

| | 需要（`psi4demand[w][S]`）に | 扱い |
|---|---|---|
| safety stock 分 | **無い** | 処理対象にならない → Yard の I に残る（＝運用上の余裕） |
| 待ちの Lot | **有る** | 処理対象だが Yard に揃っていない → 組立できず missing、CO |

### 2.3 gate（払出制御）

```
揃っている   → 各 Yard から lot_id を S（払出）、組立ノードの P へ 1 回だけ入れる
揃わない     → 払い出さない → 各 Yard の I に残る（PSI恒等式が自然に部材待ち在庫を作る）
```

### 2.4 質量保存・Lot_ID総数の整合性

止めた部材は**Yard の I に残る**ため、Lot_ID がモデル上どこにも無くなることはない。段階1の docx 会話で確認済みの通り、「質量保存が崩れる」と「ロット総数のカウントが合わなくなる」は同じ問題の表と裏であり、Yard導入によって両方解決される（§9で検証すること）。

### 2.5 kitting_list（診断）との関係

`plan_node.kitting[assembly_week][lot_id] = {child_node_name: arrival_week}` の記録ロジック自体は**変更しない**（Stage 3a-1で既にYard名ベースで正しく機能することを確認済み）。gate keeping有効化後も、kitting は「診断」の役割を維持し、`missing`が直接欠品部材を示す。

### 2.6 safety stock（ss_days）

leaf_in（例：Battery_Supply）に`ss_days`を設定すると、Battery_Yard に一週早く納入され、Yard の I に安全在庫として滞留する——既存機構（2026-09-01実測済み）がそのまま働く。**§2.2の「需要にあるかどうか」による自然な区別**により、safety stock分と待ちLotを混同しない。3a-1では配線のみ、3a-2で実際に動作検証する。

### 2.7 bom_qty との関係

1 set rule のまま。∩判定はLot_IDの有無のみを見るため、`bom_qty`は判定に一切影響しない。数量は既存通り`S_Qty = len(psi) × cpu_size × bom_qty`で別途計算される。

---

## 3. Required Semantics（そのまま維持すること）

- Lot_ID のスキーマ・集合演算に手を入れない（`_match_by_identity`は変更しない）
- Mode4のWHO/WHEN分離（`request_fix_mode4_supply_role_semantics.md`）は変更しない
- Backward Planning は変更しない（gate keeping は純粋にForward側の機構）
- `supply_role`（assembly/confluence）の判定ロジックは変更しない
- kitting_listの記録タイミング・格納先は変更しない
- 段階1の`KITTING_GATE_ENABLED`定数は、本Letterで初めて意味を持つ（有効化の方法は§4で検討）

---

## 4. 実装前の事前調査【必須】

**以下を調査・報告し、大杉さんの承認を得てから実装へ進むこと。**

### 4.1 gate keeping をどこに実装するか（最重要の設計判断）

現状の`forward_planner.py`は、InBound `walk_postorder()`の中で、各子ノード（Yard）が独立に`_propagate_to_parent()`を呼び、無条件に親のPへextendしている。gate keepingを実装するには、**親ノード（組立ノード）の全Yard子が処理し終わった後に、初めて親のPを決定できる**——現在の「子が処理され次第、即座に親へ伝播する」逐次処理とは構造が異なる。

考えられる実装方針（例。他の方針でもよい。実装時に判断し、選んだ理由を報告すること）：

- **方針A**：Yardの子については`_propagate_to_parent()`の呼び出しをスキップし、親ノード自身を処理する直前に、全Yard子の`psi4supply[w][I]`を集めてgate判定を行い、親の`psi4supply[w][P]`を直接構築してから、通常の`_process_node(親)`を実行する
- **方針B**：既存の（重複した）伝播はそのまま行い、親ノードの処理後に「Yard子を持つ親」だけを対象にした後処理パスで、Pを積集合ベースに作り直す
- その他の方針

**判断基準**：
1. `_actual_s`（実際に出荷されたLot_ID、他のノードのForward伝播が参照する）との整合性が保たれること
2. 週をまたぐ`prev_inv_lots`の継続性が壊れないこと
3. Yard自身の`psi4supply[w][I]`・`psi4supply[w][S]`・kitting記録が、gate有効化後も意味のある値であり続けること（Yardの I は「揃わず滞留した在庫」を正しく表現し続ける必要がある）

### 4.2 gate keeping の発火条件

`KITTING_GATE_ENABLED`定数（現在`False`固定）を、本Letterでどう扱うか。

- 案1：定数を`True`に切り替える。ただし**発火条件は「親が`stockyard`型の子を持つ場合のみ」**とし、それ以外のノードでは処理が完全に変わらないことを保証する。この場合、`stockyard`ノードが存在しない他11モデルは構造的に無傷（コードパス自体に入らない）となり、config切り替えは実質不要になる
- 案2：`planning_config.csv`にキーを追加する（段階1で先送りしていた論点）

**大杉さんのご意向を伺いたい。** 私（Code君）の見立ては案1（発火条件を「stockyard子の有無」に紐付ける方が、既存モデルへの影響をゼロに保証できて安全）だが、判断材料として提示する。

### 4.3 Lot_ID 総数の整合性チェック

`plan space`全体でLot_ID総数をカウントしている既存の検査箇所があるか（GUI・PPC・テストのいずれか）を確認する。あれば、gate keeping後も破綻しないことを確認する。

### 4.4 影響範囲モデルの確定

`stockyard`ノードを持つのは現時点で`ev-europe-2026`・`bom-test-2026`の2モデルのみ（Stage 3a-1で確認済み）。他モデルは無影響であることを、実装後に golden 全件で確認する。

### 4.5 PPC への影響

Yardの`S`が「gate通過時にのみ立つ」形に変わることで、PPCが参照する`_actual_s`／node週次サマリに影響が及ぶか確認する（Stage 3a-1では無影響だったが、gate有効化で状況が変わる可能性がある）。

---

## 5. テスト要件（3層）

### 5.1 Unit

- 3部材（Battery/Motor/ECU、各Yard経由）の合成ツリーで：
  - 3者のIに共通するLot（∩）だけが、組立ノードのPに**1回だけ**入ること
  - 揃わないLot（例：Battery/Motorは揃うがECUだけ来ていない）は、3者ともIに残ること
  - 組立ノードのCOに、揃わないLotが正しく計上されること
- kitting_listの`missing`が、gate有効化後も同じ意味（`required - arrived`）で機能すること
- safety stock（`ss_days`設定）が、需要に無いLotとしてYardのIに残り続け、gateの判定を乱さないこと
- `bom_qty`が判定に影響しないこと
- **Lot_ID総数の質量保存**：`Σ(全Yardの I) + Σ(組立ノードのP経由で払い出された分)` が、入力された需要Lot総数と一致すること
- gate無効時（`stockyard`子を持たないノード）は、Stage 3a-1までと完全に同じ挙動であること（regression）

### 5.2 Integration（CSV → build → backward → copy → Mode4 → forward、gate有効）

- `bom-test-2026`：Vehicle_Assy の P が S と一致する（重複が解消される）こと
- `ev-europe-2026`：Factory_Import_HU の P が実需要と一致すること。同ノードの I が現実的な値になること（現在の 734,873 のような非物理的な値でなくなること）
- 両モデルとも、PPC revenue/GM% が Stage 3a-1 までと比較して**どう変わるか、あるいは変わらないか**を報告する（欠品Lotが実際にCO化される以上、下流のRevenueが減る可能性がある——これは「正しくなった結果」であり、想定される変化である）

### 5.3 golden

- **stockyardを持たない他11ケースは無変化であること**
- `bom-test-2026`・`ev-europe-2026`は変化する。変化の内容を報告し、大杉さんの確認を得てから golden を更新する
- 併せて保留中の `request_fix_mode4_supply_role_semantics.md` の golden も、本Letター完了時点で一括して確定させる（Factory_Import_HUの最終形はgate keeping込みで初めて「正しい」状態になるため）

---

## 6. 手順

```
① §4 事前調査（特にgate keepingの実装アーキテクチャ）を実施し、報告する（実装前に一度停止）
② 大杉が調査結果を確認し、実装方針を確定
③ forward_planner.py への実装
④ §5.1 Unit テスト
⑤ §5.2 Integration（bom-test-2026, ev-europe-2026）
⑥ §5.3 golden（stockyard無しモデルは無変化、stockyard有りモデルは変化を報告）
⑦ 大杉の差分レビュー（Mode4修正・Stage 3a-1・Stage 3a-2、3件の扱い方＝一括commitか分割commitかもここで相談）
⑧ 承認後、golden更新・commit
```

**②の前に実装しないこと。⑦の前にcommitしないこと。**

---

## 7. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `tasklist | findstr python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること（warm-up追記は commit しない）
- **`.gitignore` 対象のフォルダに触れないこと**（`git ls-files` で対象を取得）
- コミットメッセージは、指定したもの以外の行（`Co-Authored-By`等）を**勝手に追加しないこと**
- **指示に矛盾を見つけた場合は、実装前に指摘すること**

---

## 8. 本 Request の範囲外

| 項目 | 理由 |
|---|---|
| Stage 3b（カンバン方式の疑似モデル化） | `kitting_list_assembly.md` §6で対象外と確定済み |
| Yardへの原価・PPCルールの本格付与 | 3a-1で「コスト0・素通り」として据え置いた論点。本Letterでも素通りのまま（Yard自体が新たにコストを持つ設計ではない） |
| Yard の GUI 可視化（Buffer Stock チャート等への追加） | 段階2（可視化）の範囲 |
| 多段の組立（子自身が組立ノードの場合） | 未検討のまま据え置き |
| Mode4 `mom_ref_node_id` の扱い | 別件 |

---

## 9. 参考

- `docs/chat_memo/260904_0919Assemble_kitting_Stockyardのモデル化.docx`（Stage 3a全体の設計根拠）
- `docs/design/kitting_list_assembly.md`（§3 Stock Yard、§4 段階3a、§5.5）
- `requests/request_kitting_stage1.md`（Kitting List段階1、`45d6eac`）
- `requests/request_stage3a1_stockyard_passthrough.md`（stockyard node_type・素通り配線。§2.4に本Letterの設計が先行記録されている）
- `requests/request_fix_mode4_supply_role_semantics.md`（Mode4 WHO/WHEN分離）

---

**End of Request Letter**
