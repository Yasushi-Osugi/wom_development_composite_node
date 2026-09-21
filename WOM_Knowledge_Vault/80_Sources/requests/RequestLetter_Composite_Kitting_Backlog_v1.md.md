---
tags: [wom, source]
---
# requests/RequestLetter_Composite_Kitting_Backlog_v1.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/RequestLetter_Composite_Kitting_Backlog_v1.md) · [原文テキスト](../../90_Raw/requests/RequestLetter_Composite_Kitting_Backlog_v1.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Composite Kitting backlog・保存修正
- 対象と設計
- 受入・互換性
- 扱わないもの

## 関連する知識源

- [[80_Sources/wom/engine/forward_planner.py|wom/engine/forward_planner.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Composite Kitting backlog・保存修正

基準: ceef9ee0e357a556fb5959fdb1e49d8b0e670347 / wom-v1r5m0。
大杉さんの本会話「はい。そうですね。設計、実装を進めてください。」を
本修正の開始指示とする。commit/push・golden更新の承認は含まない。

## 対象と設計

対象coreは `wom/engine/forward_planner.py` のKitting Gateのみ。
通常pullかつ全直下子がstockyardのAssemblyを対象とし、その他のモード・
混在子の既存経路は今回変更しない。新Compositeクラス・CSV列は導入しない。

- gate内に順序付き未完了kit集合を保持する。過去未完了を当週要求より先に
  評価し、その中で全部材が揃ったものを選ぶ（不足kitは後続kitを妨げない）。
- 当週demand Sと明示的に入力されたsupply COを候補追加する。COを物として
  払い出さず、期首完成品・既生産IDを候補から除く。
- 期首完成品IDと当該runで完成したIDの集合を保持し、一度だけ完成させる。
  同一需要IDを異なる注文に使い回さない既存Demand Anchored前提に限定する。
- cap_hardは現行と同じく正値のみ有効、整数部分を当週完成上限とする。
  0は無制限、0.1は整数0として閉鎖。能力枠のあるkitだけ部材払出とP追加を行う。
- 能力で待機したready kit数を `kitting_capacity_deferred` に
  (node_id, week_label, count) として記録する。週別待機数であり固有Lot数ではない。
  sealedやCOをここから追加せず、COは既存の `_process_node` に任せる。
- cap_softは既存 `_process_node` が実際の完成Pについて判定する。
- 全週のgate処理後に既存 `_process_node` がI+PとCO+Sを照合する。
  S予定を保持しactual_sへ実出荷を記録。既存完成品IDを全期間覚えることで、
  今回は共有の週次出荷処理を分割・複製する必要がない。
- 期末未完成はYard I、要求は最終週CO/Sとshortfallに残る。
  最終週の新規不足は翌週CO欄がないためshortfallも確認する。

## 受入・互換性

通常／遅着／能力待ち後追い／完成品とCO／重複生産防止／当週要求との競合／
soft／閉鎖／期末不足をUnitで確認。CSV→実capacity loader→ノード→gateの
Integrationと既存EV/BOM Integration、13 goldenを実行する。
golden差分が出た場合は原因を調べ、正本は更新しない。
非Yard通常PSI、push/push_sub、Backward、PPC、Yard期首在庫の意味は変更しない。

## 扱わないもの

同一IDの複数注文、重複する外部完成供給の一般的解消、加工中WIP、
消費連動補充、TW制御、新capacity軸、GUI。今回のコードレビューは担当AIの
自己レビューであり、別担当者の独立レビュー完了を意味しない。


````
