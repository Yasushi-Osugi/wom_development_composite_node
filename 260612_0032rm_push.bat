@echo off
cd /d "C:\Users\ohsug\WOM_V0R2M1_new_cockpit\WOM v1r0m0"

REM ステップ1: pycとoutputのトラッキングを解除
git rm -r --cached "wom/engine/__pycache__" --ignore-unmatch
git rm -r --cached "wom/gui/__pycache__" --ignore-unmatch
git rm -r --cached "wom/model/__pycache__" --ignore-unmatch
git rm -r --cached "wom/reports/__pycache__" --ignore-unmatch
git rm -r --cached "wom/plugins/__pycache__" --ignore-unmatch
git rm -r --cached output --ignore-unmatch

REM ステップ2: ソースファイルをステージ
git add .gitignore
git add wom/gui/app.py
git add wom/engine/backward_planner.py wom/engine/forward_planner.py
git add wom/engine/push_pull.py wom/engine/sc_tree_builder.py wom/engine/lane_assignment.py
git add wom/model/sc_tree.py wom/plugins/__init__.py wom/reports/output.py
git add "data/sample/rice-japan-2027-2028/"
git add data/sample/smartphone-legacy/edge_cost_master.csv data/sample/smartphone-legacy/node_master.csv data/sample/smartphone-legacy/route_master.csv

REM ステップ3: 確認（内容を見てからEnterで続行）
git status
pause

REM ステップ4: コミット
git commit -m "Phase B: per-node PSI & Cost chart, rice-japan master data, push-pull OT engine, warm-up period"

REM ステップ5: プッシュ
git push origin master

pause