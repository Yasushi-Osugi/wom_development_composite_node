# 公開の前の小さな整理：プラグインの組・知らない名前・OI_ の例外　報告

- 依頼書：`requests/RequestLetter_PublicReadiness_Plugins_to_CodeKun.md`
- 実装：Code君（Claude Code, Windows）、2026-10-09
- **着手時の SHA：`7ce980f`**（refactor(rice): retire legacy rice …、作業ツリーは clean）
- **保護対象のコア・golden（canonical 13・legacy 3）・モデルの値（需要・能力・価格）は変えていない。** `planning_config.csv` に足したのは `recommended_plugins` だけ。
- **commit・push はしていない。** 変更・追加のファイルの一覧は §7。
- 付表：`docs/development/public_readiness/`

---

## 0. 受入のまとめ

| ID | 検査 | 結果 |
|---|---|---|
| P-1 | 全サンプルで GUI の既定＝headless（`--plugins` なし）＝golden | **合**（`iphone` を除く。§1.3）。headless は 16 モデルすべてで golden（または明示の safe）と psi・ppc・forward・period・products・プラグインの組が一致。GUI は rice・Cookie・smartx で、読み込んだまま計画した PSI が golden と一致 |
| P-2 | rice を GUI で読み込んで既定のまま計画すると 141,210／95,727、World Map の帯 2027-W01 | **合** |
| P-3 | 知らないプラグイン名で headless・GUI の読み込みが止まり、使える名前が出る | **合**（§2） |
| P-4 | 需要の無い ID が Flow Check・lot_identity_checks で NG（テスト）。全サンプルの NG は 0 | **合**（§3） |
| P-5 | golden（13＋legacy 3）は不変。全テストを単独で実行して緑 | **合**。867 passed／3 skipped、golden の変更 0（§6） |

---

## 1. モデルごとの推奨のプラグインの組

### 1.1 データ

各モデルの `planning_config.csv` に 1 行足した（値に comma があるので `"…"` で囲む。読む側はすべて `csv.DictReader`）：

```
recommended_plugins,"HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
```

| モデル | 組 | 出所 |
|---|---|---|
| Cookie-jp-2026・apparel-global-2028-2029・apparel-us-2026・bom-test-2026・ev-europe-2026・ev-thailand-2026・iphone_global・oil-global-2027・smartx-2027-2029・soysauce-eu-2027・soysauce-jpy-2027・soysauce-us-2027 | Holiday Calendar・Buffering Stock・Capacity Override | golden の組 |
| rice-japan-2027-2028 | 上の 3 つ＋**Rice Seasonal** | golden の組 |
| ev-thailand-2026_update・india-ghee-2026・iphone・soysauce-jpy-2027-alloc | Holiday Calendar・Buffering Stock・Capacity Override | **golden なし**。Owner の決定（2026-10-09）で safe の 3 つ |

- golden の無いモデルについて：依頼書は「今の GUI の既定の組」を書くとしていたが、GUI の既定は**全部 OFF**だった（チェックは `BooleanVar(value=False)` で作られ、前の画面のチェックは手で付けたもの）。空の組だと headless の既定（safe）からも外れ、india-ghee のディワリの需要の倍率などが入らなくなるため、確認のうえ safe の 3 つにした。
- `iphone` には `planning_config.csv` が無かったので、この 1 行だけのファイルを作った（`warmup_lt`・`planning_start` が無いので、助走の生成は前と同じく何もしない）。ほかのモデルの `warmup_lt`・`cpu_size`・`lot_flow_mode` の読み込みと助走の結果は変わらないことを確かめた。
- smartx の Capacity Layer は golden で OFF なので、組に入れていない（既定 OFF のまま）。

### 1.2 GUI と headless

- 名前の検査と組の読み込みは `wom/plugins/selection.py`（新規）の一か所。クラス名（`HolidayCalendarPlugin`）と短い名前（`holiday_calendar`）を受け付ける。
- **GUI**：Load Model Folder のとき、`recommended_plugins` があればプラグインのチェックをその組に合わせる（組に無いものは OFF）。ステータスの行に「推奨のプラグインの組を適用：Holiday Calendar, …」と出す（rice は計画期間の確認の警告の後ろに続けて出す）。読み込んだ後に手で変えられる。キーが無いモデルはチェックを変えない。
  - 前回の「`rice_seasonal_config.csv` があれば Rice Seasonal を ON」の専用の処理は外した（rice の組に Rice Seasonal が入っているので同じ結果になる）。Rice Seasonal を ON にして Rice の設定が無ければ止まる動き（「このモデルには Rice の設定がありません…」）は残した。
- **headless**：`--plugins` を省略すると `recommended_plugins`（キーが無いモデルは `safe`）。使った組の出所を snapshot の `config.plugins_source` に記録する（`"recommended_plugins"` か `"safe"`）。**`--plugins` を指定したときは記録しない**——golden は `--plugins` を明示して作り、`tests/test_golden.py` は config 全体を比べるので、記録を常に足すと golden が変わってしまうため。`--plugins` は今のまま（safe／all／none／名前の列）。
- 組の決定と名前の検査は、`run()` の最初（助走の生成など、ファイルに触れる前）に行う。

### 1.3 P-1：既定＝golden

**headless**（`python -m tools.plugin_defaults_check --out <dir>`、全モデルのコピーを `--plugins` なしで計画）：

| モデル | 比べた相手 | 組の出所 | 一致 |
|---|---|---|---|
| Cookie-jp-2026 | golden | recommended_plugins | ✓ |
| apparel-global-2028-2029 | golden | recommended_plugins | ✓ |
| apparel-us-2026 | golden | recommended_plugins | ✓ |
| bom-test-2026 | golden | recommended_plugins | ✓ |
| ev-europe-2026 | golden | recommended_plugins | ✓ |
| ev-thailand-2026 | golden | recommended_plugins | ✓ |
| ev-thailand-2026_update | 明示の safe（golden なし） | recommended_plugins | ✓ |
| india-ghee-2026 | 明示の safe（golden なし） | recommended_plugins | ✓ |
| iphone | — | — | **計画の後の PPC で止まる**（下記） |
| iphone_global | golden | recommended_plugins | ✓ |
| oil-global-2027 | golden | recommended_plugins | ✓ |
| rice-japan-2027-2028 | golden | recommended_plugins | ✓（Rice Seasonal を含む） |
| smartx-2027-2029 | golden | recommended_plugins | ✓ |
| soysauce-eu-2027 | golden | recommended_plugins | ✓ |
| soysauce-jpy-2027 | golden | recommended_plugins | ✓ |
| soysauce-jpy-2027-alloc | 明示の safe（golden なし） | recommended_plugins | ✓ |
| soysauce-us-2027 | golden | recommended_plugins | ✓ |

「一致」＝psi・ppc・forward・period・products・プラグインの組・lot_flow_mode がすべて同じ（付表 `p1.csv`）。

- **`iphone`**：PPC が「No FX rate found for currency='CNY'」で止まる。前からの既知の事象（旧サンプルの為替表に CNY が無い。golden の対象外、CLAUDE.md の golden の節）。プラグインの組とは関係なく、`--plugins safe` でも同じ。計画そのもの（Flow Check）は最後まで動く（§3）。

**GUI**（`python -m main` と同じ窓、モデルのコピーを読み込み、チェックは読み込みで決まったまま＝`tools/gui_generation_line_check.py --plugins auto`）：

| モデル | 読み込み直後のチェック | 計画の PSI＝golden | 結果 |
|---|---|---|---|
| rice-japan-2027-2028 | Holiday Calendar・Buffering Stock・Capacity Override・Rice Seasonal | **一致** | 当週出荷 **141,210**・注文残 **95,727**、表 2「うち報告期間」130,536・28,558、World Map の帯「報告の開始週 **2027-W01**（vc_config.csv）」（P-2） |
| Cookie-jp-2026 | Holiday Calendar・Buffering Stock・Capacity Override | **一致** | 当週出荷 141,990・注文残 0 |
| smartx-2027-2029 | 同上（Capacity Layer は OFF） | **一致** | 当週出荷 692,464・遅配 16,073・注文残 1,274 |

どれも Run Planning Engine・PPC・Network の図・PSI List（全ノード）が例外なく終わった。付表 `gui/<モデル>/`。

## 2. 知らないプラグイン名で止める（P-3）

- headless：`--plugins` に知らない名前があれば、`run()` の最初（モデルのファイルに触れる前）に `UnknownPluginError` で止まる。例：

  > --plugins: 知らないプラグインの名前があります：HarvestBatchPlugin。使える名前：DemandSmoothingPlugin (demand_smoothing), CapacityOverridePlugin (capacity_override), BufferingStockOptimizerPlugin (buffering_stock_optimizer), HolidayCalendarPlugin (holiday_calendar), CapacityLayerPlugin (capacity_layer), RiceSeasonalPlugin (rice_seasonal)

- 同じ規則：`tools/run_headless_from_folder.py` を経由する道具（`tools/warmup_trial.py`・`lovem_observe.py`・`rice_seasonal_check.py` など、`run()` に `plugins_spec` を渡すもの）と、`_select_plugins` を直接使う `tools/sweep_flags.py`。`recommended_plugins` に知らない名前があっても同じく止まる。
- GUI：`recommended_plugins` に知らない名前があれば、Load Model Folder を止める（モデルを何も適用しない）。エラーの画面に上と同じメッセージ（ファイル名つき）、ステータスの行に「⚠ 読み込みを止めました：…」。確認：Cookie のコピーに `HarvestBatchPlugin` を足して読み込み → 画面にメッセージ、チェックは変わらず、表示中のモデルは前のまま（付表 `gui/p3_gui.json`・`p3_gui.png`）。

## 3. OI_ の例外を外した（P-4）

| 場所 | 前 | 後 |
|---|---|---|
| `wom/engine/flow_check.py`（表 1） | 需要の無い ID を受け取った・持った・出荷したノードの行を「対象外（需要に無い ID）」 | **NG**、理由「需要に無い ID（N 件。例 …）」。ほかの判定（到着差など）の後に重ねて付ける（名前に関係なく、`OI_` でも何でも） |
| `tools/lot_identity_checks.py`（K3） | `OI_` の ID を `rice_harvest_like` として別に数え、「需要に無い ID」に入れない | すべて `ids_without_demand` に数える（`rice_harvest_like` の項目は無くした） |

- 単に例外を外すだけだと、上流から整合して流れてきた需要に無い ID は到着差で NG にならないので、Flow Check では「需要に無い ID」自体を NG の理由にした。
- テスト（`tests/test_public_readiness.py`）：小さな木（1 ID の検算データ＋Rice Seasonal）の玄米倉庫の在庫に、需要に無い ID（`OI_…` と `STRAY-LOT-1` の 2 通り）を入れると、Flow Check の行が NG・理由にその ID。`lot_identity_checks` の K3 の `ids_without_demand` が 1 増える。
- 全サンプル（17 モデル、各モデルの既定の組で計画）の Flow Check：**NG 0、「需要に無い ID」の行 0**（付表 `p4_flow_check.json`）。「対象外」の行（bom-test 1・ev-europe 2・ev-thailand_update 1）は前からの Kitting・P のコピーの行で、今回の変更とは関係ない。

## 4. テスト

`tests/test_public_readiness.py`（新規 24 件）：

| テスト | 内容 |
|---|---|
| `test_every_sample_model_recommends_its_golden_plugins`（17） | 各モデルの `recommended_plugins`＝golden の組（golden の無いモデルは safe） |
| `test_headless_without_plugins_uses_the_recommended_set_and_records_it` | `--plugins` なし＝推奨の組、`plugins_source` を記録。明示なら記録しない。キーが無いモデルは safe |
| `test_unknown_plugin_name_stops_with_the_valid_names` | 知らない名前で止まり、使える名前が出る。短い名前も受け付ける |
| `test_unknown_name_stops_the_headless_run_before_the_model_is_touched` | 止まったとき、モデルのファイルは触られていない |
| `test_unknown_name_in_recommended_plugins_stops` | `recommended_plugins` の知らない名前で止まる |
| `test_id_without_demand_is_ng_in_flow_check`（2） | §3 |
| `test_id_without_demand_is_counted_by_lot_identity_checks` | §3 |

## 5. 文書

- **CLAUDE.md**：プラグインの節に「モデルごとの推奨のプラグインの組」（GUI・headless の動き、golden の無いモデル、知らない名前で止まること）。golden の作り直しの手順を、各モデルの `recommended_plugins` を `--plugins` に明示して渡す形に（省略すると config に `plugins_source` が入り golden と合わなくなる注意）。Rice の節の GUI の自動 ON の記述を、推奨の組に置き換えた。
- **`tests/test_golden.py`・`tools/run_headless_from_folder.py`** の説明：上と同じ。
- **`data/sample/rice-japan-2027-2028/README.md`**：推奨のプラグインの組と、GUI・headless での使われ方。ほかのモデルの README には推奨の組の記述が無かったので触っていない。
- `docs/WOM_Start_Here.md` は触っていない（Claude 君が直す）。

## 6. 全テスト

- `python -m pytest tests/ -q -p no:cacheprovider` を単独で実行して **867 passed／3 skipped、失敗 0**（2026-10-09、15 分 46 秒）。canonical golden 13 件・legacy 3 件はすべて緑で、`tests/golden/` に変更は無い（golden は作り直していない）。保護対象のコアにも変更は無い。

## 7. 変更・追加のファイル（削除は無し）

### 追加

```
wom/plugins/selection.py
tools/plugin_defaults_check.py
tests/test_public_readiness.py
data/sample/iphone/planning_config.csv
docs/development/WOM_PublicReadiness_Plugins_Report.md
docs/development/public_readiness/ （付表・画像）
```

### 変更

```
data/sample/*/planning_config.csv（16 モデル、recommended_plugins の 1 行）
  Cookie-jp-2026, apparel-global-2028-2029, apparel-us-2026, bom-test-2026, ev-europe-2026,
  ev-thailand-2026, ev-thailand-2026_update, india-ghee-2026, iphone_global, oil-global-2027,
  rice-japan-2027-2028, smartx-2027-2029, soysauce-eu-2027, soysauce-jpy-2027,
  soysauce-jpy-2027-alloc, soysauce-us-2027
data/sample/rice-japan-2027-2028/README.md
wom/gui/app.py（Load Model Folder：推奨の組の適用・知らない名前で止める。Rice 専用の自動 ON を外した）
wom/engine/flow_check.py（需要に無い ID を NG）
tools/run_headless_from_folder.py（--plugins の既定・名前の検査・plugins_source）
tools/lot_identity_checks.py（OI_ の分岐を外した）
tools/gui_generation_line_check.py（--plugins auto、golden との PSI の比較）
tests/test_golden.py（説明）
CLAUDE.md
```

（`requests/RequestLetter_PublicReadiness_Plugins_to_CodeKun.md` は Claude 君の依頼書）
