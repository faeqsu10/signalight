"""안전 주문 실행기 — 서킷 브레이커 + 장중 시간 체크 + 킬스위치.

TradeExecutor를 래핑하면서 자율 트레이딩 전용 안전장치를 추가한다.
"""

import logging
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from trading import Order, TradingConfig
from trading.kiwoom_client import KiwoomClient
from trading.position_tracker import PositionTracker
from trading.portfolio import PortfolioManager
from autonomous.config import AUTO_CONFIG
from autonomous.state import PipelineState
from config import DRY_RUN_VIRTUAL_ASSET

logger = logging.getLogger("signalight.auto")


class SafeExecutor:
    """안전장치가 포함된 주문 실행기."""

    def __init__(
        self,
        state: PipelineState = None,
        position_tracker: PositionTracker = None,
    ):
        self.state = state or PipelineState()
        self.tracker = position_tracker or PositionTracker()

        # 키움 클라이언트 (dry_run이면 None)
        trading_config = TradingConfig(
            dry_run=AUTO_CONFIG.dry_run,
            use_mock=AUTO_CONFIG.use_mock,
            daily_loss_limit_pct=AUTO_CONFIG.daily_loss_limit_pct,
            max_single_position_pct=AUTO_CONFIG.max_single_position_pct,
            max_order_amount=AUTO_CONFIG.max_order_amount,
        )

        self.client = None  # type: Optional[KiwoomClient]
        self.portfolio = None  # type: Optional[PortfolioManager]
        if not AUTO_CONFIG.dry_run:
            self.client = KiwoomClient(use_mock=AUTO_CONFIG.use_mock)
            self.portfolio = PortfolioManager(client=self.client)

        self.config = trading_config
        self.daily_orders = []  # type: List[Order]

    # ── 안전장치 체크 ──

    def _check_kill_switch(self) -> bool:
        """킬스위치 파일 존재 여부 확인."""
        if os.path.exists(AUTO_CONFIG.kill_switch_path):
            logger.warning("킬스위치 활성: %s", AUTO_CONFIG.kill_switch_path)
            return False
        return True

    def _check_market_hours(self) -> bool:
        """장중 시간인지 확인한다."""
        now = datetime.now()

        # 주말 체크
        if now.weekday() >= 5:
            return False

        open_time = now.replace(
            hour=AUTO_CONFIG.market_open_hour,
            minute=AUTO_CONFIG.market_open_minute,
            second=0,
        )
        close_time = now.replace(
            hour=AUTO_CONFIG.market_close_hour,
            minute=AUTO_CONFIG.market_close_minute,
            second=0,
        )

        return open_time <= now <= close_time

    def _check_all_safety(self, is_sell: bool = False) -> bool:
        """모든 안전장치를 체크한다.

        Args:
            is_sell: 매도인 경우 일부 체크 완화

        Returns:
            True = 주문 가능
        """
        if not self._check_kill_switch():
            return False

        # 장중 시간 체크 (매수/매도 모두 — KRX는 장외 주문 불가)
        if not self._check_market_hours():
            return False

        # 매도는 장중이면 항상 허용 (손절은 보호 우선)
        if is_sell:
            return True

        # 서킷 브레이커
        cb = self.state.is_circuit_breaker_active()
        if cb:
            logger.warning("서킷 브레이커 활성: %s", cb["trigger_type"])
            return False

        return True

    # ── 매수 실행 ──

    def execute_buy(
        self, stock_data: Dict, recommendation: Dict
    ) -> Optional[Order]:
        """매수 주문을 실행한다.

        Args:
            stock_data: 분석된 종목 데이터
            recommendation: TradeRule.should_buy() 결과

        Returns:
            Order 객체 또는 None
        """
        if not self._check_all_safety(is_sell=False):
            return None

        ticker = stock_data.get("ticker", "")
        name = stock_data.get("name", ticker)
        price = stock_data.get("price", 0)
        weight_pct = recommendation.get("weight_pct", AUTO_CONFIG.target_weight_pct)

        if price <= 0:
            logger.warning("매수 실패: %s 가격 0", ticker)
            return None

        # 수량 계산
        quantity = self._calculate_quantity(ticker, price, weight_pct)
        if quantity <= 0:
            logger.warning("매수 실패: %s 수량 0", ticker)
            return None

        order_amount = price * quantity
        if order_amount > AUTO_CONFIG.max_order_amount:
            quantity = AUTO_CONFIG.max_order_amount // price
            if quantity <= 0:
                return None

        # 주문 실행
        order = self._place_order(
            side="buy", ticker=ticker, name=name,
            quantity=quantity, price=price,
            reason=f"confluence={stock_data.get('confluence_score', 0):.1f}",
            confluence_score=stock_data.get("confluence_score", 0),
            regime=stock_data.get("market_regime", ""),
        )

        if order and order.status in ("filled", "simulated"):
            # 가상 포지션 생성
            indicators = stock_data.get("indicators", {})
            self.tracker.open_position(
                ticker, name,
                entry_price=price,
                entry_atr=indicators.get("atr", 0),
                regime=stock_data.get("market_regime", "sideways"),
                stop_loss=recommendation.get("stop_loss", 0),
                target1=recommendation.get("target1", 0),
                target2=recommendation.get("target2", 0),
                weight_pct=weight_pct,
            )
            logger.info(
                "매수 완료: %s(%s) %d주 @ %s원 (비중 %.1f%%)",
                name, ticker, quantity, f"{price:,}", weight_pct,
            )

        return order

    # ── 매도 실행 ──

    def execute_sell(
        self, stock_data: Dict, recommendation: Dict,
        position: Dict
    ) -> Optional[Order]:
        """매도 주문을 실행한다.

        Args:
            stock_data: 분석된 종목 데이터
            recommendation: TradeRule.should_sell() 결과
            position: 현재 포지션 정보

        Returns:
            Order 객체 또는 None
        """
        if not self._check_all_safety(is_sell=True):
            return None

        ticker = stock_data.get("ticker", "")
        name = stock_data.get("name", ticker)
        price = stock_data.get("price", 0)
        sell_pct = recommendation.get("sell_pct", 100)
        action = recommendation.get("action", "")

        if price <= 0:
            return None

        # 매도 수량 계산 (sell_pct 기반)
        # 실제 보유 수량은 포트폴리오에서 확인
        entry_price = position.get("entry_price", price)
        weight_pct = position.get("weight_pct", 0)

        # 가상 포지션 기반 수량 추정
        # (실제 API에서는 보유 수량을 직접 조회)
        if self.portfolio:
            holdings = self.portfolio.get_holdings_summary()
            actual_qty = 0
            for h in holdings:
                if h.get("code") == ticker:
                    actual_qty = h.get("quantity", 0)
                    break
            quantity = max(1, int(actual_qty * sell_pct / 100))
        else:
            # dry_run: 가상 수량 계산
            estimated_qty = max(1, int(weight_pct * 1000 / (entry_price / 1000 + 1)))
            quantity = max(1, int(estimated_qty * sell_pct / 100))

        # PnL 계산
        pnl_amount = (price - entry_price) * quantity
        pnl_pct = ((price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # 주문 실행
        order = self._place_order(
            side="sell", ticker=ticker, name=name,
            quantity=quantity, price=price,
            reason=action,
            confluence_score=stock_data.get("confluence_score", 0),
            regime=stock_data.get("market_regime", ""),
            pnl_amount=int(pnl_amount),
            pnl_pct=round(pnl_pct, 2),
        )

        if order and order.status in ("filled", "simulated"):
            # 포지션 갱신
            if action == "target1":
                self.tracker.mark_target_hit(ticker, 1)
                self.tracker.update_stop_loss(ticker, entry_price)
            elif action == "target2":
                self.tracker.mark_target_hit(ticker, 2)
            elif sell_pct >= 100:
                self.tracker.close_position(ticker, price, action)

            logger.info(
                "매도 완료: %s(%s) %d주 @ %s원 (사유: %s, PnL: %+.1f%%)",
                name, ticker, quantity, f"{price:,}", action, pnl_pct,
            )

        return order

    # ── 내부 메서드 ──

    def _place_order(
        self, side: str, ticker: str, name: str,
        quantity: int, price: int, reason: str = "",
        confluence_score: float = 0, regime: str = "",
        pnl_amount: int = None, pnl_pct: float = None,
    ) -> Optional[Order]:
        """주문을 실행하고 로그를 기록한다."""

        if AUTO_CONFIG.dry_run:
            # 시뮬레이션 모드
            order = Order(
                ticker=ticker, name=name, side=side,
                quantity=quantity, price=price,
                order_type=AUTO_CONFIG.order_type,
                status="simulated", reason=reason,
            )
            logger.info(
                "[DRY RUN] %s %s(%s) %d주 @ %s원",
                side.upper(), name, ticker, quantity, f"{price:,}",
            )
        else:
            # 실제 주문
            if self.client is None:
                logger.error("KiwoomClient가 None — 주문 불가")
                return None

            order = self.client.place_order(
                side=side, ticker=ticker,
                quantity=quantity, price=0,  # 시장가
                order_type="market",
            )
            if order is None:
                return None
            order.name = name
            order.reason = reason

        # 매매 로그 기록
        self.state.log_trade(
            ticker=ticker, name=name, side=side,
            quantity=quantity, price=price,
            order_type=AUTO_CONFIG.order_type,
            status=order.status,
            order_id=order.order_id or "",
            reason=reason,
            confluence_score=confluence_score,
            regime=regime,
            pnl_amount=pnl_amount,
            pnl_pct=pnl_pct,
        )

        self.daily_orders.append(order)
        return order

    def _calculate_quantity(
        self, ticker: str, price: int, weight_pct: float
    ) -> int:
        """매수 수량을 계산한다."""
        if self.portfolio:
            return self.portfolio.calculate_order_quantity(
                ticker, price, target_weight_pct=weight_pct
            )

        # dry_run: 가상 자산 기준 계산
        virtual_asset = DRY_RUN_VIRTUAL_ASSET
        target_amount = int(virtual_asset * weight_pct / 100)
        return max(0, target_amount // price)

    def reset_daily(self) -> None:
        """일별 카운터를 초기화한다."""
        self.daily_orders = []
