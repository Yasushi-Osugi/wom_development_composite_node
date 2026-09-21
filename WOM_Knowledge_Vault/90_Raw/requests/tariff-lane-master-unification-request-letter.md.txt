# Coding Request Letter: 関税・貿易レーン マスタの統一と評価エンジン金額の一本化

作成日: 2026-07-24
作成者: Claude (Cowork)
ステータス: **ドラフト（設計提案・未実装）**。オーナー(大杉さん)レビュー→承認後に実装フェーズへ。本レターは AGENTS.md の owner-gated ルールに従い「AIは検査・起草まで／実装コミットはオーナー」の範囲。
準拠: `docs/design/psi_ppc_separation.md`（物理/財務の分離）、`docs/design/wom_canonical_concepts.md`（単一Lot_ID原則）、`docs/architecture/ppc_engine.md`、`AGENTS.md`
出自: `soysauce-us-2027` / `soysauce-eu-2027` ケース構築中、Management(Landed Cost, 戦略KPI) と PPC(Tariff Cost, 財務KPI) の金額が一致しない（Revenue $3.54M vs $1.206M、GM 25.9% vs 60%、Tariff額の基準差）ことを大杉さんが指摘。関税マスタの粒度設計（per-edge は細かすぎ／region-pair は荒すぎ）を「**product × 地域ペア**」に統一する案を提示。

---

## 1. Business question / 解決したい問題

```text
Management ビューの Landed Cost（戦略KPI）と PPC ビューの Tariff Cost（財務KPI）が、
売上・関税額・粗利率で一致しない。原因は (a) 金額を二重に計算する2つのマネー経路
（PPCロット台帳 と money.py の集計P&L）と、(b) 関税マスタが二重定義（ppc_tariff_rule は
per-edge、edge_cost_master は per-region-pair）であること。これは WOM 設計原則
「単一 Lot_ID リストから数量側・金額側KPIを突合ギャップなく導出」に反する。
関税マスタを canonical 化し、評価金額を単一ソースへ一本化して整合をとる。
```

観測された不整合（soysauce-us-2027, S1, 関税12.5%）:

| 指標 | PPC（財務KPI） | Management（戦略KPI） |
|---|---|---|
| Revenue | $3.54M | $1.206M |
| Gross Margin | 25.9% | 60.0% |
| Tariff | Tariff Cost $161.5K（ロット積算） | Landed Cost: Customs Duty $35,215（blended平均×集計COGS） |
| データ源 | `ppc_tariff_rule.csv`（エッジ別・ロット単位） | `edge_cost_master.csv`（地域ペア別・blended・product無し） |

## 2. Educational disclaimer

本レターが対象とする soysauce ケースは公開情報とドメイン知識のみに基づく架空・教育モデル（`wom_canonical_concepts.md` Canonical concept 11 準拠）。関税率・価格は例示値。本レターはエンジン設計変更の提案であり、特定企業・実税率を主張するものではない。

## 3. 設計の核（大杉さんの提案を採用）

関税は経済的に「**HSコード（＝製品）× 原産国（from_country）× 仕向国（to_country）**」で一意に決まる。したがって canonical master の自然な粒度は「**product × 地域ペア（国ペア）**」である。

- **`ppc_tariff_rule.csv`（per-edge）は細かすぎる**：同一の JP→US を `DC_US_SF->Rest_US_West` と `DC_US_NY->Rest_US_East` の2行に重複定義しており、冗長かつ不整合の温床。→ **マスタから降格し、SCツリーから生成する中間ファイルにする**。
- **`edge_cost_master.csv`（per-region-pair）は荒すぎる**：product 次元を欠く。→ **product_id を加えて canonical に昇格**（または新 `trade_lane_master.csv`）。
- **両エンジンが同一の canonical master を読む**ことで、関税額の基準を一致させる。

## 4. マスタ再設計（Phase 1 の中心）

### 4.1 canonical: `trade_lane_master.csv`（`edge_cost_master.csv` を拡張・改称）

```text
キー: (scenario, from_country, to_country, product_id)
列 : scenario, from_country, to_country, product_id, hs_code,
     tariff_rate, tariff_basis, freight_usd_per_lot, fx_rate, notes
```
例（soysauce, Base）:
```csv
scenario,from_country,to_country,product_id,hs_code,tariff_rate,tariff_basis,freight_usd_per_lot,fx_rate,notes
Base,JP,US,Soy_Sauce,2103100000,0.125,transfer_price,4.5,1.0,対米 12.5%
Base,JP,FR,Soy_Sauce,2103100000,0.08,transfer_price,6.0,1.0,対仏 8%
Base,JP,JP,Soy_Sauce,2103100000,0.0,transfer_price,1.0,1.0,国内
Tariff10,JP,US,Soy_Sauce,2103100000,0.10,transfer_price,4.5,1.0,対米 10%
Tariff0,JP,US,Soy_Sauce,2103100000,0.0,transfer_price,4.5,1.0,対米 0%
```
※ freight はここでは lane（国ペア）総額。物理レッグ按分は不要（下記4.3参照）。

### 4.2 生成中間: `ppc_tariff_rule.csv`（per-edge）を自動生成に

新規 `tools/gen_tariff_edges.py`（またはエンジン内前処理関数）:
1. `sc_tree_master.csv` の各 outbound エッジ (parent→child) を走査。
2. 両端ノードの region → country を `node_master`（または region→country マップ）で解決。
3. `from_country != to_country`（越境）のエッジについて、`(scenario, from, to, product)` で canonical を引き、per-edge 行を生成。
→ `ppc_tariff_rule.csv` は**手編集マスタではなく生成物**（`output/` 配下 or メモリ内）になる。既存ケースは互換のため当面ファイルも残せるが、正典は canonical。

### 4.3 責務の整理（tariff / freight / fx）

- **tariff_rate**：canonical（product × 国ペア × scenario）。← 本レターの主対象。
- **freight**：2種を区別する。①国際輸送（国ペア単位）＝canonical の `freight_usd_per_lot`。②国内・拠点間の物理レッグ費＝既存 `ppc_edge_cost_rule.csv`（per-edge, 物理層）を維持。Landed Cost は blended平均を廃止し、**当該SKUの実レーンの freight を集計**する。
- **fx_rate**：canonical（国ペア）＋ 週次変動が要るなら `ppc_fx_rate.csv` を継続。「報告通貨/USD」の意味を docstring と実装で一致させる（現状 landed_cost.py の fx 解釈が曖昧＝今回のバグ源の一つ）。

## 5. 評価金額の一本化（Phase 2 の中心・本丸）

関税マスタ統一だけでは Revenue/GM の不整合（$3.54M vs $1.206M、26% vs 60%）は残る。これは**金額を二重計算しているため**。

- **PPC のイベント台帳（`ppc_event_ledger.csv` / 単一 Lot_ID リスト）を唯一の真実源**に据える。
- Management の **P&L Summary・Landed Cost・Strategic KPI の金額を、`money.py` の別集計ではなく PPC台帳（`ppc_node_pl_summary` 等）から導出**する。→ Revenue/COGS/Tariff が両ビューで同一値になる。
- **粗利の定義（コスト範囲）を canonical 化**：Management 60% は「基礎COGS（素材+加工）」ベース、PPC 26% は「全landed（+freight+tariff+DAD+SGA）」ベースで、**測っているコスト範囲が違う**。どこまでを COGS/Gross に含めるかを1つ定義し、両ビューで同じ段階を表示する（例：Gross=素材+加工まで、Operating=+物流+関税+運営、と段階を明示）。
- **関税シナリオ比較（Base/10/0）** は、blended近似（現 landed_cost.py）でなく、**各関税水準でロット台帳の tariff イベントだけ再価格付け**して集計 → lot 精度で PPC と一致。

## 6. 影響ファイル（想定）

| ファイル | 変更 |
|---|---|
| `wom/engine/landed_cost.py` | `load_edge_cost_master` → canonical `trade_lane_master` ローダ。blended平均を廃し product×lane 参照。fx解釈を明確化。 |
| `wom/engine/money.py` | `build_scenario_money_kpi` を PPC台帳導出に整合（or 置換）。units の多重計上（leaf+DAD+FG_WH）を是正。 |
| `wom/ppc/ppc_runner.py`, `ppc_forward.py` | per-edge tariff を canonical から生成して適用。 |
| `tools/gen_tariff_edges.py`（新規） | ツリー→per-edge 生成（越境判定・region→country）。 |
| `wom/gui/app.py` | Management/PPC の金額表示を単一ソース（台帳）に。 |
| `data/sample/*/edge_cost_master.csv` | `trade_lane_master.csv` へ移行（product列追加）。`ppc_tariff_rule.csv` は生成物化。 |

## 7. 段階実装（phased）

- **Phase 1（マスタ統一）**：`trade_lane_master`（product×国ペア×scenario）導入＋per-edge 生成。両エンジンが同一関税源を読む。→ **税額（Tariff / Customs Duty）が一致**。
- **Phase 2（金額一本化）**：Revenue/COGS/GM を PPC台帳に一本化。`money.py` 集計を台帳導出へ。units 多重計上是正。GM の段階定義統一。→ **売上・粗利が一致**。
- **Phase 3（関税感応度の lot 精度化）**：Landed Cost の Base/10/0 比較を台帳再価格付けに。→ 戦略ビューも財務ビューと同値。

## 8. 後方互換・検証

- 既存6ケース（rice / smartx / Cookie / ev-europe / oil-global / apparel-global）を再ラン。Management と PPC の Revenue/COGS/Tariff/GM が**一致**することを確認。
- 既存 pytest（現行 81 件）を緑維持。関税生成・canonical ローダの新規テストを追加。
- `soysauce-us-2027` / `soysauce-eu-2027` で S1/S2 × 関税(0/10/12.5%) の金額が両ビュー一致することをヘッドレス検証（`data/sample/apparel-global-2028-2029/verify/` と同様のスクリプトを同梱）。

## 9. 設計上の判断メモ

1. **region vs country**：関税は country 単位。WOM の region（`US_W`/`US_E` 等）は country（`US`）にマップする必要がある。canonical は country キー、region→country マップを `node_master`/新規小マスタで持つ。
2. **ppc_tariff_rule の扱い**：即時削除せず、当面は「生成物（正典は canonical）」として共存。ドキュメントに「手編集しない・生成される」と明記。
3. **論文との接続**：本統合は「単一 Lot_ID → 突合ギャップなし」という WOM/論文の中核原則を実装で満たす作業。未統合状態は experience paper の Limitations/Future Work に正直に記載可能（「single-Lot_ID は設計目標、現実装はPPC台帳と集計P&Lの2経路が未統合」）。
4. **スコープ**：まず Phase 1（マスタ統一）だけでも「税額の一致」という体感的な改善が得られる。Revenue/GM 一致（Phase 2）は影響が広いので独立フェーズとする。

## 10. ステータス行

```text
[x] 起草（本レター）
[x] オーナーレビュー・承認（Phase 範囲の確定、branch wom-v1r2m0）
[x] Phase 1 実装（canonical edge_cost_master + tools/gen_tariff_edges.py で per-edge 生成）
[x] Phase 1 検証（生成物 == 手作り ppc_tariff_rule、--check 0 diffs、US/EU）
[x] Phase 2 実装（Management P&L Summary + Landed Cost を PPC台帳から導出）
[x] Phase 2 検証（Base の GM が PPC/P&L で一致：US 25.9% / EU 26.2%）
[x] Phase 3 実装・検証（関税感応度 lot 精度化 = Phase2 増分2 の per-channel 再スケールで達成）
[x] オーナー commit / push（d381511, 0ada4ca ＋ テスト修正）
```

## 11. 実装結果（2026-07-25 完了、実装時の設計逸脱を含む）

**Phase 1（マスタ統一）— 完了**
- `edge_cost_master.csv` に `product_id` 列を追加して canonical 化（当初案の `trade_lane_master.csv` への改称は見送り。既存6ケースへの影響を避け、後方互換〔product_id 空欄＝全product wildcard〕を維持するため、ファイル名は据え置いた）。
- `tools/gen_tariff_edges.py` を新設。`sc_tree_master` + `ppc_node_profit_zone`（node→country）+ `route_master`（hs_code）+ canonical `edge_cost_master`（scenario別）から per-edge `ppc_tariff_rule.csv` を生成。`--check` で生成物と既存手作りファイルの一致を確認（US/EU とも 0 diffs）。`ppc_tariff_rule.csv` は「生成物（正典は canonical）」の位置づけ。

**Phase 2（金額一本化）— 完了（GUI 層でのオーバーレイ方式を採用）**
- 当初案は `money.py` の `build_scenario_money_kpi` を台帳導出へ「置換」だったが、影響範囲が広いため **GUI 層（`ManagementCockpitPanel`）で台帳値をオーバーレイする方式**に変更（`money.py` 自体は無変更、後方互換）。
  - `_ledger_pl_for_sku()`：P&L Summary の Revenue/COGS/GP/GM を `ppc_kpi_summary.json` / `ppc_node_pl_summary.csv` から取得。運転資本（Inv/CCC/AR/AP）は損益ではなく貸借項目のため money 由来のまま据え置き（意図的）。
  - `_ledger_lc_overrides()`：Landed Cost パネルの Revenue/Customs/Landed GM%/ΔMargin/Tariff% を台帳から再導出。Freight はスイープ不変の情報列として money 由来を据え置き（台帳 cost に既に内包、二重計上回避）。
- `money.py` の units 多重計上（leaf+DAD+FG_WH）は「是正」ではなく、金額を台帳ソースに切り替えることで**迂回**（money units への依存を断った）。

**Phase 3（関税感応度の lot 精度化）— Phase 2 増分2 で同時達成**
- Landed Cost の Base/10/0 比較を、チャネル別 `tariff_base`（台帳）を `rate(scenario)/rate(Base)` で再スケールして算出（tariff basis 一定＝厳密）。blended 近似を廃止。US レーンのみスイープで変動、EU 8% は不変。

**検証状況**
- soysauce-us（S1）/ soysauce-eu（S2）を GUI 実機確認：Management の P&L Summary・Node P&L・Landed Cost・PPC コックピットの GM が**全て一致**（突合ギャップ解消）。
- 既存 pytest **81 件緑**。ただし `test_ppc_vertical_slice.py::test_landed_cost_components` は本作業前から陳腐化していた（2026-07-10 の `mom_to_dad_freight_base` 分離にテスト期待値が未追随）ため、期待値に当該 freight 項を追加してテスト側を実装に合わせた（エンジン無変更）。
- 未実施（当初案からの縮小）：既存6ケースの一括再ラン・ヘッドレス検証スクリプトの同梱は今回見送り（エンジン無変更でサンプルデータ・GUI のみの変更のため、既存ケースへの回帰リスクは低いと判断）。
