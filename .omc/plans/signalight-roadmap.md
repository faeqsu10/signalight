# Signalight 로드맵

## 현재 아키텍처

```
signalight/
  main.py              # 스케줄러 진입점 (평일 16:00)
  config.py            # WATCH_LIST, MA/RSI/MACD 파라미터
  data/fetcher.py      # pykrx OHLCV 수집 (최근 60일)
  signals/indicators.py # MA, RSI, MACD 계산 (순수 함수)
  signals/strategy.py  # analyze() - 시그널 감지 (문자열 반환)
  bot/telegram.py      # 텔레그램 HTML 알림
```

### 설계 제약사항
1. `analyze()`는 문자열 리스트 반환 → 백테스팅에는 구조화된 Signal 객체 필요
2. `fetcher.py`는 "오늘 기준 최근 N일"만 조회 → 임의 기간 조회 필요
3. `indicators.py`의 순수 함수들은 그대로 재활용 가능
4. `config.py` 전역 상수 → 함수 인자 주입으로 전환 필요

---

## Phase 1: 백테스팅 엔진 (최우선)

### 파일 구조
```
backtest/
  __init__.py          # Signal, Trade, BacktestResult 데이터 모델
  engine.py            # 백테스트 실행 엔진
  report.py            # 결과 리포트 생성
  runner.py            # CLI 진입점 (python -m backtest.runner)
```

### 데이터 모델 (`backtest/__init__.py`)

```python
class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class Signal:
    date: date
    ticker: str
    name: str
    signal_type: SignalType
    source: str              # "MA_CROSS", "RSI", "MACD"
    strength: float          # 0.0 ~ 1.0
    description: str
    price: float

@dataclass
class Trade:
    ticker: str
    name: str
    entry_date: date
    entry_price: float
    entry_signal: str
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    exit_signal: Optional[str] = None
    shares: int = 0
    pnl: float = 0.0
    return_pct: float = 0.0

@dataclass
class BacktestResult:
    ticker: str
    name: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_return_per_trade: float
    trades: List[Trade]
    equity_curve: List[float]
```

### 기존 코드 수정

#### (A) `data/fetcher.py` - 기간 파라미터 확장
- `fetch_stock_data(ticker, start_date=None, end_date=None)` 시그니처로 변경
- 기존 호출부 하위 호환 유지

#### (B) `signals/strategy.py` - `generate_signals()` 추가
- 기존 `analyze()`는 그대로 유지 (마지막 1일만 비교)
- `generate_signals(df, ticker, name, **params)` 추가: 전체 기간 순회하며 Signal 객체 리스트 반환
- 파라미터를 함수 인자로 받되 기본값은 config에서

### 백테스트 엔진 (`backtest/engine.py`)

```python
class BacktestEngine:
    def __init__(self,
                 initial_capital=10_000_000,
                 commission_rate=0.00015,
                 slippage_rate=0.001,
                 position_size=1.0):

    def run(self, df, signals) -> BacktestResult:
        # 1. 시간순 시그널 순회
        # 2. BUY → 포지션 없으면 매수 (다음날 시가 체결)
        # 3. SELL → 포지션 있으면 매도
        # 4. 매일 equity_curve 갱신
        # 5. MDD, 승률 계산
```

### 데이터 흐름

```
fetcher.fetch_stock_data(ticker, start, end)
    → pd.DataFrame (OHLCV)
    → strategy.generate_signals(df, ticker, name)
    → List[Signal]
    → BacktestEngine.run(df, signals)
    → BacktestResult
    → report.format_text_report(result) → 콘솔
    → report.format_telegram_report(result) → 텔레그램
```

### CLI 사용법
```bash
python -m backtest.runner --ticker 005930 --name 삼성전자 \
    --start 20250101 --end 20251231 --capital 10000000 --notify
```

### 수락 기준

| # | 기준 | 검증 방법 |
|---|------|----------|
| AC-1 | `generate_signals()`가 과거 전체 기간 시그널 감지 | 삼성전자 1년 데이터로 Signal 리스트 반환 확인 |
| AC-2 | BUY→SELL 라운드트립 정확 추적 | 수동 테스트 DataFrame으로 Trade 결과 검증 |
| AC-3 | 수수료/슬리피지 반영 | commission=0 vs 기본값 결과 비교 |
| AC-4 | MDD 계산 정확 | equity=[100,110,90,95] → MDD=18.18% 검증 |
| AC-5 | 기존 main.py 영향 없음 | `python main.py` 정상 동작 확인 |
| AC-6 | 텔레그램 리포트 전송 | `--notify` 플래그로 수신 확인 |
| AC-7 | CLI 백테스트 실행 | `python -m backtest.runner` 성공 |

### 리스크

| 리스크 | 대응 |
|--------|------|
| pykrx 장기 조회 실패 | retry + 캐싱(csv) 추가 |
| 미래 정보 편향 | 시그널 다음날 시가 체결 규칙 |
| 거래 횟수 부족 | < 10회 시 경고 표시 |
| config 전역 상수 의존 | 함수 인자 주입 (기본값=config) |

---

## Phase 2: 지표 확장 + 복합 전략

### 파일 구조
```
signals/
  indicators.py     # + 볼린저밴드, 스토캐스틱, OBV, ATR
  conditions.py     # (신규) Condition ABC, 개별 조건 클래스
  composite.py      # (신규) CompositeStrategy 조합 엔진
  strategy.py       # 리팩터링: CompositeStrategy 기반
```

### 신규 지표
- `calc_bollinger_bands(closes, period=20, num_std=2.0)` → (upper, middle, lower)
- `calc_stochastic(highs, lows, closes, k=14, d=3)` → (%K, %D)
- `calc_obv(closes, volumes)` → OBV Series
- `calc_atr(highs, lows, closes, period=14)` → ATR Series

### 복합 전략 프레임워크

```python
class Condition(ABC):
    def evaluate(self, df, index) -> (SignalType|None, float, str)

class CompositeStrategy:
    def __init__(self, mode="ALL"|"ANY"|"MAJORITY"|"WEIGHTED")
    def add_condition(self, condition, weight=1.0)
    def generate_signals(self, df, ticker, name) -> List[Signal]
```

### 수락 기준
- 신규 지표 각각 단위 테스트 통과
- CompositeStrategy(mode="ALL")로 RSI+MACD 복합 시그널 생성 가능
- 복합 전략 백테스트 결과를 단일 전략과 비교 출력 가능
- 기존 analyze() 정상 동작 유지

---

## Phase 3: 봇 고도화 + 인프라

### 텔레그램 인터랙티브 명령어
- `/add 066570 LG전자` - 종목 추가
- `/remove 005930` - 종목 제거
- `/list` - 감시 종목 목록
- `/signal` - 즉시 시그널 체크
- `/backtest 005930 20250101 20251231` - 백테스트 실행
- `/status` - 봇 상태

### 인프라
- `main.py`: schedule → python-telegram-bot `Application.job_queue` 전환
- `config.py`: WATCH_LIST 하드코딩 → `data/watchlist.json` 영속화
- Docker + docker-compose
- 구조화된 로깅 (print → logging)

### 수락 기준
- 텔레그램 명령어로 종목 추가/제거/백테스트 가능
- docker-compose up으로 봇 기동
- 재시작 후 종목 목록 유지
- 구조화된 로그 파일 기록

---

## 구현 순서

```
Phase 1 (백테스팅)
  [1] fetcher.py 기간 파라미터 확장
  [2] Signal/Trade/BacktestResult 데이터 모델
  [3] generate_signals() 추가
  [4] BacktestEngine 핵심 엔진
  [5] 리포트 생성
  [6] CLI 러너
  의존성: [1] → [3] → [4] → [5] → [6], [2]는 [3],[4] 선행

Phase 2 (지표 확장)
  [7] 신규 지표 함수
  [8] Condition 인터페이스
  [9] CompositeStrategy 엔진
  [10] strategy.py 리팩터링
  의존성: [7] → [8] → [9] → [10]

Phase 3 (봇 + 인프라)
  [11] 텔레그램 핸들러
  [12] 동적 watchlist
  [13] main.py 전환
  [14] Docker화
  [15] 로깅 통합
  의존성: [11],[12] → [13] → [14],[15]
```
