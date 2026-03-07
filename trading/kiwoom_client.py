import logging
import os
import time
from typing import Dict, Optional

import requests
from dotenv import load_dotenv

from trading import Order

load_dotenv()

logger = logging.getLogger("signalight")

KIWOOM_REST_API_KEY = os.getenv("KIWOOM_REST_API_KEY")
KIWOOM_REST_API_SECRET = os.getenv("KIWOOM_REST_API_SECRET")
KIWOOM_ACCOUNT_NO = os.getenv("KIWOOM_ACCOUNT_NO")


class KiwoomClient:
    """키움증권 REST API 클라이언트 (requests 기반)"""

    def __init__(self, use_mock: bool = True):
        """
        Args:
            use_mock: True = 모의투자 (mockapi.kiwoom.com),
                      False = 실전투자 (api.kiwoom.com)
        """
        trading_env = os.getenv("TRADING_ENV", "mock").lower()
        # Constructor arg takes priority over env var
        self.use_mock = use_mock if use_mock is not None else (trading_env == "mock")

        self.api_key = KIWOOM_REST_API_KEY
        self.api_secret = KIWOOM_REST_API_SECRET
        self.account_no = KIWOOM_ACCOUNT_NO or os.getenv("KIWOOM_ACCOUNT_NO", "")

        self.base_url = (
            "https://mockapi.kiwoom.com" if self.use_mock
            else "https://api.kiwoom.com"
        )

        self._token: Optional[str] = None
        self._token_expires: float = 0.0

    def _get_token(self) -> Optional[str]:
        """OAuth 토큰 발급 (1시간 캐시). API 키 미설정 시 None 반환."""
        if not self.api_key or not self.api_secret:
            logger.warning("KiwoomClient: API Key/Secret이 설정되지 않았습니다.")
            return None

        # Return cached token if still valid
        if self._token and time.time() < self._token_expires:
            return self._token

        url = f"{self.base_url}/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "appkey": self.api_key,
            "secretkey": self.api_secret,
        }

        try:
            response = requests.post(url, json=data, timeout=30)
            result = response.json()
        except Exception as e:
            logger.error(f"KiwoomClient: 토큰 발급 요청 실패: {e}")
            return None

        if result.get("return_code") != 0:
            logger.error(f"KiwoomClient: 토큰 발급 실패: {result.get('return_msg')}")
            return None

        self._token = result.get("token")
        self._token_expires = time.time() + 3600
        return self._token

    def _call_api(self, api_id: str, endpoint: str, body: Dict) -> Optional[Dict]:
        """공통 API 호출 메서드. 실패 시 None 반환 (예외 발생 안 함)."""
        token = self._get_token()
        if token is None:
            return None

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "authorization": f"Bearer {token}",
        }

        try:
            time.sleep(1)  # Rate limiting: 1 second between calls
            response = requests.post(url, headers=headers, json=body, timeout=30)
            result = response.json()
        except Exception as e:
            logger.error(f"KiwoomClient [{api_id}]: 요청 실패: {e}")
            return None

        if result.get("return_code") != 0:
            logger.error(
                f"KiwoomClient [{api_id}] API 오류 "
                f"(code={result.get('return_code')}): {result.get('return_msg')}"
            )
            return None

        return result

    def get_stock_info(self, ticker: str) -> Optional[Dict]:
        """주식 기본 정보 조회 (ka10001).

        Args:
            ticker: 종목코드 6자리

        Returns:
            API 응답 딕셔너리 또는 None
        """
        return self._call_api(
            "ka10001",
            "/api/dostk/stkinfo",
            {"stk_cd": ticker},
        )

    def get_account_evaluation(self) -> Optional[Dict]:
        """계좌평가현황 조회 (kt00004).

        Returns:
            {
                "summary": { deposit, d2_deposit, total_evaluation, total_asset,
                             total_purchase, estimated_asset, today_pnl,
                             monthly_pnl, cumulative_pnl, today_pnl_pct,
                             monthly_pnl_pct, cumulative_pnl_pct },
                "holdings": [ { code, name, quantity, avg_price, current_price,
                                evaluation, pnl_amount, pnl_pct, purchase_amount } ],
                "raw": dict,
            }
            또는 None (API 키 미설정 / 오류)
        """
        result = self._call_api("kt00004", "/api/dostk/acnt", {
            "qry_tp": "0",
            "dmst_stex_tp": "KRX",
        })
        if result is None:
            return None

        def _int(v) -> int:
            try:
                return int(v)
            except (ValueError, TypeError):
                return 0

        def _float(v) -> float:
            try:
                return float(v)
            except (ValueError, TypeError):
                return 0.0

        summary = {
            "deposit": _int(result.get("entr")),
            "d2_deposit": _int(result.get("d2_entra")),
            "total_evaluation": _int(result.get("tot_est_amt")),
            "total_asset": _int(result.get("aset_evlt_amt")),
            "total_purchase": _int(result.get("tot_pur_amt")),
            "estimated_asset": _int(result.get("prsm_dpst_aset_amt")),
            "today_pnl": _int(result.get("tdy_lspft")),
            "monthly_pnl": _int(result.get("lspft2")),
            "cumulative_pnl": _int(result.get("lspft")),
            "today_pnl_pct": _float(result.get("tdy_lspft_rt")),
            "monthly_pnl_pct": _float(result.get("lspft_ratio")),
            "cumulative_pnl_pct": _float(result.get("lspft_rt")),
        }

        holdings = []
        for s in result.get("stk_acnt_evlt_prst", []):
            holdings.append({
                "code": s.get("stk_cd", ""),
                "name": s.get("stk_nm", ""),
                "quantity": _int(s.get("rmnd_qty")),
                "avg_price": _int(s.get("avg_prc")),
                "current_price": abs(_int(s.get("cur_prc"))),
                "evaluation": _int(s.get("evlt_amt")),
                "pnl_amount": _int(s.get("pl_amt")),
                "pnl_pct": _float(s.get("pl_rt")),
                "purchase_amount": _int(s.get("pur_amt")),
            })

        return {"summary": summary, "holdings": holdings, "raw": result}

    def place_order(
        self,
        side: str,
        ticker: str,
        quantity: int,
        price: int = 0,
        order_type: str = "market",
    ) -> Optional[Order]:
        """주문 실행.

        Args:
            side: "buy" 또는 "sell"
            ticker: 종목코드 6자리
            quantity: 주문수량
            price: 주문가격 (시장가=0)
            order_type: "market" 또는 "limit"

        Returns:
            Order 객체 (filled 또는 rejected 상태) 또는 None
        """
        if side not in ("buy", "sell"):
            logger.error(f"KiwoomClient.place_order: invalid side '{side}'")
            return None

        # trde_tp: "3" = 시장가, "0" = 지정가
        trde_tp = "3" if order_type == "market" else "0"
        api_id = "kt10000" if side == "buy" else "kt10001"

        # CRITICAL: All body params must be strings
        body = {
            "dmst_stex_tp": "KRX",
            "stk_cd": ticker,
            "ord_qty": str(quantity),
            "ord_uv": str(price),
            "trde_tp": trde_tp,
        }

        result = self._call_api(api_id, "/api/dostk/ordr", body)

        order = Order(
            ticker=ticker,
            name=ticker,  # name not available from order response
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )

        if result is None:
            order.status = "rejected"
            order.reason = "API 호출 실패"
            logger.error(f"주문 실패: {side} {ticker} {quantity}주")
        else:
            order.status = "filled"
            order.order_id = str(result.get("ord_no", ""))
            logger.info(
                f"주문 완료: {side} {ticker} {quantity}주 "
                f"(order_id={order.order_id})"
            )

        return order
