# Request Letter：Mode4 が `supply_role` を無視して assembly 部材を分割する問題の修正

**起票日**：2026-09-03
**起票者**：大杉
**種別**：**禁足コア変更**（`wom/engine/push_pull.py`）
**対象ブランチ**：`wom-v1r3m0`
**別タスク登録**：`task_fdcb95f8`
**設計文書**：`docs/design/kitting_list_assembly.md` §4 段階3a、§5.5

**本件は Kitting List 段階2・段階3a の前提条件である。**
本件を解決しないまま gate keeping を有効にすると、
`ev-europe-2026` Import 側は全ロットが部材不足となり生産が完全に停止する。

---

## 0. 禁足ルールに基づく承認事項

- [x] Request Letter 起票（本書）
- [ ] **§3 の事前調査を実施し報告**（実装前に一度停止）
- [ ] 3層テスト（Unit / Integration / golden）緑
- [ ] オーナー（大杉）による差分レビュー
- [ ] golden 差分が「正しくなった結果」であることの確認

**上記が揃うまでコミットしないこと。**
**§3 の事前調査を報告し、合意を得てから実装へ進むこと。**

---

## 1. 問題

### 1.1 機構

`push_pull.py` の Mode4（`push_lead_time_weeks`）は、
`decoupling_node.walk_preorder()` 配下の全 leaf_in を**無条件に
「同種の並行供給者」として扱い**、親の lot リストを
**重複なし・disjoint な 1/n スライス**に分割して各子へ書き込む。

`supply_role`（`confluence` / `assembly`）の区別は 2026-08-30 に導入したが
（`39bcb44`）、**Mode4 はそれ以前に書かれたコードであり、一切参照していない。**

### 1.2 実測（2026-09-03、Kitting List 段階1により判明）

`ev-europe-2026` Import 側、`Factory_Import_HU`（Mode4 decoupling node、3部材）：

```
kitting complete = 0 / 7,945 件
全件が「3部材中ちょうど2部材が欠けている」

Battery_HU  34件
Motor_HU    33件
ECU_HU      33件
3者の積集合は常に空。和集合は親需要100件と一致
```

**BOM 部材が「車両1台分の全部材」ではなく「全体需要の 1/3 ずつ」しか
生産されていない。** 車両1台に必要な3部品のうち、実際に揃うのは常に高々1つ。

### 1.3 なぜ見えなかったか

- MOM ノード自身の P 合計は**数量として正しい**（3スライスが過不足なく分割されるため）
- `_match_by_identity` の `set()` が「どの子が実際に供給したか」を隠蔽していた
- golden の `series_md5` はノード集計レベルのハッシュであり、**内訳を見ない**

**Kitting List 段階1が可視化するために作られた、まさにその種類の欠陥である。**

### 1.4 影響範囲

`push_config.csv` に `push_lead_time_weeks` を持つ decoupling node のうち、
配下に**複数の leaf_in**を持つもの。

| モデル | golden | decoupling node | 子 | Mode4 |
|---|---|---|---|---|
| `ev-europe-2026` | **対象** | Factory_Import_HU | Battery_HU / Motor_HU / ECU_HU | **あり** |
| `smartx-2027-2029` | 対象 | Buffer_Chip_TW | ? | あり（`push_lead_time_weeks=39`） |
| `soysauce-*-2027` | 対象 | Bottling_Noda | ? | あり（`push_lead_time_weeks=7`） |

**`smartx` と `soysauce` の配下構成は §3 の事前調査で確認すること。**

---

## 2. 修正の方向

`_propagate_to_children`（`backward_planner.py`）で A1 修正時に採用したのと
**同じロジック**を適用する。

```
supply_role == "confluence" の子   → 分割（divmod による 1/n スライス。現状のまま）
supply_role != "confluence" の子   → 全量を各子へ（複製）
```

**既存の実装を流用できるはずである。**
`39bcb44` の `_propagate_to_children` を参照すること。

混在（同じ decoupling node の配下に `confluence` と `assembly` の両方がある）も
扱えること。

---

## 3. 【実装前に実施】事前調査

**以下を調べて報告し、合意を得てから実装へ進むこと。**

### 3.1 影響を受けるモデルの特定

`data/sample/` 全モデルについて、以下を機械的に調べる。

1. `push_config.csv` に `push_lead_time_weeks` が設定されている decoupling node
2. その配下（`walk_preorder()`）の leaf_in ノードの一覧
3. 各 leaf_in の `supply_role`（`confluence` / `assembly` / 空欄＝assembly）
4. **配下に複数の leaf_in を持つケースはどれか**

**`.gitignore` 対象のフォルダに触れないこと**（`git ls-files` で対象を取得）。

### 3.2 【最重要】cap_hard の前提の確認

修正すると、**assembly の子の生産量が n 倍になる。**

```
現在    Battery_HU 34 / Motor_HU 33 / ECU_HU 33   （合計100）
修正後  Battery_HU 100 / Motor_HU 100 / ECU_HU 100（合計300）
```

**`capacity_plan.csv` の `max_supply` が現在の 1/n を前提に設定されていると、
修正後に CO が大量発生する。**

`india-ghee-2026` で同じ構図が確認されている。`capacity_plan.csv` に
「※複数leaf_in合算後のPを基準に設定」という注記があり、
**モデル構築時点で重複を認識して cap_hard を嵩上げしていた**
（`requests/request_fix_a1_supply_role_rev2.md` §1.4）。

**調べてほしいこと：**

5. §3.1 で特定した各 leaf_in の `capacity_plan.csv` の `max_supply` の値
6. `note` 列に、設定根拠を示す記述があるか
7. **修正後の生産量（n 倍）が `max_supply` を超えるか。超えるなら何倍か**
8. 超える場合、`capacity_plan.csv` の修正が必要か。
   必要なら、どの値にすべきかの案

### 3.3 修正後の golden 差分の見積り

9. §3.1 で特定したモデルのうち、**golden 対象**はどれか
10. 各モデルで、どのノードの `series_md5` が変わると予想されるか
11. 下流（supply_point / dad / leaf_out）に影響が及ぶか。
    及ぶ場合、PPC の金額も変わるか

### 3.4 `smartx-2027-2029` の特殊性

`Buffer_Chip_TW` は `push_lead_time_weeks=39` という大きな値を持つ、
**InBound decoupling の唯一の実運用例**である
（`requests/request_investigation_s2_inbound_decoupling.md`）。

12. 配下の leaf_in は単数か複数か
13. 複数の場合、本修正の影響を受けるか

---

## 4. 実装内容（§3 の合意後）

### 4.1 対象

`wom/engine/push_pull.py` の Mode4（`is_lt_shifted_mode()`）の
leaf_in 分配ロジック。

### 4.2 変更しないこと

- Mode1 / Mode2 / Mode3 の挙動
- `_propagate_to_children`（`backward_planner.py`）
- `_match_by_identity`
- lot_id のスキーマと集合演算
- **2026-08-30 の Mode4 修正（`44e67bf`、二重計上の解消）を壊さないこと**

### 4.3 `capacity_plan.csv` の扱い

§3.2 の調査結果によって判断する。

- **cap_hard の修正が不要** → CSV は変更しない
- **必要** → 本 Letter に含めるか、別 Letter とするかを、調査報告時に相談する

**調査前に CSV を変更しないこと。**

---

## 5. テスト要件（3層）

### 5.1 Unit

- Mode4 で、`confluence` の子には分割が適用されること（現状維持）
- Mode4 で、`assembly` の子には**全量が渡ること**
- 混在（`confluence` と `assembly` が同じ decoupling node 配下）が正しく処理されること
- 子が1つの場合、挙動が変わらないこと
- **2026-08-30 の二重計上（`44e67bf`）が再発しないこと**
  （`tests/test_push_pull_mode4_double_count.py` が緑のままであること）

### 5.2 Integration（`ev-europe-2026`）

- `Factory_Import_HU` の kitting `complete` が **0 → 大幅に増える**こと
- Battery_HU / Motor_HU / ECU_HU の P_sum が**それぞれ親需要と同数**になること
- 3者の積集合が**空でなくなる**こと
- CO が発生する場合、その量と原因（cap_hard 超過か否か）

**kitting は既に実装済み（`45d6eac`）なので、`complete` の件数で直接検証できる。**

### 5.3 golden（13ケース）

| 状況 | 判定 |
|---|---|
| §3.1 で「影響あり」と特定したケースが変化する | **正常**（正しくなった結果） |
| §3.1 で「影響なし」としたケースが変化する | **異常**。コミットしないこと |
| §3.1 で「影響あり」としたケースが変化しない | **要調査**。報告すること |

**golden の JSON は、大杉の承認を得るまで更新しないこと。**

---

## 6. 報告してほしいこと

**第一段階（§3 の事前調査、実装前）**

1. §3.1 の一覧（モデル × decoupling node × 子 × supply_role）
2. §3.2 の cap_hard 調査（**修正後に超過するか**）
3. §3.3 の golden 差分の見積り
4. §3.4 の `smartx` の状況
5. `capacity_plan.csv` の修正が必要かどうかの判断

**第二段階（実装後）**

6. 修正の差分（`git diff`）
7. §5.1 の Unit テスト結果（**`44e67bf` の回帰テストが緑であること**）
8. §5.2 の Integration 結果（**kitting `complete` の件数**）
9. §5.3 の golden 差分と判定
10. `git status`（`data/sample/` が clean であること）
11. 気づいた点

---

## 7. 手順

```
① §3 の事前調査を実施し、報告する（実装前に一度停止）
② 大杉が調査結果を確認し、実装方針と capacity_plan.csv の扱いを決める
③ 実装
④ §5.1 Unit テスト
⑤ §5.2 Integration（kitting complete で検証）
⑥ §5.3 golden 13ケース
⑦ 大杉の差分レビュー
⑧ 承認後、golden を更新しコミット
```

**②の前に実装しないこと。⑦の前にコミットしないこと。**

---

## 8. 実行上の注意

- テスト実行中は `python -m main`（WOM GUI）を起動しないこと
- 実行前に `tasklist | findstr python` で他プロセスが無いことを確認すること
- golden テスト後は必ず `git status -- data/sample/` を確認すること
- `capacity_plan.csv` / `demand_forecast.csv` の warm-up 追記は commit しないこと
- **`.gitignore` 対象のフォルダに触れないこと**（`git ls-files` で対象を取得）
- コミットメッセージは、指定したもの以外の行（`Co-Authored-By` 等）を
  **勝手に追加しないこと**
- **指示に矛盾を見つけた場合は、実装前に指摘すること**

---

## 9. 参考

- `docs/design/kitting_list_assembly.md` §4 段階3a（本件が前提条件である理由）
- `requests/request_fix_a1_supply_role_rev2.md`（`supply_role` の導入。同じロジックを流用）
- `requests/request_fix_mode4_double_count.md` と承認通知（Mode4 の先行修正 `44e67bf`）
- `requests/request_investigation_s1_push_pull_default.md`（Mode1〜4 の調査）
- `requests/request_investigation_s2_inbound_decoupling.md`（`smartx` の Buffer_Chip_TW）
- `requests/request_kitting_stage1.md` と `45d6eac`（本件を発見した機構）

---

## 10. 補足：この欠陥が3度目である

InBound の部材配分に関する誤りは、これで3件目になる。

```
39bcb44  A1     _in_propagate が全ロットを各子へ複製 → 二重計上
                → supply_role で分割/複製を区別して解決

44e67bf  Mode4  copy_demand_to_supply の自然コピーをクリアせず二重計上
                → leaf_in の P をクリアしてから書くよう修正

本件     Mode4  supply_role を参照せず、assembly を confluence として分割
                → 8/30 の修正時に、leaf_in が1つのケースしか見ていなかった
```

**いずれも「ノード集計レベルでは数量が正しく見える」ため、
golden では検出できなかった。**

Kitting List 段階1が、初めてこの層を可視化した。
段階2（auto-debug の判定ルール）を実装すれば、
**この種の欠陥は今後、機械が検出できるようになる。**
