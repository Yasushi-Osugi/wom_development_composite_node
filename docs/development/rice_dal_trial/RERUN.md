# Rice DAL Trial — 配置と再実行

基準: `d848c5fa0565d70f6817c1a0257341067712deca`。
本件は新しい試行モデル・測定道具・報告だけです。core・原本rice・goldenを変更するファイルはありません。

## 配置

`WOM_RiceDAL_Trial_Files.zip` の `repo_additions/` にある相対パスをリポジトリへ配置してください。
既に同名のファイルがある場合は、先に差分を確認してください。
このZIPのモデルは試行用です。golden対象への追加や原本riceの置換は行っていません。
`WOM_RiceDAL_Trial_Evidence.zip` は読取り用の測定結果で、リポジトリの入力として使いません。
`WOM_RiceDAL_Trial_LOVEM_Run.zip` は、そのまま使える観測runです。
同ZIPの `output/lovem/rice_dal_trial/run_dal_current/` を任意の作業用リポジトリへ置けます。

## 固定SHAでの再実行

他の実装と混ぜないため、基準SHAの独立checkoutを使ってください。
最新の作業ブランチの上で測定スクリプトを動かすと、SHA照合で停止します。
これは意図した動きです。Stage D第2回のHEADへ強制的に合わせることはしません。

基準checkoutには、最初は **測定道具2本だけ**を `tools/` へ置いてください。
配布済みDALフォルダを先に置くと、`prepare` は上書きを避けて停止します。

依存: Python、pandas、numpy、matplotlib、networkx、pytest（適合確認）、scipy。
今回の実測バージョンは `raw/qualification/environment.json` にあります。
WOM既存の依存が使える環境を用いてください。

Windows cmdでは:

```bat
set PYTHONHASHSEED=0
set MPLBACKEND=Agg
set PYTHONDONTWRITEBYTECODE=1
python -m tools.probe_rice_dal_trial prepare --out output/rice_dal_trial
python -m tools.probe_rice_dal_trial measure --case baseline --out output/rice_dal_trial
python -m tools.probe_rice_dal_trial measure --case legacy_calendar --out output/rice_dal_trial
python -m tools.probe_rice_dal_trial measure --case dal_current --out output/rice_dal_trial
python -m tools.probe_rice_dal_trial prepare-increased --out output/rice_dal_trial
python -m tools.probe_rice_dal_trial measure --case dal_increased --out output/rice_dal_trial
python -m tools.probe_rice_dal_trial measure --case dal_observed --out output/rice_dal_trial
python -m tools.analyze_rice_dal_trial analyze --out output/rice_dal_trial
python -m tools.analyze_rice_dal_trial verify-lovem --out output/rice_dal_trial
python -m tools.analyze_rice_dal_trial validate-raw --out output/rice_dal_trial
```

Linuxでは環境変数を `export PYTHONHASHSEED=0 MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1` で設定し、同じpythonコマンドを使えます。
既に各caseの出力先がある場合、測定道具は上書きせず停止します。別の空の出力先を使ってください。
標準のwarmup処理は複写データ上でだけ走らせ、元CSVのハッシュを前後で確認します。

測定では副作用の無いラッパーでBackward前後、Hook後、Forward結果を保存します。
`dal_observed` は既存LOVEM observerを使い、結果の独立照合はWOMのcheckerを輸入しない別スクリプトで行います。
通常のgolden生成器、World Mapツール、段階D第2回のプログラムは呼びません。

## 関連テスト（Linuxで実行済み）

```sh
python -m pytest tests/test_golden.py -k rice -q
python -m pytest tests/test_lovem_intervals.py tests/test_backward_holiday_carryback.py tests/test_capacity_soft.py tests/test_capacity_soft_backward.py tests/test_holiday_explicit_closure.py -q
```

本件で全体テストやWindowsのGUI試験を実施したとはしていません。

## LOVEM viewer

```sh
python -m wom.lovem.viewer output/lovem/rice_dal_trial/run_dal_current
```

代表ID:

- `Koshihikari:KANSAI:2027-W01:00001`
- `Yumepirika:KANSAI:2027-W01:00001`

大規模なrun（約213 MiB、全10snapshot）なので、Windowsでの全件描画の性能は別途確認が必要です。
今回の独立検査は描画によらず、生データ全件を対象にしています。
runのmanifestは `dirty=true` ですが、coreを修正した意味ではありません。新しい未commitモデルと測定道具を正しく記録したものです。

## データ保全

各ZIPには、そのZIPに入ったファイルの `SHA256SUMS` があります。
報告書の `rice_dal_trial/file_hashes.csv` は測定原本の相対パス・バイト数・SHA-256一覧です。
ZIPを展開してから照合できます。測定CSVの1件にあったgzip欠損の復元履歴は `raw/q1_file_recovery.json` に残しています。
ON/OFFの全結果一致を確認した再測定から同一のQ1データを復元し、最終データのgzip50件は読み切り検査済みです。
