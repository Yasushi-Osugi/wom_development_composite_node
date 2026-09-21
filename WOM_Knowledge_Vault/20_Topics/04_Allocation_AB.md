# 需要配分A系統と調達分析B系統

状態: **出典に基づく編集要約。正式設計変更ではない。**

A系統wom/allocationは市場への配分と利益を扱う。B系統wom/visualizationは別の分析入力・目的を持つ。同名のMerit OrderやRegime Mapを同一APIとみなさない。Presentationにはその描画側を対応付ける。

機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## 根拠・実装・検証

- [[80_Sources/wom/allocation/merit_order.py|wom/allocation/merit_order.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]
- [[80_Sources/wom/visualization/merit_order.py|wom/visualization/merit_order.py]]
- [[80_Sources/wom/visualization/pareto_front.py|wom/visualization/pareto_front.py]]
- [[80_Sources/requests/Phase4_DesignMD_AllocationMeritRegime.md|requests/Phase4_DesignMD_AllocationMeritRegime.md]]
