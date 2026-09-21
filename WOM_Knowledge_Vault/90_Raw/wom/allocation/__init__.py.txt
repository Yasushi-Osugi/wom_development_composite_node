# -*- coding: utf-8 -*-
"""
wom.allocation — ask_global_allocation（生産配分地形）モジュール

Planning Engine の外側で動作する Management 層の拡張。既存の保護コア
（backward_planner / forward_planner / plan_copy / plan_node / sc_tree /
push_pull）には一切触れない。配分比率空間を全数評価して利益地形を生成する。

設計正典：docs/design/ask_global_allocation_spec.md（v0r3）
実装依頼：requests/global-allocation-request-letter.md（Rev 3）
参照実装：tools/proto_terrain2.py（伝達式の解釈はこちらを優先）
"""
