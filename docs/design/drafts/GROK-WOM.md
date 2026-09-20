# GROK-WOM.md
# WOM開発に関するGrokとの対話知識ベース

**作成日**: 2026-09-14  
**対象リポジトリ**: https://github.com/Yasushi-Osugi/wom_v1r0m0  
**推奨ブランチ**: `wom-v1r4m0`  
**対話相手**: Grok (xAI)  
**開発者**: 大杉（Yasushi-Osugi）

このファイルは、スマホ環境での会話をLocal PCの別AIチャット環境から再開できるようにするための知識ベースである。  
新しいセッションでは、まず本ファイルを読ませたうえで作業を続けること。

---

## 1. プロジェクト概要（WOM）

**WOM (Weekly Operation Model)** は、週次PSI（Production / Sales / Inventory）を基本単位とするエンドツーエンドのサプライチェーン計画・シミュレーションツール。

- 実装: Python + tkinter GUI
- 起動: `python -m main`（GUI） / `python -m main --cli`（ヘッドレス）
- 目的: 最適解を出すソルバーではなく、需要ショック・能力制約・関税・為替・バッファ在庫配置などが週次オペレーションと損益にどう波及するかを「動かして確かめる」モデル
- 三層構造:
  - Physical Layer（実ノード / 地図）
  - Planning Layer（SCTree + PSI）
  - Management Layer（KPI / PPC / P&L）

### 計画の三層（v1r4m0で第1層が揃った）

1. **配分**（Management Planning）: どの市場にどれだけ供給するか → 利益地形図・メリットオーダー・レジーム地図
2. **配置**（Backward Planning）: いつ・どこで生産開始するか → Demand Anchored Lot
3. **実行**（Forward Planning）: 能力・在庫・LTの下で本当に実行できるか → 週次PSI・CO

---

## 2. AIエージェント向け開発ガイドの要点

### 正本の置き場所

- **共通エントリポイント**: `AGENTS.md`（Claude Code / Codex / Grok / Gemini 等向け）
- **Claude固有の補足・歴史**: `CLAUDE.md`
- **正本知識**: `docs/` 以下（development / architecture / design / scenarios）
- チャットログは探索用。**リポジトリのドキュメントが Source of Truth**

### 読むべき順序（編集前）

1. `README.md`
2. `docs/development/README.md`
3. `docs/architecture/README.md`
4. `docs/design/README.md`
5. `docs/scenarios/README.md`

### コア概念（安易に変えない）

- Weekly planning bucket
- PSI（Production/Purchase, Ship/Sales, Inventory）
- Demand Anchored Lot
- Inbound Tree / Outbound Tree
- MOM（Mother Plant） / DAD（Decoupling / Allocation）
- Capacity-aware planning
- PPC（Price / Profit / Cost）
- Scenario-based supply chain modeling

変更が必要な場合は、先に設計ドキュメントを更新する。

### 開発ルール（要約）

1. 既存サンプルモデルが動くこと
2. `python -m main` を壊さない
3. 小さくレビュー可能な変更を優先
4. 挙動・前提変更時はドキュメント更新
5. 計画ロジック変更時はテスト追加/更新
6. 無関係なリファクタとシナリオ変更を混ぜない

### Planning Engine / PPC の原則

- エンジン本体は汎用・正準のまま保つ
- シナリオ固有挙動は **CSV / プラグイン / ジェネレータ / パラメータ / ドキュメント** で表現し、コアにハードコードしない
- PPCは物理フロー・価格伝播・コスト構造・Profit Zone・Node P&L・経済前提を分離して保つ

---

## 3. 保護コア（Anti-Degrade）

過去の教訓: v1r0m3 の「MOM Constrained Demand Allocation」リファクタで、`cap_soft` の配線が副作用で外れ休眠した。

### 保護対象ファイル（ゲート付き）

- `wom/engine/backward_planner.py`
- `wom/engine/forward_planner.py`
- `wom/engine/plan_copy.py`
- `wom/model/plan_node.py`
- `wom/model/sc_tree.py`
- `wom/engine/push_pull.py`

### ルール

1. Request Letter 等の明示指示なしに改変しない
2. 改変する場合は **3層テストを緑**にする
   - **Unit**: 合成ツリーで固定値 assert
   - **Integration**: CSV → 実ローダ → ノードのデータ経路
   - **E2E golden**: `tools/run_headless_from_folder.py` + `tests/golden/*.json`（既存サンプル不変）
3. オーナー（大杉）が `git diff` をレビューしてからコミット
4. 意図的挙動変更時は golden を再生成・コミット（差分が監査証跡）

**二重化が必須**: 手続きルール（soft）だけでは不十分。テストによる機械的強制（hard）が必要。

---

## 4. 大杉の仮説（本対話の中心）

### 仮説の内容

WOM最新版（`wom-v1r4m0`）において:

1. **Headless環境**（GUIなし）を整備する
2. Grokを含む**複数のAI Agents**が、WOM初期データセット（CSV parameters）によるモデル定義の後に、次の認知・実行サイクルを回す
3. これにより **WOM自体の機能強化**を進め、同時に **WOMの強化学習環境**を整備できる

### サイクル

1. WOM入力データセット（CSV files parameters）の評価
2. WOMの実行
3. シミュレーション結果の評価
4. WOMのモデル定義の修正
   - 4-1. WOMの内部データ構造の修正
   - 4-2. 入力データセットの修正
5. 手順1に戻る

---

## 5. Grokの評価と推奨方針

### 仮説の強み

- Headless前提は必須で、既存の `tools/run_headless_from_folder.py` と golden が観測器として使える
- 「入力CSV → 実行 → 結果評価 → 修正」は、シナリオ固有をCSV/プラグインに閉じる設計思想と整合
- 「機能強化」と「強化学習環境」は段階的に分離可能

### 重要な注意点

#### A. 4-1 と 4-2 を同列に扱わない

| 区分 | 内容 | 扱い |
|------|------|------|
| **4-2** | 入力CSV / シナリオ修正 | 比較的安全。主戦場として自動適用可能（サンプル互換・golden方針を守る） |
| **4-1** | 内部データ構造・Planning Engine修正 | 保護コアに直結。**提案生成まで**に留め、適用は Request Letter + 3層テスト + オーナーレビュー |

#### B. 評価関数を明示する

曖昧な評価だとループが発散する。最低限の評価軸:

- 実行可能性（headless成功、期間・製品集合）
- 計画整合（fill rate、CO、cap違反、在庫発散）
- 経済性（Gross Profit、Profit Zone、Node P&L、構造的取りこぼし）
- 安定性（golden差分：意図的変更以外は不変）
- 説明可能性（なぜその配分/バッファになったか）

報酬はスカラー1本より、**制約付き多目的（feasibility first）**がWOMに合う。

#### C. 探索空間を制限する

全CSV次元を開けず、段階的に:

1. 既存サンプルのパラメータ感度（能力±、需要ショック、関税/為替）
2. 配分空間（利益地形図・merit order領域）
3. バッファ配置
4. 新規ノード / SCTree構造変更（コスト高）

#### D. 再現性と監査を残す

各周回でリポジトリに残すべきもの:

- 入力スナップショット（どのCSVをどう変えたか）
- headless実行ログとKPIスナップショット
- 評価スコアと判定理由
- 採用/棄却の意思決定
- コア変更提案時は Request Letter 草案と想定テスト

---

## 6. 推奨アーキテクチャ（実装方針）

```
[Observer]  headless実行 + KPI / goldenスナップショット
    ↓
[Evaluator] 評価関数（実行可能性・計画KPI・経済KPI・差分）
    ↓
[Actor]
  A. Scenario Actor  … CSV / パラメータ / プラグイン設定の変更（主戦場・自動適用可）
  B. Proposal Actor  … コア / 内部構造の「変更提案」のみ（適用は人間ゲート）
```

### RL環境としての最小単位

- **状態**: モデル定義（CSV集合）+ 実行後KPI
- **行動**: 許可されたパラメータ空間内の変更
- **報酬**: 制約満足を前提とした利益 / サービスレベル等
- **エピソード**: 1シナリオの Load → Plan → PPC

エンジンコード自体を行動空間に入れるのは、現時点ではRLというより**ソフトウェア進化（人間承認付き）**として扱う。

---

## 7. 推奨する次の実装ステップ

1. **headlessの評価用KPI契約を固定**（既存goldenの延長）
2. **1つのサンプル**（例: `soysauce-jpy-2027-alloc`）で、パラメータ摂動 → 実行 → スコアの最小ループを作る
3. **スコアと変更履歴**を `docs/` または `requests/` 配下に残す仕組みを入れる
4. その後に複数エージェント役割（評価役・修正役・監査役）を分ける

---

## 8. 主要コマンド・パス（参照用）

```bash
# GUI
python -m main

# CLI / headless
python -m main --cli --start-week 2027-W01 --num-weeks 156

# テスト
python -m pytest tests/ -v

# golden / headless ハーネス
python -m tools.run_headless_from_folder --model-dir data/sample/<case> ...
```

依存例: `tkintermapview pandas numpy matplotlib openpyxl networkx pytest`

サンプル例:
- `data/sample/rice-japan-2027-2028`
- `data/sample/iphone-2027-2029`
- `data/sample/soysauce-jpy-2027-alloc`（配分・利益地形図向け）

---

## 9. 対話の合意事項（2026-09-14時点）

- Grokの理解（AGENTS.md / CLAUDE.md / 保護コア / 開発方針）は大杉により「正確」と確認済み
- 大杉の仮説（headless + 複数AIによる評価・実行・修正サイクル → 機能強化とRL環境）は、方向として妥当と評価
- 実装時は **4-2（入力修正）を主戦場**、**4-1（内部構造）は提案のみ** と分離する
- 評価関数の明示・探索空間の制限・監査ログのリポジトリ保存が成功条件
- 本ファイル（GROK-WOM.md）を知識ベースとして、Local PCの別AI環境から再入可能にする

---

## 10. 新しいセッションへの引き継ぎ指示（他AI向け）

あなたはWOM（Weekly Operation Model）の開発支援を行う。  
まず本 `GROK-WOM.md` を読み、以下を前提とせよ。

1. リポジトリ: https://github.com/Yasushi-Osugi/wom_v1r0m0 （ブランチ `wom-v1r4m0` 推奨）
2. 正本は `AGENTS.md` と `docs/`。保護コアは無断で改変しない
3. 進行中のテーマは「headless + 複数AIエージェントによる評価・実行・修正ループ」と、それを強化学習的探索環境として整備すること
4. 入力データセット修正（4-2）を優先し、内部構造修正（4-1）は提案に留める
5. 変更は小さく、テスト・ドキュメント・監査可能性を守る

大杉からの次の具体的指示を待ち、上記方針に沿って提案・実装支援を行うこと。
