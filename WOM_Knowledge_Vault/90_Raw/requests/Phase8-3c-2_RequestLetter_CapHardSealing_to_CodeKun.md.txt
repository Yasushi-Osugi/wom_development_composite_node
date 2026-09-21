# Phase 8-3c-2 Request Letter — 能力の封印が、decoupling ノードで効いていない

正典: `requests/Phase8_DesignMD_CockpitGUI.md` rev.6 §4 S3 Run
前提: `2fc7f4b`（Phase 8-3c 追補 Q3・golden 13ケース緑）

---

## 0. **これは実装依頼ではない。調査依頼である。**

**直し方を指定しない。** 明らかに見える直し方が、測ったら使えなかったからである
（§2）。本回で頼みたいのは **切り分けと、選択肢を数字つきで出すこと**であって、
コードを変えることではない。

**T1 / T2 / T3 を終えた時点で止めて報告すること。** 実装は、選択肢を見てから
大杉さんが決める。

---

## 1. 何が起きているか（実測）

Q3 で「Golden Week 工場閉鎖」を本当の閉鎖（`cap_hard=0.1`）に直した結果、S3 が
「130週中130週は能力内（100%）」と出るようになった。**だがこれは誤りである。**

```
soysauce-jpy-2027-alloc  2027-W18:  P= 686   cap_hard=0.1   cap_hard_sealed=0
soysauce-us-2027         2027-W18:  P=1000   cap_hard=0.1   cap_hard_sealed=0
soysauce-jpy-2027        2027-W18:  P=1000   cap_hard=0.1   cap_hard_sealed=0
```

**上限 0.1 lot の週に 1000 lot 生産していて、封じられず、100% 成立と報告される。**

`soysauce-us-2027` は**本セッション以前から `0.1`** だった。つまり Q3 が壊したのでは
なく、**Q3 が見えるようにした既存の欠陥**である。そして **golden がこれを祝福して
きた**——`forward: {cap_hard_sealed: 0}` を正常として固定していた。

### 原因は特定済み

ForwardPlanner に入る直前の `Bottling_Noda` を計測した。

```
[before] node_id=IN:mom:Bottling_Noda:Soy_Sauce
         plan_mode='push'   node_type='mom'
         cap_hard(W18)=0.1  cap_soft(W18)=0.0  len(P)=0
[after ] cap_hard(W18)=0.1  len(P)=1000  sealed=0
```

```python
is_push_mode = (node.plan_mode == "push")    # PUSH decoupling (Buffer_Wafer_TW等)
...
if not is_push_mode and ch > 0 and len(node.psi4supply[w][P]) > int(ch):
```

**`cap_hard` は正しく 0.1 で届いている。判定式も正しい。`is_push_mode` が True
なので、条件に入る前に丸ごと外れている。**

`push_config.csv` が `Bottling_Noda` を decoupling 点に指定し、
`push_pull.py:227` が `plan_mode = PUSH_MODE` を立てている。**設定どおりである。**

### 何が衝突しているか

除外の意図はコメントに書かれている。

> PUSH decoupling nodes (e.g. Buffer_Wafer_TW) skip sealing:
> their P bucket holds incoming inventory (already produced upstream),
> not production at this node.

**純粋なバッファ節点**を想定した除外であり、その限りでは正しい——上流で物理的に
作られて届いた在庫を、その場所の能力で切り捨てたら在庫が消える。

ところが `Bottling_Noda` は **decoupling 点であると同時に、実際に生産する
mother plant** である（`node_master.csv`: 瓶詰・完成品工場、`sc_tree_master.csv`:
`node_type=mom` / `demand_envelope=soft` 平準化生産）。**自前の cap_hard を持つ。**

**`plan_mode == "push"` が2つの意味を背負っている。**

```
(a) このノードは生産しない。P は上流からの入庫在庫である     <- 除外が想定したもの
(b) このノードは decoupling 点である（生産するかは別）      <- Bottling_Noda
```

除外は (a) を意図して (b) で判定している。**「同じ語が2つの意味を持つ」欠陥家族**
である（`⚑` が画面ごとに違う意味を持っていた件、`gap_abs` の件と同じ）。

---

## 2. **明らかな直し方が効かないことも測った**

私（Claude君）は最初こう考えた——「純粋なバッファは自前の生産能力を持たないので
`cap_hard=0` のはずで、`ch > 0` の条件で既に除外される。だから `is_push_mode` の
除外はそもそも要らないのではないか」。

**全サンプルモデルの decoupling ノードを洗い出したら、成り立たなかった。**

```
モデル                        decoupling node      node_type/envelope   cap_hard
apparel-global-2028-2029      Garment_BD           mom/-                3500
apparel-global-2028-2029      Garment_PT           mom/-                2000
ev-europe-2026                Factory_Import_HU    mom/-                 150
ev-thailand-2026              Factory_Import_CN    mom/-                 150
ev-thailand-2026_update       Factory_Import_CN    mom/-                 105
smartx-2027-2029              Buffer_Chip_TW       mom/-                1350   <- 除外の原型
soysauce-eu-2027              Bottling_Noda        mom/-                1500
soysauce-jpy-2027-alloc       Bottling_Noda        mom/soft              800
soysauce-jpy-2027             Bottling_Noda        mom/soft             1500
soysauce-us-2027              Bottling_Noda        mom/-                1500
```

**10件すべてが `cap_hard` を持ち、10件すべてが `node_type=mom` である。**
とりわけ **`Buffer_Chip_TW`——コメントが除外の原型として挙げているまさにその型の
ノード——が cap_hard=1350 を持っている。**

つまり:

- 「`cap_hard>0` なら封じる」に変えると、**10件すべての挙動が変わる**
  （golden の該当ケースが全部動く）
- しかも**除外が守ろうとしていた原型まで封じてしまう**ので、
  「在庫が消える」という元の危険がそのまま戻る

**判定軸として使えない。** 私の案は取り下げる。

---

## 3. さらに、封じ方そのものが論点である

いまの封印は、溢れた分を **`CO[w+1]`（未充足需要）** に送る。

```python
excess = node.psi4supply[w][P][int(ch):]
node.psi4supply[w][P] = node.psi4supply[w][P][:int(ch)]
node.psi4supply[w + 1][CO].extend(excess)
```

decoupling ノードの P は「上流から届いたもの」である（`forward_planner.py:191-196`
のコメント参照——`plan_mode=="push"` の MOM は `psi4demand[w][P]` で上書きされず、
上流の PUSH 伝播で埋まる）。**届いた物を「未充足需要」に変えるのは、意味が違う。**

物理的に正しいのはおそらく **「処理能力で通せる分だけ通し、残りは在庫（I）に置く」**
であって、「未充足にする」ではない。

**つまり論点は2つある。**

```
論点1  decoupling かつ生産する mom を、封じるべきか        （判定軸の問題）
論点2  封じるなら、溢れた分は CO か I か                   （封じ方の問題）
```

**どちらも設計判断であり、本回で決めない。**

---

## T1. 切り分け — `plan_mode="push"` のノードで、P は何を表しているか

10件それぞれについて、**P が「そのノード自身の生産」なのか「上流から届いた入庫」
なのか**を、コードとデータから判定して報告してほしい。

- `_propagate_to_parent()` が P を埋めるのか、`psi4demand[w][P]` から来るのか
- その節点に上流（子）があるか。あるならそこが生産しているのか
- `cap_hard` は何の能力として設定されているか（生産能力／処理能力／受入能力）

**10件を1つの表にすること。** 型が2つに割れるのか、もっと多いのかが、判定軸を
決める材料になる。

## T2. 選択肢を、影響の数字つきで出す

最低3案を、それぞれ**どのモデルで何がどれだけ変わるか**を実測して並べてほしい。
案を推すのではなく、**判断材料を揃えること**が仕事である。

```
案1  is_push_mode の除外を外す（全 decoupling を封じる）
案2  「生産する decoupling」と「純粋バッファ」を別の属性で分け、前者だけ封じる
     （その属性を何にするかも提案に含める。plan_mode を分けるのか、
      sc_tree_master に列を足すのか、node_type で割るのか）
案3  封じ方を変える（溢れた分を CO ではなく I へ）。論点2 への対応
```

各案について:

- **`cap_hard_sealed` / `cap_soft_violation_count` が、13の golden ケースで
  どう変わるか**（件数）
- **PPC の実現利益がどれだけ変わるか**（金額。1ケースでよい——soysauce-jpy-2027）
- 在庫（I）がどう動くか——**「在庫が消える」危険が実際に起きるかどうか**

## T3. golden への影響を、先に測って報告する

**この修正は golden 13ケースのうち何件を動かすか。** 案ごとに件数と、変わる項目
（`forward` / `backward` / `psi`）を出してほしい。

Q3 のときは「`psi` の4ノードだけ・`forward` 不変」という小さな変化だった。
今回は `forward` が動く——**`cap_hard_sealed` が 0 でなくなること自体が、この
修正の目的**だからである。だからこそ、**動く前にその大きさを知っておきたい。**

---

## スコープ外（やらないこと）

- **実装。** T1〜T3 の報告で止めること
- `holiday_calendar.csv` の値（Q3 で修正済み）
- `_apply_supply_closure()`（`value` を `cap_hard` にする仕様どおりに動いている）
- S3 の画面（結論行・図・ノード一覧。エンジンが正しくなれば数字は自然に直る）
- L1〜L3 ／ 子ノードへの BAU 射影 ／ oil の表示桁 ／ 幅ゼロの文言 ／
  `state_header.py` の `P_bau` ／ `frame.py` の private 属性直読み ／
  oil の PPC が CNY 為替行欠落で落ちる件

---

## 完了条件

1. T1 の表（10件 × P の意味）が出ている
2. T2 の3案が、golden 件数・PPC 金額・在庫の動きつきで並んでいる
3. T3 の影響範囲が案ごとに出ている
4. **コードが1行も変わっていない**（テストも golden も無変更のまま）

## 報告してほしいこと

- 10件が**いくつの型に割れたか**。2つならその境界は何か
- **`Buffer_Chip_TW` に cap_hard=1350 が設定されている理由**が、データやコードから
  読み取れるか（読み取れないなら「読み取れない」と書くこと——それ自体が
  「cap_hard が2つの意味で使われている」証拠になる）
- 案2 を採る場合、**その属性をどこに持たせるのが自然か**（設計の意見として）
- T1〜T3 の過程で、**この3案のどれでもない筋**が見えたら、それを書くこと
