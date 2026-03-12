"""미국 주식 시장 스캐너 — Yahoo Finance 기반."""
import logging
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import SHORT_MA, LONG_MA, RSI_PERIOD, RSI_OVERSOLD, DATA_PERIOD_DAYS, US_WATCH_LIST
from data.us_fetcher import fetch_us_stock_data
from signals.indicators import calc_moving_average, calc_rsi

logger = logging.getLogger("signalight.us")


class USMarketScanner:
    """미국 주식 시장을 스캔하여 조건에 맞는 종목을 찾는다."""

    def __init__(self, extra_symbols: Optional[List[Tuple[str, str]]] = None):
        """
        Args:
            extra_symbols: 추가 종목 리스트 [(symbol, name), ...]
                           기본값은 config.US_WATCH_LIST
        """
        self.symbols: List[Tuple[str, str]] = list(US_WATCH_LIST)
        if extra_symbols:
            seen = {s for s, _ in self.symbols}
            for sym, name in extra_symbols:
                if sym not in seen:
                    self.symbols.append((sym, name))
                    seen.add(sym)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_ohlcv(self, symbol: str, days: Optional[int] = None) -> Optional[pd.DataFrame]:
        """종목의 OHLCV DataFrame을 반환한다. 실패 시 None.

        최소 LONG_MA + 5 행이 없으면 None을 반환한다.
        """
        if days is None:
            days = DATA_PERIOD_DAYS
        df = fetch_us_stock_data(symbol, days=days)
        if df is None or df.empty or len(df) < LONG_MA + 5:
            return None
        return df

    # ------------------------------------------------------------------
    # Public scan methods
    # ------------------------------------------------------------------

    def scan_golden_cross(self, limit: int = 50) -> List[Dict]:
        """골든크로스 발생 종목 스캔.

        단기 MA(SHORT_MA)가 장기 MA(LONG_MA)를 상향 돌파한 종목을 찾는다.

        Returns:
            list of {ticker, name, price, short_ma, long_ma, volume_ratio, signal}
        """
        results = []  # type: List[Dict]
        logger.info("US Scanner: 골든크로스 스캔 시작 (%d 종목)", len(self.symbols))

        for symbol, name in self.symbols:
            try:
                df = self._fetch_ohlcv(symbol)
                if df is None:
                    continue

                closes = df["종가"]
                volumes = df["거래량"]

                short_ma = calc_moving_average(closes, SHORT_MA)
                long_ma = calc_moving_average(closes, LONG_MA)

                short_valid = short_ma.dropna()
                long_valid = long_ma.dropna()
                if len(short_valid) < 2 or len(long_valid) < 2:
                    continue

                if (short_ma.iloc[-1] > long_ma.iloc[-1]
                        and short_ma.iloc[-2] <= long_ma.iloc[-2]):
                    recent_vols = volumes.iloc[-20:]
                    avg_vol = recent_vols.mean() if len(recent_vols) > 0 else 0
                    vol_ratio = float(volumes.iloc[-1] / avg_vol) if avg_vol > 0 else 0

                    results.append({
                        "ticker": symbol,
                        "name": name,
                        "price": round(float(closes.iloc[-1]), 2),
                        "short_ma": round(float(short_ma.iloc[-1]), 2),
                        "long_ma": round(float(long_ma.iloc[-1]), 2),
                        "volume_ratio": round(vol_ratio, 2),
                        "signal": "golden_cross",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                logger.debug("US Scanner: %s 골든크로스 처리 실패", symbol, exc_info=True)

        logger.info("US Scanner: 골든크로스 %d개 종목 발견", len(results))
        return results

    def scan_near_golden_cross(
        self, limit: int = 50, proximity_ratio: float = 0.98
    ) -> List[Dict]:
        """근접 골든크로스 종목 스캔.

        단기 MA / 장기 MA 비율이 proximity_ratio 이상 1.0 미만인 종목을 찾는다.

        Returns:
            list of {ticker, name, price, ma_ratio, signal}
        """
        results = []  # type: List[Dict]
        logger.info("US Scanner: 근접 골든크로스 스캔 시작 (%d 종목)", len(self.symbols))

        for symbol, name in self.symbols:
            try:
                df = self._fetch_ohlcv(symbol)
                if df is None:
                    continue

                closes = df["종가"]
                short_ma = calc_moving_average(closes, SHORT_MA)
                long_ma = calc_moving_average(closes, LONG_MA)

                short_valid = short_ma.dropna()
                long_valid = long_ma.dropna()
                if len(short_valid) < 1 or len(long_valid) < 1:
                    continue

                s = float(short_ma.iloc[-1])
                l = float(long_ma.iloc[-1])
                if l <= 0:
                    continue

                ratio = s / l
                if proximity_ratio <= ratio < 1.0:
                    results.append({
                        "ticker": symbol,
                        "name": name,
                        "price": round(float(closes.iloc[-1]), 2),
                        "ma_ratio": round(ratio, 4),
                        "signal": "near_golden_cross",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                logger.debug("US Scanner: %s 근접 골든크로스 처리 실패", symbol, exc_info=True)

        logger.info("US Scanner: 근접 골든크로스 %d개 종목 발견", len(results))
        return results

    def scan_rsi_oversold(
        self, limit: int = 50, oversold_threshold: float = RSI_OVERSOLD
    ) -> List[Dict]:
        """RSI 과매도 종목 스캔.

        RSI < oversold_threshold 인 종목을 찾는다.

        Returns:
            list of {ticker, name, price, rsi, signal}
        """
        results = []  # type: List[Dict]
        logger.info("US Scanner: RSI 과매도 스캔 시작 (%d 종목)", len(self.symbols))

        for symbol, name in self.symbols:
            try:
                df = self._fetch_ohlcv(symbol)
                if df is None:
                    continue

                closes = df["종가"]
                rsi_series = calc_rsi(closes, RSI_PERIOD)
                last_rsi = rsi_series.dropna()

                if len(last_rsi) == 0:
                    continue

                rsi_val = float(last_rsi.iloc[-1])
                if rsi_val < oversold_threshold:
                    results.append({
                        "ticker": symbol,
                        "name": name,
                        "price": round(float(closes.iloc[-1]), 2),
                        "rsi": round(rsi_val, 1),
                        "signal": "rsi_oversold",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                logger.debug("US Scanner: %s RSI 처리 실패", symbol, exc_info=True)

        logger.info("US Scanner: RSI 과매도 %d개 종목 발견", len(results))
        return results

    def scan_volume_surge(self, min_ratio: float = 1.5, limit: int = 50) -> List[Dict]:
        """거래량 급증 종목 스캔.

        당일 거래량이 직전 20일 평균 대비 min_ratio 이상인 종목을 찾는다.

        Returns:
            list of {ticker, name, price, volume, avg_volume, volume_ratio, signal}
        """
        results = []  # type: List[Dict]
        logger.info("US Scanner: 거래량 급증 스캔 시작 (%d 종목)", len(self.symbols))

        for symbol, name in self.symbols:
            try:
                df = self._fetch_ohlcv(symbol, days=60)
                if df is None or len(df) < 5:
                    continue

                volumes = df["거래량"]
                closes = df["종가"]

                if len(volumes) < 2:
                    continue

                prev_vols = volumes.iloc[-21:-1] if len(volumes) > 20 else volumes.iloc[:-1]
                avg_vol = prev_vols.mean() if len(prev_vols) > 0 else 0

                if avg_vol <= 0:
                    continue

                ratio = float(volumes.iloc[-1] / avg_vol)
                if ratio >= min_ratio:
                    results.append({
                        "ticker": symbol,
                        "name": name,
                        "price": round(float(closes.iloc[-1]), 2),
                        "volume": int(volumes.iloc[-1]),
                        "avg_volume": int(avg_vol),
                        "volume_ratio": round(ratio, 2),
                        "signal": "volume_surge",
                    })

                    if len(results) >= limit:
                        break
            except Exception:
                logger.debug("US Scanner: %s 거래량 처리 실패", symbol, exc_info=True)

        logger.info("US Scanner: 거래량 급증 %d개 종목 발견", len(results))
        return results
