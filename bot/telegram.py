import requests
from typing import List

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

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


def send_message(text: str) -> bool:
    """텔레그램으로 메시지를 보낸다. 4096자 초과 시 자동 분할 전송."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = _split_message(text)
    all_ok = True

    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload)
        if not resp.ok:
            print(f"텔레그램 전송 실패: {resp.status_code} {resp.text}")
            all_ok = False

    return all_ok
