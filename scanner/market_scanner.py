"""종목 자동 스캐닝 — KRX 전체 종목 중 조건 충족 종목 탐지."""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import pandas as pd
from pykrx import stock

from config import (
    SHORT_MA, LONG_MA, RSI_PERIOD,
    RSI_OVERSOLD, RSI_OVERBOUGHT, DATA_PERIOD_DAYS,
)
from signals.indicators import calc_moving_average, calc_rsi
from scanner.kospi200_tickers import (
    KOSPI200_TICKERS, KOSDAQ_MAJOR_TICKERS, ALL_FALLBACK_TICKERS,
)

logger = logging.getLogger("signalight")


class MarketScanner:
    """KRX 시장 전체를 스캔하여 조건에 맞는 종목을 찾는다."""

    def __init__(self, market: str = "KOSPI"):
        """
        Args:
            market: "KOSPI", "KOSDAQ", or "ALL"
        """
        self.market = market

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_all_tickers(self) -> List[Tuple[str, str]]:
        """시장의 전체 종목 (ticker, name) 리스트를 반환한다.

        pykrx가 정상이면 pykrx를 사용하고,
        실패 시 정적 KOSPI200/KOSDAQ 리스트를 fallback으로 사용한다.
        """
        today = datetime.today().strftime("%Y%m%d")

        if self.market == "ALL":
            markets = ["KOSPI", "KOSDAQ"]
        else:
            markets = [self.market]

        # 1) pykrx 시도
        tickers = []  # type: List[Tuple[str, str]]
        for mkt in markets:
            try:
                ticker_list = stock.get_market_ticker_list(today, market=mkt)
                if ticker_list is not None and len(ticker_list) > 0:
                    for t in ticker_list:
                        name = stock.get_market_ticker_name(t)
                        tickers.append((t, name))
            except Exception as e:
                logger.debug("pykrx ticker_list 실패 (%s): %s", mkt, e)

        if tickers:
            return tickers

        # 2) Fallback: 정적 종목 리스트
        logger.warning(
            "pykrx get_market_ticker_list 실패 — 정적 종목 리스트 사용 (%s)",
            self.market,
        )
        if self.market == "KOSDAQ":
            fallback_codes = KOSDAQ_MAJOR_TICKERS
        elif self.market == "ALL":
            fallback_codes = ALL_FALLBACK_TICKERS
        else:  # KOSPI
            fallback_codes = KOSPI200_TICKERS

        seen = set()  # type: set
        for code in fallback_codes:
            if code in seen:
                continue
            seen.add(code)
            try:
                name = stock.get_market_ticker_name(code)
                if name:
                    tickers.append((code, name))
            except Exception:
                tickers.append((code, code))

        return tickers

    def _fetch_ohlcv(self, ticker: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """종목의 OHLCV DataFrame을 반환한다. 실패 시 None.

        pykrx.stock.get_market_ohlcv_by_date() 사용.
        최소 LONG_MA + 5 행이 없으면 None을 반환한다.
        """
        if days is None:
            days = DATA_PERIOD_DAYS
        end = datetime.today()
        start = end - timedelta(days=days)
        try:
            df = stock.get_market_ohlcv_by_date(
                start.strftime("%Y%m%d"),
                end.strftime("%Y%m%d"),
                ticker,
            )
            if df.empty or len(df) < LONG_MA + 5:
                return None
            return df
        except Exception as e:
            logger.debug("Scanner: %s 데이터 조회 실패: %s", ticker, e)
            return None

    # ------------------------------------------------------------------
    # Public scan methods
    # ------------------------------------------------------------------

    def scan_golden_cross(self, limit: int = 20) -> List[Dict]:
        """골든크로스 발생 종목 스캔.

        단기 MA(SHORT_MA)가 장기 MA(LONG_MA)를 상향 돌파한 종목을 찾는다.

        Returns:
            list of {ticker, name, price, short_ma, long_ma, volume_ratio, signal}
        """
        results = []  # type: List[Dict]
        tickers = self._get_all_tickers()
        logger.info("Scanner: 골든크로스 스캔 시작 (%d 종목)", len(tickers))

        for ticker, name in tickers:
            try:
                df = self._fetch_ohlcv(ticker)
                if df is None:
                    time.sleep(0.1)
                    continue

                closes = df["종가"]
                volumes = df["거래량"]

                short_ma = calc_moving_average(closes, SHORT_MA)
                long_ma = calc_moving_average(closes, LONG_MA)

                # NaN이 아닌 유효 값이 2개 이상 필요
                short_valid = short_ma.dropna()
                long_valid = long_ma.dropna()
                if len(short_valid) < 2 or len(long_valid) < 2:
                    time.sleep(0.1)
                    continue

                # 골든크로스: 오늘 short > long, 어제 short <= long
                if (short_ma.iloc[-1] > long_ma.iloc[-1]
                        and short_ma.iloc[-2] <= long_ma.iloc[-2]):
                    recent_vols = volumes.iloc[-20:]
                    avg_vol = recent_vols.mean() if len(recent_vols) > 0 else 0
                    vol_ratio = (volumes.iloc[-1] / avg_vol) if avg_vol > 0 else 0

                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "price": int(closes.iloc[-1]),
                        "short_ma": round(float(short_ma.iloc[-1]), 1),
                        "long_ma": round(float(long_ma.iloc[-1]), 1),
                        "volume_ratio": round(float(vol_ratio), 2),
                        "signal": "golden_cross",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                pass

            time.sleep(0.1)

        logger.info("Scanner: 골든크로스 %d개 종목 발견", len(results))
        return results

    def scan_rsi_oversold(self, limit: int = 20) -> List[Dict]:
        """RSI 과매도 종목 스캔.

        RSI < RSI_OVERSOLD 인 종목을 찾는다.

        Returns:
            list of {ticker, name, price, rsi, signal}
        """
        results = []  # type: List[Dict]
        tickers = self._get_all_tickers()
        logger.info("Scanner: RSI 과매도 스캔 시작 (%d 종목)", len(tickers))

        for ticker, name in tickers:
            try:
                df = self._fetch_ohlcv(ticker)
                if df is None:
                    time.sleep(0.1)
                    continue

                closes = df["종가"]
                rsi_series = calc_rsi(closes, RSI_PERIOD)
                last_rsi = rsi_series.dropna()

                if len(last_rsi) == 0:
                    time.sleep(0.1)
                    continue

                rsi_val = float(last_rsi.iloc[-1])
                if rsi_val < RSI_OVERSOLD:
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "price": int(closes.iloc[-1]),
                        "rsi": round(rsi_val, 1),
                        "signal": "rsi_oversold",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                pass

            time.sleep(0.1)

        logger.info("Scanner: RSI 과매도 %d개 종목 발견", len(results))
        return results

    def scan_volume_surge(self, min_ratio: float = 3.0, limit: int = 20) -> List[Dict]:
        """거래량 급증 종목 스캔.

        당일 거래량이 20일 평균 대비 min_ratio 이상인 종목을 찾는다.

        Returns:
            list of {ticker, name, price, volume, avg_volume, volume_ratio, signal}
        """
        results = []  # type: List[Dict]
        tickers = self._get_all_tickers()
        logger.info("Scanner: 거래량 급증 스캔 시작 (%d 종목)", len(tickers))

        for ticker, name in tickers:
            try:
                df = self._fetch_ohlcv(ticker, days=60)
                if df is None or len(df) < 5:
                    time.sleep(0.1)
                    continue

                volumes = df["거래량"]
                closes = df["종가"]

                if len(volumes) < 2:
                    time.sleep(0.1)
                    continue

                # 마지막 거래일 제외한 직전 20일 평균
                prev_vols = volumes.iloc[-21:-1] if len(volumes) > 20 else volumes.iloc[:-1]
                avg_vol = prev_vols.mean() if len(prev_vols) > 0 else 0

                if avg_vol <= 0:
                    time.sleep(0.1)
                    continue

                ratio = float(volumes.iloc[-1] / avg_vol)
                if ratio >= min_ratio:
                    results.append({
                        "ticker": ticker,
                        "name": name,
                        "price": int(closes.iloc[-1]),
                        "volume": int(volumes.iloc[-1]),
                        "avg_volume": int(avg_vol),
                        "volume_ratio": round(ratio, 2),
                        "signal": "volume_surge",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                pass

            time.sleep(0.1)

        logger.info("Scanner: 거래량 급증 %d개 종목 발견", len(results))
        return results
