# LOVEM on WOM v0.2 への追加フィードバック：現行 PPC の入口（段階 D の前提）

- 宛先：GPT-6 Astra君
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 対象：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`
- ブランチ：`wom-v1r5m1_cap_trial`
- 扱い：段階 A〜C の範囲は変えない。段階 D（数量→金額）の設計に入る前に反映してほしい事実。

v0.2 で、Windows の matplotlib／Tk 描画（LineCollection）、`psi_intervals.jsonl` による区間保存、ev-thailand を最初の1モデルとすること、の3点が採用されたことを確認しました。ありがとうございます。

以下は、その3点とは別に、段階 D の前提として共有したい事実です。

## 現行 PPC の入口（Claude君がコードで確認）

`wom/ppc/ppc_psi_bridge.py` の処理は次のとおりです。

- 売上の起点は **leaf_out ノードだけ**。
- その `psi4supply[w][S]`（予定の S）の件数 × cpu_size を、channel×週で1行に集約する。実出荷（`_actual_s`）ではない。
- lot_id は `PSI-{product}-{channel}-{week}` という合成名になり、**元の Lot_ID は失われる**。

大杉さんの原則「全ノードで、出荷した Lot_ID の数 × Lot 単価」とは、上の3点で異なります。Trial-02 §7 の 9,293 lot が PPC に計上されることも、Explicit Closure の SE1（Cookie で供給が 1,450 lot 減っても PPC が不変）も、この入口で説明できる見込みです。

## 段階 D への反映のお願い

1. §10.2 の `existing_ppc` の定義を、上の事実にもとづいて書く（起点ノード、予定 S、集約単位、Lot_ID の喪失）。
2. 中間ノードの金額が、leaf_out の数量を祖先ノードへさかのぼって配ったもの（`wom/ppc/ppc_runner.py` の ancestry の処理）かどうかは、Claude君は静的に読んだだけで未確認です。段階 D の接続調査で確認してください。
3. `supplied`（実出荷数量にもとづく額）と `existing_ppc` の差が、上の3点のどれに由来するかを分けて示せるようにしてください。PPC をどう直すかは、この差の実測を見てから大杉さんが判断します。
