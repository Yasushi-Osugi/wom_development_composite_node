# Request Letter：warmup_lt を暦の区切りでそろえ、identity の golden を作る

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`（着手時の SHA を報告書に記録する）
- 着手の時期：Flow Check の commit（`commit_msg70`）を大杉さんが push した後
- 種別：サンプルモデルの入力（`planning_config.csv` と warmup の生成行）の変更と、golden の意図的な再生成。エンジンのコードは変えない。
- 前提：
  - 決定記録 `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md` v1.3 の **D5（rice は legacy）・D7（warmup_lt の標準値）**
  - `docs/development/WOM_FlowCheck_WarmupTrial_Report.md` §5（warmup の試行）
  - CLAUDE.md の「golden 再生成」の手順と、AGENTS.md（golden の再生成は、大杉さんの差分確認の後に commit）

---

## 1. 目的

既定の方式は identity になりました。しかし、13 golden は legacy のまま凍結されています。また、identity では、期首在庫が無いことによる期末注文残（「計画期間の端（開始）」）が、多くのモデルに出ます。

本書では、次の順で進めます。

1. 各モデルに、決定記録 D7 のルールで `warmup_lt` を決めて入れる。
2. その入力で、golden を identity で作り直す。
3. legacy の解き方（決定記録 D3 で残した旧方式）が壊れていないことを守るため、少数のモデルに legacy の golden を別に残す。

## 2. warmup_lt の決め方（D7 のルール）

決定記録 D7：`warmup_lt` は暦の区切りにそろえる。**13 週（3 か月）を基本に、標準は 17 週（約 4 か月の先行生産）。17 週で足りないモデルは 26 週（半年）。**

本書では、次の手順で機械的に決める。

1. モデルのコピー（`output/warmup_trial/` の下）で、identity で `warmup_lt` = 17・26・52 を試す（52 は 1 年。既に 52 を持つ apparel-us のため）。
2. 期末注文残が最も少なくなる値のうち、**いちばん小さい値**を選ぶ（17 と 26 で同じなら 17）。
3. 3 つとも期末注文残が 0 にならない場合は、それでも最も少ない値を選び、残った分の原因を分類する（能力・休業・開始端・ID の照合不能・経路の未割当・終わりの端・未確認。LotIdentityFlow 報告書 §5.6 と同じ方法）。**52 を超える値は試さない。**

### 2.1 対象

| モデル | 今の warmup_lt | 扱い |
|---|---:|---|
| ev-thailand-2026 | なし | **17**（決定済み。試行の最小値 14、28 まで同じ結果） |
| Cookie-jp-2026 | なし | **17**（決定済み。試行の最小値 15、26 まで同じ結果） |
| soysauce-jpy-2027 | 26 | 26 のまま（17 では足りないことを確かめて記録する） |
| soysauce-jpy-2027-alloc | 26 | 同上。あわせて P_opt/800 の条件で、9,293 件がどう扱われるかを記録する |
| apparel-global-2028-2029、ev-europe-2026、smartphone-global-2026-2029、oil-global-2027、smartx-2027-2029、soysauce-eu-2027、soysauce-us-2027 | なし | 手順 1〜3 で決める |
| apparel-us-2026 | 52 | 手順 1〜3 で決める（17 や 26 で足りれば小さい方にそろえる） |
| bom-test-2026 | 12 | 手順 1〜3 で決める（12 は暦の区切りでないので、17 にそろえられるか確かめる） |
| ev-thailand-2026_update | 16 | 同上。Factory_Local_TH の保存差の NG（既知の不具合、Flow Check 報告書 §3.4）は、この依頼では直さない |
| rice-japan-2027-2028 | なし（legacy） | **対象外**（決定記録 D5）。`planning_config.csv` はそのまま |

### 2.2 原本への反映

- 決めた値を、各モデルの `data/sample/<モデル>/planning_config.csv` に書く（ファイルが無いモデルは、既存の書式 `key,value` で作る。ほかのキーは消さない）。
- warmup は、計画の実行時に `materialize_warmup` が CSV に助走週の行を書き込む。CLAUDE.md の方針（監査の証跡＝commit した生成後の CSV と golden）に従い、**生成された行を含む CSV を、そのまま commit の対象にする**。どのファイルのどの範囲が生成行かを、報告書に表で示す。

## 3. golden の作り直し

### 3.1 identity の golden

- 13 golden を、2.2 の入力で作り直す。方式は各モデルの `planning_config.csv` のとおり（rice は legacy、それ以外は identity）。
- スナップショットの config には方式が記録される（LotIdentityFlow C1。identity のときだけ `lot_flow_mode` が載る）。`tests/test_golden.py` は、記録された方式で比べる。
- identity のスナップショットの `forward` には `cap_hard_deferred_lots`・`cap_hard_deferred_lot_weeks` が載る（`cap_hard_sealed` は載らない）。

### 3.2 legacy の golden（旧方式を守る網）

- 入力の変わる前の状態でも後の状態でもよいので、次の 3 モデルについて、**legacy で**スナップショットを作り、`tests/golden/legacy/` に置く。
  - Cookie-jp-2026（pull、Outbound のデカップリング）
  - ev-thailand-2026（push のバッファ、休業週）
  - soysauce-jpy-2027（push、warmup あり）
- `tests/test_golden.py` が、このフォルダも legacy で比べるようにする。
- rice は、3.1 で legacy の golden になるので、ここには入れない。

### 3.3 差分の確認のための資料

golden の再生成は、大杉さんが差分を確認してから commit する（AGENTS.md）。確認しやすいように、モデルごとに次を表にする。

- warmup_lt（前 → 後）、計画の開始週（前 → 後）
- 市場：需要・当週出荷・遅配・期末注文残（legacy の旧 golden／identity で warmup なし／identity で warmup あり の 3 列）
- PPC の売上・粗利（同じ 3 列）
- `forward`・`backward` の値の変化
- psi のうち変わったノードの数と、代表例
- Flow Check：表 1 の NG の件数（ev-thailand-2026_update の既知の 1 件を除いて 0 のはず）、表 2 の検算

## 4. 守ること

- エンジン・GUI のコードは変えない。本書で変えるのは、サンプルの入力（`planning_config.csv` と warmup の生成行）、golden、`tests/test_golden.py`（legacy のフォルダを読む部分）だけ。
- 変えるのは 2.1 の表の対象だけ。rice の入力は変えない。
- 52 を超える `warmup_lt` を使わない。D7 のルールで決まらない場合は、決めずに報告する。
- commit・push はしない。
- 副作用が出ても最後まで行い、報告書に書く。

## 5. 受入条件

1. 全テスト緑（新しい golden 13 件＋legacy の golden 3 件を含む）。
2. identity の 12 モデル（rice を除く）で、期末注文残の値と原因の内訳が報告されている。warmup で消えない分は、原因の分類が付いている。
3. Flow Check の NG は、ev-thailand-2026_update の既知の 1 件だけ。
4. legacy の golden 3 件は、同じ入力で legacy を実行した結果と完全に一致する。

## 6. 成果物

1. 変更した入力（`planning_config.csv`、warmup の生成行を含む CSV）
2. 新しい golden（`tests/golden/*.json`、`tests/golden/legacy/*.json`）と、`tests/test_golden.py` の変更
3. 報告書 `docs/development/WOM_Warmup17_IdentityGolden_Report.md`
   - 2 の試行の結果表（モデル × 17・26・52）と、選んだ値
   - 3.3 の差分の確認資料
   - 期末注文残が残るモデルの原因の分類
   - 副作用、本書と変えた点
   - 大杉さんが `python -m main` で確かめる手順（ev-thailand・Cookie の Flow Check で、表 2 の期末注文残が 0 になること）
