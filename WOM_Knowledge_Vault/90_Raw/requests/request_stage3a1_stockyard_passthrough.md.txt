# Request Letter：Stage 3a-1 — `stockyard` node_type 導入（素通り、挙動不変）

**起票日**：2026-09-04
**起票者**：大杉（設計：`docs/chat_memo/260904_0919Assemble_kitting_Stockyardのモデル化.docx` の会話に基づく。Letter起草：Code君）
**種別**：**禁足コア変更**（`wom/model/plan_node.py`, `wom/engine/sc_tree_builder.py`。場合により `wom/engine/backward_planner.py` / `wom/engine/forward_planner.py`）
**対象ブランチ**：`wom-v1r3m0`
**前提条件**：`request_fix_mode4_supply_role_semantics.md`（Mode4 WHO/WHEN分離）— **実装・テスト完了、大杉承認済み。golden未更新・未commitのままworking treeに保持**（2026-09-04、理由：`ev-europe-2026`のFactory_Import_HU P/I膨張はStage 3a完了までの過渡的な非物理状態であり、golden化しない）
**関連設計文書**：`docs/design/kitting_list_assembly.md`（§3 Stock Yard、§4 段階3a、§5.5）
**関連 Request Letter**：`requests/request_kitting_stage1.md`（Kitting List段階1、実装済み・commit済み `45d6eac`）

**本Letterは Stage 3a を 3a-1／3a-2 に分割したうちの 3a-1（Yardノードの型導入と配線、素通り）のみを扱う。gate keeping（3a-2）は別Letterとする。**

---

## 0. 禁足ルールに基づく承認事項

- [x] Request Letter 起票（本書）
- [ ] **§4 の事前調査（impact scan）を実施し報告**（実装前に一度停止）
- [ ] 大杉が調査結果を確認し、実装方針を確定
- [ ] Unit / Integration / golden の3層テストを実施
- [ ] **golden 判定は「現在の committed golden」ではなく「Mode4修正後・Yard挿入前のフレッシュな baseline」と比較する**（§5.3参照。理由：`ev-europe-2026` は Mode4修正により既にcommitted goldenと乖離した状態でworking treeに存在するため）
- [ ] オーナー（大杉）による `git diff` レビュー
- [ ] 承認後にのみ commit（golden更新は不要——本Letterでは挙動不変のため）

**上記が揃うまでcommitしないこと。**

**この Letter は「設計担当」を欠いた状態（Code君が起草・実装の両方を担う）で書かれている。** 他のLetterで機能してきた「設計者と実装者の独立したレビュー」が働かないため、本Letterでは通常より多くの箇所を「§4 事前調査で確認してから進める」形にしている。**§4 の報告は、実装前に必ず大杉さんの確認を得ること。**

---

## 1. 背景・本 Request の要約

`docs/chat_memo/260904_0919Assemble_kitting_Stockyardのモデル化.docx` の会話で、以下が確定した。

1. **Yard 無しでは assembly を正しくモデル化できない**。揃わない部材の行き場が無いと、`set()` で潰れて欠品が隠蔽される（Kitting List段階1で実証済みの問題そのもの）。
2. **Yard ノードの配置（モデル定義）が先、kitting event control（エンジン）が後**という順序で、循環を断ち切る。
3. Stage 3a を分割する。

```
Stage 3a-1（本Letter）  stockyard node_type の新設、モデル定義への挿入
                        素通りノードとして配線（lt=0、gate無効）
                        挙動不変・golden不変

Stage 3a-2（別Letter）  gate keeping の有効化
                        Yardの I を kitting判定に接続
                        挙動変化・golden変化
```

3a-1 が完了して初めて、3a-2 の土台（Yardという「部材の行き場」）が揃う。

---

## 2. 確定した設計（docx より、3a-2 の仕様も含めて記録——3a-1 の配線範囲を正確にするため）

### 2.1 木構造への挿入位置

```
現在   Battery_HU (leaf_in) ──────────────→ Factory_Import_HU (mom)

3a-1   Battery_HU (leaf_in) → Battery_Yard (stockyard) → Factory_Import_HU (mom)
```

Yard は **leaf_in の親、mom の子** として挿入される。既存の leaf_in ノード自体（node_type, supply_role, lt_wks, ss_days）は変更しない。Yard 自身が新しい中間ノードとして木に1段追加される。

### 2.2 node_type

**新設**：`stockyard`（大杉さんの確定指示）。既存の `mom`（中間ノードとしての流用）ではなく、新しい型として導入する。

### 2.3 3a-1 の範囲：素通り

3a-1 では Yard は以下の意味で「素通り」とする。

- `lt_wks=0`（デフォルト、CSVで明示）
- gate keeping なし。子（leaf_in）から届いた lot はそのまま親（mom）へ伝播する
- Yard 自身の `psi4supply[w][I]` は 0 のまま（3a-2 で初めて滞留が発生する）
- **挙動不変・golden不変**を確認するのが 3a-1 のゴール

### 2.4 3a-2 で確定した判定方式（3a-1の配線範囲を決めるため、ここに記録）

3a-1 自体はこれを実装しないが、**この判定方式が後で正しく動く配線**を作る必要があるため記録する。

```
判定   各 Yard の psi4supply[w][I] の Lot_ID list の積集合（∩）
       組立可能 = 全 Yard の I に共通して存在する Lot_ID
       gate: ∩ に入る Lot だけを組立ノードの P へ払い出す

診断   kitting_list（既存、Lot単位）
       missing = required − arrived

滞留   ∩ に入らない部材は各 Yard の I に残る（PSI恒等式、既存機構）

安全在庫  子（leaf_in）に ss_days を設定 → Yard の I に自然に滞留（9/1実測済み・既存機構）
          safety stock 分と「待ちlot」の区別は不要——
          組立ノード自身の psi4demand[w]["S"] に無い lot は
          そもそも処理対象にならない（＝自然に「余裕」）
          組立ノード自身の psi4demand[w]["S"] に有る lot だけが
          「揃っているか」の判定対象になる

処理イメージ（3a-2、参考）
    for w in weeks:
        for lot_id in Assembly_node.psi4demand[w]["S"]:
            if lot_id in (∩ すべての Yard の I[w]):
                # 払い出し：各Yardからlot_idをS、組立ノードのPへ
            else:
                # Yardに残る。組立ノードはCO。kitting_listにmissing記録
```

**数量判定（DBR的、min(Yard.I数)）ではなく Lot_ID 判定（∩）を採用**——数量判定は「Lot_Aのバッテリー + Lot_Bのモーターで1台組む」ことを許してしまい、Demand Anchored原則（同一Lot_IDが全ツリーを貫通する）を破る。A1・Mode4と同じ「Lot_IDを真実源とする」原則を維持する。

### 2.5 kitting 判定の主体

判定は **Factory_Import_HU（組立=mom側）が持つ**。子であるYardのI[w]を参照する（「子が届いたか」ではなく「Yardに在庫があるか」）。既存の `plan_node.kitting[assembly_week][lot_id]` の格納先（組立親ノード）は変更しない。

### 2.6 bom_qty との関係

1 set rule のまま。Yard の I に lot_A が「4本分」あっても、Lot_ID としては1回のみ記録される（∩判定はLot_IDの有無のみを見る。数量は既存通り `S_Qty = len(psi) × cpu_size × bom_qty` で別途計算）。**3a-1では変更なし。**

---

## 3. 3a-1 の実装スコープ

### 3.1 対象ファイル（想定。§4事前調査で確定させること）

- `wom/model/plan_node.py`：`NODE_TYPE_STOCKYARD = "stockyard"` 定数を追加
- `wom/engine/sc_tree_builder.py`：**恐らく変更不要**（§4.2参照——node_typeの文字列を検証せずそのまま格納する実装のため）。ただし要確認。
- `wom/engine/backward_planner.py` / `wom/engine/forward_planner.py`：**恐らく変更不要**（Yardは通常の中間ノードとして`lt_wks=0`・単一子・`supply_role`継承で振る舞うはず）。ただし§4事前調査で実際に確認すること。
- サンプルデータ：`data/sample/ev-europe-2026/sc_tree_master.csv`（Local側 Battery_DE/Motor_DE/ECU_DE、Import側 Battery_HU/Motor_HU/ECU_HU の計6箇所にYardを挿入）、`data/sample/bom-test-2026/sc_tree_master.csv`（Tire_Supply/Battery_Supplyの2箇所）
- GUI：`wom/gui/app.py` の World Map ノードスタイル・PSIチャート凡例（stockyard用の表示。**未対応でも3a-1の合否には影響しない**——動作不変の確認が主目的。表示面は「わかれば良い」程度でよい）
- PPC：`wom/ppc/ppc_runner.py`・`ppc_forward.py` のコスト連鎖（leaf_in⇄momの`.parent`直結を前提にした箇所が無いか要確認。§4事前調査）

### 3.2 明示的に変更しないこと

- `supply_role`（`assembly`/`confluence`）の判定ロジック（`_propagate_to_children`）
- `_match_by_identity`
- Mode4のWHO/WHEN分離ロジック（今回のLetterで確定済み。ただしYardを挟んだ木で正しく動くかは§4で確認する——2.1の構造変更が`leaf_membership`の収集経路に影響しないか）
- Lot_IDのスキーマ・集合演算
- Kitting List段階1の記録ロジック（`_propagate_to_parent`）——Yardが新たに「子」の位置に入るため、kittingの記録先・`required`の集合がどう変わるかは§4で確認すること（Yard自身がkitting対象になってしまわないか、等）

---

## 4. 実装前の事前調査【必須】

**以下を確認して報告し、大杉さんの承認を得てから実装へ進むこと。**

### 4.1 木構造変更の影響

`ev-europe-2026`にYardを挿入した場合、以下が現状維持されることを確認する。

1. BackwardPlanner：`_propagate_to_children`が、mom→Yard（1子、`lt_wks=0`）→leaf_in（既存のlt_wks/ss_days）という2段の伝播で、**Yard挿入前と全く同じ週にleaf_inの需要が置かれるか**
2. ForwardPlanner：Yardが`_clear_derived_p`で正しくクリア対象になるか（`node_type != NODE_TYPE_LEAF_IN`の判定に含まれるはず）。`_propagate_to_parent`/`_propagate_to_child`がYardを普通の中間ノードとして扱うか
3. Mode4：`request_fix_mode4_supply_role_semantics.md`の`leaf_membership`収集（`decoupling_node.walk_preorder()`で`node_type==NODE_TYPE_LEAF_IN`を収集）が、Yard挿入後も**leaf_in自体（Battery_HU等）を正しく見つけるか**（Yardは`leaf_in`型ではないので、`walk_preorder()`はYardを経由してさらに下のleaf_inまで辿るはず——実際に確認すること）
4. Kitting List：`_propagate_to_parent`が呼ばれる箇所で、`node`（呼び出し元）が今後「leaf_in」ではなく「Yard」になるケースが生じないか。Yardは`Factory_Import_HU`の直接の子になるため、**Yard自身がkittingの記録対象になってしまわないか**を確認する（3a-1では望ましくない——kittingは最終的にはleaf_inの実体を記録すべきという前提が崩れないか）

### 4.2 sc_tree_builder.py の実装確認

`node_type`をそのまま文字列として保存する実装（`node_type = str(row["node_type"]).strip()`）であることは確認済み（検証・allowlist無し）。ただし以下を確認する。

5. `NODE_TYPE_MOM`判定（`n.node_type == NODE_TYPE_MOM and n.parent is None`、IN root検出）に、`stockyard`が誤って引っかからないか（引っかからないはず——文字列が異なるため）
6. `_make_node_id`が`stockyard`型でも問題なくnode_idを生成するか

### 4.3 PPC・GUI への影響

7. `ppc_forward.py`のコスト連鎖解決（サプライヤーコストの`_resolve_node_list`等）が、leaf_inとmomの間にYardが挟まることで壊れないか
8. World Map（`_MAP_NODE_STYLE`）・PSIチャート凡例で`stockyard`が未定義の場合、どう表示されるか（エラーになるか、単に無色になるか）

### 4.4 golden baseline の扱い

9. `ev-europe-2026`は現在working tree上でMode4修正済み・golden未更新のため、**3a-1の「golden不変」判定は committed golden ではなく、Mode4修正後・Yard挿入前に取得したフレッシュなbaseline（`tools.run_headless_from_folder.run()`のスナップショット）と比較すること**。他12ケースは committed golden をそのまま使ってよい。

### 4.5 報告

上記1〜9の結果を大杉さんへ報告し、想定通りか、追加の変更が必要かを確認してから実装へ進むこと。

---

## 5. テスト要件（3層）

### 5.1 Unit

- `NODE_TYPE_STOCKYARD`定数が存在し、`PlanNode`に問題なく設定できる
- 合成ツリー（mom → Yard(stockyard, lt=0) → leaf_in）で、BackwardPlanner実行後、leaf_inの`psi4demand[w][S]`がYard挿入前と同じ週に同じLot_IDを持つ
- 同様にForwardPlanner実行後、mom自身の`psi4supply[w][P]`がYard挿入前と同じ内容になる（Yardの`I`は常に空）
- Yard自身の`kitting`が空のまま（もし4.1-4の懸念が実際に問題なら、ここで対策を確認する）

### 5.2 Integration（CSV → build → backward → copy → Mode4 → forward）

- `ev-europe-2026`にYardを挿入したCSVで、Local側・Import側とも、**Yard挿入前とP/S/I/CO・kitting completeが完全に一致する**こと
- `bom-test-2026`も同様

### 5.3 golden

- **他の全ケース（Yardを挿入しないモデル）は committed golden と完全一致**（無変化）
- `ev-europe-2026`・`bom-test-2026`は、§4.4のフレッシュbaseline（Mode4修正後・Yard挿入前）と完全一致することを確認する。committed golden との差分は「Mode4修正による既知の差分」のみであり、**Yard挿入による新規の差分がゼロ**であることを示す

---

## 6. 手順

```
① §4 事前調査を実施し、報告する（実装前に一度停止）
② 大杉が調査結果を確認し、実装方針を確定
③ NODE_TYPE_STOCKYARD 定数の追加、必要な配線の実装
④ サンプルデータ（ev-europe-2026, bom-test-2026）へのYard挿入
⑤ §5.1 Unit テスト
⑥ §5.2 Integration テスト
⑦ §5.3 golden（フレッシュbaseline比較）
⑧ 大杉の差分レビュー
⑨ 承認後、commit（golden更新は不要）
```

**②の前に実装しないこと。⑧の前にcommitしないこと。**

---

## 7. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `tasklist | findstr python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること（warm-up追記は commit しない）
- **`.gitignore` 対象のフォルダに触れないこと**（`git ls-files` で対象を取得）
- コミットメッセージは、指定したもの以外の行（`Co-Authored-By`等）を**勝手に追加しないこと**
- **指示に矛盾を見つけた場合は、実装前に指摘すること**
- `request_fix_mode4_supply_role_semantics.md`の変更（`wom/engine/push_pull.py`、`tests/test_push_pull_mode4_supply_role.py`）は**そのままworking treeに保持**し、本Letterの作業に含めて一緒にcommitするか、大杉さんの指示を仰ぐこと（現時点では別々にcommitしないよう指示されている）

---

## 8. 本 Request の範囲外

| 項目 | 理由 |
|---|---|
| gate keeping の有効化 | Stage 3a-2、別Letter |
| Yardの I を kitting判定に接続する実装 | Stage 3a-2 |
| safety stock（ss_days）の実運用確認 | Stage 3a-2（機構自体は既存で動くはずだが、3a-1では未検証のままでよい） |
| Yardへの原価・PPCルール付与 | 3a-2、または別途。3a-1では「コスト0・素通り」で足りるはず（§4.3で確認） |
| ev-europe-2026 golden の更新 | Stage 3a-2完了後、最終形が固まってから一括更新（大杉さんの2026-09-04判断） |
| Mode4修正のcommit | 大杉さんの指示待ち |

---

## 9. 参考

- `docs/chat_memo/260904_0919Assemble_kitting_Stockyardのモデル化.docx`（本Letterの設計根拠）
- `docs/design/kitting_list_assembly.md`（§3 Stock Yard、§4 段階3a、§5.5）
- `requests/request_kitting_stage1.md`（Kitting List段階1、`45d6eac`）
- `requests/request_fix_mode4_supply_role_semantics.md`（Mode4 WHO/WHEN分離、実装済み・承認済み・commit保留中）
- `requests/request_fix_a1_supply_role_rev2.md`（`supply_role`の導入、`_propagate_to_children`の参照元）

---

**End of Request Letter**
