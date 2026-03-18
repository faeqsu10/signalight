# Signalight

> **웹 대시보드**: https://signalight-beige.vercel.app

한국/미국 주식 매매 시그널 분석 + 자율 트레이딩 시스템.
기술적 지표, 수급, 매크로, 뉴스 감성을 종합하여 매수/매도 타이밍을 분석합니다.

## 협업 원칙

- 코드 작성 에이전트와 리뷰/테스트/검증 에이전트는 분리한다.
- 코드 작성 에이전트가 자신의 변경을 직접 리뷰하거나 최종 검증하지 않는다.
- 이 역할 분리 원칙은 항상 적용한다.
- 역할 정의 문서:
  - `docs/agents/implementer.md`
  - `docs/agents/reviewer.md`
  - `docs/agents/verifier.md`

## 주요 기능

### 텔레그램 봇
- 평일 장중 30분마다 시그널 체크 (KR 10종목 + US 30종목)
- 일일 브리핑 (16:00) + 주간 리포트 (금 16:30)
- 인터랙티브 명령어 (`/scan`, `/add`, `/remove`, `/score`, `/info`)
- 뉴스 감성 분석 (Google Gemini) + AI 종합 판단

### 자율 트레이딩
- **한국 (KR)**: 키움증권 REST API 모의투자 (KOSPI200 복합 스캔)
- **미국 (US)**: Alpaca Paper Trading (S&P 500 상위 30종목, 8개 섹터)
- 스캔 → 분석 → 매수/매도 → 성과 평가 → 자동 튜닝 파이프라인
- 서킷 브레이커 + 킬스위치 + 일일/주간 손실 한도
- 텔레그램 리포트 (스캔 요약, 일일 성과, 매매 알림)

### 웹 대시보드
- Next.js 14 기반 실시간 캔들차트 + RSI/MACD/볼린저밴드
- 종목 스크리너 (골든크로스, RSI 과매도, 거래량 급증)
- 회복 분석 (6항목 체크리스트 + 포지션 진단)
- 자율매매 대시보드 (`/autonomous` — 런타임 DB 우선, 스냅샷 fallback, 체결 시 export 자동 갱신)
- 백테스트 결과 요약 카드

## 분석 지표

| 카테고리 | 지표 |
|---------|------|
| 기술적 | MA 10/50 골든/데드크로스, Wilder's RSI, MACD, 볼린저밴드, OBV, StochRSI |
| 거래량 | 평균 대비 거래량 비율 + 시그널 확인 (1.5x 강화, 0.5x 경고) |
| 수급 | 외인/기관 연속 순매수/순매도 (가중치 1.5x) |
| 매크로 | VIX 공포지수, WTI, 환율, 금리, 금, DXY |
| 뉴스 | Google Gemini 감성 분석 + RSS 매크로 뉴스 (CNBC, Reuters, 한경) |
| 회복 | RSI 극단 과매도, BB 하단밴드 복귀, 거래량 급증, OBV 다이버전스, 기관 매수 전환 |

## 프로젝트 구조

```
signalight/
├── config.py                  # 설정 (종목, 지표, 매크로, RSS, API 키)
├── main.py                    # 진입점 + 스케줄러
├── data/
│   ├── fetcher.py             # pykrx KRX OHLCV 데이터 수집
│   ├── us_fetcher.py          # Yahoo Finance 미국 주식 OHLCV
│   ├── investor.py            # 네이버 금융 외인/기관 순매수
│   ├── macro_fetcher.py       # 글로벌 매크로 지표 (WTI/환율/금리/금/DXY)
│   ├── macro_news.py          # RSS 매크로 뉴스 수집 + 이벤트 분류
│   └── news.py                # 네이버 금융 종목별 뉴스
├── signals/
│   ├── indicators.py          # 기술적 지표 (MA, RSI, MACD, BB, OBV, 거래량)
│   ├── strategy.py            # 시그널 판단 + 합류 점수 + 시장 레짐
│   ├── recovery.py            # 회복 시그널 분석 (체크리스트 + 포지션 진단)
│   ├── sentiment.py           # Google Gemini 뉴스 감성 분석
│   └── llm_analyzer.py        # Gemini 종합 판단 (상충 시그널 해석)
├── bot/
│   ├── telegram.py            # 텔레그램 메시지 전송 (4096자 분할)
│   ├── formatter.py           # 메시지 포맷터 (시그널, 브리핑, 리포트)
│   └── interactive.py         # 텔레그램 인터랙티브 (KR + US 명령어)
├── trading/
│   ├── kiwoom_client.py       # 키움 REST API 래퍼 (OAuth, 조회, 주문)
│   ├── alpaca_client.py       # Alpaca REST API 래퍼 (계좌/포지션/주문)
│   ├── executor.py            # 주문 실행 + 안전장치
│   ├── rules.py               # 룰 기반 매매 엔진 (레짐별 진입/청산)
│   ├── position_tracker.py    # 가상 포지션 추적 (SQLite)
│   └── portfolio.py           # 포트폴리오 비중 관리
├── scanner/
│   ├── market_scanner.py      # KRX 스캐너 (골든크로스, RSI, 거래량, 근접GC)
│   └── us_market_scanner.py   # US 스캐너 (4종 스캔)
├── autonomous/                # 🇰🇷 한국 자율매매 파이프라인
│   ├── config.py              # 자율매매 설정 (포지션, 서킷브레이커)
│   ├── pipeline.py            # 메인 오케스트레이터
│   ├── universe.py            # 유니버스 선정 (KOSPI200 복합 스캔)
│   ├── analyzer.py            # 시그널 분석
│   ├── decision.py            # 매매 결정
│   ├── execution.py           # 안전 주문 실행
│   ├── evaluator.py           # 성과 평가 + 텔레그램 리포트
│   ├── optimizer.py           # 전략 자동 튜닝
│   ├── commands.py            # KR 텔레그램 명령어
│   └── runner.py              # 스케줄 러너 (--live/--once)
├── autonomous/us/             # 🇺🇸 미국 자율매매 파이프라인
│   ├── config.py              # US 설정 (ET 시간대, Alpaca)
│   ├── pipeline.py            # US 오케스트레이터
│   ├── universe.py            # US 유니버스 선정 (적응형 완화)
│   ├── analyzer.py            # US 시그널 분석
│   ├── execution.py           # Alpaca 주문 실행
│   ├── commands.py            # US 텔레그램 명령어
│   └── runner.py              # 스케줄러 (KST 기준)
├── backtest/
│   ├── engine.py              # 백테스트 엔진
│   ├── report.py              # 리포트 생성
│   └── runner.py              # CLI 러너
├── scripts/
│   └── export_auto_data.py    # 자율매매 DB → JSON (웹 대시보드용)
└── web/                       # Next.js 웹 대시보드 (Vercel 배포)
    ├── app/
    │   ├── page.tsx           # 메인 대시보드
    │   ├── autonomous/page.tsx # 자율매매 대시보드
    │   └── api/               # API Routes
    ├── components/            # 차트 컴포넌트
    └── lib/                   # 지표/전략 (TS 포팅)
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
# 거래 환경: mock (모의투자) | prod (실전투자)
TRADING_ENV=mock

# 텔레그램 봇 (필수)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_signal_channel_chat_id
TELEGRAM_ADMIN_CHAT_ID=your_admin_dm_or_ops_chat_id
AUTO_TRADE_CHAT_ID=your_auto_trade_chat_id
LONG_TRADE_CHAT_ID=your_position_trade_chat_id
MEANREV_CHAT_ID=your_meanrev_trade_chat_id

# Google Gemini (선택 — 없으면 감성 분석 건너뜀)
GOOGLE_API_KEY=your_google_api_key

# 키움증권 REST API (선택 — KR 자율매매)
KIWOOM_REST_API_KEY=your_kiwoom_key
KIWOOM_REST_API_SECRET=your_kiwoom_secret
KIWOOM_ACCOUNT_NO=your_account_no

# Alpaca Paper Trading (선택 — US 자율매매)
ALPACA_API_KEY=your_alpaca_key
ALPACA_API_SECRET=your_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# OpenDART (선택 — 공시 정보)
DART_API_KEY=your_dart_key
```

## 실행

```bash
# 텔레그램 봇 (스케줄러)
python3 main.py

# 한국 자율매매 파이프라인
python3 autonomous/runner.py --live

# 미국 자율매매 파이프라인
python3 autonomous/us/runner.py --live

# 백테스트
python3 -m backtest.runner 005930 삼성전자 --days 365

# 웹 대시보드 (로컬)
cd web && npm run dev
```

## systemd 서비스

```bash
# 서비스 상태 확인
systemctl --user status signalight              # 텔레그램 봇
systemctl --user status signalight-auto          # KR 자율매매
systemctl --user status signalight-auto-us       # US 자율매매

# 재시작
systemctl --user restart signalight

# 로그 보기
journalctl --user -u signalight -f
journalctl --user -u signalight-auto -f
journalctl --user -u signalight-auto-us -f
```

## 로그 관리

- 백엔드 공통 로깅 설정: `infra/logging_config.py`
- 운영 이벤트 저장소: `infra/ops_event_store.py`
- 텍스트 로그:
  - `logs/signalight.log`
  - `logs/auto-kr.log`
  - `logs/auto-us.log`
- JSON 구조화 로그:
  - `logs/signalight.jsonl`
  - `logs/auto-kr.jsonl`
  - `logs/auto-us.jsonl`
- 경고/에러 전용 로그:
  - `logs/signalight.error.log`
  - `logs/auto-kr.error.log`
  - `logs/auto-us.error.log`
- 운영 이벤트 DB:
  - `storage/ops_events.db`

운영 이벤트 DB에는 전체 `INFO` 로그가 아니라 중요한 이벤트만 저장합니다.
- 파이프라인 실행 시작/종료 요약
- 주문 성공/실패
- 킬스위치/서킷브레이커 같은 핵심 상태 이벤트
- 경고/오류 요약

SQLite에서 바로 확인할 수 있습니다.

```bash
sqlite3 storage/ops_events.db "SELECT created_at, service, event, message FROM ops_event_logs ORDER BY id DESC LIMIT 20;"
sqlite3 storage/ops_events.db "SELECT run_date, service, cycle_id, status, scanned_count, analyzed_count, buy_count, sell_count FROM ops_run_summary ORDER BY id DESC LIMIT 20;"
```

CLI로도 조회할 수 있습니다.

```bash
python3 scripts/ops_log_report.py --mode events --limit 20
python3 scripts/ops_log_report.py --mode runs --service auto-kr --limit 10
python3 scripts/ops_log_report.py --mode events --service auto-us --level ERROR --limit 10
python3 scripts/ops_log_report.py --mode summary
```

운영 장애 확인 절차는 [docs/operations.md](/home/faeqsu10/project/signalight/docs/operations.md)에 정리했습니다.

## 텔레그램 명령어

### 일반 명령어

| 명령어 | 설명 |
|--------|------|
| `/help` | 사용 가능한 명령어 목록 |
| `/status` | 현재 거래 상태 및 대기 주문 요약 |
| `/scan` | 수동 시장 스캔 트리거 |
| `/list` | 현재 감시 종목 목록 표시 |
| `/add 종목코드 종목명` | 감시 종목 추가 |
| `/remove 종목코드` | 감시 종목 제거 |
| `/score 종목코드` | 합류 점수 상세 |
| `/stop` | 긴급 정지 |
| `/start` | 거래 재개 |

### 자율매매 명령어 (KR)

| 명령어 | 설명 |
|--------|------|
| `/auto_status` | KR 자율매매 상태 (잔고, 포지션, MDD) |
| `/auto_config` | KR 자율매매 현재 설정값 |
| `/auto_positions` | KR 보유 포지션 상세 |
| `/auto_history` | 최근 매매 이력 |
| `/auto_pause` | 자율매매 일시 정지 |
| `/auto_resume` | 자율매매 재개 |

### 자율매매 명령어 (US)

| 명령어 | 설명 |
|--------|------|
| `/us_status` | US 자율매매 상태 (Alpaca 계좌, 포지션) |
| `/us_scan` | US 유니버스 즉시 스캔 |
| `/us_positions` | US 보유 포지션 상세 (Alpaca 실시간) |
| `/us_config` | US 자율매매 설정값 |

## Docker 배포

```bash
docker compose up -d
docker compose logs -f bot
```

## 기술 스택

- **Python 3.8+**: pykrx, schedule, requests, lxml
- **Next.js 14**: App Router, Tailwind CSS, lightweight-charts v5, SWR
- **데이터**: pykrx, Yahoo Finance, 네이버 금융, OpenDART, RSS
- **AI**: Google Gemini 2.5 Flash (감성 분석 + 종합 판단)
- **브로커**: 키움증권 REST API (KR), Alpaca Markets API (US)
- **DB**: SQLite WAL 모드
- **배포**: Vercel (웹), systemd (봇/자율매매)

> 본 시스템의 분석 결과는 기술적 지표 기반 참고 자료이며, 투자 추천이 아닙니다.

## 라이선스

MIT
