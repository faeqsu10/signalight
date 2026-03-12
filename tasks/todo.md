# Signalight TODO

## Python 백엔드 (텔레그램 봇)
- [x] 프로젝트 구조 생성
- [x] 기본 시그널 로직 (MA 크로스, RSI, MACD)
- [x] GitHub 레포 연결 및 초기 커밋
- [x] 장중 30분 간격 시그널 체크 + 키움/DART API 환경 설정
- [x] 텔레그램 봇 설정 (BotFather → 토큰 발급 → .env 설정)
- [x] 실서비스 테스트 (텔레그램 알림 수신 확인)

## Next.js 웹 대시보드
- [x] Next.js 14 프로젝트 초기화 (web/)
- [x] 데이터 레이어 구현 (yahoo-finance.ts, indicators.ts, strategy.ts)
- [x] API Route 구현 (api/stock/[ticker]/route.ts)
- [x] 차트 컴포넌트 구현 (CandleChart, RSIChart, MACDChart)
- [x] 대시보드 페이지 조립 (page.tsx + PriceInfo + SignalPanel)
- [x] 빌드 성공 확인 + API 실데이터 테스트 (삼성전자 005930)
- [x] Vercel 배포 (https://web-iota-ten-60.vercel.app)
- [ ] 모바일/PC 브라우저 접속 테스트

## 백테스팅 엔진 (Phase 1 - 완료)
- [x] fetcher.py 기간 파라미터 확장 (start_date/end_date)
- [x] Signal/Trade/BacktestResult 데이터 모델 정의 (backtest/__init__.py)
- [x] generate_signals() 전체 기간 시그널 생성 (signals/strategy.py)
- [x] BacktestEngine 핵심 엔진 구현 (backtest/engine.py)
  - 다음 거래일 시가 체결, 수수료 0.015% + 슬리피지 0.1%
  - MDD/승률/equity curve 계산, 미체결 포지션 강제 청산
- [x] 백테스트 리포트 생성 (backtest/report.py)
  - 텍스트 리포트 + 텔레그램 메시지 포맷
- [x] CLI 러너 구현 (backtest/runner.py)
  - `python3 -m backtest.runner [종목코드] [종목명] [--days N] [--capital N]`

## Phase 2 - 전략 고도화 (진행 중) + 인프라 안정화

### 전략 고도화
- [x] VIX(공포지수) + 외인/기관 매매동향 지표 추가 (웹 대시보드)
- [x] 거래량 비율 지표 추가 (Python + TS 동기화)
- [x] 시그널 구조화 (문자열 → 구조화된 dict, 합류 점수)
- [x] 텔레그램 포맷터 분리 (bot/formatter.py, 상세 근거 메시지)
- [x] 일일 종합 브리핑 (평일 16:00, 전 종목 요약)
- [x] 주간 리포트 (금요일 16:30, 주간 등락률 + 시그널 요약)
- [x] systemd 서비스 등록 (자동 시작 + 자동 재시작)
- [x] RSI Wilder's Smoothing 변경 (Python + TS 동기화)
- [x] 거래량 확인 로직 시그널 활용 (volume_ratio 기반 강화/경고)
- [x] 거래량 차트 추가 (캔들 하단 HistogramSeries)
- [x] MA 조합 변경 (5/20 → 10/50) + DATA_PERIOD_DAYS 120
- [x] 합류 점수 가중치 도입 (수급 1.5x, 기술적 1.0x, 상충 시 혼재)
- [x] 종합 시그널 배너 화면 최상단 추가
- [x] Tooltip 모바일 터치 지원 (onClick 토글 + 외부 클릭 닫힘)
- [x] 차트 모바일 반응형 높이 + 마지막 갱신 시각 표시
- [x] 신규 지표 추가 (볼린저밴드, OBV) + TS 동기화
- [x] 볼린저밴드/OBV 시그널 전략 통합 + 웹 차트 표시
- [x] 백테스트 결과 웹 대시보드 표시 (API + 요약 카드)
- [x] 복합 전략 프레임워크 (가중 점수 + 신호 강도 분류)

### 인프라 안정화 (Phase 2 신규)
- [x] systemd 재시작 정책 확인 (Restart=always, RestartSec=10)
- [x] 구조화 로깅 구현 (`infra/logging_config.py`)
- [x] Python 봇 timeout + 재시도 로직 (send_message 3회 backoff)
- [x] 헬스체크 메시지 추가 (매일 09:00)
- [x] 네이버 금융 크롤링 캐시 (investor/news 4시간 in-memory)
- [x] Vercel 배포 및 API 캐싱 (cache.ts 5분 TTL + Vercel 배포 완료)
- [x] OpenDART 시범 도입 (공시 정보 웹 통합, 외인/기관 데이터는 미제공)
- 참고: `DEVOPS_ANALYSIS.md`

## LLM 파이프라인 (Phase 1 - 완료)
- [x] google-generativeai 패키지 설치 (→ REST API 직접 호출로 전환)
- [x] signals/sentiment.py 구현 (Google Gemini 2.5 Flash 감성 분석)
- [x] config.py에 GOOGLE_API_KEY + SENTIMENT_MODEL 등 설정 추가
- [x] data/news.py 구현 (네이버 금융 뉴스 크롤러)
- [x] bot/formatter.py에 [뉴스 감성] 블록 추가 (감성+신뢰도+요약+불일치 경고)
- [x] main.py에 뉴스+감성 통합 (실패 격리, 기존 기능 영향 없음)
- [x] systemd 서비스 재시작 확인

## LLM 파이프라인 (Phase 2 - 완료)
- [x] storage/db.py 구현 (SQLite — signal_history, news_sentiment, llm_analysis)
- [x] signals/llm_analyzer.py 구현 (Gemini 종합 판단, 상충 시그널/합류>=2 시 호출)
- [x] main.py 통합 (DB 저장 + LLM 판단 호출)
- [x] bot/formatter.py에 [AI 종합 판단] 블록 추가

## 인프라 안정화 (완료)
- [x] infra/logging_config.py 구조화 로깅 (콘솔+파일, 10MB 로테이션)
- [x] main.py print→logger 전환
- [x] 매일 09:00 헬스체크 메시지 추가
- [x] ATR(14) 지표 추가 + 손절가 표시 (현재가-2*ATR)

## Phase 3 - 자동매매 + 인터랙티브 (완료)
- [x] trading/ 패키지 (Order/TradingConfig dataclass)
- [x] trading/kiwoom_client.py (키움 REST API 래퍼, OAuth, 조회, 주문)
- [x] trading/executor.py (주문 실행 + 안전장치: dry-run, 일일손실3%, 종목비중30%)
- [x] trading/portfolio.py (포트폴리오 비중 관리)
- [x] bot/interactive.py (텔레그램 인터랙티브: /stop, /status, /scan, 인라인 키보드)
- [x] scanner/market_scanner.py (KRX 종목 스캐너: 골든크로스, RSI과매도, 거래량급증)
- [x] Vercel 배포 설정 (web/vercel.json)
- [x] main.py 통합 (executor + interactive bot)
- [x] Gemini 2.5 Flash thinking 모델 JSON 파싱 수정 (sentiment.py, llm_analyzer.py)

## Phase 4 - 종목 확장 + 아키텍처 개선 (완료)
- [x] VIX 중복 호출 제거 (main.py에서 1회 호출 후 전달)
- [x] 텔레그램 메시지 4096자 자동 분할
- [x] WATCH_LIST 10종목 확장 (5+ 섹터 분산, Python + TS 동기화)
- [x] DB 기반 동적 종목 관리 (storage/db.py watch_list 테이블)
- [x] 텔레그램 /add, /remove, /list 명령어
- [x] 웹 대시보드 종목 검색 + 자동완성
- [x] 웹 스크리너 섹션 (골든크로스/RSI과매도/거래량급증)
- [x] 면책 조항 추가
- [x] main.py DB 우선 워치리스트 (config.py 폴백)

## Phase 6 - 미국 주식 + 복합 전략 + 인프라 (완료)
- [x] 미국 주식 지원 (US_WATCH_LIST 5종목, 통화/마켓 분기)
- [x] 복합 전략 프레임워크 (가중 점수 + signal_strength 5단계)
- [x] Docker 배포 설정 (Dockerfile + docker-compose.yml)
- [x] 모바일 최적화 (터치 타겟 44px, 반응형 그리드)

## Phase 7 - 회복 분석 기능 (완료)
- [x] signals/recovery.py 구현 (6항목 체크리스트, 가중 점수 0-10)
- [x] signals/indicators.py에 detect_volume_spike, detect_obv_divergence 추가
- [x] config.py에 RECOVERY_RSI_EXTREME, RECOVERY_VOLUME_SPIKE, RECOVERY_LOOKBACK_DAYS 추가
- [x] web/lib/recovery.ts 포팅 (analyzeRecovery, getPositionAction, classifyDrawdownContext)
- [x] web/app/api/stock/[ticker]/recovery/route.ts API 라우트
- [x] web/components/RecoveryPanel.tsx (체크리스트 + 점수 게이지)
- [x] web/components/PositionCard.tsx (매수가 입력 + 손익 + 액션 가이드)
- [x] page.tsx 통합 + Next.js 빌드 성공

## Phase 8 - API 캐시 + UX 개선 (완료)
- [x] API Route in-memory 캐시 (web/lib/cache.ts, 5분 TTL)
- [x] 차트 기간 선택 버튼 (1M/3M/6M/1Y)
- [x] Yahoo Finance 에러 핸들링 강화 (429 재시도, 빈 데이터)
- [x] investor.ts 파싱 실패 graceful degradation
- [x] 종목 즐겨찾기 (localStorage, ★ 토글, 드롭다운 상단 정렬)
- [x] 시그널 강도 배지 (드롭다운에 컬러 dot 표시)

## Phase 9 - 자율매매 고도화 (진행 중)
- [x] 키움 mock API 연결 확인 (OAuth 토큰 정상 발급)
- [x] shared config → autonomous config 분리 (signals/strategy.py에서 config.py 의존성 제거)
- [x] /config 텔레그램 명령 추가 (자율매매 임계값, 스캔 가중치, 옵티마이저 상태 확인)
- [x] 웹 자율매매 PnL API (scripts/export_auto_data.py + web API route + pipeline 통합)
- [ ] 웹 자율매매 대시보드 페이지 (차트 + 거래 이력 UI)
- [ ] mock 거래 데이터 축적 → 옵티마이저 피드백 루프 실증
- [ ] 자율매매 상태 모니터링 강화 (장중 로그 가시성)

## Backlog
- [x] Vercel 배포
- [x] OpenDART 시범 도입 (공시 정보, 외인/기관은 미제공)
- [ ] 모바일/PC 브라우저 접속 테스트
- [x] 시그널 히스토리 타임라인 (최근 30일, 차트 마커)
- [x] 스켈레톤 UI + 에러 재시도 버튼
- [x] 멀티 종목 비교 뷰 (2개 종목 나란히)
- [x] 브라우저 알림 연동 (Notification API)
- [x] API 요청/응답 시간 로깅
- [x] 데이터 소스별 성공/실패율 추적
- 개선사항은 `tasks/improvements.md` 참고
