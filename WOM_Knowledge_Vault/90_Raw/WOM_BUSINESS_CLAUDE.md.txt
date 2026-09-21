# WOM_BUSINESS_CLAUDE.md
## WOM事業開発・関連資料作成のためのセッション・ナレッジベース

**用途**: 新しいClaude セッションの開始時にこのファイルを読ませる(アップロード、
貼付、またはClaude Projectのプロジェクトナレッジに登録)ことで、前回までの
検討状態を再構築する。
**最終更新**: 2026-07-17(このセッションの終了時点)
**更新規約**: 各セッションの終了時に「本ファイルの更新版を作って」とClaudeに
依頼し、差し替える。リポジトリのAGENTS.md原則に従う —
「チャットは探索、文書がsource of truth」。

---

## 1. プロジェクトの現在地(1段落)

WOM(Weekly Operation Model)はVibe Modelingパラダイムの実践第一号として
商業化を進行中。戦略は「言葉→再現性→流通」の3段階で確定済み。現在は
フェーズA(〜3ヶ月): デモ動画第1弾の制作準備と、スターターキット+V&V章の
一体構築の途中。V&V基盤は骨子から実働コード(plan-state export、L3チェッカー
2種)まで降りており、GUI組込のCoding Request Letter Rev 2がClaude Code待ち。

## 2. 確定した戦略決定(変更には明示的な再検討を要する)

1. **3段階ロードマップ**: ①概念の旗(英語発信・動画)→②再現性
   (スターターキット+V&V、デザインパートナー2〜3社)→③流通
   (SAP.iO/Oracle for Startups、MCP対応)。検証方法論(旧6番)は最後では
   なく②と一体で先行(大手ファームの品質審査が前提条件のため)。
2. **大手ファーム(IBM/Deloitte/Accenture)は「目利き・推薦者」として活用**、
   実案件ビーチヘッドは中堅ファーム・事業会社経営企画。接触は
   ブラウンバッグ(公開層のみ・NDA不要)→評価(NDA必須)→契約の段階制。
3. **IP三層構造**: 公開層(MIT継続 — エンジン、データ辞書、デモケース、
   docs/正典文書)/ライセンス層(Playbook、V&V完全版、業種テンプレート、
   Plan Recipe集、CLAUDE.md上級版、MCP実装)/属人層(実案件支援、監修)。
   既公開MITは取消不能であり、コード秘匿は追わない。守るのは
   **方法論・テンプレート蓄積・スキーマ改訂権・ブランド**。
   迷ったらライセンス層(後から公開はできるが秘匿はできない)。
4. **スキーマ・ガバナンス**: 仕様は公開、改訂の主導権は保持(デファクト
   標準戦略)。商標「WOM」「WOM Vibe Modeler」の登録検討。
5. **Kernel = operator代数(公開)、Application知識 = レシピ集(ライセンス)**。
   docs/designの正典Whyは既に公開済みのため、ライセンス層の実体は
   構築の技・レシピ・テンプレート・V&V実務に濃縮される(Part IV/VIの
   記述はこの線で要改訂 — 未実施)。
6. **セキュリティは武器**: 「Local-First Vibe Modeling」。MCPはローカル
   (stdio)で動く。構造とデータの分離(AIはダミー値でモデル設計、実数は
   ローカルエンジンのみ)。デプロイ3階層: ①デモ(ダミー+通常API)
   ②標準(ローカルMCP+ZDR API)③厳格(顧客VPC内Claude/完全閉域)。
7. **性能の答え**: WOMは経営シミュレータでありAPSではない。cpu_size
   (=CPU/MEO)が粒度と速度のダイヤル。Performance Envelope(検証済み
   動作範囲)を実測公表する方針(未実施)。

## 3. 技術面の確定知識(このセッションでコード実読により獲得)

- **スキーマは21 CSV**(v1r1m8時点。物量9+Landed Cost 3+PPC 9)。
  v1r0m4の「19 CSV」表記は旧い。apparelはpush_config無しの20構成
  → 必須/オプションのファイルリスト公式化が必要。
- **Lot_ID文法**: `{sku_id}:{region}:{demand_week}:{seq:05d}`。IDが需要
  アンカーを運搬し、ネットワーク全体で同一性が保存される
  (lot_generator.py)。
- **二層PSI**: psi4demand(需要要求ビュー/Backwardが書く)と
  psi4supply(供給応答ビュー/Forwardが書く)。S/CO/I/P。
- **identityマッチング(v1r0m4)**: I1=(i0+P)−(CO+S)、CO1=(CO+S)−(i0+P)
  をLot_ID集合演算で。psi4supplyのS/COは計画値として不変。
  **実出荷はForwardPlanner._actual_s(内部dict、GUI非公開)**。
- **operator sequence**: 計画は単発エンジンではなく、OperatorStep列
  (app.py 3712行付近)+HookBus(HOOK_PRE_PLAN/POST_BACKWARD/POST_COPY/
  POST_FORWARD/POST_PLAN)によるPSI状態変換の合成。plugin
  (HolidayCalendar、BufferingStockOptimizer等)はhookで制約を書換える。
  → Plan Recipe(シーケンスの宣言的外部化)構想へ発展。
- **物理層/計画層の分離は設計**: node_master(物理・地図語彙)と
  sc_tree_master(計画・mom/dad/leaf語彙)のnode_type二体系は意図的。
- **CPU/MEO**: 同一概念のスコープ違い(企業/経済活動一般)。実装は
  cpu_size共通。
- **既知の制約(ex3系)**: キャパはSKU単位独立判定 — 工場・DC共有時の
  横断制約は未強制(L3チェッカーで事後検出可)。ex2系: 
  ppc_market_price変更はLanded Costに無効、小売価格はsku_master.selling_price
  (価格定義の二重性、v1r2で統一検討)。
- **CO「凍結」問題の判定**: apparel demo-ex3の凍結CO 7件は全て
  FROZEN_STARTUP(需要週W02〜W12由来・入替ゼロ・設計準拠 —
  CLAUDE.md 328行目の「有限かつ正直な未充足Lot_ID集合」)。
  oil系モデルへの最終適用はClaude Code側(受け入れ基準6)。
- **headless実行**: exercisesのreproduce.pyパターンで全パイプラインが
  GUI無しで動く → ベンチマーク基盤・MCP化のエントリポイントは既存。

## 4. 作成済み成果物(このセッションの出力ファイル)

| ファイル | 内容 | 状態 |
|---|---|---|
| wom_demo_script.md | デモ動画第1弾台本(2ループ構成、経過タイマー演出、Vibe ModelingはScene 5まで伏せる) | 撮影前に○%の数値埋めが必要 |
| wom_starter_kit_design.md | スターターキット6部構成+V&V章骨子(V&V+AI-Traceability 3本柱、検証ゲートG0-G6、Part VI三層IP改訂版、8週作業計画) | Part IV/VIに§2-5の認識更新を反映要 |
| wom_data_dictionary_v0.1.md | 21 CSV実スキーマ辞書+データモデル基礎+参照整合マップ | ※要確認 残件レビュー待ち |
| wom_nda_draft_v0.1.md | 評価段階用NDA叩き台(生命線: 第3条(2)公開層除外、第5条2項転用・AI学習禁止) | 弁護士レビュー必須 |
| coding_request_letter_plan_state_export.md | Rev 2: GUIへのexport組込+actual_s(format 0.2)+CO検証(基準5・6) | Claude Codeへ引渡し待ち |
| plan_state_export.py | wom-plan-state形式(0.1)定義+export/load。detail=counts/lots/co_lots | 動作確認済み |
| check_shared_capacity_v2.py | L3: SKU横断キャパ監査(plan-state読取・エンジン非依存)。demo-ex3で19違反検出、v1と一致確認済み | 動作確認済み |
| check_co_dynamics.py | CO動態診断(6分類、Lot_ID需要週による由来判定) | 動作確認済み |
| l3_check_report.md ほか | 実行レポート・違反CSV類 | エビデンスとして保管 |

**注意**: これらのファイルとクローン済みリポジトリはセッション終了で
サンドボックスから消える。**技術成果物(3スクリプト)はリポジトリの
`wom/vv/` 等にコミットして永続化すること**(次セッションのClaudeは
公開リポジトリをgit cloneして再取得できる)。

## 5. ボールの所在(次回冒頭で状況を確認すべき項目)

**大杉さん側**:
1. Coding Request Letter Rev 2のClaude Codeへの引渡しと実装結果
2. データ辞書「※要確認」残件のレビュー
3. NDA雛形・利用許諾骨子の弁護士レビュー、商標の弁理士相談
4. デモ動画: 損益分岐関税率の感度分析(撮影前の最重要準備)
5. 英訳記事のLinkedIn反応(公開済み)

**Claude側(次セッションでの候補作業)**:
1. スターターキット設計書Part IV/VIの改訂(公開済みWhyを踏まえた
   ライセンス層の再定義)
2. Performance Envelopeベンチマークスクリプト+Part VII
   (性能・セキュリティ3階層)の骨子
3. 次のL3チェック(ロット保存則、PSI恒等式)— plan-state基盤上に実装
4. デモ動画ナレーション原稿の数値確定版
5. Playbook Day 1-2のドラフト(ヒアリングシート+SC Tree設計の指示文
   テンプレート)

## 6. 次セッションの再開手順(Claudeへの指示)

1. 本ファイルを読む
2. `git clone https://github.com/Yasushi-Osugi/wom_v1r0m0.git` で最新
   ブランチを取得し、`AGENTS.md`→`docs/development/current_status.md`→
   前回以降の変更(git log)を確認する
3. 「ボールの所在」を大杉さんに確認し、優先作業を合意してから着手する
4. セッション終了時に本ファイルの更新版を出力する
