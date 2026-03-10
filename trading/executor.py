import logging
from datetime import datetime, date
from typing import Dict, List, Optional

from trading import Order, TradingConfig
from trading.kiwoom_client import KiwoomClient
from trading.portfolio import PortfolioManager

logger = logging.getLogger("signalight")


class TradeExecutor:
    """시그널 기반 주문 실행기."""

    def __init__(self, config: Optional[TradingConfig] = None):
        self.config = config or TradingConfig()
        self.client: Optional[KiwoomClient] = (
            KiwoomClient(use_mock=self.config.use_mock)
            if not self.config.dry_run
            else None
        )
        self.portfolio = PortfolioManager(client=self.client)
        self.daily_orders: List[Order] = []
        self.daily_pnl: float = 0.0
        self._last_reset_date: Optional[date] = None

    def _reset_daily_if_needed(self) -> None:
        """새 거래일 시작 시 일별 카운터 초기화."""
        today = date.today()
        if self._last_reset_date != today:
            self.daily_orders = []
            self.daily_pnl = 0.0
            self._last_reset_date = today
            logger.info(f"TradeExecutor: 일별 카운터 초기화 ({today})")

    def _check_daily_loss_limit(self) -> bool:
        """일일 손실 한도 초과 여부 확인.

        Returns:
            True = 거래 가능, False = 손실 한도 초과로 거래 불가
        """
        if self.daily_pnl >= 0:
            return True

        # Fetch total asset to compute loss %
        available_cash = self.portfolio.get_available_cash()
        if available_cash <= 0:
            # Cannot determine, allow trading
            return True

        # Approximate total asset from portfolio evaluation
        evaluation = self.portfolio._get_evaluation()
        if evaluation is None:
            return True

        total_asset = evaluation["summary"].get("estimated_asset", 0)
        if total_asset <= 0:
            return True

        loss_pct = abs(self.daily_pnl) / total_asset * 100
        if loss_pct >= self.config.daily_loss_limit_pct:
            logger.warning(
                f"TradeExecutor: 일일 손실 한도 초과 "
                f"({loss_pct:.2f}% >= {self.config.daily_loss_limit_pct}%). 거래 중단."
            )
            return False
        return True

    def _check_position_limit(self, ticker: str, order_amount: int) -> bool:
        """단일 종목 비중 한도 초과 여부 확인.

        Returns:
            True = 거래 가능, False = 비중 한도 초과
        """
        evaluation = self.portfolio._get_evaluation()
        if evaluation is None:
            # No portfolio data, allow but warn
            logger.warning("TradeExecutor: 계좌 평가 데이터 없음 — 포지션 한도 미검증")
            return True

        total_asset = evaluation["summary"].get("estimated_asset", 0)
        if total_asset <= 0:
            return True

        # Current holding value for this ticker
        current_weight_pct = self.portfolio.get_position_weight(ticker)

        # What the new position weight would be after this order
        new_weight_pct = current_weight_pct + (order_amount / total_asset * 100)
        if new_weight_pct > self.config.max_single_position_pct:
            logger.warning(
                f"TradeExecutor: 종목 비중 한도 초과 {ticker} "
                f"({new_weight_pct:.1f}% > {self.config.max_single_position_pct}%)"
            )
            return False
        return True

    def execute_signal(self, stock_data: Dict) -> Optional[Order]:
        """시그널 데이터를 기반으로 주문 실행.

        실행 조건:
        - confluence_score >= 3 (강한 시그널)
        - 일일 손실 한도 미초과
        - 종목 비중 한도 미초과

        dry_run 모드에서는 실제 주문 없이 Order(status="simulated") 생성.

        Args:
            stock_data: {
                "ticker": str,
                "name": str,
                "signal": str,       # "buy" | "sell" | "hold"
                "confluence_score": int,
                "current_price": int,
                "quantity": int,     # optional, computed if missing
            }

        Returns:
            Order 객체 또는 None (조건 미충족 시)
        """
        self._reset_daily_if_needed()

        ticker = stock_data.get("ticker", "")
        name = stock_data.get("name", ticker)
        signal = stock_data.get("signal", "hold")
        confluence_score = stock_data.get("confluence_score", 0)
        current_price = stock_data.get("current_price", 0)

        # Only act on buy/sell signals
        if signal not in ("buy", "sell"):
            return None

        # 시그널 강도 체크 (TradeRule이 사전 검증한 경우 skip_score_check=True)
        skip_check = stock_data.get("skip_score_check", False)
        if not skip_check and confluence_score < 3:
            logger.debug(
                f"TradeExecutor: 시그널 스킵 {ticker} "
                f"(confluence_score={confluence_score} < 3)"
            )
            return None

        # Determine quantity
        quantity = stock_data.get("quantity", 0)
        if quantity <= 0 and signal == "buy" and current_price > 0:
            quantity = self.portfolio.calculate_order_quantity(ticker, current_price)

        if quantity <= 0:
            logger.warning(f"TradeExecutor: 주문 수량 0 — {ticker} 스킵")
            return None

        order_amount = current_price * quantity

        # Cap at max_order_amount
        if order_amount > self.config.max_order_amount:
            quantity = self.config.max_order_amount // current_price
            order_amount = current_price * quantity
            if quantity <= 0:
                logger.warning(f"TradeExecutor: 주문 한도 초과로 수량 0 — {ticker} 스킵")
                return None

        # Risk checks (skip for sells — we always allow selling)
        if signal == "buy":
            if not self._check_daily_loss_limit():
                return None
            if not self._check_position_limit(ticker, order_amount):
                return None

        # Dry run: simulate order
        if self.config.dry_run:
            order = Order(
                ticker=ticker,
                name=name,
                side=signal,
                quantity=quantity,
                price=current_price,
                order_type="market",
                status="simulated",
                reason=f"confluence_score={confluence_score}",
            )
            self.daily_orders.append(order)
            logger.info(
                f"[DRY RUN] {signal.upper()} {name}({ticker}) "
                f"{quantity}주 @ {current_price:,}원 "
                f"(score={confluence_score})"
            )
            return order

        # Live order
        if self.client is None:
            logger.error("TradeExecutor: client가 None인데 dry_run=False — 주문 불가")
            return None

        order = self.client.place_order(
            side=signal,
            ticker=ticker,
            quantity=quantity,
            price=0,  # market order
            order_type="market",
        )
        if order is not None:
            order.name = name
            order.reason = f"confluence_score={confluence_score}"
            self.daily_orders.append(order)
            logger.info(
                f"주문 제출: {signal.upper()} {name}({ticker}) "
                f"{quantity}주 (score={confluence_score}, "
                f"status={order.status})"
            )

        return order

    def emergency_stop(self) -> None:
        """긴급 정지 — 모든 거래 비활성화."""
        self.config.dry_run = True
        logger.warning("EMERGENCY STOP: Trading disabled")
