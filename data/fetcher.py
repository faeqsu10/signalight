from datetime import datetime, timedelta
from typing import Optional
from pykrx import stock
import pandas as pd
import urllib.request
import json

from config import DATA_PERIOD_DAYS


def fetch_stock_data(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """종목코드로 OHLCV 데이터를 가져온다.

    Args:
        ticker: 종목코드 (예: "005930")
        start_date: 조회 시작일 "YYYYMMDD" 형식. None이면 오늘 기준 DATA_PERIOD_DAYS일 전.
        end_date: 조회 종료일 "YYYYMMDD" 형식. None이면 오늘.
    """
    if end_date is None:
        end_dt = datetime.today()
        end_str = end_dt.strftime("%Y%m%d")
    else:
        end_str = end_date

    if start_date is None:
        end_dt = datetime.strptime(end_str, "%Y%m%d")
        start_str = (end_dt - timedelta(days=DATA_PERIOD_DAYS)).strftime("%Y%m%d")
    else:
        start_str = start_date

    df = stock.get_market_ohlcv(start_str, end_str, ticker)

    if df.empty:
        return df

    df.index.name = "날짜"
    return df


def fetch_vix(days: int = 120) -> pd.Series:
    """Yahoo Finance에서 VIX(공포지수) 데이터를 가져온다. 종가 Series 반환."""
    now = int(datetime.now().timestamp())
    from_ts = int((datetime.now() - timedelta(days=days)).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
        f"?period1={from_ts}&period2={now}&interval=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    closes = result["indicators"]["quote"][0]["close"]

    dates = pd.to_datetime(timestamps, unit="s").normalize()
    series = pd.Series(closes, index=dates, name="VIX", dtype=float)
    series = series.dropna()
    return series
