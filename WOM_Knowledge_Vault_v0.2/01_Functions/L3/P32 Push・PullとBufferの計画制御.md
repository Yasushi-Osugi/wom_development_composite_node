---
function_id: P32
level: 3
tags: [wom, function, L3]
---
# Push・PullとBufferの計画制御

押込み・需要引き・Buffer配置の違いを明確にする。

**入力：** plan_mode、decoupling点、需要週、LT、Buffer条件。

**利用結果：** 供給配置・Buffer在庫・下流への供給。

**状態：** 限定実装・静的確認。実行保証の認定ではない。

**利用例・確認観点：** Bufferの週別P/I/Sと元需要IDを比較し、どの週のための前倒しか説明する。

**注意：** Kanban現場動作そのものは対象外。1週余裕だけで欠品ゼロを保証しない。TW1350の由来は未確認。

## 上位機能

[[01_Functions/L2/P3 組立と補充の制御|組立と補充の制御]]

## 下位機能

- [[01_Functions/L4/P32S Push・PullとBufferの計画制御の設計|Push・PullとBufferの計画制御の設計]]
