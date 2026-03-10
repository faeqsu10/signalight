"""시그널 분석기 — analyze_detailed 래핑.

유니버스 후보 종목들의 기술적 지표, 수급, 뉴스 감성을 분석한다.
"""

import logging
from typing import List, Dict, Optional

from data.fetcher import fetch_stock_data, fetch_vix
from data.investor import fetch_investor_trading
from signals.strategy import analyze_detailed

logger = logging.getLogger("signalight.auto")


class StockAnalyzer:
    """종목 분석기 — 기존 analyze_detailed를 래핑."""

    def __init__(self):
        self._vix_cache = None  # type: Optional[float]

    def analyze_candidates(
        self, candidates: List[Dict]
    ) -> List[Dict]:
        """후보 종목들을 상세 분석한다.

        Args:
            candidates: [{ticker, name, price, ...}, ...]

        Returns:
            분석 완료된 stock_data 리스트
        """
        # VIX 1회 조회
        vix_value = self._fetch_vix()

        analyzed = []
        for candidate in candidates:
            ticker = candidate["ticker"]
            name = candidate["name"]

            try:
                data = self._analyze_single(ticker, name, vix_value)
                if data:
                    # 스캔 정보 보존
                    data["composite_score"] = candidate.get("composite_score", 0)
                    data["scan_signals"] = candidate.get("scan_signals", [])
                    analyzed.append(data)
            except Exception as e:
                logger.warning("%s(%s) 분석 실패: %s", name, ticker, e)

        logger.info("분석 완료: %d/%d종목", len(analyzed), len(candidates))
        return analyzed

    def analyze_holdings(
        self, holdings: List[Dict]
    ) -> List[Dict]:
        """보유 종목들을 분석한다 (매도 판단용).

        Args:
            holdings: [{ticker, name, ...}, ...]

        Returns:
            분석 완료된 stock_data 리스트
        """
        vix_value = self._fetch_vix()

        analyzed = []
        for holding in holdings:
            ticker = holding["ticker"]
            name = holding["name"]

            try:
                data = self._analyze_single(ticker, name, vix_value)
                if data:
                    analyzed.append(data)
            except Exception as e:
                logger.warning("%s(%s) 보유종목 분석 실패: %s", name, ticker, e)

        return analyzed

    def _analyze_single(
        self, ticker: str, name: str, vix_value: Optional[float]
    ) -> Optional[Dict]:
        """단일 종목 상세 분석."""
        df = fetch_stock_data(ticker)
        if df.empty:
            logger.warning("%s(%s): 데이터 없음", name, ticker)
            return None

        investor_df = None
        try:
            investor_df = fetch_investor_trading(ticker)
        except Exception as e:
            logger.debug("%s(%s) 수급 데이터 실패: %s", name, ticker, e)

        data = analyze_detailed(
            df, ticker, name,
            investor_df=investor_df,
            vix_value=vix_value,
        )
        return data

    def _fetch_vix(self) -> Optional[float]:
        """VIX 조회 (캐시)."""
        if self._vix_cache is not None:
            return self._vix_cache

        try:
            vix_series = fetch_vix()
            if not vix_series.empty:
                self._vix_cache = float(vix_series.iloc[-1])
                logger.info("VIX: %.1f", self._vix_cache)
                return self._vix_cache
        except Exception as e:
            logger.warning("VIX 조회 실패: %s", e)

        return None

    def clear_cache(self) -> None:
        """VIX 캐시를 초기화한다."""
        self._vix_cache = None
