import logging
import time
from typing import Dict, List, Optional

from trading.kiwoom_client import KiwoomClient

logger = logging.getLogger("signalight")

_CACHE_TTL = 60  # seconds


class PortfolioManager:
    """계좌 포트폴리오 조회 및 수량 계산."""

    def __init__(self, client: Optional[KiwoomClient] = None):
        self.client = client
        self._cached_evaluation: Optional[Dict] = None
        self._cache_time: float = 0.0

    def _get_evaluation(self, force_refresh: bool = False) -> Optional[Dict]:
        """계좌평가 조회 (60초 캐시).

        Returns:
            get_account_evaluation() 결과 또는 None
        """
        if self.client is None:
            return None

        now = time.time()
        if not force_refresh and self._cached_evaluation is not None:
            if now - self._cache_time < _CACHE_TTL:
                return self._cached_evaluation

        data = self.client.get_account_evaluation()
        if data is not None:
            self._cached_evaluation = data
            self._cache_time = now
        return data

    def get_position_weight(self, ticker: str) -> float:
        """특정 종목의 포지션 비중(%) 반환.

        Args:
            ticker: 종목코드

        Returns:
            비중(%) — 0.0 if not held or no data
        """
        evaluation = self._get_evaluation()
        if evaluation is None:
            return 0.0

        total_asset = evaluation["summary"].get("estimated_asset", 0)
        if total_asset <= 0:
            return 0.0

        for holding in evaluation.get("holdings", []):
            if holding.get("code") == ticker:
                return holding.get("evaluation", 0) / total_asset * 100

        return 0.0

    def get_available_cash(self) -> int:
        """주문 가능 현금(예수금) 반환.

        Returns:
            예수금(원) — 0 if no data
        """
        evaluation = self._get_evaluation()
        if evaluation is None:
            return 0
        return evaluation["summary"].get("deposit", 0)

    def calculate_order_quantity(
        self,
        ticker: str,
        price: int,
        target_weight_pct: float = 10.0,
    ) -> int:
        """목표 비중에 도달하기 위한 매수 수량 계산.

        현재 보유 수량을 반영하여 추가로 필요한 수량을 반환한다.

        Args:
            ticker: 종목코드
            price: 현재가(원)
            target_weight_pct: 목표 비중(%)

        Returns:
            매수 수량 (0 이상 정수)
        """
        if price <= 0:
            return 0

        evaluation = self._get_evaluation()
        if evaluation is None:
            return 0

        total_asset = evaluation["summary"].get("estimated_asset", 0)
        if total_asset <= 0:
            return 0

        target_amount = int(total_asset * target_weight_pct / 100)

        # Current holding value
        current_evaluation = 0
        for holding in evaluation.get("holdings", []):
            if holding.get("code") == ticker:
                current_evaluation = holding.get("evaluation", 0)
                break

        additional_amount = target_amount - current_evaluation
        if additional_amount <= 0:
            return 0

        # Also cap by available cash
        available_cash = evaluation["summary"].get("deposit", 0)
        buy_amount = min(additional_amount, available_cash)

        quantity = buy_amount // price
        return max(0, quantity)

    def get_holdings_summary(self) -> List[Dict]:
        """보유 종목 요약 리스트 반환.

        Returns:
            [ { code, name, quantity, avg_price, current_price,
                evaluation, pnl_amount, pnl_pct, purchase_amount }, ... ]
            빈 리스트 if no data
        """
        evaluation = self._get_evaluation()
        if evaluation is None:
            return []
        return evaluation.get("holdings", [])
