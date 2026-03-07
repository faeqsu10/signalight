from typing import List, Optional

import pandas as pd

from signals.indicators import calc_moving_average, calc_rsi, calc_macd
from config import (
    SHORT_MA, LONG_MA, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    VIX_EXTREME_FEAR, VIX_FEAR, VIX_EXTREME_GREED, INVESTOR_CONSEC_DAYS,
)
from data.fetcher import fetch_vix
from backtest import Signal, SignalType


def analyze(df: pd.DataFrame, name: str, investor_df: Optional[pd.DataFrame] = None) -> List[str]:
    """주어진 OHLCV 데이터를 분석하여 시그널 메시지 리스트를 반환한다.

    Args:
        df: OHLCV DataFrame (종가 컬럼 필수)
        name: 종목명
        investor_df: 외인/기관 순매수 DataFrame (columns: 외인순매수, 기관순매수). None이면 스킵.
    """
    if len(df) < LONG_MA:
        return []

    closes = df["종가"]
    signals = []

    # 1. 이동평균선 크로스
    short_ma = calc_moving_average(closes, SHORT_MA)
    long_ma = calc_moving_average(closes, LONG_MA)

    # 오늘과 어제의 크로스 비교
    if short_ma.iloc[-2] <= long_ma.iloc[-2] and short_ma.iloc[-1] > long_ma.iloc[-1]:
        signals.append(f"[골든크로스] {name} - 단기({SHORT_MA}일)이 장기({LONG_MA}일) 이동평균을 상향 돌파! 매수 시그널")
    elif short_ma.iloc[-2] >= long_ma.iloc[-2] and short_ma.iloc[-1] < long_ma.iloc[-1]:
        signals.append(f"[데드크로스] {name} - 단기({SHORT_MA}일)이 장기({LONG_MA}일) 이동평균을 하향 돌파! 매도 시그널")

    # 2. RSI
    rsi = calc_rsi(closes, RSI_PERIOD)
    current_rsi = rsi.iloc[-1]

    if current_rsi <= RSI_OVERSOLD:
        signals.append(f"[RSI 과매도] {name} - RSI {current_rsi:.1f} (기준: {RSI_OVERSOLD} 이하) 매수 시그널")
    elif current_rsi >= RSI_OVERBOUGHT:
        signals.append(f"[RSI 과매수] {name} - RSI {current_rsi:.1f} (기준: {RSI_OVERBOUGHT} 이상) 매도 시그널")

    # 3. MACD
    macd_line, signal_line, histogram = calc_macd(closes)

    if macd_line.iloc[-2] <= signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]:
        signals.append(f"[MACD 매수] {name} - MACD 라인이 시그널 라인을 상향 돌파!")
    elif macd_line.iloc[-2] >= signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1]:
        signals.append(f"[MACD 매도] {name} - MACD 라인이 시그널 라인을 하향 돌파!")

    # 4. VIX 공포지수
    try:
        vix_series = fetch_vix(30)
        if not vix_series.empty:
            vix = vix_series.iloc[-1]
            if vix >= VIX_EXTREME_FEAR:
                signals.append(f"[VIX 공포] 시장 공포지수 {vix:.1f} - 극단적 공포 구간! 역발상 매수 기회")
            elif vix >= VIX_FEAR:
                signals.append(f"[VIX 주의] 시장 공포지수 {vix:.1f} - 공포 구간, 주의 필요")
            elif vix <= VIX_EXTREME_GREED:
                signals.append(f"[VIX 과열] 시장 공포지수 {vix:.1f} - 극단적 낙관 구간, 과열 경고")
    except Exception:
        pass

    # 5. 외인/기관 매매동향
    if investor_df is not None and len(investor_df) >= INVESTOR_CONSEC_DAYS:
        recent = investor_df.tail(INVESTOR_CONSEC_DAYS)
        frgn = recent["외인순매수"]
        inst = recent["기관순매수"]

        # 외인+기관 동시 순매수 N일 연속
        if (frgn > 0).all() and (inst > 0).all():
            signals.append(
                f"[외인/기관 매수] {name} - 외인+기관 {INVESTOR_CONSEC_DAYS}일 연속 순매수 중! 매수 시그널"
            )
        # 외인+기관 동시 순매도 N일 연속
        elif (frgn < 0).all() and (inst < 0).all():
            signals.append(
                f"[외인/기관 매도] {name} - 외인+기관 {INVESTOR_CONSEC_DAYS}일 연속 순매도 중! 매도 시그널"
            )

    return signals


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

    # 지표 시리즈 계산 (rolling/ewm은 해당 시점까지의 데이터만 사용)
    short_ma_series = calc_moving_average(closes, short_ma)
    long_ma_series = calc_moving_average(closes, long_ma)
    rsi = calc_rsi(closes, rsi_period)
    macd_line, signal_line, _ = calc_macd(closes)

    result = []  # type: List[Signal]

    # long_ma 이후부터 순회 (이전 행과 비교해야 하므로 long_ma 인덱스부터)
    for i in range(long_ma, len(df)):
        row_date = df.index[i].date() if hasattr(df.index[i], 'date') else df.index[i]
        price = float(closes.iloc[i])

        # --- MA 골든크로스 / 데드크로스 ---
        prev_short = short_ma_series.iloc[i - 1]
        prev_long = long_ma_series.iloc[i - 1]
        curr_short = short_ma_series.iloc[i]
        curr_long = long_ma_series.iloc[i]

        if prev_short <= prev_long and curr_short > curr_long:
            result.append(Signal(
                date=row_date,
                ticker=ticker,
                name=name,
                signal_type=SignalType.BUY,
                source="MA_CROSS",
                strength=0.7,
                description=f"골든크로스: 단기({short_ma}일)이 장기({long_ma}일) 이동평균을 상향 돌파",
                price=price,
            ))
        elif prev_short >= prev_long and curr_short < curr_long:
            result.append(Signal(
                date=row_date,
                ticker=ticker,
                name=name,
                signal_type=SignalType.SELL,
                source="MA_CROSS",
                strength=0.7,
                description=f"데드크로스: 단기({short_ma}일)이 장기({long_ma}일) 이동평균을 하향 돌파",
                price=price,
            ))

        # --- RSI 과매도 / 과매수 ---
        curr_rsi = rsi.iloc[i]
        if not pd.isna(curr_rsi):
            if curr_rsi <= rsi_oversold:
                result.append(Signal(
                    date=row_date,
                    ticker=ticker,
                    name=name,
                    signal_type=SignalType.BUY,
                    source="RSI",
                    strength=min(1.0, (rsi_oversold - curr_rsi) / rsi_oversold + 0.5),
                    description=f"RSI 과매도: {curr_rsi:.1f} (기준: {rsi_oversold} 이하)",
                    price=price,
                ))
            elif curr_rsi >= rsi_overbought:
                result.append(Signal(
                    date=row_date,
                    ticker=ticker,
                    name=name,
                    signal_type=SignalType.SELL,
                    source="RSI",
                    strength=min(1.0, (curr_rsi - rsi_overbought) / (100 - rsi_overbought) + 0.5),
                    description=f"RSI 과매수: {curr_rsi:.1f} (기준: {rsi_overbought} 이상)",
                    price=price,
                ))

        # --- MACD 크로스 ---
        prev_macd = macd_line.iloc[i - 1]
        prev_signal = signal_line.iloc[i - 1]
        curr_macd = macd_line.iloc[i]
        curr_signal = signal_line.iloc[i]

        if not (pd.isna(prev_macd) or pd.isna(curr_macd)):
            if prev_macd <= prev_signal and curr_macd > curr_signal:
                result.append(Signal(
                    date=row_date,
                    ticker=ticker,
                    name=name,
                    signal_type=SignalType.BUY,
                    source="MACD",
                    strength=0.6,
                    description="MACD 라인이 시그널 라인을 상향 돌파",
                    price=price,
                ))
            elif prev_macd >= prev_signal and curr_macd < curr_signal:
                result.append(Signal(
                    date=row_date,
                    ticker=ticker,
                    name=name,
                    signal_type=SignalType.SELL,
                    source="MACD",
                    strength=0.6,
                    description="MACD 라인이 시그널 라인을 하향 돌파",
                    price=price,
                ))

    return result
