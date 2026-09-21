---
tags: [wom, source]
---
# docs/development/composite_kitting_implementation_2026-09-20.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/development/composite_kitting_implementation_2026-09-20.md) · [原文テキスト](../../../90_Raw/docs/development/composite_kitting_implementation_2026-09-20.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Kitting Gate：未完了kit・能力待ちの実装修正
- 実装
- 再測定
- 検証
- Linuxでの実装時検証
- Windows適用時のテスト補助関数修正
- Windowsでの最終確認（大杉さんの実行ログ・画面報告）
- 残る範囲と引継ぎ

## 関連する知識源

- [[80_Sources/requests/RequestLetter_Composite_Kitting_Backlog_v1.md|requests/RequestLetter_Composite_Kitting_Backlog_v1.md]]
- [[80_Sources/wom/engine/forward_planner.py|wom/engine/forward_planner.py]]
- [[80_Sources/tests/test_composite_kitting_recovery.py|tests/test_composite_kitting_recovery.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Kitting Gate：未完了kit・能力待ちの実装修正

基準コミット: `ceef9ee0e357a556fb5959fdb1e49d8b0e670347`

対象repository: `Yasushi-Osugi/wom_development_composite_node`

承認: 本会話で大杉さんがPSI List操作の整理に同意し、設計・実装を指示。
設計・範囲: `requests/RequestLetter_Composite_Kitting_Backlog_v1.md`。

## 実装

`wom/engine/forward_planner.py` の通常pull・全子stockyardのAssemblyに限定。

1. gateのローカル状態に、順序付きpendingとcompleted ID集合を追加。
2. 旧未完了→当週要求の順に、部材の揃ったkitを選ぶ。不足した旧kitは
   後続のready kitを妨げない。
3. completedを期首完成品IDで初期化し、完成時に追加。再生産を防ぐ。
4. hard能力枠を確認してから各Yardを払出し、Assembly Pへ1件追加。
5. 能力不足なら部材はYard I、要求はpendingに残す。
6. 既存 `_process_node` が全週のI/PとCO/Sを照合しactual_s・次週COを作る。

gateは出荷履行を代行しない。生産済みIDが分かれば再生産を除外できるため、
今回の範囲では共通 `_process_node` を週次関数へ分解する必要はなかった。
予定S・Demand Layerは変更しない。

新診断 `ForwardPlanResult.kitting_capacity_deferred` はready kitの能力待ちを
週別記録する。sealed数への加算やCO追加はしない。GUI/headless KPI schemaへの
公開は今回の対象外で、利用側は必要に応じこのresult属性を読む。

## 再測定

合成fixture、W06要求、3部材Yard。

| 条件 | 修正前 | 修正後 |
|---|---|---|
| 通常1需要 | 完成1・出荷1 | 同じ |
| ECUがW08に遅着 | 期末まで完成0・CO1 | W08に完成1・出荷1、W09 CO0 |
| 期首完成品＋期首CO | 既存品から出荷1 | 同じ |
| 期首完成品＋同ID部材 | 再生産1、在庫収支残差1 | 再生産0、部材各1を保持、残差0 |
| W06に2要求、能力1 | 部材各2消費・完成1・CO同ID2件 | W06完成1、待ち部材各1を保持、W07完成1、W08 CO0 |

MOMのCO期間和は、遅着ケース34→2 lot-週、能力ケース68→1 lot-週。
これは固有注文数ではない。修正後の能力ケースでsealed=0なのは、
完成Pを削る前にgateで待機させたためであり、制約を無視したためではない。

## 検証

### Linuxでの実装時検証

独立Linux worktree、Python 3.12.14、pytest 9.1.1、pandas 3.0.6、
numpy 2.5.3、matplotlib 3.11.2。venvのPython実行ファイルを復元し、
依存バージョン維持・pip check正常を確認。

- 追加10条件＋既存Kittingテスト: 19 passed in 4.19s。
- 追加条件を12条件へ拡張した最終ファイル単独: 12 passed in 0.49s。
  遅着、能力待ち、完成品再生産防止、期首CO、CSV hard能力0/0.1/1、
  soft、旧要求優先、期末、旧kit不足時の新kit処理、完成後の在庫待機を含む。
- CSV Integrationは一時CSVを実capacity loaderでロードしてgateまで検証。
  既存EV/BOM Integrationも実行済み。
- 全体テスト: **452 passed, 1 skipped in 153.13s**。
  全体実行のcollection後に追加した2条件は上記12条件の単独再実行で確認。
  13 goldenすべて成功。skipはGUIテストモジュール全体。
- `git diff --check`: 正常。追跡対象変更はforward_planner.pyのみ。
- 既存全体テストが残したapparelの未追跡push_config.csvは、前回同様に
  作業コピー外へ証跡退避し、納品物に混入させていない。

### Windows適用時のテスト補助関数修正

初回のWindows実行では、テスト補助関数 `setup(qty=1, week=5)` が
テスト実行環境の初期化処理として呼ばれ、qtyへモジュールが渡されたため、
12件がセットアップ段階でエラーになった。WOMの計画処理の失敗ではなく、
納品テストの補助関数名が初期化処理と衝突した問題である。
Windows側のpytest・pluginのバージョン内訳は今回の報告からは未確認。

`tests/test_composite_kitting_recovery.py` の定義と全呼出箇所を
`_build_planned_case(qty=1, week=5)` へ改名した。
検証条件・期待値・エンジンコードには変更を加えていない。
改名後のLinux単独再実行は **12 passed in 0.33s**。

### Windowsでの最終確認（大杉さんの実行ログ・画面報告）

確認日: 2026-09-21（日本時間）。AIによるWindowsでの直接実行ではない。

作業先: `C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m0`。

| 確認項目 | 結果 |
|---|---|
| `python -m pytest tests/test_composite_kitting_recovery.py -q` | 12 passed in 1.65s |
| `python -m pytest -q -rs` | 523 passed, 3 skipped in 354.08s |
| `forward_planner.__file__` | 上記実験用フォルダ内の `wom\engine\forward_planner.py` |
| GUIモデル | `ev-europe-2026`、Planning実行 |
| GUI表示 | Factory_Import_HU、Motor_HU_Yard、Motor_HU、procurement_officeの選択とPSI Chart表示を確認 |

3件のskipは、triangle modeのdrill-down対象なしが1件、leafに下位ノードが
ないケースが2件。LinuxのGUIモジュール全体skipとは区別する。
Windowsのskip表示には旧作業フォルダ `wom-development` のパスが出ていた。
追加のimport確認でエンジンの参照先は実験フォルダと確認できたが、
この確認だけで全テストファイルの参照元を監査したことにはならない。

GUI確認は通常モデルの基本操作・描画に限定する。画像だけでは、遅着時の
同一Lot_ID回復、能力待ち時の部材保存、S系列とactual_sの一致は認定しない。
遅着・保存の挙動は専用テストで検証している。PSI Listタブの内容確認や
全GUI操作の網羅検証を実施したという意味ではない。

今回の追補はテスト補助関数の互換性修正と検証結果の記録であり、
Composite Nodeの業務設計・実装対象範囲は変更しない。
基準時点の設計ドラフト、独立レビュー、baseline測定、測定JSONは
その時点の証跡として維持する。

## 残る範囲と引継ぎ

- push/push_sub、Yard＋非Yard混在、Yard期首在庫、TW Bufferは未改修。
- 同一Lot_IDを複数の独立注文に再利用することは前提外。
- gate外からの重複完成供給を一般的に修復する機能ではない。
- Windows GUIの基本操作・描画は上記の範囲で確認済み。golden正本は更新していない。
- core差分は本AIが自己レビューした。別担当による独立レビューは未実施。
- Windowsへの適用・テストは完了。今回の変更のcommit/push完了報告はまだない。
  オーナーがステージ済み差分をレビューしてからcommit/pushする。

再現スクリプトは元の基準SHAを照合し、変更コードでの実行時には
`--allow-modified-engine` が必要。JSONに変更有無とforward_plannerのblob hashを
記録し、修正前の測定JSONを上書きしない。


````
