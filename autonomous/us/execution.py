"""미국 주식 안전 주문 실행기 — AlpacaClient 래핑 + 안전장치.

서킷 브레이커 + ET 장중 시간 체크 + 킬스위치.
"""

import logging
import math
import os
from datetime import date
from typing import Dict, List, Optional

from trading.alpaca_client import AlpacaClient
from trading import Order
from trading.position_tracker import PositionTracker
from autonomous.us.config import US_AUTO_CONFIG, USAutonomousConfig
from autonomous.state import PipelineState
from config import DRY_RUN_VIRTUAL_ASSET_USD

logger = logging.getLogger("signalight.us")


class USSafeExecutor:
    """안전장치가 포함된 미국 주식 주문 실행기."""

    def __init__(
        self,
        state: PipelineState = None,
        position_tracker: PositionTracker = None,
        config: Optional[USAutonomousConfig] = None,
    ):
        self.state = state or PipelineState()
        self.tracker = position_tracker or PositionTracker()
        self.config = config or US_AUTO_CONFIG
        self.daily_orders = []  # type: List[Order]

        # AlpacaClient (dry_run이어도 생성 — paper trading이므로 무해)
        try:
            self.client = AlpacaClient()
        except Exception as e:
            logger.warning("AlpacaClient 초기화 실패: %s", e)
            self.client = None  # type: Optional[AlpacaClient]

    # ── 안전장치 체크 ──

    def _check_kill_switch(self) -> bool:
        """킬스위치 파일 존재 여부 확인."""
        if os.path.exists(self.config.kill_switch_path):
            logger.warning("킬스위치 활성: %s", self.config.kill_switch_path)
            return False
        return True

    def _check_market_hours(self) -> bool:
        """Alpaca clock API로 미국 장중 여부를 확인한다."""
        if self.config.dry_run:
            # dry_run: 항상 장중으로 간주
            return True

        if self.client is None:
            return False

        try:
            clock = self.client._request(
                "GET", f"{self.client.base_url}/v2/clock"
            )
            return bool(clock.get("is_open", False))
        except Exception as e:
            logger.warning("Alpaca clock 조회 실패: %s — 장중 아닌 것으로 처리", e)
            return False

    def _check_all_safety(self, is_sell: bool = False) -> bool:
        """모든 안전장치를 체크한다.

        Args:
            is_sell: 매도인 경우 서킷 브레이커 체크 완화

        Returns:
            True = 주문 가능
        """
        if not self._check_kill_switch():
            return False

        if not self._check_market_hours():
            logger.info("US 장외 시간 — 주문 스킵")
            return False

        if is_sell:
            return True

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
            stock_data: 분석된 종목 데이터 (ticker, name, price, ...)
            recommendation: TradeRule.should_buy() 결과

        Returns:
            Order 객체 또는 None
        """
        if not self._check_all_safety(is_sell=False):
            return None

        ticker = stock_data.get("ticker", "")
        name = stock_data.get("name", ticker)
        price = float(stock_data.get("price", 0))
        weight_pct = recommendation.get(
            "weight_pct", self.config.target_weight_pct
        )

        if price <= 0:
            logger.warning("매수 실패: %s 가격 0", ticker)
            return None

        qty = self._calculate_quantity(ticker, weight_pct, fallback_price=price)
        if qty <= 0:
            logger.warning("매수 실패: %s 수량 0", ticker)
            return None

        order_amount = price * qty
        if order_amount > self.config.max_order_amount:
            qty = math.floor(self.config.max_order_amount / price)
            if qty <= 0:
                return None

        order = self._place_order(
            side="buy",
            ticker=ticker,
            name=name,
            quantity=qty,
            price=price,
            reason=f"confluence={stock_data.get('confluence_score', 0):.1f}",
            confluence_score=stock_data.get("confluence_score", 0),
            regime=stock_data.get("market_regime", ""),
        )

        if order and order.status in ("filled", "simulated"):
            try:
                indicators = stock_data.get("indicators", {})
                self.tracker.open_position(
                    ticker,
                    name,
                    entry_price=int(price),
                    entry_atr=indicators.get("atr", 0),
                    regime=stock_data.get("market_regime", "sideways"),
                    stop_loss=int(recommendation.get("stop_loss", 0)),
                    target1=int(recommendation.get("target1", 0)),
                    target2=int(recommendation.get("target2", 0)),
                    weight_pct=weight_pct,
                )
                logger.info(
                    "🇺🇸 매수 완료: %s(%s) %d주 @ $%.2f (비중 %.1f%%)",
                    name, ticker, qty, price, weight_pct,
                )
            except Exception as e:
                logger.error(
                    "포지션 생성 실패 (trade_log는 기록됨): %s(%s) — %s",
                    name, ticker, e, exc_info=True,
                )

        return order

    # ── 매도 실행 ──

    def execute_sell(
        self, stock_data: Dict, recommendation: Dict, position: Dict
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
        price = float(stock_data.get("price", 0))
        sell_pct = recommendation.get("sell_pct", 100)
        action = recommendation.get("action", "")

        if price <= 0:
            return None

        entry_price = float(position.get("entry_price", price))
        weight_pct = float(position.get("weight_pct", 0))

        # 실제 보유 수량 조회 또는 가상 추정
        qty = self._get_sell_quantity(ticker, sell_pct, weight_pct, price)

        pnl_amount = (price - entry_price) * qty
        pnl_pct = (
            (price - entry_price) / entry_price * 100
            if entry_price > 0
            else 0
        )

        order = self._place_order(
            side="sell",
            ticker=ticker,
            name=name,
            quantity=qty,
            price=price,
            reason=action,
            confluence_score=stock_data.get("confluence_score", 0),
            regime=stock_data.get("market_regime", ""),
            pnl_amount=round(pnl_amount, 2),
            pnl_pct=round(pnl_pct, 2),
        )

        if order and order.status in ("filled", "simulated"):
            if sell_pct < 100:
                self.tracker.partial_sell(ticker, sell_pct)
            if action == "target1":
                self.tracker.mark_target_hit(ticker, 1)
                self.tracker.update_stop_loss(ticker, int(entry_price))
            elif action == "target2":
                self.tracker.mark_target_hit(ticker, 2)
            elif sell_pct >= 100:
                self.tracker.close_position(ticker, int(price), action)

            logger.info(
                "🇺🇸 매도 완료: %s(%s) %d주 @ $%.2f (사유: %s, PnL: %+.1f%%)",
                name, ticker, qty, price, action, pnl_pct,
            )

        return order

    # ── 계좌/포지션 조회 ──

    def get_account_info(self) -> Dict:
        """Alpaca 계좌 정보를 반환한다."""
        if self.client is None:
            return {}
        try:
            return self.client.get_account()
        except Exception as e:
            logger.warning("계좌 정보 조회 실패: %s", e)
            return {}

    def get_positions(self) -> List[Dict]:
        """Alpaca 보유 포지션 목록을 반환한다."""
        if self.client is None:
            return []
        try:
            return self.client.get_positions()
        except Exception as e:
            logger.warning("포지션 조회 실패: %s", e)
            return []

    # ── 내부 메서드 ──

    def _calculate_quantity(
        self, ticker: str, weight_pct: float, fallback_price: float = 0
    ) -> int:
        """매수 수량을 계산한다 (USD 기반).

        Args:
            ticker: 종목 티커
            weight_pct: 목표 비중 (%)
            fallback_price: client가 None이거나 최신 체결가 조회 실패 시 사용할 가격
        """
        try:
            if self.client and not self.config.dry_run:
                acct = self.client.get_account()
                equity = float(acct.get("equity", DRY_RUN_VIRTUAL_ASSET_USD))
            else:
                # dry_run: 기존 투자금 차감 후 available equity로 계산
                open_positions = self.tracker.get_all_open()
                invested = sum(
                    DRY_RUN_VIRTUAL_ASSET_USD * pos.get("weight_pct", 0) / 100
                    for pos in open_positions
                )
                max_exposure = DRY_RUN_VIRTUAL_ASSET_USD * self.config.max_exposure_pct / 100
                if invested >= max_exposure:
                    logger.info(
                        "최대 노출 한도 도달: 투자금 %s >= 한도 %s", invested, max_exposure
                    )
                    return 0
                available = DRY_RUN_VIRTUAL_ASSET_USD - invested
                equity = min(available, max_exposure - invested)

            target_amount = equity * (weight_pct / 100)
            target_amount = min(target_amount, self.config.max_order_amount)

            price = 0
            if self.client:
                try:
                    trade = self.client.get_latest_trade(ticker)
                    price = float(trade.get("trade", {}).get("p", 0))
                except Exception:
                    pass

            if price <= 0:
                price = fallback_price

            if price <= 0:
                logger.warning("수량 계산 실패 (%s): 가격 정보 없음", ticker)
                return 0

            return max(0, math.floor(target_amount / price))
        except Exception as e:
            logger.warning("수량 계산 실패 (%s): %s", ticker, e)
            return 0

    def _get_sell_quantity(
        self,
        ticker: str,
        sell_pct: float,
        weight_pct: float,
        price: float,
    ) -> int:
        """매도 수량을 계산한다."""
        if self.client and not self.config.dry_run:
            try:
                pos = self.client.get_position(ticker)
                actual_qty = int(float(pos.get("qty", 0)))
                return max(1, math.floor(actual_qty * sell_pct / 100))
            except Exception:
                pass

        # dry_run: 가상 수량 추정
        virtual_qty = max(1, int(weight_pct * 10))
        return max(1, math.floor(virtual_qty * sell_pct / 100))

    def _place_order(
        self,
        side: str,
        ticker: str,
        name: str,
        quantity: int,
        price: float,
        reason: str = "",
        confluence_score: float = 0,
        regime: str = "",
        pnl_amount: float = None,
        pnl_pct: float = None,
    ) -> Optional[Order]:
        """주문을 실행하고 로그를 기록한다."""

        if self.config.dry_run:
            order = Order(
                ticker=ticker,
                name=name,
                side=side,
                quantity=quantity,
                price=int(price * 100),  # Order.price는 int — cents로 저장
                order_type=self.config.order_type,
                status="simulated",
                reason=reason,
            )
            logger.info(
                "🇺🇸 [DRY RUN] %s %s(%s) %d주 @ $%.2f",
                side.upper(), name, ticker, quantity, price,
            )
        else:
            if self.client is None:
                logger.error("AlpacaClient가 None — 주문 불가")
                return None

            try:
                resp = self.client.place_order(
                    symbol=ticker,
                    qty=quantity,
                    side=side,
                    order_type="market",
                )
                order = Order(
                    ticker=ticker,
                    name=name,
                    side=side,
                    quantity=quantity,
                    price=int(price * 100),
                    order_type="market",
                    status="filled",
                    order_id=resp.get("id", ""),
                    reason=reason,
                )
            except Exception as e:
                logger.error("Alpaca 주문 실패 (%s %s): %s", side, ticker, e)
                return None

        # 매매 로그 기록 (price를 int로 — state DB 스키마 호환)
        self.state.log_trade(
            ticker=ticker,
            name=name,
            side=side,
            quantity=quantity,
            price=int(price * 100),
            order_type=self.config.order_type,
            status=order.status,
            order_id=order.order_id or "",
            reason=reason,
            confluence_score=confluence_score,
            regime=regime,
            pnl_amount=int(pnl_amount * 100) if pnl_amount is not None else None,
            pnl_pct=pnl_pct,
        )

        self.daily_orders.append(order)
        return order

    def reset_daily(self) -> None:
        """일별 카운터를 초기화한다."""
        self.daily_orders = []
