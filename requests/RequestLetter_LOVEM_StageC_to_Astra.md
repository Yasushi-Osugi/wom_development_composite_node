# Request Letter：LOVEM 段階 C — 独立照合（legacy と identity の2つの run）

- 宛先：GPT-6 Astra君
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 種別：読み取り・照合のみ（core・データ・golden の変更なし、commit・push なし）
- リポジトリ／ブランチ：`Yasushi-Osugi/wom_development_composite_node` / `wom-v1r5m1_cap_trial`
- 基準：`a43163f`（LotIdentityFlow の commit）。ブランチが進んでいても混ぜない。
- 設計の正本：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md`（以下「設計書」）の §8・§11（Q01〜Q12）・§12.2 段階 C・§13.1
- 前提の決定：`docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md`（v1.2、以下「決定記録」）

---

## 1. 目的と位置づけ

段階 A・B（Code君）で、ev-thailand-2026 の全 Lot を観測して保存し、描画する道具ができました。その後、Forward を Lot_ID の同一性で一貫させる修正（LotIdentityFlow）が入り、方式が2つになりました。

| 方式 | 内容 |
|---|---|
| legacy | 変更前の動き。push のバッファは届いた順に出荷し CO を持たない（例外1）。Outbound のデカップリング点より下流は、P を需要 P のコピーで作る（例外2） |
| identity（既定） | push のバッファも Lot_ID で照合し CO を持つ。下流の P は親の実出荷。能力を超えた生産は ID を保ったまま翌週へ繰り延べる（決定記録 D1・D2・D4） |

本依頼では、**同じモデル・同じ需要を2つの方式で観測した run を、実装とは独立した checker で照合**し、次の2つを確かめます。

1. **legacy の不整合を、独立した規則で検出できるか。** 例外1・2を知らない checker が、legacy の run で FAIL を出し、その件数と場所が既知の事実と合うか。
2. **identity の run が、同じ規則で整合しているか。** Code君の自己検査（K1〜K6）とは別の方法で、同じ結論が出るか。出ない場合、それが WOM の不整合か、観測器の不備か、checker の規則の違いかを分ける。

Code君の報告（`docs/development/WOM_LotIdentityFlow_Report.md`）の数字は「reported」として扱い、確かめる対象にしてください。正しいと仮定しないでください。

段階 C の完了で一度区切ります。金額（Q10・Q11、段階 D）には広げないでください。

## 2. 独立性の約束（設計書 §11）

- checker は、`wom/lovem/`・`tools/lovem_*.py`・`tools/lot_identity_checks.py` の関数を import しない。run フォルダの原データ（`DATA_DICTIONARY.md` の形式）を自分で読む。
- WOM の業務規則を確かめるために `wom/engine/` のソースを読むのは構いません。ただし、判定のために WOM の関数を呼ばないでください。
- 業務規則の正本は決定記録 §1（基本ルール）と §1.3（状態の呼び方）です。コードの動きと食い違えば、決定記録を正として FAIL にし、報告してください。
- 規則を決める前に run の結果を見て、規則を結果に合わせないでください。§4 の fixture で規則を先に固めてから、実データに当ててください。

## 3. 入力

### 3.1 run フォルダ（大杉さんが作って ZIP で渡す）

同じコード（`a43163f`、dirty なし）で、方式だけを変えた2つの run を使います。手元の run_A（`17915af`＋dirty）と run_B_identity（`ac47d2f`＋dirty）は、コードの基準がそろっていないので使いません。

| run | 方式 | ZIP |
|---|---|---|
| run_C_legacy | legacy | `handoff_ev-thailand-2026_C_legacy.zip` |
| run_C_identity | identity | `handoff_ev-thailand-2026_C_identity.zip` |

各 ZIP の中身：`run/`（run フォルダ一式。`q12.json`・`se2_case.json`・`verify.json` を含む）、`DATA_DICTIONARY.md`、`REPRODUCE.md`、`SHA256SUMS.txt`。最初に SHA256SUMS を確かめ、manifest の `code_sha`・`dirty`・`lot_flow_mode` を記録してください。

### 3.2 参考（reported）

- `docs/development/WOM_LOVEM_StageAB_EVThailand_Report.md`（段階 A・B）
- `docs/development/WOM_LotIdentityFlow_Report.md`（§3 の K 検査、§5.4 SE2、§5.6〜§5.7 期末注文残と立ち上がり期、§6 LOVEM）
- `docs/development/WOM_ExplicitClosure_v1r5m0_Report.md` §6（SE2 の出典、168 lot）

## 4. 先に作るもの：小さな fixture（既知の正解）

設計書 §12.2 のとおり、実データの前に、checker の規則を小さな合成データで確かめます。run フォルダと同じ形式（DATA_DICTIONARY）で、手で正解が分かるものを作ってください。**多くは要りません。** 次の 8 つで足ります。

| # | 場面 | 正解 |
|---|---|---|
| F1 | 当週出荷 | 要求週に同じ ID が出荷 |
| F2 | 遅配 | 要求が CO に回り、後の週に同じ ID が出荷 |
| F3 | 期末注文残 | 期末まで CO に残る（「未達」ではなく期末注文残） |
| F4 | 早出し | そのノードの要求週より前に、その ID が出荷（基本ルールの違反） |
| F5 | 同数量・別 ID | 件数は要求と一致するが、別の ID が出荷（例外1の形） |
| F6 | 出所の無い入庫 | 子の P に、親が出荷していない ID が現れる（例外2の形） |
| F7 | 休業週の push | 物 X が I、要求 X が CO に同時にある。出荷した週に両方から消える（違反ではない） |
| F8 | 能力の繰り延べ | 能力を超えた lot が ID を保ったまま翌週に作られ、要求週に間に合えば遅配ではない |

判定の週は、**各ノード自身の要求週（そのノードの S の週）**です。市場の要求週ではありません（上流が LT の分だけ先に出荷するのは正常）。push_sub は要求を持たずに先へ送る方式なので、早出しの判定の対象外です。

## 5. 照合の項目

Q01〜Q09・Q12 を、2つの run のそれぞれに当ててください（Q08 は ev-thailand に Kitting が無いので、理由を付けて NOT_APPLICABLE。Q10・Q11 は段階 D なので NOT_APPLICABLE）。各項目の定義は設計書 §11 のとおりです。本依頼で特に見たいことを、項目ごとに書きます。

| Q | 特に見たいこと |
|---|---|
| Q01 観測範囲 | 全ノード・全週・全 ID の区間復元が state_digests と一致するか。期間外・未取得（`coverage.known_gaps`）の範囲 |
| Q02 元需要の保存 | 需要アンカー 63,240 件 ＝ 市場の当週出荷＋遅配＋期末注文残。legacy と identity の両方で成り立つか |
| Q03 ノード内の物量保存 | 前週 I＋入庫＝当週 I＋実出荷（CO は物量に足さない）。全ノード・全週 |
| Q04 ノード間の移動 | 親の実出荷と子の到着を ID・件数・LT・経路で対応付ける。期末の輸送中を別に数える。**legacy の leaf_out では、到着の記録が無い入庫がどれだけあるか**（段階 A では、出所の記録なしの入庫が 63,240） |
| Q05 出荷の根拠 | 実出荷した ID が、その週に物として（前週 I＋入庫）あったか。予定 S の複写だけで出荷したことにしていないか |
| Q06 要求週と実出荷週 | ノードごと・ID ごとに、当週出荷・遅配・期末注文残・早出しに分ける。legacy の push（Factory_Import_CN）の早出しの件数（Code君の報告では legacy 3,581、identity 0） |
| Q07 CO の連続性 | CO の持ち越し・新しい要求・充足の更新が整合するか。同じ ID が CO に2件以上ないか |
| Q09 休業・能力 | 休業週（capacity.csv の is_open=0、6 週）に実出荷が全 ID で 0 か。push の休業週の入庫を処理能力違反としていないか |
| Q12 観測の非干渉 | `q12.json` の証拠を確かめる。環境が許せば、観測 ON／OFF の再実行で確かめる（できなければ「証拠の確認のみ」と明記） |

### 5.1 SE2 の 168 lot（設計書 §12.2 段階 C の本題）

Factory_Import_CN、EVmaker_Import、2026-W38・W39（予定 S 150・150）。

- legacy：実出荷 132・0（差 18＋150＝168）。この 168 lot を、週ごとの数量の差と、ID の対応に分けて解いてください。どの ID が要求され、どの ID が代わりに出荷され（早出し）、要求された ID はどうなったか。設計書 §8.2 の `se2_weekly_reconciliation.csv`・`se2_id_reconciliation.jsonl` の形で出してください。
- identity：同じ 2 週の実出荷は 150・150（reported）。同じ形式で、要求された ID がそのまま出荷されたかを確かめてください。

### 5.2 立ち上がり期の要求（identity で見えるようになったもの）

Code君の報告 §5.7 では、Factory_Import_CN の CO に 400 件が全期間残り、そのうち市場 W09〜W13 の lot は計画期間の中で一度も作られていない、とされています。§5.6 では、期末注文残の大半を「計画期間の端（開始）」に分類しています。

- この 400 件（と ev-thailand の期末注文残 5,020 件）を、要求週・必要な生産週・実際の供給の履歴で、独立に確かめてください。
- 原因は断定しないでください。「計画期間の開始前に作るべきだった分」と履歴が合うかどうか、合わないものがあればその件数と例を示してください。

### 5.3 2つの run の比較

同じ需要アンカー（同じ Lot_ID の集合）なので、ID ごとに2つの run の状態を並べられます。

- ID ごとの状態（当週出荷・遅配・期末注文残）が、legacy から identity でどう変わったかの遷移表（例：legacy で当週出荷 → identity で期末注文残、の件数）
- 変わった ID が、どのノード・どの週で分かれたか（上位の例）

注意：Lot_ID の文字列が同じでも、2つの run で同じ意味だと決めつけないでください（設計書 §13.2）。今回は需要アンカーが同じ入力から作られていることを、`demand_anchors` のハッシュで確かめてから比べてください。

## 6. 判定の表し方

- status は `PASS`・`FAIL`・`UNKNOWN`・`NOT_APPLICABLE`。
- FAIL と UNKNOWN は、次のどれかに分けてください。
  - **WOM の不整合**（原因が特定できたもの。例外1・2など既知のものは、その名前で）
  - **観測器の不備**（取れていない記録があって判定できない）
  - **checker の規則の違い**（決定記録と Code君の検査で定義が違う、など）
- 件数は、ノード・週・ID の例を最大 5 件まで付けてください。全件は CSV に。
- 「物量が 100% 保存された」ことと、「要求への充足の対応が 100% 確かめられた」ことを区別してください（設計書 §13.1）。

## 7. 成果物

1. checker のコード：`tools/lovem_checker_c/`（fixture を含む。WOM の関数を import しない）
2. 照合結果：run ごとに `checks.csv`（設計書 §8.2 の形式）と、SE2 の2ファイル（§5.1）。置き場所は `docs/development/lovem/stageC/<run 名>/`。大きい CSV（1MB を超えるもの）は置かずに、件数と SHA-256 だけを報告書に書き、ファイルは大杉さんに渡す。
3. 報告書：`docs/development/WOM_LOVEM_StageC_Report.md`
   - 要約（2つの run の Q ごとの status 表を最初に）
   - fixture の結果
   - Q ごとの結果と分類（§6）
   - SE2 の 168 lot の解き方（legacy・identity）
   - 立ち上がり期の要求の確認（§5.2）
   - 2つの run の比較（§5.3）
   - Code君の報告（reported）と食い違った点
   - 観測器（段階 A）に足りなかった記録と、段階 D の前に足すべきもの
   - checker でできなかったこと・未確認

## 8. 守ること

- core・データ・golden・run フォルダを変更しない。commit・push はしない。
- 修正案は書かないでください。事実、分類、未確認を報告してください。WOM の不整合を見つけたら、その場所と証拠を示すところまでにしてください。
- 重箱の隅の検証に時間をかけないでください。**止める理由**（動作・数字・誤読に関わる）と、**申し送り**（潜在リスク・改善の余地）を分けて書いてください。
- 金額（Q10・Q11）と、ev-thailand 以外のモデルには広げないでください。

## 9. 大杉さんの準備（Astra君に渡す前に）

Windows の作業フォルダで、次を実行して 2 つの ZIP を作ります（それぞれ約 3 分）。

```powershell
cd C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial
git status --short
python -m tools.lovem_observe --model-dir data/sample/ev-thailand-2026 --out output/lovem/ev-thailand-2026/run_C_legacy --q12 --lot-flow-mode legacy
python -m tools.lovem_observe --model-dir data/sample/ev-thailand-2026 --out output/lovem/ev-thailand-2026/run_C_identity --q12 --lot-flow-mode identity
python -m tools.lovem_handoff --run output/lovem/ev-thailand-2026/run_C_legacy --out output/lovem/handoff_ev-thailand-2026_C_legacy
python -m tools.lovem_handoff --run output/lovem/ev-thailand-2026/run_C_identity --out output/lovem/handoff_ev-thailand-2026_C_identity
```

- 最初の `git status` で、`wom`・`tools`・`data` に変更が無いこと（Obsidian の Vault だけ）を確かめてください。変更があると、manifest が dirty になります。
- できた `output/lovem/handoff_ev-thailand-2026_C_legacy.zip` と `..._C_identity.zip` を、本書と一緒に Astra君に渡してください。
