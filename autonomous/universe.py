"""유니버스 선정 — KOSPI200 복합 스캔 + 유동성 필터.

MarketScanner의 3종 스캔(골든크로스/RSI과매도/거래량급증) 결과를
복합 점수로 합산하고 유동성 필터를 적용한다.
"""

import logging
from typing import List, Dict, Set
from datetime import datetime, timedelta

from pykrx import stock

from scanner.market_scanner import MarketScanner
from autonomous.config import AUTO_CONFIG

logger = logging.getLogger("signalight.auto")


class UniverseSelector:
    """KOSPI200 기반 유니버스 선정기."""

    # 기본 스캔 가중치
    DEFAULT_WEIGHTS = {
        "golden_cross": 3,
        "rsi_oversold": 2,
        "volume_surge": 1,
        "near_golden_cross": 1.5,
    }

    def __init__(self, scan_weights: Dict[str, float] = None):
        scanner_settings = {
            "data_period_days": AUTO_CONFIG.data_period_days,
            "short_ma": AUTO_CONFIG.indicator_short_ma,
            "long_ma": AUTO_CONFIG.indicator_long_ma,
            "rsi_period": AUTO_CONFIG.indicator_rsi_period,
        }
        self.scanner = MarketScanner(
            market=AUTO_CONFIG.universe_market,
            settings=scanner_settings,
        )
        self.scan_weights = scan_weights or dict(self.DEFAULT_WEIGHTS)

    def select_universe(
        self,
        held_tickers: Set[str] = None,
        max_candidates: int = None,
    ) -> List[Dict]:
        """복합 스캔으로 매매 후보 유니버스를 선정한다.

        1. 골든크로스/RSI과매도/거래량급증 3종 스캔
        2. 결과 합산 + 복합 점수 부여
        3. 유동성 필터 (거래대금 기준)
        4. 보유 종목 제외
        5. 점수순 정렬 후 상위 N개 반환

        Args:
            held_tickers: 이미 보유 중인 종목코드 집합 (제외용)
            max_candidates: 최대 후보 수 (기본: AUTO_CONFIG.universe_max_candidates)

        Returns:
            [{ticker, name, price, composite_score, scan_signals, ...}, ...]
        """
        if held_tickers is None:
            held_tickers = set()
        if max_candidates is None:
            max_candidates = AUTO_CONFIG.universe_max_candidates

        logger.info("유니버스 스캔 시작 (시장: %s)", AUTO_CONFIG.universe_market)

        # 3종 스캔 실행 (설정 기반)
        scan_limit = AUTO_CONFIG.universe_scan_limit

        golden_cross = []
        rsi_oversold = []
        volume_surge = []
        near_golden_cross = []

        try:
            golden_cross = self.scanner.scan_golden_cross(limit=scan_limit)
            logger.info("골든크로스: %d종목", len(golden_cross))
        except Exception as e:
            logger.warning("골든크로스 스캔 실패: %s", e)

        try:
            rsi_oversold = self.scanner.scan_rsi_oversold(
                limit=scan_limit,
                oversold_threshold=AUTO_CONFIG.scan_rsi_oversold_threshold,
            )
            logger.info("RSI 과매도: %d종목", len(rsi_oversold))
        except Exception as e:
            logger.warning("RSI 과매도 스캔 실패: %s", e)

        try:
            volume_surge = self.scanner.scan_volume_surge(
                min_ratio=AUTO_CONFIG.scan_volume_surge_ratio,
                limit=scan_limit,
            )
            logger.info("거래량 급증: %d종목", len(volume_surge))
        except Exception as e:
            logger.warning("거래량 급증 스캔 실패: %s", e)

        try:
            near_golden_cross = self.scanner.scan_near_golden_cross(
                limit=scan_limit,
                proximity_ratio=AUTO_CONFIG.scan_near_golden_cross_proximity,
            )
            logger.info("근접 골든크로스: %d종목", len(near_golden_cross))
        except Exception as e:
            logger.warning("근접 골든크로스 스캔 실패: %s", e)

        # 복합 점수 합산 (중복 종목은 점수 누적)
        candidates = {}  # type: Dict[str, Dict]

        for item in golden_cross:
            ticker = item["ticker"]
            if ticker not in candidates:
                candidates[ticker] = {
                    "ticker": ticker,
                    "name": item["name"],
                    "price": item["price"],
                    "composite_score": 0,
                    "scan_signals": [],
                }
            candidates[ticker]["composite_score"] += self.scan_weights.get("golden_cross", 3)
            candidates[ticker]["scan_signals"].append("golden_cross")

        for item in rsi_oversold:
            ticker = item["ticker"]
            if ticker not in candidates:
                candidates[ticker] = {
                    "ticker": ticker,
                    "name": item["name"],
                    "price": item["price"],
                    "composite_score": 0,
                    "scan_signals": [],
                }
            candidates[ticker]["composite_score"] += self.scan_weights.get("rsi_oversold", 2)
            candidates[ticker]["scan_signals"].append("rsi_oversold")
            candidates[ticker]["rsi"] = item.get("rsi")

        for item in volume_surge:
            ticker = item["ticker"]
            if ticker not in candidates:
                candidates[ticker] = {
                    "ticker": ticker,
                    "name": item["name"],
                    "price": item["price"],
                    "composite_score": 0,
                    "scan_signals": [],
                }
            candidates[ticker]["composite_score"] += self.scan_weights.get("volume_surge", 1)
            candidates[ticker]["scan_signals"].append("volume_surge")
            candidates[ticker]["volume_ratio"] = item.get("volume_ratio")

        for item in near_golden_cross:
            ticker = item["ticker"]
            if ticker not in candidates:
                candidates[ticker] = {
                    "ticker": ticker,
                    "name": item["name"],
                    "price": item["price"],
                    "composite_score": 0,
                    "scan_signals": [],
                }
            candidates[ticker]["composite_score"] += self.scan_weights.get("near_golden_cross", 1.5)
            candidates[ticker]["scan_signals"].append("near_golden_cross")
            candidates[ticker]["ma_ratio"] = item.get("ma_ratio")

        # 보유 종목 제외
        for ticker in held_tickers:
            candidates.pop(ticker, None)

        # 유동성 필터 (거래대금 기준)
        filtered = []
        for ticker, info in candidates.items():
            if self._check_liquidity(ticker):
                filtered.append(info)

        # 복합 점수 내림차순 정렬
        filtered.sort(key=lambda x: x["composite_score"], reverse=True)

        # 적응형 완화: 후보 부족 시 재스캔
        min_candidates = AUTO_CONFIG.universe_min_candidates
        max_relaxation_rounds = AUTO_CONFIG.universe_max_relaxation_rounds

        if len(filtered) < min_candidates:
            current_rsi = AUTO_CONFIG.scan_rsi_oversold_threshold
            current_vol = AUTO_CONFIG.scan_volume_surge_ratio

            for round_num in range(1, max_relaxation_rounds + 1):
                relaxed_rsi = current_rsi + (AUTO_CONFIG.universe_rsi_relaxation_step * round_num)
                relaxed_vol = current_vol - (AUTO_CONFIG.universe_volume_relaxation_step * round_num)
                relaxed_vol = max(relaxed_vol, 0.5)  # 하한선

                logger.info(
                    "적응형 완화 라운드 %d: RSI=%.0f, 거래량=%.1f",
                    round_num, relaxed_rsi, relaxed_vol,
                )

                new_rsi = []
                new_vol = []

                try:
                    new_rsi = self.scanner.scan_rsi_oversold(
                        limit=scan_limit,
                        oversold_threshold=relaxed_rsi,
                    )
                    logger.info("완화 RSI 과매도: %d종목", len(new_rsi))
                except Exception as e:
                    logger.warning("완화 RSI 스캔 실패: %s", e)

                try:
                    new_vol = self.scanner.scan_volume_surge(
                        min_ratio=relaxed_vol,
                        limit=scan_limit,
                    )
                    logger.info("완화 거래량 급증: %d종목", len(new_vol))
                except Exception as e:
                    logger.warning("완화 거래량 스캔 실패: %s", e)

                # 중복 없이 candidates에 병합
                for item in new_rsi:
                    ticker = item["ticker"]
                    if ticker not in candidates and ticker not in held_tickers:
                        candidates[ticker] = {
                            "ticker": ticker,
                            "name": item["name"],
                            "price": item["price"],
                            "composite_score": self.scan_weights.get("rsi_oversold", 2),
                            "scan_signals": ["rsi_oversold"],
                            "rsi": item.get("rsi"),
                        }

                for item in new_vol:
                    ticker = item["ticker"]
                    if ticker not in candidates and ticker not in held_tickers:
                        candidates[ticker] = {
                            "ticker": ticker,
                            "name": item["name"],
                            "price": item["price"],
                            "composite_score": self.scan_weights.get("volume_surge", 1),
                            "scan_signals": ["volume_surge"],
                            "volume_ratio": item.get("volume_ratio"),
                        }

                # 유동성 필터 재적용
                filtered = []
                for ticker, info in candidates.items():
                    if self._check_liquidity(ticker):
                        filtered.append(info)
                filtered.sort(key=lambda x: x["composite_score"], reverse=True)

                if len(filtered) >= min_candidates:
                    break

        result = filtered[:max_candidates]
        logger.info(
            "유니버스 선정 완료: %d종목 (후보 %d → 필터 %d → 최종 %d)",
            len(result), len(candidates), len(filtered), len(result),
        )
        return result

    def _check_liquidity(self, ticker: str) -> bool:
        """거래대금 기준 유동성 필터.

        최근 20일 평균 거래대금이 기준 이상인지 확인한다.
        """
        try:
            end = datetime.today()
            start = end - timedelta(days=40)
            df = stock.get_market_ohlcv_by_date(
                start.strftime("%Y%m%d"),
                end.strftime("%Y%m%d"),
                ticker,
            )
            if df.empty or len(df) < 5:
                return False

            # 거래대금 = 종가 * 거래량 (근사치)
            recent = df.tail(20)
            trading_values = recent["종가"] * recent["거래량"]
            avg_value = trading_values.mean()

            return avg_value >= AUTO_CONFIG.min_trading_value
        except Exception:
            return False
