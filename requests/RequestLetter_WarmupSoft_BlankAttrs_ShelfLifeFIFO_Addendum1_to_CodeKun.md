# Request Letter 追補 1：書き換えたテストの名前を中身に合わせる

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-25）
- 元の依頼書：`requests/RequestLetter_WarmupSoft_BlankAttrs_ShelfLifeFIFO_to_CodeKun.md`
- 種別：テストの名前の変更だけ。コードの動きは変えない。**今の full の実行が終わってから**行う。

---

## 1. 直すこと

Part A で期待値を書き換えた `tests/test_warmup_materialize.py` のテストの名前が、中身と食い違っている。

| | 今 | 直した後（案） |
|---|---|---|
| 関数名 | `test_new_format_multi_node_unchanged_behaviour` | `test_new_format_multi_node_copies_capacity_values` |
| 中身 | 新書式の助走行に、最初の実週の `max_supply` と `cap_soft` を写す（空欄の cap_soft は空欄のまま） | 同じ（変えない） |

名前は「挙動は変えない」と読めるが、Part A で挙動を変えた（cap_soft も写す）。名前だけを見た人が「warmup は max_supply だけを写す」と誤読しないように直す（誤読を招く名前は見つけ次第直す：Start Here §6）。もっと中身の分かる名前があれば、それにしてよい。

- docstring は Part A で書き換えたもののままでよい。
- 関数名を参照している所（テストの対応表、報告書、`CLAUDE.md`）があれば、あわせて直す（`tests/conftest.py` の対応表はファイル名の単位なので、たぶん変更は無い）。

## 2. 確かめること

- `python -m tools.quick_check --area core` が緑。
- full は回し直さない（名前の変更だけで、動きは変わらないため）。full の結果は、名前を変える前の実行の値を報告書に書けばよい。

## 3. 報告と commit

- 報告書 `docs/development/WOM_WarmupSoft_BlankAttrs_ShelfLifeFIFO_Report.md` に、名前を変えたことと `--area core` の結果を 1〜2 行で書く。
- 名前の変更は、元の依頼書の**実装の commit に含める**（別の commit にしない）。commit メッセージの下書きにも 1 行足す。
- この追補は、元の依頼書と同じく `docs(request)` として、実装の commit の前に commit する（大杉さんが Windows で行う）。
