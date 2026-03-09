"""텔레그램 인터랙티브 봇 — 명령어 핸들러 + 인라인 키보드 확인.

구조:
- 전역 _trading_enabled 플래그로 킬스위치 구현
- InteractiveBot 클래스가 데몬 스레드에서 long polling 실행
- 기존 bot/telegram.py의 requests 방식과 동일하게 raw API 사용
- schedule 기반 main.py와 충돌 없이 병렬 동작
"""

import logging
import threading
import time
from typing import Callable, Dict, Optional

import requests

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from bot.telegram import send_message

logger = logging.getLogger("signalight")

# ──────────────────────────────────────────────
# 전역 상태
# ──────────────────────────────────────────────

_trading_enabled: bool = True
_trading_lock = threading.Lock()
_emergency_stop_callback: Optional[Callable] = None


def is_trading_enabled() -> bool:
    """거래 활성화 여부를 반환한다. executor에서 주기적으로 호출한다."""
    with _trading_lock:
        return _trading_enabled


def set_emergency_stop_callback(callback: Callable) -> None:
    """비상정지 콜백을 등록한다. executor가 초기화 시 호출한다."""
    global _emergency_stop_callback
    _emergency_stop_callback = callback


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _post(endpoint: str, payload: Dict) -> Optional[Dict]:
    """텔레그램 Bot API에 POST 요청을 보내고 응답을 반환한다."""
    try:
        resp = requests.post(f"{_BASE_URL}/{endpoint}", json=payload, timeout=10)
        if resp.ok:
            return resp.json()
        logger.warning("텔레그램 API 오류 [%s]: %s %s", endpoint, resp.status_code, resp.text)
    except requests.RequestException as e:
        logger.error("텔레그램 API 요청 실패 [%s]: %s", endpoint, e)
    return None


def _send_with_keyboard(chat_id: str, text: str, inline_keyboard: list) -> Optional[Dict]:
    """인라인 키보드가 포함된 메시지를 전송한다."""
    return _post("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": inline_keyboard},
    })


def _answer_callback(callback_query_id: str, text: str = "") -> None:
    """인라인 키보드 콜백 쿼리에 응답한다 (로딩 스피너 해제)."""
    _post("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
    })


def _is_admin_chat(chat_id: str) -> bool:
    """관리자 chat_id인지 확인한다."""
    return str(chat_id) == str(TELEGRAM_CHAT_ID)


def _is_allowed_chat(chat_id: str) -> bool:
    """허용된 chat_id인지 확인한다. 관리자 또는 등록된 구독자."""
    if _is_admin_chat(chat_id):
        return True
    from storage.db import is_registered_subscriber
    return is_registered_subscriber(str(chat_id))


# ──────────────────────────────────────────────
# InteractiveBot
# ──────────────────────────────────────────────

class InteractiveBot:
    """텔레그램 인터랙티브 봇.

    데몬 스레드에서 long polling으로 업데이트를 수신하고,
    명령어 및 인라인 키보드 콜백을 처리한다.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        # 대기 중인 거래 확인 요청: {ticker: order_data}
        self._pending_trades: Dict[str, Dict] = {}
        self._pending_lock = threading.Lock()
        # getUpdates offset (마지막 처리 update_id + 1)
        self._offset: int = 0

    # ── 생명주기 ──────────────────────────────

    def start(self) -> None:
        """백그라운드 스레드에서 polling을 시작한다."""
        if self._running:
            logger.warning("InteractiveBot이 이미 실행 중입니다.")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_polling,
            name="telegram-interactive-bot",
            daemon=True,
        )
        self._thread.start()
        logger.info("InteractiveBot 시작 (스레드: %s)", self._thread.name)

    def stop(self) -> None:
        """polling 스레드를 중단한다."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("InteractiveBot 중단됨")

    # ── 외부 공개 메서드 ──────────────────────

    def send_trade_confirmation(self, order_data: Dict) -> bool:
        """거래 확인 메시지를 인라인 키보드와 함께 전송한다.

        Args:
            order_data: ticker, name, side, quantity, price, reason 키를 포함.

        Returns:
            메시지 전송 성공 여부.
        """
        ticker = order_data.get("ticker", "")
        name = order_data.get("name", ticker)
        side = order_data.get("side", "")
        quantity = order_data.get("quantity", 0)
        price = order_data.get("price", 0)
        reason = order_data.get("reason", "")

        side_label = "매수" if side == "buy" else "매도"
        amount = quantity * price

        text = (
            f"<b>[거래 확인 요청]</b>\n"
            f"\n"
            f"종목: <b>{name}</b> ({ticker})\n"
            f"방향: {side_label}\n"
            f"수량: {quantity:,}주\n"
            f"가격: {price:,}원\n"
            f"총액: {amount:,}원\n"
        )
        if reason:
            text += f"사유: {reason}\n"

        keyboard = [[
            {"text": "실행", "callback_data": f"confirm_trade:{ticker}"},
            {"text": "거부", "callback_data": f"reject_trade:{ticker}"},
        ]]

        result = _send_with_keyboard(TELEGRAM_CHAT_ID, text, keyboard)
        if result and result.get("ok"):
            with self._pending_lock:
                self._pending_trades[ticker] = order_data
            logger.info("거래 확인 요청 전송: %s %s %d주", ticker, side_label, quantity)
            return True

        logger.error("거래 확인 요청 전송 실패: %s", ticker)
        return False

    # ── 폴링 루프 ─────────────────────────────

    def _run_polling(self) -> None:
        """텔레그램 long polling을 실행한다. 데몬 스레드에서 호출된다."""
        logger.info("텔레그램 long polling 시작")
        consecutive_errors = 0

        while self._running:
            try:
                resp = requests.get(
                    f"{_BASE_URL}/getUpdates",
                    params={
                        "offset": self._offset,
                        "timeout": 30,  # long polling 대기 시간(초)
                        "allowed_updates": ["message", "callback_query"],
                    },
                    timeout=40,  # requests timeout은 polling timeout보다 커야 함
                )
                consecutive_errors = 0

                if not resp.ok:
                    logger.warning("getUpdates 실패: %s %s", resp.status_code, resp.text)
                    time.sleep(5)
                    continue

                data = resp.json()
                updates = data.get("result", [])

                for update in updates:
                    try:
                        self._handle_update(update)
                    except Exception as e:
                        logger.error("업데이트 처리 오류: %s | update=%s", e, update)
                    # offset을 advance: 처리한 update_id + 1
                    self._offset = update["update_id"] + 1

            except requests.RequestException as e:
                consecutive_errors += 1
                wait = min(30, 2 ** consecutive_errors)
                logger.warning(
                    "polling 네트워크 오류 (%d회 연속): %s — %d초 후 재시도",
                    consecutive_errors, e, wait,
                )
                time.sleep(wait)
            except Exception as e:
                logger.error("polling 예기치 못한 오류: %s", e)
                time.sleep(5)

        logger.info("텔레그램 long polling 종료")

    # ── 업데이트 라우팅 ───────────────────────

    def _handle_update(self, update: Dict) -> None:
        """단일 텔레그램 update를 라우팅한다."""
        if "message" in update:
            message = update["message"]
            chat_id = str(message.get("chat", {}).get("id", ""))
            text = message.get("text", "")

            # /register는 미등록 유저도 허용
            if text.startswith("/register") or text.startswith("/start"):
                parts = text.split(maxsplit=1)
                command = parts[0].lstrip("/").split("@")[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                if command == "register":
                    self._cmd_register(chat_id, args)
                    return
                elif command == "start" and not _is_allowed_chat(chat_id):
                    # 미등록 유저의 /start → 등록 안내
                    self._cmd_register_guide(chat_id)
                    return

            if not _is_allowed_chat(chat_id):
                logger.warning("허용되지 않은 chat_id에서 메시지 수신: %s", chat_id)
                send_message(
                    "등록되지 않은 사용자입니다.\n"
                    "/register [닉네임] 으로 등록하세요.\n"
                    f"(당신의 chat_id: <code>{chat_id}</code>)",
                    chat_id=chat_id,
                )
                return

            if text.startswith("/"):
                # "/command arg1 arg2" 파싱
                parts = text.split(maxsplit=1)
                command = parts[0].lstrip("/").split("@")[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                self._handle_command(chat_id, command, args)

        elif "callback_query" in update:
            callback_query = update["callback_query"]
            chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))

            if not _is_allowed_chat(chat_id):
                logger.warning("허용되지 않은 chat_id에서 콜백 수신: %s", chat_id)
                _answer_callback(callback_query["id"])
                return

            self._handle_callback(callback_query)

    # ── 명령어 핸들러 ─────────────────────────

    def _handle_command(self, chat_id: str, command: str, text: str) -> None:
        """명령어(/command) 메시지를 처리한다."""
        global _trading_enabled

        logger.info("명령어 수신: /%s (chat_id=%s)", command, chat_id)

        if command == "help":
            self._cmd_help(chat_id)

        elif command == "status":
            self._cmd_status(chat_id)

        elif command == "scan":
            if _is_admin_chat(chat_id):
                self._cmd_scan(chat_id)
            else:
                send_message("관리자 전용 명령어입니다.", chat_id=chat_id)

        elif command == "add":
            self._cmd_add(chat_id, text)

        elif command == "remove":
            self._cmd_remove(chat_id, text)

        elif command == "list":
            self._cmd_list(chat_id)

        elif command == "subscribers":
            self._cmd_subscribers(chat_id)

        elif command == "unregister":
            self._cmd_unregister(chat_id)

        elif command == "stop":
            if not _is_admin_chat(chat_id):
                send_message("관리자 전용 명령어입니다.", chat_id=chat_id)
                return
            with _trading_lock:
                _trading_enabled = False
            logger.warning("긴급 정지 명령 수신. 거래 비활성화.")

            # 외부 executor 콜백 호출
            if _emergency_stop_callback is not None:
                try:
                    _emergency_stop_callback()
                except Exception as e:
                    logger.error("emergency_stop 콜백 오류: %s", e)

            send_message(
                "<b>[긴급 정지]</b> 거래가 비활성화되었습니다.\n"
                "/start 명령으로 재개할 수 있습니다."
            )

        elif command == "start":
            if not _is_admin_chat(chat_id):
                send_message("관리자 전용 명령어입니다.", chat_id=chat_id)
                return
            with _trading_lock:
                _trading_enabled = True
            logger.info("거래 재활성화 명령 수신.")
            send_message(
                "<b>[거래 재개]</b> 거래가 다시 활성화되었습니다."
            )

        else:
            send_message(
                f"알 수 없는 명령어: <code>/{command}</code>\n"
                "/help 로 사용 가능한 명령어를 확인하세요.",
                chat_id=chat_id,
            )

    def _cmd_help(self, chat_id: str) -> None:
        """/help 명령 처리."""
        is_admin = _is_admin_chat(chat_id)

        lines = [
            "<b>Signalight 봇 명령어</b>",
            "",
            "/help — 이 도움말",
            "/status — 현재 상태 요약",
            "/list — 내 감시 종목 목록",
            "/add [종목코드] [종목명] — 감시 종목 추가",
            "/remove [종목코드] — 감시 종목 제거",
        ]

        if is_admin:
            lines.extend([
                "",
                "<b>[관리자 전용]</b>",
                "/scan — 수동 시장 스캔",
                "/stop — 긴급 정지 (거래 비활성화)",
                "/start — 거래 재개",
                "/subscribers — 구독자 목록",
            ])
        else:
            lines.extend([
                "/unregister — 구독 해제",
            ])

        send_message("\n".join(lines), chat_id=chat_id)

    def _cmd_register(self, chat_id: str, text: str) -> None:
        """/register [닉네임] — 구독자 등록."""
        from storage.db import register_subscriber

        nickname = text.strip() or f"user_{chat_id[-4:]}"

        if _is_admin_chat(chat_id):
            send_message("관리자는 이미 등록되어 있습니다.", chat_id=chat_id)
            return

        if register_subscriber(chat_id, nickname):
            send_message(
                f"<b>[등록 완료]</b> 환영합니다, {nickname}!\n"
                f"\n"
                f"알림 받을 종목을 추가하세요:\n"
                f"/add 005930 삼성전자\n"
                f"/list — 내 종목 목록\n"
                f"/help — 전체 명령어",
                chat_id=chat_id,
            )
            # 관리자에게 알림
            send_message(f"[구독자 등록] {nickname} (chat_id: {chat_id})")
            logger.info("구독자 등록: %s (chat_id=%s)", nickname, chat_id)
        else:
            send_message("이미 등록된 구독자입니다.", chat_id=chat_id)

    def _cmd_register_guide(self, chat_id: str) -> None:
        """미등록 유저의 /start 처리 — 등록 안내."""
        send_message(
            "<b>Signalight 주식 시그널 봇</b>\n"
            "\n"
            "관심 종목의 매매 시그널을 실시간 알림으로 받아보세요.\n"
            "\n"
            "/register [닉네임] 으로 등록하세요.\n"
            "예: /register 홍길동",
            chat_id=chat_id,
        )

    def _cmd_unregister(self, chat_id: str) -> None:
        """/unregister — 구독 해제."""
        from storage.db import unregister_subscriber

        if _is_admin_chat(chat_id):
            send_message("관리자는 구독 해제할 수 없습니다.", chat_id=chat_id)
            return

        if unregister_subscriber(chat_id):
            send_message("구독이 해제되었습니다. 더 이상 알림을 받지 않습니다.", chat_id=chat_id)
            send_message(f"[구독자 해제] chat_id: {chat_id}")
            logger.info("구독자 해제: chat_id=%s", chat_id)
        else:
            send_message("등록된 구독자가 아닙니다.", chat_id=chat_id)

    def _cmd_subscribers(self, chat_id: str) -> None:
        """/subscribers — 구독자 목록 (관리자 전용)."""
        if not _is_admin_chat(chat_id):
            send_message("관리자 전용 명령어입니다.", chat_id=chat_id)
            return

        from storage.db import get_active_subscribers, get_user_watchlist

        subscribers = get_active_subscribers()
        if not subscribers:
            send_message("등록된 구독자가 없습니다.")
            return

        lines = ["<b>[구독자 목록]</b>", ""]
        for i, sub in enumerate(subscribers, 1):
            cid = sub["chat_id"]
            nick = sub["nickname"] or "이름없음"
            tickers = get_user_watchlist(cid)
            ticker_str = ", ".join(name for _, name in tickers) if tickers else "종목 없음"
            lines.append(f"{i}. {nick} ({cid})")
            lines.append(f"   종목: {ticker_str}")
        lines.append(f"\n총 {len(subscribers)}명")
        send_message("\n".join(lines))

    def _cmd_add(self, chat_id: str, text: str) -> None:
        """/add 종목코드 종목명 — 감시 종목 추가."""
        from storage.db import add_to_watchlist, add_to_user_watchlist

        parts = text.strip().split(maxsplit=1)
        if len(parts) < 2:
            send_message("사용법: /add [종목코드] [종목명]\n예: /add 005930 삼성전자", chat_id=chat_id)
            return

        ticker, name = parts[0], parts[1]

        if _is_admin_chat(chat_id):
            # 관리자: 전역 워치리스트에 추가
            if add_to_watchlist(ticker, name):
                send_message(f"감시 종목 추가: <b>{name}</b> ({ticker})", chat_id=chat_id)
                logger.info("종목 추가: %s (%s)", name, ticker)
            else:
                send_message(f"이미 감시 중인 종목입니다: <b>{name}</b> ({ticker})", chat_id=chat_id)
        else:
            # 구독자: 개인 워치리스트에 추가
            if add_to_user_watchlist(chat_id, ticker, name):
                send_message(f"내 종목 추가: <b>{name}</b> ({ticker})", chat_id=chat_id)
                logger.info("구독자 종목 추가: chat_id=%s, %s (%s)", chat_id, name, ticker)
            else:
                send_message(f"이미 추가된 종목입니다: <b>{name}</b> ({ticker})", chat_id=chat_id)

    def _cmd_remove(self, chat_id: str, text: str) -> None:
        """/remove 종목코드 — 감시 종목 제거."""
        from storage.db import remove_from_watchlist, remove_from_user_watchlist

        ticker = text.strip()
        if not ticker:
            send_message("사용법: /remove [종목코드]\n예: /remove 005930", chat_id=chat_id)
            return

        if _is_admin_chat(chat_id):
            if remove_from_watchlist(ticker):
                send_message(f"감시 종목 제거: ({ticker})", chat_id=chat_id)
                logger.info("종목 제거: %s", ticker)
            else:
                send_message(f"감시 목록에 없는 종목입니다: ({ticker})", chat_id=chat_id)
        else:
            if remove_from_user_watchlist(chat_id, ticker):
                send_message(f"내 종목 제거: ({ticker})", chat_id=chat_id)
                logger.info("구독자 종목 제거: chat_id=%s, %s", chat_id, ticker)
            else:
                send_message(f"내 목록에 없는 종목입니다: ({ticker})", chat_id=chat_id)

    def _cmd_list(self, chat_id: str) -> None:
        """/list — 감시 종목 목록 표시."""
        from storage.db import get_active_watchlist, get_user_watchlist

        if _is_admin_chat(chat_id):
            watchlist = get_active_watchlist()
            title = "감시 종목 목록"
        else:
            watchlist = get_user_watchlist(chat_id)
            title = "내 감시 종목"

        if not watchlist:
            msg = "감시 중인 종목이 없습니다."
            if not _is_admin_chat(chat_id):
                msg += "\n/add 005930 삼성전자 로 종목을 추가하세요."
            send_message(msg, chat_id=chat_id)
            return

        lines = [f"<b>[{title}]</b>", ""]
        for i, (ticker, name) in enumerate(watchlist, 1):
            lines.append(f"{i}. {name} ({ticker})")
        lines.append(f"\n총 {len(watchlist)}개 종목")
        send_message("\n".join(lines), chat_id=chat_id)

    def _cmd_status(self, chat_id: str) -> None:
        """/status 명령 처리."""
        lines = ["<b>[Signalight 상태]</b>", ""]

        if _is_admin_chat(chat_id):
            with _trading_lock:
                enabled = _trading_enabled
            status_label = "활성" if enabled else "비활성 (긴급 정지)"

            with self._pending_lock:
                pending_count = len(self._pending_trades)
                pending_tickers = list(self._pending_trades.keys())

            lines.append(f"거래 상태: <b>{status_label}</b>")
            lines.append(f"대기 중인 확인 요청: {pending_count}건")
            if pending_tickers:
                lines.append(f"대기 종목: {', '.join(pending_tickers)}")

            from storage.db import get_active_subscribers
            subs = get_active_subscribers()
            lines.append(f"구독자: {len(subs)}명")
        else:
            from storage.db import get_user_watchlist
            watchlist = get_user_watchlist(chat_id)
            lines.append(f"내 감시 종목: {len(watchlist)}개")
            if watchlist:
                names = ", ".join(name for _, name in watchlist)
                lines.append(f"종목: {names}")

        send_message("\n".join(lines), chat_id=chat_id)

    def _cmd_scan(self, chat_id: str) -> None:
        """/scan 명령 처리. 수동 시장 스캔을 트리거한다."""
        send_message("수동 스캔을 시작합니다. 잠시 후 결과를 전송합니다...")
        logger.info("/scan 명령: 수동 시장 스캔 요청")

        # 스캔은 별도 스레드에서 실행해 polling 루프를 블로킹하지 않는다
        scan_thread = threading.Thread(
            target=self._run_manual_scan,
            name="manual-scan",
            daemon=True,
        )
        scan_thread.start()

    def _run_manual_scan(self) -> None:
        """수동 시장 스캔을 실행하고 결과를 전송한다."""
        try:
            # main.py의 check_signals와 동일한 흐름을 따른다
            from data.fetcher import fetch_stock_data, fetch_vix
            from data.investor import fetch_investor_trading
            from signals.strategy import analyze_detailed
            from bot.formatter import format_signal_alert
            from storage.db import get_active_watchlist
            from config import WATCH_LIST as _CONFIG_WATCH_LIST

            # DB 우선, config 폴백
            try:
                watchlist = get_active_watchlist() or _CONFIG_WATCH_LIST
            except Exception:
                watchlist = _CONFIG_WATCH_LIST

            # VIX 1회 조회
            vix_value = None
            try:
                vix_series = fetch_vix()
                if not vix_series.empty:
                    vix_value = float(vix_series.iloc[-1])
            except Exception:
                pass

            stock_data_list = []
            for ticker, name in watchlist:
                try:
                    df = fetch_stock_data(ticker)
                    if df.empty:
                        continue
                    investor_df = None
                    try:
                        investor_df = fetch_investor_trading(ticker)
                    except Exception:
                        pass
                    data = analyze_detailed(df, ticker, name, investor_df=investor_df, vix_value=vix_value)
                    stock_data_list.append(data)
                except Exception as e:
                    logger.error("수동 스캔 중 오류 [%s]: %s", ticker, e)

            if stock_data_list:
                message = format_signal_alert(stock_data_list)
                send_message(message)
            else:
                send_message("수동 스캔: 데이터를 수집하지 못했습니다.")
        except Exception as e:
            logger.error("수동 스캔 실행 오류: %s", e)
            send_message(f"수동 스캔 오류: {e}")

    # ── 콜백 핸들러 ───────────────────────────

    def _handle_callback(self, callback_query: Dict) -> None:
        """인라인 키보드 콜백 쿼리를 처리한다."""
        query_id = callback_query.get("id", "")
        data = callback_query.get("data", "")

        logger.info("콜백 수신: %s", data)

        if data.startswith("confirm_trade:"):
            ticker = data.split(":", 1)[1]
            self._confirm_trade(query_id, ticker)

        elif data.startswith("reject_trade:"):
            ticker = data.split(":", 1)[1]
            self._reject_trade(query_id, ticker)

        else:
            logger.warning("알 수 없는 콜백 데이터: %s", data)
            _answer_callback(query_id, "알 수 없는 요청")

    def _confirm_trade(self, query_id: str, ticker: str) -> None:
        """거래 확인 콜백을 처리한다."""
        with self._pending_lock:
            order_data = self._pending_trades.pop(ticker, None)

        if order_data is None:
            _answer_callback(query_id, "이미 처리된 요청입니다.")
            logger.warning("confirm_trade: 대기 주문 없음 — ticker=%s", ticker)
            return

        _answer_callback(query_id, "실행 승인")

        name = order_data.get("name", ticker)
        side = order_data.get("side", "")
        quantity = order_data.get("quantity", 0)
        price = order_data.get("price", 0)
        side_label = "매수" if side == "buy" else "매도"

        logger.info("거래 승인: %s %s %d주 @%d", ticker, side_label, quantity, price)
        send_message(
            f"<b>[거래 승인]</b> {name} ({ticker})\n"
            f"{side_label} {quantity:,}주 @ {price:,}원\n"
            f"주문이 실행됩니다."
        )

        # 실제 주문 실행 콜백이 order_data에 포함된 경우 호출
        execute_fn = order_data.get("execute_fn")
        if callable(execute_fn):
            try:
                execute_fn(order_data)
            except Exception as e:
                logger.error("주문 실행 오류 [%s]: %s", ticker, e)
                send_message(f"<b>[주문 오류]</b> {name} ({ticker}): {e}")

    def _reject_trade(self, query_id: str, ticker: str) -> None:
        """거래 거부 콜백을 처리한다."""
        with self._pending_lock:
            order_data = self._pending_trades.pop(ticker, None)

        if order_data is None:
            _answer_callback(query_id, "이미 처리된 요청입니다.")
            logger.warning("reject_trade: 대기 주문 없음 — ticker=%s", ticker)
            return

        _answer_callback(query_id, "거래 거부됨")

        name = order_data.get("name", ticker)
        side = order_data.get("side", "")
        side_label = "매수" if side == "buy" else "매도"

        logger.info("거래 거부: %s %s", ticker, side_label)
        send_message(
            f"<b>[거래 거부]</b> {name} ({ticker})\n"
            f"{side_label} 주문이 취소되었습니다."
        )
