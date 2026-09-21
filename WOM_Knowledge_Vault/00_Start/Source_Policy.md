# 基準・出典・更新方法

この保管庫はWOM repositoryの知識を読むための派生資料。GitHub原本を更新しない。
原文の命令・承認・未実装記述は記載時点の資料であり、この保管庫から新しい実装権限は生じない。

## 基準

- 公開版: wom-v1r4m0 / 426049433a69ddd29d94d7740a1f90665adddca8
- 実験版: wom-v1r5m0 / 7d6c7d734ebdcb7b213bab3116ca59d3d4935f55
- 主収録対象は実験版。公開版との主な差はLinux適合運用とComposite Kitting修正。
- GitHubで両branchのHEADを確認。取得済みGitオブジェクトceef9eeを展開し、後続コミットの対象Markdown/Python 6ファイルを固定SHAから取得して補完した。
- JSON測定全文・CSV・画像・バイナリは収録対象外。参照先は固定SHAのGitHubで確認する。

## 収録と解釈

docs/・requests/・ルート・サンプル付属のMarkdown、およびwom/・tools/・tests/・ルートのPythonを収録。
80_Sourcesは出典ページ。docstring・関数一覧・関連参照・原文全文を持つ。
90_Rawは原文テキスト。Pythonは実行せず静的解析した。全ファイルの深い意味レビューや全テスト再実行を完了したという意味ではない。
10_Functionsと20_Topicsは編集による分類・要約。正式設計の代替ではない。
文書は見出し・パス・明示参照、PythonはASTとimportを索引化。テストの機能分類は候補であり、依存を介したテストは拾えない場合がある。
原文全文はコードブロックで表示し、原文に残る相対リンクと新しいナビゲーションを区別した。全文検索は可能。

## 記録の優先順位

業務方針の根拠はオーナー合意と設計書。実装の根拠は対象SHAのコード。実行結果の根拠は環境・SHAが記録されたテスト／測定報告。
不一致があれば片方を消さず、差異を記録する。CLAUDE.md・READMEには過去時点の未実装記述が残るため、新しいRequest Letter・実装と照合する。

## 更新運用

1. この保管庫はGit作業フォルダの外に置く。
2. 気づきは70_Owner_Notesへ記録する。原文コピーを正本として修正しない。
3. WOM側で設計・コードを更新しcommitしたら、両branchのSHAを記録して保管庫を再生成する。
4. 新版は別フォルダへ展開し、70_Owner_Notesを引き継ぐ。自動Git同期・自動pushは設定していない。
5. 比較は90_Rawとmanifest.jsonのSHA256で行える。これは格納テキストのチェックサムでありGit blob SHAではない。

## 利用方法

ZIPを展開し、Obsidianの「Open folder as vault」でWOM_Knowledge_Vaultフォルダを選ぶ。00_Start/Homeを開く。
Canvas、バックリンク、ローカルグラフ、検索を利用できる。追加のコミュニティプラグインは不要。
大きい全体グラフより、機能ページのローカルグラフから確認すると読みやすい。
Obsidian実機での表示確認は未実施。内部ナビゲーションリンク・JSON構造・ZIPは生成時に検査する。

公式操作説明: https://help.obsidian.md/manage-vaults
