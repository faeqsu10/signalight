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

# Stochastic RSI 설정
STOCH_RSI_PERIOD = 14
STOCH_RSI_SMOOTH_K = 3
STOCH_RSI_SMOOTH_D = 3
STOCH_RSI_OVERSOLD = 20
STOCH_RSI_OVERBOUGHT = 80
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

# ──────────────────────────────────────────────
# 매매 추천 룰 설정
# ──────────────────────────────────────────────

# 매수 진입 — 레짐별 합류 점수 임계값
ENTRY_THRESHOLD_UPTREND = 2.5   # 상승장: 낮은 기준 (추세가 이미 우호적)
ENTRY_THRESHOLD_SIDEWAYS = 3.5  # 횡보장: 표준 기준
ENTRY_THRESHOLD_DOWNTREND = 4.5 # 하락장: 높은 기준 (역추세 진입은 강한 근거 필요)

# 매수 진입 — 거래량 필터
MIN_VOLUME_RATIO = 0.7  # 최소 거래량 비율 (평균 대비 70% 이상)

# 분할 매수 설정
SPLIT_BUY_PHASES = 3         # 분할 매수 단계 수
SPLIT_BUY_CONFIRM_DAYS = 2   # Phase 2 확인 대기 일수
SPLIT_BUY_PHASE3_BONUS = 1.0 # Phase 3 진입 추가 점수 기준

# 매도 — 손절 ATR 배수 (레짐별)
STOP_LOSS_ATR_UPTREND = 2.5   # 상승장: 넓은 손절 (추세에 여유)
STOP_LOSS_ATR_SIDEWAYS = 2.0  # 횡보장: 표준
STOP_LOSS_ATR_DOWNTREND = 1.5 # 하락장: 좁은 손절 (빠른 탈출)
MAX_LOSS_PCT = 8.0             # 최대 손실 하드캡 (%)

# 매도 — 목표가 ATR 배수
TARGET1_ATR_MULT = 2.0  # 1차 목표 (1/3 매도)
TARGET2_ATR_MULT = 3.5  # 2차 목표 (1/3 매도)

# 매도 — 트레일링 스탑
TRAILING_STOP_ATR_MULT = 1.5  # 트레일링 ATR 배수

# 매도 — 시간 제한
MAX_HOLDING_DAYS = 20  # 최대 보유 거래일

# 포트폴리오 리스크 관리
MAX_POSITIONS = 5              # 최대 동시 보유 종목 수
MAX_EXPOSURE_PCT = 70.0        # 최대 총 투자 비중 (%)
MAX_SECTOR_POSITIONS = 2       # 같은 섹터 최대 보유 수
TARGET_WEIGHT_PCT = 10.0       # 종목당 목표 비중 (%)
MAX_SINGLE_POSITION_PCT = 15.0 # 종목당 최대 비중 (%)

# VIX 기반 포지션 조절
VIX_POSITION_MULT_CALM = 1.0      # VIX < 15: 풀 사이즈
VIX_POSITION_MULT_NORMAL = 0.8    # VIX 15-25: 80%
VIX_POSITION_MULT_FEAR = 0.6      # VIX 25-30: 60%
VIX_POSITION_MULT_EXTREME = 0.5   # VIX > 30: 50%

# 주간 손실 한도
WEEKLY_LOSS_LIMIT_PCT = 5.0  # 주간 손실 5% 초과 시 매수 중단

# 섹터 매핑 (종목코드 → 섹터)
SECTOR_MAP = {
    "005930": "반도체", "000660": "반도체",
    "373220": "2차전지", "006400": "2차전지",
    "207940": "바이오", "068270": "바이오",
    "105560": "금융",
    "005380": "자동차",
    "035420": "IT", "035720": "IT",
}

# ──────────────────────────────────────────────
# 글로벌 매크로 데이터 설정
# ──────────────────────────────────────────────

# 매크로 가격 지표 (티커, 이름, 단위, 일간변동 임계치%)
MACRO_INDICATORS = {
    "WTI": {"ticker": "CL=F", "name": "WTI 원유", "unit": "USD/bbl", "threshold_pct": 5.0},
    "BRENT": {"ticker": "BZ=F", "name": "브렌트유", "unit": "USD/bbl", "threshold_pct": 5.0},
    "USDKRW": {"ticker": "KRW=X", "name": "원달러 환율", "unit": "KRW", "threshold_pct": 1.5},
    "US10Y": {"ticker": "^TNX", "name": "미국 10년 국채", "unit": "%", "threshold_pct": 5.0},
    "GOLD": {"ticker": "GC=F", "name": "금", "unit": "USD/oz", "threshold_pct": 3.0},
    "DXY": {"ticker": "DX-Y.NYB", "name": "달러 인덱스", "unit": "pt", "threshold_pct": 1.5},
}

# 매크로 시그널 합류점수 최대 기여 (기술적 시그널 압도 방지)
MACRO_SIGNAL_MAX_SCORE = 1.5

# 매크로 캐시 TTL (초)
MACRO_CACHE_TTL = 14400  # 4시간

# 매크로 이벤트 → 섹터 영향 매핑
# 각 이벤트는 수혜 섹터(buy)와 피해 섹터(sell)를 정의
MACRO_SECTOR_IMPACT = {
    "oil_surge": {
        "buy": ["에너지", "정유", "조선"],
        "sell": ["항공", "운송", "화학"],
    },
    "oil_crash": {
        "buy": ["항공", "운송", "화학"],
        "sell": ["에너지", "정유"],
    },
    "fx_krw_weak": {
        "buy": ["반도체", "자동차", "조선"],  # 수출 수혜
        "sell": ["항공", "여행"],              # 원가 부담
    },
    "fx_krw_strong": {
        "buy": ["항공", "여행", "내수"],
        "sell": ["반도체", "자동차"],          # 수출 불리
    },
    "rate_hike": {
        "buy": ["금융", "보험"],
        "sell": ["성장주", "IT", "2차전지", "바이오"],
    },
    "rate_cut": {
        "buy": ["성장주", "IT", "2차전지", "바이오"],
        "sell": ["금융"],
    },
    "gold_surge": {
        "buy": ["금광", "안전자산"],
        "sell": [],
    },
    "dollar_strong": {
        "buy": ["반도체", "자동차"],  # 수출 수혜 (원화 약세 동반)
        "sell": ["내수"],
    },
}

# 매크로 이벤트 판단 기준 (지표 키 → 이벤트 매핑)
MACRO_EVENT_RULES = {
    "WTI": {
        "surge_pct": 5.0,    # 일간 +5% → oil_surge
        "crash_pct": -5.0,   # 일간 -5% → oil_crash
        "surge_event": "oil_surge",
        "crash_event": "oil_crash",
    },
    "USDKRW": {
        "surge_pct": 1.5,    # 일간 +1.5% → fx_krw_weak (원화 약세)
        "crash_pct": -1.5,   # 일간 -1.5% → fx_krw_strong (원화 강세)
        "surge_event": "fx_krw_weak",
        "crash_event": "fx_krw_strong",
    },
    "US10Y": {
        "surge_pct": 5.0,    # 일간 +5% (금리 상승) → rate_hike
        "crash_pct": -5.0,   # 일간 -5% (금리 하락) → rate_cut
        "surge_event": "rate_hike",
        "crash_event": "rate_cut",
    },
    "GOLD": {
        "surge_pct": 3.0,
        "crash_pct": -3.0,
        "surge_event": "gold_surge",
        "crash_event": None,
    },
    "DXY": {
        "surge_pct": 1.5,
        "crash_pct": -1.5,
        "surge_event": "dollar_strong",
        "crash_event": None,
    },
}
