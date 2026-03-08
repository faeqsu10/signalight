# Signalight

> **GitHub**: https://github.com/faeqsu10/signalight
> **웹 대시보드**: https://signalight.vercel.app

한국/미국 주식 매매 시그널 분석 시스템. 기술적 지표 + 수급 + 뉴스 감성을 종합하여 매수/매도 타이밍을 알려줍니다.

## 기능

- **텔레그램 봇** — 평일 장중 30분마다 시그널 체크, 일일 브리핑(16:00), 주간 리포트(금 16:30)
- **웹 대시보드** — Next.js 기반 실시간 캔들차트 + RSI/MACD + 시그널 패널
- **뉴스 감성 분석** — Google Gemini로 네이버 금융 뉴스 감성 자동 분석
- **회복 분석** — 급락 종목 바닥 시그널 체크리스트 (6항목 가중 점수) + 포지션 진단
- **백테스팅** — CLI로 과거 데이터 기반 전략 검증

## 분석 지표

| 카테고리 | 지표 |
|---------|------|
| 기술적 | MA 10/50 골든/데드크로스, Wilder's RSI, MACD, 볼린저밴드, OBV |
| 거래량 | 평균 대비 거래량 비율 + 시그널 확인 (1.5x↑ 강화, 0.5x↓ 경고) |
| 수급 | 외인/기관 연속 순매수·순매도 (가중치 1.5x) |
| 시장 | VIX 공포지수 |
| 뉴스 | Google Gemini 감성 분석 (긍정/부정/중립 + 신뢰도) |
| 회복 | RSI 극단 과매도, BB 하단밴드 복귀, 거래량 급증, OBV 다이버전스, 기관 매수 전환 |

## 프로젝트 구조

```
signalight/
├── config.py              # 설정 (종목, 지표 파라미터, API 키)
├── main.py                # 진입점 + 스케줄러
├── data/
│   ├── fetcher.py         # pykrx KRX OHLCV 데이터 수집
│   ├── investor.py        # 네이버 금융 외인/기관 순매수 크롤링
│   └── news.py            # 네이버 금융 종목별 뉴스 크롤링
├── signals/
│   ├── indicators.py      # 기술적 지표 (MA, RSI, MACD, BB, OBV, 거래량)
│   ├── strategy.py        # 시그널 판단 + 합류 점수
│   ├── recovery.py        # 회복 시그널 분석 (체크리스트 + 포지션 진단)
│   └── sentiment.py       # Google Gemini 뉴스 감성 분석
├── bot/
│   ├── telegram.py        # 텔레그램 메시지 전송
│   ├── formatter.py       # 메시지 포맷터 (시그널, 브리핑, 리포트)
│   └── interactive.py     # 텔레그램 인터랙티브 (/stop, /status, /scan)
├── trading/
│   ├── kiwoom_client.py   # 키움 REST API 래퍼
│   ├── executor.py        # 주문 실행 + 안전장치 (dry-run 기본)
│   └── portfolio.py       # 포트폴리오 비중 관리
├── scanner/
│   └── market_scanner.py  # KRX 종목 스캐너 (골든크로스, RSI, 거래량)
├── backtest/
│   ├── engine.py          # 백테스트 엔진
│   ├── report.py          # 리포트 생성
│   └── runner.py          # CLI 러너
└── web/                   # Next.js 웹 대시보드
    ├── app/
    │   ├── page.tsx       # 메인 대시보드
    │   └── api/           # API Routes
    ├── components/        # 차트 컴포넌트
    └── lib/               # 지표/전략 (TS 포팅)
```

## 설치

```bash
# Python 의존성
pip install pykrx python-telegram-bot schedule python-dotenv requests lxml

# 웹 대시보드
cd web && npm install
```

## 환경변수 (.env)

```env
# 필수
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# 뉴스 감성 분석 (선택 — 없으면 감성 분석 건너뜀)
GOOGLE_API_KEY=your_google_api_key

# 키움 REST API (선택 — 자동매매 기능)
TRADING_ENV=mock
KIWOOM_REST_API_KEY=your_kiwoom_key
KIWOOM_REST_API_SECRET=your_kiwoom_secret
KIWOOM_ACCOUNT_NO=5012345678
```

## 실행

```bash
# 텔레그램 봇 (스케줄러)
python3 main.py

# 백테스트
python3 -m backtest.runner 005930 삼성전자 --days 365

# 웹 대시보드
cd web && npm run dev
```

## 텔레그램 명령어

| 명령어 | 설명 |
|--------|------|
| `/help` | 사용 가능한 명령어 목록 |
| `/status` | 현재 거래 상태 및 대기 주문 요약 |
| `/scan` | 수동 시장 스캔 트리거 |
| `/list` | 현재 감시 종목 목록 표시 |
| `/add 종목코드 종목명` | 감시 종목 추가 (예: `/add 005930 삼성전자`) |
| `/remove 종목코드` | 감시 종목 제거 (예: `/remove 005930`) |
| `/stop` | 긴급 정지 (거래 비활성화) |
| `/start` | 거래 재개 |

## 자동매매 (키움 모의투자)

키움증권 REST API를 통한 자동매매 기능 (기본값: dry-run 모드).

- **dry-run 모드** (기본): 실제 주문 없이 시뮬레이션만 수행
- **모의투자**: `TRADING_ENV=mock`으로 키움 모의투자 연동
- **안전장치**: 일일 손실 한도 3%, 단일 종목 비중 30% 제한
- **인라인 키보드**: 매매 시그널 발생 시 텔레그램에서 확인/거부 선택

## 웹 스크리너

웹 대시보드에서 감시 종목의 기술적 스크리닝 결과를 실시간 표시:
- **골든크로스**: MA10이 MA50을 상향 돌파한 종목
- **RSI 과매도**: RSI < 30 종목
- **거래량 급증**: 20일 평균 대비 3배 이상 거래량

> 본 정보는 기술적 지표 기반 스크리닝 결과이며, 투자 추천이 아닙니다.

## 종목 스캐너

KRX 전체 종목 중 조건 충족 종목을 자동 탐지:
- **골든크로스**: MA10이 MA50을 상향 돌파한 종목
- **RSI 과매도**: RSI < 30 종목
- **거래량 급증**: 20일 평균 대비 3배 이상 거래량

## 회복 분석

급락한 종목의 바닥 신호를 6가지 기술적 지표로 체크합니다.

| 체크 항목 | 가중치 | 설명 |
|-----------|--------|------|
| RSI 극단 과매도 | 1.5 | RSI < 20 (극단적 과매도 구간) |
| RSI 과매도 이탈 | 1.5 | RSI가 30 이하에서 30 이상으로 복귀 |
| BB 하단밴드 복귀 | 1.5 | 볼린저밴드 하단 터치 후 반등 |
| 거래량 급증 (투매) | 1.5 | 20일 평균 대비 3배 이상 거래량 |
| OBV 상승 다이버전스 | 1.5 | 가격 하락 + OBV 상승 (매집 신호) |
| 기관 매수 전환 | 1.0 | 기관 3일 연속 순매수 |

**점수 해석** (0-10):
- 9-10: 강한 회복 신호 (다수 바닥 지표 확인)
- 6-8: 복수 바닥 신호 (일부 조건 충족)
- 3-5: 초기 바닥 신호 (아직 하락 중일 수 있음)
- 0-2: 회복 신호 미감지

**내 포지션 진단**: 매수가를 입력하면 현재 시그널과 손익률을 조합한 맞춤 액션 가이드를 제공합니다.

> 본 분석은 기술적 지표 기반 현황 판단이며, 투자 추천이 아닙니다.

## Docker 배포

```bash
# 빌드 및 실행
docker compose up -d

# 로그 확인
docker compose logs -f bot
```

`.env` 파일을 프로젝트 루트에 생성한 후 실행하세요.

## systemd 서비스 (자동 실행)

```bash
# 서비스 상태 확인
systemctl --user status signalight

# 재시작
systemctl --user restart signalight

# 로그 보기
journalctl --user -u signalight -f
```

## 텔레그램 알림 예시

```
━━━━━━━━━━━━━━━━━━━
삼성전자 (005930) | 🟢 매수
━━━━━━━━━━━━━━━━━━━
현재가: 58,000원 🔴 (+1.5%)

[트리거] 골든크로스
 • MA10이 MA50 상향 돌파 [거래량 확인 ↑]

[보조 지표]
 • RSI: 45.2 (중립)
 • MACD: 히스토그램 양전환 (+120.5)
 • 거래량: 평균 대비 130%

[뉴스 감성] 🟢 긍정 (신뢰도 85%)
 • HBM4 양산 본격화, AI 반도체 수요 증가 전망

[합류 점수] 3/5 (매수 우세)
```

## 설정 커스터마이즈 (config.py)

```python
# 감시 종목 (기본 10종목, 5+ 섹터 분산)
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
# 또는 텔레그램에서 /add, /remove로 동적 관리 (SQLite DB 저장)

# 지표 파라미터 조정
SHORT_MA = 10       # 단기 이동평균
LONG_MA = 50        # 장기 이동평균
RSI_PERIOD = 14     # RSI 기간
RSI_OVERSOLD = 30   # RSI 과매도 기준
RSI_OVERBOUGHT = 70 # RSI 과매수 기준

# 감성 분석 모델
SENTIMENT_MODEL = "gemini-2.5-flash"
```

## 라이선스

MIT
