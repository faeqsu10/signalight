# Signalight 인프라/배포 종합 분석

**분석 날짜**: 2026-03-08
**프로젝트 단계**: Phase 2 진행 중 (Phase 3 예정)
**현재 상태**: Python 봇 systemd 운영 중, 웹 대시보드 미배포

---

## 1. 현황 요약

### Python 텔레그램 봇
- **배포**: systemd user service (`signalight.service` 수동 설정)
- **실행**: 평일 09:30~15:30 매 30분 신호 체크 + 장마감 리포트
- **에러 처리**: try/except 격리, 부분 실패는 기존 기능 영향 없음
- **로깅**: stdout/stderr 콘솔 출력만 (파일 로깅 없음)
- **재시작 정책**: systemd 설정 필요 (현재 미확인)

### Next.js 웹 대시보드
- **상태**: 로컬 개발 서버만 운영 (미배포)
- **API**: Next.js API Route (병렬 데이터 fetch, 에러 핸들링 기본)
- **데이터 갱신**: SWR 60초 자동 갱신
- **배포**: Vercel 준비 상태 (root directory 지정 필요)

### 데이터 소스
- **pykrx**: KRX 일일 OHLCV (장 폐장 후 수집)
- **Yahoo Finance v8**: VIX, 기간별 차트 (rate limit 있음)
- **네이버 금융**: 외인/기관 매매동향, 뉴스 (크롤링, 안정성 낮음)
- **Google Gemini**: 감성 분석 (선택적, REST API, timeout 10초)

---

## 2. 주요 이슈 분석

### 2.1 Python 봇 안정성 (Critical)

**문제점:**
- 장 오픈 시 (`check_signals()`) 데이터 소스 3개 동시 호출, 한 곳 실패 시 전체 영향
  - pykrx + Yahoo Finance VIX + 네이버 금융 외인/기관 + 뉴스 + Gemini
  - 네이버 금융 크롤링: 페이지 레이아웃 변경 시 파싱 실패 → 수급 데이터 없음
  - 크롤링은 법적 회색 지대 (Terms of Service 위반 위험)
- 에러 메시지가 콘솔에만 출력 → 실제 장중 문제 발생 시 발견 어려움
- `send_message()` 실패 시 텔레그램 전송 못 함 (중요 신호 누락 가능)
- pykrx 호출 timeout 없음 (30분마다 최대 몇십 초 대기 가능)
- systemd 재시작 정책 미확인 → 프로세스 다운 시 자동 복구 불확실

**영향도**: 높음 (평일 장중 수익성 영향, 신호 누락 가능)

---

### 2.2 웹 대시보드 배포 미흡

**문제점:**
- 로컬 개발 서버만 운영 중 (외부 접근 불가)
- API Route 에러 핸들링: 모든 에러를 500으로 반환 (에러 원인 불명확)
- Yahoo Finance rate limit 대응 없음 → 대시보드 접속자 증가 시 실패
- 데이터 캐싱 없음 → 매 요청마다 API 호출 (비용, 대역폭 낭비)
- 모바일 최적화 미완성

**배포 선택지:**
- Vercel (추천): serverless, GitHub 자동 배포, 환경변수 관리, 로깅 제공
- AWS Lambda + API Gateway: 더 많은 제어, 비용 낮음
- self-hosted: VPS/Docker, 비용 낮지만 운영 복잡도 높음

---

### 2.3 데이터 안정성 (High)

**네이버 금융 크롤링 위험:**
```
현재 코드 (data/news.py, data/investor.py):
- 페이지 구조에 직접 의존 (XPath 파싱)
- 인코딩: euc-kr (legacy 유지)
- User-Agent 헤더 필수
- 예외 시 빈 리스트 반환 (silent fail)
```

**개선 방안:**
1. 공식 API 전환 (OpenDART: `.env.example`에 이미 준비됨)
   - 외인/기관: 금감원 공시 → 데이터 신뢰도 높음
   - 뉴스: Naver Search API (v3, 유료) 또는 RSS Feed 활용
2. 캐시 도입 (memory 또는 SQLite)
   - 일일 1회만 fetch → rate limit 압력 완화
   - 오류 시 어제 데이터 폴백

**Yahoo Finance rate limit:**
- 최대 2000 요청/일, 분당 수 십 건 → 동시 다중 사용자 시 실패 가능
- Next.js API Route에 in-memory 캐시 (5분) 추가 필수
- Vercel 배포 시 Edge Cache 활용 가능

---

### 2.4 로깅 및 모니터링 (High)

**현재 상태:**
- Python: stdout/stderr만 (파일 로깅 없음)
- 웹: API 에러만 반환 (무슨 이유인지 불명확)
- 모니터링 구조 없음 → 봇 다운 감지 불가

**필요사항:**
1. **Python 구조화 로깅**
   - 로그 파일: `logs/signalight-{YYYY-MM-DD}.log`
   - 일별 로테이션 + 10MB 크기 제한
   - 각 fetch 함수별 성공/실패 기록

2. **봇 헬스체크**
   - 매 신호 체크 후 "최근 실행: {시간}" 마크 남기기
   - 24시간 이상 실행 없으면 알림 (별도 타이머)

3. **웹 API 로깅**
   - 요청 시간, 종목, 응답 시간, 데이터 소스별 성공/실패
   - Vercel Functions Logs 활용

---

### 2.5 보안 이슈 (Medium)

**API 키 관리:**
- `.env.example` 있음 (좋음)
- `config.py`에서 `load_dotenv()` 호출 (좋음)
- **문제**: Git에 `.env` 실수 커밋 가능성 (`.gitignore` 확인 필수)

**크롤링 법적 이슈:**
- **네이버 금융 뉴스**: Terms of Service 위반 가능성
  - 공식 API 없음 → 회색 지대
  - 대체: RSS Feed, 네이버 검색 API, 언론사 피드
- **외인/기관 데이터**: 공식 sources 선호
  - OpenDART (금감원): 완전 공개, API 제공
  - KRX (한국거래소): 공식 공시

**권장사항:**
1. OpenDART API 활용 (`.env.example`에 `DART_API_KEY` 이미 준비)
2. 뉴스는 RSS Feed 또는 유료 API (Naver Search API v3)
3. 크롤링 필요 시 robots.txt + User-Agent, Rate Limiting 준수

---

### 2.6 Docker화 필요성

**현재 환경:**
- Python: systemd user service (WSL2/Linux 전용)
- 웹: Next.js dev server (로컬)

**Docker 필요성:**
| 관점 | 평가 | 우선순위 |
|------|-----|--------|
| **배포 재현성** | 낮음 (이미 systemd 구성) | P2 |
| **환경 격리** | 중간 (다른 서비스와 공존) | P2 |
| **클라우드 마이그레이션** | 높음 (Lambda, ECS 등) | P1 |
| **팀 협업** | 중간 (로컬 개발 환경 표준화) | P2 |

**Phase 3 도입 권장:**
```yaml
# 구성
- Python 봇: Python 3.11-slim 기반
  - TZ=Asia/Seoul (pykrx 타임존)
  - volumes: [./data/watchlist.json] (영속화)
  - restart: unless-stopped
  - logging: json-file + 일별 로테이션 (10MB)

- Next.js 웹: Node 20-alpine
  - 빌드: `npm run build`
  - 실행: `npm start` (포트 3000)
```

---

## 3. 개선 로드맵

### Phase 2 (지금 ~ 2주)

#### P0 (Critical)
- [ ] **Python 봇 안정성**
  - systemd `signalight.service` 재시작 정책 확인 (`Restart=on-failure`, `RestartSec=60`)
  - 각 fetch 함수에 timeout 추가 (pykrx, requests)
  - 구조화 로깅 추가: `infra/logging_config.py` 작성 + handlers 설정
  - `send_message()` 실패 시 재시도 로직 (exponential backoff)

- [ ] **네이버 금융 크롤링 안정성**
  - in-memory 캐시 도입 (24시간) → 매일 1회만 fetch
  - XPath 파싱 에러 시 graceful degradation (silent fail)
  - OpenDART 시범 도입 (외인/기관 데이터)

#### P1 (High)
- [ ] **웹 대시보드 배포**
  - Vercel 연결: GitHub Actions + 자동 배포
  - API Route 캐싱: in-memory (5분) 또는 Vercel KV
  - API 에러 메시지 구체화 (어느 데이터 소스 실패인지)

- [ ] **모니터링 기초**
  - Python: `logs/` 디렉토리 + 일별 로테이션
  - 텔레그램: 일일 health check 메시지 (09:00 "봇 상태 확인")

#### P2 (Medium)
- [ ] **데이터 캐싱 프레임워크**
  - SQLite (simple) 또는 Redis (scalable)
  - OHLCV, VIX, 외인/기관, 뉴스: 최소 4시간 캐시
  - 캐시 miss 시 real-time fetch

- [ ] **크롤링 법적 정리**
  - Terms of Service 재검토
  - OpenDART + RSS 우선, 뉴스는 공식 API 검토

### Phase 3 (3주 이후)

#### P0
- [ ] **Docker 도입**
  - `Dockerfile` (Python 3.11-slim + pykrx 의존성)
  - `docker-compose.yml` (Python bot + Next.js)
  - systemd 서비스 대체 (또는 병행)

#### P1
- [ ] **종합 모니터링**
  - 텔레그램 헬스체크 → 24h 타임아웃 감지
  - 또는 third-party (Uptime Robot, Better Stack)
  - API 응답 시간, 에러율 추적

- [ ] **자동 재시작 & 기울어 관리**
  - Kubernetes 또는 systemd watchdog
  - Circuit breaker: 연속 3회 실패 시 slack alert

---

## 4. 파일별 개선 제안

### 4.1 `/infra/logging_config.py` (신규)

```python
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def setup_logging():
    """구조화된 로깅 설정"""
    logger = logging.getLogger("signalight")
    logger.setLevel(logging.DEBUG)

    # 파일: 일별 로테이션, 10MB
    handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / f"signalight.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=7,  # 7일 보관
    )

    # 포맷: timestamp | level | message
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

# main.py에서 사용
logger = setup_logging()
logger.info("시그널 체크 시작...")
logger.error("VIX 데이터 조회 실패: {e}")
```

### 4.2 `main.py` 개선사항

**1) Timeout 추가**
```python
from data.fetcher import fetch_stock_data  # timeout 추가

def fetch_stock_data(..., timeout=30):
    """timeout=30초 추가"""
```

**2) 텔레그램 전송 재시도**
```python
def send_message_with_retry(text: str, max_retries=3):
    for attempt in range(max_retries):
        try:
            if send_message(text):
                return True
        except Exception as e:
            logger.warning(f"전송 실패 {attempt+1}/{max_retries}: {e}")
            time.sleep(2 ** attempt)  # exponential backoff
    logger.error("최대 재시도 초과")
    return False
```

**3) 헬스체크 메시지**
```python
# 09:00 추가
schedule.every().monday.at("09:00").do(send_health_check)

def send_health_check():
    """매일 봇 상태 확인 메시지"""
    msg = f"[Signalight 헬스체크]\n시간: {datetime.now()}\n상태: 정상"
    send_message(msg)
```

### 4.3 `config.py` 개선사항

**현재:**
```python
# Google Gemini API (이미 있음)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SENTIMENT_MODEL = "gemini-2.5-flash"
```

**추가할 사항:**
```python
# 캐싱
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL_MINUTES = int(os.getenv("CACHE_TTL_MINUTES", "240"))  # 4시간

# API Timeout
PYKRX_TIMEOUT = int(os.getenv("PYKRX_TIMEOUT", "30"))
REQUESTS_TIMEOUT = int(os.getenv("REQUESTS_TIMEOUT", "10"))

# 로깅
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

### 4.4 `web/app/api/stock/[ticker]/route.ts` 개선사항

**1) 캐싱 추가**
```typescript
// 간단한 in-memory 캐시 (Vercel 함수 내)
const cache = new Map<string, { data: any; time: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5분

if (cache.has(ticker)) {
  const cached = cache.get(ticker)!;
  if (Date.now() - cached.time < CACHE_TTL) {
    return NextResponse.json(cached.data);
  }
}
```

**2) 에러 메시지 구체화**
```typescript
try {
  const [ohlcv, vixData, investorData] = await Promise.all([
    fetchOHLCV(ticker, 120).catch(e => {
      logger.error(`fetchOHLCV failed: ${e.message}`);
      throw new Error(`OHLCV 데이터 조회 실패: ${e.message}`);
    }),
    ...
  ]);
} catch (error) {
  const message = error instanceof Error ? error.message : "Unknown error";
  return NextResponse.json(
    { error: message, source: "api", timestamp: new Date().toISOString() },
    { status: 500 }
  );
}
```

### 4.5 `.env.example` 업데이트

**현재:**
```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
DART_API_KEY=...  # ← 이미 준비됨 (잘함!)
```

**추가:**
```env
# Python 봇
PYKRX_TIMEOUT=30
REQUESTS_TIMEOUT=10
CACHE_ENABLED=true
CACHE_TTL_MINUTES=240
LOG_LEVEL=INFO

# Google Gemini (현재)
GOOGLE_API_KEY=...

# 웹 대시보드 (Vercel)
NEXT_PUBLIC_LOG_LEVEL=info

# 모니터링 (향후)
HEALTH_CHECK_CHAT_ID=...  # 별도 채널 (선택사항)
```

---

## 5. 보안 체크리스트

- [ ] `.gitignore` 확인: `.env`, `.env.*`, `.omc/`, `.claude/` 포함?
- [ ] GitHub Secrets: TELEGRAM_BOT_TOKEN, GOOGLE_API_KEY, DART_API_KEY 설정
- [ ] Vercel Environment Variables: 웹 배포 시 API 키 설정
- [ ] 크롤링 Terms of Service: 네이버 금융 확인, OpenDART 우선 검토
- [ ] Rate Limiting: Yahoo Finance 2000 req/day 준수, User-Agent 설정

---

## 6. 배포 체크리스트 (Phase 3)

### Python 봇
- [ ] systemd 서비스 설정 확인 (`Restart=on-failure`)
- [ ] 로깅 구조 추가 (`infra/logging_config.py`)
- [ ] timeout + 재시도 로직 추가
- [ ] Docker 이미지 빌드 및 테스트
- [ ] 캐싱 도입 (선택: memory 또는 SQLite)

### Next.js 웹
- [ ] Vercel 계정 연결 (root directory: `web/`)
- [ ] 환경변수 설정 (API 키)
- [ ] API Route 캐싱 추가
- [ ] 에러 메시지 구체화
- [ ] 모바일 테스트

### 모니터링
- [ ] 헬스체크 메시지 일일 송신
- [ ] 봇 다운 감지 (24h 타임아웃)
- [ ] API 로깅 확인

---

## 7. 우선순위 요약

| 우선순위 | 항목 | 영향도 | 복잡도 | 시간 |
|---------|------|--------|--------|------|
| **P0** | systemd 재시작 정책 확인 | 높음 | 낮음 | 30분 |
| **P0** | Python 구조화 로깅 | 높음 | 낮음 | 2시간 |
| **P0** | timeout + 재시도 로직 | 높음 | 중간 | 3시간 |
| **P1** | Vercel 배포 | 중간 | 낮음 | 1시간 |
| **P1** | API Route 캐싱 | 중간 | 중간 | 2시간 |
| **P1** | 헬스체크 메시지 | 중간 | 낮음 | 1시간 |
| **P2** | Docker 도입 | 낮음 | 높음 | 4시간 |
| **P2** | 종합 모니터링 | 낮음 | 높음 | 6시간 |

**Phase 2 목표 (이주 내)**: P0 + P1 항목 완료
**Phase 3 목표 (3주 이후)**: Docker + 종합 모니터링

---

## 8. 관련 파일 경로

**현재 상태 파일:**
- `/home/faeqsu10/project/signalight/main.py` — 메인 스케줄러
- `/home/faeqsu10/project/signalight/config.py` — 환경변수 설정
- `/home/faeqsu10/project/signalight/bot/telegram.py` — 텔레그램 전송
- `/home/faeqsu10/project/signalight/data/fetcher.py` — pykrx 호출
- `/home/faeqsu10/project/signalight/data/news.py` — 네이버 뉴스 크롤링
- `/home/faeqsu10/project/signalight/data/investor.py` — 외인/기관 크롤링
- `/home/faeqsu10/project/signalight/signals/sentiment.py` — Gemini 감성 분석
- `/home/faeqsu10/project/signalight/web/app/api/stock/[ticker]/route.ts` — 웹 API
- `/home/faeqsu10/project/signalight/.env.example` — 환경변수 템플릿

**신규 파일:**
- `/home/faeqsu10/project/signalight/infra/logging_config.py` (작성 필요)
- `/home/faeqsu10/project/signalight/Dockerfile` (Phase 3)
- `/home/faeqsu10/project/signalight/docker-compose.yml` (Phase 3)

---

## 부록: 크롤링 법적 조사

### 현재 대상
1. **네이버 금융 뉴스** (`data/news.py`)
   - URL: `https://finance.naver.com/item/news_news.naver?code={ticker}`
   - 방식: XPath 파싱
   - **법적 상태**: 회색 지대 (Terms of Service 명시 확인 필요)

2. **네이버 금융 외인/기관** (`data/investor.py`)
   - URL: `https://finance.naver.com/item/frgn.naver?code={ticker}`
   - 방식: XPath 파싱
   - **법적 상태**: 회색 지대 (공시 기반 데이터이지만 크롤링 가능성 있음)

### 권장 대안

**뉴스:**
- RSS Feed (각 언론사 제공)
- Naver Search API v3 (유료, 합법)
- 종목별 보도자료 (회사 홈페이지)

**외인/기관:**
- **OpenDART** (금감원, 무료, 공식 API)
  - URL: `https://opendart.fss.or.kr/`
  - 공시 데이터 → 완전 합법, 신뢰도 높음
  - `.env.example`에 `DART_API_KEY` 이미 준비됨

- **KRX 공시** (한국거래소)
  - URL: `https://data.krx.co.kr/`
  - 공식 데이터

### 액션 아이템
1. Naver 크롤링 Terms 확인 (1시간)
2. OpenDART API 시범 (2시간)
3. RSS Feed 수집 검토 (1시간)

---

## 결론

Signalight는 **Python 봇은 안정적이나, 데이터 소스 안정성과 웹 배포 미흡**이 주 문제입니다.

**즉시 조치 (이주 내):**
1. systemd 재시작 정책 확인
2. 로깅 + timeout 추가
3. Vercel 배포 + API 캐싱
4. 헬스체크 메시지 추가

**장기 개선 (Phase 3):**
1. Docker 도입으로 배포 자동화
2. OpenDART + 공식 API로 크롤링 법적 위험 제거
3. 종합 모니터링 (24h 감시)

현재 상태에서 **크리티컬 장애는 없으나, 운영 중 작은 장애들이 누적될 가능성이 높습니다**. Phase 2 개선으로 안정성을 크게 높일 수 있습니다.
