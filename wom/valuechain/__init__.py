# -*- coding: utf-8 -*-
"""
wom.valuechain — 段階 D（金額編）第 1 回：Value Chain の台帳
（設計：docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md、
 依頼：requests/RequestLetter_StageD_Phase1_to_CodeKun.md）

計画（identity）の**区間ごとの実出荷**を起点に、Lot_ID ごとの在庫原価・金額の明細を作る。
計画の結果を読むだけで、計画は変えない。今の PPC（wom/ppc）は変えずに並べて比べる。

- policy.py   費用の分け方（依頼 §1-4）。この表は、ここ 1 か所だけに置く
- masters.py  マスターの読み込み（vc_config / vc_entity / vc_node_assignment / vc_price_rule と、
              今の PPC のマスター）。同じ区間の同じ種類の価格が 2 か所にあれば止める
- fx.py       為替（基準通貨を経由した 2 通貨の換算、助走週は表の最初の週、表の外は未評価）
- records.py  計画の結果 → 出荷の記録（LOVEM の実出荷と同じ ID）・入荷・区間
- ledger.py   台帳の本体（在庫の記録、金額の明細、三つの原価の基準）
- views.py    V1・V2・V3（単週と累計）、在庫、照合
- run.py      モデルのフォルダから台帳を作って CSV に出す（tools/valuechain_run.py が呼ぶ）
"""
