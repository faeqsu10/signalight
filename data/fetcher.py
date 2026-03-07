from datetime import datetime, timedelta
from pykrx import stock
import pandas as pd

from config import DATA_PERIOD_DAYS


def fetch_stock_data(ticker: str) -> pd.DataFrame:
    """종목코드로 최근 N일간의 OHLCV 데이터를 가져온다."""
    end = datetime.today()
    start = end - timedelta(days=DATA_PERIOD_DAYS)

    df = stock.get_market_ohlcv(
        start.strftime("%Y%m%d"),
        end.strftime("%Y%m%d"),
        ticker,
    )

    if df.empty:
        return df

    df.index.name = "날짜"
    return df
