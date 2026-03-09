# 개선사항 추적

> 우선순위: P0(긴급) > P1(높음) > P2(보통) > P3(낮음)

## P0 - LLM 파이프라인 (진행 중)

> 상세 로드맵: `tasks/llm-pipeline-roadmap.md`

### Phase 1: 뉴스 감성 분석 (완료)
- [x] `signals/sentiment.py` 구현 — Google Gemini 2.5 Flash REST API 호출
- [x] `config.py`에 `GOOGLE_API_KEY` 추가
- [x] `data/news.py` 구현 — 네이버 금융 종목별 뉴스 크롤러
- [x] `bot/formatter.py` — [뉴스 감성] 블록 (감성+신뢰도+요약+방향 불일치 경고)
- [x] `main.py` — 뉴스+감성 통합 (try/except 격리)
- 비용: 월 ~400원

### Phase 2: LLM 종합 판단 + DB (예정)
- 상충 시그널 시 Claude에게 종합 판단 위임
- SQLite로 시그널/매매 이력 저장
- 기간: 3-4주

### Phase 3: 키움 모의투자 자동매매 (예정)
- 키움 REST API 연동, dry-run 기본
- 단계적 신뢰 구축 (페이퍼 → 확인 후 실행 → 반자동)
- 기간: 4-6주

## P1 - 기능 개선

### 종목 검색/추가 기능
- 현재: WATCH_LIST 하드코딩 (삼성전자, SK하이닉스 2개)
- 개선: 검색창에서 종목명/코드 입력 → 동적으로 차트 표시
- 참고: Yahoo Finance API는 임의 종목코드 지원 (`{code}.KS`)

### 거래량 차트 추가
- 현재: 캔들차트에 거래량 미표시
- 개선: 캔들차트 하단에 거래량 바 차트 오버레이
- lightweight-charts의 HistogramSeries를 별도 pane으로 추가

### 볼린저 밴드 + OBV 지표 추가 (완료)
- [x] 볼린저 밴드 (20일 MA ± 2σ) Python + TS 양쪽 구현
- [x] OBV (On-Balance Volume) Python + TS 양쪽 구현
- [x] 전략 통합 (하단밴드 이탈=매수, 상단밴드 이탈=매도)

### 시그널 히스토리 (완료)
- [x] 차트에 시그널 발생 시점 마커 추가 (createSeriesMarkers)
- [x] 매수=빨강 삼각형 위, 매도=파랑 삼각형 아래

### 미국 주식 지원 (완료)
- [x] Yahoo Finance 티커 자동 분기 (한국: `.KS`, 미국: 그대로)
- [x] US_WATCH_LIST 5종목 (AAPL, NVDA, TSLA, MSFT, AMZN)
- [x] 통화 분기 (₩ / $), 마켓 배지 (KR/US)

### 복합 전략 프레임워크 (완료)
- [x] 가중 점수 기반 신호 강도 5단계 (strong_buy/buy/neutral/sell/strong_sell)
- [x] Python + TS 양쪽 동기화

### 합류 점수 시스템 고도화 (완료)
- [x] 이진→연속 강도 점수 전환 (RSI/MA/MACD/BB 0.0~1.0)
- [x] 수급 AND→OR 분리 (외인/기관 각 0.75점 독립)
- [x] OBV 상승 다이버전스 + Stochastic RSI 편입
- [x] 시장 레짐 기반 동적 가중치 (상승/하락/횡보)
- [x] TypeScript 동기화 완료

### 텔레그램 메시지 포맷 리디자인 (완료)
- [x] 일일 브리핑: 시장 온도 섹션, 주목 종목 분리, compact 나머지, 한줄 코멘트
- [x] 시그널 알림: 핵심 요약 문장, ✅/🔻/⬜ 근거 해석, 프로그레스 바(▓░)
- [x] /score 합류점수 분해 명령어, /info FAQ 합류점수 설명

### Docker 배포 (완료)
- [x] Multi-stage Dockerfile + docker-compose.yml
- [x] .dockerignore 설정

## P2 - UX 개선

### 종목 즐겨찾기
- localStorage로 사용자별 관심 종목 저장
- 드롭다운에 즐겨찾기 종목 우선 표시

### 차트 기간 선택 (완료)
- [x] 1M / 3M / 6M / 1Y 선택 버튼 추가

### 로딩/에러 UX (완료)
- [x] 스켈레톤 UI (pulse 애니메이션, 차트+패널 모양)
- [x] 에러 시 재시도 버튼 (SWR mutate())

### 모바일 최적화
- 차트 높이 반응형 조정 (모바일에서 400px는 과도)
- 터치 제스처 지원 확인
- RSI/MACD 차트 모바일에서 세로 배치 확인

## P0 - 인프라 안정성 (Phase 2 우선)

### Python 봇 안정성 강화 (완료)
- [x] systemd 서비스 재시작 정책 (Restart=always, RestartSec=10)
- [x] 구조화 로깅: `infra/logging_config.py` (콘솔+파일, 10MB 로테이션)
- [x] 각 fetch 함수에 timeout 설정 (pykrx, requests)
- [x] `send_message()` 재시도 로직 (3회, exponential backoff)
- [x] 헬스체크 메시지 (매일 09:00)

### 네이버 금융 크롤링 안정성 (일부 완료)
- [x] in-memory 캐시 도입 (4시간 TTL, investor.py + news.py)
- [x] XPath 파싱 실패 시 graceful degradation (investor.ts try/catch + API warnings)
- [x] OpenDART API 시범 도입 (공시 정보 웹 통합, 외인/기관 데이터는 미제공)
- [ ] Terms of Service 법적 검토 (뉴스, 외인/기관)
- 참고: `DEVOPS_ANALYSIS.md` 부록

### 웹 대시보드 배포
- [x] Vercel 배포 완료 (https://web-iota-ten-60.vercel.app)
- [x] API Route in-memory 캐시 추가 (5분, web/lib/cache.ts)
- [x] 에러 메시지 구체화 (데이터 소스별 warnings 배열 반환)
- [x] 환경변수 설정 (DART_API_KEY — Vercel에서 설정 시 공시 정보 활성화)
- 참고: `DEVOPS_ANALYSIS.md` 섹션 4.4

## P1 - 모니터링 기초

### 봇 헬스체크
- [ ] 일일 헬스체크 메시지 (09:00 "봇 상태 확인")
- [ ] 24시간 타임아웃 감시 (봇 다운 감지)
- [ ] 텔레그램 수신 확인

### API 로깅 강화 (완료)
- [x] Next.js API 요청/응답 시간 기록 (api-logger.ts, 5개 route)
- [x] 데이터 소스별 성공/실패율 추적 (metrics.ts, watchlist API 노출)
- [ ] Vercel Functions Logs 활용

## P2 - 데이터 캐싱 프레임워크

### 캐싱 레이어
- [ ] SQLite 또는 in-memory 캐시
- [ ] OHLCV, VIX, 외인/기관, 뉴스: 최소 4시간 캐시
- [ ] 캐시 miss 시 real-time fetch

## P2 - 기술 품질

### RSI 계산 방식 개선 (완료)
- [x] Wilder's smoothing (EMA 기반) 방식으로 변경
- [x] Python과 TS 양쪽 동시 반영

### API 에러 핸들링 강화
- Yahoo Finance API 요청 제한(rate limit) 대응
- 장 마감/공휴일 시 빈 데이터 처리
- API 실패 시 캐시된 데이터 표시

### 회복 분석 기능 (완료)
- [x] 회복 시그널 체크리스트 (6항목 가중 점수 0-10)
  - RSI 극단 과매도, RSI 과매도 이탈, BB 하단밴드 복귀
  - 거래량 급증(투매), OBV 상승 다이버전스, 기관 매수 전환
- [x] 내 포지션 진단 카드 (매수가 입력 → 맞춤 액션 가이드)
- [x] 시장 맥락 분류기 (시장 전체 vs 섹터 vs 개별 종목 낙폭)
- [x] 과거 낙폭 에피소드 탐색 (find_historical_drawdowns)
- [x] Python + TS 양쪽 구현 + API Route + 웹 UI

## P3 - 향후 확장

### 미국 주식 지원
- Yahoo Finance 티커 형식 그대로 사용 가능 (AAPL, TSLA 등)
- constants.ts에 US_WATCH_LIST 추가
- 통화 표시 ($) 분기 처리
- 시간대 처리 (KST vs EST)

### 알림 연동 (완료)
- [x] 브라우저 Notification API 연동 (권한 요청 + 시그널 변경 감지)

### 다크/라이트 모드 토글 (완료)
- [x] ThemeToggle 컴포넌트 + 시스템 설정 연동

### 멀티 종목 비교 뷰 (완료)
- [x] 2개 종목 나란히 비교 (가격, 변동률, 시그널 수, 강도 배지)
