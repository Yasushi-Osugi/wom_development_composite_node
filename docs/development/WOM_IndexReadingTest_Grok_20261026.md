# 索引の読解試験 v0.1 の結果 — Grok、2026-10-26

- 試験：`requests/BSSEAF_IndexReadingTest_v0.1.md`（問 1〜10）
- 受けた AI：Grok（新しい会話。経緯・chatlog なし）。§2 の本文を貼り付けて渡した
- 対象の版：`02e4210`（GitHub。回答は Start Here「改4」・意味体系 v0.3 を読んでいる）
- 採点：Claude君（2026-10-26）、採点の表 `requests/BSSEAF_IndexReadingTest_v0.1_AnswerKey.md`

## 1. 採点

| 問 | 判定 | Start Here から | 気づいたこと |
|---|---|---|---|
| 1 | ○ | 辿れた | 「いつ届くかは決まっていない、扱いは未決」。U1 の名前は挙げていない |
| 2 | ○ | 辿れた | 前の期間の混入と、受渡点での引渡しの完了で数えること |
| 3 | ○ | 辿れた | ⑤、③ は 0 |
| 4 | ○ | 辿れた | (b) 数量配分モードを見つけ、確かめることを 4 点（identity、鍵と数量、期間・能力の固定、表2）。作業用の写しで回すことは挙げていない。(c) は二重計上と金額の入力は挙げたが、期間が 104 週に固定、PPC を無条件に呼ぶ、は挙げていない（薄い） |
| 5 | ○ | 辿れた | |
| 6 | ○ | 辿れた | 境界の効果には触れていない |
| 7 | ○ | 辿れた | 大杉さんの判断（D21）であることは書いていない |
| 8 | ○ | 辿れた | cap_hard 側の上限、直列の inbound、既定 OFF。LP と貪欲法の別には触れていない |
| 9 | ○ | 辿れた | README §6 の古い記述との食い違いには気づいていない |
| 10 | △ | 辿れた | 意味体系の U1〜U4 だけ。化粧品の事例の未決（H9・H10、計画の最初の週の lot、受渡点、市場の優先）を挙げていない |

**合格**：E4 に関わる問（3・4(b)・5・8）はすべて ○。○ 9・△ 1・× 0。10 問とも Start Here から辿れた（§0.1 の表の順）。

## 2. Claude Code（新しいセッション）との違い

- 読んだファイルは 8 つでほぼ同じ（Code君は加えて `flow_check.py`）。どちらも §0.1 の表の「意味体系 → 三層設計 MD → 事例」の順に辿った。
- 答えの深さが違う。Code君は文書どうしの食い違い（README §6、三層設計 MD の front matter）と、文書に書かれていないこと（化粧品の木が直列の inbound か）まで指摘した。Grok は文書の要点を正しく拾ったが、事例の側の未決や、文書の食い違いには踏み込まなかった。
- 索引の評価としては、**どちらの AI も同じ道で、迷わずに知識へ辿り着いた**。E4 への打ち手は効いている。答えの深さの差は、読み手の側の差であり、索引の直しは要らない。

## 3. 回答（原文）

**根拠の中心は `docs/WOM_Start_Here.md`（2026-10-26 改4）§0・§0.1 から辿ったものです。** そこから `docs/semantics/supply_allocation.md`（v0.3）、`docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md`、および化粧品関連の報告書・対応表に進みました。

### 問 1
未配分は **50**、配分後の未充足は **0**。  
B の残り 50 は「いつ届く」とは決まっていません（対象にしなかっただけ。扱い自体が未決）。

根拠：`docs/semantics/supply_allocation.md` §4 例1（および §2 の「未配分の需要」「注文残」、§3 の関係式）。Start Here §0.1 も同趣旨。

### 問 2
よくない。  
対象期間中の出荷には、前の期間の需要への遅れた納品が混ざる。実納品（④）は「需要の一件ごとに、受渡点での引渡し完了と照合して数える」ものであり、期間中の出荷量そのものではない。混ざった量を入れると ②＝④＋⑤ が崩れる。

根拠：`docs/semantics/supply_allocation.md` §3.2 と例3、§8 の混同4。

### 問 3
**別の量**（§3 の ⑤ 配分後の未充足）。  
C3a は元の需要のまま計画しており、③（未配分）は 0。期末注文残 192 lot（Serum 104＋Cream 88）はすべてタイの代理店の要求で、Backward の押し戻しで計画期間内に配置・引渡しできなかった分。

根拠：`docs/semantics/supply_allocation.md` §9・確認の問い3；`docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md` §3.1・§3.4；`docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md` §3.1・§3.2（P0＝C3a と同じ 192）。

### 問 4
(a) **要らない**（人が数量／比率を指定する判断の仕方の場合）。  
(b) **ある**。数量配分モード（`tools/run_quantity_allocation.py` ＋ `wom/allocation/handoff.py` の `write_demand_for_quantity_allocation()`）。使う前に、identity モードであること、配分ファイルの鍵（sku_id, region）と数量が需要と整合していること、期間・能力・操業カレンダーが変わらないこと、Flow Check 表2 で ①〜⑤ が記録できることを確かめる。  
(c) 比率経路（`write_demand_for_allocation()`）は地域×週の重みを全 SKU の行で作り、同じ地域の各行に同じ数量を入れるため、化粧品のように同一 region に複数 SKU があると数量が二重計上になる（検査で止まるようになったが、その経路自体は金額前提の入力も読む）。

根拠：`docs/semantics/supply_allocation.md` §6；`docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md` §3.1；`docs/development/WOM_QuantityAllocationMode_Report.md` 全体（特に C.1・C.4）；`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` Q04・Q09。

### 問 5
**Flow Check 表2 の backlog_end**（要求の Lot_ID と実出荷の Lot_ID を照合して、期間内に一度も出荷されなかった分）を使う。  
最終週の CO や、毎週の CO の合計（lot×週）は使わない。CO[w] は繰り越しの要求であり、最終週に新規に出た未充足や当週出荷の扱いが一致しない。

根拠：`docs/WOM_Start_Here.md` §0.1；`docs/semantics/supply_allocation.md` §3・§8 混同5；`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` Q05（および v0.1 からの訂正）。

### 問 6
**言えない**（計画期間の終わりの状態だけでは判定できない）。  
調べるもの：  
- 継続する需要の水準と有効な供給能力（歩留まり・休みを引いたもの）の関係  
- 先行生産で対象期間を満たせるか（期間初めからの累計能力と累計需要の関係）  
- 在庫量・保管期間・製品年齢が許容範囲か  

根拠：`docs/semantics/supply_allocation.md` §7。

### 問 7
**業務の欠品としては扱わない**（計画の境界の効果）。  
配分合計を能力合計にそろえても、計画の最初の週（原料 LT のため作れない）と最後の週付近（店頭在庫の時間や期間外に需要がないため余裕が使えない）の端の効果で 4 lot 残る。期間を前後に延ばすと消える種類の量。

根拠：`docs/semantics/supply_allocation.md` §7「計画の境界の効果」；`docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md` §3.2・§4（P1 の ⑤＝4 の内訳と理由）。

### 問 8
**同じではない**。  
能力の層の `unallocated` は「設定した能力・前倒し窓の下で、内部の計画へ配置できなかった量」。③（Management が対象外にした量）とも ⑤（Forward 後に判定時点まで引渡し未完了の量）とも異なる。  
化粧品に当てはめる前に：木が直列 inbound の条件を満たすか、上限が `shippable_limit()`（cap_hard 側）であることと化粧品の cap_soft 平準化方針が対応しているか、既定 OFF と `max_advance_weeks` の設定を確かめる。

根拠：`docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md` §2 WOM-ALLOC-07；`requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md` Q10。

### 問 9
**採用されている**（§2 用語の定義と §3 数量の関係）。  
大杉さんが 2026-10-26 に採用（対応表 v0.2 §4 の J1。GPT君のレビューを補って）。  
化粧品での実行確認：数量配分モードの C3a 写しで ①〜⑤ が Flow Check 表2 と一致（V09）、P1 で ③ と ⑤ が別々に記録された、と文書に明記されている。

根拠：`docs/semantics/supply_allocation.md` §0（採否表）；Start Here §0.1。

### 問 10
意味体系 §5 の未決事項（保留）：  
- U1：未配分の需要の扱い（失うか、繰り越すか）  
- U2：納期延期の規則  
- U3：配分の判断の基準（利益の場合の細部など）  
- U4：配分の時間の粒度（合計だけか、週単位までか）  

一般則は未決で、事例ごとに決める。

根拠：`docs/semantics/supply_allocation.md` §5・§0。

---

**読んだファイル（読んだ順）**  
1. `docs/WOM_Start_Here.md`（入口。§0・§0.1 で供給配分の意味体系と三層設計 MD へ案内）  
2. `docs/semantics/supply_allocation.md`（§0〜§10。例題・未決事項・確認の問いが問1〜7・9・10 の直接の根拠）  
3. `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md`（特に §2 WOM-ALLOC-07、§3.1 数量配分モード）  
4. `docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md`（C3a の 192 lot）  
5. `docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md`（P0/P1 の ①〜⑤、境界効果の 4 lot）  
6. `docs/development/WOM_QuantityAllocationMode_Report.md`（数量配分モードの経路・二重計上の問題）  
7. `docs/semantics/README.md`（採否と根拠の読み方）  
8. `requests/BSSEAF_SupplyAllocation_ALC_Mapping_v0.2.md`（Q05 の数え方、Q04/Q09/Q10）  

迷った点はほとんどなく、Start Here §0.1 の表が「意味体系 → 三層設計 MD → 事例報告書」の順を明示していたため、そのまま辿れました。化粧品の具体数値は Start Here が指す事例報告書で確認しました。