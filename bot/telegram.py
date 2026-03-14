import logging
import time
import requests
from typing import List

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger("signalight.telegram")

MAX_RETRIES = 3

TELEGRAM_MAX_LENGTH = 4096


def _split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> List[str]:
    """긴 메시지를 max_length 이하로 분할한다. 줄 단위로 분할."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        # 한 줄이 max_length를 초과하면 강제 분할
        if len(line) + 1 > max_length:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(line), max_length):
                chunks.append(line[i:i + max_length])
            continue

        if len(current) + len(line) + 1 > max_length:
            chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line

    if current:
        chunks.append(current)

    return chunks


def send_message(text: str, chat_id: str = None, bot_token: str = None) -> bool:
    """텔레그램으로 메시지를 보낸다. 4096자 초과 시 자동 분할 전송.

    Args:
        text: 전송할 메시지 (HTML 파싱).
        chat_id: 대상 chat_id. None이면 기본 TELEGRAM_CHAT_ID 사용.
        bot_token: 봇 토큰. None이면 기본 TELEGRAM_BOT_TOKEN 사용.
    """
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    token = bot_token or TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    chunks = _split_message(text)
    all_ok = True

    for chunk in chunks:
        payload = {
            "chat_id": target_chat_id,
            "text": chunk,
            "parse_mode": "HTML",
        }
        sent = False
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.ok:
                    sent = True
                    break
                logger.warning("텔레그램 전송 실패 (시도 %d/%d): %s %s", attempt + 1, MAX_RETRIES, resp.status_code, resp.text)
            except requests.RequestException as e:
                logger.warning("텔레그램 요청 오류 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s
        if not sent:
            all_ok = False

    return all_ok
