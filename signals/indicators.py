import pandas as pd


def calc_moving_average(closes: pd.Series, period: int) -> pd.Series:
    """단순 이동평균선 계산."""
    return closes.rolling(window=period).mean()


def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI(상대강도지수) 계산."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 계산. (macd_line, signal_line, histogram) 반환."""
    ema_fast = closes.ewm(span=fast).mean()
    ema_slow = closes.ewm(span=slow).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calc_volume_ratio(volumes: pd.Series, period: int = 20) -> float:
    """현재 거래량 / N일 평균 거래량 비율을 반환한다."""
    if len(volumes) < period:
        return 1.0
    avg = volumes.iloc[-period:].mean()
    if avg == 0:
        return 1.0
    return float(volumes.iloc[-1] / avg)
