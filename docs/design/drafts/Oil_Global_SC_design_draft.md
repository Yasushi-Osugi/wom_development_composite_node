# Global Oil Supply Chain — WOM モデル設計ドラフト v1

第5回note記事向け。Cookie-jp-2026 / ev-europe-2026 と同じ「現地生産 vs 越境輸入」の対比構造を踏襲しつつ、石油SC特有の要素（クラックスプレッド、タンカー輸送LT、地政学リスク）を新たに組み込む案。

架空モデルであることを明記し、実在の産油国・石油会社名は使用しない（NOC/IOCのような一般名詞＋地域コードで匿名化する、ev-thailand-2026と同じ方針）。

---

## 1. 全体構造（案）

Cookie/EVと同じ「SKU二本立て（現地精製 vs 輸入完成品）」パターンを踏襲する。

```
SKU_Local（原油輸入 → 国内精製）
  leaf_in: Crude_ME（中東産原油、産油地域）
    → MOM: Refinery_Local（国内製油所）
      → supply_point
        → DAD: Tank_Local（国内貯油タンク、Buffering Stock候補）
          → leaf_out: Retail_Local_A / Retail_Local_B / Retail_Local_C（地域販売、給油所チャネル）

SKU_Import（海外精製 → 完成品輸入）
  leaf_in: Refinery_SG（海外製油拠点、完成品の調達源として扱う）
    → MOM: Import_Hub（輸入基地・受入タンクMOM）
      → supply_point
        → DAD: Tank_Import（輸入貯油タンク、Buffering Stock候補）
          → leaf_out: Retail_Import_A / Retail_Import_B（地域販売、SKU_Local側と別チャネル）
```

- 石油そのものではなく「ガソリン（完成品）」を最終SKUとして扱う（Crack Spreadを表現しやすいため）。
- `leaf_in` の `Crude_ME` は原油そのもの、`Refinery_SG` は「海外で精製済みの完成品」を供給する側 — 役割上は両方 `leaf_in` だが、単価の意味が異なる点をppc_supplier_cost.csvで区別する。

---

## 2. Node一覧（node_type = WOM規約: leaf_in/mom/supply_point/dad/leaf_out）

| node_id | node_type | 役割 | 備考 |
|---|---|---|---|
| Crude_ME | leaf_in | 中東産原油（架空の産油地域コード） | 週次原油価格（Brent/WTI/Dubaiのような指標を架空名で） |
| Refinery_SG | leaf_in | 海外精製拠点（輸入完成品の調達源） | purchase_priceは完成品ガソリン価格ベース |
| Refinery_Local | mom | 国内製油所 | cap_hard=精製能力、conversion_cost=精製コスト |
| Import_Hub | mom | 輸入基地（受入タンクMOM） | plan_mode=push想定（タンカー到着はPUSH的） |
| supply_point | supply_point | InBound/OutBound bridge | 既存WOM規約通り |
| Tank_Local | dad | 国内貯油タンク | buffering_stock_flag対象、ss_days候補 |
| Tank_Import | dad | 輸入貯油タンク | 同上、タンカーLTが長いため安全在庫の意味が大きい |
| Retail_Local_A/B/C | leaf_out | 国内給油所チャネル（地域別） | region必須 |
| Retail_Import_A/B | leaf_out | 輸入品給油所チャネル | region必須 |

---

## 3. Master CSVへの追加・流用方針

既存スキーマ（sku_master / demand_forecast / node_master / sc_tree_master / capacity_plan / lane_assignment / node_cost_master / edge_cost_master / route_master / holiday_calendar / inventory_master）はそのまま流用。石油特有の表現は、**新しいCSVを増やさず、既存項目の値の置き方で表現する**方針とする（エンジン改修を最小化するため）。

| 石油特有の要素 | 表現方法（既存スキーマ内） |
|---|---|
| クラックスプレッド | `ppc_supplier_cost.csv`（原油/輸入完成品の仕入値）と`ppc_market_price.csv`（ガソリン販売価格）の差分。Node P&L画面でRefinery_Local/Import_Hubの粗利（実質マイナス表示＝コスト集中箇所）として、EVケースと同じ見せ方ができる |
| タンカー輸送リードタイム | `sc_tree_master.csv`の`lead_time_weeks`をCrude_ME→Refinery_Local、Refinery_SG→Import_Hubで長め（4〜6週）に設定 |
| 貯油タンクの安全在庫 | `ss_days`をTank_Local/Tank_Importに設定、`buffering_stock_flag=1` — 既存のBufferingStockOptimizerPluginがそのまま使える |
| 精製能力の制約 | `capacity_plan.csv`でRefinery_Localのcap_hardを設定（既存MOM Constrained Demand Allocationがそのまま使える） |
| 為替・関税 | `edge_cost_master.csv`のfx_rate/tariff — Landed Cost engineがそのまま使える |

→ **既存エンジンのままでも、モデルデータの組み方だけでOil SC特有のストーリーの大半（クラックスプレッド、安全在庫、精製能力制約、為替）は表現できる**、というのが設計上の要点。

---

## 4. 新規エンジン拡張候補（今回のスコープ外・将来検討）

CLAUDE.mdの「未対応・次回検討事項」にすでに記載されている、**レーン障害時の代替ルート切り替えPlugin**（ホルムズ海峡封鎖 → 喜望峰迂回ルートへの切り替え、`HOOK_PRE_PLAN`で`edge_cost_master.csv`/`route_master.csv`ベースの`lt_wks`・`cap_hard`書き換え）は、Oil Caseと非常に相性が良い（地政学リスクの象徴的なシナリオのため）。

ただし今回のドラフトでは、まず**既存エンジンのみで組めるベースモデル**を優先し、このPluginは「Phase 2（発展編）」として、ベースモデルが動いた後に着手する方が手戻りが少ないと考える。

---

## 5. 主要シナリオ（案、3〜5個）

| # | シナリオ名 | 内容 | 確認したいWOMの効能 |
|---|---|---|---|
| 1 | Baseline | 平常時の週次PSI・Crack Spread | Node P&L・Management Cockpitの基本動作 |
| 2 | Refinery_Outage | Refinery_Localが数週間cap_hard=0（定期修繕/事故想定） | MOM cap_hardクリップ＋CO前倒し、Fill Rate低下の可視化 |
| 3 | Crude_Price_Spike | Crude_MEの`ppc_supplier_cost`が急騰（OPEC減産想定） | Crack Spread縮小がNode P&Lにどう波及するか |
| 4 | Tanker_Delay | Refinery_SG→Import_Hubの`lead_time_weeks`が一時的に延長（航路混雑想定） | Tank_ImportのSS_daysバッファがどこまで吸収できるか |
| 5（Phase 2） | Strait_Closure | 主要航路封鎖 → 迂回ルートでlt_wks・freight急増 | 新規Route Disruption Pluginの検証（将来） |

---

## 6. 次のステップ（提案）

1. 本ドラフトのSC構造・シナリオ内容をレビュー・確定
2. `data/sample/oil-global-2027/` フォルダを新設し、全マスターCSVを作成（rice-japan-2027-2028を雛形に）
3. ヘッドレスCLIで週次PSIを実行し、実データでCrack Spread等の数値を検証
4. Management/PPC CockpitでNode P&L・Buffer Stockの見え方を確認
5. note記事ドラフト作成（Cookie/EV記事と同じ構成：はじめに→モデル構造→注目ポイント(Crack Spread)→シナリオ結果→今後の拡張候補→おわりに）
