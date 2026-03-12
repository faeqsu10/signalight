"""Alpaca REST API 래퍼 — 미국 주식 Paper Trading."""

import json
import logging
import urllib.error
import urllib.request
from typing import Dict, List, Optional

from config import ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL

logger = logging.getLogger("signalight.alpaca")

DATA_BASE_URL = "https://data.alpaca.markets"


class AlpacaClient:
    """Alpaca Paper Trading REST API 클라이언트 (urllib 기반, 외부 패키지 불필요)."""

    def __init__(self) -> None:
        self.api_key = ALPACA_API_KEY
        self.api_secret = ALPACA_API_SECRET
        self.base_url = ALPACA_BASE_URL.rstrip("/")

        if not self.api_key or not self.api_secret:
            logger.warning("AlpacaClient: ALPACA_API_KEY / ALPACA_API_SECRET 미설정")

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def get_account(self) -> Dict:
        """계좌 정보 조회. (현금, 포트폴리오 가치, 상태 등)"""
        return self._request("GET", f"{self.base_url}/v2/account")

    def get_positions(self) -> List[Dict]:
        """보유 포지션 전체 조회."""
        result = self._request("GET", f"{self.base_url}/v2/positions")
        return result if isinstance(result, list) else []

    def get_position(self, symbol: str) -> Dict:
        """특정 종목 포지션 조회.

        Args:
            symbol: 종목 심볼 (예: "AAPL")
        """
        return self._request("GET", f"{self.base_url}/v2/positions/{symbol}")

    def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
    ) -> Dict:
        """주문 실행.

        Args:
            symbol: 종목 심볼 (예: "AAPL")
            qty: 주문 수량
            side: "buy" 또는 "sell"
            order_type: "market" 또는 "limit"
            time_in_force: "day", "gtc", "ioc", "fok"

        Returns:
            Alpaca 주문 응답 딕셔너리
        """
        body = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        return self._request("POST", f"{self.base_url}/v2/orders", body=body)

    def get_order(self, order_id: str) -> Dict:
        """주문 상태 조회.

        Args:
            order_id: Alpaca 주문 UUID
        """
        return self._request("GET", f"{self.base_url}/v2/orders/{order_id}")

    def get_orders(self, status: str = "open") -> List[Dict]:
        """주문 목록 조회.

        Args:
            status: "open", "closed", "all"
        """
        result = self._request("GET", f"{self.base_url}/v2/orders?status={status}")
        return result if isinstance(result, list) else []

    def cancel_order(self, order_id: str) -> bool:
        """주문 취소.

        Args:
            order_id: Alpaca 주문 UUID

        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            self._request("DELETE", f"{self.base_url}/v2/orders/{order_id}")
            return True
        except Exception as e:
            logger.error(f"AlpacaClient.cancel_order({order_id}): {e}")
            return False

    def get_asset(self, symbol: str) -> Dict:
        """종목 정보 조회 (거래 가능 여부 포함).

        Args:
            symbol: 종목 심볼 (예: "AAPL")
        """
        return self._request("GET", f"{self.base_url}/v2/assets/{symbol}")

    def get_latest_quote(self, symbol: str) -> Dict:
        """최신 호가(bid/ask) 조회.

        Args:
            symbol: 종목 심볼 (예: "AAPL")
        """
        return self._request(
            "GET", f"{DATA_BASE_URL}/v2/stocks/{symbol}/quotes/latest"
        )

    def get_latest_trade(self, symbol: str) -> Dict:
        """최신 체결가 조회.

        Args:
            symbol: 종목 심볼 (예: "AAPL")
        """
        return self._request(
            "GET", f"{DATA_BASE_URL}/v2/stocks/{symbol}/trades/latest"
        )

    # ──────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────

    def _request(self, method: str, url: str, body: Optional[Dict] = None) -> Dict:
        """HTTP 요청 실행.

        Args:
            method: "GET", "POST", "DELETE"
            url: 전체 URL
            body: POST 시 JSON 바디 (선택)

        Returns:
            파싱된 JSON 응답 (dict 또는 list)

        Raises:
            RuntimeError: API 키 미설정 또는 HTTP 오류
        """
        if not self.api_key or not self.api_secret:
            raise RuntimeError("AlpacaClient: API 키가 설정되지 않았습니다.")

        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
        }

        encoded_body: Optional[bytes] = None
        if body is not None:
            encoded_body = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=encoded_body,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.error(
                f"AlpacaClient [{method} {url}] HTTP {e.code}: {error_body}"
            )
            raise RuntimeError(
                f"Alpaca API 오류 HTTP {e.code}: {error_body}"
            ) from e
        except Exception as e:
            logger.error(f"AlpacaClient [{method} {url}] 요청 실패: {e}")
            raise
