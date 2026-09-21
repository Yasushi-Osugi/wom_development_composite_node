# Coding Request Letter: 操業制約レイヤー（操業カレンダー＋ソフト能力）の core 統合と cap_hard/cap_soft 二層化

作成日: 2026-07-27
作成者: Claude (Cowork) ＋ 大杉さんとの設計対話
ステータス: **ドラフト（設計提案・未実装）**。オーナー(大杉さん)レビュー→承認後に実装フェーズへ。AGENTS.md の owner-gated ルール（AIは検査・起草まで／実装コミットはオーナー）に従う。
想定ブランチ: **`wom-v1r2m0_test`**（エンジン改修を含むため、現行 `wom-v1r2m0` とは分ける）
準拠: `docs/design/psi_ppc_separation.md`、`docs/design/wom_canonical_concepts.md`、`AGENTS.md`、本リポジトリ CLAUDE.md
出自: soysauce-us-2027 の休日カレンダー動作確認中に大杉さんが提起した2つの設計上の違和感——(A) 休日カレンダーが plugin になっていること、(B) ソフト能力 cap_soft が「影も形も見えない」こと——を設計レベルで整理し、1つのテーマに統合したもの。

---

## 1. Business question / 解決したい問題

```text
WOM の Planning Engine は、demand-allocation（Backward の Demand Envelope）において
「物理的な生産能力の限界 cap_hard」しか知らない。しかし現実の供給制約は2階建てである：
  ・操業制約（intrinsic・全ノードが持つ）：操業カレンダー（休日/稼働週）＋ ソフト能力（シフト体制 1直/2直/3直）
  ・物理制約（ceiling）：設備の物理上限、または天候依存の収穫予想量
現状 WOM は、操業レイヤーを「休日＝plugin で cap_hard 代用」「ソフト能力 cap_soft＝骨格はあるが休眠」
という不完全な形で扱っており、demand envelope が一律 cap_hard に潰れている。
これを、PySI 時代の素直な形——操業レイヤーを traversal の一級入力とし、cap_hard は物理 ceiling——
に純化（リファクタ）する。
```

## 2. 出自・背景（大杉さんの2つの違和感）

**違和感A（休日カレンダーが plugin）**
大杉さんの実装イメージ（PySI 由来）：Planning Engine の tree-traversal 中、**Backward で P を置く瞬間・Forward で S を置く瞬間**に、休暇週や SS_Days を判定して **Lot を置く週をズラす**、という極めてシンプルな処理。操業カレンダーは全ノードが当然に持つ intrinsic な属性であり、optional なアドオン（plugin）ではない。現行 WOM が `HolidayCalendarPlugin`（HOOK_PRE_PLAN で cap_hard=~0 を差し込む）にしているのは概念の格が合っていない。

**違和感B（cap_soft が休眠）**
米SC の「収穫期の生産制約」を起点にした指摘。米は秋の1〜2週で一年分を収穫＝`cap_hard = 収穫予想量（天候依存）`。一方、通常の工場は物理上限とは別に、操業計画に基づく**ソフト能力（1直8H/2直16H/3直24H）**が定義できる。この二層は以前の WOM に実装されていたはずだが、wom-v1r2m0 では実行上見えない。

**統合的な理解**：A も B も、**「操業レイヤー（操業カレンダー＋ソフト能力）を demand-allocation traversal の一級市民に戻す」**という1つの設計テーマに束ねられる。

## 3. 現状のコード考古学（事実・wom-v1r2m0）

**cap_soft は骨格が残っているが配線が切れている（休眠）：**
- `wom/model/plan_node.py`：`CAP_HARD`/`CAP_SOFT` の2定数、`cap_soft(week)` getter、`set_capacity(cap_hard, cap_soft)`。ノードは両方を保持できる。
- `wom/engine/capacity_sealer.py`：cap_soft を扱う専用モジュール（*"Operational plan limit (preferred ceiling, e.g. regular-shift target)"*）。だが planning pipeline から **import も呼出もされず孤立**。
- `wom/engine/forward_planner.py`：`cap_soft_violations` / `record_cap_soft_violation` / Step 0b「P[w] > cap_soft なら flag（動かさない）」。ただし cap_soft=0 のため**デッドパス**。
- `wom/gui/app.py`：PSI チャートに `cap_soft(w)` の線を描くコード（1691/1782行）はあるが、cap_soft=0 なので何も描かれない。

**demand envelope は cap_hard 一本：**
- `wom/engine/backward_planner.py` `_apply_mom_cap_backward`：`psi4demand[w][P]` を **`cap_hard(w)` で clip**、超過を CO 前倒し。cap_soft は一切関与しない。

**データ・ローダが cap_soft を埋めない：**
- 全ケースの `capacity_plan.csv` は列が `sku_id, node_name, week, max_supply, source`（iphone系は region）で、**cap_soft 列が無い**。
- `app.py` の能力ローダ（5097/5108行）は `max_supply → cap_hard` のみをマップ。

**休日・収穫は plugin 代用：**
- 休日：`HolidayCalendarPlugin`（`holiday_calendar.csv` を読み、HOOK_PRE_PLAN で `set_capacity(cap_hard=value)`）。=「カレンダー・スキップ」を「cap_hard クリップ」で代用。
- 収穫：`HarvestBatchPlugin`（季節スパイク）。=「cap_hard=収穫予想量」という素直な形ではなく plugin 代用。

**SS_Days は既に core にある（片肺の証拠）：**
- `_ot_propagate`/`_in_propagate` は `node.lt_wks + node.ss_wks` をオフセットに使用。SS の「置く週をずらす」は traversal に入っているのに、休日の「置く週をずらす」は plugin にある——**この非対称が違和感Aの正体**。

**推定される経緯**：`v1r0m3` の「MOM Constrained Demand Allocation」リファクタで demand allocation を cap_hard 一本に単純化した際、cap_soft の配線（sealer 呼出＋データ列）が外れ、骨格だけ残って休眠した。

## 4. 設計の核（2つの分離軸）

**軸1：操業レイヤー（intrinsic）と 撹乱イベント（overlay）を峻別する**
- **操業レイヤー（core・全ノード intrinsic）**：操業カレンダー（稼働/休日週）＋ ソフト能力（シフト）。traversal の一級入力。
- **撹乱イベント層（optional・overlay）**：ストライキ・災害・地政学・関税・原油スパイク・レーン障害等。throughput 減や CO を生む "事件"。← ここは plugin/override が妥当。

**軸2：能力を二層で扱う（cap_soft ＝ 操業計画、cap_hard ＝ 物理 ceiling）**
- **cap_soft（操業計画/シフト）**：Backward の Demand Envelope が流し込む先の "通常上限"。
- **cap_hard（物理上限 or 収穫予想量）**：cap_soft を超えたときに使える増産余地の ceiling。ここも超えたら CO。
- 米：シフト自由度が無いので `cap_soft = cap_hard = 収穫予想量` と置ける（退化ケース）。工場：`cap_soft(2直) < cap_hard(3直=物理)`。

**軸3：カレンダー・スキップ と 能力クリップ を峻別する**
- **カレンダー・スキップ**（休日・計画・反復）：その週は稼働しないので**隣の稼働週に置き直す**。出力は保存、時間だけズレる。CO は原理的に出ない（前倒し/後追いで吸収）。
- **能力クリップ**（cap_soft/cap_hard 超過）：能力を超えた分は増産余地→CO。**現行 plugin は休日をこの能力クリップで代用しており、意味論が混ざっている**。

## 5. 提案する設計（操業レイヤー統合＋二層能力）

### 5.1 操業カレンダーを per-node intrinsic 属性に
- `PlanNode` に `operating_calendar`（稼働週集合 or 休日週集合、既定＝全週稼働）を持たせる。
- Backward/Forward の traversal で、P/S を置く週が休日なら**最も近い稼働週にスキップ（前倒し優先）**。SS_Days のオフセットと**同じ「配置週調整」パイプに統一**する。
- データ源：`operating_calendar.csv`（node_name × week × open/closed）を新設、または既存 `holiday_calendar.csv` の `supply_closure` をこの層に**吸収**（`HolidayCalendarPlugin` は薄いアダプタとして後方互換で残す案も可）。

### 5.2 Demand Envelope を cap_soft 基準に、cap_hard を物理 ceiling に
- `_apply_mom_cap_backward` を「**cap_soft で envelope → 超過は cap_hard まで増産余地を使う → それも超えたら CO**」に拡張。
- `capacity_plan.csv` に **`cap_soft` 列を追加**（省略時は cap_soft=cap_hard に既定＝現行互換）。ローダ（app.py 5097/5108）を cap_soft も読むよう拡張、または `capacity_sealer.py` を pipeline に配線して二層をまとめて設定。
- Forward の cap_soft 違反 flag（既存 Step 0b）を活かし、「操業計画超過（要・追加シフト）」を KPI/警告として可視化。

### 5.3 撹乱イベントは overlay として維持・整理
- ストライキ/災害/地政学/コストスパイク/レーン障害は、操業レイヤーとは別の overlay（既存の `CapacityOverride`／`HolidayCalendarPlugin` の "本来の撹乱" 用途／外側シナリオレイヤーの CSV 生成）として整理。
- 収穫（`HarvestBatchPlugin`）は、大杉さんのモデル（`cap_hard=収穫予想量`＋操業カレンダーで収穫週のみ稼働）で置き換え可能か検討（plugin 依存を減らす）。

## 6. 関連論点：CO が「どこに」出るか＝decoupling 位置（別リクエストの種）

大杉さん指摘の「InBound leaf を buffering stock に定義すれば CO が発生する」は本リクエストの隣接テーマ。**demand-anchored 設計は欠品を隠していない**——decoupling point（buffering stock）の置き場所が「需給ミスマッチ＝CO がどのノードに顕在化するか」を決める。顧客側欠品として語るなら decoupling を leaf_out 寄りに、供給源不足として語るなら leaf_in 寄りに。**まず CSV のみ（decouple 位置の付け替え）で観測する軽い実験を先行**させ、engine 改修が本当に必要かを見極める（本リクエストの Phase 0 に相当）。下流 leaf_out の S に欠品を露出する件は将来の別リクエスト（fill rate/欠品可視化）として切り出す。

## 7. 影響ファイル（想定）

| ファイル | 変更 |
|---|---|
| `wom/model/plan_node.py` | `operating_calendar` 属性追加。cap_soft は既存。 |
| `wom/engine/backward_planner.py` | `_apply_mom_cap_backward` を cap_soft envelope + cap_hard ceiling に。traversal に休日スキップを SS オフセットと統一。 |
| `wom/engine/forward_planner.py` | cap_soft 違反 flag を活用（既存）。休日スキップ整合。 |
| `wom/engine/capacity_sealer.py` | pipeline へ配線（or ローダに二層設定を吸収）。 |
| `wom/gui/app.py` | capacity_plan.csv ローダを cap_soft 対応。PSIチャートの cap_soft 線が実データで描画される。 |
| `wom/plugins/holiday_calendar_plugin.py` | 「操業カレンダー」を core へ移譲。plugin は "真の撹乱閉鎖" 用の薄いアダプタとして残す（後方互換）。 |
| `data/sample/*/capacity_plan.csv` | `cap_soft` 列を追加（省略時 cap_soft=cap_hard）。 |
| `data/sample/*/operating_calendar.csv`（新規・任意） | node×week の稼働カレンダー。または holiday_calendar から生成。 |

## 8. 段階実装（phased）

- **Phase 0（実験・CSVのみ・現行ブランチ可）**：decouple 位置を付け替え、休日閉鎖で CO がどこに出るか観測（§6）。engine 改修の要否を見極める。
- **Phase 1（cap_soft 復活）**：capacity_plan に cap_soft 列＋ローダ対応。`_apply_mom_cap_backward` を「cap_soft envelope→cap_hard ceiling→CO」に。Forward の cap_soft 違反可視化。→ **工場のシフト制約が demand allocation に効く**。
- **Phase 2（操業カレンダーの core 統合）**：per-node `operating_calendar`＋traversal スキップを SS オフセットと統一。休日を plugin から core へ。→ **休日が "カレンダー・スキップ"（CO を出さない前倒し）として正しく効く**。
- **Phase 3（撹乱層の整理）**：真の撹乱（ストライキ/災害/地政学/コスト）を overlay として明確に分離。収穫の cap_hard 化を検討。

## 9. 後方互換・検証

- **既定値で現行挙動を保つ**：cap_soft 列省略時 `cap_soft=cap_hard`、operating_calendar 未指定時＝全週稼働。→ 既存6ケース＋soysauce の挙動不変を確認。
- 既存 pytest（現行 81 件）緑維持。二層 envelope・カレンダースキップの新規テスト追加。
- 米SC（`rice-japan-2027-2028`）で「収穫週のみ稼働＋cap_hard=収穫量」を新モデルで再現し、`HarvestBatchPlugin` と同等の PSI が出るか比較。
- soysauce で「2直=cap_soft、3直=cap_hard、繁忙期に cap_soft 超過→増産 or CO」が demand allocation に効くことを確認。

## 10. 設計判断メモ

1. **plugin を全否定しない**：操業レイヤー（intrinsic）は core へ。だが "真の撹乱イベント"（optional・非intrinsic）は plugin/override のままが妥当。境界は「全ノードが当然に持つ属性か否か」。
2. **cap_soft=0 の意味**：現行は「未設定=無制限」。二層化後も 0 は無制限のままとし、"操業計画を敷かない" 選択を許す。cap_hard=0 の「未設定 vs 意図的全停止」曖昧問題（既知）は operating_calendar 導入で自然に解消（休日は calendar で表現し、cap は能力に専念）。
3. **SS_Days との統一が鍵**：SS は既に traversal のオフセットに入っている。休日スキップを同じパイプに載せることで、大杉さんの「置く週をズラすだけ」という自然な実装イメージに一致する。
4. **論文との接続**：本統合は「操業カレンダー×シフト能力×収穫制約」を、plugin の寄せ集めではなく **統一された配置週・能力モデル**として説明できるようになり、経営工学的な一般性（撹乱×ノードの網羅）の土台になる。

## 11. 退行防止（Anti-Degrade）― cap_soft の教訓を制度化

**教訓の精密化**：cap_soft の退行は「テストが皆無」だったからではない。`tests/test_step7_capacity.py::test_cap_soft_violation_no_movement` は**存在し、Forward の cap_soft 違反フラグは今も生きている**。死んだのは (i) **Backward の demand envelope としての cap_soft 使用**（そもそも未実装）と、(ii) **CSV→ローダ→ノードのデータ経路**（capacity_plan に列が無く、ローダが cap_hard しか読まない）。既存テストは**ノードを直接 `set_capacity` して CSV をバイパス**していたため、この2つの穴を誰も踏まなかった。
→ **原則：機能ごとに "入力→処理→出力" を跨ぐ3層テストを必須化する。**

### 11.1 （必須）3層テスト方針
各機能（cap_soft 二層 envelope／操業カレンダー・スキップ／SS 統一）に、以下3層を必ず持たせる：
1. **Unit（望む挙動）**：ノード単体で望む出力を**固定値 assert**（例：cap_soft=2・cap_hard=4・需要=6 → `len(psi4demand[w][P])≤4`、`len(psi4demand[w][CO])==2`）。入力を作者が固定するので期待値も決定論的。cap_soft を無視する改変で赤。
2. **Integration（データ経路）**：`cap_soft` 列つき `capacity_plan.csv` を**実ローダで読み込み**、`node.cap_soft(w)==CSV値` を assert。← **今回欠けていた層**。ローダが列を無視した瞬間に赤。
3. **E2E ゴールデン（スナップショット）**：サンプルケースを**入力ごと凍結**（バージョン管理下の固定データ）し、既知良好な1回の実行から主要KPI（GM・PSI 形状ハッシュ・CO 数・trust event 数）を **golden ファイルとして記録・コミット**。以後「現行実行 == golden」を assert。入力も出力も固定。意図的変更時は golden を**意図的に再生成・コミット**（差分そのものが監査証跡）。

### 11.2 （整備）ゴールデン・ハーネス
`tools/run_headless_from_folder.py`（GUI 抜きで Load→Planning→PPC 実行）＋ `tests/golden/<case>.json`（KPI スナップショット）を **Phase 1 の先頭で整備**。CLAUDE.md が繰り返し「見送り」と記録してきた "6ケース一括ヘッドレス検証" を、ここで恒久インフラ化する。

### 11.3 （制度）禁足ルール（procedural guardrail・soft）
CLAUDE.md / AGENTS.md に、Planning Engine の**保護対象コア**を列挙して明記する：
`wom/engine/backward_planner.py`, `forward_planner.py`, `plan_copy.py`, `wom/model/plan_node.py`, `wom/model/sc_tree.py`, `wom/engine/push_pull.py`。
ルール文言：「**明示的な指示（Request Letter 参照）が無い限り改変しない。改変時は3層テスト緑必須＋オーナーが差分レビュー**」。＝ゲート式（「絶対に触るな」ではなく「認可＋テスト緑を条件に触る」）。

### 11.4 二重化が必須（禁足ルールだけでは不十分）
cap_soft は**意図的で承認されたリファクタ（v1r0m3）の副作用**で死んだ。禁足ルールは「無認可・不用意な改変」を防ぐが、「**承認された変更の副作用**」は防げない。それを機械的に捕まえるのは**テストのみ**。さらに AI が markdown のルールに従うかは確率的で保証がない一方、テストは機械が強制する。→ **禁足ルール（soft・意図表明）＋ 3層テスト（hard・機械強制）の二重化**を必須とする。

## 12. ステータス行

実装ブランチは当初案の `wom-v1r2m0_test` ではなく **`wom-v1r2m2`** で実施（2026-07-30）。

```text
[x] 起草（本レター）
[x] オーナーレビュー・承認（Phase 範囲の確定）
[~] Phase 0（decouple 位置実験・CSVのみ）  ← Phase 1a を優先し省略（engine 改修の要否は Fork A で解消）
[x] Phase 1a（ゴールデン・ハーネス整備：tools/run_headless_from_folder.py + tests/golden、12ケース）
[x] Phase 1b（cap_soft データ経路＋Forward可視化＋Backward envelope・Fork A・3層テスト）
[x] Phase 1 検証（soysauce-jpy でシフト制約可視化・101件全緑・golden 緑・GUI 確認）
[ ] Phase 2（操業カレンダー core 統合・SS 統一 ＋ 3層テスト）
[ ] Phase 2 検証（休日=カレンダースキップ・rice 収穫再現・golden 緑）
[ ] Phase 3（撹乱層の分離整理）
[x] CLAUDE.md/AGENTS.md に禁足ルール（保護対象コア＋3層テスト条件）を明記
[x] オーナー commit / push（wom-v1r2m2：Phase 1a=043a6d7 / 1b データ経路=4a633f9 / 1b Slice2=49d2edd）
```

**実装メモ（当初設計からの確定事項）**：cap_soft は全て **Fork A＝フラグのみ・lot 不動**で実装（配置は cap_hard が支配、CO 閾値も cap_hard のまま）。これにより既存12ケースの psi/ppc は不変で golden 緑を維持。二層 envelope の「増産余地を使う」は placement 変更ではなく残業帯の可視化（Forward=実行/psi4supply、Backward=計画/psi4demand の2レイヤー）として表現した。§5.2 の CO 閾値を cap_soft 側に動かす案は不採用（需要は常に cap_hard まで充当されるため退化する）。
