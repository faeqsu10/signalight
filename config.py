import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Claude AI API (뉴스 감성 분석)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 키움 REST API (외인/기관 매매동향 등)
KIWOOM_REST_API_KEY = os.getenv("KIWOOM_REST_API_KEY")
KIWOOM_REST_API_SECRET = os.getenv("KIWOOM_REST_API_SECRET")

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
INVESTOR_CONSEC_DAYS = 3  # 외인/기관 연속 순매수/순매도 판단 기준 (일)

# VIX 공포지수 기준
VIX_EXTREME_FEAR = 30   # 극단적 공포 (역발상 매수 기회)
VIX_FEAR = 25           # 공포 구간 (주의 필요)
VIX_EXTREME_GREED = 12  # 극단적 낙관 (과열 경고)
