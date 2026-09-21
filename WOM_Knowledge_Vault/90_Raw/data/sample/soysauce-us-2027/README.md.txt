# soysauce-us-2027 — 醤油の対米/対欧輸出ケース（S1 米国集中ベースライン）

日本の特産品「醤油」を千葉県野田（仮想MOM）で醸造・瓶詰し、海上で米国（西海岸SF・東海岸NY）と
欧州（ロッテルダムDC→仏・白・蘭）へ輸出、海外在庫バッファ拠点を経て各市場のレストラン（最終消費）へ届ける
週次PSI×PPCモデル。デモ動画（トランプ関税スイープ／損益分岐週アニメ／米国集中 vs 欧州分散）用。

## 二本木
- Inbound: Materials_JP(leaf_in) → Brewing_Noda(mom) → Bottling_Noda(終端mom)
- Bridge: SP_Soy(supply_point)
- Outbound: FG_WH_Noda(dad,buffer) → { DC_US_SF→Rest_US_West / DC_US_NY→Rest_US_East /
  DC_JP→Rest_JP / DC_EU_RTM→Rest_FR,Rest_BE,Rest_NL }（各leaf_out）
- 海外在庫バッファ: FG_WH_Noda / DC_US_SF / DC_US_NY / DC_EU_RTM（buffering_stock_flag=1, ss_days=21）
- 醤油=液体・重量物・賞味期限（sku_master.shelf_life_wks=78）、海上レーン（lt_wks: SF5 / NY6 / EU6）

## デモのシナリオ操作
- **関税スイープ**: ppc_tariff_rule.csv の US 2行（DC_US_SF->Rest_US_West / DC_US_NY->Rest_US_East）
  tariff_rate を 0.0 / 0.10 / 0.125 に。edge_cost_master.csv にも scenario(Base/Tariff10/Tariff0)を同梱。
- **配分 S1→S2**: demand_forecast.csv の region 数量を切替。
  - S1(米国集中・本データの初期値): JP300 / US_W350 / US_E350 / EU0
  - S2(欧州分散): JP300 / US_W175 / US_E175 / FR150 / BE100 / NL100
- HSコード 2103.10（醤油）。関税率・価格は例示（実勢は要確認）。

## 実行・検証
`python -m main` → Load Model Folder → soysauce-us-2027 → Run Planning。
World Map / Network(バッファ在庫) / Management(損益分岐週) / PPC(利益ゾーン) を確認。
S1/S2 × 関税3水準を回し、収録準備メモ B表の例示値を実出力へ差し替える。

*注: 本データは公開情報とドメイン知識のみに基づく例示・教育用。特定企業を指すものではない（国産醤油の一般カテゴリ）。*
*AGENTSルールに従い、コミット/プッシュはオーナーが実施。*

---

## シナリオ切替の手順（S1 米国集中 ⇄ S2 欧州分散）

配分は `demand_forecast.csv`（active）を差し替えて切替える。同梱の2ファイルを用意済み：
- `demand_forecast_S1.csv` … 米国集中（JP300 / US_W350 / US_E350 / EU0）＝現行ベースライン
- `demand_forecast_S2.csv` … 欧州分散（JP300 / US_W175 / US_E175 / FR150 / BE100 / NL100）

**切替コマンド（Windows）**
```
copy /Y demand_forecast_S2.csv demand_forecast.csv   & rem → S2へ
copy /Y demand_forecast_S1.csv demand_forecast.csv   & rem → S1へ戻す
```
差し替え後、GUIで Run Planning を再実行。S2にすると欧州レストラン（Rest_FR/BE/NL）のPSIが立ち上がる。

## 関税スイープの手順（US 0% / 10% / 12.5%）
`ppc_tariff_rule.csv` の US 2行（`DC_US_SF->Rest_US_West` と `DC_US_NY->Rest_US_East`）の `tariff_rate` を
`0.125`（現行）/ `0.10` / `0.0` に書き換えて Run Planning。
※ Management の「Tariff & FX — Landed Cost」パネルは Base/Tariff10/Tariff0 を同時表示するので、
   1回の実行で3水準の Landed GM%・関税負担を比較できる（`edge_cost_master.csv` の scenario 行）。

## 収録用の6ラン・マトリクス
S1/S2 × 関税(0/10/12.5%) の6通りを回し、各回で以下を記録して収録準備メモ B表を実数化：
- PPC KPI Summary：Revenue / Gross Marg / Tariff Cost
- Management P&L：Revenue / Gross Profit / Gross Margin% / Ccc Wks
- Landed Cost パネル：Landed GM% / 関税負担% （3水準同時表示）
