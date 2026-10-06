# Rice DAL Trial — データ辞書

## ケース

`baseline`: 原本legacy、156週。`legacy_calendar`: W53/W52補完legacy、157週。
`dal_current`: 173週identity、現行田能力。`dal_increased`: 田の収穫週だけ能力増強。
`dal_observed`: dal_currentと同一条件、LOVEM ON。

## 主な生データ

| ファイル | 粒度と意味 |
|---|---|
| `run_manifest.json` | 固定SHA、入力CSVのハッシュ、プラグイン、lot_flow_mode、cpu_size、実行時間、元モデル不変 |
| `headless_snapshot.json` | 既存headlessの返却値。PPCと数量の既存集計 |
| `fingerprints.json` | 全品目・全ノードDemand/Supplyの順序付きハッシュ、実出荷、Backward/Forward結果、PPCファイル。ON/OFF照合用 |
| `*_post_backward_demand_counts.csv` | Backward直後、品目・node・週別Demand S/CO/I/Pと能力 |
| `*_post_backward_hooks_demand_counts.csv` | Hook（HarvestBatch等）を適用した後の同じ計数 |
| `*_field_P.csv.gz` | 上記各時点の田のP、Lot_IDごとの行 |
| `node_week.csv` | 最終結果の品目・node・週。Demand S/P、Supply S/P、期末I、週初CO、実出荷S、能力、操業状態 |
| `actual_shipments.csv.gz` | 実出荷の全出現。商品・node_id・week_index・sequence（0始まり）・lot_idを1件として保存 |
| `demand_anchors.csv.gz` | Holiday適用後の市場Demand S。要求週とIDの全数。LOVEMのpre-hook anchorsとは時点が異なる |
| `market_lot_status.csv.gz` | 上記要求IDを実出荷と照合。early/on_time/late/not_shipped、最初の出荷週、遅配週数、出荷出現数 |
| `market_summary.csv` | 品目×市場×scope(all/report)。reportは要求週2027-W01〜2028-W52のID集合 |
| `q1_field_placement.csv.gz` | 田Pの配置週、田の要求週、その週以前の直近収穫週、対応する市場要求週、非収穫配置かどうか |
| `forward_results.json.gz` | 公開ForwardPlanResult属性の値。内部のset等は除外。cap_hard_eventsは件数記録 |
| `backward_results.json.gz` | BackwardPlanResult属性。past_dueは開始端で配置できなかった要求の記録 |
| `ppc/ppc_lot_reconciliation.csv` | 週次に集約された販売。qtyを単価/単位原価に掛けて金額を求める。物理Lot_IDの1対1台帳ではない |

`supply_S` は通常要求だが、原本のHarvestBatchが設定する `push_sub` では実出荷表示へ書き換わる。
田の元要求の週は **Demand S**から読む。`actual_S`・`actual_shipments` は物理的に出荷された件数。

`CO_start` は週初。最終週終了後のCO列はPSIに保存されない。
期末注文残は、需要ID全数から全実出荷IDを照合する。現行DALは、最終週CO∪S−実出荷ともID集合が一致した。
`cap_hard_deferred_lots` はコード上 `(node_id, lot_id)` の重複なし件数であり、全ネットワークでのユニークLot数ではない。
`cap_hard_deferred_lot_weeks` と `cap_hard_events` の合計は、繰返し待つ同一Lotを毎週数える。
加工能力待ちで後週へ送られたPを、I在庫として数えてはいない。

## 付表

| ファイル | 内容 |
|---|---|
| `case_comparison.csv` | 要求週集合の数量と、実出荷週で切ったPPC金額を別欄で表示 |
| `polishing_capacity.csv` | 精白品目別能力・計画P超過・実現P/S・繰延Lot週 |
| `node_inventory_summary.csv` | node別Iピーク・IのべLot週・2027開始時I |
| `harvest_plugin_omissions.csv` | Harvest前後の田PにあるIDの差。市場未充足数ではない |
| `field_placement_by_market_year.csv` | 市場要求年別の田Pの収穫／非収穫配置 |
| `lot_examples.json` | 2つの代表需要IDの田Pと全ノード実出荷の履歴 |
| `lovem_independent_verification.json` | 出荷イベント1対1、全snapshot区間の独立復元、Q12一致 |
| `raw_validation.json` | gzip50件、Holidayによるanchor追加削減、最終COのID照合 |
| `protected_file_integrity.json` | 基準のtracked 987ファイルが全件SHA-256一致 |

## LOVEM run

`manifest.json`、`weeks.csv`、`nodes.csv`、`capacity.csv`、`events.jsonl.gz`、
`relations.jsonl.gz`、`source_evidence.jsonl.gz`、`state_digests.jsonl`、
`psi_intervals/`、`ppc/`を含む既存形式のrun。
元のLOVEM形式を変更していないため、既存viewerで読める。
独立検査は順序付き実出荷とPSIのmultisetを別々に扱う。
区間は元リストの並び順を復元する形式ではない。
