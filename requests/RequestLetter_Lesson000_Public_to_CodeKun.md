# Request Letter — Lesson 000（お米が足りない）を公開する：比較モデルを作る道具と `docs/lessons/lesson000/`

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-15
- 基準：`wom-v1r5m1_cap_trial` の最新（この依頼書を入れた commit）。着手時の SHA を報告する
- 種別：道具・テスト・文書。**`wom/`・`data/sample/`・golden・保護対象のコアは変えない。commit はしない**
- テストの段：途中は `--smoke`、最後に `--smoke` と `--area rice,public`。**全テストは不要**（`wom/` を変えないため）

## 0. 背景と決定

前の依頼（`RequestLetter_RiceTeachingVariants_to_CodeKun.md`）で作った比較モデル 3 つと結果は、手元だけ（`docs/business/lesson000/`、git の対象外）にある。Owner の判断で、**Lesson 000 は公開する**。ただし：

1. **比較モデルは写しを置かない。** `data/sample/rice-japan-2027-2028` から、決まった数行だけを変えて作る道具にする。理由：`data/sample/` に置くと golden・identity・推奨プラグインのテストの対象になり、GUI のモデルの一覧にも並ぶ。写しは、基準のモデルを直したときに古いまま残る。
2. **置き場所は `docs/lessons/lesson000/`。** 台本の公開版 `Lesson000_Rice.md` は Claude 君が置いた（このフォルダに既にある。中身は変えない）。
3. 公開のファイルに書かないもの：`docs/business/` への参照、事業の名前（Owner が手元の `private/real_name_denylist.txt` に入れてある。`tests/test_no_real_names.py` が見つける）、講師用の採点の例（手元に残す）、事業・価格・レビューした人の話。

## 1. 道具 `tools/lesson000_variants.py`

```
python -m tools.lesson000_variants                     # 3 つを output/lesson000/models/ に作る
python -m tools.lesson000_variants --out <フォルダ>
python -m tools.lesson000_variants --run               # 作って、基準と 3 つを実行し、結果の表を作る
python -m tools.lesson000_variants --list              # 変える値の表を表示するだけ
```

1. **変える値は、道具の中の一つの表**（変種 → ファイル → 行の条件 → 列 → 掛ける率 1.3、または値）にする。前の依頼書 §1 の表と同じ変更：
   - `rice_harvest_plus30`：新潟の収穫（`rice_resource_capacity.csv` の `FIELD_NIIGATA` の収穫週、`rice_crop_limit.csv` の `FIELD_NIIGATA`、`capacity_plan.csv` の `Koshihikari,Tanbo_Niigata` の収穫週）15,500 → 20,150、46,500 → 60,450
   - `rice_mill_plus30`：`MILL_E` 1,300 → 1,690、`MILL_W` 1,000 → 1,300（`rice_resources.csv`、`capacity_plan.csv` の `Seihaku_E`・`Seihaku_W` の全行。`rice_resource_capacity.csv` に精米の行があれば揃える）
   - `rice_harvest_mill_plus30`：両方
   - 手元の変種を作ったときに、ほかにも揃えた所があれば、それも表に入れる（そして報告する）。
2. 基準のフォルダを丸ごと写してから、表の行だけを変える。**表の条件に当たる行が見つからない、または当たる数が想定と違うときは止める**（基準のモデルが変わったことに気づけるように）。黙って飛ばさない。
3. 各変種の `README.md` の先頭に「授業の比較モデル。基準からの変更は次のとおり」と、変えた値の表を書く（道具が作る）。note 列は「比較用：+30%」に直してよい。
4. `--run`：基準と 3 つを `tools.rice_seasonal_check` で実行し（`--plugins` 省略＝推奨の組）、生の結果は `output/lesson000/results/<名前>/` に置く。前の依頼書 §3 の「並べる表」と照合の表を、`--summary <パス>`（既定 `output/lesson000/results/summary.md`）に書く。表は道具が作る（手で書いた文は入れない）。
5. 照合（flow identity の誤り 0、資源・年産上限の超過 0、早出し 0）が一つでも合わなければ、表を書かずに止める。

## 2. 確かめること（前の結果と同じになること）

1. **手元の変種と同じか**：道具で作った 3 つと `docs/business/lesson000/<名前>/` を、ファイルごとに比べる（note 列と README は除く）。違えば止めて報告。
2. **結果が同じか**：`--run` の表の数字が、手元の `docs/business/lesson000/results/summary.md` と同じ（コシヒカリ・報告期間の当週出荷／注文残：基準 93,874／28,556、収穫 +30% と両方 121,774／656、精米 +30% 93,874／28,556。市場ごとの値、上限に当たった週の数も）。
3. 確かめた後、`--run` の `summary.md` を `docs/lessons/lesson000/results/summary.md` に置く。生の結果（1 つ約 750 KB）は公開のフォルダに入れない。

## 3. 公開のフォルダ `docs/lessons/lesson000/`

| ファイル | 作る人 | 中身 |
|---|---|---|
| `Lesson000_Rice.md` | Claude 君（済み） | 台本（講師用の節を含む）。変えない。直したい所があれば報告だけ |
| `README.md` | Code君 | 何の授業か（2〜3 行）、講師の準備の手順（`python -m tools.lesson000_variants --run` → GUI で基準を開く → 結果カードを作る）、比較モデルの変える値の表（道具の `--list` と同じ）、所要時間の目安、`results/summary.md` の説明 |
| `results/summary.md` | 道具（§2.3） | 並べた表と照合 |

- 数字には必ず範囲（品目・期間）を付ける。モデルは架空であることを一行書く。
- 台本と README で、パス・名前・数字が食い違っていないかを読み比べる。

## 4. テスト

`tests/test_lesson000_variants.py`（速いもの。計画は回さない）：
1. 一時フォルダに 3 つを作り、基準との違いが**表の行・列だけ**であること（ほかのセル・ファイルは同じ）。
2. 変えた値が基準の値 × 1.3 であること（15,500 → 20,150 など）。
3. 表の条件が基準のモデルで想定どおりの数の行に当たること（基準のモデルが変わったら、このテストが落ちて気づく）。
4. `tests/conftest.py` の対応表に `("rice", "public")` で 1 行足す。smoke には入れなくてよい（速ければ入れてもよい）。

`tools/quick_check.py` のパスの規則に、`tools/lesson000_variants.py` と `docs/lessons/` を足す（領域 `rice`・`public`）。

## 5. 受入条件

| ID | 検査 |
|---|---|
| L-1 | 道具で作った 3 つが手元の変種と同じ（§2.1） |
| L-2 | `--run` の数字が手元の結果と同じ（§2.2）。照合はすべて合格 |
| L-3 | `tests/test_lesson000_variants.py` が緑。基準の値を一時的に 1 か所変えると止まる（または落ちる）ことを一度確かめ、戻す |
| L-4 | 追加・変更したファイルに `docs/business` が無い（`git grep -n` で 0 件。依頼書は除く） |
| L-5 | `tests/test_no_real_names.py` が緑（Owner の手元の一覧も読まれる状態で） |
| L-6 | `--smoke` と `--area rice,public` が緑。件数と時間 |
| L-7 | `git status`：`data/sample/`・`wom/`・`tests/golden/` に変更が無い。`docs/business/` は触っていない |

## 6. 範囲の外

- `README.md`（リポジトリのトップ）と `docs/WOM_Start_Here.md` は触らない（Claude 君が直す）。
- `docs/business/` の中は、読むだけ（比べるため）。消さない・動かさない。
- 台本の中身は変えない。

## 7. 報告

- `docs/development/WOM_Lesson000_Public_Report.md`：着手の SHA、L-1〜L-7、道具の変える値の表、予想と違ったこと。
- 追加・変更のファイルの一覧。
- commit・push はしない。
