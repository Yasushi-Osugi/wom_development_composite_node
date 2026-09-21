---
tags: [wom, source]
---
# requests/Phase8-3c_Addendum_to_CodeKun.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase8-3c_Addendum_to_CodeKun.md) · [原文テキスト](../../90_Raw/requests/Phase8-3c_Addendum_to_CodeKun.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Phase 8-3c Addendum — 実機で出た3件（Q1 / Q2 / Q3）
- Q1. 降りられないのに、降りられるように見えている
- 何が起きたか
- 直すこと
- Q2. Gate 0 条件10 — 「降りられないなら、降りられるように見えない」
- Q3. `holiday_calendar.csv` の「Golden Week 工場閉鎖」が閉鎖になっていない
- 実機で見えたこと
- 測って分かった、もっと大きい話
- 直すこと
- golden への影響（**実測済み**）
- golden の更新について（**独立したコミットにすること**）
- スコープ外（やらないこと）
- 完了条件
- 報告してほしいこと

## 関連する知識源

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 8-3c Addendum — 実機で出た3件（Q1 / Q2 / Q3）

正典: `requests/Phase8_DesignMD_CockpitGUI.md` rev.6
前提: `85e4a43`（Phase 8-3c 実装・501 passed / 3 skipped・golden 13ケース緑）

大杉さんが `python main.py --cockpit` で S1 → S3 を通しで確認された結果、
3件出た。**3件とも、画面を見なければ出なかった。**

---

## Q1. 降りられないのに、降りられるように見えている

### 何が起きたか

S3 の確認は `soysauce-jpy-2027-alloc`（3市場）で行った。S1 に戻って
子ノード欄の `JP 10% / US 45% / EU 45%` をクリックしても何も起きない。

**機能は壊れていない。** N=3 は triangle モードで、**ドリルダウンは元々無い**
（全体が最初から三角図に出ているため。Gate 0 条件4 もそう書いて skip している）。

**問題は、押せないのに押せるように見えることである。**

```python
lbl = tk.Label(row, text=label_text, bg=BG_MID, fg=FG_ACC,      # 青（他のリンクと同じ色）
              font=_JA_FONT, cursor="hand2", anchor="w")         # 指カーソル
lbl.pack(fill="x")
if self._view and self._view["mode"] == "hierarchy":             # バインドは hierarchy だけ
    lbl.bind("<Button-1>", lambda _e, c=child: self._on_child_click(c))
```

**色と指カーソルは無条件、バインドだけが条件つき。** 画面が事実と違うことを
言っている——8-3b-3 で直した「200px 跳ねて『消えた』と読まれた」と同じ家族である。

**これは 8-3c の回帰ではない。Phase 8-2 から入っていた。** 大杉さんが普段
`oil-global-2027`（15市場・hierarchy）を使っておられたので出なかっただけで、
S3 の確認で3市場のモデルに移って初めて踏んだ。

### 直すこと

`wom/cockpit/s1_allocate.py` の `_render_children()` で、**バインドを付けるか
どうかと、見た目を同じ条件から出す**。

```
バインドあり   fg=FG_ACC      cursor="hand2"
バインドなし   fg=FG_WHITE    cursor=""
```

**条件を2回書かないこと**（`if` を1つにして、そこで色・カーソル・バインドを
まとめて決める）。同じ事実を2箇所に書くと片方だけ直る——K1 と同じ理由である。

`is_unallocated` の枝（Phase 8-2a・D1 で「降りる手段は塞がない」と決めた所）は
hierarchy なのでバインドが付く。**そこは見た目も今までどおり**にすること。

---

## Q2. Gate 0 条件10 — 「降りられないなら、降りられるように見えない」

条件4 は「**子を出すなら**バインドがある」を見ており、**triangle モードは
対象外として skip している**。だから Q1 は構造上どの条件にも掛からなかった。

条件4 の**鏡**を足す。

```
条件4   バインドがある行が存在すること           （降りられるなら押せる）
条件10  バインドが無い行は cursor が hand2 でないこと  （降りられないなら押せるように見えない）
```

- 6状態＋S3 の全状態に当てる。**特定の画面・市場名・node_path を名指ししない**
- `_children_frame` の各行を歩き、`w.bind("<Button-1>")` が空なら
  `w.cget("cursor")` が `"hand2"` でないことを検査する
- **Q1 を入れる前に条件10 を書き、その時点で triangle 状態が落ちることを確認して
  から Q1 で緑にすること。** 8-1b から続けている作法である

この条件は S4 / S5 でもそのまま効く。**「押せるように見えるものは押せる」は
画面によらない不変条件**だからである。

---

## Q3. `holiday_calendar.csv` の「Golden Week 工場閉鎖」が閉鎖になっていない

### 実機で見えたこと

S3 の `Bottling_Noda` の図で、cap_hard が 2箇所（2027-W18 / 2028-W18）だけ
**800 → 1500 に跳ね上がっていた**。大杉さんの指摘——「cap_hard は機械装置の
物理上限のような値のはずで、突出が出るのは不自然」。

そのとおりだった。**`capacity_plan.csv` は 130週すべて 800 で綺麗**である。
書き換えているのは `holiday_calendar.csv` と HolidayCalendar プラグインである。

```
holiday_id,holiday_name,                           start_week,end_week,node_name,    effect,        value
GW_2027,   Japan Golden Week factory closure 2027, 2027-W18,  2027-W18,Bottling_Noda,supply_closure,1500.0
```

```python
def _apply_supply_closure(self, nodes, w_idxs, w_lbls, cap_val, name):
    node.set_capacity(w, cap_hard=cap_val)      # value をそのまま cap_hard にする
```

**プラグインは CSV のとおりに動いている。誤っているのはデータである。**

### 測って分かった、もっと大きい話

**同じ「Japan Golden Week factory closure」が4つのモデルに複製されていて、
値が食い違っている。**

```
モデル                    Bottling_Noda の通常能力   GW の値    実際に起きること
soysauce-jpy-2027                    1500            1500      **何も起きない**（no-op）
soysauce-eu-2027                     1500            1500      **何も起きない**（no-op）
soysauce-us-2027                     1500               0.1     正しく閉鎖する
soysauce-jpy-2027-alloc               800            1500      **逆に 87% 増える**  ★実機で見えたのはこれ
```

読み取れる経緯はこうである。

1. もともと4モデルとも通常能力 1500 / GW 値 1500 で、**閉鎖は黙って効いていなかった**
2. 誰かが気づいて **`soysauce-us-2027` だけ 0.1 に直した**。他の3つに反映しなかった
3. `-alloc` を作るとき、配分デモのため**通常能力だけを 800 に下げた**。
   `holiday_calendar.csv` の 1500 が取り残され、**no-op が「逆効果」に化けた**

**「黙って壊れる」欠陥家族の新しい型である**——同じ事実が複数のモデルに複製され、
**片方だけ直された**。大杉さんの方針「誤読を招くものは見つけ次第、関連資料を
全部まとめて置換して落とし穴を潰す」の、データ版がここに要る。

他モデルの規約も確認した。**閉鎖は下げる**が一貫している。

```
Cookie-jp / ev-* / iphone / smartx   0.0 〜 0.5     閉鎖・春節・ディワリ
oil-global-2027                      1.0 〜 500     閉鎖・整備・スト・減産（通常より下）
apparel-us-2026                      1500（通常 15000 の 1/10）
apparel-global-2028-2029             700（通常 3500 の 1/5）／ 400（通常 2000 の 1/5）
```

**apparel の 1500 / 700 / 400 は誤りではない**（通常能力より下がっている）。
問題は soysauce 4モデルだけである。

### 直すこと

**`soysauce-jpy-2027` / `soysauce-eu-2027` / `soysauce-jpy-2027-alloc` の
GW 2行を、既に直っている `soysauce-us-2027` に揃えて `0.1` にする。**

新しい値を発明しない——**同じ祝日・同じノード・同じ規則が既に1つ直っている
なら、それに揃えるのがいちばん安全**である。

### golden への影響（**実測済み**）

`soysauce-jpy-2027` と `soysauce-eu-2027` は golden 13ケースに入っている
（`-alloc` は入っていない）。`soysauce-jpy-2027` を 0.1 に直して実走し、
golden と項目ごとに突き合わせた。

```
period      同じ
products    同じ
config      同じ
forward     同じ    （cap_hard_sealed 0 / cap_soft_violation_count 0 のまま）
backward    同じ
psi         変わる  （Soy_Sauce の4ノード: Brewing_Noda / SP_Soy / Materials_JP / Bottling_Noda）
```

**変わるのは `psi` の4ノードだけ**で、能力挙動のカウンタは動かない。
`soysauce-eu-2027` は同型のはずだが未測定——**Code君が測って報告すること。**

### golden の更新について（**独立したコミットにすること**）

golden は「エンジンの挙動が勝手に変わっていないか」を守る網である。
**今回変えるのは入力データであって、エンジンではない。** だから更新は正当だが、
**エンジンの退行を同じコミットに紛れ込ませないこと**が条件になる。

- **データ修正と golden 再生成だけを含むコミットを1本立てる**
  （Q1 / Q2 のコード変更とは分ける）
- コミットメッセージに、**golden のどの項目が・どのケースで変わったかを書く**
  （上の表の形で。「golden を更新した」だけでは、後から読んで何が起きたのか
  分からない）
- 再生成の**前後で `period` / `products` / `config` / `forward` / `backward` が
  変わっていないことを確認**する。ここが変わったら、それはデータ修正では
  説明できない何かが起きている合図なので、止めて報告すること

---

## スコープ外（やらないこと）

- **`_apply_supply_closure()` のプラグイン側**は触らない。`value` を cap_hard に
  するという仕様どおりに動いており、誤っているのはデータである。
  （「closure なのに上げられる」ことを検知する仕組みを入れるかどうかは別の設計判断）
- `apparel-us-2026` / `apparel-global-2028-2029` の値（通常能力より下がっており、正しい）
- `Materials_JP` の図が読みにくい件（cap_hard 50,000 に対し P が 700 前後で棒が潰れる）。
  誤りではないので申し送り
- L1〜L3（子ノードに「この枝の利益」を出す）／ 子ノードへの BAU 射影 ／
  oil の表示桁 ／ 幅ゼロの文言 ／ `state_header.py` の `P_bau`
- `frame.py` の private 属性直読み、S1⇄S3 遷移の自動テスト（8-3d 以降）
- `oil-global-2027` は PPC が `No FX rate found for currency='CNY'` で落ちるため
  S3 を完走できない（`ppc_fx_rate.csv` に CNY 行が無い）。**別途**

---

## 完了条件

1. Q1: バインドの有無と見た目が**同じ条件から**出ている（条件を2回書いていない）
2. Q2: 条件10 が入っており、**Q1 の前に書いて triangle 状態が落ちることを確認済み**
3. Q3: soysauce 3モデルの GW 値が `0.1` に揃っている
4. golden 再生成は**独立したコミット**。`period`/`products`/`config`/`forward`/
   `backward` が不変であることを確認済み
5. 既存 501 passed / 3 skipped が維持されている（条件10 の分だけ増える）

## 報告してほしいこと

- 条件10 が Q1 前に落ちたときの、落ちた状態と cursor の値
- `soysauce-eu-2027` の golden がどの項目で変わったか（`soysauce-jpy-2027` は
  `psi` の4ノードだけだった）
- Q1 で `is_unallocated` の枝の見た目が変わっていないこと
- 条件10 が S3 の状態にもそのまま効いたかどうか

````
