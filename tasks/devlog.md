# Signalight 개발 리스트

> 전체 개발 항목 추적. 작업 완료 시 자동 업데이트.
> 최종 갱신: 2026-03-08

---

## Phase 1 — 프로젝트 기초 + 텔레그램 봇 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 1 | 프로젝트 구조 생성 | ✅ | Python 백엔드 기본 구조 |
| 2 | 기본 시그널 로직 (MA 크로스, RSI, MACD) | ✅ | signals/indicators.py, strategy.py |
| 3 | GitHub 레포 연결 및 초기 커밋 | ✅ | |
| 4 | 장중 30분 간격 시그널 체크 + 키움/DART API 환경 설정 | ✅ | schedule 기반 |
| 5 | 텔레그램 봇 설정 (BotFather → 토큰 발급 → .env) | ✅ | |
| 6 | 실서비스 테스트 (텔레그램 알림 수신 확인) | ✅ | |

## Phase 1 — Next.js 웹 대시보드 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 7 | Next.js 14 프로젝트 초기화 (web/) | ✅ | App Router |
| 8 | 데이터 레이어 구현 (yahoo-finance.ts, indicators.ts, strategy.ts) | ✅ | Python→TS 포팅 |
| 9 | API Route 구현 (api/stock/[ticker]/route.ts) | ✅ | |
| 10 | 차트 컴포넌트 (CandleChart, RSIChart, MACDChart) | ✅ | lightweight-charts v5 |
| 11 | 대시보드 페이지 조립 (page.tsx + PriceInfo + SignalPanel) | ✅ | |
| 12 | 빌드 성공 확인 + API 실데이터 테스트 (005930) | ✅ | |

## Phase 1 — 백테스팅 엔진 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 13 | fetcher.py 기간 파라미터 확장 (start_date/end_date) | ✅ | |
| 14 | Signal/Trade/BacktestResult 데이터 모델 정의 | ✅ | backtest/__init__.py |
| 15 | generate_signals() 전체 기간 시그널 생성 | ✅ | signals/strategy.py |
| 16 | BacktestEngine 핵심 엔진 구현 | ✅ | 다음 거래일 시가 체결, 수수료+슬리피지 |
| 17 | 백테스트 리포트 생성 (텍스트 + 텔레그램 포맷) | ✅ | backtest/report.py |
| 18 | CLI 러너 구현 | ✅ | `python3 -m backtest.runner` |

## Phase 2 — 전략 고도화 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 19 | VIX(공포지수) + 외인/기관 매매동향 지표 추가 (웹) | ✅ | |
| 20 | 거래량 비율 지표 추가 (Python + TS 동기화) | ✅ | |
| 21 | 시그널 구조화 (문자열 → 구조화된 dict, 합류 점수) | ✅ | |
| 22 | 텔레그램 포맷터 분리 (bot/formatter.py) | ✅ | 상세 근거 메시지 |
| 23 | 일일 종합 브리핑 (평일 16:00) | ✅ | 전 종목 요약 |
| 24 | 주간 리포트 (금요일 16:30) | ✅ | 주간 등락률 + 시그널 요약 |
| 25 | systemd 서비스 등록 (자동 시작 + 재시작) | ✅ | |
| 26 | RSI Wilder's Smoothing 변경 (Python + TS) | ✅ | |
| 27 | 거래량 확인 로직 시그널 활용 (volume_ratio 기반) | ✅ | |
| 28 | 거래량 차트 추가 (캔들 하단 HistogramSeries) | ✅ | |
| 29 | MA 조합 변경 (5/20 → 10/50) + DATA_PERIOD_DAYS 120 | ✅ | |
| 30 | 합류 점수 가중치 도입 (수급 1.5x, 기술적 1.0x) | ✅ | |
| 31 | 종합 시그널 배너 화면 최상단 추가 | ✅ | |
| 32 | Tooltip 모바일 터치 지원 (onClick 토글) | ✅ | |
| 33 | 차트 모바일 반응형 높이 + 마지막 갱신 시각 표시 | ✅ | |
| 34 | 신규 지표 추가 (볼린저밴드, OBV) + TS 동기화 | ✅ | |
| 35 | 볼린저밴드/OBV 시그널 전략 통합 + 웹 차트 표시 | ✅ | |
| 36 | 백테스트 결과 웹 대시보드 표시 (API + 요약 카드) | ✅ | |
| 37 | 복합 전략 프레임워크 (가중 점수 + 신호 강도 분류) | ✅ | |

## Phase 2 — 인프라 안정화 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 38 | systemd 재시작 정책 확인 (Restart=always) | ✅ | |
| 39 | 구조화 로깅 구현 (infra/logging_config.py) | ✅ | 콘솔+파일, 10MB 로테이션 |
| 40 | Python 봇 timeout + 재시도 로직 (3회 backoff) | ✅ | |
| 41 | 헬스체크 메시지 추가 (매일 09:00) | ✅ | |
| 42 | 네이버 금융 크롤링 캐시 (4시간 in-memory) | ✅ | investor.py + news.py |

## LLM 파이프라인 Phase 1 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 43 | Google Gemini 2.5 Flash REST API 연동 | ✅ | signals/sentiment.py |
| 44 | config.py에 GOOGLE_API_KEY + SENTIMENT_MODEL 설정 | ✅ | |
| 45 | data/news.py 구현 (네이버 금융 뉴스 크롤러) | ✅ | |
| 46 | bot/formatter.py에 [뉴스 감성] 블록 추가 | ✅ | 감성+신뢰도+요약+불일치 경고 |
| 47 | main.py에 뉴스+감성 통합 (실패 격리) | ✅ | |
| 48 | systemd 서비스 재시작 확인 | ✅ | |

## LLM 파이프라인 Phase 2 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 49 | storage/db.py 구현 (SQLite — signal_history, news_sentiment, llm_analysis) | ✅ | WAL 모드 |
| 50 | signals/llm_analyzer.py 구현 (Gemini 종합 판단) | ✅ | 상충 시그널/합류>=2 시 호출 |
| 51 | main.py 통합 (DB 저장 + LLM 판단 호출) | ✅ | |
| 52 | bot/formatter.py에 [AI 종합 판단] 블록 추가 | ✅ | |

## Phase 3 — 자동매매 + 인터랙티브 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 53 | trading/ 패키지 (Order/TradingConfig dataclass) | ✅ | |
| 54 | trading/kiwoom_client.py (키움 REST API 래퍼) | ✅ | OAuth, 조회, 주문 |
| 55 | trading/executor.py (주문 실행 + 안전장치) | ✅ | dry-run, 일일손실3%, 종목비중30% |
| 56 | trading/portfolio.py (포트폴리오 비중 관리) | ✅ | |
| 57 | bot/interactive.py (텔레그램 인터랙티브) | ✅ | /stop, /status, /scan, 인라인 키보드 |
| 58 | scanner/market_scanner.py (KRX 종목 스캐너) | ✅ | 골든크로스, RSI과매도, 거래량급증 |
| 59 | Vercel 배포 설정 (web/vercel.json) | ✅ | |
| 60 | main.py 통합 (executor + interactive bot) | ✅ | |
| 61 | Gemini 2.5 Flash thinking 모델 JSON 파싱 수정 | ✅ | sentiment.py, llm_analyzer.py |

## Phase 4 — 종목 확장 + 아키텍처 개선 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 62 | VIX 중복 호출 제거 (main.py에서 1회 호출 후 전달) | ✅ | |
| 63 | 텔레그램 메시지 4096자 자동 분할 | ✅ | |
| 64 | WATCH_LIST 10종목 확장 (5+ 섹터 분산) | ✅ | Python + TS 동기화 |
| 65 | DB 기반 동적 종목 관리 (storage/db.py watch_list) | ✅ | |
| 66 | 텔레그램 /add, /remove, /list 명령어 | ✅ | |
| 67 | 웹 대시보드 종목 검색 + 자동완성 | ✅ | |
| 68 | 웹 스크리너 섹션 (골든크로스/RSI과매도/거래량급증) | ✅ | |
| 69 | 면책 조항 추가 | ✅ | |
| 70 | main.py DB 우선 워치리스트 (config.py 폴백) | ✅ | |

## Phase 6 — 미국 주식 + 복합 전략 + 인프라 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 71 | 미국 주식 지원 (US_WATCH_LIST 5종목, 통화/마켓 분기) | ✅ | AAPL, NVDA, TSLA, MSFT, AMZN |
| 72 | 복합 전략 프레임워크 (가중 점수 + signal_strength 5단계) | ✅ | Python + TS 동기화 |
| 73 | Docker 배포 설정 (Dockerfile + docker-compose.yml) | ✅ | Multi-stage |
| 74 | 모바일 최적화 (터치 타겟 44px, 반응형 그리드) | ✅ | |

## Phase 7 — 회복 분석 기능 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 75 | signals/recovery.py 구현 (6항목 체크리스트, 가중 점수 0-10) | ✅ | RSI극단, RSI이탈, BB복귀, 거래량급증, OBV다이버전스, 기관매수 |
| 76 | signals/indicators.py에 detect_volume_spike, detect_obv_divergence 추가 | ✅ | |
| 77 | config.py에 RECOVERY 관련 설정 추가 | ✅ | |
| 78 | web/lib/recovery.ts 포팅 (analyzeRecovery 등) | ✅ | Python→TS 동기화 |
| 79 | web/app/api/stock/[ticker]/recovery/route.ts API 라우트 | ✅ | 캐시 포함 |
| 80 | web/components/RecoveryPanel.tsx (체크리스트 + 점수 게이지) | ✅ | |
| 81 | web/components/PositionCard.tsx (매수가 입력 + 손익 + 액션 가이드) | ✅ | localStorage 저장, 300ms 디바운스 |
| 82 | page.tsx 통합 + Next.js 빌드 성공 | ✅ | |

## Phase 8 — API 캐시 + UX 개선 [완료]

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| 83 | API Route in-memory 캐시 (web/lib/cache.ts, 5분 TTL) | ✅ | |
| 84 | 차트 기간 선택 버튼 (1M/3M/6M/1Y) | ✅ | SWR key 포함 |
| 85 | Yahoo Finance 에러 핸들링 강화 (429 재시도, 빈 데이터) | ✅ | fetchWithRetry |
| 86 | investor.ts 파싱 실패 graceful degradation | ✅ | |
| 87 | 종목 즐겨찾기 (localStorage, ★ 토글, 드롭다운 상단 정렬) | ✅ | |
| 88 | 시그널 강도 배지 (드롭다운에 컬러 dot 표시) | ✅ | |

---

## Backlog — 미완료 항목

| # | 항목 | 상태 | 우선순위 | 비고 |
|---|------|------|----------|------|
| B-1 | Vercel 배포 | ⬜ | P1 | Root Directory: web/ |
| B-2 | OpenDART 시범 도입 (외인/기관 공식 API) | ⬜ | P2 | 네이버 크롤링 대체 |
| B-3 | 모바일/PC 브라우저 접속 테스트 | ⬜ | P2 | |
| B-4 | 시그널 히스토리 타임라인 (최근 30일) | ⬜ | P2 | 차트에 마커 추가 |
| B-5 | XPath 파싱 실패 시 graceful degradation | ⬜ | P2 | 네이버 금융 |
| B-6 | Terms of Service 법적 검토 (뉴스, 외인/기관) | ⬜ | P3 | |
| B-7 | 에러 메시지 구체화 (데이터 소스별) | ⬜ | P3 | |
| B-8 | 스켈레톤 UI + 에러 재시도 버튼 | ⬜ | P3 | |
| B-9 | 다크/라이트 모드 토글 | ⬜ | P3 | 현재 다크모드 고정 |
| B-10 | 멀티 종목 비교 뷰 | ⬜ | P3 | 2~3개 나란히 |
| B-11 | 브라우저 알림 연동 | ⬜ | P3 | 시그널 발생 시 |
| B-12 | Next.js API 요청/응답 시간 로깅 | ⬜ | P3 | |
| B-13 | 데이터 소스별 성공/실패율 추적 | ⬜ | P3 | |

---

## 통계

- **총 항목**: 101개 (완료 88 + 백로그 13)
- **완료율**: 87%
