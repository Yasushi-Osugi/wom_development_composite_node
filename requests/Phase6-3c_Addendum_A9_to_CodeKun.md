# Phase 6-3c 追加指示（A9）— 原価経路の再構成を直す、uom の後始末、文書同期

**宛先**: Code君
**作成日**: 2026年9月11日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（6-3 の完了条件）
**ブランチ**: `wom-v1r4m0`
**先行**: `requests/Phase6-3_RequestLetter_to_CodeKun.md` ／ `requests/Phase6-3b_Addendum_to_CodeKun.md`（A1〜A8）

---

## 0. 先に、私（Claude君）の説明の訂正が2つある

Code君の「`tariff_rate=0.0` はコスト連鎖が切れている副作用である」という報告を受けて調べ直した結果、**前回の私の説明に2つ誤りがあった。**

### 訂正1: 「サンプルデータの不足」ではなかった

前回、`ppc_tariff_rule.csv` の `edge_id` が `ppc_edge_cost_rule.csv` と噛み合っていないことを「データの不備」と書いた。**誤りだった。**

PPC（B系統）の golden を確認したところ:

```
oil-global-2027   revenue_base   1,649,727,940,180
                  cost_base      1,070,189,765,287
                  tariff_base           53,620,617   ← 関税が計上されている
                  gross_margin_pct            0.35
```

**PPC は原価も関税も正しく拾っている。** PPC は経路を**ツリーから**組み（`walk_ancestor_chain`）、`MOM→first_DAD` という規約でエッジ ID を作る。`ppc_tariff_rule.csv` の `Refinery_Local->Tank_Local` はその規約に**合っている**。

噛み合っていないのは `cost_block.py` の側である。**同じ CSV を、2つのエンジンが違う規約で読んでいた。** データは PPC が使える形で正しく揃っている。**Phase 6-4「データ補完」は不要。撤回する。**

### 訂正2: 「PPC と同じ規約に直す」は、そのままでは soysauce を壊す

「`cost_block.py` の経路を `sc_tree_master.csv` の `parent_node` に直せばよい」と書いたが、**素朴にやると soysauce の全回帰値が動く。** 実測した。

```
Rest_JP   現行(コスト表由来・5 hops)  USD 3.1 / JPY 1,725
          parent_node 由来(3 hops)    USD 2.0 / JPY   225   ★
```

原因は **inbound 側のツリーの向き**である。soysauce の `Materials_JP`（leaf_in）の `parent_node` は `Brewing_Noda`——inbound 側では親子が**流れと逆**を向いている。素朴に親を辿ると製造原価を取りこぼし、両方を混ぜると `Brewing_Noda` の 750 JPY を**二重計上**する（こちらも実測した）。

**現行のコスト表由来の経路は間違っていない。** 足りないのは「コスト行が無い区間」だけである。

---

## A9-6: 経路の再構成を直す（**本書の主目的**）

### A9-6.1 方式 —「コスト表を主、outbound 側のツリーを補助」

```python
# 現行（維持）: コスト表の "A->B" が流れの向きを与える
pred = {}
for eid in edge_cost:
    a, b = eid.split("->")
    pred[b] = a

# 追加: outbound 側の sc_tree で、pred に無い子だけを補う
#   - side == "outbound" に限ること（inbound は親子が流れと逆を向いている）
#   - すでに pred にある子は上書きしないこと（コスト表が正典）
for r in sct_rows:
    if r.get("side") != "outbound":
        continue
    child, parent = r["node_name"], r["parent_node"]
    if parent and child not in pred:
        pred[child] = parent
```

**実測で確認済み（この方式でよいことの根拠）**:

| ケース | ツリーから補った辺 | 既存ブロックとの差 |
|---|---:|---|
| `soysauce-jpy-2027-alloc` | **0本** | **6市場すべて完全一致（1円も動かない）** |
| `oil-global-2027` | **21本**（`Tank_*→Retail_*`） | 21市場すべてが初めて原価を得る |

soysauce で補う辺が0本なのは偶然ではない。**コスト行が全区間に存在するモデルでは、この追加は何もしない。** 効くのは「経路はあるがコストが無い区間」があるモデルだけである。

補った後の oil の経路と原価（実測・`side="outbound"` 限定）:

```
Retail_Local_KANTO  ← Tank_Local ← SP_Oil_Local ← Refinery_Local    JPY  36,000
Retail_Import_*     ← Tank_Import ← SP_Oil_Import ← Import_Hub      JPY  18,000
Retail_EU_*         ← Tank_EU_Local ← … ← Refinery_EU               EUR     230
Retail_US_*         ← Tank_US_Local ← … ← Refinery_USGulf           USD     270
```

### A9-6.2 関税の照合を「経路上の探索」にする

現行は `final_edge`（leaf へ入る最後のエッジ）1本だけで関税表を引いている。

```python
trate = tariff_of_edge.get(final_edge, 0.0)     # ← 課税点が leaf 直前に固定されている
```

**課税点は国境であって、leaf の直前とは限らない。** soysauce ではたまたま `DC_*→Rest_*` が課税点だったので露見しなかった。oil の課税点は `Refinery_Local->Tank_Local` / `Import_Hub->Tank_Import` である。

**修正**: 経路上の全エッジについて関税表を引き、**ヒットが1件ならそれを採る**。

```python
hits = [tariff_of_edge[e] for e in chain_edges if e in tariff_of_edge]
if len(hits) > 1:
    raise ValueError(f"leaf {leaf!r}: multiple tariff rows on the path {…}; ambiguous taxation point")
trate = hits[0] if hits else 0.0
```

**実測（soysauce）**: 6市場すべてで**ヒットは1件**、しかも現行の `final_edge` と同じエッジである。**値は1円も動かない。**

**さらに oil 向けに1点**: `ppc_tariff_rule.csv` は PPC の `MOM→first_DAD` 規約に従い、**`supply_point` を飛ばした畳みエッジ**（`Refinery_Local->Tank_Local`）を使っている。経路をそのまま引くと oil のヒットは0件になる（実測済み）。したがって**照合キーには、経路上の実エッジに加えて「`supply_point` を1つ飛ばした畳みエッジ」も含める**こと。

```
実エッジ:   SP_Oil_Local->Tank_Local
畳みエッジ: Refinery_Local->Tank_Local        ← こちらが関税表にある
```

soysauce の経路に `supply_point` は含まれないので、この追加も**soysauce には何も起きない**。

**要実測（Code君へ）**: この照合で oil が拾う関税率が `Gasoline_Import` = 0.03、`Gasoline_EU_Import` = 0.02、その他 0.0 になるはずである。**違ったら合わせにいかず報告すること。**

### A9-6.3 到達性の検査（**黙ってゼロを返さない**）

```python
if hops == 0:
    raise ValueError(
        f"leaf {leaf!r} has no upstream edge: neither ppc_edge_cost_rule.csv nor the "
        f"outbound sc_tree links it to a parent. The cost block would be all-zero."
    )
```

`derive_cost_blocks(..., require_full_path: bool = True)` とし、`False` のときだけ通して、返却に到達できなかった leaf の一覧を載せる。**既定は止める。**

これは `region` の黙った上書き（V6.1）、価格の最後勝ち（A2）に続く**同じ家族の3件目**である。3件とも「黙ってゼロ／黙って上書き」だった。

### A9-6.4 影響範囲

`ga_market_aggregation.csv` を持つのは soysauce と oil の2ケースだけなので、**A系統への影響はこの2つに閉じる**。B系統（PPC・golden 13ケース）は `cost_block.py` を import していないので無関係である。

**それでも、着手順は「soysauce が1円も動かないことを先に確認してから」とすること。** 上の実測はエッジ・ノード費の積み上げまでで、`derive_cost_blocks()` の全体を通したものではない。

---

## A9-1: `note` 列を行ごとの実 `uom` にする

Code君の指摘どおり。A8 で絞り込みを外す以上、CLI 引数の値を全行に書くと嘘になる。**その行自身の `uom`** を書くこと。A8 が言う「なぜこの行が入っているかが CSV から読める」はそのためである。

## A9-2: `transfer_price_usd` / `mat_usd` を絞り込み後の SKU から導出する

`sku_rows[0]` と `_latest_prior(sup_rows, …)` が `uom` 絞り込みの外にある件。**位置づけは「バグ修正」ではなく「前提の明示化」**である。今日の数字が動かない理由は2つあり、性質が違う。

- `mat_usd`: `material_usd_base = mat_usd` なので `usd_eff` の中で**構造的に相殺する**（設計上つねに成立）
- `transfer_price_usd`: `tariff_rate` にしか掛からず、oil はいま全市場 0.0。**これは「今の状態」に依存した偶然である**——Code君の指摘のとおり

**A9-6.2 で oil の関税が非ゼロになった瞬間、`transfer_price_usd` は実際に効き始める。** だから A9-2 は A9-6 と同じコミットに入れる価値がある。

なお、より深い前提として **`transfer_price_usd` の導出（`sku_rows[0]["unit_cost"] / base_fx`）は「モデル全体で1 SKU」を仮定している**。soysauce は `Soy_Sauce` 1つなので正しく動いていた。oil は 8 SKU・3通貨（JP 110,000 JPY / EU 145 EUR / US 88 USD）で、`uom` で分離してもこの仮定は直らない。**A9-2 は uom 単位までの改善であり、SKU 跨ぎの移転価格は未解決**である旨を docstring に残すこと。

## A9-3: oil の回帰値は「構造」を固定し、「利益」は A9-6 の後に取り直す

A6/A8 で固定した `profit = 20,885,805,337.0` / `hierarchy_gap = 558,359,363.0` は、**原価ゼロのモデルの上の数字である。破棄する。**

- **構造**（市場数15 / ノード数10 / 点数1,050）は原価に依存しない（`build_hierarchy` は `sc_tree` と通貨だけを見る）。**そのまま固定してよい**
- **利益・誤差**は A9-6 の実装後に**測り直してから**固定する。本書には期待値を書かない——**Code君が測った値を報告し、それを次の回帰値とする**

`uom="KL100KBBL"` 側は、`sc.material_usd`（kL スケールの量）をタンカーロットに適用することになるため、**利益・感度分析は意味を持たない**。構造チェック（6市場・3ノード）のみとし、profit は assert しない。

## A9-4: 仕様書 v0r6 §2.6 に2点追加

1. **シナリオ軸も同じ lot 単位で表現されていること。** `material_usd` は「1 lot あたりの原料 USD」であり、市場の lot 単位に縛られる。単位の違う市場群に同じシナリオ軸を当てても意味がない
2. **原価ブロックの導出は、leaf から上流へ経路が到達できることを前提とする。** 経路は `ppc_edge_cost_rule.csv` の流れを主とし、outbound 側の `sc_tree_master.csv` で補う。到達できない場合は拒否する（A9-6.3）
3. **既知の限界**: `transfer_price_usd` の導出は単一 SKU モデルを前提とする（§5 Step 2 に注記）

## A9-5: 文書の同期

- 設計書 §7.3 のテスト計画（16〜21の6件）を、実装した10件（V7.1〜V7.8 + A7.1/A7.2）に合わせる
- 設計書 §8 のチェックボックスを実態に合わせる
- **README の `三角図13枚 × 231点 = 3,003点` を `10ノード・1,050点` に直す**（rev.7 で 21市場→15市場になったので二重に古い）

---

## テスト

`tests/test_allocation_hierarchical.py` に追記。

1. `test_path_supplement_does_not_change_soysauce` — **最重要**。A9-6 適用後も soysauce の6市場・3市場ブロックが**全フィールド完全一致**すること（`==` で厳密比較）
2. `test_tariff_found_on_path_not_only_final_edge` — soysauce で従来と同じ関税率（0.125 / 0.08 / 0.0）が引けること
3. `test_unreachable_leaf_raises` — 経路が無い leaf で `ValueError`。`require_full_path=False` なら通り、`incomplete_paths` に載ること
4. `test_oil_structure_only` — 15市場・10ノード・1,050点。**profit は assert しない**

既存の Phase 4/5/6 の全回帰値が不変であること（付録A 5件・117円/119円・`103,891,296.0` ほか）。

---

## 成功基準

- [ ] soysauce の原価ブロックが**1円も動かない**（A9-6 の全体を通して）
- [ ] oil の21市場が原価を得る。関税が `Import`=0.03 / `EU_Import`=0.02 で拾える（**要実測・報告**）
- [ ] 経路が到達しない leaf は既定で `ValueError`
- [ ] oil の利益・誤差の回帰値を**測り直して報告**（本書は値を指定しない）
- [ ] README / 設計書 §7.3・§8 が実態と一致
- [ ] 既存テスト全PASS（新規4件を加えた件数を報告すること）

---

## 実装者への申し送り

**1. Code君の報告がなければ、原価ゼロの数字を回帰値として固定したままだった。**
`tariff_rate=0.0` を「関税ゼロとモデル化されている」と読んで先に進むのが自然なところを、「なぜゼロなのか」を追ってくれたのが効いた。**A6/A8 の回帰値を破棄するのは、その報告の直接の成果である。**

**2. soysauce が動いたら、そこで止めて報告すること。**
Phase 4/5/6 の全分解値と公開済み note 記事の数字が soysauce に乗っている。**「動いたけれど小さいから良い」は無い。** 1円でも動いたら先に相談すること。

**3. 本書は oil の利益の期待値を書いていない。**
A9-6 の実装によって決まる値だからである。**測って報告してもらい、それを正典にする。** 逆に、こちらが先に値を書いて Code君がそれに合わせにいく、という順序を作らないためでもある。

**4. 3件目の「黙って壊れる」である。**
`region` の上書き、価格の最後勝ち、経路の未到達——いずれも例外を出さずに静かに間違った値を返していた。**A系統の導出まわりは、この形の欠陥をまだ抱えている可能性がある。** 気づいたら、修正の可否と別に、まず報告してほしい。
