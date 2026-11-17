---
handoff:
  case_id: MONEYBASE-003
  task_id: smartx-cost-fix-and-unused-rule-warning
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  start_commit: 64372f0        # 着手時（2026-11-15 21:28、2026-11-17 08:38 に再開）
  request: requests/RequestLetter_MoneyBase_Smartx_CostFix_to_CodeKun.md
  acceptance:
    S1: pass   # 順 1・2 の後、16 モデルの snapshot が golden と同じ。警告の一覧が調査と行ごとに一致
    S2: pass   # 順 3 の後、golden が変わったのは smartx の ppc の塊だけ（5 行）
    S3: pass   # §4 の 1〜4、粗利率 47.0%
    S4: pass   # smartx の「鍵が合わない、または読まない場所」0（引かれなかった行 0、0 の行 0）
    S5: pass   # 新しいテスト 8 件、smoke 507、--full 1,250 passed・3 skipped・失敗 0
    S6: pass
  stop_reasons: []
  open_items: []
  next: owner
---

# 報告書：smartx の金額を直す（運賃・関税の付け替え、原価を完成品の仕入値で持つ）と、引かれなかった規則の行の警告

- 依頼書：`requests/RequestLetter_MoneyBase_Smartx_CostFix_to_CodeKun.md`（v0.1）
- 作業：Code君（Claude Code、Windows）、2026-11-15〜17
- 着手時の SHA：`64372f0`
- 付録：`docs/development/WOM_MoneyBase_Smartx_CostFix_appendix/`
- 作業の出力（git の対象外）：`output/moneybase_costfix/`

## 一言で

**smartx の粗利率は 90.4% から 47.0% になりました。** 原価を組立工場での完成品の仕入値（320〜490 USD）で持つようにし、運賃と関税を物理の区間に付け替え、DC のノードの運賃を消しました。費用は 6,750 万 → 3 億 7,134 万 USD、関税は 256 万 → 4,175 万 USD（移転価格が仕入値に連れて上がったため）。変わったのは smartx の golden の `ppc` の 5 行だけで、計画の結果は 1 バイトも変わっていません。

あわせて、PPC が「一度も引かれなかった規則の行」を実行の後に `ppc_warnings.csv` へ一覧で出すようにしました（止めない、`trust_event_count` に数えない）。16 モデルで回した一覧は、2 日前の調査と行ごとに一致しました。直した後の smartx は 0 件です。

## 1. 順 1：apparel-us・ev 3 モデルの読まれない行を消す（採否 4）

調査の G2（工場のノードに置いた仕入値。PPC は leaf_in の仕入値だけ読む。同じ額は部材＋組立費で計上済み）の 22 行を `ppc_supplier_cost.csv` から消した（付録 `a_removed_supplier_rows.csv`）：

| モデル | 消した行 |
|---|---|
| apparel-us-2026 | `Factory_Import_CN`（19.0 USD）× 8 製品、`Factory_Local_ES`（17.0 USD）× 8 製品 ＝ 16 行 |
| ev-europe-2026 | `Factory_Local_DE` 19,900 EUR、`Factory_Import_HU` 14,900 EUR |
| ev-thailand-2026・ev-thailand-2026_update | `Factory_Local_TH` 780,000 THB、`Factory_Import_CN` 950,000 THB（各 2 行） |

## 2. 順 2：引かれなかった規則の行の警告（採否 5）

| 項目 | 作ったもの |
|---|---|
| 置き場 | `wom/ppc/ppc_unused_rules.py`（新規）。`wom/ppc/ppc_runner.py` が PPC の後に呼ぶ |
| 判定 | 読み込んだ規則の行のうち、**PPC の明細（PPCEvent）に一度も計上されなかった行**。鍵は調査と同じ（区間の費用 `edge_id × product_id × cost_type`、関税 `edge_id × product_id`、ノードの費用 `node_id × product_id × cost_type`、仕入値・市場価格・移転価格はノード × 製品） |
| 出力 | `ppc_warnings.csv` に 1 行ずつ（種類 `unused_rule_row`、場所 `ファイル:行番号 鍵`、理由と額）。率も額も 0 の行は `unused_rule_row_zero`。件数は `ppc_kpi_summary.json` の `unused_rule_rows`（`count`・`zero_count`・`by_reason`） |
| 理由 | `ppc_unused_edge`（`<leaf>->CONSUMER`：Value Chain だけの区間）／`no_shipment`（その製品、またはその行の先の市場に売上の明細が無い）／`key_or_place`（それ以外） |
| 止めない | 警告だけ。`trust_events` に入れない。snapshot（golden）が読む KPI の鍵は変えていない |
| 共有の規則 | 共有の規則から読んだファイルは、そのモデルの製品の行だけを対象にする |

**依頼書との違い（判断）**：依頼書は「引き当てで、引いた鍵を記録する（`lookup_log` と同じ作り）」としていたが、**検索したかどうかではなく、明細に計上されたかで判定した**。規則を検索しても、額 0 の行（区間の運賃 0 は明細を作らない）や、その場所では使わない費目の行（入荷の区間では `logistics_cost` だけを使う、など）は計上されないので、検索の記録では「使われた」と誤って数えるため。結果は調査（明細と突き合わせた方法）と行ごとに同じ。

確かめ（付録 `warnings_vs_survey_run1.csv`）：16 モデルを golden と同じプラグインの組で回した。

- **16 モデルとも snapshot が golden と同じ**（順 1 の行の削除と警告の追加で、金額も計画も変わらない）。
- 警告の一覧が、調査の「引かれていない行」（順 1 で消した 22 行を除く）・「0 の行で引かれていない行」と**行番号まで一致**：cosmetics 2（`ppc_unused_edge`）＋ 0 の行 6、smartphone 38（`key_or_place`）、smartx 22（`key_or_place`）＋ 0 の行 4、soysauce-us 12（`no_shipment`）。ほかの 12 モデルは 0。

## 3. 順 3：smartx の原価と、運賃・関税（採否 2・1）

### 3.1 PPC に足したもの（C）

- **原価の持ち方の表** `ppc_cost_basis.csv`（任意。モデルのフォルダ。無ければ全製品が今のまま）：`product_id`・`cost_basis`（`parts`／`finished_goods`）・`purchase_node`。
- `finished_goods` の製品：`ppc_supplier_cost.csv` の（`purchase_node`、製品）の仕入値を、そのノードの `supplier_cost`（`EXW`）として 1 回だけ計上し、leaf_in からの積み上げ（部材の仕入値、入荷の区間、途中の工場の費用）と `purchase_node` 自身のノードの費用は計上しない。`purchase_node` から先（出荷の区間、DC、関税、市場）と移転価格の規則は今のまま（`wom/ppc/ppc_forward.py`、`ppc_engine.py` が渡すだけ）。
- 止める条件（`wom/ppc/ppc_runner.py` の `PPCCostBasisError`）：列が足りない、製品の重複、計画の木に無い製品、`cost_basis` が 2 つの値以外、`finished_goods` に `purchase_node` が無い、`parts` に `purchase_node` がある、`purchase_node` がその製品の最後の工場でない、その仕入値の行が無い（0 として計算しない）。

### 3.2 smartx のデータ（C・D）

付録 `smartx_changed_rows.csv`（全行と理由）、変更の道具 `smartx_data_fix.py`。

| ファイル | 変更 |
|---|---|
| `ppc_cost_basis.csv`（新規） | 4 製品を `finished_goods`：SmartX → `AssemblyCN_g1`、SmartXNext → `AssemblyCN_g3`、SmartXPro_CN → `AssemblyCN`、SmartXPro_IN → `AssemblyIN` |
| `ppc_supplier_cost.csv` | 7 行を削除：部材（`WaferFab_TW`・`_g1`・`_g3`、`SensorIN`）と台湾の工場（`FoundryTW`・`_g1`・`_g3`）。残るのは組立工場の 4 行（320／490／450／470 USD） |
| `ppc_node_cost_rule.csv` | 23 行を削除：台湾の工場と組立工場の加工費・入荷の運賃（14 行）、9 つの DC のノードの運賃（9 行）。残るのは DC の作業費 9 行 |
| `ppc_transfer_price_rule.csv` | 台湾の工場の移転価格 3 行を削除。残るのは組立工場の 4 行（cost_plus 10%、SmartXPro_IN 8%） |
| `ppc_edge_cost_rule.csv` | SmartX・SmartXNext の supply point 経由の 8 行を削除し、12 行を追加：組立工場 → DC（16.1／18.2／13.3、17.9／20.8／15.3）、DC → 市場（0.9、1.2）。Pro と同じ書き方 |
| `ppc_tariff_rule.csv` | SmartX・SmartXNext の supply point 経由の 8 行を削除し、12 行を追加：組立工場 → DC（米州 25%・欧州 7.5%・APAC 0%）、DC → 市場（0%） |

### 3.3 golden

smartx だけ作り直した（プラグインは `recommended_plugins` を明示）。差分は `ppc` の塊の 5 行だけ。`psi`・`backward`・`forward`・`period`・`products`・`config`・`case` はバイト単位で同じ（付録 `golden_smartx_before.json`・`golden_smartx_after.json`）。

| | 前 | 後 |
|---|---:|---:|
| 売上（USD） | 700,825,463.00 | 700,825,463.00 |
| 費用 | 67,503,725.76 | **371,343,704.70** |
| 粗利 | 633,321,737.24 | 329,481,758.30 |
| 粗利率 | 90.37% | **47.01%** |
| 関税 | 2,558,419.56 | **41,751,951.30** |
| trust_event_count | 207 | **566** |
| 組立工場の利益（mom_profit） | 4,805,173.07 | 30,325,245.60 |

`trust_event_count` が増えたのは、すべて `TARIFF_SHOCK`（関税が移転価格の 20% を超える）：米州向け 25% の区間を、前は SmartXPro_IN（207 lot）だけが引いていたが、SmartX（235 lot）と SmartXNext（124 lot）も引くようになった（207 ＋ 235 ＋ 124 ＝ 566）。

## 4. §4 の確かめ

### 4.1 原価の筋（1 台あたり、付録 `s4_1_cost_per_unit.csv`）

| 製品・市場 | 仕入値 | 運賃 | DC の作業費 | 関税 | **PPC の原価** | マスタの小売の原価 | 売価 | 粗利率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SmartX・米州 | 320.0 | 17.0 | 4.8 | 88.00 | **429.80** | 460 | 699 | 38.5% |
| SmartX・欧州 | 320.0 | 19.1 | 5.2 | 26.40 | **370.70** | 480 | 799 | 53.6% |
| SmartX・APAC | 320.0 | 14.2 | 4.2 | 0 | **338.40** | 440 | 649 | 47.9% |
| SmartXNext・米州 | 490.0 | 19.1 | 5.2 | 134.75 | **649.05** | 670 | 1,099 | 40.9% |
| SmartXNext・欧州 | 490.0 | 22.0 | 5.8 | 40.42 | **558.22** | 700 | 1,199 | 53.4% |
| SmartXNext・APAC | 490.0 | 16.5 | 4.8 | 0 | **511.30** | 640 | 1,049 | 51.3% |
| SmartXPro_CN・欧州 | 450.0 | 20.7 | 5.5 | 37.12 | **513.33** | 640 | 1,099 | 53.3% |
| SmartXPro_CN・APAC | 450.0 | 15.3 | 4.5 | 0 | **469.80** | 600 | 949 | 50.5% |
| SmartXPro_IN・米州 | 470.0 | 17.0 | 5.0 | 126.90 | **618.90** | 620 | 999 | 38.0% |

- 依頼書のとおり一致は求めない。PPC の原価はマスタの小売の原価より 1〜130 USD 低い。マスタの小売の原価は、PPC に無い DC・販社の利幅や関税の前提（どの国の税率か）を含むと読める。差が小さいのは関税 25% の米州（Pro_IN 1 USD、SmartXNext 21 USD）、大きいのは関税の無い APAC・低い欧州（100〜130 USD）で、マスタの小売の原価が関税の差を区別していないことと合う（読み方。マスタの作り方の記録は無い）。
- 運賃の列は、組立工場 → DC と DC → 市場の区間の合計（例：SmartX・米州 16.1 ＋ 0.9）。

### 4.2 粗利率

**47.01%**。依頼書の目安（45〜50%）の中。

### 4.3 関税（付録 `s4_3_tariff_by_edge.csv`・`s4_3_tariff_representative_lots.csv`）

- 関税の明細 **すべての行で、関税 ＝ 移転価格 × 税率**（1 lot あたり。移転価格は SmartX 352・SmartXNext 539・Pro_CN 495・Pro_IN 507.6 USD ＝ 仕入値 × 1.1／1.08）。
- 区間ごとの合計：SmartX 米州 5,249,992.0、欧州 1,102,305.6、SmartXNext 米州 15,770,331.5、欧州 3,307,411.8、Pro_CN 欧州 2,774,574.0、Pro_IN 米州 13,547,336.4、APAC と DC → 市場は 0。計 41,751,951.3 USD。
- 調査 §3.1 の見込み（＋408 万 USD）より大きいのは、見込みが前の移転価格（約 60〜84 USD）で計算していたため（依頼書の §4 の 3 のとおり）。

### 4.4 運賃の差し引き（付録 `s4_checks.json`）

| | 額（USD） | 調査 §3.1 |
|---|---:|---:|
| 区間の運賃の増（SmartX 2,489,498.8・SmartXNext 5,580,361.4） | ＋8,069,860.20 | ＋8,069,860.20（一致） |
| DC のノードの運賃の削除（SmartX・SmartXNext 4,431,541.5、Pro 2,647,672.0） | −7,079,213.50 | −4,431,541.5 − 2,647,672（一致） |
| 台湾の工場・組立工場のノードの運賃の削除（仕入値に含まれる） | −4,953,344.50 | （調査の範囲外。C で消えた分） |
| 残ったノードの運賃 | 0 | |

### 4.5 計画と、ほかのモデル

- smartx の計画の結果は変わらない（§3.3）。
- ほかの 15 モデル：順 1・2 の後の 16 モデルの実行で snapshot が golden と同じ。順 3 は smartx のデータと、`ppc_cost_basis.csv` の無いモデルでは何もしない PPC の分岐だけ。`--full`（golden の全モデル）が通った（§6）。

## 5. 順 4・5

- **順 4**：直した後の smartx の警告は `unused_rule_row` 0、`unused_rule_row_zero` 0（`ppc_warnings.csv` に残るのは、前からある `price_before_first_rule_week` 4 行だけ。付録 `smartx_ppc_warnings_after.csv`）。
- **順 5**：`data/sample/smartphone-global-2026-2029/README.md` に PPC の限界（固定の経路、DC の作業費が計上されない、米州の Phone16 は中国組立・中国発の関税、38 行が警告に出る、木の経路で見るなら smartx）を、`data/sample/smartx-2027-2029/README.md` に新しい原価の持ち方と金額を書き足した。過去の報告書の数字は書き換えていない（記録として残す）。

## 6. テスト

- `tests/test_ppc_cost_basis.py`（新規、5 件）：表が無ければ今のまま（bom-test の golden と同じ）、`finished_goods` で仕入値だけを計上し部材・工場の費用を計上しない・移転価格は仕入値 × 1.1・DC の運賃と売上は今のまま・使わなくなった 4 行が警告に出る、`purchase_node` が最後の工場でなければ止まる、仕入値の行が無ければ止まる、表の検査。
- `tests/test_ppc_unused_rule_rows.py`（新規、3 件）：理由の区別（鍵が合わない・実出荷なし・PPC が使わない区間）と 0 の行の種類、共有の規則はそのモデルの製品だけ、smartphone で警告 38 件・`trust_event_count` と `ppc` は golden のまま。
- `tests/conftest.py` の領域の表に 2 行（`ppc`）。
- 実行結果：

| 段 | 結果 |
|---|---|
| 新しいテスト 2 ファイルと、警告に関わる前のテスト（`test_stage_d_part0.py`・`test_ppc_no_silent_fallback.py`） | 36 passed |
| `quick_check --smoke` | **507 passed・失敗 0（110 秒）** |
| `quick_check --full`（golden の全モデルを含む） | **1,250 passed・3 skipped・失敗 0（1,356 秒）** |

付録 `qc_smoke.log`・`qc_full.log`。

## 7. golden の差分を大杉さんが確かめる手順

1. 差分を見る（`ppc` の 5 行だけのはず）：
   ```
   git diff tests/golden/smartx-2027-2029.json
   ```
2. ほかの golden が変わっていないこと：
   ```
   git status tests/golden
   ```
   （`smartx-2027-2029.json` だけが変更）
3. 作り直しの再現（同じ値が出る）：
   ```
   python -m tools.run_headless_from_folder --model-dir data\sample\smartx-2027-2029 --plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin --out output\smartx_check.json --quiet
   ```
   表示の `GM=47.0% trust=566`、`output\smartx_check.json` と golden が同じ。
4. golden のテスト：
   ```
   python -m tools.quick_check --golden smartx-2027-2029
   ```

## 8. 申し送り

1. 警告の判定は、検索の記録ではなく明細で行った（§2 の「依頼書との違い」）。
2. `ppc_cost_basis.csv` は GENERIC の経路（計画の木から工場を見つける経路）で使える。名前付きの固定の経路（rice・cookie・smartphone）では、最後の工場が固定の値なので、そのモデルに表を置くときは `purchase_node` をその値にする（今は置いているモデルが無い）。
3. smartx の `ppc_supplier_cost.csv` の仕入値は 2027-W01 からの 1 行なので、2026 年の lot は「最初の行より前の週」として最初の行の値で評価される（前からある `price_before_first_rule_week` の警告。値は変わらない）。
4. マスタ（`node_cost_master.csv`）の部材・台湾の工場の行は残している（PPC は読まない。PPC 以外の道具が読むため。範囲の外）。
5. 依頼書の「範囲」にある 5 モデル以外のサンプル・golden は変えていない。保護対象のコア・Value Chain も変えていない。

## 9. 大杉さんに決めてほしいこと

| # | 一言で | 中身 | 推奨 |
|---|---|---|---|
| D1 | smartx の新しい金額を採る | 粗利率 47.0%、関税 4,175 万 USD、trust event 566。golden の差分は §7 | **採る** |
| D2 | 警告を画面に出すか | 今は `ppc_warnings.csv` と `ppc_kpi_summary.json` だけ。コックピット・9 タブの画面には出していない | 今は出さない。次に金額を見る画面を作るときに、件数と理由を ④ の注意に出す |
| D3 | smartx のマスタの小売の原価 | PPC の原価と 1〜130 USD 違う（§4.1）。マスタの作り方の記録が無い | 今は直さない。マスタを読む機能を見直すときに |

## 10. 記録

- 時刻：始め 2026-11-15 21:28、中断の後 2026-11-17 08:38 に再開、終わり 09:20 ごろ（Windows の時計）。
- 人の橋渡し：中断の後の「もう一度試してください」。
- 再利用した知識：引かれていない規則の行の調査（`8bcb622`、smartx の対応表、警告の案）、smartx の運賃の調査（`b7a2ed1`）、PPC の作り（`ppc_forward.py` の Step 1a〜1c、`ppc_tariff.py`、`ppc_runner.py`、`ppc_rules.py`）、golden の作り直しの作法（CLAUDE.md）。
- 迷った所・足りなかった情報：
  1. 警告の「引いた」の意味（検索か計上か）。計上にした（§2）。
  2. 関税の DC → 市場の区間：Pro の書き方（0% の行を置く）にそろえた。組立工場 → supply point の 0% の行は置かない（Pro の移行と同じ）。
  3. 依頼書の §4 の 1 の「マスタの小売の原価」との差の理由は、マスタの作り方の記録が無いので読み方として書いた。
