---
handoff:
  case_id: MONEYBASE-003
  task_id: smartx-cost-fix-and-unused-rule-warning
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "449e5c2 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 引かれていない規則の行の調査（Code君）
      version: "8bcb622（2026-11-15）"
      applicability: "§2 の 6 つの群、§3.1 smartx の対応表（付録 smartx_fix_plan.csv）、§4 の警告の案、§6 の D1〜D6"
    - id: smartx の運賃の調査（Code君）
      version: "b7a2ed1"
      applicability: "ノードと区間の運賃の二重、SKU 分割の移行（55ae30c）の経緯"
    - id: Claude君の検証
      version: "このチャットの記録（2026-11-15）"
      applicability: "smartx の node_cost_master.csv は組立の原価を 320／450／490 USD／lot と書いていて、ppc_supplier_cost.csv と同じ。小売の原価 460 に対し売価 699（粗利 34%）。golden の ppc に trust_event_count（207）がある"
  acceptance:
    ref: "この依頼書 §6"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：smartx の金額を直す（運賃・関税の付け替え、原価を完成品の仕入値で持つ）と、引かれなかった規則の行の警告

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-15）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 経営コックピットの段 3 は commit 済み（`449e5c2`）。到達点 3 は通過
- 範囲：`wom/ppc/`（§2 の C・D の所だけ）、`data/sample/smartx-2027-2029/`、`data/sample/apparel-us-2026/`・`ev-europe-2026/`・`ev-thailand-2026/`・`ev-thailand-2026_update/` の `ppc_supplier_cost.csv` の行の削除、`data/sample/smartphone-global-2026-2029/README.md` の追記、`tests/golden/smartx-2027-2029.json` の作り直し、テスト、報告書。**保護対象のコア（計画のエンジン）・Value Chain・ほかのサンプルと golden は変えない**
- Python は `C:\Users\ohsug\anaconda3\python.exe` を明示。`quick_check` の出力をファイルへ流すときは `PYTHONIOENCODING=utf-8`
- **§3 の順番で進める**。golden が変わるのは smartx だけで、それは最後の 1 回だけ

---

## 一言で

**smartx の PPC は、組立の仕入値（320〜490 USD）を読まずに、ウェーハと加工費だけで原価を作っているので、粗利率が 90.4% という、ありえない値になっています。完成品の仕入値で原価を持つ形に直し、あわせて運賃・関税を区間に付け替えてください。ほかのモデルの金額は変えずに、「一度も引かれなかった規則の行」を実行の後に一覧で出す警告も足してください。**

## 0. 大杉さんの判断（2026-11-15、5 件とも推奨どおり採用）

| # | 一言で | 推奨 | 採否 |
|---|---|---|---|
| 1 | smartx の運賃と関税を区間に付け替え、DC のノードの運賃を消す（調査の D1） | 直す（調査 §3.1 の対応表のとおり） | 採用 |
| 2 | smartx の原価を、組立工場での完成品の仕入値で持つ（調査の D2） | 直す。**どの製品を完成品の仕入値で持つかは、新しい小さな表で明示する**（§2 C。表が無い製品とモデルは今のまま） | 採用 |
| 3 | smartphone の固定の経路は直さない（調査の D3） | 直さない。README に限界を書き足すだけ | 採用 |
| 4 | apparel-us・ev 3 モデルの、読まれていない工場の仕入値の行を消す（調査の D4） | 消す。金額も golden も変わらない | 採用 |
| 5 | PPC に「一度も引かれなかった規則の行」の警告を足す（調査の D5） | 足す。**`trust_event_count` には数えない**（golden を守るため） | 採用 |

## 1. 分かっていること

| # | 事実 | 根拠 |
|---|---|---|
| F1 | smartx の golden の `ppc`：`cost_base 67,503,725.76`・`revenue_base 700,825,463`・`gross_margin_pct 0.90368`・`tariff_base 2,558,419.56`・`trust_event_count 207` | `tests/golden/smartx-2027-2029.json` |
| F2 | PPC は仕入値を、製品の leaf_in（部材の供給元）のノードでだけ読む（`ppc_forward.py` Step 1a）。smartx の組立工場の仕入値 7 行（AssemblyCN 450・AssemblyIN 470・AssemblyCN_g1 320・AssemblyCN_g3 490、FoundryTW 38・_g1 28・_g3 42）は一度も読まれない | 調査 §2 の G2、`ppc_forward.py` |
| F3 | smartx の `node_cost_master.csv` は、組立の原価を 320／490 USD／lot（`AssemblyCN_g1`・`AssemblyCN_g3`）と書いていて、`ppc_supplier_cost.csv` と同じ値。小売の原価 460 に対し売価 699（粗利 34%）。**同じサンプルの中で、PPC だけが合っていない** | Claude君の検証 |
| F4 | 組立工場の移転価格は原価に 10% を乗せる形（`cost_plus`）。原価が変われば移転価格も、それに掛かる関税も変わる | `ppc_transfer_price_rule.csv` |
| F5 | SmartX・SmartXNext の区間の運賃・関税 12 行は鍵が supply point 経由で引かれない。付け替えの対応表は調査の付録 `smartx_fix_plan.csv` | 調査 §3.1 |
| F6 | `trust_event_count` は Step 6 の突き合わせ（`ppc_reconcile.py`）から作られ、規則の引き当てとは別。golden の `ppc` に入っている | `ppc_kpi.py`、golden |
| F7 | apparel-us の 16 行、ev-europe・ev-thailand・ev-thailand_update の各 2 行は工場のノードの仕入値で読まれない。同じ額は部材＋組立費で計上済み（足すと二重） | 調査 §2 の G2、付録 `q3_mom_supplier_rows.csv` |
| F8 | smartx の PPC の金額を検査するテストは無い。今の値を記録している文書が 7 つある | 調査 §3.2 |

## 2. 直すこと

### A. apparel-us・ev 3 モデルの読まれない行を消す（採否 4）

付録 `unapplied_rows.csv` の G2 のうち、apparel-us の 16 行と ev 3 モデルの 6 行を `ppc_supplier_cost.csv` から消す。**16 モデルの golden が変わらないこと**を確かめる。

### B. 引かれなかった規則の行の警告（採否 5）

| 項目 | 中身 |
|---|---|
| 記録 | `ppc_rules.py` の引き当て（区間の費用・関税・ノードの費用・移転価格・仕入値・市場価格）で、引いた鍵を記録する（今の `lookup_log` と同じ作り） |
| 出力 | 実行の後、読み込んだ行のうち一度も引かれなかった行を `ppc_warnings.csv` に 1 行ずつ（種類 `unused_rule_row`、ファイル、行番号、鍵、額）、件数を `ppc_kpi_summary.json` に別の鍵で。0 の行（率も額も 0）は別の種類で数える |
| 理由の区別 | その製品 × 市場に実出荷が無いもの（「実出荷なし」）と、PPC が作らない形の区間（`<leaf>->CONSUMER` など。「PPC が使わない区間」）を分けて出す。それ以外は「鍵が合わない、または読まない場所」 |
| 止めない | 警告だけ（R12 の作法）。**`trust_events` に入れない、`trust_event_count` を変えない** |
| 共有の規則 | 共有の規則（`data/ppc`）から読んだ行は、そのモデルの製品の行だけを対象にする（調査 §1 と同じ） |

確かめ：16 モデルで回し、警告の一覧が調査の結果（A で消した行を除く）と一致すること。**16 モデルの golden が変わらないこと**。

### C. smartx の原価を完成品の仕入値で持つ（採否 2）

**原価の持ち方の表**（新しい任意のファイル `ppc_cost_basis.csv`。無ければ全製品が今のまま）：

| 列 | 中身 |
|---|---|
| `product_id` | 製品 |
| `cost_basis` | `parts`（今のまま：leaf_in の仕入値から積み上げる）か `finished_goods`（完成品の仕入値） |
| `purchase_node` | `finished_goods` のとき、仕入値を読むノード。**その製品の最後の工場（m_node）でなければ止める** |

`finished_goods` の製品で PPC がすること：

1. `ppc_supplier_cost.csv` の（`purchase_node`、製品）の仕入値を、そのノードの `supplier_cost`（`EXW`）として 1 回計上する。行が無ければ止める（黙って 0 にしない。R4）。
2. leaf_in からの積み上げ（Step 1a の部材の仕入値、Step 1b の入荷の区間と途中の工場の費用）と、`purchase_node` 自身のノードの費用（加工費・入荷の運賃）は**計上しない**（仕入値に含まれるため）。
3. `purchase_node` から先（出荷の区間、DC、関税、市場）は今のまま。移転価格は今の規則のまま（原価に 10% を乗せる）。

smartx の 4 製品（SmartX・SmartXNext・SmartXPro_CN・SmartXPro_IN）を `finished_goods` にし、`purchase_node` は AssemblyCN_g1・AssemblyCN_g3・AssemblyCN・AssemblyIN。

**仕入値に含まれるので使わなくなる smartx の行は消す**（残すと B の警告に出続けるため）：leaf_in の仕入値（WaferFab_TW・_g1・_g3、SensorIN）、台湾の工場の仕入値（FoundryTW・_g1・_g3）、台湾の工場と組立工場のノードの費用（加工費・入荷の運賃）、台湾の工場の移転価格 3 行。消した行の一覧を報告書に。

### D. smartx の運賃と関税の付け替え（採否 1）

調査の付録 `smartx_fix_plan.csv` のとおり：SmartX・SmartXNext の国際輸送の運賃と関税を「組立工場 → DC」の区間に、国内の 0.9・1.2 を「DC → 市場」の区間に付け替える（Pro と同じ書き方）。9 つの DC のノードの運賃（`logistics_cost`）を消す。

### E. smartphone の README（採否 3）

`data/sample/smartphone-global-2026-2029/README.md` に、PPC の限界を書き足す：PPC は固定の経路（EMS_A_CN → SP_Phone16 → 市場）で計算し、計画の木の DC・台湾の工場・インドの工場を通らない。DC の作業費（費用の約 0.86%）が計上されず、米州の Phone16 は中国組立・中国発の関税で計上される。木の経路で見るなら smartx を使う。

## 3. 進める順番

| 順 | 作業 | golden |
|---|---|---|
| 1 | A（apparel・ev の行を消す） | 16 モデルとも変わらないことを確かめる |
| 2 | B（警告） | 16 モデルとも変わらないことを確かめる。警告の一覧が調査と一致 |
| 3 | C と D を一緒に（smartx の原価と運賃・関税） | **smartx だけ作り直す**。`ppc` の塊以外（`psi`・`backward`・`forward` など計画の結果）が変わったら止める |
| 4 | B の警告を smartx で回し直す | smartx の「鍵が合わない、または読まない場所」が 0 になること |
| 5 | E（smartphone の README）、smartx の README の金額の記述 | 変わらない |

## 4. 期待する値と、確かめ方

1. **smartx の原価の筋**：製品ごとに、PPC の 1 lot あたりの原価（仕入値＋出荷の運賃＋関税＋DC・市場の費用）を出し、`node_cost_master.csv` の小売の原価（例：SmartX の Retail_AMER_g1 460 USD）と並べる。**一致は求めない**（マスタの小売の原価には DC の利幅などが入る）。差の理由を書く。
2. **粗利率の目安**：Claude君の概算で 45〜50%。この範囲を大きく外れたら（例えば 35% を下回る、60% を上回る）、止めて理由を調べる。
3. **関税**：移転価格が仕入値に連れて上がるので、関税は調査 §3.1 の ＋408 万 USD（今の移転価格で計算）よりずっと大きくなる。製品 × 区間ごとに、関税 ＝ 移転価格 × 税率 × 物量 になっていることを、代表の lot で確かめる。
4. **運賃の差し引き**：区間の運賃が増え、DC のノードの運賃が消える。調査 §3.1 の額と照合する。
5. **計画は変わらない**：smartx の golden で、`ppc` の塊以外がバイト単位で同じ。
6. **ほかの 15 モデル**：golden が変わらない。

## 5. テスト

- `tests/test_ppc_cost_basis.py`（新規）：表が無ければ今のままの明細、`finished_goods` で積み上げと `purchase_node` のノードの費用を計上しない、`purchase_node` が最後の工場でなければ止める、仕入値の行が無ければ止める、出荷側と移転価格は今のまま。小さな合成のモデルで。
- `tests/test_ppc_unused_rule_rows.py`（新規）：引かれなかった行が警告に出る、0 の行は別の種類、「実出荷なし」「PPC が使わない区間」の区別、`trust_event_count` が変わらない。
- `quick_check --smoke`、領域（`ppc`）、**`--full`**（golden の全モデル。PPC を変えるため）。

## 6. 合格の条件

| # | 条件 |
|---|---|
| S1 | 順 1・2 の後、16 モデルの golden が変わらない。警告の一覧が調査の結果と一致 |
| S2 | 順 3 の後、golden が変わったのは smartx の `ppc` の塊だけ |
| S3 | §4 の 1〜4 を報告書に表で示す。粗利率が §4 の 2 の範囲 |
| S4 | smartx で、「鍵が合わない、または読まない場所」の警告が 0 |
| S5 | §5 のテストと `--full` が通る |
| S6 | 消した行・付け替えた行・新しいファイルの一覧を報告書に |

**止める理由**：smartx の計画の結果が変わる、ほかのモデルの golden が変わる、粗利率が §4 の 2 の範囲を大きく外れる、`ppc_cost_basis.csv` の作りでは表せない製品が出た（変えずに報告）。

**止める理由ではないもの**：smartx の `trust_event_count` が変わること（原価と区間が変わるため。変わった理由を書く）。

## 7. しないこと

smartphone の固定の経路を木の経路に直すこと、インド発の関税の規則を作ること、smartx に Value Chain のマスタを足すこと、読み込みの時の形の検査（調査 §4 の案 B）、過去の報告書の数字を書き換えること（記録として残す。smartx の README に新しい値を書く）。

## 8. 報告書と記録

- 報告書：`docs/development/WOM_MoneyBase_Smartx_CostFix_Report.md`、付録。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- 中身：着手時の SHA、順 1〜5 の結果、§4・S1〜S6、smartx の金額の前後（費用・関税・粗利率・`trust_event_count`）、**golden の差分を大杉さんが確かめる手順**、申し送り、大杉さんに決めてほしいこと（一言の決定と中身、推奨）。
- 記録：始めと終わりの時刻、人の橋渡し、再利用した知識、この依頼書で迷った所・足りなかった情報。
- commit メッセージの下書きを、順 1・2（golden が変わらない）と順 3〜5（smartx の golden を作り直す）で分けて 2 つ。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-15 | 初版。§0 の 5 件を大杉さんが推奨どおり採用 |
