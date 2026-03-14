"""시그널 분석기 — analyze_detailed 래핑.

유니버스 후보 종목들의 기술적 지표, 수급, 뉴스 감성을 분석한다.
"""

import logging
from typing import List, Dict, Optional

from config import MACRO_EVENT_RULES, MACRO_SECTOR_IMPACT, MACRO_SIGNAL_MAX_SCORE
from data.fetcher import fetch_stock_data, fetch_vix
from data.investor import fetch_investor_trading
from data.macro_fetcher import fetch_all_macro_prices
from signals.strategy import analyze_detailed

logger = logging.getLogger("signalight.auto")


class StockAnalyzer:
    """종목 분석기 — 기존 analyze_detailed를 래핑."""

    def __init__(self, config=None):
        from autonomous.config import AUTO_CONFIG
        cfg = config or AUTO_CONFIG
        self._vix_cache = None  # type: Optional[float]
        self._macro_cache = None  # type: Optional[Dict]
        self._strategy_settings = {
            "short_ma": cfg.indicator_short_ma,
            "long_ma": cfg.indicator_long_ma,
            "rsi_period": cfg.indicator_rsi_period,
            "rsi_oversold": cfg.indicator_rsi_oversold,
            "rsi_overbought": cfg.indicator_rsi_overbought,
            "stoch_rsi_period": cfg.indicator_stoch_rsi_period,
            "stoch_rsi_smooth_k": cfg.indicator_stoch_rsi_smooth_k,
            "stoch_rsi_smooth_d": cfg.indicator_stoch_rsi_smooth_d,
            "stoch_rsi_oversold": cfg.indicator_stoch_rsi_oversold,
            "stoch_rsi_overbought": cfg.indicator_stoch_rsi_overbought,
            "investor_consec_days": cfg.investor_consec_days,
            "vix_extreme_fear": cfg.vix_extreme_fear,
            "vix_fear": cfg.vix_fear,
            "vix_extreme_greed": cfg.vix_extreme_greed,
            # 매크로 시그널 설정 (config.py에서 가져옴)
            "macro_signal_max_score": MACRO_SIGNAL_MAX_SCORE,
            "macro_event_rules": dict(MACRO_EVENT_RULES),
            "macro_sector_impact": dict(MACRO_SECTOR_IMPACT),
            "sector_map": cfg.sector_map,
        }
        if cfg.enabled_indicators is not None:
            self._strategy_settings["enabled_indicators"] = list(cfg.enabled_indicators)

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

        # 매크로 데이터 (4시간 내부 캐시 + 사이클 단위 캐시)
        macro_data = self._fetch_macro()

        data = analyze_detailed(
            df, ticker, name,
            investor_df=investor_df,
            vix_value=vix_value,
            strategy_settings=self._strategy_settings,
            macro_data=macro_data,
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

    def _fetch_macro(self) -> Optional[Dict]:
        """글로벌 매크로 데이터 조회 (사이클 단위 캐시).

        fetch_all_macro_prices()는 내부 4시간 캐시를 가지며,
        여기서는 사이클 단위로 추가 캐싱하여 중복 호출을 방지한다.
        """
        if self._macro_cache is not None:
            return self._macro_cache

        try:
            macro_data = fetch_all_macro_prices()
            if macro_data:
                self._macro_cache = macro_data
                indicators = ", ".join(
                    f"{k}={v.get('price', 'N/A')}" for k, v in macro_data.items()
                )
                logger.info("매크로 데이터: %s", indicators)
                return self._macro_cache
        except Exception as e:
            logger.warning("매크로 데이터 조회 실패: %s", e)

        return None

    def get_macro_data(self) -> Optional[Dict]:
        """캐시된 매크로 데이터를 반환한다 (없으면 None)."""
        return self._macro_cache

    def clear_cache(self) -> None:
        """VIX + 매크로 캐시를 초기화한다."""
        self._vix_cache = None
        self._macro_cache = None
