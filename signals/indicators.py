import pandas as pd


def calc_moving_average(closes: pd.Series, period: int) -> pd.Series:
    """단순 이동평균선 계산."""
    return closes.rolling(window=period).mean()


def calc_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI(상대강도지수) 계산 — Wilder's Smoothing 방식."""
    delta = closes.diff().dropna()
    gains = delta.where(delta > 0, 0.0).values
    losses = (-delta.where(delta < 0, 0.0)).values

    rsi = pd.Series([float('nan')] * len(closes), index=closes.index)

    if len(gains) < period:
        return rsi

    # Seed: SMA of first `period` values
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    if avg_loss == 0:
        rsi.iloc[period] = 100.0
    else:
        rsi.iloc[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    # Wilder's smoothing
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi.iloc[i + 1] = 100.0
        else:
            rsi.iloc[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    return rsi


def calc_macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 계산. (macd_line, signal_line, histogram) 반환."""
    ema_fast = closes.ewm(span=fast).mean()
    ema_slow = closes.ewm(span=slow).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calc_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14) -> pd.Series:
    """ATR(Average True Range) 계산 — Wilder's Smoothing 방식."""
    prev_close = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_close).abs()
    tr3 = (lows - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = pd.Series([float('nan')] * len(closes), index=closes.index)

    tr_vals = tr.dropna().values
    if len(tr_vals) < period:
        return atr

    # Seed: SMA of first `period` TR values
    atr_val = sum(tr_vals[:period]) / period
    offset = len(closes) - len(tr_vals)
    atr.iloc[offset + period - 1] = atr_val

    # Wilder's smoothing
    for i in range(period, len(tr_vals)):
        atr_val = (atr_val * (period - 1) + tr_vals[i]) / period
        atr.iloc[offset + i] = atr_val

    return atr


def calc_bollinger_bands(closes: pd.Series, period: int = 20, num_std: int = 2):
    """볼린저밴드 계산. (upper, middle, lower) Series 반환."""
    middle = closes.rolling(window=period).mean()
    std = closes.rolling(window=period).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def calc_obv(closes: pd.Series, volumes: pd.Series) -> pd.Series:
    """OBV(On-Balance Volume) 계산."""
    obv = pd.Series(0.0, index=closes.index)
    for i in range(1, len(closes)):
        if closes.iloc[i] > closes.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] + volumes.iloc[i]
        elif closes.iloc[i] < closes.iloc[i - 1]:
            obv.iloc[i] = obv.iloc[i - 1] - volumes.iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i - 1]
    return obv


def detect_volume_spike(volumes: pd.Series, threshold: float = 3.0, period: int = 20) -> bool:
    """현재 거래량이 평균 대비 threshold배 이상인지 판단 (투매/급등 감지)."""
    if len(volumes) < period + 1:
        return False
    avg = volumes.iloc[-(period + 1):-1].mean()
    if avg == 0:
        return False
    return float(volumes.iloc[-1] / avg) >= threshold


def detect_obv_divergence(closes: pd.Series, obv: pd.Series, lookback: int = 20) -> bool:
    """OBV 상승 다이버전스 감지: 주가는 하락하지만 OBV는 상승하는 패턴.
    최근 lookback 기간 동안 가격 저점이 하락하면서 OBV 저점이 상승하면 True."""
    if len(closes) < lookback or len(obv) < lookback:
        return False

    recent_closes = closes.iloc[-lookback:]
    recent_obv = obv.iloc[-lookback:]

    half = lookback // 2
    first_half_close_min = recent_closes.iloc[:half].min()
    second_half_close_min = recent_closes.iloc[half:].min()
    first_half_obv_min = recent_obv.iloc[:half].min()
    second_half_obv_min = recent_obv.iloc[half:].min()

    # 가격은 더 낮은 저점, OBV는 더 높은 저점 → 상승 다이버전스
    return second_half_close_min < first_half_close_min and second_half_obv_min > first_half_obv_min


def calc_volume_ratio(volumes: pd.Series, period: int = 20) -> float:
    """현재 거래량 / N일 평균 거래량 비율을 반환한다."""
    if len(volumes) < period:
        return 1.0
    avg = volumes.iloc[-period:].mean()
    if avg == 0:
        return 1.0
    return float(volumes.iloc[-1] / avg)
