# Request Letter：Mode4（LT シフト）の二重計上バグ修正

**起票日**：2026-08-30
**起票者**：大杉
**種別**：**禁足コア変更**（`wom/engine/push_pull.py`）
**対象ブランチ**：`wom-v1r3m0`
**先行調査**：
- `requests/request_investigation_s1_push_pull_default.md`（PUSH/PULL 既定）
- `requests/request_investigation_s2_inbound_decoupling.md`（InBound decoupling）
- スイープ4本：`apparel_s1.yaml` / `apparel_s1_pushlt.yaml` / `apparel_s1_horizon.yaml` / `apparel_s1_holiday_lt8.yaml` / `apparel_s1_lt3.yaml`

---

## 0. 禁足ルールに基づく承認事項

本件は保護対象コア `wom/engine/push_pull.py` の変更を伴う。CLAUDE.md 冒頭の禁足ルールに従い、以下を条件とする。

- [x] Request Letter 起票（本書）
- [ ] 3層テスト（Unit / Integration / golden）緑
- [ ] オーナー（大杉）による差分レビュー
- [ ] golden 差分が生じた場合、その差分が「正しくなった結果」であることの確認

**上記が揃うまでコミットしないこと。**

---

## 1. 確定した原因

### 1.1 機構

実行順序（`push_pull.py` module docstring）：

```
Step 5  copy_demand_to_supply()
        leaf_in.psi4supply[w][P] = leaf_in.psi4demand[w][P]   ← 全週にディープコピー
Step 8  PushProductionPlanner.setup()  → Mode4
        leaf_in.psi4supply[w][P] = list(leaf_lots)            ← 一部の週のみ上書き
Step 6  ForwardPlanner.run()
```

Mode4（`is_lt_shifted_mode()`、`push_pull.py:255-303`）は `w in range(n_weeks)` の全週を回るが、
`future_w = w + lt_weeks` の需要が空なら `if not lots: continue`（`push_pull.py:286-287`）で
**その週をスキップし、`psi4supply[w][P]` を一切触らない。**

したがって **Mode4 が明示的に書いた週だけが上書きされ、触らなかった週には
Step 5 の自然コピーが残る。**

- Mode4 が書く週：`d − LT`（`d` は decoupling node の実需要週、`LT` = `push_lead_time_weeks`）
- 自然コピーの週：`d − τ`（`τ` = その leaf_in 自身の `lt_wks + ss_wks`）

**`LT ≠ τ` である限り両者は別の週になり、同じ Lot が二重に残る。**

### 1.2 症状

- 上流（leaf_in / MOM）の `P_sum` が最大約2倍に増加
- 下流（supply_point / DAD）に CO が単調発生し、解消しない
- MOM に「在庫」が立つが、これは二重計上分であり実体がない

### 1.3 実測（`apparel-us-2026` / `Apparel_Outsourced_S1`、leaf_in は `Fabric_CN` 1つ、τ=3）

| `push_lead_time_weeks` | Fabric_CN / Factory_Import_CN `P_sum` | SP `CO_sum` | DC `CO_sum` | Factory `I_max` |
|---|---|---|---|---|
| （Mode4 なし = `mode_only`） | **23,884** | 0 | 0 | 0 |
| 1 | 28,642 | 534,076 | 441,295 | — |
| 2 | 24,784 | 260,212 | 206,185 | 3,529 |
| **3（= τ）** | **23,884** | **0** | **0** | **0** |
| 4 | 26,184 | 32,650 | 19,550 | 4,229 |
| 8 | 46,868 | 303,050 | 221,256 | — |

`LT = τ = 3` のとき、下流の全指標が `mode_only`（Mode4 を起動しないベースライン）と
**ビット単位で一致**する。すなわち **`LT = τ` は Mode4 が no-op になる特異点**であり、
それ以外の全ての値で二重計上が発生する。

`LT` に対して非単調なのは、`_apply_mom_cap_backward` による cap 超過分の週跨ぎ前倒し
（`backward_planner.py:507-510`）で実需要週が広くばらけており、
「Mode4 が書く週集合」と「自然コピーの週集合」の重なり方が `LT` ごとに離散的に変わるため。

### 1.4 棄却された仮説（記録）

| 仮説 | 検証 | 結果 |
|---|---|---|
| horizon 端で `w+LT` の参照先が消える | `warmup_lt` 52 / 78 / 104 | **棄却**。CO は1ロットも変わらず |
| `holiday_calendar` の閉鎖と LT シフトの衝突 | 閉鎖の有無 | **棄却**。`series_md5` が完全一致 |
| Mode4 が `extend` で追加している | コード確認 | **棄却**。`=`（代入）である |
| `divmod` による leaf_in 分配の不具合 | コード確認 | **棄却**。leaf_in が1つなら no-op |
| ソース側の Lot_ID 重複 | `backward_planner.py` 確認 | **棄却**。`clear()+extend()` による移動で複製なし |

### 1.5 実務上の含意

`push_lead_time_weeks` は「decoupling node より手前で前倒し生産する」ための
パラメータであり、**`τ` と異なる値を指定するのが前提**である。
したがって **通常運用では必ずこのバグが発生する。**`LT = τ` は唯一の例外だが、
そのとき Mode4 は何もしないので機能として意味がない。

**結論：現状、Mode4 による先行生産は実質的に使用不能。**

---

## 2. 修正内容

### 2.1 方針

**Mode4 が対象 leaf_in の `psi4supply[w][P]` を書き始める前に、
その leaf_in の全週の `psi4supply[w][P]` をクリアする。**

これにより「Mode4 が書いた週だけが有効」となり、
設計意図である「既存 Lot_ID の**再配置**」が成立する。

### 2.2 実装範囲

- 対象ファイル：`wom/engine/push_pull.py`
- 対象箇所：`is_lt_shifted_mode()` 分岐（`push_pull.py:255-303` 付近）
- **クリアの対象は、Mode4 が書き込む leaf_in ノードのみ。** 他のノードには触れないこと
- Mode1〜3 の挙動は**一切変更しないこと**
- `mode_only=True` の早期 return（`push_pull.py:249-250`）より後に置くこと
  （`mode_only` では Mode4 に到達しないため）

### 2.3 実装しないこと（範囲外）

以下は本 Request Letter の範囲外とする。別途起票すること。

- `mom_ref_node_id` が Mode4 で無視される件（docstring とコードの不整合）
- `push_eol_week` が GUI 本番／headless 経路で CSV から読まれていない件
- `plan_mode` 既定値（`pull`）の是非
- A1（multi-leaf_in × 需要段差の擬似 CO）

---

## 3. 影響範囲の事前確認【修正と同時に実施】

**修正を適用する前に、以下を機械的に調べて報告すること。**

`data/sample/` 配下の全モデルについて、`push_config.csv` に
`push_lead_time_weeks` が指定されている行を抽出し、**その値と、対応する
decoupling node の leaf_in の `τ`（= `lt_wks` + `ss_days`/7 の切り上げ、
実装の定義に合わせること）を突き合わせる。**

| ケース | decoupling node | `push_lead_time_weeks` | leaf_in の τ | 一致？ |
|---|---|---|---|---|
| `smartx-2027-2029` | `Buffer_Chip_TW` | 39 | ? | ? |
| `soysauce-us/eu/jpy-2027` | `Bottling_Noda` | 7 | ? | ? |
| `apparel-global-2028-2029` | `Garment_BD` / `Garment_PT` | ? | ? | ? |
| `ev-europe-2026` | `Factory_Import_HU` | ? | ? | ? |
| `ev-thailand-2026(_update)` | `Factory_Import_CN` | ? | ? | ? |

**一致していないケースは、現在すでに二重計上が起きている。**
その場合、修正後に golden の値が変わる。**どのケースが該当するかを、修正前に確定させること。**

leaf_in が複数ある場合は、全 leaf_in の τ を列挙すること。

---

## 4. テスト要件（3層）

### 4.1 Unit

`tools/sweep_specs/apparel_s1_lt3.yaml` の観測を固定するテストを追加する。

- `apparel-us-2026` / `Apparel_Outsourced_S1`、`buffering_stock_flag=1`
- `push_lead_time_weeks` = 2 / 3 / 4 / 8 のそれぞれで、
  **`Fabric_CN` の `P_sum` が 23,884（base）と一致すること**
- 同条件で **SP / DC の `CO_sum` が 0 であること**

**修正前はこのテストが赤になることを、先に確認すること**（修正が効いていることの証明）。

### 4.2 Integration

- `Factory_Import_CN` の `psi4supply[w][P]` に、Mode4 が書いた週以外の値が残っていないこと
- `mode_only=True` のときは従来通り Mode4 に到達しないこと
- Mode1 / Mode2 / Mode3 の挙動が変わっていないこと

### 4.3 golden（12ケース）

**全ケースを実行し、`series_md5` の差分を報告すること。**

判定基準：

| 状況 | 判定 |
|---|---|
| §3 で「τ と一致」と確認されたケースが**変化しない** | **正常** |
| §3 で「τ と不一致」と確認されたケースが**変化する** | **正常**（正しくなった結果） |
| §3 で「一致」のケースが変化した | **異常**。修正が過剰。原因を報告し、コミットしないこと |
| §3 で「不一致」のケースが変化しなかった | **要調査**。想定と違う。報告すること |

**golden の JSON は、大杉の承認を得るまで更新しないこと。**
差分の内容（どのノードのどのバケットがどう変わったか）を報告し、
「正しくなった」ことを大杉が確認してから更新する。

---

## 5. 報告してほしいこと

1. §3 の突合表（全ケース、τ の値つき）
2. 修正の差分（`git diff`）
3. §4.1 の Unit テストが**修正前に赤・修正後に緑**であること
4. §4.2 の Integration 結果
5. §4.3 の golden 差分（変化したケース名と、変化の内容）
6. §4.3 の判定表に照らした判定
7. **`git status`**（`data/sample/` が clean であること）
8. 気づいた点

---

## 6. 手順

```
① §3 の突合を先に実施し、報告する（修正前）
② 修正を実装する
③ §4.1 Unit テストを追加し、修正前後で赤→緑を確認する
④ §4.2 Integration を実施
⑤ §4.3 golden 12ケースを実行し、差分を報告する
⑥ 大杉の差分レビュー
⑦ 承認後、golden JSON を更新（必要な場合）
⑧ 承認後、コミット
```

**⑥の前にコミットしないこと。**

---

## 7. 実行上の注意

- sweep / テスト実行中は `python -m main`（WOM GUI）を起動しないこと。
  WOM は起動中に `capacity_plan.csv` / `demand_forecast.csv` へ warm-up 行を
  自動追記し続けるため、CSV が競合する（2026-08-30 に実際に発生）
- 実行前に `Get-Process python` で他プロセスが無いことを確認すること
- `data/sample/` を恒久的に書き換えないこと

---

## 8. 参考

- `docs/design/design_memo_confluence_assembly_autotuning.md`（合流と組立、auto-debug）
- `docs/design/three_layer_production_allocation.md` §5（`lt_wks` はエッジ属性）
- `CLAUDE.md` 冒頭「禁足ルール（Planning Engine 保護対象コア）」
- `tools/sweep_flags.py` と `tools/sweep_specs/apparel_s1_lt3.yaml`（再現手段）
