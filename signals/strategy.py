from typing import Dict, List, Optional

import pandas as pd

from signals.indicators import (
    calc_moving_average, calc_rsi, calc_macd, calc_volume_ratio,
    calc_atr, calc_bollinger_bands, calc_obv,
    calc_stochastic_rsi, calc_obv_divergence_strength,
    calc_obv_bearish_divergence_strength,
)
# Local defaults — mirrors config.py values so this module has no dependency on config.py.
# autonomous/analyzer.py passes overrides via strategy_settings dict at call time.
SHORT_MA = 10
LONG_MA = 50
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_EXTREME_LOW = 20          # RSI 연속 강도 점수 상한 기준 (과매도 극단)
RSI_EXTREME_HIGH = 80         # RSI 연속 강도 점수 상한 기준 (과매수 극단)
VIX_EXTREME_FEAR = 30
VIX_FEAR = 25
VIX_EXTREME_GREED = 12
INVESTOR_CONSEC_DAYS = 3
STOCH_RSI_PERIOD = 14
STOCH_RSI_SMOOTH_K = 3
STOCH_RSI_SMOOTH_D = 3
STOCH_RSI_OVERSOLD = 20
STOCH_RSI_OVERBOUGHT = 80
MACRO_SIGNAL_MAX_SCORE = 1.5
BB_PCT_B_LOWER = 0.2          # 볼린저밴드 %B 하단 근처 임계값
BB_PCT_B_UPPER = 0.8          # 볼린저밴드 %B 상단 근처 임계값
OBV_DIVERGENCE_WEIGHT = 0.8   # OBV 다이버전스 가중치
CONFLUENCE_MIXED_TOLERANCE = 1.0  # 합류 점수 혼재 판정 허용 오차 (net_score 방식, 1.0으로 완화)
SIGNAL_STRENGTH_STRONG_BUY = 3.5   # 강한 매수 시그널 임계값
SIGNAL_STRENGTH_BUY = 1.5          # 매수 시그널 임계값
SIGNAL_STRENGTH_STRONG_SELL = -3.5  # 강한 매도 시그널 임계값
SIGNAL_STRENGTH_SELL = -1.5        # 매도 시그널 임계값
VOLUME_RATIO_HIGH = 1.5       # 거래량 비율 높음 기준
VOLUME_RATIO_LOW = 0.5        # 거래량 비율 낮음 기준

from backtest import Signal, SignalType


def _count_consecutive(series: pd.Series) -> int:
    """시리즈 끝에서부터 양수(또는 음수) 연속 일수를 반환한다.
    양수 연속이면 +N, 음수 연속이면 -N, 혼재면 0."""
    if series.empty:
        return 0
    count = 0
    last_sign = 1 if series.iloc[-1] > 0 else (-1 if series.iloc[-1] < 0 else 0)
    if last_sign == 0:
        return 0
    for val in reversed(series.values):
        if (last_sign > 0 and val > 0) or (last_sign < 0 and val < 0):
            count += 1
        else:
            break
    return count * last_sign


def _detect_market_regime(
    closes: pd.Series,
    short_ma: pd.Series,
    long_ma: pd.Series,
    rsi_value: Optional[float],
) -> str:
    """시장 레짐을 판단한다: 'uptrend', 'downtrend', 'sideways'.

    기준:
    - 상승장: 현재가 > 장기MA AND 단기MA > 장기MA AND RSI > 50
    - 하락장: 현재가 < 장기MA AND 단기MA < 장기MA AND RSI < 50
    - 횡보장: 그 외
    """
    price = float(closes.iloc[-1])
    cur_short = float(short_ma.iloc[-1])
    cur_long = float(long_ma.iloc[-1])

    if pd.isna(cur_short) or pd.isna(cur_long):
        return "sideways"

    rsi_ok = rsi_value is not None

    if price > cur_long and cur_short > cur_long and (not rsi_ok or rsi_value > 50):
        return "uptrend"
    elif price < cur_long and cur_short < cur_long and (not rsi_ok or rsi_value < 50):
        return "downtrend"
    return "sideways"


def _regime_weight(regime: str, signal_type: str) -> float:
    """시장 레짐에 따라 시그널 가중치 배율을 반환한다.

    상승장: 매수 1.2x, 매도 0.8x
    하락장: 매도 1.2x, 매수 0.8x
    횡보장: 1.0x
    """
    if regime == "uptrend":
        return 1.2 if signal_type == "buy" else 0.8
    elif regime == "downtrend":
        return 1.2 if signal_type == "sell" else 0.8
    return 1.0


def _continuous_rsi_score(
    rsi_value: float,
    rsi_oversold: float = RSI_OVERSOLD,
    rsi_overbought: float = RSI_OVERBOUGHT,
    rsi_extreme_low: float = RSI_EXTREME_LOW,
    rsi_extreme_high: float = RSI_EXTREME_HIGH,
) -> float:
    """RSI 연속 강도 점수 (0.0 ~ 1.0).
    과매도: RSI oversold=0.5, 중간=0.75, extreme_low=1.0 (선형 보간)
    과매수: RSI overbought=0.5, 중간=0.75, extreme_high=1.0 (선형 보간)
    중립 구간은 0.0.
    """
    if rsi_value <= rsi_extreme_low:
        return 1.0
    elif rsi_value <= rsi_oversold:
        # extreme_low~oversold 구간: 1.0 → 0.5 선형
        return 0.5 + 0.5 * (rsi_oversold - rsi_value) / (rsi_oversold - rsi_extreme_low)
    elif rsi_value >= rsi_extreme_high:
        return 1.0
    elif rsi_value >= rsi_overbought:
        # overbought~extreme_high 구간: 0.5 → 1.0 선형
        return 0.5 + 0.5 * (rsi_value - rsi_overbought) / (rsi_extreme_high - rsi_overbought)
    return 0.0


def _continuous_bb_score(
    price: float,
    bb_lower: float,
    bb_upper: float,
    bb_middle: float,
    bb_pct_b_lower: float = BB_PCT_B_LOWER,
    bb_pct_b_upper: float = BB_PCT_B_UPPER,
) -> float:
    """볼린저밴드 %B 기반 연속 점수 (0.0 ~ 1.0).
    하단 이탈: 1.0 (매수)
    하단 근처(하위 bb_pct_b_lower): 0.3~0.7 (매수)
    상단 이탈: 1.0 (매도)
    상단 근처(상위 bb_pct_b_upper): 0.3~0.7 (매도)
    반환: (buy_score, sell_score)
    """
    bb_range = bb_upper - bb_lower
    if bb_range <= 0:
        return 0.0

    pct_b = (price - bb_lower) / bb_range  # 0=하단, 1=상단

    if pct_b <= 0:  # 하단 이탈
        return 1.0  # buy
    elif pct_b < bb_pct_b_lower:  # 하단 근처
        return 0.3 + 0.4 * (bb_pct_b_lower - pct_b) / bb_pct_b_lower  # 0.3~0.7 buy
    elif pct_b >= 1.0:  # 상단 이탈
        return -1.0  # sell (음수로 표현)
    elif pct_b > bb_pct_b_upper:  # 상단 근처
        return -(0.3 + 0.4 * (pct_b - bb_pct_b_upper) / (1.0 - bb_pct_b_upper))  # -0.3~-0.7 sell
    return 0.0


def analyze_detailed(
    df: pd.DataFrame,
    ticker: str,
    name: str,
    investor_df: Optional[pd.DataFrame] = None,
    vix_value: Optional[float] = None,
    strategy_settings: Optional[Dict] = None,
    macro_data: Optional[Dict] = None,
) -> Dict:
    """주어진 OHLCV 데이터를 분석하여 구조화된 시그널 데이터를 반환한다.

    v2: 연속 강도 점수 + 수급 분리 + OBV 다이버전스 + Stochastic RSI + 시장 레짐 가중치

    Returns:
        dict with keys: name, ticker, price, change_pct, signals, indicators,
                        investor, confluence_score, total_indicators, market_regime
    """
    result = {
        "name": name,
        "ticker": ticker,
        "price": 0,
        "change_pct": 0.0,
        "signals": [],
        "indicators": {},
        "investor": {},
        "confluence_score": 0,
        "total_indicators": 10,  # MA, RSI, MACD, BB, OBV, VIX, 외인, 기관, StochRSI, 매크로
        "market_regime": "sideways",
    }

    settings = strategy_settings or {}
    short_ma_days = int(settings.get("short_ma", SHORT_MA))
    long_ma_days = int(settings.get("long_ma", LONG_MA))
    rsi_period = int(settings.get("rsi_period", RSI_PERIOD))
    rsi_oversold = float(settings.get("rsi_oversold", RSI_OVERSOLD))
    rsi_overbought = float(settings.get("rsi_overbought", RSI_OVERBOUGHT))
    rsi_extreme_low = float(settings.get("rsi_extreme_low", RSI_EXTREME_LOW))
    rsi_extreme_high = float(settings.get("rsi_extreme_high", RSI_EXTREME_HIGH))
    stoch_rsi_period = int(settings.get("stoch_rsi_period", STOCH_RSI_PERIOD))
    stoch_rsi_smooth_k = int(settings.get("stoch_rsi_smooth_k", STOCH_RSI_SMOOTH_K))
    stoch_rsi_smooth_d = int(settings.get("stoch_rsi_smooth_d", STOCH_RSI_SMOOTH_D))
    stoch_rsi_oversold = float(settings.get("stoch_rsi_oversold", STOCH_RSI_OVERSOLD))
    stoch_rsi_overbought = float(settings.get("stoch_rsi_overbought", STOCH_RSI_OVERBOUGHT))
    investor_consec_days = int(settings.get("investor_consec_days", INVESTOR_CONSEC_DAYS))
    vix_extreme_fear = float(settings.get("vix_extreme_fear", VIX_EXTREME_FEAR))
    vix_fear = float(settings.get("vix_fear", VIX_FEAR))
    vix_extreme_greed = float(settings.get("vix_extreme_greed", VIX_EXTREME_GREED))
    bb_pct_b_lower = float(settings.get("bb_pct_b_lower", BB_PCT_B_LOWER))
    bb_pct_b_upper = float(settings.get("bb_pct_b_upper", BB_PCT_B_UPPER))
    obv_divergence_weight = float(settings.get("obv_divergence_weight", OBV_DIVERGENCE_WEIGHT))
    confluence_mixed_tolerance = float(settings.get("confluence_mixed_tolerance", CONFLUENCE_MIXED_TOLERANCE))
    signal_strength_strong_buy = float(settings.get("signal_strength_strong_buy", SIGNAL_STRENGTH_STRONG_BUY))
    signal_strength_buy = float(settings.get("signal_strength_buy", SIGNAL_STRENGTH_BUY))
    signal_strength_strong_sell = float(settings.get("signal_strength_strong_sell", SIGNAL_STRENGTH_STRONG_SELL))
    signal_strength_sell = float(settings.get("signal_strength_sell", SIGNAL_STRENGTH_SELL))
    volume_ratio_high = float(settings.get("volume_ratio_high", VOLUME_RATIO_HIGH))
    volume_ratio_low = float(settings.get("volume_ratio_low", VOLUME_RATIO_LOW))

    if len(df) < long_ma_days:
        return result

    closes = df["종가"]
    volumes = df["거래량"]
    current_price = int(closes.iloc[-1])
    prev_price = int(closes.iloc[-2]) if len(closes) >= 2 else current_price
    change_pct = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0.0

    result["price"] = current_price
    result["change_pct"] = round(change_pct, 2)

    signals = []  # type: List[Dict]
    buy_score = 0.0
    sell_score = 0.0

    # ── 지표 계산 ──────────────────────────────────
    short_ma = calc_moving_average(closes, short_ma_days)
    long_ma = calc_moving_average(closes, long_ma_days)
    rsi = calc_rsi(closes, rsi_period)
    macd_line, signal_line, histogram = calc_macd(closes)
    volume_ratio = calc_volume_ratio(volumes)
    atr = calc_atr(df["고가"], df["저가"], closes, period=14)
    bb_upper, bb_middle, bb_lower = calc_bollinger_bands(closes, 20, 2)
    obv = calc_obv(closes, volumes)
    stoch_k, stoch_d = calc_stochastic_rsi(
        closes, stoch_rsi_period, stoch_rsi_smooth_k, stoch_rsi_smooth_d,
    )

    current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    current_histogram = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
    current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None
    current_bb_upper = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None
    current_bb_lower = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None
    current_bb_middle = float(bb_middle.iloc[-1]) if not pd.isna(bb_middle.iloc[-1]) else None
    current_obv = float(obv.iloc[-1])
    current_stoch_k = float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else None
    current_stoch_d = float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else None

    atr_stop_loss = int(current_price - 2 * current_atr) if current_atr else None

    result["indicators"] = {
        "rsi": current_rsi,
        "macd_histogram": current_histogram,
        "short_ma": float(short_ma.iloc[-1]) if not pd.isna(short_ma.iloc[-1]) else None,
        "long_ma": float(long_ma.iloc[-1]) if not pd.isna(long_ma.iloc[-1]) else None,
        "volume_ratio": round(volume_ratio, 2),
        "atr": round(current_atr, 0) if current_atr else None,
        "atr_stop_loss": atr_stop_loss,
        "bb_upper": round(current_bb_upper, 0) if current_bb_upper else None,
        "bb_lower": round(current_bb_lower, 0) if current_bb_lower else None,
        "obv": current_obv,
        "stoch_rsi_k": round(current_stoch_k, 1) if current_stoch_k is not None else None,
        "stoch_rsi_d": round(current_stoch_d, 1) if current_stoch_d is not None else None,
    }

    # ── 시장 레짐 판단 ────────────────────────────
    regime = _detect_market_regime(closes, short_ma, long_ma, current_rsi)
    result["market_regime"] = regime

    # ── 1. 이동평균선 (연속 점수) ──────────────────
    vol_note = ""
    if volume_ratio >= volume_ratio_high:
        vol_note = " [거래량 확인 ↑]"
    elif volume_ratio < volume_ratio_low:
        vol_note = " [거래량 부족 주의]"

    cur_short_val = float(short_ma.iloc[-1]) if not pd.isna(short_ma.iloc[-1]) else None
    cur_long_val = float(long_ma.iloc[-1]) if not pd.isna(long_ma.iloc[-1]) else None

    if cur_short_val is not None and cur_long_val is not None:
        prev_short_val = float(short_ma.iloc[-2]) if not pd.isna(short_ma.iloc[-2]) else None
        prev_long_val = float(long_ma.iloc[-2]) if not pd.isna(long_ma.iloc[-2]) else None

        if prev_short_val is not None and prev_long_val is not None:
            # 크로스오버: 1.0점
            if prev_short_val <= prev_long_val and cur_short_val > cur_long_val:
                ma_score = 1.0 * _regime_weight(regime, "buy")
                signals.append({
                    "trigger": "골든크로스",
                    "type": "buy",
                    "source": "MA_CROSS",
                    "detail": f"{short_ma_days}일선({cur_short_val:,.0f}) > {long_ma_days}일선({cur_long_val:,.0f}) 상향 돌파{vol_note}",
                    "strength": round(ma_score, 2),
                })
                buy_score += ma_score
            elif prev_short_val >= prev_long_val and cur_short_val < cur_long_val:
                ma_score = 1.0 * _regime_weight(regime, "sell")
                signals.append({
                    "trigger": "데드크로스",
                    "type": "sell",
                    "source": "MA_CROSS",
                    "detail": f"{short_ma_days}일선({cur_short_val:,.0f}) < {long_ma_days}일선({cur_long_val:,.0f}) 하향 돌파{vol_note}",
                    "strength": round(ma_score, 2),
                })
                sell_score += ma_score
            else:
                # 추세 정렬: 크로스 없어도 정렬 방향에 보조 점수
                if cur_short_val > cur_long_val and current_price > cur_short_val:
                    # 강한 상승 정렬 (가격 > 단기 > 장기)
                    align_score = 0.4 * _regime_weight(regime, "buy")
                    signals.append({
                        "trigger": "MA 상승 정렬",
                        "type": "buy",
                        "source": "MA_ALIGN",
                        "detail": f"가격({current_price:,}) > {short_ma_days}일선({cur_short_val:,.0f}) > {long_ma_days}일선({cur_long_val:,.0f}) 강한 상승 정렬",
                        "strength": round(align_score, 2),
                    })
                    buy_score += align_score
                elif cur_short_val < cur_long_val and current_price < cur_short_val:
                    # 강한 하락 정렬 (가격 < 단기 < 장기)
                    align_score = 0.4 * _regime_weight(regime, "sell")
                    signals.append({
                        "trigger": "MA 하락 정렬",
                        "type": "sell",
                        "source": "MA_ALIGN",
                        "detail": f"가격({current_price:,}) < {short_ma_days}일선({cur_short_val:,.0f}) < {long_ma_days}일선({cur_long_val:,.0f}) 강한 하락 정렬",
                        "strength": round(align_score, 2),
                    })
                    sell_score += align_score

    # ── 2. RSI (연속 강도 점수) ────────────────────
    rsi_fired_buy = False
    rsi_fired_sell = False
    if current_rsi is not None:
        rsi_score = _continuous_rsi_score(current_rsi, rsi_oversold, rsi_overbought, rsi_extreme_low, rsi_extreme_high)
        if rsi_score > 0:
            if current_rsi <= rsi_oversold:
                weighted = rsi_score * _regime_weight(regime, "buy")
                signals.append({
                    "trigger": "RSI 과매도",
                    "type": "buy",
                    "source": "RSI",
                    "detail": f"RSI {current_rsi:.1f} (강도: {rsi_score:.1f})",
                    "strength": round(weighted, 2),
                })
                buy_score += weighted
                rsi_fired_buy = True
            elif current_rsi <= 40:
                # RSI 35~40: graduated buy signal (데드존 해소)
                # 40에 가까울수록 약한 신호
                grad_strength = 0.5 * (40 - current_rsi) / (40 - rsi_oversold)
                weighted = grad_strength * _regime_weight(regime, "buy")
                signals.append({
                    "trigger": "RSI 근접 과매도",
                    "type": "buy",
                    "source": "RSI",
                    "detail": f"RSI {current_rsi:.1f} (근접 과매도, 강도: {grad_strength:.2f})",
                    "strength": round(weighted, 2),
                })
                buy_score += weighted
                rsi_fired_buy = True
            elif current_rsi >= rsi_overbought:
                weighted = rsi_score * _regime_weight(regime, "sell")
                signals.append({
                    "trigger": "RSI 과매수",
                    "type": "sell",
                    "source": "RSI",
                    "detail": f"RSI {current_rsi:.1f} (강도: {rsi_score:.1f})",
                    "strength": round(weighted, 2),
                })
                sell_score += weighted
                rsi_fired_sell = True

    # ── 3. MACD (연속 강도 점수) ───────────────────
    if not pd.isna(macd_line.iloc[-2]) and not pd.isna(macd_line.iloc[-1]):
        prev_macd = float(macd_line.iloc[-2])
        prev_sig = float(signal_line.iloc[-2])
        cur_macd = float(macd_line.iloc[-1])
        cur_sig = float(signal_line.iloc[-1])

        if prev_macd <= prev_sig and cur_macd > cur_sig:
            # 크로스오버: 1.0
            macd_score = 1.0 * _regime_weight(regime, "buy")
            signals.append({
                "trigger": "MACD 매수",
                "type": "buy",
                "source": "MACD",
                "detail": "MACD 라인이 시그널 라인을 상향 돌파",
                "strength": round(macd_score, 2),
            })
            buy_score += macd_score
        elif prev_macd >= prev_sig and cur_macd < cur_sig:
            macd_score = 1.0 * _regime_weight(regime, "sell")
            signals.append({
                "trigger": "MACD 매도",
                "type": "sell",
                "source": "MACD",
                "detail": "MACD 라인이 시그널 라인을 하향 돌파",
                "strength": round(macd_score, 2),
            })
            sell_score += macd_score
        else:
            # 히스토그램 방향 보조 점수
            if current_histogram is not None:
                prev_hist = float(histogram.iloc[-2]) if not pd.isna(histogram.iloc[-2]) else 0
                if current_histogram > 0 and current_histogram > prev_hist:
                    # 양수 히스토그램 확대 → 매수 보조
                    buy_score += 0.3 * _regime_weight(regime, "buy")
                elif current_histogram < 0 and current_histogram < prev_hist:
                    # 음수 히스토그램 확대 → 매도 보조
                    sell_score += 0.3 * _regime_weight(regime, "sell")

    # ── 4. 볼린저밴드 (%B 기반 연속 점수) ──────────
    if current_bb_lower is not None and current_bb_upper is not None and current_bb_middle is not None:
        bb_score = _continuous_bb_score(current_price, current_bb_lower, current_bb_upper, current_bb_middle, bb_pct_b_lower, bb_pct_b_upper)
        if bb_score > 0:
            weighted = bb_score * _regime_weight(regime, "buy")
            signals.append({
                "trigger": "볼린저밴드 하단",
                "type": "buy",
                "source": "BB",
                "detail": f"현재가({current_price:,}) ≤ 하단밴드({current_bb_lower:,.0f}), 반등 가능성 (강도: {bb_score:.1f})",
                "strength": round(weighted, 2),
            })
            buy_score += weighted
        elif bb_score < 0:
            abs_score = abs(bb_score)
            weighted = abs_score * _regime_weight(regime, "sell")
            signals.append({
                "trigger": "볼린저밴드 상단",
                "type": "sell",
                "source": "BB",
                "detail": f"현재가({current_price:,}) ≥ 상단밴드({current_bb_upper:,.0f}), 과열 주의 (강도: {abs_score:.1f})",
                "strength": round(weighted, 2),
            })
            sell_score += weighted

    # ── 5. OBV 다이버전스 (신규) ──────────────────
    obv_strength = calc_obv_divergence_strength(closes, obv, lookback=20)
    if obv_strength > 0:
        weighted = obv_strength * obv_divergence_weight * _regime_weight(regime, "buy")
        signals.append({
            "trigger": "OBV 상승 다이버전스",
            "type": "buy",
            "source": "OBV",
            "detail": f"가격 하락 중 OBV 상승 — 매집 가능성 (강도: {obv_strength:.1f})",
            "strength": round(weighted, 2),
        })
        buy_score += weighted

    # OBV 약세 다이버전스 (bearish)
    bearish_div = calc_obv_bearish_divergence_strength(closes, obv, lookback=20)
    if bearish_div > 0:
        weighted = bearish_div * obv_divergence_weight * _regime_weight(regime, "sell")
        signals.append({
            "trigger": "OBV 약세 다이버전스",
            "type": "sell",
            "source": "OBV",
            "detail": f"가격 상승 중 거래량 감소 (강도: {bearish_div:.2f})",
            "strength": round(weighted, 2),
        })
        sell_score += weighted

    # ── 6. Stochastic RSI (신규) ──────────────────
    if current_stoch_k is not None:
        if current_stoch_k <= stoch_rsi_oversold:
            # 연속 점수: 20=0.5, 10=0.75, 0=1.0
            raw = 0.5 + 0.5 * (stoch_rsi_oversold - current_stoch_k) / stoch_rsi_oversold
            stoch_weighted = min(1.0, raw) * _regime_weight(regime, "buy")
            # RSI가 같은 방향으로 이미 fire했으면 중복 부풀림 방지 (0.5배 할인)
            if rsi_fired_buy:
                stoch_weighted *= 0.7
            signals.append({
                "trigger": "StochRSI 과매도",
                "type": "buy",
                "source": "STOCH_RSI",
                "detail": f"StochRSI K={current_stoch_k:.1f} (기준: {stoch_rsi_oversold:.0f} 이하)",
                "strength": round(stoch_weighted, 2),
            })
            buy_score += stoch_weighted
        elif current_stoch_k >= stoch_rsi_overbought:
            raw = 0.5 + 0.5 * (current_stoch_k - stoch_rsi_overbought) / (100 - stoch_rsi_overbought)
            stoch_weighted = min(1.0, raw) * _regime_weight(regime, "sell")
            # RSI가 같은 방향으로 이미 fire했으면 중복 부풀림 방지 (0.5배 할인)
            if rsi_fired_sell:
                stoch_weighted *= 0.7
            signals.append({
                "trigger": "StochRSI 과매수",
                "type": "sell",
                "source": "STOCH_RSI",
                "detail": f"StochRSI K={current_stoch_k:.1f} (기준: {stoch_rsi_overbought:.0f} 이상)",
                "strength": round(stoch_weighted, 2),
            })
            sell_score += stoch_weighted

    # ── 7. VIX 공포지수 ──────────────────────────
    if vix_value is not None:
        result["indicators"]["vix"] = vix_value
        if vix_value >= vix_extreme_fear:
            vix_weighted = 1.0 * _regime_weight(regime, "buy")
            signals.append({
                "trigger": "VIX 공포",
                "type": "buy",
                "source": "VIX",
                "detail": f"시장 공포지수 {vix_value:.1f} - 극단적 공포 구간, 역발상 매수 기회",
                "strength": round(vix_weighted, 2),
            })
            buy_score += vix_weighted
        elif vix_value >= vix_fear:
            vix_weighted = 0.7 * _regime_weight(regime, "buy")
            signals.append({
                "trigger": "VIX 주의",
                "type": "buy",
                "source": "VIX",
                "detail": f"시장 공포지수 {vix_value:.1f} - 공포 구간",
                "strength": round(vix_weighted, 2),
            })
            buy_score += vix_weighted
        elif vix_value <= vix_extreme_greed:
            vix_weighted = 1.0 * _regime_weight(regime, "sell")
            signals.append({
                "trigger": "VIX 과열",
                "type": "sell",
                "source": "VIX",
                "detail": f"시장 공포지수 {vix_value:.1f} - 극단적 낙관, 과열 경고",
                "strength": round(vix_weighted, 2),
            })
            sell_score += vix_weighted

    # ── 8. 매크로 시그널 (유가, 환율, 금리) ──────────
    if macro_data:
        macro_max = float(settings.get("macro_signal_max_score", MACRO_SIGNAL_MAX_SCORE))
        macro_buy = 0.0
        macro_sell = 0.0

        for key, mdata in macro_data.items():
            if not isinstance(mdata, dict):
                continue
            change_pct = mdata.get("change_pct", 0)
            threshold = mdata.get("threshold_pct", 5.0)
            name_str = mdata.get("name", key)

            if abs(change_pct) < threshold * 0.5:
                continue  # 임계치의 50% 미만이면 무시

            # 변동 강도 (0.0~1.0): 임계치의 50%에서 0.0, 100%에서 1.0
            intensity = min(1.0, (abs(change_pct) - threshold * 0.5) / (threshold * 0.5))

            # 섹터 연관성 확인 (현재 종목의 섹터)
            stock_sector = settings.get("sector_map", {}).get(ticker, "")

            # 이벤트 판단 규칙 및 섹터 임팩트
            event_rules = settings.get("macro_event_rules", {}).get(key, {})
            sector_impact = settings.get("macro_sector_impact", {})

            if change_pct > 0 and event_rules.get("surge_pct") and change_pct >= event_rules["surge_pct"] * 0.5:
                event = event_rules.get("surge_event")
                if event and event in sector_impact:
                    impact = sector_impact[event]
                    if stock_sector in impact.get("buy", []):
                        score = intensity * 0.5
                        macro_buy += score
                        signals.append({
                            "trigger": f"매크로 수혜 ({name_str})",
                            "type": "buy",
                            "source": "MACRO",
                            "detail": f"{name_str} {change_pct:+.1f}% → {stock_sector} 수혜",
                            "strength": round(score, 2),
                        })
                    elif stock_sector in impact.get("sell", []):
                        score = intensity * 0.5
                        macro_sell += score
                        signals.append({
                            "trigger": f"매크로 리스크 ({name_str})",
                            "type": "sell",
                            "source": "MACRO",
                            "detail": f"{name_str} {change_pct:+.1f}% → {stock_sector} 부정적",
                            "strength": round(score, 2),
                        })

            elif change_pct < 0 and event_rules.get("crash_pct") and change_pct <= event_rules["crash_pct"] * 0.5:
                event = event_rules.get("crash_event")
                if event and event in sector_impact:
                    impact = sector_impact[event]
                    if stock_sector in impact.get("buy", []):
                        score = intensity * 0.5
                        macro_buy += score
                        signals.append({
                            "trigger": f"매크로 수혜 ({name_str})",
                            "type": "buy",
                            "source": "MACRO",
                            "detail": f"{name_str} {change_pct:+.1f}% → {stock_sector} 수혜",
                            "strength": round(score, 2),
                        })
                    elif stock_sector in impact.get("sell", []):
                        score = intensity * 0.5
                        macro_sell += score
                        signals.append({
                            "trigger": f"매크로 리스크 ({name_str})",
                            "type": "sell",
                            "source": "MACRO",
                            "detail": f"{name_str} {change_pct:+.1f}% → {stock_sector} 부정적",
                            "strength": round(score, 2),
                        })

        # cap 적용
        macro_buy = min(macro_buy, macro_max)
        macro_sell = min(macro_sell, macro_max)
        buy_score += macro_buy
        sell_score += macro_sell

        # 매크로 데이터를 indicators에 저장
        result["indicators"]["macro"] = {
            k: {"price": v.get("price"), "change_pct": v.get("change_pct")}
            for k, v in macro_data.items() if isinstance(v, dict)
        }

    # ── 9. 외인/기관 매매동향 (OR 분리) ────────────
    if investor_df is not None and len(investor_df) >= investor_consec_days:
        frgn = investor_df["외인순매수"]
        inst = investor_df["기관순매수"]

        foreign_consec = _count_consecutive(frgn)
        institutional_consec = _count_consecutive(inst)

        recent = investor_df.tail(investor_consec_days)
        foreign_net = int(recent["외인순매수"].sum())
        institutional_net = int(recent["기관순매수"].sum())

        result["investor"] = {
            "foreign_net": foreign_net,
            "institutional_net": institutional_net,
            "foreign_consec_days": foreign_consec,
            "institutional_consec_days": institutional_consec,
        }

        recent_frgn = recent["외인순매수"]
        recent_inst = recent["기관순매수"]

        # 외인 개별 (0.75점)
        if (recent_frgn > 0).all():
            weighted = 0.75 * _regime_weight(regime, "buy")
            signals.append({
                "trigger": "외인 연속 매수",
                "type": "buy",
                "source": "FOREIGN",
                "detail": f"외국인 {investor_consec_days}일 연속 순매수 ({foreign_net:+,}주)",
                "strength": round(weighted, 2),
            })
            buy_score += weighted
        elif (recent_frgn < 0).all():
            weighted = 0.75 * _regime_weight(regime, "sell")
            signals.append({
                "trigger": "외인 연속 매도",
                "type": "sell",
                "source": "FOREIGN",
                "detail": f"외국인 {investor_consec_days}일 연속 순매도 ({foreign_net:+,}주)",
                "strength": round(weighted, 2),
            })
            sell_score += weighted

        # 기관 개별 (0.75점)
        if (recent_inst > 0).all():
            weighted = 0.75 * _regime_weight(regime, "buy")
            signals.append({
                "trigger": "기관 연속 매수",
                "type": "buy",
                "source": "INSTITUTIONAL",
                "detail": f"기관 {investor_consec_days}일 연속 순매수 ({institutional_net:+,}주)",
                "strength": round(weighted, 2),
            })
            buy_score += weighted
        elif (recent_inst < 0).all():
            weighted = 0.75 * _regime_weight(regime, "sell")
            signals.append({
                "trigger": "기관 연속 매도",
                "type": "sell",
                "source": "INSTITUTIONAL",
                "detail": f"기관 {investor_consec_days}일 연속 순매도 ({institutional_net:+,}주)",
                "strength": round(weighted, 2),
            })
            sell_score += weighted

    result["signals"] = signals
    result["buy_score"] = round(buy_score, 2)
    result["sell_score"] = round(sell_score, 2)

    # ── 합류 점수 계산 (방향별 가중 합산) ──────────
    if buy_score > 0 and sell_score > 0 and abs(buy_score - sell_score) < confluence_mixed_tolerance:
        # 혼재 상태: net_score 사용 (이전: score=0으로 소멸)
        result["confluence_score"] = round(abs(buy_score - sell_score), 1)
        result["confluence_direction"] = "buy" if buy_score > sell_score else ("sell" if sell_score > buy_score else "neutral")
        result["confluence_mixed"] = True  # 혼재 플래그 (정보용)
    else:
        result["confluence_score"] = round(max(buy_score, sell_score), 1)
        result["confluence_direction"] = "buy" if buy_score > sell_score else ("sell" if sell_score > buy_score else "neutral")
        result["confluence_mixed"] = False

    # 신호 강도 분류 (가중 점수 기반)
    net_score = buy_score - sell_score
    if net_score >= signal_strength_strong_buy:
        result["signal_strength"] = "strong_buy"
    elif net_score >= signal_strength_buy:
        result["signal_strength"] = "buy"
    elif net_score <= signal_strength_strong_sell:
        result["signal_strength"] = "strong_sell"
    elif net_score <= signal_strength_sell:
        result["signal_strength"] = "sell"
    else:
        result["signal_strength"] = "neutral"

    return result


def analyze(df: pd.DataFrame, name: str, investor_df: Optional[pd.DataFrame] = None) -> List[str]:
    """기존 호환용: 시그널 메시지 문자열 리스트를 반환한다."""
    data = analyze_detailed(df, "", name, investor_df=investor_df)
    messages = []
    for sig in data["signals"]:
        signal_type = "매수" if sig["type"] == "buy" else "매도"
        messages.append(f"[{sig['trigger']}] {name} - {sig['detail']}")
    return messages


def generate_signals(
    df: pd.DataFrame,
    ticker: str,
    name: str,
    short_ma: int = SHORT_MA,
    long_ma: int = LONG_MA,
    rsi_period: int = RSI_PERIOD,
    rsi_oversold: int = RSI_OVERSOLD,
    rsi_overbought: int = RSI_OVERBOUGHT,
) -> List[Signal]:
    """전체 DataFrame을 순회하며 각 날짜에서의 시그널을 Signal 객체 리스트로 반환한다."""
    if len(df) < long_ma:
        return []

    closes = df["종가"]

    short_ma_series = calc_moving_average(closes, short_ma)
    long_ma_series = calc_moving_average(closes, long_ma)
    rsi = calc_rsi(closes, rsi_period)
    macd_line, signal_line, _ = calc_macd(closes)

    result = []  # type: List[Signal]

    for i in range(long_ma, len(df)):
        row_date = df.index[i].date() if hasattr(df.index[i], 'date') else df.index[i]
        price = float(closes.iloc[i])

        prev_short = short_ma_series.iloc[i - 1]
        prev_long = long_ma_series.iloc[i - 1]
        curr_short = short_ma_series.iloc[i]
        curr_long = long_ma_series.iloc[i]

        if prev_short <= prev_long and curr_short > curr_long:
            result.append(Signal(
                date=row_date, ticker=ticker, name=name,
                signal_type=SignalType.BUY, source="MA_CROSS", strength=0.7,
                description=f"골든크로스: 단기({short_ma}일)이 장기({long_ma}일) 이동평균을 상향 돌파",
                price=price,
            ))
        elif prev_short >= prev_long and curr_short < curr_long:
            result.append(Signal(
                date=row_date, ticker=ticker, name=name,
                signal_type=SignalType.SELL, source="MA_CROSS", strength=0.7,
                description=f"데드크로스: 단기({short_ma}일)이 장기({long_ma}일) 이동평균을 하향 돌파",
                price=price,
            ))

        curr_rsi = rsi.iloc[i]
        if not pd.isna(curr_rsi):
            if curr_rsi <= rsi_oversold:
                result.append(Signal(
                    date=row_date, ticker=ticker, name=name,
                    signal_type=SignalType.BUY, source="RSI",
                    strength=min(1.0, (rsi_oversold - curr_rsi) / rsi_oversold + 0.5),
                    description=f"RSI 과매도: {curr_rsi:.1f} (기준: {rsi_oversold} 이하)",
                    price=price,
                ))
            elif curr_rsi >= rsi_overbought:
                result.append(Signal(
                    date=row_date, ticker=ticker, name=name,
                    signal_type=SignalType.SELL, source="RSI",
                    strength=min(1.0, (curr_rsi - rsi_overbought) / (100 - rsi_overbought) + 0.5),
                    description=f"RSI 과매수: {curr_rsi:.1f} (기준: {rsi_overbought} 이상)",
                    price=price,
                ))

        prev_macd = macd_line.iloc[i - 1]
        prev_signal = signal_line.iloc[i - 1]
        curr_macd = macd_line.iloc[i]
        curr_signal = signal_line.iloc[i]

        if not (pd.isna(prev_macd) or pd.isna(curr_macd)):
            if prev_macd <= prev_signal and curr_macd > curr_signal:
                result.append(Signal(
                    date=row_date, ticker=ticker, name=name,
                    signal_type=SignalType.BUY, source="MACD", strength=0.6,
                    description="MACD 라인이 시그널 라인을 상향 돌파",
                    price=price,
                ))
            elif prev_macd >= prev_signal and curr_macd < curr_signal:
                result.append(Signal(
                    date=row_date, ticker=ticker, name=name,
                    signal_type=SignalType.SELL, source="MACD", strength=0.6,
                    description="MACD 라인이 시그널 라인을 하향 돌파",
                    price=price,
                ))

    return result
