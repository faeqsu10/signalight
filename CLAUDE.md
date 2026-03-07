# Signalight - Claude Code 프로젝트 가이드

## 프로젝트 개요
한국 주식 매매 시그널(매수/매도 타이밍) 분석 시스템
- **텔레그램 봇**: Python 기반, 평일 자동 알림
- **웹 대시보드**: Next.js 기반, 실시간 차트 + 시그널 표시

## 아키텍처

```
signalight/
├── [Python 백엔드] 텔레그램 알림 봇
│   ├── config.py           # 설정 (종목, 지표 파라미터, 환경변수)
│   ├── main.py             # 진입점 + 스케줄러 (평일 장중 30분 간격)
│   ├── data/
│   │   ├── fetcher.py      # pykrx로 KRX OHLCV 데이터 수집
│   │   └── news.py         # 네이버 금융 종목별 뉴스 크롤러
│   ├── signals/
│   │   ├── indicators.py   # 기술적 지표 (MA, RSI, MACD)
│   │   ├── strategy.py     # 시그널 판단 로직
│   │   └── sentiment.py    # Claude Haiku 뉴스 감성 분석
│   └── bot/
│       ├── telegram.py     # 텔레그램 메시지 전송
│       └── formatter.py    # 메시지 포맷터 (시그널 알림, 일일 브리핑, 주간 리포트)
│
├── [Next.js 프론트엔드] 웹 대시보드
│   └── web/
│       ├── app/
│       │   ├── page.tsx                    # 메인 대시보드 (SWR 60초 갱신)
│       │   ├── layout.tsx                  # 레이아웃 (다크모드)
│       │   └── api/stock/[ticker]/route.ts # API Route (데이터+지표+시그널)
│       ├── components/
│       │   ├── CandleChart.tsx             # 캔들차트 + MA 오버레이
│       │   ├── RSIChart.tsx                # RSI 라인 + 30/70 기준선
│       │   ├── MACDChart.tsx               # MACD/Signal + 히스토그램
│       │   ├── SignalPanel.tsx             # 시그널 현황 패널
│       │   └── PriceInfo.tsx               # 현재가, 등락률, 종합 시그널
│       └── lib/
│           ├── constants.ts                # config.py 포팅 + VIX/수급 설정값
│           ├── indicators.ts               # indicators.py 포팅
│           ├── investor.ts                 # 네이버 금융 외인/기관 순매수 fetch
│           ├── strategy.ts                 # strategy.py 포팅 + VIX/수급 시그널
│           └── yahoo-finance.ts            # Yahoo Finance OHLCV + VIX fetch
│
└── tasks/
    ├── todo.md             # 작업 체크리스트
    ├── lessons.md          # 학습 기록
    └── improvements.md     # 개선사항 추적
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

**커밋 OK**:
- `.omc/plans/` — 로드맵/계획 문서

**커밋 전 체크**: `git status`로 민감 파일 미포함 확인 필수

## 자동 수행 규칙 (유저가 말하지 않아도 항상)
1. **작업 완료 시 커밋** — 의미 있는 단위로 커밋, 보안 파일 제외 확인
2. **문서 업데이트** — 구조/기능 변경 시 `tasks/todo.md`, `lessons.md`, `improvements.md` 갱신
3. **CLAUDE.md 동기화** — 프로젝트 구조 변경 시 아키텍처 섹션 업데이트
4. **Python ↔ TS 동기화** — 지표 로직 변경 시 양쪽 반영
5. **테스트 검증** — 코드 작성 후 import/실행 테스트로 동작 확인
6. **교훈 기록** — 실수나 새로운 발견은 `tasks/lessons.md`에 기록

## 파일 간 관계 (Python ↔ TypeScript 포팅 매핑)
| Python | TypeScript | 설명 |
|--------|-----------|------|
| `config.py` (WATCH_LIST, 파라미터) | `web/lib/constants.ts` | 종목 리스트, MA/RSI/MACD 설정값 |
| `signals/indicators.py` | `web/lib/indicators.ts` | MA, RSI, MACD 계산 로직 |
| `signals/strategy.py` | `web/lib/strategy.ts` | 시그널 판단 (골든크로스, 과매도 등) |
| `bot/formatter.py` | (텔레그램 전용) | 메시지 포맷 (시그널 알림, 일일 브리핑, 주간 리포트) |

**중요**: 지표 로직을 수정하면 Python과 TypeScript 양쪽 모두 반영해야 한다.

## 문서 관리
- `tasks/todo.md` — 작업 체크리스트 (완료되면 체크)
- `tasks/lessons.md` — 개발 중 배운 교훈 기록
- `tasks/improvements.md` — 개선사항 추적 (우선순위별)
- `CLAUDE.md` (이 파일) — 프로젝트 가이드 (구조 변경 시 업데이트)

---

## Workflow Orchestration

### 1. Plan First
- 3단계 이상이거나 구조적 결정이 필요한 작업은 plan mode 진입
- 문제가 생기면 즉시 멈추고 재계획 - 밀어붙이지 않는다
- 검증 단계도 계획에 포함
- 모호함을 줄이기 위해 상세 스펙을 먼저 작성

### 2. Subagent 전략
- 메인 컨텍스트를 깔끔하게 유지하기 위해 subagent 적극 활용
- 리서치, 탐색, 병렬 분석은 subagent에 위임
- 복잡한 문제는 subagent로 더 많은 compute 투입
- subagent당 하나의 명확한 목표

### 3. 자기 개선 루프
- 유저 수정을 받으면: `tasks/lessons.md`에 패턴 기록
- 같은 실수를 방지하는 규칙 작성
- 세션 시작 시 lessons 검토

### 4. 완료 전 검증
- 동작 증명 없이 완료 처리하지 않는다
- 테스트 실행, 로그 확인, 정상 동작 시연
- "시니어 엔지니어가 승인할 수준인가?" 자문

### 5. 균형 잡힌 우아함
- 비단순 변경: "더 우아한 방법이 있는가?" 자문
- 단순하고 명확한 수정은 오버엔지니어링 금지

### 6. 자율적 버그 수정
- 버그 리포트 받으면 질문 없이 해결
- 로그, 에러, 실패 테스트 확인 후 직접 수정

## Task Management

1. `tasks/todo.md`에 체크리스트로 계획 작성
2. 구현 전 계획 확인
3. 진행하면서 완료 항목 체크
4. 각 단계마다 변경사항 요약
5. 결과를 `tasks/todo.md`에 기록
6. 수정 받으면 `tasks/lessons.md` 업데이트
7. 개선 아이디어는 `tasks/improvements.md`에 기록

## Core Principles

- **단순함 우선**: 변경은 최대한 간결하게. 영향 범위 최소화.
- **근본 원인 해결**: 임시 수정 금지. 시니어 개발자 기준.
- **최소 영향**: 필요한 부분만 수정. 버그 유입 방지.
- **양쪽 동기화**: Python/TS 지표 로직 변경 시 반드시 양쪽 반영.
