from typing import Dict, List, Optional

import pandas as pd

from signals.indicators import calc_moving_average, calc_rsi, calc_macd, calc_volume_ratio, calc_atr, calc_bollinger_bands, calc_obv
from config import (
    SHORT_MA, LONG_MA, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    VIX_EXTREME_FEAR, VIX_FEAR, VIX_EXTREME_GREED, INVESTOR_CONSEC_DAYS,
)

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


def analyze_detailed(
    df: pd.DataFrame,
    ticker: str,
    name: str,
    investor_df: Optional[pd.DataFrame] = None,
    vix_value: Optional[float] = None,
) -> Dict:
    """주어진 OHLCV 데이터를 분석하여 구조화된 시그널 데이터를 반환한다.

    Returns:
        dict with keys: name, ticker, price, change_pct, signals, indicators,
                        investor, confluence_score, total_indicators
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
        "total_indicators": 7,  # MA, RSI, MACD, BB, OBV, VIX, 수급
    }

    if len(df) < LONG_MA:
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

    # 지표 계산
    short_ma = calc_moving_average(closes, SHORT_MA)
    long_ma = calc_moving_average(closes, LONG_MA)
    rsi = calc_rsi(closes, RSI_PERIOD)
    macd_line, signal_line, histogram = calc_macd(closes)
    volume_ratio = calc_volume_ratio(volumes)
    atr = calc_atr(df["고가"], df["저가"], closes, period=14)

    current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
    current_histogram = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
    current_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None

    # ATR 기반 손절가 (현재가 - 2 * ATR)
    atr_stop_loss = int(current_price - 2 * current_atr) if current_atr else None

    # 볼린저밴드
    bb_upper, bb_middle, bb_lower = calc_bollinger_bands(closes, 20, 2)
    current_bb_upper = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None
    current_bb_lower = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None

    # OBV
    obv = calc_obv(closes, volumes)
    current_obv = float(obv.iloc[-1])

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
    }

    # 1. 이동평균선 크로스
    vol_note = ""
    if volume_ratio >= 1.5:
        vol_note = " [거래량 확인 ↑]"
    elif volume_ratio < 0.5:
        vol_note = " [거래량 부족 주의]"

    if short_ma.iloc[-2] <= long_ma.iloc[-2] and short_ma.iloc[-1] > long_ma.iloc[-1]:
        signals.append({
            "trigger": "골든크로스",
            "type": "buy",
            "source": "MA_CROSS",
            "detail": f"{SHORT_MA}일선({short_ma.iloc[-1]:,.0f}) > {LONG_MA}일선({long_ma.iloc[-1]:,.0f}) 상향 돌파{vol_note}",
        })
        buy_score += 1.0
    elif short_ma.iloc[-2] >= long_ma.iloc[-2] and short_ma.iloc[-1] < long_ma.iloc[-1]:
        signals.append({
            "trigger": "데드크로스",
            "type": "sell",
            "source": "MA_CROSS",
            "detail": f"{SHORT_MA}일선({short_ma.iloc[-1]:,.0f}) < {LONG_MA}일선({long_ma.iloc[-1]:,.0f}) 하향 돌파{vol_note}",
        })
        sell_score += 1.0

    # 2. RSI
    if current_rsi is not None:
        if current_rsi <= RSI_OVERSOLD:
            signals.append({
                "trigger": "RSI 과매도",
                "type": "buy",
                "source": "RSI",
                "detail": f"RSI {current_rsi:.1f} (기준: {RSI_OVERSOLD} 이하)",
            })
            buy_score += 1.0
        elif current_rsi >= RSI_OVERBOUGHT:
            signals.append({
                "trigger": "RSI 과매수",
                "type": "sell",
                "source": "RSI",
                "detail": f"RSI {current_rsi:.1f} (기준: {RSI_OVERBOUGHT} 이상)",
            })
            sell_score += 1.0

    # 3. MACD
    if not pd.isna(macd_line.iloc[-2]) and not pd.isna(macd_line.iloc[-1]):
        if macd_line.iloc[-2] <= signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]:
            signals.append({
                "trigger": "MACD 매수",
                "type": "buy",
                "source": "MACD",
                "detail": "MACD 라인이 시그널 라인을 상향 돌파",
            })
            buy_score += 1.0
        elif macd_line.iloc[-2] >= signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]:
            signals.append({
                "trigger": "MACD 매도",
                "type": "sell",
                "source": "MACD",
                "detail": "MACD 라인이 시그널 라인을 하향 돌파",
            })
            sell_score += 1.0

    # 4. 볼린저밴드
    if current_bb_lower is not None and current_bb_upper is not None:
        if current_price <= current_bb_lower:
            signals.append({
                "trigger": "볼린저밴드 하단 이탈",
                "type": "buy",
                "source": "BB",
                "detail": f"현재가({current_price:,}) <= 하단밴드({current_bb_lower:,.0f}), 반등 가능성",
            })
            buy_score += 1.0
        elif current_price >= current_bb_upper:
            signals.append({
                "trigger": "볼린저밴드 상단 이탈",
                "type": "sell",
                "source": "BB",
                "detail": f"현재가({current_price:,}) >= 상단밴드({current_bb_upper:,.0f}), 과열 주의",
            })
            sell_score += 1.0

    # 5. VIX 공포지수 (외부에서 전달받음 — 종목마다 중복 호출 방지)
    if vix_value is not None:
        result["indicators"]["vix"] = vix_value
        if vix_value >= VIX_EXTREME_FEAR:
            signals.append({
                "trigger": "VIX 공포",
                "type": "buy",
                "source": "VIX",
                "detail": f"시장 공포지수 {vix_value:.1f} - 극단적 공포 구간, 역발상 매수 기회",
            })
            buy_score += 1.0
        elif vix_value >= VIX_FEAR:
            signals.append({
                "trigger": "VIX 주의",
                "type": "buy",
                "source": "VIX",
                "detail": f"시장 공포지수 {vix_value:.1f} - 공포 구간",
            })
            buy_score += 1.0
        elif vix_value <= VIX_EXTREME_GREED:
            signals.append({
                "trigger": "VIX 과열",
                "type": "sell",
                "source": "VIX",
                "detail": f"시장 공포지수 {vix_value:.1f} - 극단적 낙관, 과열 경고",
            })
            sell_score += 1.0

    # 5. 외인/기관 매매동향
    if investor_df is not None and len(investor_df) >= INVESTOR_CONSEC_DAYS:
        frgn = investor_df["외인순매수"]
        inst = investor_df["기관순매수"]

        foreign_consec = _count_consecutive(frgn)
        institutional_consec = _count_consecutive(inst)

        # 최근 N일 합산 금액
        recent = investor_df.tail(INVESTOR_CONSEC_DAYS)
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

        if (recent_frgn > 0).all() and (recent_inst > 0).all():
            signals.append({
                "trigger": "외인/기관 동시 매수",
                "type": "buy",
                "source": "INVESTOR",
                "detail": f"외인+기관 {INVESTOR_CONSEC_DAYS}일 연속 순매수",
            })
            buy_score += 1.5  # 수급 시그널 가중치
        elif (recent_frgn < 0).all() and (recent_inst < 0).all():
            signals.append({
                "trigger": "외인/기관 동시 매도",
                "type": "sell",
                "source": "INVESTOR",
                "detail": f"외인+기관 {INVESTOR_CONSEC_DAYS}일 연속 순매도",
            })
            sell_score += 1.5  # 수급 시그널 가중치

    result["signals"] = signals
    if buy_score > 0 and buy_score == sell_score:
        result["confluence_score"] = 0
        result["confluence_direction"] = "mixed"
    else:
        result["confluence_score"] = round(max(buy_score, sell_score), 1)
        result["confluence_direction"] = "buy" if buy_score > sell_score else "sell"

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
