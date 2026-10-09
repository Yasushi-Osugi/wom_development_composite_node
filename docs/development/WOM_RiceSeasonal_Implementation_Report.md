# Rice 季節供給・玄米保管・精米の本実装　報告

- 依頼書：`requests/RequestLetter_RiceSeasonal_Implementation_to_CodeKun.md`（§8.1・§8.2 の Owner の決定を含む）
- **追加の依頼（2026-10-09）**：`requests/RequestLetter_RiceSeasonal_PolishAdvance1_to_CodeKun.md`（精米の前倒し 1 週・報告の開始週を一か所に・Flow Check 表 2 の報告期間）。結果は **§13**。本書の数字は前倒し 1 週の結果に更新した（0 週の値は §13 の比較の表）。
- 前提：`docs/design/drafts/WOM_Rice_Seasonal_Model_Design_v0.1.md`、`docs/development/WOM_Rice_Seasonal_Definition_Report.md`（Sol 君の試作）
- 実装：Code君（Claude Code, Windows）、2026-10-08
- リポジトリ：`Yasushi-Osugi/wom_development_composite_node`、ブランチ `wom-v1r5m1_cap_trial`
- **着手時の SHA：`26a1e8eb7bc2f899246168a60c8f480857a0b614`**（依頼書の基準と同じ）。着手時の作業ツリーには Sol 君・Claude 君の未コミットの追加（試作・依頼書・設計案・Start Here の修正）があり、そのまま土台にした。
- **保護対象のコアは変えていない。** `wom/engine/hook_bus.py`（コアではない）を 1 か所直した（§9.1）。
- **元の Rice・HarvestBatch・canonical golden は変えていない。** commit・push・PR はしていない。
- 付表・図：`docs/development/rice_seasonal/`

本書は「観測結果／コードで確かめたこと／解釈／未確認」を分けて書く。

---

## 0. 受入のまとめ

| ID | 検査 | 結果 |
|---|---|---|
| K-R1 | 手計算の週・ID・物量・W53・玄米 I が一致。要求週を書き換えない | **合**。新しいプラグインを headless の計画に入れて再現（§2） |
| K-R2 | 全実出荷の ID／出現数が上流と LT で照合可能。期首合成 ID 0、早出し 0、不正重複 0 | **合**。1 ID の検算と移行用コピーの全 236,937 ID（§5.3） |
| K-R3 | 資源×週・年産上限を実績から独立に数え直す。週の在庫ピークも超えない | **合**。超過 0（§5.4） |
| K-R4 | 収穫量不足・精米能力不足・保管不足・保存年齢・計画開始端を別条件で再現。残る ID を出す | **合**（§6） |
| K-R5 | 二品目の共用精米を一度だけ制約 | **合**（§6、移行用コピーでも精米センターが共用の上限で止まる週がある：前倒し 1 週で 28 週） |
| K-R6 | 歩留まりで玄米／精米／その他の産出が保存。kg と需要 lot 相当の件数を混同しない | **合**（§5.6） |
| K-R7 | 上位計画の後に能力を変える負例で Forward が不足を返す | **合**（§6） |
| K-R8 | 観測 ON／OFF 一致、LOVEM の actual_ship と全件 1 対 1、区間復元 | **合**。snapshot 一致、actual_ship 988,470 件が全ノードで 1 対 1、区間の照合は全 10 snapshot・264 セル・12,069,376 区間で不一致 0（セルごとの独立照合、§5.8） |
| K-R9 | plugin OFF で 13＋legacy 3 golden が一致、元 Rice／HarvestBatch が不変、GUI／headless の同一条件の比較 | **合**。全テスト 818 passed／3 skipped（単独）、元のファイル不変、GUI と headless の結果が一致（§8・§11） |
| K-R10 | 通常 Rice 移行後の市場要求 ID 全集合、年産別の消費／残在庫、実出荷ベースの集計 | **合**（§5） |

---

## 1. 何を作ったか

| 種類 | ファイル | 内容 |
|---|---|---|
| 上位の層 | `wom/capacity_layer/rice_seasonal.py`（新規） | 計画の木から経路を読み、各 ID に**収穫週 h と精米週 p の二つの日付**を選ぶ問題を作り、整数で解き、元の ID に展開し、内部の計画の位置として渡す。物量台帳・資源の使用量 |
| プラグイン | `wom/plugins/rice_seasonal.py`（新規） | `RiceSeasonalPlugin`（POST_BACKWARD、**既定 OFF**、`ALL_BUILTIN_PLUGINS` の最後）。**全品目を一度に**解く |
| 入力 | `rice_*.csv` 6 本（移行用コピーに置く） | 方針・レシピ・資源（単位つき）・資源の割当・週の能力と収穫カレンダー・年産上限 |
| 移行用コピー | `data/trial/rice-japan-2027-2028-seasonal/`（新規） | `tools/gen_rice_seasonal_migration.py` が元の Rice から作る（§4） |
| 道具 | `tools/gen_rice_seasonal_migration.py`、`tools/rice_seasonal_check.py`（照合）、`tools/probe_rice_seasonal_definition.py`（`--allow-head` を追加）、`tools/gui_generation_line_check.py`（Rice の結果も記録） | |
| テスト | `tests/test_rice_seasonal_layer.py`（新規 25 件） | |
| 修正 | `wom/engine/hook_bus.py`、`wom/plugins/capacity_layer.py` | プラグインの例外が黙って握りつぶされる件（§9.1） |

Sol 君の試作（`rice_trial.py`・試作 22 件のテスト・1 ID の検算データ）はそのまま残した（試作 22 件は緑）。

---

## 2. A — 1 品目・1 ID を同じ手計算で再現（K-R1）

まず試作 22 件をそのまま実行：**22 passed**（Windows、scipy 1.13.1。Sol 君は Linux・scipy 1.17.0）。probe は `--allow-head`（§8 で許可）を足し、今の HEAD で Sol 君の 3 条件（plain・serial・seasonal）の結果を再現した（`output/rice_seasonal/A_probe/`）。

次に、**新しいプラグインを headless の計画（CSV → 実ローダ → 木 → Backward → プラグイン → Forward）に入れて**、手計算の正本 `scenario.json` の `expected` と照合した（`test_k_r1_one_id_hand_calculation_through_the_plugin`。期待値は変えていない）：

| 対象 | 手計算 | 結果 |
|---|---|---|
| 市場 ID | Koshihikari:KANSAI:2027-W01:00001、1 件 | 同じ（元の要求のまま） |
| 収穫／倉庫入庫／払出し／精米 | 2026-W43 / W45 / W50 / W52 | 同じ |
| DC／販売 | 2026-W53 / 2027-W01 | 同じ（W53 を含む） |
| 玄米の期末 I | W45〜W49 の 5 週、100/9 kg | 同じ（倉庫の I にその ID だけ、5 週） |
| 精米の物量 | 10 kg、その他の産出 10/9 kg | 同じ（Fraction で検算）。玄米 kg 週 500/9 |
| 市場 | 当週 1・遅配 0・早出し 0・期末注文残 0 | 同じ |
| 供給の系列 | source 以外の P＝上流の実出荷＋LT、期首在庫 0 | 照合の誤り 0、`opening_inv_counts` 空 |

> 窓の意味の違い（記録）：Sol 君の `max_harvest_advance_weeks=13` は「収穫から要求まで」。本実装の `harvest_lookback_weeks` は Owner の決定（§8.1-5「52 週＋経路の LT」）に合わせて「経路の LT を除いた分」。検算の経路の LT は 1+1+2+1+1=6 週なので、同じ窓は 7。テストではこう換算した。

---

## 3. B — Rice の上位の層とプラグイン

### 3.1 二つの日付と経路

- 経路は計画の木から読む：市場 → DC → 精米 → 玄米倉庫 → SP（仮想）、集荷（InBound の根）→ 田（leaf_in 1 つ）。これ以外の形（分岐した InBound、bom_qty≠1、ss_days≠0）は `RiceTreeError` で止める。
- 1 ID の時刻（`Timing`）：収穫 h（田の P・出荷）→ 集荷 c（＝SP）→ 倉庫の到着 a →（保管）→ 払出し b → 精米 p → DC → 市場の到着。**休業の週に届いたものは次に開いている週に処理する**（Forward の Step 0-closure と同じ規則）。精米週 p は、市場の到着が要求週に間に合う最も遅い開いている週（精米の前倒し 0 週のとき）。b＝p−（倉庫→精米の LT）。
- 候補：要求ごとに、遡及の窓（収穫から要求まで ≤ 52＋経路の LT）・保存年齢（b−a ≤ 52）に入る収穫週 h。

### 3.2 資源と単位（§2・§3）

| 役割 | 予約する週 | 単位 |
|---|---|---|
| 収穫・集荷・倉庫の受入れ・精米 | h・c・a・p | 玄米 kg／週 |
| 玄米の保管 | [a, b]（週内のピーク、保守的） | 玄米 kg（在庫） |
| DC・市場 | DC の週・市場の到着の週 | 精米 kg／週 |
| 年産 | 作期ごとに 1 本 | 玄米 kg |

- 1 lot＝精米 `white_kg_per_lot`、玄米＝それ÷歩留まり。PSI の件数は 1 ID＝最終需要 1 lot のまま（cpu_size で ID を割らない）。
- 能力の値：空欄の既定値は不可（0 を書くか `unlimited` を明示）、0 は能力ゼロ、欠けた資源・週はエラー。lot で書いた能力は、その資源を使う品目のレシピが同じときだけ kg に換算する（違えばエラー）。役割と資源の種類（玄米 kg／週・精米 kg／週・在庫 kg）が合わなければエラー。
- 品目が共用する設備は、資源の割当で**同じ resource_id** を指すことで一つの制約になる（名前から推測しない）。

### 3.3 集約と解き方（規模の注意）

- 要求は（品目, 市場, 要求週）ごとに**集約**し、その要求の元の ID の列（市場の順）を持つ。変数は候補ごとの整数の lot 数。解いた後、元の ID の順に展開する（候補は収穫週の早い順に割り当て、残りの ID が未割当）。ID の消失・重複は展開のときに検査する。
- 移行用コピーの規模（実測、精米の前倒し 1 週）：要求 1,248、ID 236,937、候補 8,600、非ゼロ係数 290,540。問題の作成 0.5 秒、5 段の解法で計 約 3 秒、プラグイン全体で 約 5 秒（前倒し 0 週では候補 4,400・全体 約 2.5 秒）。1 ID ごとの変数にしていない。
- HiGHS の MILP で、各段を最適と証明して次の段へ（証明できなければ止める）：
  1. 要求週までに割り当てる ID 数（最大）
  2. 要求週の早い順（Σ 割当×要求週 を最小）— Owner の決定 2
  3. 同じ品目・同じ要求週の中で、市場の要求量に比例（最大剰余法の目標からの L1 の差を最小）— Owner の決定 2
  4. 精米の前倒し lot・週（最小）
  5. 玄米 kg 週（最小）
- LP の連続上界と整数の結果を分けて出す（移行用コピーでは 141,210.0 と 141,210 で一致）。分数の ID は出荷しない。

**端数の扱い（Owner の決定 2）**：同じ品目・同じ要求週で足りないとき、その週に割り当てられた総数を、市場の要求量に比例して分ける。各市場の正確な取り分の整数部分を先に配り、残りを小数部分の大きい順に 1 つずつ配る（最大剰余法）。同じ小数部分なら要求量の大きい市場、それも同じなら市場の名前の順。目標どおりに配れない週（経路の LT の違いで、ある市場にはまだ届かない週など）は、目標からの差の合計が最小になるように配る。

### 3.4 共同計算点（フックの注意）

- 現行の計画は、品目ごとに Backward → POST_BACKWARD → copy → Forward を終えてから次の品目へ進む。共用の精米を一度だけ制約するため、プラグインは**最初の品目の POST_BACKWARD で全品目の問題を一度に解き**、各品目の POST_BACKWARD ではその品目の内部の位置だけを書く。
- 市場の需要を変えるのは PRE_PLAN（Holiday Calendar の需要の倍率）で、需要の ID は計画の前に全品目分作られるので、最初の POST_BACKWARD の時点で全品目の市場の要求は確定している。各品目の位置を書く前に、その品目の市場の要求が共同問題で使ったものと同じかを照合し、違えば止める。
- `ALL_BUILTIN_PLUGINS` の**最後**に登録したので、同じ POST_BACKWARD のほかのプラグイン（Holiday の閉鎖週の後処理など）の後に書く。後の品目の Backward は自分の品目のノードしか書かないので、先の品目の配置を上書きしない。

---

## 4. C — 通常 Rice の移行用コピー

`python -m tools.gen_rice_seasonal_migration` が `data/sample/rice-japan-2027-2028`（legacy、変えない）から `data/trial/rice-japan-2027-2028-seasonal/` を作る（作り直しても README 以外は 1 バイトも変わらないことを確認）。

| ファイル | 変更 | 根拠 |
|---|---|---|
| planning_config.csv | lot_flow_mode を identity に | §1 C |
| capacity_plan.csv | 稲作田の非収穫週 0.1 → 0。精米センターのエンジンの上限を品目共用の値（東 1,300・西 1,000）に。2028-W52 の行を追加（元は W51 まで＝W52 は上限なしだった） | §3「0.1 の整数化に依存しない」、§8.1-7 |
| node_cost_master.csv | 精米センターから先の 16 行 | §8.2 |
| sku_master.csv | unit_cost・selling_price（8 行）、note 列 | §8.2 |
| rice_seasonal_config.csv | 遡及 52 週（＋LT）、保存 52 週、**精米の前倒し 1 週まで**（2026-10-09 変更） | §8.1-5、追加の依頼 |
| vc_config.csv（新規） | `report_start` = 2027-W01 だけ。**報告の開始週の正典**（World Map・Value Chain・Flow Check・Rice の層が同じ値を読む） | §8.1-6、追加の依頼 作業 5 |
| rice_recipe.csv | 精米 3,000 kg／lot、歩留まり 0.9 | §8.1-3・4 |
| rice_resources.csv・rice_resource_map.csv | 精米センター東・西は**品目共用の一つの資源**（1,300・1,000 lot／週）。玄米倉庫・集荷・DC・市場は「上限なし」を明示 | §8.1-7 |
| rice_resource_capacity.csv・rice_crop_limit.csv | 収穫週と週の能力は今の capacity_plan.csv の値。年産上限＝収穫週の能力の合計 | §8.1-1（データは直さない） |

- HarvestBatch は使わない。プラグインは Holiday Calendar・Buffering Stock・Capacity Override（後の 2 つは入力が無く何もしない）＋ Rice Seasonal。
- 精米センターのエンジンの上限（品目ごとに 1,300・1,000）は、品目の合計の制約を持たない。品目の合計は上位の層が一つの資源で守り、実際の P から数え直して確かめた（§5.4）。
- **年産上限は「週の能力の合計」と同じ値にした。** §2 は「年産上限は週の能力の単純な合計とは独立」と言うが、独立の業務値は決まっていない（§8.1-1「データは直さない」）。§5.5 のとおり、今の値では年産上限は効いていない（週の収穫能力が先に効く）。

---

## 5. 移行用コピーの結果（K-R2・K-R3・K-R6・K-R10）

`python -m tools.rice_seasonal_check --model-dir data/trial/rice-japan-2027-2028-seasonal --out <dir> [--lovem]`。上位の層の割当ではなく、**Forward の実出荷から数え直した**。付表 `docs/development/rice_seasonal/`。

### 5.1 市場（元の要求 ID 全集合 236,937 件）

| 品目 | 期間 | 当週出荷 | 遅配 | 早出し | 期末の注文残 |
|---|---|---:|---:|---:|---:|
| コシヒカリ | 助走（2026） | 7,740 | 0 | 0 | 52,163 |
| | 報告（2027-W01〜） | 93,874 | 0 | 0 | **28,556** |
| ゆめぴりか | 助走（2026） | 2,934 | 0 | 0 | 15,006 |
| | 報告 | 36,662 | 0 | 0 | **2** |
| 合計 | | 141,210 | 0 | **0** | 95,727 |

- 上位の層の割当と実出荷は 1 件ずつ一致（割り当てた ID はすべて要求週に出荷、割り当てられない ID はすべて期末注文残。食い違い 0）。期末の注文残は、元の要求の ID・要求週のまま残る（消したり、別の週の新しい ID に置き換えたりしない）。
- 全 ID の一覧（品目・市場・ID・要求週・期間・結果・出荷週・収穫週・作期・倉庫の入出庫・精米週・未割当の理由）：`market_ids.csv.gz`。

### 5.2 不足の原因の切り分け（反事実の再計算）

上位の問題の資源の上限を外して解き直した（`shortage_decomposition.json`）：

| 条件 | 報告期間の不足 コシヒカリ | ゆめぴりか | （参考：前倒し 0 週） |
|---|---:|---:|---|
| そのまま | 28,556 | 2 | 28,578・2 |
| 精米センターの上限なし | 28,556 | 2 | 28,556・2 |
| 年産上限なし（週の収穫能力はある） | 28,556 | 2 | 28,578・2 |
| 週の収穫能力なし（年産上限はある） | 28,556 | 2 | 28,578・2 |
| 収穫（週・年産）とも上限なし | 312 | 25 | 8,101・2,052 |
| すべて上限なし | **0** | **0** | 0・0 |

- **コシヒカリの報告期間の不足 28,556 は、すべて収穫量（46,500 lot／年＜需要）による。** 精米の前倒しを 1 週まで許したので、精米センターによる不足（0 週のときの 22 lot）は無くなった。週の能力と年産上限は同じ値なので、どちらか一方を外しても変わらない。
- 収穫を無制限にすると、共用の精米センター（東 1,300・西 1,000）が効き始めるが、前倒し 1 週のもとでは不足はコシヒカリ 312・ゆめぴりか 25 にとどまる（0 週では 8,101・2,052）。
- **助走の年の不足（コシヒカリ 52,163・ゆめぴりか 15,006）は、すべて「候補なし」**：2025 年産の収穫は計画期間の外で、2026 年の収穫が届くまでの要求に割り当てられる収穫が無い（§8 の補足 3。匿名の期首在庫で埋めていない）。
- ゆめぴりかの報告期間の 2 lot は、需要の倍率（年末の ×1.35 など）で年の需要が年産をわずかに超える分。

### 5.3 出荷の照合（K-R2）

全ノード・全週で、次を実出荷から数え直した（`flow_identities`）：

| 検査 | 誤り |
|---|---:|
| I＝（前週の I＋P）−出荷 | 0 |
| CO＝（前週の CO＋S）−出荷 | 0 |
| 出荷に供給がある・要求がある | 0 |
| P＝上流の実出荷＋LT（休業の週の受入れは次に開いている週へ移す） | 0 |
| 同じ ID の不正な重複 | 0 |
| 需要に無い ID の出荷・期首の合成 ID（OI_） | 0・0 |
| 割り当てた ID の田・精米の実出荷の週が計画と一致 | 不一致 0 |
| Forward の能力による繰り延べ | 0 |

### 5.4 資源（K-R3、実出荷・実際の P から kg で数え直し）

- 収穫（週）・作期（年産）・精米センター東西（両品目の合計）・玄米倉庫（期末 I と週内のピーク＝前週末 I＋今週 P）を数え直した。**上限を超えた資源×週は 0。** 精米センター東は 1,300 lot（4,333,333 kg）ちょうどの週がある（共用の上限で止まっている）。
- 精米の使用量の合計：計画 470,700,000 kg ＝ 実際 470,700,000 kg。精米センターが共用の上限ちょうどの週は 28 週（前倒し 0 週では 12 週）。
- 玄米倉庫の週内のピーク（新潟）：最大 147,086,667 kg（44,126 lot 相当、2026-W45・2027-W45）。上限なしを明示した資源なので比較はしない（値は付表 `resource_usage.csv`）。

### 5.5 年産別の消費と残り（K-R10）

| 品目 | 作期 | 年産上限（lot） | 収穫（lot） | 助走の需要へ | 報告の需要へ | 収穫しなかった分 |
|---|---|---:|---:|---:|---:|---:|
| コシヒカリ | 2026 | 46,500 | 46,500 | 7,740 | 38,760 | 0 |
| | 2027 | 46,500 | 46,500 | 0 | 46,500 | 0 |
| | 2028 | 46,500 | 8,614 | 0 | 8,614 | 37,886 |
| ゆめぴりか | 2026 | 18,200 | 18,200 | 2,934 | 15,266 | 0 |
| | 2027 | 18,200 | 18,200 | 0 | 18,200 | 0 |
| | 2028 | 18,200 | 3,196 | 0 | 3,196 | 15,004 |

- 計画は需要に紐づく分だけを収穫する（需要の ID が無い収穫はしない）。2028 年産は計画期間の終わり（2028-W52）までの需要の分だけ。
- 2026 年産の多くは報告期間（2027 年）の需要へ回る（年をまたぐ保管）。

### 5.6 報告の期首在庫（2026-W53 の週末、収穫の履歴から）

| 品目 | 作期 | 状態 | lot | kg |
|---|---|---|---:|---:|
| コシヒカリ | 2026 | 玄米倉庫 | 34,142 | 113,806,667（玄米） |
| | 2026 | 倉庫→精米の輸送中 | 1,685 | 5,616,667（玄米） |
| | 2026 | 精米の後（DC・市場への途中） | 2,933 | 8,799,000（精米） |
| ゆめぴりか | 2026 | 玄米倉庫 | 13,438 | 44,793,333（玄米） |
| | 2026 | 倉庫→精米の輸送中 | 951 | 3,170,000（玄米） |
| | 2026 | 精米の後 | 877 | 2,631,000（精米） |

すべて 2026 年産で、需要の ID に紐づく（匿名の期首在庫・OI_ の生成なし）。GUI の PSI List でも、玄米倉庫（新潟）の 2026-W53 の I は 34,142。

### 5.7 物量（K-R6）

収穫した玄米 470,700,000 kg ＝ 精米 423,630,000 kg ＋ その他の産出 47,070,000 kg（Fraction で 1 ID ずつ検算）。玄米は精米の週に台帳から出て、精米と玄米に同じ物量を二重に残さない。kg の台帳（`physical_ledger.csv`、品目×週の段階別の物量）と PSI の件数（需要 lot 相当）は別に持つ。その他の産出に金額は付けていない（§8.1-4）。

### 5.8 LOVEM（K-R8）

観測つきの計画（`python -m tools.rice_seasonal_check ... --lovem` が作る run フォルダ `output/rice_seasonal/C/lovem_on`）に対して、段階を分けて照合した（付表 `docs/development/rice_seasonal/lovem/`）。

| 照合 | 結果 |
|---|---|
| 観測 ON／OFF：snapshot（psi・ppc・forward・products・period） | すべて一致 |
| LOVEM の actual_ship イベントと、観測なしの計画の木の実出荷：(ノード, 週, ID) の多重集合 | 全ノード 988,470 件で 1 対 1（市場 141,210 件も 1 対 1） |
| 区間の照合（`tools/lovem_interval_check.py`）：元の PSI と区間データから、それぞれ独立に Lot_ID ごとの連続区間と出現数を求めて全件照合 | **全 10 snapshot、区間のあるセル 264・空のセル 312、不一致 0**。区間 12,069,376、出現数（ID×週）24,417,855。異常（同じセルの塊が二度出る・役割／数量が既定値でない）0。（前倒し 0 週の run でも同じ照合で不一致 0：セル 262、区間 12,049,335） |

**区間の照合のやり方（2026-10-09 の追加指示）**：

- モデルのコピーを観測なしで同じプラグインでもう一度計画し、observer と同じ時点（Backward の前・後、POST_BACKWARD のフックの後、copy の後、最後）で、**この道具自身のコード**で元の PSI から Lot_ID ごとの連続区間（I・CO：同じ出現数で続く週、P・S：週ごと）と出現数を求める。出現数は週の中の同じ ID の個数で、set で消さない。
- 同じ時点の区間ファイルを、セル（snapshot→node→層→バケット）の塊ごとに読み、(Lot_ID, 開始, 終了, 出現数) の多重集合と、ID ごとの出現数の合計（Σ 週数×出現数）を照合し、済んだセルは捨てる。全 snapshot の「ID×週」をメモリに展開しない。snapshot ごとに開始・終了・セル数・経過時間を出す（`summary.json`）、セルごとに区間数・ID 数・出現数・経過時間・結果を出す（`cells.csv`）。
- 所要時間：全体 267 秒（2026-10-09 07:49:23〜07:53:50、前倒し 1 週の run）。うち元の PSI から区間を求める処理 76 秒、照合 27 秒、残りは計画のやり直しと区間ファイルの読み込み。最大のセル（前倒し 0 週の run）はコシヒカリの final の Retail_KANTO の supply CO（期末の注文残の ID が長く CO に残る）：区間 30,579・出現数 3,192,549、4.3 秒。
- 小さな fixture（1 ID の検算データに ID を足したもの）で、新しい照合と、従来の週別に展開する照合（`wom.lovem.verify.verify_run`）がどちらも合格、区間ファイルを改ざん（出現数を 1 増やす・同じ区間を 2 行にする）するとどちらも不合格、で一致することをテストにした（`tests/test_lovem_interval_check.py`、4 件）。

**従来の照合（`verify_run`）を止めた記録**：Rice の run フォルダに対して `verify_run` を単独で実行したところ、1 時間 38 分（2026-10-08 22:33:54 開始、CPU 2,845 秒）経っても終わらず、コミット済みメモリ 8,163 MB（物理メモリ 7.4 GB を超え、ページングしていた）・最大ワーキングセット 2,936 MB だった。処理位置は外から読めない（進捗を出さない）。指示どおり、この検証プロセスだけを止めた（run フォルダ・完了した照合結果は残した）。`verify_run` は 1 snapshot の全セルを「週×ID」の Counter に展開してから照合するので、ID×週の出現数が 2,000 万を超える Rice ではメモリが足りない、と推定する（メモリの実測からの推定。プロファイルはしていない）。新しい照合では異常な遅さは残っていないため、1 セルでの計測（復元と照合の内訳）は上の数字のとおり。

> 記録：Holiday Calendar の需要の倍率（PRE_PLAN）は、市場に `HOL:` で始まる ID を足す（既存の機能）。これは上位の層が作る ID ではなく、元の市場の要求の一部として扱った（期首の合成 ID〔OI_〕・匿名の割当ではない）。

---

## 6. 単体・結合のテスト（K-R4・K-R5・K-R7）

`tests/test_rice_seasonal_layer.py`（25 件）。手計算の値は `scenario.json` から読む。

| 区分 | テスト | 内容 |
|---|---|---|
| K-R1・K-R2 | `test_k_r1_one_id_hand_calculation_through_the_plugin` | §2 の表。headless の計画（CSV → 実ローダ → プラグイン → Forward） |
| | `test_plugin_off_plan_cannot_assign_the_past_harvest` | プラグイン OFF では過去の収穫に割り当てられず注文残 |
| K-R4 | `test_k_r4_shortage_causes_keep_the_id`（5 条件） | 収穫なし／保管不足（10 kg＜100/9 kg）／保存年齢 4 週／遡及の窓 3 週／精米の週が能力ゼロ：どれも割当 0、元の ID が理由つきで残る |
| | `test_k_r4_mill_closed_week_can_use_an_earlier_milling_week_when_allowed` | 精米の前倒しを 1 週許すと W51 に精米（前倒し 1 lot・週） |
| | `test_k_r4_crop_season_limit_is_separate_from_weekly_harvest` | 週の収穫能力は足りても年産上限で 1 件だけ |
| | `test_k_r4_plan_start_edge_has_no_option` | 計画開始端：2026-W44 の要求には届く収穫が無い（候補なし） |
| 集約 | `test_aggregated_request_expands_to_original_ids_in_market_order` | 3 ID の要求で 2 lot 分だけ割当 → 市場の順の先頭 2 ID、残り 1 ID が未割当 |
| | `test_largest_remainder_split` | 最大剰余法 |
| K-R5 | `test_k_r5_shared_mill_is_one_constraint_across_products`・`..._plugin_solves_once_for_both_products` | 二品目が同じ精米資源（1 lot／週）なら 1 件、別資源なら 2 件。プラグインでも全品目を一度に解き、市場の結果と一致 |
| K-R6 | `test_k_r6_mass_balance_and_id_count` | 2 ID：精米 20 kg、その他の産出 20/9 kg、件数は 2 |
| K-R7 | `test_k_r7_capacity_changed_after_allocation_is_caught_by_forward` | 割当の後に精米の能力を 0 にすると、Forward が繰り延べ（1 lot）、当週出荷 0、早出し 0 |
| 休業 | `test_closed_dc_week_moves_the_lot_to_the_next_open_week` | DC が W53 休業：W52 精米では市場に W02 着で遅れるので、精米 W51・DC W52・市場 W53（要求の 1 週前、避けられない前倒し 1）。Forward の照合の誤り 0、当週出荷 |
| 入力 | `test_input_errors_stop`（3）・`test_missing_input_file_stops_the_plugin`・`test_role_with_the_wrong_resource_kind_stops`・`test_legacy_lot_flow_is_refused` | 既定値の無い能力・知らない単位・年産上限の欠け・入力ファイルの欠け・役割と資源の種類の不一致・legacy の計画、で止まる |
| 登録 | `test_plugin_is_off_by_default_and_registered_last` | 既定 OFF、最後 |
| K-R10 | `test_k_r10_migration_copy_regression` | 移行用コピーの数値（§5.1）と照合の誤り 0 |

> テストの訂正（記録）：(1) 3 ID の集約のテストは、最初、精米・倉庫・市場の能力が 1 lot／週のままで「2 件割当」を期待していた。精米の前倒し 0 のため 1 件しか入らないのが正しく、能力を広げて年産上限だけが効く形に直した。(2) 休業のテストで、一度計画した木で Forward をやり直すと、`copy_demand_to_supply` が需要の無い週の供給を消さないため、前の計画の S が残って照合の誤りが出た。テストの側で供給を空にしてからやり直すようにした（新しい計画は供給が空から始まるので、計画そのものの問題ではない）。

---

## 7. 試作の結果との関係

| | Sol 君の試作（`rice_trial.py`） | 本実装（`rice_seasonal.py`） |
|---|---|---|
| 変数 | 1 ID ごと（0／1） | 要求（品目×市場×要求週）ごとの整数量 → 元の ID に展開 |
| 品目 | 経路を手で宣言 | 計画の木から読む。全品目を一度に |
| 休業 | 未対応（エラー） | Forward と同じ規則（次に開いている週） |
| 入力 | 検算用の値をコードで | `rice_*.csv`（単位・未設定・0 を区別） |
| 目的 | 割当数 → 精米の前倒し → 玄米 kg 週 | 割当数 → 要求週の早い順 → 週内の比例 → 精米の前倒し → 玄米 kg 週 |
| エンジンへ | 隔離した検算用の木 | プラグイン（GUI・headless） |

試作の 22 件のテストは変えずに緑。1 ID の手計算は、試作と本実装の両方で同じ結果。

---

## 8. GUI と headless の同一条件の比較（K-R9 の一部）

`python -m tools.gui_generation_line_check --model-dir <移行用コピーのコピー> --out <dir> --layer off --plugins holiday_calendar,buffering_stock_optimizer,capacity_override,rice_seasonal`（`python -m main` と同じ窓、画像は Win32 の PrintWindow）：

| | GUI | headless |
|---|---:|---:|
| 当週出荷 | 141,210 | 141,210 |
| 遅配・早出し | 0・0 | 0・0 |
| 期末の注文残 | 95,727 | 95,727 |
| Flow Check 表 2「うち報告期間」 当週出荷・注文残 | 130,536・28,558 | 130,536・28,558（93,874＋36,662、28,556＋2） |
| World Map の帯 | 報告の開始週 2027-W01（vc_config.csv） | — |
| Run Planning Engine → PPC の完了 | 例外なし | — |
| Network の図、PSI List（全 24 ノード） | 例外なし | — |

画像：`docs/development/rice_seasonal/gui/`（玄米倉庫・精米・田・市場の PSI List、`flow_check.png`、`worldmap.png`）。報告の開始週の無いモデル（1 ID の検算データ）では、表 2 の列と要約の行は前と同じ（「うち報告期間」は出ない）ことも GUI で確かめた。

---

## 9. 副作用・判断を仰ぎたいこと・申し送り

### 9.1 見つけて直したもの：プラグインの例外が黙って握りつぶされる

`HookBus.fire()` は、プラグインの例外を表示するだけで計画を続けていた。Rice Seasonal で入力が欠けている・legacy の計画、などで止まるはずが、**プラグインの配置の無い（元の Backward の）計画がそのまま出る**ことを、テストで見つけた（前の依頼の Capacity Layer も同じ）。`fatal_errors = True` を宣言したプラグインだけ、例外で計画を止めるようにした（`wom/engine/hook_bus.py`、コアではない）。Rice Seasonal と Capacity Layer に宣言した。ほかのプラグインは今のまま（golden に影響なし）。

### 9.2 判断を仰ぎたいこと

1. **元の Rice とその golden の置き換え**：移行用コピーの受入と、大杉さんの差分の確認の後（依頼書 §1 C）。置き換えるときは、README・決定記録・CLAUDE.md・`docs/WOM_Start_Here.md` §3・§7 を同時に更新する（§6）。今回は Start Here を変えていない。
2. **年産上限の業務値**：今は週の収穫能力の合計と同じ値。別の値（気象・作付面積から）を持つなら、`rice_crop_limit.csv` を差し替える。
3. ~~精米の前倒し 0 週と休業~~ → **前倒し 1 週まで（Owner の決定、2026-10-09）**。精米による不足 22 lot は 0 になった（§13）。前倒しは解き方の 4 段目で最小にするが、2・3 段目（要求週の早い順・週内の比例）を良くするためにも使われ、休業の前の数週に広がる（約 19,400 lot）。Owner の決定で、この順番（比例を優先）のままとした。

### 9.3 次の設計へ渡すもの（今回は扱わない）

- 収穫年ごとの価格と古い在庫の評価損（§8.2）。今は 1 本の価格。
- その他の産出（ぬか等）の売上・廃棄費・金額台帳への接続（§2）。物量は `physical_ledger.csv` に記録した。
- Forward の kg 変換（歩留まり）は実装していない。PSI は需要 lot 相当の件数で、kg は上位の層の物量台帳で別に持つ。
- **LOVEM の `wom.lovem.verify.verify_run` は大きなモデルでメモリが足りない**（§5.8。1 snapshot の全セルを週×ID に展開する）。Rice は `tools/lovem_interval_check.py`（セルごと）で照合した。`verify_run` 自体と LOVEM の受入の手順をセルごとの方式に替えるかは、LOVEM 側の判断（今回は `verify_run` を変えていない）。
- 共用の精米の上限は、エンジン（Forward）では品目ごとにしか確かめられない。品目の合計は上位の層と、この照合の道具（実際の P からの数え直し）で確かめる。

### 9.4 未確認

- 大杉さんの実機での確認（§10）。

---

## 10. `python -m main` で確かめる手順

| # | 操作 | 期待する表示 |
|---|---|---|
| 1 | `data/trial/rice-japan-2027-2028-seasonal` を読み込み、Plugins で Holiday Calendar と **Rice Seasonal（収穫・玄米保管・精米）** を ON（Harvest Batch は OFF）にして Run Planning Engine | エラーなく終わる。コンソールに `[RiceSeasonal] joint problem: 1248 requests, 236937 IDs, 8600 options; served 141210, unallocated 95727` と、未割当の警告 1 行（`Koshihikari report 28556, Koshihikari warmup 52163, Yumepirika report 2, Yumepirika warmup 15006`） |
| 2 | Network → PSI List で `OUT:dad:Genmai_Souko_Niigata:Koshihikari` | 2026-W43〜W45 に P 15,500、I が積み上がり、毎週の払出しで減る。2026-W53 の I は 34,142 |
| 3 | `IN:leaf_in:Tanbo_Niigata:Koshihikari` | 収穫は W41〜W43 だけ（CapHard 15,500）、ほかの週は CapHard 0 |
| 4 | Network → Flow Check の表 2 | 早出し 0、遅配 0。注文残はコシヒカリ 80,719、ゆめぴりか 15,008（合計 95,727）。**「うち報告期間」の列**：コシヒカリ（Σ 製品）当週出荷 93,874・注文残 28,556、ゆめぴりか 36,662・2。上の要約の行に「うち報告期間（2027-W01〜）：当週出荷 130,536・期末注文残 28,558」 |
| 4b | World Map | 帯に「報告の開始週 2027-W01（vc_config.csv）」 |
| 5 | Rice Seasonal を OFF にして Run Planning Engine | 過去の収穫に割り当てられず、注文残が大きく増える（プラグインの効果の比較） |

---

## 11. 全テスト

- `python -m pytest tests/ -q -p no:cacheprovider`：**818 passed／3 skipped、失敗 0**（2026-10-09、16 分 38 秒、**ほかの検査と並行させずに単独で実行**）。canonical golden 13 件＋legacy 3 件（plugin OFF）を含み、すべて一致。
- 実行の後、`data/sample/`・`tests/golden/`・`wom/engine/harvest_batch_plugin.py` に変更が無いことを `git status` で確かめた（元の Rice・HarvestBatch・golden は不変）。
- 記録：その前の 1 回（2026-10-08）は、LOVEM の照合（`verify_run`、8 GB 超）と並行して実行したため、`tests/test_lovem_observer.py` の 2 件がメモリ不足・OS のエラーで落ちた（812 passed）。単独で再実行して 6 件とも緑を確かめ、上の単独の全テストで確定した。

---

## 12. 成果物・再実行

| 種類 | 場所 |
|---|---|
| コード | `wom/capacity_layer/rice_seasonal.py`、`wom/plugins/rice_seasonal.py`、`wom/plugins/__init__.py`、`wom/engine/hook_bus.py`、`wom/plugins/capacity_layer.py`。追加の依頼：`wom/engine/report_start.py`（新規）、`wom/worldmap_ne/flows.py`、`wom/engine/flow_check.py`、`wom/gui/app.py`（Flow Check の表 2）、`tools/run_headless_from_folder.py`（Flow Check の CSV） |
| データ | `data/trial/rice-japan-2027-2028-seasonal/`（生成物） |
| 道具 | `tools/gen_rice_seasonal_migration.py`、`tools/rice_seasonal_check.py`、`tools/rice_seasonal_lovem_check.py`（snapshot・actual_ship）、`tools/lovem_interval_check.py`（区間のセルごとの照合）、`tools/probe_rice_seasonal_definition.py`（`--allow-head`）、`tools/gui_generation_line_check.py` |
| テスト | `tests/test_rice_seasonal_layer.py`（25 件）、`tests/test_lovem_interval_check.py`（4 件）、`tests/test_report_start.py`（5 件、追加の依頼） |
| 付表 | `docs/development/rice_seasonal/`（summary.json、market_ids.csv.gz〔全 ID〕、crop_year.csv、opening_stock.csv、physical_ledger.csv、resource_usage.csv、weekly_market.csv、shortage_decomposition.json、gui/） |

再実行：

```
python -m tools.gen_rice_seasonal_migration
python -m tools.rice_seasonal_check --model-dir data/trial/rice-japan-2027-2028-seasonal --out output/rice_seasonal/C --lovem   # 観測の run を作る（最後の verify_run は Rice では重い。下の 2 本で照合する）
python -m tools.rice_seasonal_lovem_check --model-dir data/trial/rice-japan-2027-2028-seasonal --run-dir output/rice_seasonal/C/lovem_on --skip-restore
python -m tools.lovem_interval_check --model-dir data/trial/rice-japan-2027-2028-seasonal --run-dir output/rice_seasonal/C/lovem_on --plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin --out output/rice_seasonal/C/interval_check
python -m pytest tests/test_rice_seasonal_layer.py tests/test_rice_seasonal_trial.py -q
python -m tools.probe_rice_seasonal_definition --out output/rice_seasonal/A_probe --allow-head
```

LOVEM の観測の run フォルダは大きいのでリポジトリに入れない（`output/rice_seasonal/C/lovem_on`、作り直せる）。

---

## 13. 追加の依頼：精米の前倒し 1 週・報告の開始週・表 2（2026-10-09）

依頼書：`requests/RequestLetter_RiceSeasonal_PolishAdvance1_to_CodeKun.md`。作業ツリーは未コミットのまま、その上で続けた。

### 13.1 精米の前倒しを 1 週まで（作業 1〜4）

`tools/gen_rice_seasonal_migration.py` の `max_polish_advance_weeks` を 1 にして移行用コピーを作り直した（CSV は手で直していない）。

| | 前倒し 0 週（前） | **前倒し 1 週（後）** |
|---|---:|---:|
| 当週出荷 | 141,188 | **141,210** |
| 遅配・早出し | 0・0 | 0・**0** |
| 期末注文残 合計 | 95,749 | **95,727** |
| うち コシヒカリ 助走／報告 | 52,163／28,578 | 52,163／**28,556** |
| うち ゆめぴりか 助走／報告 | 15,006／2 | 15,006／2 |
| 精米センターによる不足（上限なしとの差） | 22 | **0** |
| 前倒しした lot（要求に間に合う最も遅い精米週より 1 週早い） | 0 | 19,400（コシヒカリ 15,230・ゆめぴりか 4,170） |
| 精米後に市場で待つ在庫（市場の I の lot・週、DC は 0） | 1,696＋4,895＝6,591 | 23,621＋8,002＝31,623 |
| 精米の前倒し lot・週（Σ 要求週−市場の到着週） | 6,591 | 31,623 |
| 週内の比例の配分のずれ（目標との差の合計） | 5,368 | 2,992 |
| 玄米 kg 週 | 8,809,906,667 | 8,238,046,667 |
| 精米センターが共用の上限ちょうどの週 | 12 | 28 |
| 候補の数・プラグインの時間 | 4,400・約 2.5 秒 | 8,600・約 5 秒 |

（出典：`docs/development/rice_seasonal/adv_compare.json`、`adv0/`）

- **精米による不足 22 lot は 0 になった。** 残る報告期間の不足（コシヒカリ 28,556・ゆめぴりか 2）は収穫量だけによる（§5.2）。
- **市場の早出しは 0 のまま。** 前倒しで市場に早く着いた ID は、市場の在庫として要求週まで待ち、要求週に出荷される（市場の I が 6,591 → 31,623 lot・週に増えたのはこのため）。
- **前倒しの使われ方**：精米週ごとに数えると、GW（精米センター休業 W18–19）の前の W11〜W16、年末年始（DC 休業 W52–W01）と需要の倍率（W50–51 ×1.35）の前の W44〜W50 と W52、お盆（DC 休業 W33–34）の前の W30・W33 に集まる（品目×精米センター×週の内訳は `adv_compare.json` の `advanced_detail`）。休業の直前の週だけではなく、数週前まで広がる。
- **理由**：前倒しは解き方の 4 段目で最小にしているが、その前の 2 段目（要求週の早い順）・3 段目（週内の比例）を良くするために、精米週を 1 週ずらせる自由が使われる（比例のずれ 5,368 → 2,992）。依頼書の見込み「使うのは必要な週だけのはず」とは違った。
- **Owner の決定（2026-10-09）**：今の順番のまま（比例の配分〔決定 2〕を優先し、前倒しは 1 週の範囲で使ってよい）。参考に、前倒しを 2 段目（割当数の次）にした場合も解いた（`solve(..., advance_first=True)`、既定は False）：

| 解き方の順番 | 当週出荷 | 精米の前倒し lot・週 | 比例のずれ | 要求週の早い順（Σ 割当×要求週） |
|---|---:|---:|---:|---:|
| **今の順番**：割当数→早い順→比例→前倒し→玄米 | 141,210 | 31,623 | 2,992 | 13,787,648 |
| 参考：割当数→前倒し→早い順→比例→玄米 | 141,210 | 4,913 | 7,542 | 13,940,370 |

注文残の内訳はどちらも同じ（出典 `adv_order.json`）。

- 照合（作り直し）：flow identity の誤り 0、経路の不一致 0、資源の超過 0、需要に無い ID・合成 ID 0、早出し 0、Forward の繰り延べ 0。LOVEM：観測 ON／OFF の snapshot 一致、actual_ship 988,470 件が全ノードで 1 対 1、区間の照合 264 セル不一致 0（§5.8）。GUI と headless の結果が一致（§8）。
- テストの値（`tests/test_rice_seasonal_layer.py::test_k_r10_migration_copy_regression`）：前 当週出荷 141,188・注文残 95,749・コシヒカリ報告 28,578 → 後 141,210・95,727・28,556。1 ID の手計算（scenario.json、前倒し 0 週）は変えていない。

### 13.2 報告の開始週を一か所に（作業 5）

- 正典は `vc_config.csv` の `report_start`。読むのは `wom/engine/report_start.py`（新規）の一か所：World Map（`wom/worldmap_ne/flows.report_start_index` はここへ委譲、挙動は同じ）、Rice の層、Flow Check。Value Chain は今のまま、同じキーをマスターとして読む。
- Rice の層：`rice_seasonal_config.csv` に `report_start` があれば止める（「vc_config.csv に移す」と出す）。`vc_config.csv` に無ければ、World Map と同じく最初の非ゼロ需要週。
- 移行用コピーに `vc_config.csv`（`report_start,2027-W01` の 1 行だけ）を生成で置いた。**副作用の確認**：Value Chain の台帳は vc_* の 4 本（vc_config・vc_entity・vc_node_assignment・vc_price_rule）が揃ったときだけ作られるので、1 本だけでは今と同じく「台帳のマスターがありません」の表示のまま（ほかの vc_* は不要）。通貨などの値を仮に置くことはしていない。
- World Map の帯：「報告の開始週 **2027-W01（vc_config.csv）**」（GUI で確かめた。前は「2026-W01（最初の非ゼロ需要週）」）。

### 13.3 Flow Check の表 2 に報告期間（作業 6）

- 報告の開始週を `vc_config.csv` で決めているモデルだけ、表 2 に「うち報告期間 当週出荷」「うち報告期間 注文残」の列を足し、上の要約の行に「うち報告期間（開始週〜）：当週出荷 …・期末注文残 …」を足す。数えるのは、要求週が報告の開始週以後の ID。CSV の書き出し（GUI・headless の `--flow-check`）にも同じ列（`demand_report`・`on_time_report`・`backlog_end_report`）。
- 報告の開始週の無いモデルでは、表・要約の行・CSV とも前と同じ（列を隠す。テスト `test_flow_check_table_2_report_columns_only_with_a_report_start` と GUI で確認）。
- 移行用コピー：コシヒカリ（Σ 製品）当週出荷 101,614 のうち報告期間 93,874、注文残 80,719 のうち報告期間 28,556。ゆめぴりか 39,596 のうち 36,662、15,008 のうち 2。モデル全体 当週出荷 141,210 のうち 130,536、注文残 95,727 のうち 28,558。

### 13.4 テスト

- `tests/test_report_start.py`（新規 5 件）：vc_config.csv が一か所の正典・無いときの代わり、移行用コピーの World Map の帯の週が 2027-W01、rice_seasonal_config.csv に report_start があれば止まる、Rice の層が vc_config.csv の値を使う、表 2 の報告期間の列は報告の開始週があるときだけ（ほかの列は変わらない）。

### 13.5 全テスト

- `python -m pytest tests/ -q -p no:cacheprovider`：**823 passed／3 skipped、失敗 0**（2026-10-09、15 分 41 秒、ほかの検査と並行させずに単独で実行）。canonical golden 13 件＋legacy 3 件（plugin OFF）を含み、すべて一致（Flow Check・World Map の変更は golden に影響しない）。
- 実行の後、`data/sample/`・`tests/golden/`・`wom/engine/harvest_batch_plugin.py` に変更が無いことを確かめた。`docs/WOM_Start_Here.md` は着手前からの Claude 君の変更のままで、触っていない。
