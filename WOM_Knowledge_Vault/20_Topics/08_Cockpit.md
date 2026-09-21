# S1・S3とManagement Cockpit

状態: **出典に基づく編集要約。正式設計変更ではない。**

従来WOMAppと新CockpitAppは別の入口。S1で配分候補を比較し、S3で実行結果を確認する。設計書に載るS4等を、ページ名の存在だけで実装済みと判断しない。

機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## 根拠・実装・検証

- [[80_Sources/wom/cockpit/cockpit_app.py|wom/cockpit/cockpit_app.py]]
- [[80_Sources/wom/cockpit/frame.py|wom/cockpit/frame.py]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]
- [[80_Sources/wom/cockpit/s3_run.py|wom/cockpit/s3_run.py]]
- [[80_Sources/wom/cockpit/s3_view_model.py|wom/cockpit/s3_view_model.py]]
- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
