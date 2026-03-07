from datetime import datetime, timedelta
from typing import Optional
from pykrx import stock
import pandas as pd

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
