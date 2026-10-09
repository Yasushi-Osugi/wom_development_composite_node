# Request Letter — 公開の前のサンプルの見直し（追加）：画像の中の実名

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-09
- 基準：作業ツリーのまま（`RequestLetter_SampleNames_PublicReview_to_CodeKun.md` の作業の上。まだ commit していない）
- 前提：`docs/development/WOM_SampleNames_PublicReview_Report.md` の「画像の中の実名」
- **この依頼書にも実名を書かない。** 予備の一覧と対応表は `output/sample_names/`（git の対象外）

## 0. 背景

テキストの検査（`tests/test_no_real_names.py`）は画像の中を見られない。
Owner が `output/sample_names/image_review.html`（画像の一覧のページ、git の対象外）で全体を見たところ、次の 4 枚の上部に、スマートフォンのモデルの**元の名前**が写っていた。

- `docs/development/sim_mgmt_worldmap/part1/1_simulation_done.png`
- `docs/development/sim_mgmt_worldmap/part1/2_planning_done_ppc_running.png`
- `docs/development/sim_mgmt_worldmap/part1/3_planning_ppc_done.png`
- `docs/development/sim_mgmt_worldmap/part1/4_simulation_after_planning.png`

Code君の報告にある古い画面 3 枚（名前を変えたもの）も、中には元の名前が写っている。
Owner は「ほぼ大丈夫」と見たが、ざっと見ただけなので、残りも目で確かめてほしい。

## 1. 作業

1. **目で確かめる**：git が追跡する画像（新しく撮った `docs/development/sample_names/gui/` を含む）を開いて、元の実名（予備の一覧・対応表の語）が写っていないかを見る。ウィンドウのタイトル・帯・凡例・ノードのラベル・PSI List のノード名・World Map の拠点名・表の見出しに注意する。少なくとも、上の 4 枚と同じフォルダ、`worldmap_actual_flows/`、`sim_mgmt_worldmap/`、`stage_d_phase1/`・`stage_d_phase2/`、`flow_check_warmup/`、`lot_identity_flow/`、`lovem/`、`docs/images/` は全部見る。
2. **写っていた画像は削除する。** その画像を参照している文書（報告書など）には、画像の参照の所に「（画像は 2026-10-09 に削除。実在の名前が写っていたため）」と注記する。文書のほかの文は変えない。
3. **`docs/images/`（README など外向け）に写っていたものだけは、新しい名前で撮り直す**（同じ画面・同じ大きさ）。撮り直せないものは、理由を書いて削除する。
4. 一覧のページ `output/sample_names/image_review.html` を作り直す（削除・撮り直しの後の状態。Owner が最後にもう一度見るため）。

## 2. 受入・報告

| ID | 検査 |
|---|---|
| I-1 | 確かめた画像の数と、写っていた画像の一覧（パスだけ。写っていた名前は書かない） |
| I-2 | 削除した画像を参照していた文書に注記があり、壊れたリンクが残っていない |
| I-3 | `docs/images/` の撮り直しの前後（新しい画像のパス） |
| I-4 | `tests/test_no_real_names.py` と全テストが緑 |

- 報告は `docs/development/WOM_SampleNames_PublicReview_Report.md` に節を足す（新しい報告書は作らない）。元の実名は書かない。
- 最後に、削除・追加・変更のファイルの一覧。
- commit・push はしない（前の依頼の作業と一緒に、Owner が commit する）。
