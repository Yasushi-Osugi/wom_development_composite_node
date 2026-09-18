# Phase 8-3c Request Letter — S3 Run（2枚目の画面）

正典: `requests/Phase8_DesignMD_CockpitGUI.md` rev.5 §4「S3 Run」／§8.2
前提: `4ffe8ec`（Phase 8-3b-3・488 passed / 3 skipped）

---

## 0. この回の主題は S3 ではない — 骨格の仮説の検証である

8-3a の完了条件にこう置いた。

> 8-3c で S3 を足すとき、骨格側（`frame.py` / `navigator.py` / `state_header.py` /
> `ops_bar.py`）に手を入れずに済む

これは 8-3b で1回、8-3b-3 でもう1回遅れた。**2枚目の画面を足すまで反証できない
仮説**であり、本回がその検証である。S3 の作り込みより、**どこに手が入ったかを
正確に報告すること**のほうが価値が高い。

**そして、書く前に読んだ時点で仮説は一部崩れている。** 正直に書く。

| ファイル | 実状 | 手が入るか |
|---|---|---|
| `frame.py` | `self._s1` を `_body` に直接 pack。**画面を差し替える機構はまだ無い**（申し送りに「そうする形にする」と書いてあるだけ） | **入る**（設計どおり） |
| `ops_bar.py` | `⚑ この計画案を保存` と注記 `（計画するのは上の推奨配分です）` が**S1 専用の文言でハードコード**。`set_next_label()` はあるが commit ラベル/注記を変える API が無い | **入る**（想定外） |
| `navigator.py` | `render(current, enabled, passed)` だけ。**無変更で足りるはず** | ここが本当の検証点 |
| `state_header.py` | `pre_plan` / `feasible_plan` 両方を既に扱う | **無変更で足りるはず** |

`ops_bar.py` の2つの文字列は、**同じ事実（いまどの画面か）が骨格と画面の2箇所に
分かれている**形で、K1「語は1箇所にだけ定義する」と同じ家族である。骨格が
「画面ごとに変わる語」を持ってしまっていた。

---

## 1. 測ってわかったこと — S3 の計算は**すでに全部ある**

`tools/run_planning_loop.py` が、S1 の配分から第2層・第3層を回して
`realized` を埋めるところまで headless で完結している。S1 の `commit()` は
その手順1〜3（`new_state()` → `save()` = `pre_plan`）と同じことを既にやっている。

**S3 Run がやるのは手順4〜6だけである。**

```
4. write_demand_for_allocation()  →  demand_forecast_<id>.csv
5. run_headless(model_dir, demand_file=…, planning_state=True)
6. attach_placement() / attach_realized() → save()（state="feasible_plan"）
```

実測（`soysauce-jpy-2027-alloc` / `s1_base` / cap 800 / P_opt、この検証環境）:

```
real 0m9.278s        <- 手順1〜7 の全部。大半は手順5
未充足 0 lot
能力超過 4週（2027-W13, 2027-W17, 2028-W13, 2028-W17）
在庫ピーク 0週
計画 JP15 / US42 / EU42   実績 JP15 / US42 / EU42
```

**9秒は GUI を固めるには長すぎる**（Windows なら「応答なし」がタイトルバーに出る）。
N2 で扱う。

`snap["period"]` は `{"start": <週ラベル>, "weeks": <週数>}` を持つ。
`snap["planning_state_extras"]` は `cap_hard_violation_weeks` と
`cap_soft_violation_weeks` を**別々に**持つ（`realized.capacity_violation_weeks` は
両者を合成した後の値なので、hard と soft を区別したい画面側は extras を読むこと）。

---

## N1. `frame.py` に画面差し替えを入れる

- `_body` の中身を `_current_step` に応じて差し替える。S1 と S3 の2枚だけ
- S3 は **`pre_plan` が保存済みのときだけ有効**（S1 で ⚑ を押していないと配分が
  無い）。`_state is None` なら Navigator 上で S3 は `○`・クリック不可のまま
- `_on_next` / `_on_back` を実際に配線する（S1 の「▶ 次へ：S2 Place」は S2 が
  無いので、**S1 では S3 へ飛ばす**のではなく disabled のままでよい。Navigator の
  `S3 Run` をクリックして入る形にする——`▶ 次へ` のラベルは設計書 §3.1 の
  並びを保つ）
- `_current_screen()` が「いま `_body` にある画面」を返すようにする

## N2. S3 の実行は別スレッドで、画面は待ち状態を出す

9秒間 Tk のイベントループを止めない。**tkinter は単一スレッドなので、
ワーカースレッドからウィジェットに触らないこと。**

```
[▶ 実行] を押す → ボタン disabled、「実行中…」表示
  → threading.Thread が run_headless() だけを回す（Tk に一切触らない）
  → 結果を queue に置く
  → メインスレッドの after(100ms) が queue を見て、取れたら描画
```

失敗したら例外を queue に載せ、**メインスレッド側で** `messagebox` を出す。

**実行は自動で始めない。** S3 に入っただけで9秒走るのは、経営者が誤ってタブを
押した場合に理不尽である。明示的に押させること。

**ディスクに副作用が出ることを画面に書く**——`demand_forecast_<id>.csv` が
モデルフォルダに、`output/ppc/*` と `output/planning_state/<case>/<id>.json` が
出力先に書かれる。

## N3. 結論行（3行・§3.1 の3行以内）

```
104 週中 100 週は能力内（96%）
2027-W13 ほか 4週で能力超過（cap_hard 0週 / cap_soft 4週）、未充足 0 lot
実際に供給できた配分 JP 15 / US 42 / EU 42（計画 JP 15 / US 42 / EU 42）
```

- 総週数は `snap["period"]["weeks"]`。**`realized` には総週数が無い**ので
  スナップショットから取ること
- hard と soft は**区別して出す**（extras から。「3直でも足りない」のか
  「残業すれば入る」のかは経営の判断が変わる）
- 3行目は `realized.allocation` と `state["allocation"]` の並置。**S1 の
  結論行と同じ書式**（`format_market_name()` を使う）

実行前は3行とも空にして、「▶ 実行」を押すよう促す1行だけを出す。

## N4. 週次系列を `planning_state_extras` に足す（**golden は変わらない**）

設計書 §4 の「P vs Capacity Limits（cap_soft 点線・cap_hard 実線・超過週を赤帯）」を
本回で作る。そのために週次系列が要るが、`run_headless()` の返り値には入っていない
（extras が持つのは超過した**週のリスト**だけ）。

**足す先は `_planning_state_extras()`（`tools/run_headless_from_folder.py`）で、
ここは `planning_state=True` のときだけ呼ばれる。** `tests/test_golden.py` は
`planning_state` を渡していない（既定 False）ので、**golden は1バイトも変わらない**
——C8 の「既定 False のときの返却は現行と1バイトも変わらない」という約束は、
まさにこの形の追加を安全にするために置かれたものであり、Phase 7 が
`planning_state_extras` 自体を同じ形で足した前例がある。

```
extras["capacity_series"] = {
    <node_name>: {
        "week_labels": [...],      # nd.week_labels
        "p":           [...],      # len(psi4supply[w][P])
        "cap_hard":    [...],      # nd.cap_hard(w)
        "cap_soft":    [...],      # nd.cap_soft(w)
    }, ...
}
```

- **能力を持つノードだけ**（`cap_hard` も `cap_soft` も全週ゼロなら入れない）。
  実測: soysauce 3ノード / oil 16ノード。16×104×3 ≒ 5,000 個の数値で、量は問題にならない
- 製品が複数ある場合の扱い（ノード名が製品をまたいで衝突しうるか）は**実装前に確認し、
  衝突するなら製品でネストして報告すること**
- `attach_realized()` は**触らない**——`realized` に系列は載せない（設計書 §2.2
  「載せないもの: Lot ID 一覧、週次の全系列。履歴書には結論だけ」）。系列は
  S3 が画面に出すためだけにスナップショットから読む

**`planning_state=False` の経路に1行も足さないこと。** golden 13ケースが緑のままで
あることを確認して報告する。

## N5. 根拠の図 — P vs Capacity Limits

`wom/gui/app.py:1772` の `_draw_capacity_chart(node, psi)` が同じ図を既に描いている
（`week_labels` / `psi[w][P]` / `cap_hard(w)` / `cap_soft(w)` の4つしか使っていない）。
**`app.py` は import しない**（§8.2 の方針）ので、N4 の系列から同じ図を描き直す。

```
P を棒          cap_hard 実線（赤）   cap_soft 点線（橙）
超過した週に赤帯（cap_hard）／橙帯（cap_soft）
```

**どのノードを既定で出すか**: 結論行を説明するノード——**超過週が最も多いノード**。
超過が1週も無ければ、能力に対する余裕が最も小さいノード。補助パネルにノードの
一覧を出し、クリックで図を切り替える（S1 のドリルダウンと同じ操作感）。

超過が0週なら帯を描かない。能力が設定されていないノードは一覧に出さない
（`app.py` は "No CapHard / CapSoft set on this node" を出しているが、
**そもそも一覧に出さないほうが強い**——S1 の `is_unallocated` と同じ規律）。

## N6. 補助パネル

**8-3b-3・M1 の並べ方をそのまま守ること。** 常に在るものを上、条件つきを下。

```
能力ノード（常に在る・クリックで図を切替）
  Bottling_Noda    超過 4週
  Brewing_Noda     超過 0週
  Materials_JP     超過 0週
実行の結果（条件つき・実行後だけ）
  未充足 0 lot
  在庫ピーク 0週
  最早着手週 2026-W28
```

`realized.issues` は**空のまま**（設計書 §2.2 のとおり S4 で配線する）。
**空のリストを見出しごと出さないこと**（K2）。

## N7. `⚑` の意味が画面ごとに違う — `ops_bar.py` に API を足す

| 画面 | `⚑` が意味すること | ラベル |
|---|---|---|
| S1 | この配分で計画する（`new_state` → `save` = `pre_plan`） | ⚑ この配分で計画する |
| S3 | 実行結果を記録する（`attach_realized` → `save` = `feasible_plan`） | ⚑ この実行結果を記録する |

`set_commit_label(text)` と `set_commit_note(text)` を足し、`frame.py` が画面を
差し替えるときに一緒に設定する。**注記の文言を `ops_bar.py` が持ち続けないこと**
——持つべきは画面側である。

`commit()` という**契約は変えない**（引数なし・Planning State を返す・失敗は
例外）。契約が保つかどうかも仮説の一部なので、**変える必要が出たら報告すること。**

## N8. Gate 0 を S3 にも効かせる

Gate 0 の9条件は「特定の画面を名指ししない汎用の不変条件」として書いてきた。
**それが本当かどうかも、2枚目の画面で初めて分かる。**

- S3 のパネルを `STATES` に足す（実行前 / 実行後の2状態）
- **条件1〜9 のうち、S3 にそのまま効いたものと、効かなかったものを報告すること**

効かない条件があっても**それ自体は失敗ではない**（S1 固有の前提が混じっていた
という発見であり、それは価値がある）。**黙って S3 だけ除外しないこと。**

---

## スコープ外（やらないこと）

- `attach_realized()` / `realized` への週次系列の格納（設計書 §2.2「履歴書には
  結論だけ」。系列は画面が snapshot から読む）
- **S2 Place**（設計書 §8.2 のとおり葉のみ・結論行なし）
- **S4 / S5**、`realized.issues` の配線
- **L1〜L3**（子ノードに「この枝の利益」を出す）— 本回の後
- 子ノードへの BAU 射影 / oil の表示桁 / 幅ゼロの文言（8-3b から継続）
- `state_header.py` の `_PROFIT_LEVEL_KEYS` に `P_bau` が無い件（S1 側の小さな
  取りこぼし。本回では触らない）

---

## 完了条件

1. S1 で ⚑ → Navigator から S3 へ入り、▶ 実行 → 結論行が出て、⚑ で
   `feasible_plan` が保存される、が通しで動く
2. 実行中に画面が固まらない（9秒間クリックを受け付ける）
3. Gate 0 に S3 の2状態が入っている
4. 既存 488 passed / 3 skipped が維持されている
5. **golden 13ケースが緑**（`planning_state=False` の経路に1行も足していないこと）

## 報告してほしいこと — **これが本回の成果物である**

**骨格の4ファイルそれぞれについて、手を入れたか／入れずに済んだかを、
変更行数と理由つきで報告すること。**

```
frame.py         入れた／入れずに済んだ   +__ -__   理由:
navigator.py     入れた／入れずに済んだ   +__ -__   理由:
ops_bar.py       入れた／入れずに済んだ   +__ -__   理由:
state_header.py  入れた／入れずに済んだ   +__ -__   理由:
```

あわせて:

- `commit()` の契約（引数なし・Planning State を返す・失敗は例外）は**そのまま
  使えたか**。使えなかったなら何が足りなかったか
- Gate 0 の条件1〜9 のうち、**S3 にそのまま効いたものと効かなかったもの**
- `run_headless()` の実測時間（この環境では 9.3 秒。大杉さんの PC では違うはず）
- **骨格の切り方が足りないと感じた箇所**——設計の話なので、実装せずに報告だけで
  よい。それが 8-3d / 8-3e の入力になる
