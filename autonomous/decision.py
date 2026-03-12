"""매매 결정 엔진 — TradeRule 래핑 + 포트폴리오 제약.

TradeRule의 should_buy/should_sell을 래핑하면서
포트폴리오 레벨 제약(주간 손실, 섹터 집중, 최대 포지션)을 추가한다.
"""

import logging
from typing import List, Dict, Optional

from trading.rules import TradeRule
from trading.position_tracker import PositionTracker
from autonomous.config import AUTO_CONFIG
from autonomous.state import PipelineState

logger = logging.getLogger("signalight.auto")


class DecisionEngine:
    """매매 결정 엔진."""

    def __init__(
        self,
        trade_rule: TradeRule = None,
        position_tracker: PositionTracker = None,
        state: PipelineState = None,
    ):
        self.trade_rule = trade_rule or TradeRule()
        self.tracker = position_tracker or PositionTracker()
        self.state = state or PipelineState()

    def make_buy_decisions(
        self, analyzed_stocks: List[Dict]
    ) -> List[Dict]:
        """매수 결정을 생성한다.

        1. 포트폴리오 레벨 제약 체크 (서킷 브레이커, 포지션 한도)
        2. 종목별 should_buy() 호출
        3. confluence_score 순 정렬
        4. 상위 N개만 선택

        Args:
            analyzed_stocks: 분석 완료된 stock_data 리스트

        Returns:
            매수 추천 리스트 [{stock_data, recommendation}, ...]
        """
        # 포트폴리오 레벨 체크
        if not self._check_portfolio_constraints():
            logger.info("포트폴리오 제약으로 매수 불가")
            return []

        all_open = self.tracker.get_all_open()
        current_count = len(all_open)

        # 남은 슬롯
        available_slots = AUTO_CONFIG.max_positions - current_count
        if available_slots <= 0:
            logger.info("최대 포지션 수 도달 (%d/%d)",
                        current_count, AUTO_CONFIG.max_positions)
            return []

        # 종목별 매수 판단
        buy_candidates = []
        for data in analyzed_stocks:
            ticker = data.get("ticker", "")

            # 이미 보유 중이면 스킵
            if self.tracker.get_position(ticker):
                continue

            # 섹터 집중도 체크
            if not self._check_sector_limit(data, all_open):
                continue

            rec = self.trade_rule.should_buy(data, all_open)
            if rec.get("recommend"):
                # 포지션 크기를 AUTO_CONFIG 기준으로 조정
                rec["weight_pct"] = min(
                    rec.get("weight_pct", AUTO_CONFIG.target_weight_pct),
                    AUTO_CONFIG.target_weight_pct,
                )
                buy_candidates.append({
                    "stock_data": data,
                    "recommendation": rec,
                    "confluence_score": data.get("confluence_score", 0),
                    "scan_signals": data.get("scan_signals", []),
                })

        # confluence_score 내림차순 정렬
        buy_candidates.sort(
            key=lambda x: x["confluence_score"], reverse=True
        )

        # 남은 슬롯만큼만 선택
        selected = buy_candidates[:available_slots]

        if selected:
            logger.info(
                "매수 결정: %d종목 (후보 %d → 선택 %d)",
                len(selected), len(buy_candidates), len(selected),
            )
            for item in selected:
                sd = item["stock_data"]
                logger.info(
                    "  %s(%s) score=%.1f weight=%.1f%%",
                    sd["name"], sd["ticker"],
                    item["confluence_score"],
                    item["recommendation"]["weight_pct"],
                )

        return selected

    def make_sell_decisions(
        self, analyzed_holdings: List[Dict]
    ) -> List[Dict]:
        """매도 결정을 생성한다.

        보유 종목별로 should_sell()을 호출한다.

        Args:
            analyzed_holdings: 보유 종목 분석 데이터

        Returns:
            매도 추천 리스트 [{stock_data, recommendation, position}, ...]
        """
        sell_decisions = []

        for data in analyzed_holdings:
            ticker = data.get("ticker", "")
            position = self.tracker.get_position(ticker)
            if position is None:
                continue

            # 최고가 갱신
            current_price = data.get("price", 0)
            if current_price > 0:
                self.tracker.update_highest_close(ticker, current_price)
                position = self.tracker.get_position(ticker)

            rec = self.trade_rule.should_sell(data, position)
            if rec.get("recommend"):
                sell_decisions.append({
                    "stock_data": data,
                    "recommendation": rec,
                    "position": position,
                })
                logger.info(
                    "매도 결정: %s(%s) action=%s sell_pct=%d%%",
                    data["name"], ticker,
                    rec.get("action", ""),
                    rec.get("sell_pct", 0),
                )

        return sell_decisions

    def _check_portfolio_constraints(self) -> bool:
        """포트폴리오 레벨 제약을 체크한다."""
        # 서킷 브레이커 확인
        cb = self.state.is_circuit_breaker_active()
        if cb:
            logger.warning(
                "서킷 브레이커 활성: %s (재개: %s)",
                cb["trigger_type"], cb.get("resume_date", "미정"),
            )
            return False

        # 주간 손실 한도
        weekly = self.state.get_weekly_pnl()
        if weekly["total_pnl"] < 0:
            # 에퀴티 스냅샷에서 총 자산 추정
            equity_history = self.state.get_equity_history(days=7)
            if equity_history:
                total_equity = equity_history[-1]["total_equity"]
                if total_equity > 0:
                    weekly_loss_pct = abs(weekly["total_pnl"]) / total_equity * 100
                    if weekly_loss_pct >= AUTO_CONFIG.weekly_loss_limit_pct:
                        logger.warning(
                            "주간 손실 한도 초과: %.1f%% >= %.1f%%",
                            weekly_loss_pct, AUTO_CONFIG.weekly_loss_limit_pct,
                        )
                        return False

        # 연속 패배 한도
        consec = self.state.get_consecutive_losses()
        if consec >= AUTO_CONFIG.max_consecutive_losses:
            logger.warning(
                "연속 패배 한도: %d연패 >= %d",
                consec, AUTO_CONFIG.max_consecutive_losses,
            )
            return False

        # 최대 낙폭 킬스위치
        max_dd = self.state.get_max_drawdown()
        if max_dd >= AUTO_CONFIG.max_drawdown_pct:
            logger.warning(
                "최대 낙폭 킬스위치: %.1f%% >= %.1f%%",
                max_dd, AUTO_CONFIG.max_drawdown_pct,
            )
            return False

        return True

    def _check_sector_limit(
        self, stock_data: Dict, open_positions: List[Dict]
    ) -> bool:
        """섹터 집중도를 체크한다."""
        ticker = stock_data.get("ticker", "")
        sector_map = AUTO_CONFIG.sector_map
        sector = sector_map.get(ticker, "기타")

        # 같은 섹터의 현재 보유 수
        sector_count = sum(
            1 for pos in open_positions
            if sector_map.get(pos["ticker"], "기타") == sector
        )

        if sector_count >= AUTO_CONFIG.max_sector_positions:
            logger.debug(
                "%s: 섹터 한도 초과 (%s: %d/%d)",
                ticker, sector, sector_count, AUTO_CONFIG.max_sector_positions,
            )
            return False

        return True
