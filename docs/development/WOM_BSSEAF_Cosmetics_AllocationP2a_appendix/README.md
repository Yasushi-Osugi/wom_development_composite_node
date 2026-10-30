# 付録：BS-SEAF 化粧品 — 配分の試行 P2-a の再現用データ

本報告：`docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_Report.md`。

- `scripts/`：試行のスクリプト。`output/bsseaf_cosmetics/p2a_work/` に置いて、リポジトリの根から実行する。
  1. `make_allocation.py`：貢献利益を M0 の PPC の結果と照合し、配分のファイルを書く（M0 の試行の `money_m0_work/checks_ppc.json` が要る。写し `P2a1`・`P2a2` は C3a の CSV を写して先に作る）
  2. `python -m tools.run_quantity_allocation …`（報告書 §3 のコマンド。各写しで 1 回）
  3. `measure.py P2a1 P2a2 P1`：M2〜M4（Part A の `tools.shelf_life_check --demand-file` を使う）
  4. `evaluate.py`：評価の額、タイ 30% の感度
  5. `tables.py`：報告書の表
- `allocation/`：数量配分モードの配分のファイル 2 つ。
- `records/`：配分の記録（貢献利益の照合を含む）、評価の額、各案の測定（⑤ の Lot_ID、工場の端の週、年齢、能力のハッシュ）。

金額は架空のブランドの仮定（M0、`requests/BSSEAF_Cosmetics_Money_Assumptions_v0.1.md` §5.1）。評価の額は配分を比べるための比較値で、営業利益ではない。
