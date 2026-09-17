# -*- coding: utf-8 -*-
"""
wom/allocation/transmission.py — 伝達式 Step 0〜5（単位 P&L・純関数）
====================================================================
1 チャネル（＝市場）の per-lot 損益を、原価ブロック（通貨別・関税前）と
外部環境シナリオ θ から合成する純関数群。配分比率 x やグリッド（Step 6〜11）は
`grid.py` が扱う。本モジュールは「1 点が正しい」ことを担保する土台。

正典：docs/design/ask_global_allocation_spec.md §5（Step 0〜5）
参照：tools/proto_terrain2.py（伝達式の解釈はこちらを優先）

Step 対応:
  Step 0   レート解決            rates()
  Step 0.5 原価ブロック          CostBlock（入力。導出は cost_block.py の役割）
  Step 1   製造原価の合成        unit_pnl(): usd/eur/jpy × レート
  Step 2   移転価格             transfer_price_usd（既定 17.6 = 16.0×1.1）
  Step 3   関税                 tariff_rate × transfer_price（transfer_price 基準）
  Step 4   チャネル原価の確定     unit_pnl().cost
  Step 5   販売価格             price_local × レート

検証（付録 A.1、transfer_price=17.6・EUR=USD×1.08）:
  FX150 $6 → JP 750.0 / US 1747.5 / EU 1831.5
  FX200 $6 → JP 295.0 / US 2855.0 / EU 2967.0
  FX200 $8 → JP -105.0 / US 2455.0 / EU 2567.0
  FX115 $6 → JP 1068.5 / US 972.25 / EU 1036.65

Phase 5（数量依存の関税・cliff型）:
  正典：requests/Phase5_DesignMD_NonConcaveTariff.md §3
  CostBlock.tariff_at(qty) / unit_pnl_at_quantity() を追加（本節末尾）。
  unit_pnl() 本体は無変更——unit_pnl_at_quantity() は dataclasses.replace() 経由で
  呼ぶだけで、計算式を二重に持たない。
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional

# 移転価格（Step 2）: 終端 MOM 累積原価 16.0 USD × (1 + 0.1) = 17.6 USD
#   ppc_transfer_price_rule.csv: Bottling_Noda cost_plus 0.1 USD
DEFAULT_TRANSFER_PRICE_USD = 16.0 * 1.1


@dataclass(frozen=True)
class Scenario:
    """外部環境シナリオ θ のうち、単位 P&L に効く成分。

    fx_usd        : USD/JPY スポット（Step 0 の e_set）
    material_usd  : 原料の USD 建て価格（Step 1 で原料ブロックを上書き）
    eur_per_usd   : EUR/USD 比（ppc_fx_rate.csv 実関係 = 1.08）
    """
    fx_usd: float
    material_usd: float          # 既定値なし（Phase 8-1b）: soysauce の $6 が汎用既定値の
                                  # 席に座り、oil-global-2027 に黙って複写されていたことの是正。
                                  # 呼び出し側は必ず明示すること。
    eur_per_usd: float = 1.08


@dataclass(frozen=True)
class CostBlock:
    """1 チャネルの原価ブロック（per lot・関税前）＋販売条件。

    通貨別ブロック（Step 0.5 の導出結果。cost_block.py が既存 CSV から導出する）:
      usd : 外貨(USD)建てブロック合計。原料 base $6 を含む（scenario で置換される）
      eur : EUR 建てブロック合計
      jpy : 円建てブロック合計（醸造・瓶詰・FG 倉庫・国内 DC 等）

    material_usd_base : usd に含まれる原料の base 額（scenario.material_usd で差し替える基準）
    tariff_rate       : 従価関税率（transfer_price 基準・Step 3）
    price_local       : 販売価格（現地通貨建て・ppc_market_price）
    ccy               : 販売通貨 'JPY' / 'USD' / 'EUR'
    demand_qty        : 市場需要（lot・Step 6 の D[m]）

    tariff_rate_preferential : Phase 5・cliff型の特恵税率（既定 None＝従来動作）。
        配分量が preferential_threshold_lot 以上になったときに tariff_rate の
        代わりに適用される（FTA原産地規則の「域内付加価値比率が閾値を超えれば
        特恵税率」を数量依存関税として表現したもの）。
    preferential_threshold_lot : 特恵発動の閾値（lot、既定 None）。
        どちらか一方でも None なら常に tariff_rate（従来動作、後方互換）。
    """
    usd: float
    eur: float
    jpy: float
    tariff_rate: float
    price_local: float
    ccy: str
    demand_qty: int
    material_usd_base: float     # 既定値なし（Phase 8-1b、material_usd と同じ理由）
    tariff_rate_preferential: Optional[float] = None
    preferential_threshold_lot: Optional[float] = None

    def tariff_at(self, qty: float) -> float:
        """配分量 qty のときに適用される関税率（Step 3 用）。

        cliff型: qty >= preferential_threshold_lot なら tariff_rate_preferential、
        そうでなければ tariff_rate。どちらかが None なら常に tariff_rate。
        """
        if self.tariff_rate_preferential is None or self.preferential_threshold_lot is None:
            return self.tariff_rate
        return (self.tariff_rate_preferential
                if qty >= self.preferential_threshold_lot else self.tariff_rate)


def rates(sc: Scenario) -> Dict[str, float]:
    """Step 0: 通貨→JPY レート（base_currency=JPY 前提）。"""
    return {"JPY": 1.0, "USD": sc.fx_usd, "EUR": sc.fx_usd * sc.eur_per_usd}


def unit_pnl(cb: CostBlock, sc: Scenario,
             transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD) -> Dict[str, float]:
    """Step 1〜5: 1 チャネルの per-lot 損益（JPY 建て）。

    Returns dict:
      rev    売価（JPY/lot）           = price_local × rate[ccy]
      cost   原価（JPY/lot・関税込）    = usd_eff×rate.USD + eur×rate.EUR + jpy
      margin 単位マージン              = rev − cost
      fcost  外貨建コスト（JPY 換算）   = usd_eff×rate.USD + eur×rate.EUR   （FCR 用）
      frev   外貨建収入（JPY 換算）     = rev（販売通貨≠JPY のとき）        （FRR 用）
    """
    r = rates(sc)
    # Step 1（原料上書き）+ Step 3（関税 = 率 × 移転価格、USD 建て）
    usd_eff = cb.usd - cb.material_usd_base + sc.material_usd \
        + cb.tariff_rate * transfer_price_usd
    cost = usd_eff * r["USD"] + cb.eur * r["EUR"] + cb.jpy
    rev = cb.price_local * r[cb.ccy]
    fcost = usd_eff * r["USD"] + cb.eur * r["EUR"]
    frev = rev if cb.ccy != "JPY" else 0.0
    return {"rev": rev, "cost": cost, "margin": rev - cost,
            "fcost": fcost, "frev": frev}


def unit_pnl_at_quantity(
    cb: CostBlock, sc: Scenario, qty: float,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
) -> Dict[str, float]:
    """配分量 qty のときの per-lot 損益（Phase 5・cliff型の数量依存関税）。

    cb.tariff_at(qty) で税率を解決し、その税率を持つ CostBlock の複製に対して
    既存の unit_pnl() を呼ぶ。計算式そのものは unit_pnl() のまま（重複実装しない）。
    cliff未設定（tariff_rate_preferential/preferential_threshold_lot が None）の
    CostBlock では tariff_at(qty) は常に cb.tariff_rate を返すため、
    このとき unit_pnl(cb, ...) と完全に一致する（後方互換）。
    """
    rate = cb.tariff_at(qty)
    if rate == cb.tariff_rate:
        return unit_pnl(cb, sc, transfer_price_usd)       # 従来経路そのまま
    return unit_pnl(replace(cb, tariff_rate=rate), sc, transfer_price_usd)
