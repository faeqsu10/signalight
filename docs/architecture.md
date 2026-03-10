# Signalight 시스템 아키텍처

## 개요

Signalight는 두 개의 독립적인 프로세스로 구성된 한국 주식 매매 시그널 분석 시스템이다.

| 프로세스 | 진입점 | 역할 | 배포 |
|----------|--------|------|------|
| 텔레그램 알림 봇 | `main.py` | 평일 장 마감 후 시그널 분석 결과를 텔레그램으로 전송 | `signalight.service` |
| 자율 트레이딩 파이프라인 | `autonomous/runner.py` | 스캔 → 분석 → 결정 → 실행 → 평가 자동화 | `signalight-auto.service` |

두 프로세스는 공통 신호 분석 모듈(`signals/`, `trading/`, `storage/`)을 공유하되, 스케줄과 실행 흐름은 완전히 분리되어 있다.

---

## 6단계 파이프라인 다이어그램

자율 트레이딩 파이프라인(`autonomous/pipeline.py`)의 전체 흐름:

```
+------------------+     +---------------------+     +------------------+
|  1. 데이터 수집  | --> |  2. 탑 종목 스캔/   | --> |  3. 매매 결정    |
|                  |     |     분석             |     |                  |
|  pykrx, Yahoo,  |     |  market_scanner.py   |     |  trading/rules.py|
|  네이버, Gemini  |     |  signals/*           |     |  decision.py     |
+------------------+     +---------------------+     +------------------+
                                                               |
+------------------+     +---------------------+     +------------------+
|  6. 자동 개선    | <-- |  5. 성과 평가       | <-- |  4. 안전 실행    |
|                  |     |                     |     |                  |
|  optimizer.py    |     |  evaluator.py       |     |  execution.py    |
|  (성과 기반 튜닝)|     |  state.py           |     |  kiwoom_client.py|
+------------------+     +---------------------+     +------------------+
```

텔레그램 알림 봇(`main.py`)은 1단계와 2단계만 수행하고, 결과를 텔레그램으로 전송한다.

---

## 데이터 소스

| 소스 | 모듈 | 제공 데이터 | 비고 |
|------|------|------------|------|
| pykrx | `data/fetcher.py` | KRX OHLCV 120일, 거래량 | 컬럼명 한글: `시가`, `고가`, `저가`, `종가`, `거래량` |
| Yahoo Finance | `data/fetcher.py` | VIX 지수 | User-Agent 헤더 필수, v8 chart API |
| 네이버 금융 | `data/investor.py` | 외인/기관 순매수 | 해외 서버(Vercel)에서 IP 차단 가능 |
| 네이버 금융 | `data/news.py` | 종목별 최근 뉴스 | 크롤링 기반 |
| Google Gemini | `signals/sentiment.py` | 뉴스 감성 점수 (-1.0 ~ 1.0) | Gemini 2.5 Flash REST API |
| Google Gemini | `signals/llm_analyzer.py` | 상충 시그널 종합 판단 | 합류 점수 + 감성 + 수급 통합 해석 |

---

## 1단계 — 데이터 수집

**담당 모듈**: `data/fetcher.py`, `data/investor.py`, `data/news.py`

```
data/
├── fetcher.py      # pykrx KRX OHLCV + Yahoo VIX
├── investor.py     # 네이버 금융 외인/기관 순매수 크롤링
└── news.py         # 네이버 금융 종목별 뉴스 크롤링
```

- `fetcher.py`: pykrx로 KRX OHLCV 120일치를 수집. VIX는 Yahoo Finance v8 API로 별도 조회. `main.py`에서 VIX는 1회만 조회하여 재사용한다.
- `investor.py`: 네이버 금융 외인/기관 순매수 데이터를 크롤링. 수급 시그널 가중치(1.5x) 적용에 사용된다.
- `news.py`: 종목별 최근 뉴스 제목 + URL 수집. Gemini 감성 분석의 입력값이 된다.

---

## 2단계 — 스캔 및 분석

### 2-1. 유니버스 스캔

**담당 모듈**: `scanner/market_scanner.py`, `scanner/kospi200_tickers.py`, `autonomous/universe.py`

```
scanner/
├── market_scanner.py       # KOSPI200 전체 스캔 (3가지 조건)
└── kospi200_tickers.py     # pykrx fallback 정적 종목 리스트
```

`market_scanner.py`가 수행하는 3가지 스캔과 점수:

| 스캔 조건 | 함수 | 점수 |
|----------|------|------|
| 골든 크로스 (MA10 > MA50 이탈 + 방향 전환) | `golden_cross` | 3점 |
| RSI 과매도 회복 (RSI 30 이하 반등) | `rsi_oversold` | 2점 |
| 거래량 급증 (5일 평균 대비 3배 이상) | `volume_surge` | 1점 |

`autonomous/universe.py`는 위 스캔 결과를 복합 필터링(유동성, 보유 종목 제외 등)하여 최종 매수 후보 리스트를 반환한다.

### 2-2. 기술적 지표

**담당 모듈**: `signals/indicators.py`

총 9개 지표 계산:

| 지표 | 설명 |
|------|------|
| MA (이동평균) | MA10, MA50 — 골든/데드 크로스 판단 기준 |
| Wilder RSI | 과매수(70)/과매도(30) — 일반 EMA RSI와 다름 |
| MACD | MACD 라인, 시그널 라인, 히스토그램 |
| ATR | 손절/목표가 배수 계산 기준 |
| 볼린저 밴드 | 상단/하단 밴드 돌파 여부 |
| OBV | 거래량 누적 추세 확인 |
| StochRSI | RSI의 스토캐스틱 응용 — 단기 반전 포착 |
| 거래량 비율 | 5일 평균 대비 현재 거래량 |
| VIX | 시장 공포 지수 — 포지션 크기 배수 결정 |

### 2-3. 합류 점수 및 시장 레짐

**담당 모듈**: `signals/strategy.py`

- **합류 점수(confluence score)**: 여러 시그널이 같은 방향으로 정렬될수록 높은 점수 부여
- **수급 가중치**: 외인/기관 순매수 시그널에 1.5배 가중치 적용
- **시장 레짐 감지**: KOSPI MA200 기준으로 `uptrend` / `sideways` / `downtrend` 판별

### 2-4. 감성 분석 및 LLM 판단

**담당 모듈**: `signals/sentiment.py`, `signals/llm_analyzer.py`

- `sentiment.py`: 뉴스 제목 리스트를 Gemini에 전달 → 감성 점수(-1.0 ~ 1.0) 반환. DB에 캐싱(중복 API 호출 방지).
- `llm_analyzer.py`: 기술적 시그널과 감성 점수가 상충할 때 Gemini로 종합 판단 수행.

---

## 3단계 — 매매 결정

**담당 모듈**: `trading/rules.py`, `autonomous/decision.py`

### 진입 임계값 (시장 레짐별)

| 레짐 | 합류 점수 임계값 | 설명 |
|------|----------------|------|
| `uptrend` | 2.5 | 상승장 — 낮은 기준으로 적극 진입 |
| `sideways` | 3.5 | 횡보장 — 중간 기준 |
| `downtrend` | 4.5 | 하락장 — 높은 기준으로 선별 진입 |

### VIX 포지션 크기 배수

| VIX 범위 | 배수 |
|----------|------|
| 15 이하 (안정) | `VIX_POSITION_MULT_CALM` |
| 15 ~ 25 (보통) | `VIX_POSITION_MULT_NORMAL` |
| 25 ~ 30 (공포) | `VIX_POSITION_MULT_FEAR` |
| 30 초과 (극도 공포) | `VIX_POSITION_MULT_EXTREME` |

### 매수 게이트 조건

`trading/rules.py`의 `_has_trend_gate()`: MA 크로스/정렬 또는 MACD 크로스 중 하나 이상 충족해야 진입 허용.

### 분할 매수

- `SPLIT_BUY_PHASES`: 분할 단계 수 (기본 3단계)
- `SPLIT_BUY_CONFIRM_DAYS`: 다음 단계 진입 전 확인 대기일
- `SPLIT_BUY_PHASE3_BONUS`: 3단계 진입 시 추가 비중 보너스

### 포트폴리오 제약 (`autonomous/decision.py`)

- 최대 보유 종목 수: `MAX_POSITIONS`
- 최대 단일 종목 비중: `MAX_SINGLE_POSITION_PCT`
- 최대 섹터별 종목 수: `MAX_SECTOR_POSITIONS`
- 총 노출 한도: `MAX_EXPOSURE_PCT`

---

## 4단계 — 안전 실행

**담당 모듈**: `autonomous/execution.py`, `trading/kiwoom_client.py`, `trading/position_tracker.py`

### 안전장치 계층

```
execute_buy() / execute_sell()
        |
        v
  +-----------+
  | 킬스위치   |  KILL_SWITCH 환경변수 또는 파일 존재 시 즉시 중단
  +-----------+
        |
        v
  +-----------+
  | 장중 시간 |  09:00 ~ 15:20 KST 범위 밖이면 주문 거부
  +-----------+
        |
        v
  +--------------+
  | 서킷 브레이커 |  일일 손실 한도 초과 시 당일 신규 주문 차단
  +--------------+
        |
        v
  +----------+
  | dry_run  |  dry_run=True면 실제 API 호출 없이 simulated 상태 반환
  +----------+
        |
        v
  +--------------+
  | KiwoomClient |  키움 REST API OAuth 인증 + 실주문 실행
  +--------------+
```

### 모듈별 역할

| 모듈 | 역할 |
|------|------|
| `autonomous/execution.py` (`SafeExecutor`) | 안전장치 체크 + `trading/executor.py` 래핑 |
| `trading/kiwoom_client.py` | 키움 REST API 래퍼 (OAuth, 잔고 조회, 매수/매도 주문) |
| `trading/executor.py` | 주문 실행 + 손실한도/비중한도 안전장치 |
| `trading/position_tracker.py` | 가상 포지션 SQLite 추적 (분할단계, 트레일링 스탑) |
| `trading/portfolio.py` | 포트폴리오 비중 관리 |

### 손절 / 목표가

- 손절: 진입가 - (ATR × `STOP_LOSS_ATR_MULT`) — 레짐별 배수 다름
- 1차 목표: 진입가 + (ATR × `TARGET1_ATR_MULT`)
- 2차 목표: 진입가 + (ATR × `TARGET2_ATR_MULT`)
- 트레일링 스탑: 고점 - (ATR × `TRAILING_STOP_ATR_MULT`)
- 최대 보유일: `MAX_HOLDING_DAYS` 초과 시 강제 청산

---

## 5단계 — 성과 평가

**담당 모듈**: `autonomous/evaluator.py`, `autonomous/state.py`

### evaluator.py

- `daily_summary()`: 매일 장 마감 후 일일 매매 결과(매수/매도 건수, 실현 PnL) 텔레그램 전송 (`AUTO_TRADE_CHAT_ID`)
- `weekly_report()`: 주간 누적 수익률, 승률, MDD 계산 및 텔레그램 전송
- `send_trade_notification()`: 매수/매도 체결 즉시 개별 알림 전송

### state.py

- `PipelineState`: SQLite WAL 모드로 파이프라인 상태 영속화
- 기록 테이블: `auto_trade_log`, `daily_pnl`, `equity_snapshots`
- 주요 메서드: `record_trade()`, `record_daily_pnl()`, `save_equity_snapshot()`, `get_recent_trades()`

---

## 6단계 — 자동 개선 (StrategyOptimizer)

**모듈**: `autonomous/optimizer.py`

매매 결과를 분석하여 전략 파라미터를 보수적으로 자동 조정한다.

### 조정 대상

| 파라미터 | 기본값 | 조정 범위 | 조정 기준 |
|----------|--------|-----------|-----------|
| golden_cross 가중치 | 3.0 | 2.1~3.9 | 스캔별 승률 비례 |
| rsi_oversold 가중치 | 2.0 | 1.4~2.6 | 스캔별 승률 비례 |
| volume_surge 가중치 | 1.0 | 0.7~1.3 | 스캔별 승률 비례 |
| uptrend 매수 임계값 | 2.5 | 2.0~3.0 | 전체 승률 기반 |
| sideways 매수 임계값 | 3.5 | 3.0~4.0 | 전체 승률 기반 |
| downtrend 매수 임계값 | 4.5 | 4.0~5.0 | 전체 승률 기반 |

### 가드레일

- **최소 샘플**: 20건 이상 거래 후 활성화 (과적합 방지)
- **가중치 범위**: 기본값 대비 +-30%
- **임계값 범위**: +-0.5
- **승률 > 60%**: 임계값 소폭 하향 (진입 쉽게)
- **승률 < 40%**: 임계값 소폭 상향 (진입 어렵게)

### 데이터 흐름

```
매수 체결 시: scan_signals를 trade log reason에 기록
  |
  v
주간 평가 시: 청산된 포지션의 결과를 optimizer_scan_results에 기록
  |
  v
다음 일일 사이클 시작 시: get_optimized_params()로 조정된 파라미터 적용
  |
  v
universe.py: 조정된 scan_weights로 후보 점수 산정
```

### DB 테이블

| 테이블 | 컬럼 | 설명 |
|--------|------|------|
| `optimizer_scan_results` | ticker, scan_signal, pnl_pct, is_win, created_at | 스캔 시그널별 매매 성과 |

---

## DB 스키마 요약

### `storage/db.py` (메인 봇 + 공유)

| 테이블 | 컬럼 | 설명 |
|--------|------|------|
| `signal_history` | ticker, signal_type, score, regime, created_at | 시그널 이력 |
| `news_sentiment` | ticker, headline, sentiment_score, analyzed_at | 뉴스 감성 캐시 |
| `llm_analysis` | ticker, prompt_hash, result_json, created_at | LLM 판단 캐시 |
| `watch_list` | ticker, name, added_at | DB 기반 감시 종목 |
| `subscribers` | chat_id, active, created_at | 텔레그램 구독자 |

### `trading/position_tracker.py`

| 테이블 | 컬럼 | 설명 |
|--------|------|------|
| `virtual_positions` | ticker, name, entry_price, quantity, split_phase, trailing_stop, status, opened_at, closed_at | 가상 포지션 추적 |

### `autonomous/state.py`

| 테이블 | 컬럼 | 설명 |
|--------|------|------|
| `auto_trade_log` | ticker, name, side, price, quantity, pnl_amount, pnl_pct, reason, trade_date | 자율매매 거래 로그 |
| `auto_daily_pnl` | trade_date, realized_pnl, trades_count, wins, losses | 일별 PnL 집계 |
| `auto_equity_snapshots` | snapshot_date, total_equity, invested_amount, cash_amount, open_positions | 에퀴티 스냅샷 |

### `autonomous/optimizer.py`

| 테이블 | 컬럼 | 설명 |
|--------|------|------|
| `optimizer_scan_results` | ticker, scan_signal, pnl_pct, is_win, created_at | 스캔 시그널별 매매 성과 추적 |

---

## 모듈 입출력 표

| 모듈 | 입력 | 출력 |
|------|------|------|
| `data/fetcher.py` | ticker 문자열, 조회일수 | OHLCV DataFrame (pykrx 한글 컬럼), VIX float |
| `data/investor.py` | ticker 문자열 | 외인/기관 순매수 dict |
| `data/news.py` | ticker 문자열 | 뉴스 제목+URL 리스트 |
| `scanner/market_scanner.py` | 전체 KOSPI200 ticker 리스트 | 조건별 점수 포함 후보 종목 리스트 |
| `signals/indicators.py` | OHLCV DataFrame | 9개 지표값 dict (MA, RSI, MACD, ATR, BB, OBV, StochRSI, 거래량비율, VIX) |
| `signals/strategy.py` | 지표값 dict + 수급 dict + VIX | 합류 점수, 시그널 목록, 시장 레짐 문자열 |
| `signals/sentiment.py` | 뉴스 제목 리스트 | 감성 점수 float (-1.0 ~ 1.0), DB 캐싱 |
| `signals/llm_analyzer.py` | 지표값 + 합류 점수 + 감성 점수 | LLM 종합 판단 dict (action, reason) |
| `signals/recovery.py` | OHLCV + 지표 + 수급 | 회복 체크리스트 6항목, 점수, 포지션 진단 |
| `trading/rules.py` (`TradeRule`) | 시그널 dict + 포지션 dict + 레짐 | 매수/매도 추천 dict (action, stop_loss, target1, target2) |
| `autonomous/universe.py` | 보유 ticker set | 매수 후보 종목 리스트 (ticker, name, scan_score) |
| `autonomous/analyzer.py` | 후보 종목 리스트 | 지표+시그널+감성 포함 분석 결과 리스트 |
| `autonomous/decision.py` | 분석 결과 리스트 + 포지션 상태 | 매수/매도 결정 리스트 (recommendation, stock_data) |
| `autonomous/execution.py` (`SafeExecutor`) | 결정 dict + 추천 dict | `Order` 객체 (status: filled/simulated/rejected) |
| `autonomous/evaluator.py` | PipelineState + PositionTracker | 텔레그램 메시지 전송, 반환값 없음 |
| `bot/formatter.py` | 시그널 분석 결과 dict | 텔레그램 마크다운 메시지 문자열 |
| `bot/telegram.py` | 메시지 문자열, chat_id | 텔레그램 전송 (4096자 분할, 3회 재시도) |

---

## 배포 구성

### systemd 서비스

```
/etc/systemd/system/ (또는 ~/.config/systemd/user/)
├── signalight.service       # main.py — 텔레그램 알림 봇
└── signalight-auto.service  # autonomous/runner.py — 자율매매 (dry_run)
```

**signalight.service** (텔레그램 알림 봇):
- 평일 장 마감 후 1회 실행 (`schedule` 기반)
- 워치리스트 종목 분석 → 텔레그램 시그널 알림

**signalight-auto.service** (자율 트레이딩):
- 장 시작 전 일일 사이클 실행 (`autonomous/runner.py --once`)
- 장중 손절 모니터링 (`run_intraday_monitor`)
- 금요일 주간 성과 평가 (`run_weekly_evaluation`)
- 현재 `dry_run=True` 모드 운영 중 (실제 주문 미발생)

### 웹 대시보드

- **배포**: Vercel (https://web-iota-ten-60.vercel.app)
- **스택**: Next.js 14 App Router + TypeScript + Tailwind CSS
- **차트**: lightweight-charts v5 (`addSeries(CandlestickSeries, opts)` API)
- **데이터 갱신**: SWR 60초 자동 갱신
- **캐싱**: in-memory 5분 TTL (cold start마다 초기화)
- **제한**: 네이버 금융 크롤링이 해외 IP에서 차단됨 → `investorData: null` graceful degradation

### 알려진 배포 제약

| 제약 | 원인 | 대응 |
|------|------|------|
| 네이버 금융 수급 데이터 누락 | Vercel 해외 서버 IP 차단 | `investorData: null` 허용, 프론트엔드 graceful degradation |
| 웹 캐시 cold start 초기화 | Vercel 서버리스 in-memory 특성 | 첫 요청 시 지연 감수, 재계산 |
| VIX 중복 조회 | Yahoo Finance API 호출 비용 | `main.py`에서 1회만 조회 후 전달 |

---

## Python - TypeScript 포팅 매핑

웹 대시보드는 Python 서버 없이 독립 실행되므로, 지표 로직이 TypeScript로 포팅되어 있다.
지표 로직 변경 시 Python과 TypeScript 양쪽을 반드시 동기화해야 한다.

| Python | TypeScript | 설명 |
|--------|-----------|------|
| `config.py` | `web/lib/constants.ts` | WATCH_LIST, MA/RSI/MACD 파라미터 |
| `signals/indicators.py` | `web/lib/indicators.ts` | MA, Wilder RSI, MACD, BB, OBV 계산 |
| `signals/strategy.py` | `web/lib/strategy.ts` | 합류 점수, 시그널 판단, 레짐 감지 |
| `signals/recovery.py` | `web/lib/recovery.ts` | 회복 체크리스트, 포지션 진단 |
| `data/investor.py` | `web/lib/investor.ts` | 네이버 금융 외인/기관 수급 fetch |

---

## 로깅 및 모니터링

**담당 모듈**: `infra/logging_config.py`

- 콘솔 + 파일 동시 출력
- 파일 로테이션: 10MB × 5백업
- 구조화 로그 포맷: `timestamp | level | logger_name | message`
- SQLite WAL 모드: 동시 읽기/쓰기 충돌 방지

---

## 캐싱 전략

| 레이어 | 위치 | TTL | 대상 |
|--------|------|-----|------|
| Python in-memory | `main.py`, `autonomous/analyzer.py` | 4시간 | VIX, OHLCV |
| DB 캐시 | `storage/db.py` (news_sentiment, llm_analysis) | 없음 (hash 기반 중복 방지) | Gemini API 응답 |
| 웹 in-memory | `web/app/api/*/route.ts` | 5분 | Yahoo Finance OHLCV, 지표 계산 결과 |
