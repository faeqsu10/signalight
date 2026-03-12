"""미국 주식 시그널 분석 모듈 — analyze_detailed 래핑.

유니버스 후보 종목들의 기술적 지표와 VIX/매크로 데이터를 분석한다.
수급 데이터(외인/기관)는 미국 주식에 적용되지 않으므로 제외.
"""

import logging
from typing import Dict, List, Optional

from autonomous.us.config import US_AUTO_CONFIG
from config import MACRO_EVENT_RULES, MACRO_SECTOR_IMPACT, MACRO_SIGNAL_MAX_SCORE
from data.us_fetcher import fetch_us_stock_data
from data.fetcher import fetch_vix
from data.macro_fetcher import fetch_all_macro_prices
from signals.strategy import analyze_detailed

logger = logging.getLogger("signalight.us")


class USStockAnalyzer:
    """미국 종목 분석기 — 기존 analyze_detailed를 래핑."""

    def __init__(self):
        self._vix_cache = None  # type: Optional[float]
        self._macro_cache = None  # type: Optional[Dict]
        self._strategy_settings = {
            "short_ma": US_AUTO_CONFIG.indicator_short_ma,
            "long_ma": US_AUTO_CONFIG.indicator_long_ma,
            "rsi_period": US_AUTO_CONFIG.indicator_rsi_period,
            "rsi_oversold": US_AUTO_CONFIG.indicator_rsi_oversold,
            "rsi_overbought": US_AUTO_CONFIG.indicator_rsi_overbought,
            # StochRSI — US config에 없으면 KR 기본값 사용
            "stoch_rsi_period": 14,
            "stoch_rsi_smooth_k": 3,
            "stoch_rsi_smooth_d": 3,
            "stoch_rsi_oversold": 20.0,
            "stoch_rsi_overbought": 80.0,
            # 수급 연속일 (미국은 수급 없으므로 실질적으로 미사용)
            "investor_consec_days": 3,
            # VIX 임계값
            "vix_extreme_fear": US_AUTO_CONFIG.vix_extreme_fear,
            "vix_fear": US_AUTO_CONFIG.vix_fear,
            "vix_extreme_greed": US_AUTO_CONFIG.vix_extreme_greed,
            # 매크로 시그널 설정
            "macro_signal_max_score": MACRO_SIGNAL_MAX_SCORE,
            "macro_event_rules": dict(MACRO_EVENT_RULES),
            "macro_sector_impact": dict(MACRO_SECTOR_IMPACT),
            "sector_map": US_AUTO_CONFIG.sector_map,
            # 진입 임계값
            "entry_threshold_uptrend": US_AUTO_CONFIG.initial_entry_threshold_uptrend,
            "entry_threshold_sideways": US_AUTO_CONFIG.initial_entry_threshold_sideways,
            "entry_threshold_downtrend": US_AUTO_CONFIG.initial_entry_threshold_downtrend,
            "min_volume_ratio": US_AUTO_CONFIG.initial_min_volume_ratio,
        }

    def analyze_candidates(self, candidates: List[Dict]) -> List[Dict]:
        """후보 종목들을 상세 분석한다.

        Args:
            candidates: [{ticker, name, price, composite_score, scan_signals, ...}, ...]

        Returns:
            분석 완료된 stock_data 리스트
        """
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

        logger.info("US 분석 완료: %d/%d종목", len(analyzed), len(candidates))
        return analyzed

    def analyze_holdings(self, holdings: List[Dict]) -> List[Dict]:
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
        self, symbol: str, name: str, vix_value: Optional[float]
    ) -> Optional[Dict]:
        """단일 종목 상세 분석."""
        df = fetch_us_stock_data(symbol, days=US_AUTO_CONFIG.data_period_days)
        if df is None or df.empty or len(df) < 50:
            logger.warning("%s(%s): 데이터 부족 또는 없음", name, symbol)
            return None

        macro_data = self._fetch_macro()

        data = analyze_detailed(
            df, symbol, name,
            investor_df=None,   # 미국 주식: 수급 데이터 없음
            vix_value=vix_value,
            strategy_settings=self._strategy_settings,
            macro_data=macro_data,
        )
        return data

    def _fetch_vix(self) -> Optional[float]:
        """VIX 조회 (사이클 단위 캐시)."""
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
        """글로벌 매크로 데이터 조회 (사이클 단위 캐시)."""
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
