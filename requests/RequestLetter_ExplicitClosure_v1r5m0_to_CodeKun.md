# Request Letter：休業を「週の状態」に一本化し、能力値から切り離す（Explicit Closure v1r5m0）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 種別：core 変更を含む実装。AGENTS.md の保護対象（`plan_node.py`・`forward_planner.py`・`backward_planner.py`・`push_pull.py`）を含む。
- リポジトリ／ブランチ：`wom_development_composite_node` / `wom-v1r5m0`
- 基準コミット：`4ed2f145dfb30b95058c0d274665eca64e4fc4c4`
- 置き換える依頼：`docs/codex_requests/holiday_explicit_closure_engine_request.md`（基準 `2169bf6`、未実装）
  - 設計意図は引き継ぐ。
  - 現行コードとの差分、push ノードの扱い、休業週に届いた lot の扱い、データ移行は本書で上書きする。
- 承認：大杉さん 2026-09-27（effect 名 `partial_capacity`、E2・E3、副作用が出た場合の進め方 §8）
- 事実の正本：`docs/development/WOM_Capacity_Trial02_Report.md`（GPT-6 Astra君、WOM-CAPACITY-TRIAL-02）。
  - 本書は同報告の数値を引用するだけで、複製はしない。

---

## 1. 目的

休業（工場閉鎖・保守停止）は、現在 `holiday_calendar.csv` の `value` を `cap_hard` に書き込むことで表されています。Trial-02 で次のことが測定されました。

1. **soysauce の W18 が S=0 になるのは偶然による（Trial-02 §3）。**
   - 休業の適用処理 `set_capacity(w, cap_hard=0.1)` の既定引数が、cap_soft を 686 から 0 に上書きする。
   - その結果、Backward は soft による平準化の目標を使わずに hard の側へ落ち、`int(0.1)=0` が目標になる。
   - cap_soft=686 を保持した反事実では、W18 は Backward S/P=686、実出荷=686 になった。
2. **value=0.0 の休業は、処理を止めていない（Trial-02 §5）。**
   - MOM ノード（Cookie、ev-europe、ev-thailand）では、休業週にも処理が残る。
   - smartx の `WaferFab_TW`（leaf_in / push_sub）では、Mode 4 が copy の後に leaf の P を置き直す（`push_pull.py` の l.304 以降）ため、休業週にも P が残る。Backward と `on_post_backward` だけでは休業を保証できない。
3. **設備能力が休業週だけ書き換わる。** 画面の CapHard が W18 だけ「0」と表示されるのは、0.1 を小数0桁で表示しているためである（Trial-02 §4.1）。

本依頼では、**休業を「週の状態」として1か所で持ち、全ての処理がそれを見る**ように直します。能力値の意味（0＝未設定）は変えません。

## 2. 合意済みの業務方針（議論の対象にしない）

| ID | 内容 | 出所 |
|---|---|---|
| D1 | cap_hard は工程設備の物理的な処理能力の上限。休業で書き換えない | 大杉さん 2026-09-27 |
| D2 | cap_soft は Planning Engine が使う計画上の操業能力。休業週は数値の 0 | 大杉さん 2026-09-27 |
| D3 | 休業は能力値の特殊値ではなく週の状態。`effect=supply_closure` なら value に関係なく完全休業 | `docs/design/holiday_calendar_and_capacity_semantics.md` §3・§12 |
| D4 | push ノードの休業週は、入庫（P）を受け入れ、処理（S＝瓶詰・出荷）を止める | 大杉さん 2026-09-27 |
| D5 | value が 0 でも 0.1 でもない supply_closure 行は、effect 名を `partial_capacity` に付け替える。挙動は現状のまま（§4.2 C2-b） | 大杉さん 2026-09-27 |
| D6 | 部分操業が動かすべきなのは **cap_soft**。cap_hard は物理制約で簡単に動かせない。**本依頼では D5 により cap_hard を書き換える現状を残すが、これは移行中の既知の逸脱であり、次の依頼で cap_soft へ移す** | 大杉さん 2026-09-27 |
| D7 | 内部の約束「cap = 0 は未設定」は本依頼では変えない。None／Enum への移行は対象外 | 旧依頼 Decision A |

D5 の effect 名について：最初の案は `capacity_override` でした。しかし、同じ名前の既存プラグイン `CapacityOverridePlugin`（`name = "capacity_override"`、`cap_override.csv` を読む）があります。同じ名前に別の意味を持たせないよう、設計書 §3.3 にあるもう一つの名前 `partial_capacity` を使います（大杉さん承認済み 2026-09-27）。

## 3. 本依頼の設計判断（Trial-02 から導いたもの）

| ID | 判断 | 理由 |
|---|---|---|
| E1 | 休業は既存の `op_shifts[w] = 0` で表す。新しい属性は作らない | Backward の充填目標と `_build_closed_index` は、既に `op_shifts==0` を休業として扱っている（Trial-02 §4.1 の `backward_planner.py:520` の行） |
| E2 | 非 push ノードで休業週に P が届いた場合は、**lot を消さず、次の開いている週の P へ繰り延べる**。Step 0a の封印（P→CO[w+1]）は使わない | Step 0a は超過した lot を P から外し、CO[w+1] の需要側にだけ残すため、供給側から lot が消える。Composite Draft §8.2「能力等で生産が成立しない場合も、部材の所在を消失させない」に合わせる |
| E3 | Mode 4 が leaf の P を置く週が休業なら、**直前の開いている週へ前倒しする**。前にない場合は直後の開いている週へ置く。規則は `on_post_backward` と同じ | 休業は計画段階で解決する（旧依頼 Decision C）。smartx の WaferFab_TW の P が休業週に残るのは、この経路による（Trial-02 §5.2） |
| E4 | push ノードの休業週は、P を受け入れ、実出荷を 0 にし、全量を I に残す（D4） | Trial-02 §4.3：入庫を止めると I の時点が変わる。S を止めても、今の soysauce では結果が変わらない |

## 4. 変更内容

現行挙動の正本は Trial-02 報告 §4.1（能力値を読む22か所）と §4.2（旧依頼 §3 との照合）です。以下は変更する箇所だけを示します。

### 4.1 PlanNode（`wom/model/plan_node.py`）

次の2つの読み取り関数を追加します。

```python
def processing_limit(self, w) -> Optional[float]:
    """処理の上限。休業=0.0、未設定=None、それ以外=cap_hard。"""
    if not self.is_open(w):
        return 0.0
    ch = self.cap_hard(w)
    return ch if ch > 0 else None

def planned_capacity(self, w) -> Optional[float]:
    """計画上の操業能力。休業=0.0、未設定=None、それ以外=cap_soft。"""
    if not self.is_open(w):
        return 0.0
    cs = self.cap_soft(w)
    return cs if cs > 0 else None
```

- 新しく書くコードは、0 と「未設定」を取り違えないよう、この2関数（戻り値に None を含む）を使う。
- 既存の `cap_hard()` / `cap_soft()` は生の値を返すまま残す（D7）。

`set_capacity` は、既定値を `None` にして「渡さなかった方は変更しない」に変えます。

```python
def set_capacity(self, week, cap_hard=None, cap_soft=None):
    if cap_hard is not None: self.capacity[week][CAP_HARD] = cap_hard
    if cap_soft is not None: self.capacity[week][CAP_SOFT] = cap_soft
```

`summary()`（l.456–457）に `"is_open"` を加えます。

### 4.2 HolidayCalendarPlugin（`wom/engine/holiday_calendar_plugin.py`）

- **C2-a `supply_closure`**
  - 対象ノード・週について `node.set_operating_shifts(w, 0)` を呼ぶ。`set_capacity` は呼ばない。value は読まない。
  - value が 0・0.1・空のいずれでもない行が来たら警告を出す。文言：「supply_closure は value を使わない。部分操業は partial_capacity を使うこと」。
- **C2-b `partial_capacity`（新 effect。移行中の互換）**
  - 現状の supply_closure と同じ結果になるように実装する。
    - `set_capacity(w, cap_hard=value)`。cap_soft は保持される（4.1 の変更による）。
    - 現状どおり `config["explicit_closures"]` に登録し、`on_post_backward` の leaf_in の P シフト対象にも含める。
  - 現状の「部分操業」行は、LT スキップと leaf_in の P シフトでは休業として扱われています。今回はそれも含めて挙動を変えません。
  - コードに `# TRANSITIONAL (D6): 部分操業は cap_soft を動かすのが正。LT スキップと P シフトからも外す。次の依頼で移行` と明記する。
- `explicit_closures` の構築（l.65–75、l.135–139）は、対象 effect を `{"supply_closure", "partial_capacity"}` にする。
- **読み込み順序の確認**：GUI（`gui/app.py` l.5163 付近）と headless（`run_headless_from_folder.py` l.181–194）の両方で、次の順になっていることを確認する。
  1. `load_operating_calendar`
  2. `HolidayCalendarPlugin.on_pre_plan`

  逆になっている経路があると、休業の shifts=0 が操業カレンダーの値で上書きされる。

### 4.3 Backward（`wom/engine/backward_planner.py`）

- `_apply_mom_cap_backward` の `is_closed` を `not node.is_open(w)` に置き換える。意味は現行と同じ（op_shifts==0）。C2-a によって holiday の休業もここで効くようになる。
- `_build_closed_index` は変更不要。

### 4.4 Mode 4（`wom/engine/push_pull.py` l.304 以降）（E3）

- `leaf_node.psi4supply[w][P] = list(leaf_lots)` の前に、`leaf_node.is_open(w)` を確認する。
- 休業週なら、直前の開いている週（なければ直後の開いている週）の P に**追加**する。上書きしない。
- 移した件数を、新しい診断 `mode4_closure_shifted`（leaf node_id, 元の週, 移した先の週, 件数）として記録する。

### 4.5 Forward（`wom/engine/forward_planner.py`）

- **休業週の繰り延べ（非 push、E2）**
  - Step 0a の前に処理する：`not node.is_open(w)` かつ P が空でなければ、P の lot を次の開いている週の P の末尾へ移す。
  - 診断 `closure_p_deferred`（node_id, 週, 件数）を記録する。
  - 次の開いている週が計画期間内にない場合は、診断 `closure_p_unplaced`（node_id, 週, lot_id のリスト）を記録して P から外す。既知の限界として報告書に記す。
- **Step 0a**：現行のまま。休業週の P は上の処理で既に空になっている。
- **push ノードの休業週（D4・E4）**
  - P は受け入れ、`actual_s = []` として全量を I に残す。
  - S 計画が 0 でない場合（Backward との不整合）は、診断 `closure_s_planned`（node_id, 週, 件数）を記録する。
- **Step 0b**
  - 非 push：`pc = node.planned_capacity(w)` が 0 より大きいときだけ、P と比較する。
  - push：P ではなく、その週の実出荷件数（`len(actual_s)`）と `pc` を比較する。判定は push の出荷を計算した後に移す。
- **Kitting 予算（l.654）**
  - `lim = node.processing_limit(w)`、`remaining = int(lim) if lim is not None else len(candidates)` とする。
  - 休業週は 0 になり、kit は部材を消費せずに持ち越される（既存の回復処理による）。

### 4.6 その他の読み手

- `harvest_batch_plugin`（l.78）：収穫週の条件に `and node.is_open(w)` を足す。
- `strategic_kpi`（l.249）
  - `lim = node.processing_limit(w)` とし、lim が None または 0 の週は稼働率の集計から除く。
  - soysauce の値は変わる（休業週の P/0.1 による150%上限が消える）。変わった値を報告する。
- `capacity_sealer.build_capacity_load_report`（テスト専用）
  - `processing_limit` を使う。
  - l.252 の、直後に上書きされる死んだ代入行を削除する。

### 4.7 表示

- **PSI List（`gui/app.py` l.1690–1691）**
  - CapHard 列は生の `cap_hard` を表示する。W18 も 800。
  - CapSoft 列は `planned_capacity`：None →「—」、0.0 →「0」、それ以外は数値。
- **「P vs Capacity Limits」（`gui/app.py` l.1774–1856）**
  - push ノードの棒は、S3（Phase 8-3c-4 案5）と同じく処理量 `len(S) − _push_shortfall[w]` にする。
  - 休業週は超過色で塗らず、背景を灰色にする。
- **S3（`run_headless_from_folder.py` l.385–386）**
  - `cap_hard_series` は生の値のまま。
  - `cap_soft_series` は `planned_capacity`（None は 0 として渡す）。
  - 休業週のリスト `closed_weeks` を view に加える。描画での扱いは灰色背景だけにする。
- **Debugger（`gui/app.py` l.4207）**：変更しない。

### 4.8 データ移行

| 対象 | 行数 | 変更 |
|---|---:|---|
| soysauce-eu / jpy / jpy-alloc / us-2027 | 8 | `supply_closure` の value `0.1` → `0`（EU・JPY・alloc は commit `2fc7f4b` で 1500 から 0.1 に変えたもの。US は元から 0.1） |
| value が 0 でも 0.1 でもない supply_closure 行（モデル配下） | 43 | effect → `partial_capacity`（value はそのまま） |
| `rice-japan-2027-2028_BK260613_1515`（バックアップ） | 16 | 同上（落とし穴を残さないため） |
| `data/sample/holiday_calendar.csv`（旧 root sample） | 2 | GW_2027・GW_2028 の DAD_Japan（0.3）を同上 |
| value = 0.0 の supply_closure 行 | 34（モデル配下）＋4（root） | 変更しない。**今回から休業として効き始める** |

43行の内訳：apparel-global 4、apparel-us 4、ev-thailand-2026_update 4、smartphone-global-2026-2029 3、oil-global-2027 7、rice-japan-2027-2028 16、smartx-2027-2029 5。

### 4.9 文書

- `docs/design/holiday_calendar_and_capacity_semantics.md` の末尾に「実装状況（2026-09-xx）」の節を足す。内容は、本依頼で実装したこと、E1〜E4、`partial_capacity` が移行中であること（D6）、None／Enum が未着手であること。
- 旧依頼の先頭には、本書への置き換えを示す注記を Claude君が追加済み。

## 5. テスト

旧依頼 §6 の Test 1〜8 を、現行コードに合わせて移植します。Test 3・6 は D4・E2 に合わせて、push と非 push に分けます。次を追加します。

| # | 内容 |
|---|---|
| T9 | push ノードの休業週：P は受け入れ、実出荷は 0、全量が I に残る |
| T10 | `set_capacity(w, cap_hard=x)` で cap_soft が変わらない |
| T11 | `partial_capacity`：cap_hard=value、cap_soft 保持、explicit_closures と leaf_in の P シフトの対象になる（現状互換） |
| T12 | **H1 の回帰防止**：休業週に cap_soft=686 が残っていても Backward の S=0（Trial-02 §3 の反事実を固定化） |
| T13 | `value=0.0` の supply_closure が MOM の充填目標を 0 にする |
| T14 | 表示用 view：休業週の CapHard は生の値、CapSoft は 0、「—」は未設定の週だけ |
| T15 | **lot の保存**：非 push ノードの休業週に P が届いた場合、lot は消えずに次の開いている週の P に移る。`closure_p_deferred` が記録される |
| T16 | **Mode 4**：leaf の置き先が休業週なら直前の開いている週へ移り、Lot_ID の集合は変わらない |
| T17 | 読み込み順序：操業カレンダーで 18直の週に supply_closure を掛けると、GUI・headless の両方で `is_open=False` になる |

3層（Unit／Integration／E2E golden）をすべて通してください。GUI の Gate 0 テストも Windows で実行してください。

## 6. 受入条件と報告

### 6.1 結果が変わってはいけないもの

- **soysauce-eu / jpy / us-2027（golden あり）**：psi・forward・backward・ppc が一致すること。cap の値や sealed 件数を含むフィールドが変わった場合は、そのフィールドと値を列挙する。
- **soysauce-jpy-2027-alloc（golden なし）**：headless の P_opt／800 で、Bottling_Noda の 2027・2028 年の W16–W19 について P／S／実出荷／I の前後比較表を出し、一致すること。
  - 基準値は Trial-02 §3 の baseline：W17 = P0/S686/実出荷0/I0、W18 = P686/S0/実出荷0/I686、W19 = P686/S686/実出荷686/I686。
- **apparel-global、apparel-us、oil-global-2027、rice-japan-2027-2028（golden あり）**：一致すること（`partial_capacity` の互換）。
- **smartphone-global-2026-2029（golden あり）**：一致すること。Trial-02 §5.1 で、value=0.0 の休業行はすべて休業週に活動がなかった（判定不能）ため、変化は見込まない。変化した場合も実装は最後まで行い、§6.4 の形式で報告する。

### 6.2 結果が変わってよいもの（意図した変更）

Trial-02 §5.1 で「効いていない」と判定された value=0.0 の休業が、効き始めます。

| モデル（golden） | 行 | node / type / mode | Trial-02 の休業週の処理 | 期待 |
|---|---|---|---|---|
| Cookie-jp-2026 | CNY2026・CNY2027 | Factory_GP_CN / mom / pull | P 1500・1538 | 休業週の処理が 0、前の週へ前倒し |
| ev-europe-2026 | KASSEL ×2 | Factory_Local_DE / mom / pull | P 500・500 | 同上 |
| ev-europe-2026 | HU_SUMMER ×2 | Factory_Import_HU / mom / push | 実出荷 200・110 | 休業週の実出荷 0（入庫は受け入れる） |
| ev-thailand-2026 | RAYONG ×2 | Factory_Local_TH / mom / pull | P 500・500 | 休業週の処理が 0 |
| ev-thailand-2026 | GOLDEN_WEEK ×2 | Factory_Import_CN / mom / push | 実出荷 221・221 | 休業週の実出荷 0 |
| smartx-2027-2029 | CNY 2026–2029 | WaferFab_TW / leaf_in / push_sub | P 2700・2298・1802・755 | Mode 4 の置き先が休業週の前へ移り、休業週の P が 0 |

- **golden は再生成しないでください。** 休業行ごとに次を表で報告し、大杉さんが差分を確認してから再生成します。
  - 休業週と移った先の週の、処理系列（push は実出荷、それ以外は P）の前後の値
  - `closure_p_deferred`・`closure_p_unplaced`・`closure_s_planned`・`mode4_closure_shifted` の件数
  - PPC の売上・粗利の前後差
- 表に無いモデルで差分が出た場合も、実装は最後まで行い、§6.4 の形式で報告してください。

### 6.3 報告に含めるもの

1. 変更ファイルごとの diff の要約
2. テスト結果（件数・失敗の有無）
3. 6.1 の一致確認
4. 6.2 の差分表
5. `strategic_kpi` の soysauce の値の前後
6. §6.4 の副作用の一覧（無ければ「なし」と明記）
7. 本書と変えた実装があれば、その内容と理由
8. 画面確認：soysauce-jpy-2027-alloc の Bottling_Noda の PSI List（W16–W19）と「P vs Capacity Limits」のスクリーンショット。W18 が CapHard 800・CapSoft 0 であること。

### 6.4 副作用の報告

§6.1 で変わってはいけないものが変わった場合、§6.2 の表に無い変化が出た場合、E2・E3 の診断が想定外の件数で出た場合は、実装を止めずに最後まで行ったうえで、1件ごとに次を報告してください。大杉さんが `python -m main` で実機確認します。

| 項目 | 内容 |
|---|---|
| どこで | モデル、product、node、週 |
| 何が | 変わった系列（P／S／実出荷／I／CO、PPC の金額など）の前後の値 |
| なぜ（推定） | 原因と考える変更箇所（E1〜E4、C2-a/b など）。確かめていない場合は「推定」と明記する |
| 実機での見方 | `python -m main` → モデルフォルダ → Run Planning Engine → Network で node を選択 → PSI List／PSI Chart のどの週を見ればよいか |
| 期待との差 | 本書の期待（§6.1／§6.2）と、観測した値の違い |

## 7. 対象外

- cap の None／Enum への移行（D7）
- `partial_capacity` を cap_soft へ移すこと、LT スキップと P シフトから外すこと（D6。次の依頼）
- Mode 4 の `push_lead_time_weeks`。Trial-02 §6 により、soysauce の 7＝6＋1 は設計書どおり。
- Bottling に一度も実出荷されない 9,293 lot と PPC の計上（Trial-02 §7。売上 73,461,824円・粗利 24,625,145円）。別の依頼で扱う。
- S3 の結論文の書き換え

## 8. 手続き

- 保護対象の core を変更するので、commit 前に大杉さんが `git diff` を確認します。確認が済むまで commit・push しないでください。
- golden の再生成は、6.2 の差分を大杉さんが承認した後に、別の commit で行ってください。
- **副作用が出ても実装は止めず、最後まで行ってください。** E2（繰り延べ）と E3（Mode 4 の前倒し）は、Trial-02 の実測にもとづく設計判断であり、まだ実装で試されていません。想定外の動きは §6.4 の形式で報告してください。大杉さんが実機で確認し、扱いを決めます。
- 本書の指示どおりには実装できないコードの事実を見つけた場合も、止めずに、本書の意図（§2・§3）に最も近い形で実装してください。その場合は、何を本書と変えたかと、その理由を報告に明記してください。
