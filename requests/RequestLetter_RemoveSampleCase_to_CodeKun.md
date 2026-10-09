# Request Letter — サンプルの 1 モデルと関連資料の削除

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-09
- 基準：作業ツリーのまま（名前の置き換え・画像の作業の上。まだ commit していない）。**この作業を、画像の作業より先に行う。**
- 種別：削除・文書・テスト。保護対象のコアはコメントだけ。

## 0. 決定

Owner の判断で、**サンプルの 1 モデルと、それに関するデータ・資料をリポジトリからすべて削除する。**
理由は書かない（この依頼書・報告書・コメント・commit のメッセージのどこにも、理由や背景を書かない）。文書には「Owner の判断で削除（2026-10-09）」とだけ書く。

## 1. 作業

1. **棚卸し**：git が追跡するすべてのファイルと、まだ add していない新しいファイル（`git ls-files --cached --others --exclude-standard`）から、このモデルに関するものを探す。手がかり：モデル名とその書き方の揺れ、このモデルの品目に関する語、拠点名・製品名・市場名。画像も対象（ファイル名と、目で見て中身）。`smartx_bottleneck/figures/india_requirements_and_capacity.png` が smartx の図か、このモデルの図かを見て判断する。
   - 結果は `output/remove_case/inventory.csv`（git の対象外）に書く。報告書には件数とパスだけ。
2. **削除**：
   - このモデルのフォルダ全体、その golden（前の依頼で作ったばかりの golden も含む）、再現スイープの spec、このモデルだけの図・記録・道具。
   - ほかのモデルと共有の道具・テスト（例 `tests/test_backward_supply_role.py`）が、このモデルを例やデータとして使っていれば、ほかのモデルか小さな人工の木に置き換える。テストの意図（何を守るテストか）は変えない。置き換えられないテストは、理由を書いて報告する（消すかは Owner）。
3. **文書の記述**：CLAUDE.md・README.md・`docs/` の設計・報告・`requests/` の依頼書で、このモデルに触れている所を削る。
   - 一文や表の一行だけなら、その部分を削る。
   - 段落や節がこのモデルの話なら、その段落・節を「（Owner の判断で削除。2026-10-09）」の一行に置き換える。
   - 数字の表（全モデルの比較など）からは、このモデルの行を削る。合計の行があれば数え直す。
   - 祝日の暦（`holiday_calendar.csv`）にある一般の祝日の名前は、このモデルと関係なければ残す。
4. **保護対象のコア**（`plan_node.py`・`backward_planner.py` など）は、コメントにこのモデルの名前・例があれば、一般の書き方に直す。コードは変えない。
5. 前の依頼の成果物（`output/sample_names/` の対応表・棚卸し・`private_list_suggestion.txt`・`image_review.html`、`docs/development/sample_names/`、`docs/development/public_readiness/` の表）から、このモデルの行・項目を削る。
6. **`docs/WOM_Start_Here.md` は触らない**（Claude 君が直す）。

## 2. 受入条件

| ID | 検査 |
|---|---|
| X-1 | 追跡するファイル・新しいファイルの中身とファイル名に、このモデルの名前・拠点名・製品名が残っていない（棚卸しの手がかりで再検索して 0 件。Start Here を除く） |
| X-2 | golden は 16 件（canonical 13＋legacy 3 → 計画どおりの件数を報告）。残りのモデルの golden は不変 |
| X-3 | 置き換えたテストが、同じことを守っている（何を、どのモデル・木で守るようにしたか） |
| X-4 | 全テストを単独で実行して緑。件数を報告 |

## 3. 報告

- 前の報告書 `docs/development/WOM_SampleNames_PublicReview_Report.md` に節を一つ足す。題は「サンプルの 1 モデルの削除（Owner の判断）」。理由は書かない。
- 削除・変更したファイルの一覧（パスだけ）。
- commit・push はしない。
