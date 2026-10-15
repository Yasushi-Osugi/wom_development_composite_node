# WOM Lesson000 Public Report — 比較モデルを作る道具と `docs/lessons/lesson000/`

- 依頼書：`requests/RequestLetter_Lesson000_Public_to_CodeKun.md`（2026-10-15）
- 着手時の SHA：`887603437f3364ab4070706d2dea0c9bf1c125b5`（branch `wom-v1r5m1_cap_trial`）
- 種別：道具・テスト・文書。`wom/`・`data/sample/`・golden・保護対象のコア・台本 `Lesson000_Rice.md` は変えていない。
- テストの段：途中は `--smoke`、最後に `--smoke` と `--area rice,public`。全テストは回していない（依頼書のとおり）。

## 道具 `tools/lesson000_variants.py`

```
python -m tools.lesson000_variants                     # 3 つを output/lesson000/models/ に作る
python -m tools.lesson000_variants --out <フォルダ>
python -m tools.lesson000_variants --run               # 作って、基準と 3 つを実行し、表を作る
python -m tools.lesson000_variants --list              # 変える値の表を表示するだけ
```

- 変える値は道具の中の一つの表 `CHANGES`（グループ・ファイル・行の条件・列と基準の値・想定の行数・note の列・説明）。変種は `VARIANTS`（`rice_harvest_plus30`＝harvest、`rice_mill_plus30`＝mill、`rice_harvest_mill_plus30`＝両方）。
- 基準のフォルダを丸ごと写し（`__pycache__`・`_ppc` を除く）、表の行だけを ×1.3（`Fraction(13, 10)`。整数にならなければ止まる）。値の書き方（`15500.0` か `15500` か）は基準に合わせる。変えた行の note 列（`capacity_plan.csv` は `source` 列）を「比較用：+30%」に直す。
- 行の条件には**基準の値**も入れてある（例：`FIELD_NIIGATA` かつ `capacity` が 15,500）。当たる行の数が想定と違えば、黙って飛ばさずに止まる（`SystemExit`、どのファイル・どの条件・何行・想定何行かを表示）。
- 各変種の `README.md` の先頭に「授業の比較モデル。基準からの変更は次のとおり」と変えた値の表を書く。
- `--run`：基準と 3 つを `python -m tools.rice_seasonal_check`（`--plugins` 省略＝推奨の組）で順に実行。生の結果は `output/lesson000/results/<名前>/`。照合（flow identity の誤り・資源と年産上限の超過・早出し・経路の照合・上位の層と実出荷の不一致・物量の保存）が一つでも合わなければ、表を書かずに止まる。表は `--summary`（既定 `output/lesson000/results/summary.md`）に道具が書く（手で書いた文は入れない）。

### 変える値の表（`--list` と同じ）

| 変種 | ファイル | 変える行 | 列 | 前 → 後 | 行数 |
|---|---|---|---|---|---:|
| harvest | `rice_resource_capacity.csv` | FIELD_NIIGATA の収穫週（各年 W41〜W43） | `capacity` | 15,500 → 20,150 | 9 |
| harvest | `rice_crop_limit.csv` | FIELD_NIIGATA の年産上限（2026・2027・2028） | `limit` | 46,500 → 60,450 | 3 |
| harvest | `capacity_plan.csv` | Koshihikari,Tanbo_Niigata の収穫週 | `max_supply` | 15,500 → 20,150 | 9 |
| mill | `rice_resources.csv` | MILL_E | `default_capacity` | 1,300 → 1,690 | 1 |
| mill | `rice_resources.csv` | MILL_W | `default_capacity` | 1,000 → 1,300 | 1 |
| mill | `capacity_plan.csv` | Seihaku_E の全行（両品目） | `max_supply` | 1,300 → 1,690 | 314 |
| mill | `capacity_plan.csv` | Seihaku_W の全行（両品目） | `max_supply` | 1,000 → 1,300 | 314 |
| mill | `rice_resource_capacity.csv` | MILL_E・MILL_W の週ごとの行 | — | 基準には無い（0 行を確かめる。現れたら止まる） | 0 |

手元の変種を作ったときに、これ以外に揃えた所は**無い**（前の依頼の比較モデルも、この 7 か所と note 列だけを変えた）。

## 受入

| ID | 検査 | 結果 |
|---|---|---|
| L-1 | 道具の 3 つが手元の変種と同じ | **合**：前の依頼で作った手元の 3 つ（git の対象外のフォルダ）と `diff -rq`（README を除く）で、3 つとも全ファイルがバイトまで同じ。note 列も同じ文言だったので、除かずに一致した |
| L-2 | `--run` の数字が手元の結果と同じ。照合はすべて合格 | **合**：照合は 4 つとも 0・合格。コシヒカリ・報告期間の当週出荷／注文残：基準 93,874／28,556、収穫 +30% 121,774／656、精米 +30% 93,874／28,556、両方 121,774／656。市場ごと（例：収穫 +30% は関東 17・東北 369・関西 134・九州 136）、当週出荷 0 の週（精米 +30% の 2028 年は W34〜W45）、精米センター東・西が上限に当たった週（17・25・7・11／11・14・4・6）、年産、玄米倉庫のピークも、前の結果とすべて同じ。実行時間は 105・98・79・95 秒 |
| L-3 | テストが緑。基準を 1 か所変えると止まる | **合**：`tests/test_lesson000_variants.py` 8 passed（1.2 秒）。一度だけ実物の `data/sample/rice-japan-2027-2028/rice_resources.csv` の `MILL_W` を 1,000→1,100 に変えて道具を実行し、「`rice_resources.csv: condition {'resource_id': 'MILL_W'} with default_capacity=1000 matched 0 rows, expected 1`」で止まる（exit 1）ことを確かめ、元のバイト列に戻した（sha256 一致、`git status` に変更なし）。同じ確かめを一時フォルダの写しで行うテスト（`test_a_changed_base_model_stops_the_tool`）も入れた |
| L-4 | 追加・変更したファイルに事業の資料のフォルダへの参照が無い | **合**：追加・変更した 7 ファイル（この報告書を含め、依頼書を除く）を検索して 0 件。追跡しているファイル全体の `git grep` で当たるのは、前からある `.gitignore` の 1 行（そのフォルダを対象外にする行）だけ |
| L-5 | `tests/test_no_real_names.py` が緑（手元の一覧も読まれる状態で） | **合**：`private/real_name_denylist.txt` がある状態で、smoke と `public` の中で緑 |
| L-6 | `--smoke` と `--area rice,public` | **合**：smoke **505 passed、61 秒**（前の 497 件＋新しいテスト 8 件。smoke に入れた）。`rice,public` **127 passed、89 秒** |
| L-7 | `data/sample/`・`wom/`・`tests/golden/` に変更なし | **合**：`git status` は下の一覧のファイルだけ。事業の資料のフォルダは読んだだけ（比べるため） |

## テスト `tests/test_lesson000_variants.py`（8 件、計画は回さない）

1. 3 つそれぞれ（パラメータ）：基準と比べて、違うのは `CHANGES` のファイルだけ（README を除く）。そのファイルの中でも、違うセルは条件に当たった行の、変える列と note 列だけ。
2. 3 つそれぞれ：変えた値が基準の値 × 1.3 で、note 列が「比較用：+30%」、行数が想定どおり。
3. `CHANGES` の条件が、基準のモデルで想定どおりの数の行に当たる（基準のモデルが変われば落ちる）。
4. 写しの基準で `rice_crop_limit.csv` の 1 行を変えると、道具が `matched 2 rows, expected 3` で止まる。

`tests/conftest.py` の対応表に `("rice", "public")` で 1 行足し、smoke にも入れた（1.2 秒）。`tools/quick_check.py` の `PATH_RULES` に `tools/lesson000_variants.py` と `docs/lessons/*`（領域 `rice`・`public`）を足し、`tests/README.md` の表にも同じ行を足した。

## 公開のフォルダ `docs/lessons/lesson000/`

| ファイル | 中身 |
|---|---|
| `Lesson000_Rice.md` | 台本（変えていない） |
| `README.md`（新規） | 何の授業か、架空のモデルであること、講師の準備の手順（`--run` → GUI で基準を開く → 結果カード → AI に指示とカード 1）、変える値の表（`--list` と同じ）、所要時間の目安（`--run` 約 6〜7 分）、`results/summary.md` の説明と主な数字（範囲付き） |
| `results/summary.md`（新規） | `--run` が作った表をそのまま置いた（照合、並べる表、変える値）。生の結果は置いていない |

### 台本と README の読み比べ（台本は変えていない。気づいた点だけ）

- パス・変種の名前（`rice_harvest_plus30`・`rice_mill_plus30`・`rice_harvest_mill_plus30`）・数字は一致した。カード 3 の表（届いた／届かなかった、市場ごと、当週 0 の週、精米センター東の上限の週）は `results/summary.md` と同じ。
- カード 3 の講師用の「656 の内訳」も、収穫 +30% の実行結果から数え直して一致した（2027-W01〜W45：要求 51,795・未充足 0、2027-W46〜2028-W45：61,215・335、2028-W46〜W52：9,420・321）。
- 台本のカード 3 は「2026-10-15 実行」、公開の `results/summary.md` は 2026-10-16 の実行（道具で同じ数字を再現したもの）。日付だけの違いで、直す必要は無いと思うが、揃えるなら台本の側。
- 台本 §8 の末尾「比較モデルごとに『変えた値・変えなかった値・実行の結果・基準との差』を 1 枚にまとめる」の 1 枚ずつは、公開のフォルダには無い（`results/summary.md` は並べた表と変える値だけ。依頼書が「手で書いた文は入れない」としているため）。講師が手元で作る、と読める書き方なら今のままでよい。
- 台本 §6 は講師用だが、公開すると受講者も事前に読める（Claude 君の指摘のとおり）。判断は Owner。

## 予想と違ったこと

- 道具の 3 つが、note 列まで含めて手元の変種とバイトまで同じになった（依頼書は note 列と README を除いて比べる想定だった）。前の依頼で同じ文言を使っていたため。
- `rice_resource_capacity.csv` に精米の行は無かった。「あれば揃える」は、表に「0 行であること」として入れた（基準に精米の週ごとの行が加わると止まる）。

## 追加・変更のファイル

追加：
- `tools/lesson000_variants.py`
- `tests/test_lesson000_variants.py`
- `docs/lessons/lesson000/README.md`
- `docs/lessons/lesson000/results/summary.md`
- `docs/development/WOM_Lesson000_Public_Report.md`（この報告書）

変更：
- `tests/conftest.py`（対応表に 1 行、smoke に 1 行）
- `tools/quick_check.py`（`PATH_RULES` に 2 行）
- `tests/README.md`（パスと領域の表に 1 行）

git の対象外：`output/lesson000/`（作ったモデルと生の結果）。
