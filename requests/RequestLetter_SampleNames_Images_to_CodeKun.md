# Request Letter — 公開の前のサンプルの見直し（追加）：画像の中の実名（範囲を絞った版）

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-09（2026-10-15 に範囲を絞って書き直し）
- 基準：`wom-v1r5m1_cap_trial`、**81254d9**（名前の置き換えとサンプルの 1 モデルの削除は commit・push 済み）。着手時の SHA を報告する
- 前提：`docs/development/WOM_SampleNames_PublicReview_Report.md` の「画像の中の実名」
- **この依頼書にも実名を書かない。** 予備の一覧と対応表は `output/sample_names/`（git の対象外）

## 0. 背景と範囲

テキストの検査（`tests/test_no_real_names.py`）は画像の中を見られない。
Owner が `output/sample_names/image_review.html` で全 149 枚を一通り見て、「ほぼ大丈夫。下の 4 枚に元の名前が写っている」と判断した。
**全部の画像を見直す必要はない。** Owner の負担（利用の上限）を考えて、作業は下の 19 枚だけにする。

## 1. 作業

### 1.1 削除する 7 枚（目で確かめ直さなくてよい）

Owner が見つけた 4 枚：

- `docs/development/sim_mgmt_worldmap/part1/1_simulation_done.png`
- `docs/development/sim_mgmt_worldmap/part1/2_planning_done_ppc_running.png`
- `docs/development/sim_mgmt_worldmap/part1/3_planning_ppc_done.png`
- `docs/development/sim_mgmt_worldmap/part1/4_simulation_after_planning.png`

前の報告で Code君が挙げた 3 枚（名前だけ変えて、中に元の名前が写っているもの）：

- `docs/development/worldmap_actual_flows/smartphone_world.png`
- `docs/development/sim_mgmt_worldmap/screens/smartphone-global-2026-2029__World.png`
- `docs/development/sim_mgmt_worldmap/part1/kpi__smartphone-global-2026-2029__after__1280x720__All.png`

7 枚を削除する。参照している文書（報告書・json など）には、参照の所に「（画像は 2026-10-09 に削除。実在の名前が写っていたため）」と注記する。文書のほかの文は変えない。

### 1.2 目で確かめる 12 枚：`docs/images/`（README など外向け）

`docs/images/` の 12 枚だけを開いて、元の実名（予備の一覧・対応表の語）が写っていないかを見る。ウィンドウのタイトル・帯・凡例・ノードのラベル・ノード名・拠点名に注意する。

- 写っていなければ、何もしない。
- 写っていれば、新しい名前で撮り直す（同じ画面・同じ大きさ）。撮り直せないものは、理由を書いて削除し、参照している所に 1.1 と同じ注記をする。

### 1.3 やらないこと

- ほかのフォルダの画像は見ない（Owner が確認済み）。
- `image_review.html` は作り直さない。

## 2. 受入・報告

| ID | 検査 |
|---|---|
| I-1 | 1.1 の 7 枚が削除され、参照していた文書に注記があり、壊れたリンクが残っていない |
| I-2 | `docs/images/` の 12 枚の結果（写っていなかった／撮り直した／削除した。パスだけ。写っていた名前は書かない） |
| I-3 | `tests/test_no_real_names.py` と、画像を参照するテスト（あれば）が緑。全テストの実行は不要（画像と文書の注記だけの変更のため） |

- 報告は `docs/development/WOM_SampleNames_PublicReview_Report.md` に節を足す（新しい報告書は作らない）。元の実名は書かない。
- 最後に、削除・追加・変更のファイルの一覧。
- commit・push はしない（Owner が新しく commit する）。
