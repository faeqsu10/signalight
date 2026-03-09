"""텔레그램 AI 채팅 핸들러 — Gemini 기반 주식 Q&A.

/ask 명령어로 자연어 질문을 받아 Gemini로 답변한다.
종목명/종목코드가 감지되면 실시간 데이터를 조회하여 컨텍스트에 포함한다.
"""

import logging
import re
import time
import threading
import requests
from typing import Dict, List, Optional, Tuple

from config import (
    GOOGLE_API_KEY, SENTIMENT_MODEL, WATCH_LIST,
)

logger = logging.getLogger("signalight")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

# ──────────────────────────────────────────────
# 시스템 프롬프트
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 Signalight 주식 분석 봇의 AI 어시스턴트입니다.
한국 주식 시장 기술적 분석 전문가로서, 사용자의 질문에 친절하고 정확하게 답변합니다.

역할:
- 기술적 지표(MA, RSI, MACD, 볼린저밴드, OBV) 설명
- 시그널 분석 결과 해석
- Signalight 시스템 사용법 안내
- 주식 용어 설명

제한:
- 투자 추천이 아닌 참고 정보만 제공합니다
- "사세요/파세요" 같은 단정적 표현은 하지 않습니다
- 답변은 간결하게 합니다 (300자 이내 권장)
- 면책사항: 투자 판단의 최종 책임은 사용자에게 있습니다

사용 가능한 봇 명령어:
/help - 도움말, /info - FAQ, /list - 내 종목, /add - 종목 추가, /remove - 종목 제거, /status - 상태, /ask - AI 질문

HTML 태그(<b>, <i>, <code>)를 사용하여 가독성 좋게 포맷하세요.
<, >, & 문자는 반드시 HTML 엔티티로 이스케이프하세요."""

# ──────────────────────────────────────────────
# 종목 별칭 매핑
# ──────────────────────────────────────────────

_ALIASES: Dict[str, str] = {
    "삼전": "005930", "삼성": "005930",
    "하닉": "000660", "하이닉스": "000660",
    "엘지에솔": "373220", "에솔": "373220",
    "삼디": "006400",
    "삼바": "207940", "삼성바이오": "207940",
    "셀트": "068270",
    "KB": "105560", "케이비": "105560",
    "현차": "005380", "현대": "005380",
    "네이버": "035420", "naver": "035420",
    "카카오": "035720", "카톡": "035720",
}

# ──────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────

class RateLimiter:
    """인당 분/일 횟수 제한."""

    def __init__(self, per_minute: int = 3, per_day: int = 30):
        self._per_minute = per_minute
        self._per_day = per_day
        self._minute_log: Dict[str, List[float]] = {}  # chat_id -> [timestamp, ...]
        self._daily_counts: Dict[str, int] = {}
        self._daily_date: str = ""
        self._lock = threading.Lock()

    def check(self, chat_id: str) -> Tuple[bool, str]:
        """허용 여부와 거부 메시지를 반환한다."""
        now = time.time()
        today = time.strftime("%Y%m%d")

        with self._lock:
            # 날짜 리셋
            if today != self._daily_date:
                self._daily_counts.clear()
                self._daily_date = today

            # 일일 한도
            daily = self._daily_counts.get(chat_id, 0)
            if daily >= self._per_day:
                return False, f"일일 질문 한도({self._per_day}회)를 초과했습니다. 내일 다시 이용해주세요."

            # 분당 한도
            timestamps = self._minute_log.get(chat_id, [])
            timestamps = [t for t in timestamps if now - t < 60]
            self._minute_log[chat_id] = timestamps

            if len(timestamps) >= self._per_minute:
                return False, f"너무 빠릅니다. 1분에 {self._per_minute}회까지 가능합니다."

            # 허용 — 기록
            timestamps.append(now)
            self._minute_log[chat_id] = timestamps
            self._daily_counts[chat_id] = daily + 1

            remaining = self._per_day - daily - 1
            return True, f"({remaining}회 남음)"

    def get_usage(self, chat_id: str) -> Tuple[int, int]:
        """(사용횟수, 일일한도)를 반환한다."""
        with self._lock:
            daily = self._daily_counts.get(chat_id, 0)
            return daily, self._per_day


# ──────────────────────────────────────────────
# ChatHandler
# ──────────────────────────────────────────────

class ChatHandler:
    """Gemini 기반 AI 채팅 핸들러."""

    def __init__(self):
        self._rate_limiter = RateLimiter(per_minute=3, per_day=10)
        # 종목 매핑 빌드 (이름 → ticker)
        self._name_to_ticker: Dict[str, str] = {}
        for ticker, name in WATCH_LIST:
            self._name_to_ticker[name] = ticker
        # DB 워치리스트도 시도
        try:
            from storage.db import get_active_watchlist
            for ticker, name in get_active_watchlist():
                self._name_to_ticker[name] = ticker
        except Exception:
            pass

    def handle(self, chat_id: str, question: str) -> None:
        """질문을 처리하고 답변을 전송한다. 별도 스레드에서 호출."""
        from bot.telegram import send_message

        if not GOOGLE_API_KEY:
            send_message("AI 채팅 기능이 설정되지 않았습니다. (API 키 미설정)", chat_id=chat_id)
            return

        question = question.strip()
        if not question:
            send_message("사용법: /ask [질문]\n예: /ask 골든크로스가 뭐야?", chat_id=chat_id)
            return

        # Rate limit 체크
        allowed, msg = self._rate_limiter.check(chat_id)
        if not allowed:
            send_message(msg, chat_id=chat_id)
            return

        # "typing..." 표시
        self._send_typing(chat_id)

        # 종목 감지 → 데이터 조회
        ticker_info = self._detect_ticker(question)
        context = ""
        if ticker_info:
            ticker, name = ticker_info
            context = self._build_stock_context(ticker, name)

        # Gemini 호출
        answer = self._call_gemini(question, context)
        if answer:
            remaining_msg = msg  # "(N회 남음)"
            send_message(f"{answer}\n\n<i>{remaining_msg}</i>", chat_id=chat_id)
        else:
            send_message("죄송합니다, 답변 생성에 실패했습니다. 잠시 후 다시 시도해주세요.", chat_id=chat_id)

    def get_usage(self, chat_id: str) -> Tuple[int, int]:
        """사용량 조회."""
        return self._rate_limiter.get_usage(chat_id)

    # ── 내부 메서드 ──────────────────────────

    def _detect_ticker(self, text: str) -> Optional[Tuple[str, str]]:
        """텍스트에서 종목을 감지한다. (ticker, name) 반환."""
        # 1. 종목코드 직접 언급
        code_match = re.search(r'\b(\d{6})\b', text)
        if code_match:
            code = code_match.group(1)
            for ticker, name in WATCH_LIST:
                if ticker == code:
                    return (ticker, name)
            # DB에서도 확인
            try:
                from storage.db import get_active_watchlist
                for ticker, name in get_active_watchlist():
                    if ticker == code:
                        return (ticker, name)
            except Exception:
                pass

        # 2. 종목명 매칭 (긴 이름 우선)
        sorted_names = sorted(self._name_to_ticker.keys(), key=len, reverse=True)
        for name in sorted_names:
            if name in text:
                return (self._name_to_ticker[name], name)

        # 3. 별칭 매칭
        text_lower = text.lower()
        for alias, ticker in _ALIASES.items():
            if alias in text_lower:
                for t, n in WATCH_LIST:
                    if t == ticker:
                        return (ticker, n)

        return None

    def _build_stock_context(self, ticker: str, name: str) -> str:
        """종목의 실시간 분석 데이터를 컨텍스트 문자열로 구성한다."""
        try:
            from data.fetcher import fetch_stock_data, fetch_vix
            from data.investor import fetch_investor_trading
            from signals.strategy import analyze_detailed

            df = fetch_stock_data(ticker)
            if df.empty:
                return f"[{name}({ticker}) 데이터 조회 실패]"

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

            indicators = data.get("indicators", {})
            signals = data.get("signals", [])
            investor = data.get("investor", {})

            lines = [
                f"[실시간 분석 데이터: {name} ({ticker})]",
                f"현재가: {data.get('price', 0):,}원 ({data.get('change_pct', 0):+.1f}%)",
            ]

            rsi = indicators.get("rsi")
            if rsi is not None:
                lines.append(f"RSI: {rsi:.1f}")

            macd_hist = indicators.get("macd_histogram")
            if macd_hist is not None:
                lines.append(f"MACD 히스토그램: {macd_hist:+.1f}")

            vol_ratio = indicators.get("volume_ratio")
            if vol_ratio is not None:
                lines.append(f"거래량 비율: 평균 대비 {int(vol_ratio * 100)}%")

            if vix_value is not None:
                lines.append(f"VIX: {vix_value:.1f}")

            foreign_net = investor.get("foreign_net")
            if foreign_net is not None:
                direction = "순매수" if foreign_net >= 0 else "순매도"
                lines.append(f"외인: {direction} {abs(foreign_net):,}주")

            inst_net = investor.get("institutional_net")
            if inst_net is not None:
                direction = "순매수" if inst_net >= 0 else "순매도"
                lines.append(f"기관: {direction} {abs(inst_net):,}주")

            score = data.get("confluence_score", 0)
            total = data.get("total_indicators", 0)
            direction = data.get("confluence_direction", "")
            if total > 0:
                lines.append(f"합류점수: {score}/{total} ({direction})")

            if signals:
                sig_strs = [f"{s['type']}:{s['trigger']}" for s in signals]
                lines.append(f"활성 시그널: {', '.join(sig_strs)}")
            else:
                lines.append("활성 시그널: 없음")

            return "\n".join(lines)

        except Exception as e:
            logger.warning("채팅 컨텍스트 빌드 실패 [%s]: %s", ticker, e)
            return f"[{name}({ticker}) 데이터 조회 중 오류 발생]"

    def _call_gemini(self, question: str, context: str = "") -> Optional[str]:
        """Gemini API를 호출하여 답변을 받는다."""
        prompt_parts = [SYSTEM_PROMPT]
        if context:
            prompt_parts.append(f"\n{context}")
        prompt_parts.append(f"\n사용자 질문: {question}")
        prompt = "\n".join(prompt_parts)

        try:
            url = GEMINI_URL.format(SENTIMENT_MODEL)
            resp = requests.post(
                url,
                params={"key": GOOGLE_API_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 1024,
                    },
                },
                timeout=15,
            )

            if resp.status_code != 200:
                logger.warning("채팅 Gemini API 오류: %d %s", resp.status_code, resp.text[:200])
                return None

            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]

            # thought 파트 스킵 (Gemini 2.5 Flash thinking 모델)
            text = ""
            for part in parts:
                if part.get("thought"):
                    continue
                text = part.get("text", "").strip()
                if text:
                    break
            if not text:
                text = parts[-1].get("text", "").strip()

            return self._sanitize_html(text) if text else None

        except requests.Timeout:
            logger.warning("채팅 Gemini 타임아웃")
            return None
        except Exception as e:
            logger.warning("채팅 Gemini 호출 실패: %s", e)
            return None

    @staticmethod
    def _sanitize_html(text: str) -> str:
        """Gemini 응답의 HTML을 텔레그램 호환으로 정리한다.

        텔레그램은 <b>, <i>, <code>, <pre> 만 허용.
        그 외 태그는 제거하고, 허용 태그의 짝이 안 맞으면 제거한다.
        """
        import html as html_lib

        # 허용 태그
        allowed = {"b", "i", "code", "pre"}

        # 1단계: 허용되지 않는 태그 제거 (내용은 유지)
        import re
        def replace_tag(match):
            full = match.group(0)
            tag_name = match.group(1).lower().strip("/")
            if tag_name in allowed:
                return full
            return ""

        cleaned = re.sub(r'<(/?\w+)[^>]*>', replace_tag, text)

        # 2단계: 열린 태그와 닫힌 태그 짝 확인
        for tag in allowed:
            open_count = len(re.findall(rf'<{tag}>', cleaned))
            close_count = len(re.findall(rf'</{tag}>', cleaned))
            if open_count != close_count:
                # 짝이 안 맞으면 해당 태그 전부 제거
                cleaned = re.sub(rf'</?{tag}>', '', cleaned)

        return cleaned

    def _send_typing(self, chat_id: str) -> None:
        """'typing...' 상태를 표시한다."""
        try:
            from config import TELEGRAM_BOT_TOKEN
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
                timeout=5,
            )
        except Exception:
            pass
