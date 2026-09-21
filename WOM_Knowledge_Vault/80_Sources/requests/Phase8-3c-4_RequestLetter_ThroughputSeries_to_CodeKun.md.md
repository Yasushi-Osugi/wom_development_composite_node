---
tags: [wom, source]
---
# requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md) · [原文テキスト](../../90_Raw/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## 原文の見出し

- Phase 8-3c-4 Request Letter — 訂正と、案5（図が比べる系列を処理量にする）
- 0. **まず訂正する。エンジンは正しかった。誤っていたのは私（Claude君）の読みである。**
- 何を間違えたか
- 誤りが入っている記録
- 正しい所在
- 案1〜4 は全部落とす
- X1. `capacity_series` が「何の系列か」を宣言する
- X2. S3 の図とラベルを、宣言に従わせる
- X3. Gate 0 条件11 — ラベルと宣言が一致する
- スコープ外（やらないこと）
- 完了条件
- 報告してほしいこと

## 関連する知識源

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 8-3c-4 Request Letter — 訂正と、案5（図が比べる系列を処理量にする）

正典: `requests/Phase8_DesignMD_CockpitGUI.md` rev.6 §4 S3 Run
前提: `dac6887`（Phase 8-3c-3）＋ Code君の U1/U2 測定報告

---

## 0. **まず訂正する。エンジンは正しかった。誤っていたのは私（Claude君）の読みである。**

Code君の報告を受けて、Claude君の側で実測した。

```
週           W14    W15    W16    W17    W18    W19    W20    W21
P           1286   1286   1286      0   1000   1000   1000   1000
S           1142   1286   1286   1286      0   1000   1000   1000
I           1286   1286   1286      0   1000   1000   1000   1000
actual_s    1142   1286   1286   1286      0   1000   1000   1000
cap_hard  1500.0 1500.0 1500.0 1500.0    0.1 1500.0 1500.0 1500.0
```

**閉鎖週 W18 の処理量は 0。実出荷も 0。閉鎖は守られている。**
`S[w] = P[w-1]` の関係が表にそのまま出ており、Backward は閉鎖週の出荷を W14〜W17 に
前倒し済みである（`P[W17]=0` → `S[W18]=0`）。

### 何を間違えたか

`plan_mode=='push'` で封印が skip される、という**機構の観察は正しかった**。
そこから導いた結論が誤っていた——**`P` を「このノードの生産量」と読んだ。**
push ノードの `P` は**入庫**である。

しかも `forward_planner.py` 468行のコメントがそう書いている。

> their P bucket holds incoming inventory (already produced upstream),
> not production at this node.

**私はこのコメントを「2つの意味が衝突している証拠」として引用しながら、
自分は誤った方の意味で読み続けていた。**

### 誤りが入っている記録

```
2fc7f4b  commit_msg52  「閉鎖週に 1000 lot 生産していて、封じられず、100% 成立と報告される」
                        「golden がこれを祝福してきた」                      <- 誤り
cce752f  8-3c-2 依頼書  §1 全体がこの前提の上に建っている                    <- 誤り
dac6887  8-3c-3 依頼書  案4 の成否基準「2,000 lot の行き先を追えるか」        <- 成立しない
```

履歴は書き換えない。**本依頼書と、そのコミットメッセージに訂正を残す**——設計書
rev.6 で `cap_hard` の語を訂正したときと同じ扱いにする。

### 正しい所在

**数字は正しかった。図が嘘をついていた。**

```
結論行   「130週中130週は能力内（100%）」          正しい
図       棒（入庫 P）を線（処理能力 cap）と比べている   これが誤り
```

`cap_hard` は**処理能力**である（T1 で「型 A の cap_hard は加工スループット
（縫製・組立・瓶詰）」と結論が出ている）。**処理能力と比べるべきは処理量であって、
入庫量ではない。**

### 案1〜4 は全部落とす

4案とも「閉鎖が守られていない」という誤った前提の上に建っていた。前提が消えたので
4案とも消える。**案4b（処理量を絞って後追い出荷）だけは本物の穴を突いている**
——処理能力を実際に超えても現行 WOM は何も言わない（Code君の人工ケースで
`実出荷 1000 > cap 800`、`sealed 0`）。**だが本回には入れない。** 現行のどのモデルも
通らない経路であり、「後追い出荷」は push ノードの計画意味論の変更（バグ修正ではなく
設計判断）だからである。**その経路を通すモデルを用意してから、独立の回で扱う。**

---

## X1. `capacity_series` が「何の系列か」を宣言する

いまの `capacity_series` は `p`（入庫または生産）だけを持ち、**それが何であるかを
言わない。** 画面が「P だろう」と決めて比べた結果が今回の誤読である。

**系列を選ばせない。1本だけ出し、それが何かを一緒に出す。**

```python
capacity_series[product][node] = {
    "week_labels":     [...],
    "series":          [...],      # 比べるべき系列。1本だけ
    "series_kind":     "throughput" | "production",
    "series_label_ja": "処理量（lot）" | "生産量（lot）",   # 語はここにだけ置く
    "shortfall":       [...],      # 供給不足で通せなかった量（push のみ。他は 0）
    "cap_hard":        [...],
    "cap_soft":        [...],
}
```

```
plan_mode == "push"   series = 実出荷（actual_s）   series_kind="throughput"
それ以外              series = psi4supply[w][P]     series_kind="production"
```

**`S`（需要階段）ではなく実出荷を採る。** `S` は「通す予定だった量」、実出荷は
「実際に通った量」である。**能力が縛ったかどうかを問う図なら、比べるべきは実際に
通った量**——`S` を使うと、実際には出荷されていない量を「処理した」と主張してしまう。
`-alloc`（P_opt・cap=800）の W17 で `S=686 / 実出荷=0` と両者が食い違う実例がある
（合計でも S 78,709 / 実出荷 73,907）。

実出荷は planner 内部（`self._actual_s`）にあり `_planning_state_extras()` からは
届かないが、**ノード側に `node._push_shortfall[w]` がある**（`forward_planner.py:522`）。

```
actual_s   = available[:total_cnt]
shortfall  = max(0, total_cnt - avail_cnt)
→ 実出荷 = len(psi4supply[w][S]) - node._push_shortfall[w]     （厳密に成立）
```

**`p` という鍵は残さないこと。** 残すと「どちらを使うか」の選択が画面側に戻り、
今回の欠陥が復活する余地ができる。**選択肢を消すのが修正の中身である**
（K1「語は1箇所にだけ定義する」の系列版）。

- 足す先は `_planning_state_extras()`。`planning_state=True` のときだけ通るので
  **golden は1バイトも変わらない**（Q3 / N4 と同じ形）
- `plan_mode` の判定は**ここで一度だけ**行う。`s3_view_model` にも `s3_run` にも
  書かないこと
- **`shortfall` を一緒に載せる理由**——実出荷が低い週の原因は2つある。
  「能力で通せなかった」と「そもそも物が無かった」である。**図は「能力 vs 処理量」
  なのに、供給不足の凹みが同じ形で出る。** 注意書きでは防げない（K2 / M1 で
  繰り返し確認したとおり、**注釈より構造**）。`shortfall` を持たせ、補助パネルに
  「供給不足で処理できなかった週: N週」と出せば、見ただけで区別がつく。
  論点3 でも必ず要る情報である
- **`node._push_shortfall` は private 属性の直読みである。** 本回では公開属性に
  変えない——「エンジン無変更」の保証を崩さないため。**論点3 で
  `forward_planner.py` を触るので、そのときに公開属性へ格上げする**（申し送りに
  「いつ返すか」まで書く）

## X2. S3 の図とラベルを、宣言に従わせる

```
y軸        = series_label_ja（view が出した語をそのまま使う）
タイトル   = f"{node} — {series_label_ja の単位を除いた語} vs Capacity Limits"
```

**語は `series_label_ja` にだけ置く。** 画面側にもテスト側にも
「`kind` → 語」の対応表を書かないこと——書けば語が2箇所以上になり、K1 に反する。
（Claude君の当初案は条件11 のテスト側に対応表を持たせる形で、**K1 を条件に書き
ながら自分で破っていた**。Code君の指摘で直した。）

**系列が変わればラベルも変わる。** 同じ「P（lot）」の下で中身がノードによって変わる
のは、本セッションで繰り返し直してきた欠陥そのものである（`⚑` が画面ごとに違う意味を
持っていた件、`cap_hard`「超過」の語、`plan_mode` の二義）。

**画面側で `plan_mode` を見ないこと。** 見るのは `series_kind` だけにする
（計算と描画を分ける、Phase 8-1 からの柱）。

補助パネルのノード一覧・結論行は**そのまま**。`capacity_events` 由来なので影響しない。

## X3. Gate 0 条件11 — ラベルと宣言が一致する

今回の欠陥は「図の軸が、実際に描いている系列と違うものを名乗っていた」ことである。
**条件1〜10 のどれも、軸ラベルと中身の対応を見ていない。**

```
条件11-a  図の y 軸ラベルが、view の series_label_ja と一致すること
条件11-b  2つの series_kind で、ラベルが互いに異なること
```

- テストは**語を持たない**。「宣言と一致するか」と「2つの kind で違うか」だけを見る
- `-alloc` の S3 には `push`（Bottling）と `push_sub`（Brewing / Materials）が同居する。
  **1つの fixture で両方の kind を検査でき、X2 前に落ちることも確認できる**
  （現状は全ノードが「P（lot）」のため）
- 特定の画面・ノード名を名指ししない。**S4/S5 で別の系列を描くときもそのまま効く**
- **X2 を入れる前に条件11 を書き、その時点で落ちることを確認してから緑にすること**
  （8-1b から続けている作法）

---

## スコープ外（やらないこと）

- **案1〜4b のいずれも実装しない。** 4案の前提は消えた。案4b は別回
- **論点3（1週のずれ）**——Backward が閉鎖を出荷週に、Forward の封印が入庫週に
  適用している件。`-alloc` の「W17 の実出荷が 0」も同じ根と見られる。**次回**
- **U2（PPC が在庫保有費にも中間ノードの未充足にも反応しない件）**——事実は確定した。
  S4 Evaluate の設計で扱う
- `Buffer_Chip_TW` の `cap_hard=1350` の意味（不明のまま。記録済み）
- L1〜L3 ／ 子ノードへの BAU 射影 ／ oil の表示桁 ／ 幅ゼロの文言 ／
  `state_header.py` の `P_bau` ／ `frame.py` の private 属性直読み ／
  oil の PPC が CNY 為替行欠落で落ちる件

---

## 完了条件

1. `capacity_series` が `series` / `series_kind` を持ち、**`p` は残っていない**
2. `plan_mode` の判定が `_planning_state_extras()` の1箇所だけにある
3. 図の y 軸ラベルとタイトルが `series_kind` に従う
4. **結論行の数字が変わらない**（`130週中130週は能力内（100%）`）——**もともと正しかった**
5. **`Bottling_Noda` の図で、棒が cap_hard の線を超えない**（これが本回の目的）
6. Gate 0 条件11 が入っており、X2 前に落ちることを確認済み
7. **golden 13ケースが緑**（`planning_state=False` の経路に1行も足していない）
8. 既存 **509 passed / 3 skipped** が維持されている（条件11 の分だけ増える）

## 報告してほしいこと

- 条件11 が X2 前に落ちたときの、落ちた状態とラベルの値
- `series_label_ja` を画面が使うだけで済んだか。**`plan_mode` や `series_kind` を
  画面側で分岐に使う必要が出たなら、それ自体を報告すること**（切り分けが足りない合図）
- **`series_kind` が二値で足りるか**——golden 13ケースの `capacity_series` に載る
  ノードの `(plan_mode, node_type)` 分布を出すこと。`push` でも `leaf_in`/`mom` でも
  ないノードに cap があれば、「生産量」というラベルが実態（入庫）と合わない
- 型 B（`Buffer_Chip_TW`）の図が、この変更でどう見えるか。
  **`Buffer_Chip_TW` の cap_hard=1350 は下流 `FoundryTW` の cap と同値である**
  （`WaferFab_TW` は 20000）。複写の疑いに根拠があるが断定はしない——手がかりとして記録
- `-alloc` の W17 で実出荷が 0 に凹むのは**本物の事象**（論点3 の現れ）であり、
  本変更が作った欠陥ではない。目視 QA のとき混同しないよう、報告に明記すること

````
