import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Google Gemini API (뉴스 감성 분석)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 감성 분석 설정
SENTIMENT_MODEL = "gemini-2.5-flash"
SENTIMENT_TEMPERATURE = 0
SENTIMENT_MAX_TOKENS = 2048
SENTIMENT_TIMEOUT = 10  # 초

# 뉴스 크롤링 설정
NEWS_FETCH_LIMIT = 5
NEWS_TIMEOUT = 10  # 초

# 키움 REST API
KIWOOM_REST_API_KEY = os.getenv("KIWOOM_REST_API_KEY")
KIWOOM_REST_API_SECRET = os.getenv("KIWOOM_REST_API_SECRET")
KIWOOM_ACCOUNT_NO = os.getenv("KIWOOM_ACCOUNT_NO", "")
TRADING_ENV = os.getenv("TRADING_ENV", "mock")  # "mock" or "prod"

# 감시할 종목 리스트 (종목코드, 종목명) — 10종목, 5+ 섹터 분산
WATCH_LIST = [
    ("005930", "삼성전자"),       # 반도체
    ("000660", "SK하이닉스"),     # 반도체
    ("373220", "LG에너지솔루션"),  # 2차전지
    ("006400", "삼성SDI"),        # 2차전지
    ("207940", "삼성바이오로직스"),  # 바이오
    ("068270", "셀트리온"),        # 바이오
    ("105560", "KB금융"),          # 금융
    ("005380", "현대차"),          # 자동차
    ("035420", "NAVER"),          # IT/플랫폼
    ("035720", "카카오"),          # IT/플랫폼
]

# 미국 주식 감시 리스트
US_WATCH_LIST = [
    ("AAPL", "Apple"),
    ("NVDA", "NVIDIA"),
    ("TSLA", "Tesla"),
    ("MSFT", "Microsoft"),
    ("AMZN", "Amazon"),
]

# 시그널 설정
SHORT_MA = 10      # 단기 이동평균 (10일)
LONG_MA = 50       # 장기 이동평균 (50일)
RSI_PERIOD = 14    # RSI 기간
RSI_OVERSOLD = 30  # RSI 과매도 기준
RSI_OVERBOUGHT = 70  # RSI 과매수 기준
DATA_PERIOD_DAYS = 120  # 데이터 조회 기간 (일)
INVESTOR_CONSEC_DAYS = 3  # 외인/기관 연속 순매수/순매도 판단 기준 (일)

# VIX 공포지수 기준
VIX_EXTREME_FEAR = 30   # 극단적 공포 (역발상 매수 기회)
VIX_FEAR = 25           # 공포 구간 (주의 필요)
VIX_EXTREME_GREED = 12  # 극단적 낙관 (과열 경고)

# 회복 분석 설정
RECOVERY_RSI_EXTREME = 20      # RSI 극단 과매도 기준
RECOVERY_VOLUME_SPIKE = 3.0    # 투매/급등 거래량 배수 (평균 대비)
RECOVERY_LOOKBACK_DAYS = 750   # 과거 낙폭 에피소드 탐색 기간 (약 3년)
