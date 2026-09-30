# iphone_evupdate_s2 — 比較表・対応表・実行条件

`docs/development/WOM_iPhoneWarmup_EVUpdateKitting_S2_Report.md` の付表。
依頼書：`requests/RequestLetter_iPhoneWarmup_EVUpdateKitting_S2_to_CodeKun.md`

## 実行条件

| 項目 | 値 |
|---|---|
| リポジトリ／ブランチ | `Yasushi-Osugi/wom_development_composite_node`／`wom-v1r5m1_cap_trial` |
| 基準 SHA（依頼書） | `979cf7afb669a5eba17318ad81ff4f4525dd7641` |
| 着手時の HEAD | `b6d5482`（基準＋依頼書 1 ファイル。コード・サンプル・golden は基準と同じ） |
| 着手時の作業ツリー | コード・サンプル・golden に差分なし。Obsidian Vault（`WOM_Knowledge_Vault*`）に未 commit の変更あり（触っていない） |
| 実行環境 | Windows 11 Home、`C:\Users\ohsug\anaconda3\python.exe`（Python 3.12.3）、`PYTHONDONTWRITEBYTECODE=1`、pytest は `-p no:cacheprovider` |
| 作業フォルダ | `C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial` |
| プラグイン | golden のモデルは golden に記録された一覧。ev-thailand-2026_update・alloc は `safe` |
| 測定の出力先 | `output/iphone_evupdate_s2/A`・`B`・`C`（git の対象外。大きい生データは ZIP。下の「生データ」） |

## 測定スクリプト（再実行できる）

| 区分 | コマンド | 内容 |
|---|---|---|
| A | `python -m tools.warmup_trial --model iphone_global --weeks 0,17,26 --out output/iphone_evupdate_s2/A` | モデルのコピーで warmup を変えて実行。市場の結果、期末注文残の ID ごとの分類 |
| B | `python -m tools.ev_update_kitting_trial --out output/iphone_evupdate_s2/B` | ev_update のコピーで、今の構成／置場を外した構成／モーターを遅らせた構成 |
| C | `python -m tools.s2_eval_compare --out output/iphone_evupdate_s2/C --base-ref 979cf7a` | 基準 commit の評価コードと今の評価コードを、同じ計画結果に当てて比べる（全モデル×2 方式） |

どれも原本（`data/sample/`）には書かない。

## このフォルダのファイル

| ファイル | 内容 |
|---|---|
| `A_iphone_warmup_trial.csv` | iphone：warmup なし／17／26 の市場・原因・PPC・助走の生産量と在庫 |
| `A_iphone_backlog_nodes.csv` | iphone：止まったノード、最初に置けなかったノード、条件の組み合わせ、足りなかった週数 |
| `A_capacity_schema_mapping.md` | `capacity_plan.csv` の 2 つの書式と、助走行の作り方の対応表 |
| `B_ev_update_node_path_mapping.md` | ev_update：置場を入れる前後のノード・経路・LT・参照 CSV の対応表 |
| `B_ev_update_summary.csv` | ev_update：条件ごとの市場・Flow Check・重複の件数・PPC |
| `B_ev_update_psi_nodes.csv` | ev_update：EVmaker_Local の各ノードの P（のべ・異なる ID）・実出荷・在庫・CO |
| `B_ev_update_kitting_table3.csv` | ev_update：Flow Check 表 3（部材の消費と完成の照合） |
| `B4_duplicates_all_models.csv` | 全モデルの「供給側の同じ ID の重複」の件数と Flow Check |
| `C_s2_usage_inventory.md` | S2：S・実出荷を使う箇所の棚卸し（変更の前後） |
| `C_s2_compare.csv` | S2：全モデル×2 方式の、基準の評価と今の評価の比較 |

## 生データ

`output/iphone_evupdate_s2/iphone_evupdate_s2_rawdata.zip`（git の対象外）。中身と SHA-256 は `rawdata_sha256.txt`。
