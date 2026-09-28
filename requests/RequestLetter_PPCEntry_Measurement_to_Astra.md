# Request Letter：PPC 入口の実測（LOVEM 段階 D の先行分）

- 宛先：GPT-6 Astra君
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 種別：読み取り・測定のみ（core・データ・golden の変更なし、commit・push なし）
- リポジトリ／ブランチ：`Yasushi-Osugi/wom_development_composite_node` / `wom-v1r5m1_cap_trial`
- 測定基準：`e747936`（2026-09-28 時点の先頭）。ブランチが進んでいても混ぜない。
- 設計の正本：`docs/design/drafts/LOVEM_on_WOM_Observation_Visualization_Design_v0.2.md` の §10.4〜§10.7（Astra君の追補）

---

## 1. 目的と位置づけ

LOVEM の段階 A〜C（ev-thailand）は、Code君が並行して進めます。本依頼は、そのうち**段階 D の「PPC 入口の実測」だけを先に行う**ものです。画面は不要です。

背景：数量の変化が金額に届かない現象を、3回確認しています。

| 観測 | 内容 |
|---|---|
| Trial-02 §7（`4ed2f14`） | soysauce-jpy-2027-alloc の P_opt で、Bottling を一度も通らない 9,293 lot が PPC に計上（売上 73,461,824円・粗利 24,625,145円） |
| Explicit Closure SE1（`1b1f426`） | Cookie で Factory_GP_CN の供給が 1,450 lot 減っても、PPC は1円も変わらない |
| 休業行の移行（`e747936`） | 17ケースすべてで PPC 不変 |

v0.2 §10.4 の静的確認では、PPC の入口（`ppc_psi_bridge.psi_to_sales_records`）が leaf_out の Supply S の件数を読み、実出荷（`_actual_s`）を読まないことが分かっています。本依頼では、それを**実行時の数字で確かめ**、PPC をどう直すかを大杉さんが判断するための材料を揃えます。

**修正案は書かないでください。** 事実と、修正の選択肢に関わる観測だけを報告してください。

## 2. 対象

| 対象 | 条件 | 役割 |
|---|---|---|
| 全13 golden モデル＋soysauce-jpy-2027-alloc（原需要・P_opt/800）＋ev-thailand-2026_update | 各モデルの既定の plugin セット（golden の config と同じ） | P1 の fallback・除外の全数調査だけ |
| soysauce-jpy-2027-alloc | P_opt/800（Trial-02 と同条件） | P2〜P4 の主対象 |
| Cookie-jp-2026 | 既定 | P2〜P4。runner で GENERIC とは別のシナリオ分岐を通る（v0.2 §10.5） |

## 3. 測定項目

### P1　入口の fallback と除外の全数調査

runner は、PSI から作った販売記録が PPC の既知の製品・channel と1件も合わないと、生成したサンプル販売データに差し替えます。一部しか合わない場合は、合わない行を捨てます（`ppc_runner.py` の Step 3・4）。どちらも verbose 以外では何も表示しません。

対象の全モデル・全条件について、次を1行ずつ出してください。

- 呼出経路（GUI／headless／cockpit のうち、測定したもの）と、選ばれたシナリオ分岐
- bridge が出した行数と数量（lot・unit）
- フィルタで採用した行数・数量、除外した行数・数量、除外された product／channel の一覧
- `psi_mode`、サンプルデータへの fallback の有無
- leaf_out から channel への対応が一対一か。複数の leaf_out が同じ channel に写像されて合成 lot_id が衝突していないか

**fallback または除外が1件でもあれば、そのモデルの PPC の数字は PSI と対応していません。** この表は最優先で出してください。

### P2　入口の数量：予定 S と実出荷の対応

主対象2モデルについて、leaf_out × 週ごとに次を出してください。

- bridge が読んだ Supply S の件数
- 同じ週の実出荷（`_actual_s`）の件数
- 差（予定 − 実出荷）と、その週の CO
- S の Lot_ID と実出荷の Lot_ID の多重集合の差（件数が一致しても ID が違う場合を分ける）

v0.2 §10.7 の `ppc_entry_records.jsonl` と `ppc_entry_links.jsonl` の形式で保存してください。後で LOVEM の段階 D がそのまま使えるようにするためです。bridge の直前で元の Lot_ID を採取し、合成 lot_id を文字分割しただけの対応は observed にしないでください。

leaf_out に期首在庫があれば、上流で未供給でも leaf_out では出荷できる場合があります。上流の未供給から販売の不成立を推定せず、leaf_out の実出荷を直接数えてください（v0.2 §10.7 の注意と同じ）。

### P3　supplied と existing_ppc の金額差

主対象2モデルについて、次の2つを同じ価格・原価・為替規則で計算し、比べてください。

- **existing_ppc**：現行のまま PPC を実行した結果
- **supplied**：bridge への入力だけを「leaf_out の実出荷（`_actual_s`）の件数 × cpu_size」に差し替えて、同じ PPC エンジンで実行した結果。差し替えは、作業コピー上の monkeypatch か、同じ形式の sales_records を渡す方法で行い、core は変えない。

比べる単位は、全体、product×channel、週です。差は v0.2 §10.6 の分類（数量・時点／集約・ID 追跡／その他）に分けてください。

- 予定週に出荷されず後の週に出荷された分（時点の差）と、期間内に一度も出荷されない分（数量の差）を分ける。
- soysauce-jpy-2027-alloc では、Trial-02 の 9,293 lot・売上 73,461,824円・粗利 24,625,145円が `e747936` でも再現するかを示す。Explicit Closure は soysauce の PSI を変えていないので、同じ値になる見込みです。違えば原因を調べてください。
- Cookie では、SE1 の 1,450 lot の減少が leaf_out の実出荷に届いているか、届いていないならどのノードで止まっているかを示す。

### P4　中間ノードの金額の数量起点（v0.2 §10.5）

主対象2モデルの中間ノード（leaf_out 以外）について、PPC の各ノードの金額がどの数量から計算されているかを、実行時の値で分類してください。

- 自ノードの実出荷
- leaf_out の販売数量から導出（祖先ノードへの配分）
- その他
- 未確認

`ppc_node_basis.csv`（v0.2 §10.7）の形式で保存してください。大杉さんの原則「全ノードで、出荷した Lot_ID の数 × Lot 単価」と比べて、どのノードで何が違うかが分かる形にしてください。

## 4. 成果物

1. 報告書 `docs/development/WOM_PPC_Entry_Measurement_Report.md`
   - 冒頭に P1 の表（fallback・除外があったモデル）と、P3 の金額差の要約
   - **観測／原因仮説／大杉さんの判断が必要なこと** を分けて書く
2. 測定スクリプト `tools/probe_ppc_entry.py`（commit できる状態で渡し、commit はしない。基準 SHA を照合する）
3. 生データ一式（`ppc_entry_records.jsonl`・`ppc_entry_links.jsonl`・`ppc_node_basis.csv`・`ppc_basis_differences.csv` ほか）を ZIP にまとめて大杉さんへ渡し、報告書に各ファイルの SHA-256 を記載する

## 5. 禁止事項と終了条件

- core・サンプル CSV 原本・golden を変更しない。supplied の計算は作業コピー上の monkeypatch か、差し替えた sales_records で行う。
- commit・push・PR をしない。
- PPC の修正案・Request Letter の草案は書かない。
- 価格・原価規則が取得できないノードは「計算不能」とし、単価や引当を補って埋めない。
- 検査できなかった項目は「未確認」とし、推測で埋めない。
- P1〜P4 の報告と生データの受け渡しで終了する。

## 6. 優先順位

時間が限られる場合は、**P1 → P3 → P2 → P4** の順で進めてください。P1 は PPC の数字全体の信頼性、P3 は判断に必要な金額差に直結します。
