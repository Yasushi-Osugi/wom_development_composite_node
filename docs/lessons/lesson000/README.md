# Lesson 000「お米が足りない」

年に一度しか取れないお米が、需要より約 2 割少ない。いつ、どの市場に、どれだけ届けるか、足りない分にどう手を打つかを、WOM の週ごとの計画と、前提を一つずつ変えた比較で考える 90 分の授業。台本は同じフォルダの `Lesson000_Rice.md`。

使うモデルは公開のサンプル `data/sample/rice-japan-2027-2028`。**架空のケース**で、実在の会社・団体・取引とは関係がない。

## ファイル

| ファイル | 中身 |
|---|---|
| `Lesson000_Rice.md` | 授業の台本（流れ、AI 指導役への指示、結果カード、事前・事後のケース、評価の基準、講師用の節） |
| `README.md` | この文書。講師の準備の手順と、比較モデルの作り方 |
| `results/summary.md` | 基準と比較モデル 3 つの結果を並べた表と照合（`tools/lesson000_variants.py --run` が作ったもの） |

## 講師の準備（授業の前日まで）

1. **比較モデルを作って実行する**（約 6〜7 分。4 つを順に計画する）：
   ```
   python -m tools.lesson000_variants --run
   ```
   - 基準から比較モデル 3 つを `output/lesson000/models/` に作り、基準と 3 つを `tools.rice_seasonal_check` で計画・照合する（推奨のプラグインの組）。
   - 生の結果は `output/lesson000/results/<名前>/`、並べた表は `output/lesson000/results/summary.md`。
   - 照合（flow identity の誤り・資源と年産上限の超過・早出し）が一つでも合わなければ、表を書かずに止まる。
   - 表を `results/summary.md`（このフォルダ）と比べ、数字が同じことを確かめる。違えば、基準のモデルか WOM が変わっている。
2. **GUI で基準を開く**：`python -m main` → Load Model Folder → `data/sample/rice-japan-2027-2028`（推奨のプラグインが自動で入る）→ Run Planning Engine。見せる画面は台本 §2。
3. **結果カードを用意する**：台本 §5 のカード 1〜4 を、段階ごとに貼れる形にしておく。カード 3 の比較モデルの数字は、手順 1 の表から取る。比較モデルを GUI で見せる場合は、`output/lesson000/models/<名前>` を Load Model Folder で開く。
4. AI チャットに台本 §4 の指示と、カード 1 だけを貼る。

比較モデルを作るだけなら `python -m tools.lesson000_variants`（実行しない）。置き場所を変えるなら `--out <フォルダ>`。変える値を見るだけなら `--list`。

## 比較モデルの変える値

基準のフォルダを丸ごと写してから、下の行だけを変える（`tools/lesson000_variants.py` の表 `CHANGES`。`--list` と同じ）。上位の層とエンジンの両方の上限を**揃えて**変える（片方だけ変えても効かない）。ゆめぴりか（北海道）、需要、休業、価格、プラグインの組は変えない。変えた行の note 列は「比較用：+30%」になる。

**`rice_harvest_plus30`：新潟の収穫 +30%**

| ファイル | 変える行 | 列 | 前 → 後 | 行数 |
|---|---|---|---|---:|
| `rice_resource_capacity.csv` | FIELD_NIIGATA の収穫週（各年 W41〜W43） | `capacity` | 15,500 → 20,150（×1.3） | 9 |
| `rice_crop_limit.csv` | FIELD_NIIGATA の年産上限（2026・2027・2028） | `limit` | 46,500 → 60,450（×1.3） | 3 |
| `capacity_plan.csv` | Koshihikari,Tanbo_Niigata の収穫週 | `max_supply` | 15,500 → 20,150（×1.3） | 9 |

**`rice_mill_plus30`：精米センター +30%（二品目で共用）**

| ファイル | 変える行 | 列 | 前 → 後 | 行数 |
|---|---|---|---|---:|
| `rice_resources.csv` | MILL_E（精米センター東、二品目で共用） | `default_capacity` | 1,300 → 1,690（×1.3） | 1 |
| `rice_resources.csv` | MILL_W（精米センター西、二品目で共用） | `default_capacity` | 1,000 → 1,300（×1.3） | 1 |
| `capacity_plan.csv` | Seihaku_E の全行（両品目） | `max_supply` | 1,300 → 1,690（×1.3） | 314 |
| `capacity_plan.csv` | Seihaku_W の全行（両品目） | `max_supply` | 1,000 → 1,300（×1.3） | 314 |

`rice_resource_capacity.csv` には精米の週ごとの行が無い（基準のモデル）。行が現れたら道具が止まる。

**`rice_harvest_mill_plus30`：両方**（上の 2 つの表の 7 か所すべて）

基準のモデルが変わって、表の条件に当たる行が無い、または数が違うときは、道具は黙って飛ばさずに止まる。そのときは `CHANGES` を見直す。`tests/test_lesson000_variants.py` も落ちる。

## `results/summary.md`

`--run` が作った表をそのまま置いた（2026-10-16 の実行）。主な数字（範囲：コシヒカリ、報告の期間 2027〜2028 年、要求 122,430 lot）：

| | 基準 | 収穫 +30% | 精米 +30% | 両方 |
|---|---:|---:|---:|---:|
| 当週に届いた／届かなかった（lot） | 93,874／28,556 | 121,774／656 | 93,874／28,556 | 121,774／656 |

市場ごとの値、当週の出荷が 0 の週、精米センターが上限に当たった週の数、年産の使い切り、玄米倉庫のピーク、照合の表は `results/summary.md` にある。生の結果（ID ごとの記録など、1 つ約 750 KB）は公開しない。手順 1 で手元に作れる。
