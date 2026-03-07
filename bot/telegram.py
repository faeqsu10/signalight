import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_message(text: str):
    """텔레그램으로 메시지를 보낸다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload)
    if not resp.ok:
        print(f"텔레그램 전송 실패: {resp.status_code} {resp.text}")
    return resp.ok
