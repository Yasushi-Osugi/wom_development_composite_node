# smartx-2027-2029

SmartX（第 1 世代）→ SmartXNext（次世代）の世代の切り替えと、SmartXPro_CN／SmartXPro_IN の 4 製品のモデル。
計画期間は 2025-W36〜2030-W52（278 週、助走 17 週を含む）。

## 組立ラインの能力（RequestLetter_GenerationLine_UpperLayer、2026-10-07）

### 世代間で共有するライン（`AssemblyCN_g1` → `AssemblyCN_g3`）

SmartX と SmartXNext は**同じ組立ラインを使う**。混流生産はしない。SmartX の生産を止めてから
SmartXNext を始めるまでに、設備を調整する**空き期間**がある。

| 項目 | 値 | 決め方 |
|---|---|---|
| SmartX のラインの能力（`AssemblyCN_g1`） | **1,438 lot／週** | SmartX のピークの週の需要（全市場の合計）1,307（2026-W01）× 1.1 を切り上げ |
| SmartXNext のラインの能力（`AssemblyCN_g3`） | **3,713 lot／週** | SmartXNext のピークの週の需要 3,375（2030-W27）× 1.1 を切り上げ（3,712.5） |
| 切り替えの週 `s*` | **2028-W26** | 上位の層の比較で選んだ（前倒しの窓 17 週で、未割当が最小） |
| 空き期間 `g` | **4 週**（2028-W26〜2028-W29） | 仮の値 |
| SmartXNext の生産開始 | **2028-W30** | `s* + g` |

`capacity_plan.csv` の 2 つのノードの行（計画期間の全週）：

| 週（ラインの週） | `AssemblyCN_g1`（SmartX） | `AssemblyCN_g3`（SmartXNext） |
|---|---:|---:|
| 〜 2028-W25 | 1,438 | **0** |
| 2028-W26 〜 2028-W29（空き期間） | **0** | **0** |
| 2028-W30 〜 | **0** | 3,713 |

- 0 は「能力ゼロ」、空欄は「上限なし」（RequestLetter_CapacityZeroBlank）。発売前・生産終了後の週も
  0 を明示している（空欄にすると上限なしになり、Backward が何年も前から作りだめる）。
- 作り直すとき：
  `python -m tools.gen_generation_line_capacity --model-dir data/sample/smartx-2027-2029 --switch-week 2028-W26 --gap 4`
  （能力は `--factor 1.1` で需要から計算。`--cap-old`／`--cap-new` で直接指定もできる）。
- 切り替えの週の比較：`python -m tools.generation_switch_sweep --model-dir data/sample/smartx-2027-2029 --out <dir> --window 17`

### 別のライン

- SmartXPro_CN の `AssemblyCN` は、同じ鄭州の工場の中の**別のライン**。能力は前からの値のまま
  （2030-W14 以降は 0 ＝ 生産終了）。
- SmartXPro_IN の `AssemblyIN`・`SensorIN` は、インドのラインで前からの値のまま。

## 上位の層（Capacity Layer）の設定：`capacity_layer_config.csv`

| key | value | 意味 |
|---|---|---|
| `max_advance_weeks` | 17 | 前倒しの窓（市場の要求週より何週まで前に作ってよいか） |

Plugins の **Capacity Layer** を ON にしたときだけ使う（既定は OFF）。golden は OFF で作っている。
OFF のときは Backward の能力の押し戻しに前倒しの上限が無いので、ON（窓 17 週）とは結果が違う
（`docs/development/WOM_GenerationLine_UpperLayer_Report.md`）。
