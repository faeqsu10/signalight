"""미국 주식 OHLCV 데이터 수집 — Yahoo Finance v8 chart API."""
import json
import logging
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger("signalight.us")

# 4시간 인메모리 캐시
_cache: Dict[str, object] = {}  # key -> (DataFrame, expires_at)
_CACHE_TTL = 14400  # 4시간 (초)


def fetch_us_stock_data(symbol: str, days: int = 120) -> Optional[pd.DataFrame]:
    """Yahoo Finance v8 chart API로 미국 주식 OHLCV 데이터를 가져온다.

    Args:
        symbol: 미국 주식 심볼 (예: "AAPL", "NVDA")
        days: 조회 기간 (일). 기본 120일.

    Returns:
        DataFrame (DatetimeIndex, 컬럼: 시가, 고가, 저가, 종가, 거래량)
        실패 시 None.
    """
    cache_key = f"{symbol}:{days}"
    now_ts = datetime.now().timestamp()

    # 캐시 확인
    if cache_key in _cache:
        cached_df, expires_at = _cache[cache_key]  # type: ignore[misc]
        if now_ts < expires_at:
            logger.debug("US fetcher cache hit: %s", symbol)
            return cached_df

    try:
        period2 = int(now_ts)
        period1 = int((datetime.now() - timedelta(days=days)).timestamp())
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?period1={period1}&period2={period2}&interval=1d"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]

        dates = pd.to_datetime(timestamps, unit="s").normalize()
        df = pd.DataFrame(
            {
                "시가": quote["open"],
                "고가": quote["high"],
                "저가": quote["low"],
                "종가": quote["close"],
                "거래량": quote["volume"],
            },
            index=dates,
        )
        df.index.name = "날짜"
        df = df.dropna(subset=["종가"])

        _cache[cache_key] = (df, now_ts + _CACHE_TTL)
        logger.debug("US fetcher: %s %d rows", symbol, len(df))
        return df

    except Exception as e:
        logger.warning("US fetcher: %s 조회 실패: %s", symbol, e)
        return None
