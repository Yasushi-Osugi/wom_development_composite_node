# Phase 6-3b 追加指示（Addendum）— lot 単位の粒度束縛と `oil-global-2027` の接続

**宛先**: Code君
**作成日**: 2026年9月11日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（6-3 の完了条件）
**ブランチ**: `wom-v1r4m0`
**本体**: `requests/Phase6-3_RequestLetter_to_CodeKun.md`（V2 / V6 を本書で上書きする）
**正典**: `docs/design/ask_global_allocation_spec.md` v0r5 ／ `requests/Phase6_DesignMD_NMarketHierarchy.md` rev.7

---

## 0. まず、報告への回答

**Code君の判断は正しい。`aggregate_block()` のチェックを緩めなかったのは正解である。** これはコードのバグではなく、`oil-global-2027` が意図的に混在単位で作られていることによる。数字が証拠になっている。

```
Retail_Local_KANTO      Gasoline_Local          JPY         170,000
Retail_Local_H_KANTO    Gasoline_Local_Hormuz   JPY   2,700,000,000
                                                比 = 15,882
```

CLAUDE.md L528 が「1 lot = 100,000 bbl 原油換算（**≈15,900 kL**）」と書いている。**比 15,882 はこの単位差そのものである。**

**ただし、問題は単位変換で済む話ではない。** A系統は「1つの能力プールを、複数市場が lot 単位で奪い合う」モデルである。lot の物理的意味が市場ごとに違えば、この前提自体が成立しない。しかも Hormuz/RedSea は別の製油所（`Refinery_Local_H` / `_R`）を持ち、時間的にも排他（Hormuz は W01-W18、RedSea は W15 以降）である。**そもそも Local と同じ配分問題に属していない。**

**したがって除外は「諦め」ではなく、正しいモデリングである**（大杉さん判断、2026-09-11）。選択肢2（単位変換）は採らない——CLAUDE.md が意図的設計と明記しており、B系統の PSI シミュレーションと note 記事第5回がこの数字に依存している。選択肢3（グルーピング原則の変更）も採らない——原則は「能力の取り合いが強い市場を同じ枝に置く」という理屈から出ており、単位の都合で曲げると §5.4 の趣旨が崩れる。

**除外はハードコードの SKU 名リストでは行わない。** 単位はデータに書かせる（A3〜A5）。

---

## A1: `aggregate_block()` の `price_local` 制約を外す（**私の仕様の誤り**）

本体 Request Letter V2 に

```
- price_local / ccy : 子で同一であること（違えば ValueError・C10）
```

と書いたのは**誤りだった**。soysauce では FR/BE/NL がたまたま同価（6,156）、US_W/US_E も同価（6,000）なので気づかなかったが、**グループ内で販売価格が違うのは異常ではなく普通である**（oil の KANTO 170,000 / KANSAI 168,000 / CHUBU 172,000）。

**修正**: `price_local` は原価と同じく**需要加重平均**にする。同一を要求するのは `ccy` と `material_usd_base` だけ。

```python
def aggregate_block(children: Sequence[CostBlock]) -> CostBlock:
    tot = sum(c.demand_qty for c in children)
    w = [c.demand_qty / tot for c in children]

    ccys = {c.ccy for c in children}
    if len(ccys) != 1:                       # 通貨混在は無意味（C10・維持）
        raise ValueError(f"aggregate_block(): mixed currency {sorted(ccys)}")
    mats = {c.material_usd_base for c in children}
    if len(mats) != 1:
        raise ValueError(f"aggregate_block(): mixed material_usd_base {sorted(mats)}")
    for c in children:                       # cliff 混在は非対応（維持）
        if c.tariff_rate_preferential is not None or c.preferential_threshold_lot is not None:
            raise ValueError("aggregate_block(): cliff is not supported in a group")

    return CostBlock(
        usd=sum(x*c.usd for x, c in zip(w, children)),
        eur=sum(x*c.eur for x, c in zip(w, children)),
        jpy=sum(x*c.jpy for x, c in zip(w, children)),
        tariff_rate=sum(x*c.tariff_rate for x, c in zip(w, children)),
        price_local=sum(x*c.price_local for x, c in zip(w, children)),   # ← 平均にする
        ccy=children[0].ccy,
        demand_qty=tot,
        material_usd_base=children[0].material_usd_base,
    )
```

**soysauce の回帰値は1円も変わらない**（グループ内が同価なので加重平均も同値）。Claude君が実測で確認済み——この修正版で集約した3グループが、`derive_cost_blocks()` の3市場ブロックと**全フィールド一致**する。

---

## A2: `cost_block.py` の価格解決も同じ落とし穴

```python
# wom/allocation/cost_block.py:133 付近
for r in regs:
    ...
    price, ccy = pr, pc           # 市場内で共通
```

**「市場内で共通」と書いてあるが、共通である保証はどこにもない。** 実際には**ループの最後の region の価格**が採られる。soysauce では同価なので露見しないが、`ga_market_aggregation.csv` の1グループに価格の違う region が並べば、**黙って最後の1件が採用される**。V6.1 で直した `region` 重複と**同じ家族のバグ**である。

**修正**: 価格も `internal_ratio` による加重平均にし、通貨は同一を検査して混在なら `ValueError`。

```python
price = sum(w_r * price_r for ...)      # internal_ratio による加重平均
if len({ccy_r for ...}) != 1:
    raise ValueError(f"market_group {market!r} mixes currencies {...}")
```

**soysauce・oil とも値は変わらない**（soysauce は同価、oil は1グループ1 region）。C8 の対象。

---

## A3: `sku_master.csv` の `uom` が実態と食い違っている（**これが根本**）

`oil-global-2027` の `sku_master.csv` は**全 SKU の `uom` が `KL`** になっている。しかし Hormuz/RedSea の `sku_name` は

```
Gasoline (Hormuz Normal Route, crude-equiv lot=100kbbl)
Gasoline (RedSea Alt Route,   crude-equiv lot=100kbbl)
```

**単位が製品名の文字列の中にしか書かれておらず、`uom` 列は嘘をついている。**

**修正**: 該当6行の `uom` を `KL` → **`KL100KBBL`** にする（`100,000 bbl ≈ 15,900 kL` を表す。名前は他案でもよいが、`KL` と区別がつくこと）。

**この修正は計算を1円も動かさない。** `uom` はコード上どこでも計算に使われていないことを確認済みである。

```
wom/data/schema.py:68            UOM = "uom"            ← 列名の定義のみ
tools/gen_apparel_global_model.py:348  ヘッダ行に書くだけ
tools/gen_apparel_model.py:233         同上
```

**他のケースはすべて単一 `uom` で正しい**（`CS` / `EA` / `TIN15KG` / `lot` / `KL`）。`oil-global-2027` だけが、単一値を名乗りながら実態が2種類だった。

---

## A4: `derive_cost_blocks()` に `uom` 絞り込みを足す

```python
def derive_cost_blocks(model_dir: str, base_week: str = BASE_WEEK,
                       base_fx: float = BASE_FX,
                       level: str = "market",
                       uom: Optional[str] = None) -> Tuple[Dict[str, CostBlock], float]:
    """uom=None（既定）: モデル内の uom が1種類ならそのまま。
                        2種類以上なら ValueError（どれを使うか指示させる）。
       uom="KL"        : その uom の SKU に属する市場だけを返す。
    """
```

**エラーメッセージには、見つかった `uom` の一覧と、絞り込みの書き方を必ず入れること。**

```
ValueError: model has markets in 2 different lot units ['KL', 'KL100KBBL'];
  an allocation problem must use a single unit (spec v0r5 §2.4).
  Pass uom="KL" (15 markets) or uom="KL100KBBL" (6 markets).
```

**soysauce は `uom` が `CS` の1種類なので、既定のまま挙動が変わってはいけない（C8）。**

`leaf_out` → `sku_id` の対応は `sc_tree_master.csv` の `product_name` から引ける。`sku_id` → `uom` は `sku_master.csv` から引ける。

---

## A5: 生成器を `uom` 駆動にする

`tools/gen_oil_ga_aggregation.py` を次のように直す。

- `--uom KL`（既定）で、その単位の市場だけを書く。**SKU 名のハードコードは作らない**
- `note` 列に `uom=<値>` を記録する（なぜこの行が入っているかが CSV 自体から読める）
- 除外した行数と理由を標準出力に出す（`6 rows excluded: uom=KL100KBBL`）

生成後の `data/sample/oil-global-2027/ga_market_aggregation.csv` は **15行**になる。

---

## A6: V6.3 の完走基準を差し替える

本体 Request Letter の「21市場・13ノード・1,743点」を、**15市場・10ノード・1,050点**に置き換える。

**Claude君が Code君の実装（`hierarchical_simplex.py`）に A1 の修正だけを当てて実測した結果**:

```
市場数 15   transfer_price = $733.33

  ALL                    子3   市場15          231点
    JPY                  子2   市場5            21点
      SP_Oil_Local       子3   市場3           231点
      SP_Oil_Import      子2   市場2            21点
    EUR                  子2   市場5            21点
      SP_Oil_EU_Local    子3   市場3           231点
      SP_Oil_EU_Import   子2   市場2            21点
    USD                  子2   市場5            21点
      SP_Oil_US_Local    子3   市場3           231点
      SP_Oil_US_Import   子2   市場2            21点
                                     ──────────────
                              10ノード      1,050点
```

**木の形は本体 Letter の予測どおりである**（地域＝通貨圏3 → 供給ライン6 → 市場15）。第一原則（Mother Plant）が供給ラインを、第二原則（通貨圏）がその上をまとめている。第三原則は不要になった（JP の供給ラインが Hormuz/RedSea を除いて2本になるため）。

誤差の実測（`fx=150 / mat=6.0`）:

| `cap_wk` | `P_hier`（1,050点） | `P_opt` | `P_opt − P_hier` | 比率 | 限界市場 |
|---:|---:|---:|---:|---:|---|
| 400 | 12,025,728,000.0 | 12,087,579,600.0 | 61,851,600.0 | 0.51% | `Retail_EU_DE` |
| 800 | 20,885,805,337.0 | 21,444,164,700.0 | 558,359,363.0 | 2.60% | `Retail_Local_KANTO` |
| 1500 | 31,911,826,137.0 | 32,836,576,700.0 | 924,750,563.0 | 2.82% | `Retail_US_TX` |

**平坦全数は N=15 で `C(34,14)` = 1,391,975,640点（約13.9億点）であり、原理的に走らない。** したがって `hierarchy_gap()` の `P_flat` は `None` を返す（`max_flat_points` 超過）。これは設計どおりの挙動である。

**削減比 1,325,691 倍。** 21市場でなくとも、6-3 の主張——「平坦格子が原理的に走らない規模を階層化が扱える」——は完全に成立する。

---

## A7: テスト追加（2件）

`tests/test_allocation_hierarchical.py` に追記。

### A7.1 `test_aggregate_block_averages_price`

価格の違う子を渡すと、**例外にならず需要加重平均が返る**こと。

```python
# demand 3:1、price 100:200 -> 平均 125
assert agg.price_local == pytest.approx(125.0, abs=1e-9)
# 通貨が違えば ValueError（こちらは維持）
with pytest.raises(ValueError, match="mixed currency"):
    aggregate_block([jpy_block, usd_block])
```

### A7.2 `test_oil_uom_split_and_hierarchy`

```python
# uom を指定しないと、2種類あることを理由に落ちる
with pytest.raises(ValueError, match="KL100KBBL"):
    derive_cost_blocks(OIL_DIR)

blocks, tp = derive_cost_blocks(OIL_DIR, uom="KL")
assert len(blocks) == 15
tree = build_hierarchy(blocks, OIL_DIR)
r = scan_hierarchical(blocks, tree, tp, Scenario(fx_usd=150.0, material_usd=6.0), cap_wk=800.0)
assert r["nodes"] == 10
assert r["points"] == 1_050
assert r["profit"] == pytest.approx(20_885_805_337.0, abs=1.0)

g = hierarchy_gap(blocks, tree, tp, sc, cap_wk=800.0)
assert g["P_flat"] is None                    # 13.9億点なので走らせない
assert g["hierarchy_gap"] == pytest.approx(558_359_363.0, abs=1.0)
```

**`P_hier` の回帰値は A1 修正後のものである。** A1 を入れないと再現しない。

---

## 成功基準（6-3 全体・更新）

- [x] 6-3a の8件（`b41581a` 時点で全PASS）
- [ ] `aggregate_block()` が価格を平均し、通貨混在のみ拒否する（A1）
- [ ] `cost_block.py` の価格解決が加重平均になり、通貨混在を拒否する（A2）
- [ ] `oil-global-2027` の `sku_master.csv` の `uom` が実態を表す（A3）
- [ ] `derive_cost_blocks(uom=...)` が単位を絞り、混在を拒否する（A4）
- [ ] 生成器が `uom` 駆動になり、CSV が15行になる（A5）
- [ ] `oil-global-2027` が **10ノード・1,050点**で完走する（A6）
- [ ] soysauce の全回帰値・Phase 4/5/6 の全分解値・golden 13ケースが不変
- [ ] **398件全PASS**（396 + 新規2）

---

## 実装者への申し送り

**1. A1 は Claude君の仕様ミスであって、Code君の実装ミスではない。**
「グループ内の価格は同一」という制約を Claude君が書いた。soysauce でたまたま成立していたので気づかなかった。**実装は指示どおりだったので、直すのは指示のほうである。**

**2. `uom` を直すのは「データを合わせにいく」のとは違う。**
A3 は数値を都合よく変える作業ではない。**`uom` 列がいま事実と違うことを書いている**ので、事実に直すだけである。`uom` は計算にまったく使われていないので、金額は1円も動かない。動いたら報告すること。

**3. ハードコードの SKU 名リストを作らないこと（A5）。**
`Gasoline_Local_Hormuz` を名指しで除外するコードを書くと、次のモデルで同じ問題が起きたときに誰も気づけない。**単位はデータに書かせ、コードは単位で絞る。**

**4. 数値が合わなかったら、合わせにいかず報告すること。**
A6 の実測値は Code君の `hierarchical_simplex.py` に A1 の修正だけを当てて Claude君が測ったものである。A2/A4 の実装次第で細部が動く可能性はあるが、**木の形（10ノード・1,050点）は動かないはず**である。ここが違ったら先に相談すること。
