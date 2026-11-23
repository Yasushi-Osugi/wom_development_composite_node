---
handoff:
  case_id: STRATEGY-CONVERT-002
  task_id: promo-convert-slice2-capacity-short
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  start_sha: b251848
  request: requests/RequestLetter_Promo_Convert_Slice2_CapacityShort_to_CodeKun.md（v0.1）
  base_model: data/sample/cosmetics-sg-th-2027-2029（能力だけを C3a に変えた写し）
  overflow_policy: proportional_week（既定）
  acceptance: "S1〜S6（§1）"
  status: "S1〜S6 合う。MID・HIGH では、増えた対象の納品と同じ量だけ、2029 年のクリームの未充足（⑤）が増えた"
  open_items: []
  stop_reasons: []
  next: owner
---

# 報告：経営施策の変換 — 2 本目：工場の能力が足りない条件（化粧品 C3a）で、同じ追加販促を比べた

- 依頼書：`requests/RequestLetter_Promo_Convert_Slice2_CapacityShort_to_CodeKun.md`（v0.1）
- 着手時の SHA：`b251848`
- 実行：Windows 11、Python 3.12.3（`C:\Users\ohsug\anaconda3\python.exe`）
- 出力：`output/strategy_slice2/`（git の対象外）。付録：`docs/development/WOM_Promo_Convert_Slice2_CapacityShort_appendix/`

この報告は事実だけを書きます。どの案が良いかは書きません。金額は試算です。保有費は未設定なので、在庫の増減は P0 にも A にも入っていません。

## 0. 一言で

- 工場の生産は、4 案ともどの週も同じでした（生産の差 0）。
- 販促で増えた SG の EC のクリームの 2028 年の納品（MID +6・HIGH +12 lot）は、2029 年の需要に回るはずだった在庫から出ています。
- その分、2029 年のクリームの未充足（⑤）が同じ量だけ増えました。
  - MID：SG の代理店 +3、SG の店舗 +2、SG の EC 自身 +1（計 +6）
  - HIGH：SG の代理店 +6、SG の店舗 +3、SG の EC 自身 +2、タイの代理店 +1（計 +12）
- 総納品（3,864 lot）は 4 案で同じです。
- P0 の差は MID +317,400 円・HIGH +680,316 円で、1 本目（能力に余裕）の約 3 割です。追加費用 276,000 円を引いた控除後の差 ΔA は、MID +41,400 円・HIGH +404,316 円です。

## 1. 合格の条件

| # | 条件 | 結果 |
|---|---|---|
| S1 | C01 が C3a の記録（新しい既定の値）を再現 | **合う**。注文残 192（市場別も：美容液 SG の代理店 50・SG の EC 27・SG の店舗 22・タイの代理店 5、クリーム 47・18・19・4）、総納品 3,864、売上 1,100,849,400 円、試算利益 601,449,564 円（PPC の台帳）。P0（報告期間）600,719,196 円 |
| S2 | 変換が 1 本目と同じ期待値 | **合う**。需要の増分 0・0・6・12 lot（反応 2028-W12〜W23、未反映の端数 0）、追加費用 276,000 円（週 23,000 円 × 12 週）。変換の道具の検査（案の写しの対象外の需要が元のモデルと同じ）は通った。C3a は能力だけを変えた写しなので、需要は正式なサンプルと同じ |
| S3 | LOW がエンジンの結果で C01 と同じ、A だけ −276,000 円 | **合う**。snapshot（forward・backward・ppc・psi）が同じ。P0 600,719,196 円は同じで、A は 600,443,196 円 |
| S4 | MID・HIGH の §2.2・§2.3 の表。①＝②＋③、②＝④＋⑤ が鍵ごとに合う。市場別・週別の差の和が全体の差に合う | **合う**。①〜⑤ は `period_fulfillment.request_table` が要求週ごとに検査（合わなければ止まる）。週別の表の各列は「その他の週」と「計」まで足すと全体の差になり、市場別の試算利益の差の和は ΔP0 と、報告期間の週別の試算利益の差の和に一致した（`strategy_compare` が検査し、合わなければ止まる） |
| S5 | 1 本目との対比の表 | §4 |
| S6 | エンジン・正式なサンプル・golden が変わっていない。`--changed` が通る | §7 |

## 2. 4 案の要約（報告期間 2027-W01〜2029-W52、付録 `summary/`）

| 案 | P0（円） | 追加費用 | A ＝ P0 − 追加費用 | ΔA | 対象（クリーム × SG の EC）①／④／⑤ | 他の市場の ④ の差・⑤ の差 | 押し戻し（延べ） |
|---|---:|---:|---:|---:|---|---|---:|
| C01 P_BASE_SHORT | 600,719,196 | 0 | 600,719,196 | 0 | 299／281／18 | — | 73,788 |
| C02 P_PROMO_LOW_SHORT | 600,719,196 | 276,000 | 600,443,196 | −276,000 | 299／281／18 | 0・0 | 73,788 |
| C03 P_PROMO_MID_SHORT | 601,036,596 | 276,000 | 600,760,596 | +41,400 | 305／286／19 | −5・+5 | 74,286 |
| C04 P_PROMO_HIGH_SHORT | 601,399,512 | 276,000 | 601,123,512 | +404,316 | 311／291／20 | −10・+10 | 74,778 |

- ②＝①、③＝0（配分の方針を付けていない）。④ はすべて当週の納品で、前倒しも遅配も 0。
- 製品の年齢（先入れ先出し）の最大は 4 案とも 27 週（対象のチャネルは 24 週）で、52 週超の納品は 0。グループの在庫の、週の最大は 4 案とも 601 lot。
- 押し戻しの延べ（工場 × 市場）は増えたが、工場の生産の量は同じ（§3.2）。

## 3. MID・HIGH で何が変わったか（C01 との差）

### 3.1 市場 × 要求年の ④・⑤（付録 `market/market_year_C03.csv`・`_C04.csv`）

| 案 | 市場（クリーム） | 年 | ④ 当週の差 | ⑤ の差 |
|---|---|---|---:|---:|
| MID | SG の EC（対象） | 2028 | +6 | 0 |
| MID | SG の EC（対象） | 2029 | −1 | +1 |
| MID | SG の代理店 | 2029 | −3 | +3 |
| MID | SG の店舗 | 2029 | −2 | +2 |
| HIGH | SG の EC（対象） | 2028 | +12 | 0 |
| HIGH | SG の EC（対象） | 2029 | −2 | +2 |
| HIGH | SG の代理店 | 2029 | −6 | +6 |
| HIGH | SG の店舗 | 2029 | −3 | +3 |
| HIGH | タイの代理店 | 2029 | −1 | +1 |

- MID：対象の ① は +6。そのうち 6 lot が 2028 年に当週で届いた。その分、2029 年の SG の代理店で 3、SG の店舗で 2、SG の EC 自身で 1 が届かなくなった（⑤ +6）。対象の ④ の差は差し引き +5。
- HIGH：対象の ① は +12。そのうち 12 lot が 2028 年に届き、2029 年の SG の代理店で 6、SG の店舗で 3、SG の EC 自身で 2、タイの代理店で 1 が届かなくなった（⑤ +12）。対象の ④ の差は差し引き +10。
- クリームの総納品（1,680 lot）は変わらない（工場の能力が決める）。⑤ の合計は、需要の増分（6・12 lot）だけ増えた。
- 美容液（工場の能力は製品ごとに別）は、①〜⑤・金額とも 4 案で同じ。

### 3.2 週別の表（2028-W08〜W30 と ⑤ が出た週。付録 `weekly/weekly_C03.md`・`_C04.md`）

HIGH の要点（全行は付録の表）：

| 週 | 追加費用 | 対象の当週の差（要求週） | 他の市場の当週の差（要求週） | 工場の生産の差 | 在庫の差（lot） | 試算利益の差 |
|---|---:|---:|---:|---:|---:|---:|
| 2028-W10・W11 | 23,000 ずつ | 0 | 0 | 0 | 0 | −720 ずつ |
| 2028-W12〜W23 | W12〜W21 は 23,000 ずつ | +1 ずつ（計 +12） | 0 | 0 | −1 ずつ減って W23 に −12 | 約 +194,000〜195,000 ずつ |
| 2028-W24〜2029-W04 | 0 | 0 | 0 | 0 | −12 のまま | 0 |
| 2029-W05〜W44 | 0 | W08・W10 に −1 | W05・W06・W21・W23・W25・W44 に −1、W07・W09 に −2（計 −10） | 0 | 欠けた分だけ戻り 0 へ | 欠けた週に約 −112,000〜−421,000 |
| 計 | 276,000 | +10 | −10 | 0 | −581 lot・週 | +680,316 |

- 費用は 2028-W10〜W21 に出て、効果（対象の当週の納品）は W12〜W23 に出た。その在庫は 2029 年に足りなくなり、2029-W05〜W44 に他の市場と対象自身の納品が欠けた。
- 工場の生産の差は全週 0。在庫は販促の期間に減り、2029 年の欠けた分だけ戻った。在庫の lot・週は全体で MID −284、HIGH −581 減った。保有費が未設定なので、この減少は P0 にも A にも入っていない。
- ①〜⑤ の列は要求週、費用・生産・在庫・試算利益の列は起きた週で数えた。週ごとの試算利益の −720 は、倉庫費の出る週のずれ。

### 3.3 P0 の差の市場別の内訳（報告期間、円。付録 `market/market_money_C03.csv`・`_C04.csv`）

| 案 | 市場（クリーム） | 売上の差 | 原価の差 | 経費の差 | 試算利益の差 |
|---|---|---:|---:|---:|---:|
| MID | SG の EC（対象） | +1,807,800 | +248,640 | +587,340 | +971,820 |
| MID | SG の代理店 | −513,360 | −146,700 | −30,312 | −336,348 |
| MID | SG の店舗 | −761,760 | −99,456 | −344,232 | −318,072 |
| MID | 計 | +532,680 | +2,484 | +212,796 | **+317,400**（＝ΔP0） |
| HIGH | SG の EC（対象） | +3,615,600 | +497,280 | +1,174,680 | +1,943,640 |
| HIGH | SG の代理店 | −1,026,720 | −293,400 | −60,624 | −672,696 |
| HIGH | SG の店舗 | −1,142,640 | −149,184 | −516,348 | −477,108 |
| HIGH | タイの代理店 | −172,800 | −49,056 | −10,224 | −113,520 |
| HIGH | 計 | +1,273,440 | +5,640 | +587,484 | **+680,316**（＝ΔP0） |

- 美容液の市場は全部 0。
- SG の EC の経費の差のうち、既存の 15% の広告費（`marketing_cost`）の増加は MID +271,170 円・HIGH +542,340 円（売上の差の 15%）。同じ額の `sga_cost`、運賃（MID +41,400）と倉庫費も増えた。
- 追加費用 276,000 円は P0 の外で、A の計算で引いている（ΔA ＝ ΔP0 − 276,000）。
- SG の店舗の経費の減り（MID −344,232。ほぼ全部が `sga_cost`）は、売上の減り（−761,760）の約 45% です。金額の規則は変えていません。この比率の理由は調べていません。

## 4. 1 本目（能力に余裕）との対比

同じ施策・同じシート・同じ変換で、工場の能力の条件だけが違う。1 本目の数は `WOM_Promo_Convert_Slice1_Report.md` §3。

| | 1 本目 MID | 2 本目 MID | 1 本目 HIGH | 2 本目 HIGH |
|---|---:|---:|---:|---:|
| 工場の能力 | 正式なサンプル | C3a（美容液 17／14、クリーム 13／11） | 正式なサンプル | C3a |
| 対象の ① の増分 | +6 | +6 | +12 | +12 |
| 対象の ④ の差（当週） | +6 | +5 | +12 | +10 |
| 他の市場の ⑤ の差 | 0 | +5（2029 年、SG の代理店 3・店舗 2） | 0 | +10（2029 年、SG の代理店 6・店舗 3・タイ 1） |
| 対象自身の 2029 年の ⑤ の差 | 0 | +1 | 0 | +2 |
| 総納品の差 | +6 | 0 | +12 | 0 |
| 工場の生産の差 | +6 | 0 | +12 | 0 |
| ΔP0（円） | +1,166,184 | +317,400 | +2,332,368 | +680,316 |
| 追加費用（円） | 276,000 | 276,000 | 276,000 | 276,000 |
| ΔA（円） | +890,184 | +41,400 | +2,056,368 | +404,316 |
| 在庫 | 作り溜めで最大 146 → 152 lot | 販促の期間に減り、lot・週で −284 | 最大 146 → 157 lot | lot・週で −581 |

1 本目は、工場が増えた需要を前の週に作り足して、増分が全部売上になった。2 本目は工場に作り足す余地が無く、増えた対象の納品は、後の年の他の市場（と対象自身）の納品と入れ替わった。

## 5. 道具の追加（`tools/strategy_compare.py`・`wom/strategy/compare.py`・`tools/compare_scenarios.py`）

- `strategy_compare --weekly <開始週> <終了週>` を足した。案ごとに次を書く：
  - `weekly_<案>.csv`・`.md`：週別の差。範囲の週と、⑤ が出た週（範囲の外も）の行に、「その他の週」と「計」の行を付ける。
  - `market_money_<案>.csv`：報告期間の市場別の売上・原価・経費・試算利益。base・alt・差。
  - `market_year_<案>.csv`：市場 × 要求年の ①・④ 当週・④・⑤。
  - md には、⑤ が出た週のうち差の無い週を載せない（CSV には全部ある）。
- 差の和の検査（S4）を書く前に行い、合わなければ止める（終了コード 2）。
- 計算は比較の道具の関数を使った：①〜⑤ は `period_fulfillment.request_table`、工場の生産は `compare_scenarios.factory_weekly`、在庫は `vc_inventory_weekly`、金額は新しい `compare_scenarios.money_by_week_market`。
- `money_by_week_market` は `money_by_week_sku` と同じ明細を使う。明細を選ぶ部分を `consolidated_money_frames` に切り出して、2 つの関数で共有した。`money_by_week_sku` の結果は変わらない（既存のテストで確かめた）。
  - 市場は各明細の Lot_ID の（製品・地域）から決める。Lot_ID の無い明細は「(Lot_ID なし)」の行にまとめる。
  - 週ごとの合計が `vc_v3_weekly.csv` の `profit_r2_hq_wk` に合わなければ止める。
- **金額の出どころ**：依頼書 §3 は「PPC の台帳」と書いていますが、P0 は Value Chain の明細（`vc_money_lines`、連結の 2 回目の試算利益）から出ています。市場別の和が ΔP0 に合うように、同じ明細を使いました。PPC の台帳（`ppc_node_pl_summary`）は別の台帳で、合計が P0 と一致しません。
- テスト `tests/test_strategy_weekly_market.py`（4 件、`tests/conftest.py` に領域 allocation で登録）：
  - 合成の 2 案で、週別の差が計に、市場別の差が ΔP0 に合う。⑤ が出た範囲の外の週に行が付く。
  - 費用の前提の週額の空欄・計画の外の週で止まる。
  - `money_by_week_market` の市場の和が `profit_r2_hq_wk` に合い、合わなければ止まる。

## 6. 気づいたこと

1. **欠けが出た週は、C01 でも ⑤ が出ている 2029 年の区間**です。2028 年の対象の要求が増えても工場の生産は変わらず（全週の差 0）、増えた分は在庫から出ました。その在庫が無くなった分だけ、もともと足りなかった区間の欠けが増えました。
2. **欠ける市場は、比例の押し戻し（`proportional_week`）で分かれた**：SG の代理店・店舗・EC・タイ。`tail` なら、別の市場に偏っていたはずです（段 1〜3）。
3. **増えた分の利益の差**：対象の 1 lot は約 +195,000 円です。他の市場の 1 lot の減り（例：SG の代理店 約 −112,000 円）より大きいので、ΔP0 は正になりました。市場ごとの 1 lot の利益の違いだけで決まっていて、販促の効果ではありません。
4. 保有費を置くと、在庫が減った分だけ（MID −284・HIGH −581 lot・週）、2 本目の A は 1 本目とは逆向きに動きます（1 本目は作り溜めで在庫が増えた）。

## 7. テストと変えていないもの

- `python -m pytest tests/test_strategy_weekly_market.py tests/test_test_areas.py`：8 passed。
- `python -m tools.quick_check --changed`：§7.1。
- エンジン（保護対象のコアを含む）・PPC・Value Chain・正式なサンプル・golden は変えていない（`git status`：変更は §5 のファイルとテスト・報告書・付録だけ）。

### 7.1 `--changed` の結果

`python -m tools.quick_check --changed`（2026-11-23、Windows）：領域 allocation・ppc・public、**759 passed・0 failed**・617 deselected、576 秒。保護対象のコアは変えていないので、full と 3 層テストの要求は出ていない。

## 8. 大杉さんが実機で確かめる手順

```powershell
$PY="C:\Users\ohsug\anaconda3\python.exe"; $W="output/strategy_slice2/ws"; $M="data/sample/cosmetics-sg-th-2027-2029"; $S="tests/data/strategy_slice1"
& $PY -m tools.cockpit_cases new  --ws $W --model $M --max-age-weeks 52 --name P_BASE_SHORT
& $PY -m tools.cockpit_cases set  --ws $W --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
& $PY -m tools.cockpit_cases set  --ws $W --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
& $PY -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_LOW_SHORT
& $PY -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_MID_SHORT
& $PY -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_HIGH_SHORT
& $PY -m tools.strategy_convert --ws $W --case C01 --plan P_BASE       --sheets $S --base-model $M
& $PY -m tools.strategy_convert --ws $W --case C02 --plan P_PROMO_LOW  --sheets $S --base-model $M
& $PY -m tools.strategy_convert --ws $W --case C03 --plan P_PROMO_MID  --sheets $S --base-model $M
& $PY -m tools.strategy_convert --ws $W --case C04 --plan P_PROMO_HIGH --sheets $S --base-model $M
& $PY -m tools.cockpit_cases run --ws $W --case C01 C02 C03 C04
& $PY -m tools.strategy_compare --ws $W --base C01 --cases C02,C03,C04 --weekly 2028-W08 2028-W30
```

- 作業のフォルダ（`output/strategy_slice2/ws`）は今回の実行で既にあるので、`new` は止まります。そのまま見るなら最後の 1 行だけ、作り直すなら別の名前で。
- 見る所：
  - `strategy_compare` の画面の出力（§2 の表）
  - `<作業>/strategy_compare/C01_C02_C03_C04/weekly_C03.md`（週別の差・市場別の金額・市場 × 年）
- **比較の画面で C01 と C03 を並べる**：

```powershell
& $PY -m main --cockpit-compare --ws output/strategy_slice2/ws --base C01 --alt C03
```

  - P0 の差 +317,400 円を確かめる。
  - 需要の差は SG の EC のクリームの 6 週だけ。
  - 2029 年に SG の代理店・店舗の当週の納品が減っている。
  - 費用の前提の行 `promo_campaign_add` の分だけ控除後が下がる。

## 付録

- `summary/`：4 案の要約（`strategy_summary.csv`・`.md`）、①〜⑤ の鍵別、押し戻し
- `weekly/`：週別の差（C02・C03・C04。csv と md）
- `market/`：市場別の金額の差、市場 × 要求年の差
- `change_log/`：4 案の変更記録と費用の前提
- `scripts/setup_run.sh`：案を作って回した手順

## commit メッセージの下書き

- `commit_msg237.txt`：道具とテスト
- `commit_msg238.txt`：報告書と付録

## 大杉さんの判断（2026-11-23）

- 市場別の金額は、P0 と同じ Value Chain の明細から出す（依頼書の「PPC の台帳」は誤り。PPC の台帳での内訳は要らない）。
