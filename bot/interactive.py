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
from autonomous.commands import is_auto_trade_chat, handle_auto_command
from autonomous.us.commands import handle_us_command

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
        # AI 채팅 핸들러
        from bot.chat import ChatHandler
        self._chat_handler = ChatHandler()

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

            # 자율매매 전용 채팅 → autonomous/commands.py로 라우팅
            if is_auto_trade_chat(chat_id) and text.startswith("/"):
                parts = text.split(maxsplit=1)
                command = parts[0].lstrip("/").split("@")[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                if handle_auto_command(chat_id, command, args):
                    return
                if handle_us_command(chat_id, command, args):
                    return
                # 자율매매 전용 채팅에서 미지원 명령어
                send_message(
                    f"알 수 없는 명령어: <code>/{command}</code>\n"
                    "/help 로 사용 가능한 명령어를 확인하세요.",
                    chat_id=chat_id,
                )
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

        elif command == "ask":
            self._cmd_ask(chat_id, text)

        elif command == "score":
            self._cmd_score(chat_id, text)

        elif command == "info":
            self._cmd_info(chat_id)
            
        elif command == "us_plan":
            self._cmd_us_plan(chat_id)

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
            "/info — 자주 묻는 질문 (FAQ)",
            "/status — 현재 상태 요약",
            "/list — 내 감시 종목 목록",
            "/add [종목코드] [종목명] — 감시 종목 추가",
            "/remove [종목코드] — 감시 종목 제거",
            "/ask [질문] — AI에게 질문 (일 10회)",
            "/score [종목명] — 합류점수 분해 보기",
            "/us_plan — 미국 빅테크 매수 전략",
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

    # ── FAQ 데이터 ──────────────────────────────

    _FAQ = {
        "what": (
            "<b>Signalight이 뭔가요?</b>\n"
            "\n"
            "한국 주식 매매 시그널(매수/매도 타이밍)을 자동 분석해서\n"
            "텔레그램으로 알림을 보내주는 봇입니다.\n"
            "\n"
            "• 자동매매 ❌ → 자동알림 ✅\n"
            "• 실제 주문은 하지 않으며, 참고용 시그널만 제공합니다."
        ),
        "signals": (
            "<b>어떤 시그널이 오나요?</b>\n"
            "\n"
            "🟢 <b>매수 시그널</b>\n"
            "• 골든크로스 (단기MA가 장기MA 상향 돌파)\n"
            "• RSI 과매도 (30 이하)\n"
            "• MACD 상향 교차\n"
            "• 외인/기관 연속 순매수\n"
            "\n"
            "🔴 <b>매도 시그널</b>\n"
            "• 데드크로스 (단기MA가 장기MA 하향 돌파)\n"
            "• RSI 과매수 (70 이상)\n"
            "• MACD 하향 교차\n"
            "• 외인/기관 연속 순매도\n"
            "\n"
            "여러 지표가 동시에 같은 방향이면 합류 점수가 높아져\n"
            "더 강한 시그널로 판단합니다."
        ),
        "schedule": (
            "<b>알림은 언제 오나요?</b>\n"
            "\n"
            "📋 <b>평일 스케줄</b>\n"
            "• 09:00 — 헬스체크 (봇 정상 동작 확인)\n"
            "• 09:30~15:30 — 30분마다 시그널 체크\n"
            "  → 시그널 발생 시에만 알림\n"
            "• 16:00 — 일일 브리핑 (전 종목 요약)\n"
            "• 금요일 16:30 — 주간 리포트\n"
            "\n"
            "⚠️ 주말/공휴일에는 알림이 오지 않습니다."
        ),
        "howto": (
            "<b>사용법</b>\n"
            "\n"
            "1️⃣ <b>등록</b>\n"
            "/register 닉네임\n"
            "\n"
            "2️⃣ <b>종목 추가</b>\n"
            "/add 005930 삼성전자\n"
            "/add 035420 NAVER\n"
            "\n"
            "3️⃣ <b>종목 제거</b>\n"
            "/remove 005930\n"
            "\n"
            "4️⃣ <b>내 종목 확인</b>\n"
            "/list\n"
            "\n"
            "추가한 종목에 시그널이 발생하면 자동으로 알림이 옵니다!"
        ),
        "codes": (
            "<b>주요 종목코드</b>\n"
            "\n"
            "005930 — 삼성전자\n"
            "000660 — SK하이닉스\n"
            "373220 — LG에너지솔루션\n"
            "006400 — 삼성SDI\n"
            "207940 — 삼성바이오로직스\n"
            "068270 — 셀트리온\n"
            "105560 — KB금융\n"
            "005380 — 현대차\n"
            "035420 — NAVER\n"
            "035720 — 카카오\n"
            "\n"
            "종목코드는 네이버 증권에서 확인할 수 있습니다."
        ),
        "disclaimer": (
            "<b>면책사항</b>\n"
            "\n"
            "⚠️ Signalight은 투자 참고용 도구입니다.\n"
            "\n"
            "• 투자 판단의 최종 책임은 본인에게 있습니다\n"
            "• 시그널은 기술적 지표 기반이며 100% 정확하지 않습니다\n"
            "• 과거 시그널이 미래 수익을 보장하지 않습니다\n"
            "• 본 서비스로 인한 투자 손실에 책임지지 않습니다"
        ),
        "confluence": (
            "<b>합류점수란?</b>\n"
            "\n"
            "\"살 때인가?\" \"팔 때인가?\"를 판단하는 종합점수예요.\n"
            "9개 항목을 체크해서, 같은 방향이 많을수록 점수가 높아져요.\n"
            "\n"
            "<b>체크하는 9가지:</b>\n"
            "\n"
            "📈 <b>가격 흐름 (4개)</b>\n"
            "① 이동평균선 — 단기선이 장기선을 뚫고 올라가면 매수\n"
            "② RSI — 주가가 많이 빠져서 \"너무 싸다\" 구간이면 매수\n"
            "③ MACD — 추세 전환 신호가 나오면 매수/매도\n"
            "④ 볼린저밴드 — 평소 가격 범위를 벗어나면 반등/조정 신호\n"
            "\n"
            "📊 <b>거래량 (2개)</b>\n"
            "⑤ OBV — 주가는 빠지는데 거래량이 늘면 \"누가 모으는 중\"\n"
            "⑥ StochRSI — RSI를 한번 더 분석해서 바닥/천장을 정밀 포착\n"
            "\n"
            "💰 <b>외부 환경 (3개)</b>\n"
            "⑦ VIX — 시장이 공포에 빠지면 오히려 매수 기회\n"
            "⑧ 외국인 — 3일 연속 사고 있으면 매수 신호\n"
            "⑨ 기관 — 3일 연속 사고 있으면 매수 신호\n"
            "\n"
            "<b>점수 읽는 법:</b>\n"
            "• <b>3.5 이상</b> → 강한 신호! 여러 지표가 한 방향\n"
            "• <b>1.5 이상</b> → 신호 있음\n"
            "• <b>1.5 미만</b> → 뚜렷한 방향 없음\n"
            "\n"
            "점수가 높다 = 더 많은 근거가 모였다는 뜻이에요.\n"
            "단, 높은 점수가 100% 수익을 보장하지는 않습니다!\n"
            "\n"
            "/score 삼성전자 — 지금 점수 확인해보기"
        ),
    }

    def _cmd_ask(self, chat_id: str, text: str) -> None:
        """/ask [질문] — AI에게 질문. 별도 스레드에서 처리."""
        ask_thread = threading.Thread(
            target=self._chat_handler.handle,
            args=(chat_id, text),
            name="ai-chat",
            daemon=True,
        )
        ask_thread.start()

    def _cmd_score(self, chat_id: str, text: str) -> None:
        """/score [종목명/코드] — 합류점수 실시간 분해 표시."""
        query = text.strip()
        if not query:
            send_message(
                "사용법: /score [종목명 또는 종목코드]\n"
                "예: /score 삼성전자\n"
                "예: /score 005930",
                chat_id=chat_id,
            )
            return

        # 별도 스레드에서 실행 (데이터 조회가 느릴 수 있음)
        score_thread = threading.Thread(
            target=self._run_score,
            args=(chat_id, query),
            name="score-query",
            daemon=True,
        )
        score_thread.start()

    def _run_score(self, chat_id: str, query: str) -> None:
        """합류점수 분해를 조회하여 메시지를 전송한다."""
        try:
            from data.fetcher import fetch_stock_data, fetch_vix
            from data.investor import fetch_investor_trading
            from signals.strategy import analyze_detailed
            from config import WATCH_LIST as _CONFIG_WATCH_LIST
            from storage.db import get_active_watchlist

            # 종목 찾기
            try:
                watchlist = get_active_watchlist() or _CONFIG_WATCH_LIST
            except Exception:
                watchlist = _CONFIG_WATCH_LIST

            ticker = None
            name = None

            # 1. 종목코드 직접 매칭
            for t, n in watchlist:
                if t == query:
                    ticker, name = t, n
                    break

            # 2. 종목명 매칭
            if not ticker:
                for t, n in watchlist:
                    if query in n or n in query:
                        ticker, name = t, n
                        break

            # 3. 별칭 매칭
            if not ticker:
                from bot.chat import _ALIASES
                query_lower = query.lower()
                for alias, code in _ALIASES.items():
                    if alias in query_lower:
                        for t, n in watchlist:
                            if t == code:
                                ticker, name = t, n
                                break
                        break

            if not ticker:
                send_message(
                    f"'{query}'에 해당하는 종목을 찾을 수 없습니다.\n"
                    "/list 로 감시 종목을 확인하세요.",
                    chat_id=chat_id,
                )
                return

            # 데이터 조회
            df = fetch_stock_data(ticker)
            if df.empty:
                send_message(f"{name}({ticker}) 데이터를 조회할 수 없습니다.", chat_id=chat_id)
                return

            investor_df = None
            try:
                investor_df = fetch_investor_trading(ticker)
            except Exception:
                pass

            vix_value = None
            try:
                vix_series = fetch_vix()
                if not vix_series.empty:
                    vix_value = float(vix_series.iloc[-1])
            except Exception:
                pass

            data = analyze_detailed(df, ticker, name, investor_df=investor_df, vix_value=vix_value)

            # 메시지 구성
            regime_labels = {
                "uptrend": "📈 상승장",
                "downtrend": "📉 하락장",
                "sideways": "➡️ 횡보장",
            }
            regime = data.get("market_regime", "sideways")
            regime_label = regime_labels.get(regime, "➡️ 횡보장")

            lines = [
                f"<b>[{name} 합류점수]</b>",
                f"현재가: {data.get('price', 0):,}원 ({data.get('change_pct', 0):+.1f}%)",
                f"시장 분위기: {regime_label}",
                "",
            ]

            # 지표별 해석 매핑
            _easy_explain = {
                "골든크로스": "단기선이 장기선을 뚫고 올라감 → 상승 전환",
                "데드크로스": "단기선이 장기선 아래로 내려감 → 하락 전환",
                "RSI 과매도": "많이 빠져서 '너무 싸다' 구간 → 반등 가능",
                "RSI 과매수": "많이 올라서 '너무 비싸다' 구간 → 조정 가능",
                "MACD 매수": "추세 전환 신호 → 상승 추세 시작",
                "MACD 매도": "추세 전환 신호 → 하락 추세 시작",
                "볼린저밴드 하단": "평소 가격 범위 아래로 이탈 → 반등 가능",
                "볼린저밴드 상단": "평소 가격 범위 위로 이탈 → 과열 주의",
                "OBV 상승 다이버전스": "주가↓ 거래량↑ → 누군가 모으는 중",
                "StochRSI 과매도": "정밀 지표도 바닥 신호 → 반등 임박",
                "StochRSI 과매수": "정밀 지표도 천장 신호 → 조정 임박",
                "VIX 공포": "시장 전체가 공포 → 역발상 매수 기회",
                "VIX 주의": "시장에 불안감 있음 → 매수 기회 가능",
                "VIX 과열": "시장이 너무 낙관적 → 과열 경고",
                "외인 연속 매수": "외국인이 계속 사는 중 → 긍정적",
                "외인 연속 매도": "외국인이 계속 파는 중 → 부정적",
                "기관 연속 매수": "기관이 계속 사는 중 → 긍정적",
                "기관 연속 매도": "기관이 계속 파는 중 → 부정적",
            }

            # 시그널별 점수 분해
            signals = data.get("signals", [])
            buy_total = 0.0
            sell_total = 0.0
            buy_reasons = []
            sell_reasons = []

            if signals:
                lines.append("<b>📊 지표별 점수:</b>")
                for sig in signals:
                    sig_type = sig["type"]
                    sig_strength = sig.get("strength", 0)
                    trigger = sig["trigger"]
                    explain = _easy_explain.get(trigger, "")

                    if sig_type == "buy":
                        icon = "🟢"
                        buy_total += sig_strength if sig_strength else 0
                        score_str = f"+{sig_strength:.2f}" if sig_strength else ""
                        if explain:
                            buy_reasons.append(explain.split("→")[0].strip())
                    elif sig_type == "sell":
                        icon = "🔴"
                        sell_total += sig_strength if sig_strength else 0
                        score_str = f"-{sig_strength:.2f}" if sig_strength else ""
                        if explain:
                            sell_reasons.append(explain.split("→")[0].strip())
                    else:
                        icon = "⚪"
                        score_str = ""

                    line = f"  {icon} {trigger} {score_str}"
                    if explain:
                        line += f"\n       <i>{explain}</i>"
                    lines.append(line)
            else:
                lines.append("활성 시그널 없음")

            # 합산 + 판정
            lines.append("")
            lines.append(f"<b>매수 합계: {buy_total:.1f}  |  매도 합계: {sell_total:.1f}</b>")

            score = data.get("confluence_score", 0)
            direction = data.get("confluence_direction", "neutral")
            strength = data.get("signal_strength", "neutral")

            strength_emojis = {
                "strong_buy": "🟢🟢",
                "buy": "🟢",
                "neutral": "⚪",
                "sell": "🔴",
                "strong_sell": "🔴🔴",
            }
            strength_labels = {
                "strong_buy": "강한 매수",
                "buy": "매수",
                "neutral": "중립",
                "sell": "매도",
                "strong_sell": "강한 매도",
            }
            s_emoji = strength_emojis.get(strength, "⚪")
            s_label = strength_labels.get(strength, "중립")

            lines.append(f"\n{s_emoji} <b>판정: {s_label} (합류점수 {score})</b>")

            # 쉬운 해석 요약
            lines.append("")
            lines.append("<b>💬 쉬운 해석:</b>")

            net = buy_total - sell_total
            if strength == "strong_buy":
                lines.append("여러 지표가 한꺼번에 매수를 가리키고 있어요.")
                lines.append("강한 매수 근거가 모인 상태입니다.")
            elif strength == "buy":
                lines.append("매수 쪽 근거가 더 많은 상태예요.")
                if sell_reasons:
                    lines.append(f"다만 {', '.join(sell_reasons[:2])} 주의.")
            elif strength == "strong_sell":
                lines.append("여러 지표가 한꺼번에 매도를 가리키고 있어요.")
                lines.append("조심해야 할 상태입니다.")
            elif strength == "sell":
                lines.append("매도 쪽 근거가 더 많은 상태예요.")
                if buy_reasons:
                    lines.append(f"다만 {', '.join(buy_reasons[:2])} 긍정적.")
            else:
                # 중립/혼재
                if buy_total > 0 and sell_total > 0:
                    lines.append("매수 신호와 매도 신호가 섞여 있어요.")
                    if buy_reasons and sell_reasons:
                        lines.append(f"  👍 {', '.join(buy_reasons[:2])}")
                        lines.append(f"  👎 {', '.join(sell_reasons[:2])}")
                    lines.append("→ 한쪽으로 확실히 기울 때까지 기다리는 게 좋아요.")
                elif buy_total == 0 and sell_total == 0:
                    lines.append("뚜렷한 매수/매도 신호가 없는 상태예요.")
                    lines.append("→ 지켜보면서 변화를 기다리세요.")
                else:
                    lines.append("약한 신호만 있는 상태예요.")
                    lines.append("→ 더 많은 근거가 모일 때까지 관망 추천.")

            send_message("\n".join(lines), chat_id=chat_id)

        except Exception as e:
            logger.error("점수 조회 오류 [%s]: %s", query, e)
            send_message(f"점수 조회 중 오류가 발생했습니다: {e}", chat_id=chat_id)

    def _cmd_info(self, chat_id: str) -> None:
        """/info — FAQ 인라인 키보드 표시."""
        keyboard = [
            [
                {"text": "이게 뭔가요?", "callback_data": "faq:what"},
                {"text": "어떤 알림이 오나요?", "callback_data": "faq:signals"},
            ],
            [
                {"text": "알림 시간", "callback_data": "faq:schedule"},
                {"text": "사용법", "callback_data": "faq:howto"},
            ],
            [
                {"text": "합류점수란?", "callback_data": "faq:confluence"},
                {"text": "종목코드 목록", "callback_data": "faq:codes"},
            ],
            [
                {"text": "면책사항", "callback_data": "faq:disclaimer"},
            ],
        ]
        _send_with_keyboard(
            chat_id,
            "<b>궁금한 항목을 선택하세요 👇</b>",
            keyboard,
        )

    def _handle_faq(self, query_id: str, chat_id: str, faq_key: str) -> None:
        """FAQ 콜백을 처리한다."""
        _answer_callback(query_id)
        answer = self._FAQ.get(faq_key)
        if answer:
            send_message(answer, chat_id=chat_id)
        else:
            send_message("해당 항목을 찾을 수 없습니다.", chat_id=chat_id)

    def _cmd_us_plan(self, chat_id: str) -> None:
        """/us_plan — 미국 빅테크 분할 매수 가이드를 표시한다."""
        msg = (
            "<b>[💰 빅테크 소수점 분할 매수 가이드]</b>\n"
            "\n"
            "<b>예산:</b> 월 50만 원\n"
            "<b>전략:</b> 하락 알림 봇 연계 분할 매수 (DCA + Price Drop)\n"
            "\n"
            "<b>1. 포트폴리오 비중 (총 50만 원)</b>\n"
            "🥇 엔비디아(NVDA): 40% (20만 원)\n"
            "🥈 테슬라(TSLA): 30% (15만 원)\n"
            "🥉 팔란티어(PLTR): 20% (10만 원)\n"
            "🏅 구글(GOOGL): 10% (5만 원)\n"
            "\n"
            "<b>2. 실전 액션 플랜</b>\n"
            "<b>🔥 1단계: 즉시 기초 물량 확보 (예산 25%)</b>\n"
            "오늘 당장 소수점 투자로 담기:\n"
            "• 엔비디아 5만 원 / 테슬라 4만 원\n"
            "• 팔란티어 2.5만 원 / 구글 1만 원\n"
            "\n"
            "<b>🤖 2단계: 알림 연계 기계적 줍줍 (나머지 75%)</b>\n"
            "장중 알림이 오면 해당 종목 배정 예산 내에서 기계적 추매:\n"
            "• 👀 관망 (-10%대): 1~2만 원 투입\n"
            "• 🎯 적극 (-20%대): 2~4만 원 투입\n"
            "• 🔥 강력 (-30%이상): 5만 원 이상 투입\n"
            "\n"
            "<i>💡 알림이 일주일 내내 안 오면? 금요일 밤 남은 예산 1/3을 기계적으로 매수하세요.</i>"
        )
        send_message(msg, chat_id=chat_id)

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
        chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))

        logger.info("콜백 수신: %s", data)

        if data.startswith("faq:"):
            faq_key = data.split(":", 1)[1]
            self._handle_faq(query_id, chat_id, faq_key)

        elif data.startswith("confirm_trade:"):
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
