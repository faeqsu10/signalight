# [프로젝트명] - Claude Code 프로젝트 가이드

> 이 파일은 Signalight 프로젝트에서 8개 Phase, 101개 항목 개발을 통해 축적된 교훈과 패턴을 일반화한 템플릿입니다.
> 새 프로젝트에 복사 후 `[placeholder]` 부분을 채워 사용하세요.

## 프로젝트 개요
[1-2문장으로 프로젝트가 무엇을 하는지 설명]
- **백엔드**: [언어/프레임워크] 기반, [핵심 기능]
- **프론트엔드**: [프레임워크] 기반, [핵심 기능]
- **데이터**: [데이터 소스], [저장소]

## 아키텍처

```
project/
├── config.py              # 설정 (환경변수, 파라미터)
├── main.py                # 진입점
├── data/                  # 외부 데이터 수집 레이어
├── domain/                # 비즈니스 로직 레이어
├── storage/               # 영속성 레이어 (DB)
├── infra/                 # 인프라 (로깅, 모니터링)
├── api/                   # 외부 인터페이스 (봇, API)
│
├── web/                   # 프론트엔드 (해당 시)
│   ├── app/               # 라우트/페이지
│   ├── components/        # UI 컴포넌트
│   └── lib/               # 유틸리티/비즈니스 로직
│
├── infra/                 # 공통 인프라 설정
└── tasks/                 # 작업 추적 문서
    ├── todo.md            # 현재 작업 체크리스트
    ├── devlog.md          # 전체 개발 항목 추적
    ├── lessons.md         # 교훈 기록
    └── improvements.md    # 개선사항 추적 (P0~P3)
```

> 트리 주석은 파일의 **역할**을 적는다 (기술적 설명이 아닌 비즈니스 역할).
> 구조 변경 시 반드시 이 섹션을 업데이트한다.

## 기술 스택

### 백엔드
- [언어] [버전]+ (호환성 제약 명시)
- [라이브러리] (버전 + 핵심 API 주의사항)

### 프론트엔드
- [프레임워크] (버전 + 라우터 방식)
- [차트/UI 라이브러리] (버전 — 이전 버전과의 API 차이 명시)
- [상태관리/데이터 패칭] (갱신 주기)

> **규칙**: 라이브러리 **버전**을 명시한다. 이전 버전과 API가 다른 부분을 구체적으로 명시한다.

## 핵심 규칙 (Gotchas)

> 실제로 **실수가 발생했던 항목**만 기록한다. 이론적 주의사항 금지.
> 각 규칙에 **잘못하면 어떤 에러가 나는지** 한마디로 첨부.

- [외부 라이브러리 고유 규칙] — 없으면 [에러 내용]
- [호환성 규칙] — 어기면 [에러 내용]
- [프레임워크 버전 규칙] — v(n-1)과 다른 점: [차이]
- [도메인 규칙] — 예: 색상 관례, 단위 표기, 인코딩

## 커밋 보안 규칙

**커밋 금지 파일** (`.gitignore`에 등록됨):
- `.env`, `.env.*` — API 토큰, 시크릿
- `.claude/` — Claude Code 세션/에이전트 데이터
- `.omc/state/`, `.omc/project-memory.json` — 플러그인 상태 파일
- `*.png`, `*.jpg` — 스크린샷/이미지 파일
- `node_modules/`, `__pycache__/`, `.next/`, `dist/` — 빌드 산출물
- `*.db`, `*.sqlite` — 로컬 데이터베이스

**커밋 전 체크**: `git status`로 민감 파일 미포함 확인 필수

## 자동 수행 규칙 (유저가 말하지 않아도 항상)

1. **작업 완료 시 커밋** — 의미 있는 단위로 커밋, 보안 파일 제외 확인
2. **문서 업데이트** — 구조/기능 변경 시 `tasks/todo.md`, `lessons.md`, `improvements.md`, `devlog.md` 갱신
3. **CLAUDE.md 동기화** — 프로젝트 구조 변경 시 아키텍처 섹션 업데이트
4. **다중 언어 동기화** — 공유 로직 변경 시 양쪽 반영 (해당되는 경우)
5. **테스트 검증** — 코드 작성 후 import/실행 테스트로 동작 확인
6. **교훈 기록** — 실수나 새로운 발견은 `tasks/lessons.md`에 기록

## 파일 간 매핑 (다중 언어 동기화)

> 같은 로직이 여러 언어에 존재할 때 한쪽만 수정하면 불일치가 발생한다.

| 소스 (Python/Go/...) | 대상 (TypeScript/...) | 설명 |
|----------------------|----------------------|------|
| `domain/logic.py` | `web/lib/logic.ts` | 핵심 계산 로직 |
| `config.py` | `web/lib/constants.ts` | 설정값, 파라미터 |

**포팅 주의사항**:
- `pandas.rolling().mean()` → 직접 for 루프로 구현
- `pandas.ewm(span=n).mean()` → `alpha = 2/(span+1)` EMA 수동 구현
- `series.diff()` → `arr[i] - arr[i-1]`
- 인덱스 기반 접근 시 off-by-one 에러 주의

---

## Workflow Orchestration

### 1. Plan First
- 3단계 이상이거나 구조적 결정이 필요한 작업은 plan mode 진입
- 문제가 생기면 즉시 멈추고 재계획 — 밀어붙이지 않는다
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

### 문서 체계
- `tasks/todo.md` — 현재 작업 체크리스트 (완료되면 체크)
- `tasks/devlog.md` — 전체 개발 항목 추적 (Phase별 테이블, 통계)
- `tasks/lessons.md` — 개발 중 배운 교훈 기록
- `tasks/improvements.md` — 개선사항 추적 (P0/P1/P2/P3 우선순위)

### 프로세스
1. `tasks/todo.md`에 체크리스트로 계획 작성
2. 구현 전 계획 확인
3. 진행하면서 완료 항목 체크
4. 각 단계마다 변경사항 요약
5. 결과를 `tasks/devlog.md`에 기록
6. 수정 받으면 `tasks/lessons.md` 업데이트
7. 개선 아이디어는 `tasks/improvements.md`에 기록

### 개선사항 우선순위 체계
> P0(긴급) > P1(높음) > P2(보통) > P3(낮음)

## Core Principles

- **단순함 우선**: 변경은 최대한 간결하게. 영향 범위 최소화.
- **근본 원인 해결**: 임시 수정(워크어라운드) 금지. 시니어 개발자 기준.
- **최소 영향**: 필요한 부분만 수정. 버그 유입 방지.
- **실패 격리**: 부가 기능 실패가 핵심 기능에 영향을 주지 않는다.
- **Graceful degradation**: 외부 의존성 실패 시 기능 저하는 허용, 전체 중단은 불허.
- **양쪽 동기화**: 공유 로직 변경 시 반드시 모든 구현체에 반영.

---

## 에러 핸들링 패턴

### 계층별 try/except 격리
- **핵심 기능**: 예외 전파 (빠르게 실패)
- **부가 기능**: try/except으로 완전 격리, None 반환
- **데이터 저장**: 별도 try/except, 실패해도 메인 흐름 유지

```python
# 부가 기능 실패 격리 패턴
try:
    optional_result = call_optional_service()
    data["optional_field"] = optional_result
except Exception as e:
    logger.warning("부가 기능 실패: %s", e)
    data["optional_field"] = None

# API 키 없음 조기 반환 패턴
if not API_KEY:
    logger.warning("API 키 미설정. 기능 건너뜀.")
    return None
```

### 규칙
- 부가 기능은 실패해도 핵심 기능에 영향 없어야 함
- 데이터 필드가 None이면 출력/포맷터에서 해당 블록을 생략
- API 키 미설정은 경고 로그 후 None 반환 (예외 전파 금지)

## API 통합 패턴

### 재시도 (Retry with Exponential Backoff)

```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            break
        logger.warning("실패 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES, resp.status_code)
    except requests.RequestException as e:
        logger.warning("요청 오류 (시도 %d/%d): %s", attempt + 1, MAX_RETRIES, e)
    if attempt < MAX_RETRIES - 1:
        time.sleep(2 ** attempt)  # 1s, 2s
```

### Rate Limit 대응 (TypeScript)

```typescript
if (res.status === 429) {
    await new Promise(resolve => setTimeout(resolve, 1000));
    return fetch(url, options);  // 1회 재시도
}
```

### 필수 규칙
- 크롤링: **User-Agent 헤더 필수** (없으면 403)
- 인코딩: 사이트별 인코딩 확인 (euc-kr 등)
- 외부 API 호출: **반드시 timeout 파라미터 설정** (기본 10초)
- LLM API: 더 긴 timeout 허용 (30초)

### 메시지 크기 제한 대응
- 플랫폼별 최대 길이 확인 (텔레그램: 4096자)
- 긴 메시지는 줄 단위로 분할 전송
- 한 줄이 max_length 초과 시 강제 분할

## 로깅 패턴

### 구조화 로깅 설정

```python
import logging
import logging.handlers

LOG_DIR = "logs/"
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

def setup_logging(level=logging.INFO):
    logger = logging.getLogger("project_name")
    logger.setLevel(level)
    if logger.handlers:
        return logger  # 중복 등록 방지

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 파일 핸들러 (RotatingFileHandler)
    file_handler = logging.handlers.RotatingFileHandler(
        f"{LOG_DIR}/app.log", maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
```

### 규칙
- 모듈별 child logger: `logging.getLogger("project.module")`
- **print() 금지** — 반드시 logger 사용 (파일 로그에 남지 않음)
- 외부 호출 결과(성공/실패)의 **반환값을 확인**하고 로깅
- 중복 핸들러 방지: `if logger.handlers: return`

## 캐싱 패턴

### Python — dict 기반 in-memory 캐시

```python
_cache: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL = 4 * 3600  # 4시간

def get_data(key: str):
    if key in _cache:
        cached_time, cached_data = _cache[key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_data
    result = fetch_from_external(key)
    _cache[key] = (time.time(), result)
    return result
```

### TypeScript — Map 기반 in-memory 캐시

```typescript
const cache = new Map<string, { data: unknown; expires: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5분

export function getCached<T>(key: string): T | null {
    const entry = cache.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expires) {
        cache.delete(key);
        return null;
    }
    return entry.data as T;
}

export function setCache(key: string, data: unknown): void {
    cache.set(key, { data, expires: Date.now() + CACHE_TTL });
}
```

### TTL 기준
- 자주 변하는 데이터 (주가, 실시간): **5분**
- 느리게 변하는 데이터 (뉴스, 크롤링): **4시간**
- 설정 데이터: **세션 동안 유지**

## 데이터베이스 패턴 (SQLite)

### 연결 관리
- WAL 모드 활성화: `PRAGMA journal_mode=WAL` (동시 읽기 성능)
- `row_factory = sqlite3.Row` (dict-like 접근)
- 함수별 conn open/close (장기 커넥션 유지 금지)

### 테이블 설계
- `CREATE TABLE IF NOT EXISTS` — 멱등 초기화
- `CREATE INDEX IF NOT EXISTS` — 자주 조회하는 컬럼에 인덱스
- `created_at TEXT DEFAULT (datetime('now', 'localtime'))` — 자동 타임스탬프
- JSON 필드: `TEXT` 타입 + `json.dumps(data, ensure_ascii=False)`

### 데이터 관리
- 시드 데이터: `INSERT OR IGNORE` 패턴으로 중복 방지
- soft delete: `active INTEGER DEFAULT 1` 컬럼으로 논리 삭제
- 삭제 = `UPDATE SET active = 0`, 복원 = `UPDATE SET active = 1`

## 프론트엔드 패턴 (Next.js)

### 데이터 페칭
- SWR로 자동 갱신 (`refreshInterval: 60000`)
- API Route에서 서버사이드 데이터 조합 + 캐시
- 에러 시 빈 배열 반환 (UI 깨짐 방지)

### 반응형/모바일
- 터치 타겟 최소 **44px** (모바일 UX)
- 차트 높이 반응형 조정
- Tooltip: hover + onClick 토글 (모바일 터치 지원)

### localStorage 활용
- 즐겨찾기, 사용자 입력값 영속화
- 입력 디바운스 (**300ms**) — 매 키 입력마다 API 호출하지 않음

```typescript
useEffect(() => {
    const timer = setTimeout(() => {
        fetch(`/api/resource?param=${value}`).then(/* ... */);
    }, 300);
    return () => clearTimeout(timer);
}, [value]);
```

### API Route 패턴
- 서버사이드에서 외부 API 호출 (CORS 우회)
- in-memory 캐시로 같은 요청 재사용
- 에러 시 구체적 HTTP 상태 코드 반환
- `Promise.all()`로 독립 데이터 소스 병렬 fetch

## LLM API 통합 패턴

### 호출 조건 게이팅
- 모든 요청에 LLM을 호출하지 않는다
- 조건 함수로 필요한 경우만 호출 (예: `should_call_llm()`)
- 비용 추정 및 모니터링

### 프롬프트 설계
- 역할 정의 + 출력 형식 명시 + 입력 데이터 제공
- "반드시 JSON 형식으로만 응답하세요" 명시
- 필수 필드 목록을 프롬프트에 포함

### 응답 처리

```python
# 마크다운 코드블록 제거
text = raw_text.strip()
if text.startswith("```"):
    text = text.split("\n", 1)[1]  # 첫 줄 제거
if text.endswith("```"):
    text = text[:-3]

# JSON 안전 추출
start = text.find("{")
end = text.rfind("}") + 1
if start >= 0 and end > start:
    data = json.loads(text[start:end])

# 필수 필드 검증 + 값 클램핑
score = max(-1, min(1, data.get("score", 0)))
confidence = max(0, min(1, data.get("confidence", 0.5)))
```

### 선택적 기능 원칙
- LLM 기반 기능은 항상 **선택적** — 없어도 핵심 기능이 동작해야 함
- 실패 시 None 반환 (예외 전파 금지)
- API 키 미설정 = 경고 로그 + None
- 포맷터에서 None 체크 후 블록 생략

## 배포/인프라 체크리스트

### 프로세스 관리
- [ ] systemd (또는 PM2, supervisor) 서비스 등록
- [ ] `Restart=always`, `RestartSec=10` (자동 재시작)
- [ ] 로그 출력 경로 설정

### 헬스체크
- [ ] 주기적 헬스체크 메시지 (매일 09:00 등)
- [ ] 프로세스 다운 감지 + 알림

### Docker
- [ ] Multi-stage build (빌드 이미지와 런타임 이미지 분리)
- [ ] `.dockerignore` 설정 (`.env`, `node_modules`, `__pycache__`)
- [ ] `docker-compose.yml`로 서비스 조합

### 환경변수
- [ ] 모든 시크릿은 환경변수로 관리
- [ ] `.env.example` 파일로 필요한 변수 목록 문서화
- [ ] 환경변수 미설정 시 명확한 에러 메시지

### Vercel (프론트엔드)
- [ ] Root Directory 설정 (모노레포 시)
- [ ] 환경변수 설정 (빌드/런타임)

## 테스트 전략

### 최소 검증 (항상 수행)
- 코드 작성 후 **import 테스트** (모듈 로드 확인)
- 주요 함수 실행 테스트 (실제 데이터로 1회 호출)
- 빌드 성공 확인 (Next.js: `npm run build`)

### dry-run 모드
- 실제 외부 호출 없이 시뮬레이션 (`dry_run=True` 기본)
- 안전장치: 일일 한도, 항목별 비중 한도

### 시뮬레이션/백테스트
- 미래 편향(look-ahead bias) 방지
- 비용(수수료, 슬리피지) 반영
- 거래 N회 미만 시 통계적 신뢰도 경고
- 미완료 작업은 마지막 시점 기준으로 강제 종료

## 스케줄링 패턴

### 구조

```python
# 시작 시 1회 즉시 실행
job_function()

# 스케줄 등록
schedule.every(30).minutes.do(job_function)
schedule.every().day.at("16:00").do(daily_job)
schedule.every().friday.at("16:30").do(weekly_job)
schedule.every().day.at("09:00").do(healthcheck)

# 등록된 스케줄 로그 출력 (디버깅 용이)
for job in schedule.get_jobs():
    logger.info("  %s", job)

# 스케줄 루프
while True:
    schedule.run_pending()
    time.sleep(60)
```

### 규칙
- 공통 데이터는 **1회 조회 후 전달** (중복 호출 방지)
- 캐시 TTL로 같은 데이터 재요청 방지
- 시작 시 1회 즉시 실행 → 이후 스케줄 등록

---

## 빠른 시작 체크리스트

새 프로젝트 시작 시:

1. [ ] 이 파일을 `CLAUDE.md`로 복사
2. [ ] 프로젝트 개요, 아키텍처, 기술 스택 섹션 채우기
3. [ ] `tasks/` 폴더 생성 (`todo.md`, `devlog.md`, `lessons.md`, `improvements.md`)
4. [ ] `.gitignore`에 보안 파일 패턴 추가
5. [ ] `infra/logging_config.py` 복사 (로깅)
6. [ ] `.env.example` 작성
7. [ ] 핵심 규칙 (Gotchas) 섹션에 첫 번째 교훈 기록
8. [ ] 해당 안 되는 섹션 삭제 (프론트엔드 없으면 삭제 등)
