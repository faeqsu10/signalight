# Signalight - Claude Code 프로젝트 가이드

## 프로젝트 개요
한국 주식 매매 시그널(매수/매도 타이밍) 분석 시스템
- **텔레그램 봇**: Python 기반, 평일 자동 알림
- **웹 대시보드**: Next.js 기반, 실시간 차트 + 시그널 표시

## 아키텍처

```
signalight/
├── [Python 백엔드] 텔레그램 알림 봇
│   ├── config.py           # 설정 (KR 10종목 + US 30종목, 지표 파라미터, 환경변수, RSS 뉴스)
│   ├── main.py             # 진입점 + 스케줄러 (DB 우선 워치리스트, VIX 1회 조회)
│   ├── data/
│   │   ├── fetcher.py      # pykrx KRX OHLCV + Yahoo VIX 데이터 수집
│   │   ├── investor.py     # 네이버 금융 외인/기관 순매수 크롤링
│   │   ├── macro_fetcher.py # 글로벌 매크로 가격 지표 (WTI/환율/금리/금/DXY, 4시간 캐시)
│   │   ├── us_fetcher.py   # Yahoo Finance 미국 주식 OHLCV (한글 컬럼명 변환)
│   │   ├── news.py         # 네이버 금융 종목별 뉴스 크롤링
│   │   └── macro_news.py   # 글로벌 매크로 RSS 뉴스 수집 + 키워드 이벤트 분류
│   ├── signals/
│   │   ├── indicators.py   # 기술적 지표 (MA, Wilder RSI, MACD, ATR, BB, OBV, StochRSI, 거래량)
│   │   ├── strategy.py     # 시그널 판단 + 연속 강도 합류 점수 + 시장 레짐 가중치
│   │   ├── recovery.py     # 회복 시그널 분석 (6항목 체크리스트 + 포지션 진단)
│   │   ├── sentiment.py    # Google Gemini 뉴스 감성 분석
│   │   └── llm_analyzer.py # Gemini 종합 판단 (상충 시그널 해석)
│   ├── storage/
│   │   └── db.py           # SQLite (시그널 이력, 감성, LLM 판단, watch_list)
│   ├── infra/
│   │   ├── logging_config.py # 구조화 로깅 (콘솔+텍스트+JSON+에러 로그)
│   │   └── ops_event_store.py # 운영 이벤트 SQLite 저장소 (핵심 이벤트/실행 요약)
│   ├── bot/
│   │   ├── telegram.py     # 텔레그램 메시지 전송 (4096자 분할 + 3회 재시도)
│   │   ├── formatter.py    # 메시지 포맷터 (분석 보고서 스타일: 시장 온도, 주목 종목, 프로그레스 바, 한줄 코멘트)
│   │   └── interactive.py  # 텔레그램 인터랙티브 (/stop, /status, /scan, /add, /remove, /list, /score, /info)
│   ├── trading/
│   │   ├── __init__.py        # Order, TradingConfig dataclass
│   │   ├── kiwoom_client.py   # 키움 REST API 래퍼 (OAuth, 조회, 주문)
│   │   ├── alpaca_client.py   # Alpaca REST API 래퍼 (계좌/포지션/주문/호가)
│   │   ├── executor.py        # 주문 실행 + 안전장치 (dry-run, 손실한도, 비중한도)
│   │   ├── rules.py           # 룰 기반 매매 추천 엔진 (레짐별 진입/청산, 분할매수, 리스크관리)
│   │   ├── position_tracker.py # 가상 포지션 추적 (SQLite, 분할단계, 트레일링스탑)
│   │   └── portfolio.py       # 포트폴리오 비중 관리
│   └── scanner/
│       ├── __init__.py
│       ├── market_scanner.py    # KRX 종목 스캐너 (골든크로스, RSI과매도, 거래량급증)
│       ├── us_market_scanner.py # US 스캐너 (골든크로스/RSI/거래량/근접GC)
│       └── kospi200_tickers.py  # pykrx fallback 정적 종목 리스트 (KOSPI200+KOSDAQ)
│
├── [자율 트레이딩 파이프라인] main.py와 분리된 별도 프로세스
│   ├── autonomous/            # 한국 주식 자율 트레이딩 파이프라인
│   │   ├── __init__.py
│   │   ├── config.py          # 자율매매 전용 설정 (포지션 5%, 서킷브레이커, 타이밍)
│   │   ├── state.py           # 파이프라인 상태 관리 (SQLite: PnL, 에퀴티, 매매로그)
│   │   ├── universe.py        # 유니버스 선정 (KOSPI200 복합 스캔 + 유동성 필터)
│   │   ├── analyzer.py        # 시그널 분석 (analyze_detailed 래핑)
│   │   ├── decision.py        # 매매 결정 (TradeRule 래핑 + 포트폴리오 제약)
│   │   ├── execution.py       # 안전 주문 실행 (서킷브레이커 + 킬스위치 + 장중 체크)
│   │   ├── evaluator.py       # 성과 평가 + 텔레그램 리포트 (AUTO_TRADE_CHAT_ID)
│   │   ├── optimizer.py       # 성과 기반 전략 자동 튜닝 (스캔 가중치, 합류 임계값)
│   │   ├── pipeline.py        # 메인 오케스트레이터 (스캔→분석→결정→실행→추적→평가→개선→웹export)
│   │   ├── commands.py        # 자율매매 텔레그램 명령어 (/status, /config, /positions, /history, /pause, /resume)
│   │   └── runner.py          # 별도 프로세스 진입점 (schedule 기반, --live/--once 옵션)
│   │
│   └── autonomous/us/         # 미국 주식 자율 트레이딩 파이프라인
│       ├── __init__.py
│       ├── config.py          # US 전용 설정 (ET 시간대, USD, Alpaca Paper Trading)
│       ├── universe.py        # US 유니버스 선정 (Yahoo 기반 스캔 + 적응형 완화)
│       ├── analyzer.py        # US 시그널 분석 (analyze_detailed 래핑)
│       ├── execution.py       # Alpaca 주문 실행 (장중 체크, 킬스위치)
│       ├── pipeline.py        # US 오케스트레이터 (스캔→분석→결정→실행)
│       ├── commands.py        # US 텔레그램 명령어 (/us_status, /us_scan, /us_positions, /us_config)
│       └── runner.py          # 스케줄러 (05:50 KST 일일스캔, 23:35-05:45 장중)
│
├── [Next.js 프론트엔드] 웹 대시보드
│   └── web/
│       ├── app/
│       │   ├── page.tsx                    # 메인 대시보드 (검색+스크리너+면책조항)
│       │   ├── layout.tsx                  # 레이아웃 (다크모드)
│       │   └── api/
│       │       ├── stock/[ticker]/route.ts # 종목 데이터+지표+시그널
│       │       ├── watchlist/route.ts      # 감시 종목 목록 API
│       │       ├── scanner/route.ts        # 스크리너 API (골든크로스/RSI/거래량)
│       │       ├── backtest/[ticker]/route.ts # 백테스트 API (1년 수익률/MDD/승률)
│       │       ├── stock/[ticker]/recovery/route.ts # 회복 분석 API
│       │       └── stock/[ticker]/disclosure/route.ts # OpenDART 공시 API
│       ├── components/
│       │   ├── CandleChart.tsx             # 캔들차트 + MA 오버레이
│       │   ├── RSIChart.tsx                # RSI 라인 + 30/70 기준선
│       │   ├── MACDChart.tsx               # MACD/Signal + 히스토그램
│       │   ├── SignalPanel.tsx             # 시그널 현황 패널
│       │   ├── PriceInfo.tsx               # 현재가, 등락률, 종합 시그널
│       │   ├── RecoveryPanel.tsx           # 회복 시그널 체크리스트 + 점수
│       │   ├── PositionCard.tsx            # 내 포지션 진단 (매수가 입력)
│       │   └── DisclosurePanel.tsx         # OpenDART 최근 공시 목록
│       └── lib/
│           ├── api-logger.ts               # API 요청/응답 시간 로깅
│           ├── constants.ts                # config.py 포팅 + VIX/수급 설정값
│           ├── indicators.ts               # indicators.py 포팅
│           ├── investor.ts                 # 네이버 금융 외인/기관 순매수 fetch
│           ├── metrics.ts                  # 데이터 소스별 성공/실패율 추적
│           ├── opendart.ts                 # OpenDART API (공시 조회 + corp_code 매핑)
│           ├── recovery.ts                 # recovery.py 포팅 (회복 분석 + 포지션 진단)
│           ├── strategy.ts                 # strategy.py 포팅 + VIX/수급 시그널
│           └── yahoo-finance.ts            # Yahoo Finance OHLCV + VIX fetch
│
├── scripts/
│   └── export_auto_data.py  # 자율매매 DB → JSON export (웹 대시보드용)
│
├── infra/
│   └── logging_config.py   # 구조화 로깅 설정 (Phase 2에서 추가)
│
├── tasks/
│   ├── todo.md             # 작업 체크리스트
│   ├── lessons.md          # 학습 기록
│   └── improvements.md     # 개선사항 추적
│
└── DEVOPS_ANALYSIS.md      # 인프라/배포 종합 분석 (Phase 2)
```

## 기술 스택

### Python 백엔드
- Python 3.8+ (typing import 필수)
- pykrx (KRX 한국거래소 데이터)
- python-telegram-bot (알림)
- schedule (스케줄러)

### Next.js 프론트엔드
- Next.js 14 (App Router) + TypeScript
- Tailwind CSS (다크모드 기본)
- lightweight-charts v5 (TradingView 캔들차트)
- SWR (데이터 자동 갱신 60초)
- Yahoo Finance API (한국 주식: `{ticker}.KS`)
- Python 서버 불필요 — 지표 계산을 TS로 포팅

## 핵심 규칙
- pykrx 컬럼명은 한글이다: `시가`, `고가`, `저가`, `종가`, `거래량`
- Python 3.8 호환 필수: `list[str]` 대신 `List[str]` (typing import)
- 종목 추가/수정은 Python은 `config.py`, 웹은 `web/lib/constants.ts`의 `WATCH_LIST`
- lightweight-charts v5 API: `chart.addSeries(CandlestickSeries, opts)` (v4의 `addCandlestickSeries()` 아님)
- 한국 주식 색상 관례: 상승=빨강(#ef4444), 하락=파랑(#3b82f6)

## 커밋 보안 규칙
**커밋 금지 파일** (`.gitignore`에 등록됨):
- `.env`, `.env.*` — API 토큰, chat_id 등 민감 정보
- `.claude/` — Claude Code 세션/에이전트 데이터
- `.omc/state/`, `.omc/project-memory.json` — 플러그인 상태 파일
- `*.png`, `*.jpg` — 스크린샷/이미지 파일
- `node_modules/`, `__pycache__/`, `.next/` — 빌드 산출물
- `docs/edgecase_test.md` — 엣지 케이스 테스트 원칙 문서, 비공개 자산

**커밋 OK**:
- `.omc/plans/` — 로드맵/계획 문서

**커밋 전 체크**: `git status`로 민감 파일 미포함 확인 필수

## 자동 수행 규칙 (유저가 말하지 않아도 항상)
1. **작업 완료 시 커밋** — 의미 있는 단위로 커밋, 보안 파일 제외 확인
2. **문서 업데이트** — 구조/기능 변경 시 `tasks/todo.md`, `lessons.md`, `improvements.md` 갱신
3. **CLAUDE.md 동기화** — 프로젝트 구조 변경 시 아키텍처 섹션 업데이트
4. **Python ↔ TS 동기화** — 지표 로직 변경 시 양쪽 반영
5. **역할 분리 검증** — 코드 작성자와 테스트/리뷰/검증 담당자는 분리한다. 코드 작성자가 자기 변경을 직접 리뷰하거나 최종 검증하지 않는다.
6. **교훈 기록** — 실수나 새로운 발견은 `tasks/lessons.md`에 기록
7. **엣지 케이스 기준 준수** — 테스트 설계/보강 시 `docs/edgecase_test.md`를 우선 참고

## 에이전트 역할 분리 원칙
- 코드 작성 에이전트와 리뷰/테스트/검증 에이전트는 반드시 분리한다.
- 코드 작성 에이전트는 구현까지만 담당하고, 리뷰/테스트/최종 검증은 별도 에이전트가 맡는다.
- 이 원칙은 예외 없이 항상 적용한다.

## 파일 간 관계 (Python ↔ TypeScript 포팅 매핑)
| Python | TypeScript | 설명 |
|--------|-----------|------|
| `config.py` (WATCH_LIST, 파라미터) | `web/lib/constants.ts` | 종목 리스트, MA/RSI/MACD 설정값 |
| `signals/indicators.py` | `web/lib/indicators.ts` | MA, RSI, MACD, BB, OBV 계산 로직 + 신호 강도 |
| `signals/strategy.py` | `web/lib/strategy.ts` | 시그널 판단 (골든크로스, 과매도 등) |
| `signals/recovery.py` | `web/lib/recovery.ts` | 회복 분석 (체크리스트, 포지션 진단, 맥락 분류) |
| `bot/formatter.py` | (텔레그램 전용) | 메시지 포맷 (시그널 알림, 일일 브리핑, 주간 리포트) |

**중요**: 지표 로직을 수정하면 Python과 TypeScript 양쪽 모두 반영해야 한다.

## DevOps & 배포

### 현재 상태
- **Python 봇**: systemd user service (`signalight.service`) — 텔레그램 알림 봇
- **자율 트레이딩**: systemd user service (`signalight-auto.service`) — dry_run 스케줄 기반 자동매매
- **미국 자율 트레이딩**: systemd user service (`signalight-auto-us.service`) — Alpaca Paper Trading 스케줄 기반 자동매매
- **웹 대시보드**: Vercel 배포 완료 (https://web-iota-ten-60.vercel.app)
- **자율매매 대시보드 API**: 로컬/서버 DB가 있으면 실시간 조회, 없으면 `web/public/data/autonomous.json` fallback
- **데이터 소스**: pykrx, Yahoo Finance, 네이버 금융 크롤링, Google Gemini API
- **로깅**: 구조화 로깅 (콘솔+파일, 10MB 로테이션 × 5백업) — `infra/logging_config.py`
- **운영 이벤트 DB**: `storage/ops_events.db` — 파이프라인 실행 요약, 주문/오류 핵심 이벤트 저장
- **DB**: SQLite WAL 모드 (시그널 이력, 감성, LLM 판단, watch_list, 자율매매 상태)
- **Docker**: Multi-stage Dockerfile + docker-compose.yml 구성 완료
- **캐싱**: Python in-memory 4시간 TTL + 웹 API in-memory 5분 TTL

### 알려진 제한
- 네이버 금융 크롤링이 Vercel(해외 서버)에서 IP 차단됨 → investorData null (graceful degradation 동작)
- Vercel 서버리스 in-memory 캐시는 cold start마다 초기화됨

## 문서 관리
- `tasks/todo.md` — 작업 체크리스트 (완료되면 체크)
- `tasks/devlog.md` — 전체 개발 항목 추적 (Phase별 테이블)
- `tasks/lessons.md` — 개발 중 배운 교훈 기록
- `tasks/improvements.md` — 개선사항 추적 (우선순위별)
- `CLAUDE.md` (이 파일) — 프로젝트 가이드 (구조 변경 시 업데이트)
- `DEVOPS_ANALYSIS.md` — 인프라/배포 종합 분석 (Phase 2)
- `docs/edgecase_test.md` — 비공개 엣지 케이스 테스트 원칙 문서 (테스트 작성 시 상시 참고, 커밋 금지)

## 운영 로그 규칙
- 원본 운영 로그는 파일 + `journalctl`을 기준으로 본다.
- 전체 로그를 SQLite에 저장하지 않는다.
- `storage/ops_events.db`에는 장애 파악에 필요한 핵심 운영 이벤트만 저장한다.
- 새 파이프라인/러너 작업 시 `cycle_id`, `service`, `event`를 포함한 구조화 로그를 우선 사용한다.

---

## Workflow Orchestration

### 1. Plan Node Default
- 3+ 단계 또는 아키텍처 결정 시 plan mode 진입
- 문제 발생 시 즉시 재계획
- **사전 스펙 필수**: 1,000줄+ 또는 파일 10개+ 변경 예상 시 `tasks/spec-{feature}.md` 작성
  - 목표
  - 입력
  - 출력
  - 실패 조건
  - 완료 기준
- **테스트 선행**: 테스트 스켈레톤(함수명 + assert 조건)을 별도 커밋으로 먼저 생성
- 구현 커밋이 이를 통과시키는 2-커밋 패턴 유지
- **커밋 분리**: 1,000줄 초과 변경 시 최소 3커밋으로 분리
  - 모듈
  - 테스트
  - 마이그레이션

### 2. Subagent Strategy
- 연구/탐색/병렬 분석을 subagent로 오프로드
- 메인 컨텍스트 윈도우를 불필요하게 소모하지 않는다

### 3. Self-Improvement Loop
- 수정 후 `tasks/lessons.md` 업데이트
- 반복 실수는 규칙으로 승격

### 4. Verification Before Done
- 완료 전 테스트/로그/diff 확인 필수
- 완료 처리는 결정론적 검증 게이트 통과 후에만 한다

### 5. Demand Elegance (Balanced)
- 비자명한 변경에만 적용
- 단순 수정은 과도하게 복잡하게 만들지 않는다

### 6. Autonomous Bug Fixing
- 버그 보고 시 즉시 수정
- 사용자 컨텍스트 스위칭 최소화

### 7. Role Separation (역할 분리)
- **비단순 작업 기준**: 파일 3개 이상 변경, 새 모듈 생성, 또는 3단계 이상 구현
- 비단순 작업에서는 **구현 에이전트 ≠ 검증 에이전트** 원칙 적용
- 구현 완료 후 반드시 별도 에이전트로 테스트/리뷰 수행
  - `test-engineer`: 엣지 케이스 + 통합 테스트 설계
  - `code-reviewer` 또는 `critic`: 보안/에러/멱등성 리뷰
  - `verifier`: 최종 검증 (smoke check + 결과 비교)

## AI Collaboration Rules

아래 규칙은 AI 에이전트(Claude Code 포함)가 이 저장소에서 작업할 때 기본 운영 원칙으로 따른다.

### 1. 코드보다 의도를 먼저 검토
- 기본 검토 대상은 diff 자체보다 `목표`, `입력`, `출력`, `실패 조건`, `완료 기준`
- acceptance criteria 없는 비단순 작업은 바로 구현에 들어가지 않는다

### 2. 검증 규칙을 구현 전에 정한다
- 테스트와 verify 기준은 구현 후 보완이 아니라 사전 정의가 원칙
- pass/fail 기준 없는 기능은 완료 처리하지 않는다

### 3. 인간은 상류 의사결정에 집중
- 사람은 줄단위 코드 감시보다 데이터 충분성, 규칙 타당성, 운영 리스크를 우선 판단
- 특히 달핀통에서는 `데이터가 정말 판단을 뒷받침하는가`를 먼저 본다

### 4. 단일 에이전트를 신뢰하지 않는다
- 중요한 작업은 작성 역할과 검증 역할을 분리
- 가능하면 `critic`, `debugger`, `verifier` 성격의 검토를 따로 둔다

### 5. 완료 기준은 결정론적 게이트
- 아래 중 관련 항목 통과가 완료 기준
  - pytest
  - verify 스크립트
  - schema/domain 계약 검증
  - import/smoke check
  - 보안/정적 규칙
- "AI가 괜찮다고 판단했다"만으로 완료 처리하지 않는다

### 6. 고위험 변경은 자동 에스컬레이션
- 아래 변경은 반드시 추가 검토 또는 인간 판단을 거친다
  - 인증/권한
  - TypeDB schema/rules
  - DB 스키마
  - Compose/인프라
  - 외부 연동 비밀값/토큰
  - 새 의존성 추가

### 7. 변경은 작게 나누고, 검증은 자주 한다
- 큰 한 번의 리뷰보다 작은 변경과 자주 돌리는 검증을 우선
- 병렬 작업 시에는 기능 경계보다 파일 소유권 경계를 먼저 정한다

### 8. 운영 관측성이 없는 기능은 미완료다
- 새 기능은 가능하면 `request_id`, `trace_id`, `run_id` 또는 동등한 추적 키를 남긴다
- 처리 성공과 후처리 실패를 구분해 기록한다

### 9. 롤백/재실행 가능성을 함께 설계
- 새 기능은 실패 시 끌 수 있는 방법과 재실행 멱등성을 같이 본다
- 배치/도출/동기화는 부분 실패 후 재복구 경로가 있어야 한다

### 10. 줄단위 코드 리뷰는 예외적 정밀 검사로 사용
- 기본 게이트는 스펙, 검증, 관측성
- 줄단위 코드 리뷰는 아래에 집중
  - 보안 민감 변경
  - 복잡한 알고리즘
  - 다중 시스템 경계
  - 운영 장애 발생 지점

## Task Management

1. **Plan First**: `tasks/todo.md`에 체크리스트 작성
2. **Track Progress**: 진행 중 체크
3. **Capture Lessons**: `tasks/lessons.md`에 교훈 기록
4. **작업 로그**: 작업 종료 시 `tasks/worklogs/YYYY-MM-DD-{주제}.md`에 기록
   - 작업 시간: `HH:MM 시작 ~ HH:MM 완료 (약 N시간)`
   - 전/후 비교 + 이점
   - 커밋 목록
   - 테스트 결과
   - 미완료 항목
   - 대표님 보고 요약 (비개발자 1~3줄)
   - 템플릿: `tasks/worklog-template.md`

## Core Principles

- **Simplicity First**: 최소한의 변경으로 목표 달성
- **No Laziness**: 근본 원인 해결, 임시 수정 금지
- **Minimal Impact**: 필요한 부분만 변경
- **양쪽 동기화**: Python/TS 지표 로직 변경 시 반드시 양쪽 반영.
