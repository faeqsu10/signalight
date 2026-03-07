from typing import List

import pandas as pd

from signals.indicators import calc_moving_average, calc_rsi, calc_macd
from config import SHORT_MA, LONG_MA, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT


def analyze(df: pd.DataFrame, name: str) -> List[str]:
    """주어진 OHLCV 데이터를 분석하여 시그널 메시지 리스트를 반환한다."""
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

    return signals
