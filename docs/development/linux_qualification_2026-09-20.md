# Composite Node実験用Linux環境の適合確認

日付: 2026-09-20

## 許可と対象

大杉さんは本会話で、実験リポジトリに限定した独立Linuxコピーの
段階的適合確認を許可した。Windows作業フォルダは共有・操作しない。
保護core、差分レビュー、commit/pushの承認規則は継続する。
golden正本更新と最終GUI確認はWindowsで行う。

- Repository: `Yasushi-Osugi/wom_development_composite_node`
- Branch: `wom-v1r5m0`
- Baseline: `426049433a69ddd29d94d7740a1f90665adddca8`
- Linux checkout: `/workspace/scratch/ae3ea3e36a29/wom_composite_linux`
- Python venv: `/workspace/scratch/ae3ea3e36a29/wom_linux_venv`
- OS / Python: Linux x86_64 / CPython 3.12.14

このコピーの `origin` は上記実験リポジトリを指す。Windows側の
`origin`（旧開発リポジトリ）とはremote名の意味が異なる。

## 完全性と比較基準

- clone後の作業ツリーはclean。
- `git fsck --full`: exit 0、診断なし。
- 文書編集前の `git diff --exit-code HEAD`: exit 0。
- `31e2f2d..4260494` の差分は `docs/design/drafts/GROK-WOM.md` の追加のみ。
- 今回の適合確認ではWOMコード・サンプルCSV・golden正本を変更しない。

Gitオブジェクトと取得済み作業ファイルの検査で問題は見られなかった。
これは当該コピーに関する確認であり、あらゆるLinux mountの保証ではない。
Windowsの同一SHAでの新規再実行は未実施。比較対象はコミット済みgolden。

## 依存関係

独立venvへ `requirements.txt` と、README記載の追加依存
`pytest networkx tkintermapview` をインストールした。
`python -m pip check` は `No broken requirements found.`。

| Package | Version |
|---|---|
| pytest | 9.1.1 |
| pandas | 3.0.6 |
| numpy | 2.5.3 |
| matplotlib | 3.11.2 |
| openpyxl | 3.1.5 |
| networkx | 3.6.1 |
| tkintermapview | 1.30 |

Windowsの依存バージョンと一致させた環境ではない。

## 検証

実行コマンド（リポジトリroot）:

```sh
/workspace/scratch/ae3ea3e36a29/wom_linux_venv/bin/python -m pytest -q --junitxml=/workspace/scratch/ae3ea3e36a29/wom_linux_pytest.xml
```

結果: **442 passed, 1 skipped in 103.81s** (exit 0)。

- JUnit記録で `tests.test_golden` の13ケースが実行・成功したことを確認。
- `tests.test_gui_panel_invariants` はモジュール全体がcollection時にskip。
  この環境ではGUI群を検証していないため、Windowsの511 passed / 3 skipped
  とテスト数を直接比較しない。
- 実行後に未追跡の `data/sample/apparel-us-2026/push_config.csv` が残った。
  既存テストにはサンプルフォルダ内で設定を一時変更する経路がある。
  残留の厳密な発生箇所は未確定。今回これを修正したとは扱わない。
- 残留CSVは作業コピー外の
  `/workspace/scratch/ae3ea3e36a29/wom_linux_test_generated_push_config.csv`
  へ移動して保存した。Windows原本には影響しない。
- 追跡対象のWOMコード・サンプルCSV・goldenには実行後も差分なし。

`tests/test_golden.py` はheadless harnessでLoad→Planning→PPCを実行し、
period/products/config、forward/backward、ppc、psiを既存goldenと比較する。
GUI表示のない環境でのGUIスキップは合格に読み替えない。

## 判定

このSHAと記載依存環境について、既存の非GUIテストと13ケースの
headless golden比較を行う範囲で適合を確認した。所有者が承認した
段階的Linux開発・測定へ進める。Composite業務仕様への適合やGUIの
品質を、この環境確認だけで認定しない。

今後の反復実験も独立コピーで行い、実行前後の追跡・未追跡差分を確認する。
未追跡CSVの残留は再実行へ影響し得るため、測定条件に混入させない。

## 変更と適用

`AGENTS.md` のLinux一律禁止を、当該実験リポジトリだけの段階的許可へ
変更するローカル案を作成。commit/pushは実施していない。
Windows側へ反映する際は差分を確認してからcommitする。
