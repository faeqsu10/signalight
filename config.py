import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 감시할 종목 리스트 (종목코드, 종목명)
WATCH_LIST = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
]

# 시그널 설정
SHORT_MA = 5       # 단기 이동평균 (5일)
LONG_MA = 20       # 장기 이동평균 (20일)
RSI_PERIOD = 14    # RSI 기간
RSI_OVERSOLD = 30  # RSI 과매도 기준
RSI_OVERBOUGHT = 70  # RSI 과매수 기준
DATA_PERIOD_DAYS = 60  # 데이터 조회 기간 (일)
