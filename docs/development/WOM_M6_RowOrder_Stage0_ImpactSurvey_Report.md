---
handoff:
  case_id: COCKPIT-M6-003
  task_id: row-order-bias-stage0-impact-survey
  role_from: implement           # Code君
  role_to: owner                 # 大杉さん
  target_commit: "着手時 98f5e1bcfbf5b27bc5aadf0efef8b8b1129d62e9（この報告の commit は大杉さん）"
  knowledge_used:
    - id: 行の順の偏りの直し方の設計
      version: "v0.3"
      applicability: "§1（E1〜E3）・§6 段 0"
    - id: 到達点 6 の報告書
      version: "9c5ba48 ＋ 訂正"
      applicability: "§3 原因の調べ方（r0_probe の包み方）"
  acceptance:
    ref: "依頼書 §5"
    result: "S1〜S4 すべて合格"
  status: "完了（読むだけ）"
  open_items:
    - "段 1（overflow_policy の実装）で、golden を作り直すモデルの範囲は本報告 §4 の 13 モデル（＋legacy の 3）の見込み"
  stop_reasons: []
  next: owner
---

# 報告：行の順の偏りの直し方 — 段 0：golden のどのモデルが変わりうるか

- 依頼書：`requests/RequestLetter_M6_RowOrder_Stage0_ImpactSurvey_to_CodeKun.md`（v0.1、2026-11-18）
- 着手時の SHA：`98f5e1bcfbf5b27bc5aadf0efef8b8b1129d62e9`（branch `wom-v1r6m0_BS-SEAF`）
- 出力：`output/roworder_stage0/`（git の対象外）。付録：`docs/development/WOM_M6_RowOrder_Stage0_ImpactSurvey_appendix/`
  - `candidates.csv`（§1.1）、`measured.csv`（§1.2）、`tables.md`（全行の表）、`measured_json/`（モデルごと・週ごとの明細）、`scripts/`（調査のスクリプト 3 本）

## 1. 一言で

**golden の 16 モデルのうち 13 で、押し戻し（E2・E3）が「市場が 2 つ以上並ぶ週」に働いています。押し戻し方を替えると、この 13 の golden は変わる見込みです。** 変わらない見込みは bom-test・cosmetics・rice の 3 つ。legacy の golden 3 つ（Cookie・ev-thailand・soysauce-jpy）も、すべて変わる見込みです。

調査で回した 19 回の計画は、すべて golden と一致しました（包み方は計画を変えていない）。

## 2. 合格の条件

| # | 条件 | 結果 |
|---|---|---|
| S1 | 16 モデルすべてで §1.1 の候補を表にした | **合格**。工場 51（モデル × 製品 × 工場）、候補 47（付録 `candidates.csv`、§3.1） |
| S2 | §1.2 の実測を表にした | **合格**。16 モデルすべて回せた（rice も 38 秒）。legacy の golden 3 つも回した（付録 `measured.csv`、§3.2） |
| S3 | 変わる見込みのモデルの一覧がある | **合格**（§4） |
| S4 | エンジン・正式なサンプル・golden が変わっていない | **合格**。書いたのは `output/` の下のスクリプトと結果、この報告書と付録だけ |

## 3. 調べ方と表

### 3.1 候補（CSV だけ。計画は回さない）

- 対象の工場：計画の木（`sc_tree_master.csv`）で `node_type = mom` かつ親の無いノード。Backward の押し戻し（`_apply_mom_cap_backward`）は、この工場だけにかかる。
- 能力：`capacity_plan.csv` の `max_supply`・`cap_soft` の行（旧書式の smartphone は製品の行）、`holiday_calendar.csv` の `partial_capacity`。休業：`supply_closure`、`operating_calendar.csv` の 0 shift。
- 市場：その製品の leaf_out の数（工場が 2 つの製品は `lane_assignment.csv` の行。smartphone の Phone16 は行が無いので全 leaf）。
- **候補 ＝ 能力か休業がかかり、市場が 2 つ以上**。

| モデル | 工場 | 候補 | 候補でない工場と理由 |
|---|---:|---:|---|
| Cookie-jp-2026 | 2 | 2 | |
| apparel-global-2028-2029 | 2 | 2 | |
| apparel-us-2026 | 16 | 16 | |
| bom-test-2026 | 1 | 0 | Vehicle_Assy：能力・休業なし、市場 1 |
| cosmetics-sg-th-2027-2029 | 2 | 2 | |
| ev-europe-2026 | 2 | 2 | |
| ev-thailand-2026 | 2 | 2 | |
| ev-thailand-2026_update | 2 | 2 | |
| oil-global-2027 | 8 | 8 | |
| rice-japan-2027-2028 | 2 | 0 | 集荷の 2 工場：`capacity_plan` に行が無い（rice の能力は Rice Seasonal の資源の表で、Backward の押し戻しにはかからない） |
| smartphone-global-2026-2029 | 4 | 4 | |
| smartx-2027-2029 | 4 | 3 | AssemblyIN：市場 1 |
| soysauce-eu／us／jpy／jpy-alloc | 各 1 | 各 1 | |

工場ごとの行（能力・休業の行数、市場の数、`demand_envelope`）は付録 `tables.md` の前半。

### 3.2 実測（計画を回して）

- golden と同じプラグインの組と方式（golden の `config` の `plugins`・`lot_flow_mode`）で headless の計画を回した。
- `BackwardPlanner._apply_mom_cap_backward` を自分のスクリプトの中で包み、元の関数を呼ぶ前後でノードを読むだけにした（付録 `scripts/measure.py`）。
  - その週に押し戻した lot ＝ 呼び出しで `psi4demand[w][CO]` に足された lot
  - その週の並び ＝ 呼び出しの後の `psi4demand[w][S]` ＋ 押し戻した lot
  - 落ちた lot ＝ 呼び出しで `past_due_lots` に足されたもの（計画の最初の週を超えた分）
- 各モデルの snapshot を golden の `period・products・config・forward・backward・ppc・psi` と比べ、違えば止める作りにした。**19 回すべて一致**。
- 1 モデルずつ回し、終わるごとに `output/roworder_stage0/<モデル>.json` に書いた（rice は最後）。

**変わる見込みの工場**（「超過の週（複数市場）」か「休業の週（複数市場）」が 1 以上。全行は付録 `tables.md`）：

| モデル | 製品 | 工場 | 超過の週（うち複数市場） | 休業の週（うち複数市場） | はみ出しの延べ | 落ちた lot |
|---|---|---|---|---|---:|---|
| Cookie-jp-2026 | Cookie_Import | Factory_GP_CN | 55（55） | 4（4） | 69,248 | 0 |
| apparel-global-2028-2029 | Apparel_Vertical | Garment_PT | 18（18） | 0 | 18,814 | 0 |
| apparel-us-2026 | Apparel_Outsourced_S3 | Factory_Import_CN | 1（1） | 0 | 708 | 0 |
| | Apparel_Integrated_S6 | Factory_Local_ES | 4（4） | 0 | 5,284 | 0 |
| ev-europe-2026 | EVmaker_Local | Factory_Local_DE | 0 | 2（2） | 1,000 | 0 |
| | EVmaker_Import | Factory_Import_HU | 5（5） | 4（3） | 830 | 0 |
| ev-thailand-2026 | EVmaker_Local | Factory_Local_TH | 0 | 2（2） | 1,000 | 0 |
| | EVmaker_Import | Factory_Import_CN | 8（8） | 4（4） | 1,440 | 0 |
| ev-thailand-2026_update | EVmaker_Local | Factory_Local_TH | 2（2） | 0 | 700 | 0 |
| | EVmaker_Import | Factory_Import_CN | 99（99） | 4（4） | 13,253 | 0 |
| oil-global-2027 | Gasoline_Local | Refinery_Local | 18（18） | 0 | 5,800 | 0 |
| | Gasoline_Local_RedSea | Refinery_Local_R | 98（98） | 0 | 9,023 | 4（CHUBU 3・KANSAI 1） |
| | Gasoline_EU_Local | Refinery_EU | 81（81） | 0 | 170,662 | 0 |
| | Gasoline_US_Local | Refinery_USGulf | 65（65） | 0 | 89,742 | 0 |
| smartphone-global-2026-2029 | Phone16 | EMS_A_CN | 148（128） | 0 | 2,461,276 | 24,587（APAC） |
| | Phone15 | EMS_A_CN_i15 | 160（160） | 0 | 1,609,879 | 19,547（APAC 16,249・EMEA 3,298） |
| | Phone17 | EMS_A_CN_i17 | 73（73） | 0 | 3,217,648 | 0 |
| smartx-2027-2029 | SmartX | AssemblyCN_g1 | 127（127） | 0 | 971,956 | 0 |
| | SmartXNext | AssemblyCN_g3 | 151（151） | 0 | 190,107 | 1,274（AMER 466・APAC 373・EMEA 435） |
| | SmartXPro_CN | AssemblyCN | 154（153） | 0 | 389,556 | 0 |
| soysauce-eu-2027 | Soy_Sauce | Bottling_Noda | 2（2） | 2（2） | 3,000 | 0 |
| soysauce-us-2027 | Soy_Sauce | Bottling_Noda | 2（2） | 2（2） | 3,000 | 0 |
| soysauce-jpy-2027 | Soy_Sauce | Bottling_Noda | 9（9） | 3（3） | 6,852 | 0 |
| soysauce-jpy-2027-alloc | Soy_Sauce | Bottling_Noda | 113（113） | 3（3） | 2,121,613 | 20,408（BE 6,096・FR 6,912・NL 6,100・JP 600・US 各 350） |

- 「はみ出しの延べ」は、同じ lot が何週も続けて押し戻されると毎回数える（延べの数。未充足の量ではない）。
- legacy の golden 3 つは、同じモデルの identity と工場ごとに同じ数字（Backward は方式によらず同じ）。

## 4. 変わる見込みのモデルの一覧

| 変わる見込み（13） | 変わらない見込み（3） |
|---|---|
| Cookie-jp-2026、apparel-global-2028-2029、apparel-us-2026、ev-europe-2026、ev-thailand-2026、ev-thailand-2026_update、oil-global-2027、smartphone-global-2026-2029、smartx-2027-2029、soysauce-eu-2027、soysauce-us-2027、soysauce-jpy-2027、soysauce-jpy-2027-alloc | bom-test-2026（市場 1、能力なし）、cosmetics-sg-th-2027-2029（候補だが、押し戻しが 1 週も起きない）、rice-japan-2027-2028（工場に Backward の能力が無い） |

**legacy の golden**：Cookie-jp-2026・ev-thailand-2026・soysauce-jpy-2027 の 3 つとも変わる見込み。

「見込み」としたのは次の理由から。

- 新しい方式で選ぶ lot が、たまたま今の「並びの末尾」と同じになる週もある。
- 市場が 1 つの週は、市場の中の選び方（設計書 v0.3 §3.3）が今と同じなら変わらない。

## 5. 気づいたこと

1. **休業だけで効く工場がある**：ev-europe の Factory_Local_DE と ev-thailand の Factory_Local_TH は、能力の超過は 0 週で、休業の週（各 2、市場 3）の押し戻しだけで変わる見込み。案 C・C_a2 の休業の週（E3）の扱いが、そのまま golden に出る。
2. **超過の週の多くは、休業の lot の繰り越し**：soysauce-jpy の超過 9 週は、3 回の休業（2027-W18・2028-W18・2028-W33）の直前の 3 週ずつ。休業の週の 1,000 lot が soft の目標の余りに収まるまで前へ送られている（例：W15 142・W16 428・W17 714・W18 1,000）。soysauce-eu・us の超過 2 週も、休業の前の週。
3. **候補でも押し戻しが起きない工場が多い**：候補 47 のうち、実測で変わる見込みは 24。cosmetics（soft の能力が需要を上回る）、apparel-us の 16 製品中 14、oil の輸入ハブ 3 つ・Hormuz、Cookie_Local、Garment_BD、smartphone の EMS_A_IN（Phone16 の 2 つ目の工場。押し戻しはすべて EMS_A_CN で起きた）。候補（CSV）だけでは過大になる。
4. **市場が 1 つの週の超過**：smartphone の EMS_A_CN は超過 148 週のうち 20 週、smartx の AssemblyCN は 154 週のうち 1 週が、並びに市場が 1 つだけ（発売の初めや終わりの週と見られる）。ここは市場の中の選び方だけが効く。
5. **落ちた lot（計画の前へ）が出ているのは 4 工場**：smartphone の 2 工場、smartx の AssemblyCN_g3、oil の Refinery_Local_R、soysauce-jpy-alloc。soysauce-jpy-alloc の 20,408 は、到達点 6 の R0（21 シフトの写しで BE・NL の不足 5,726・5,800）とは条件が違う正式なサンプル（能力 800 の固定）の数字。どの市場が落ちるかが行の順で決まっている形は同じ（BE・NL・FR に集中）。
6. **smartphone・smartx・soysauce-jpy-alloc の延べが大きい**：能力の不足が長く続き、同じ lot が何十週も押し戻され続けている。段 1 で比べるとき、この 3 つは差が大きく出る見込み。

## 6. しなかったこと

エンジンの変更、新しい方式の実装（段 1）、golden の作り直し、テストの実行（コードは変えていない）。

## 7. 大杉さんが確かめる手順（任意）

候補の表と実測の表は、次の 3 行で作り直せます（実測は全部で約 3 分。結果のファイルがあるモデルは飛ばすので、作り直すときは `output/roworder_stage0/*.json` を消してから）。

```bash
python output/roworder_stage0/candidates.py
```

```bash
python output/roworder_stage0/measure.py
```

```bash
python output/roworder_stage0/tables.py
```

`output\roworder_stage0\tables.md` が付録の `tables.md` と同じになり、`measure.py` の出力の各行が `golden_match=True` になります。
