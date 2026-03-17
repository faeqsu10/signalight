# Lessons Learned

## Python 호환성
- Python 3.8에서는 `list[str]`, `dict[str, int]` 등 빌트인 제네릭 문법 사용 불가
- `from typing import List, Dict` 사용 필수

## lightweight-charts v5 API 변경
- v4: `chart.addCandlestickSeries({...})`, `chart.addLineSeries({...})`
- v5: `chart.addSeries(CandlestickSeries, {...})`, `chart.addSeries(LineSeries, {...})`
- import: `import { CandlestickSeries, LineSeries, HistogramSeries } from "lightweight-charts"`
- v5에서는 `IChartApi`에 `addCandlestickSeries` 메서드가 존재하지 않음

## Yahoo Finance API
- 한국 주식 티커 형식: `{종목코드}.KS` (예: `005930.KS`)
- v8 chart API: `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}`
- User-Agent 헤더 필수, 없으면 403 에러
- 응답 구조: `json.chart.result[0].timestamp` + `json.chart.result[0].indicators.quote[0]`

## 백테스트 엔진 설계
- 시그널 발생일 **다음 거래일 시가**에 체결해야 미래 편향(look-ahead bias) 방지
- 수수료(0.015%) + 슬리피지(0.1%)를 반영해야 현실적인 수익률 산출
- 같은 날 여러 시그널이 있으면 strength가 높은 것 하나만 선택
- 거래 10회 미만이면 통계적 신뢰도 경고 필요
- MDD(최대낙폭) 계산: peak 대비 하락률의 최대값
- 미체결 포지션은 마지막 날 종가로 강제 청산하여 결과에 포함

## 에이전트 팀 구성
- `.claude/agents/` 디렉토리에 YAML frontmatter가 있는 `.md` 파일로 에이전트 정의
- 각 에이전트 폴더에 `MEMORY.md` 필요 (에이전트별 학습 기록)
- Claude Code는 세션 시작 시 에이전트를 스캔 → 세션 중 추가한 에이전트는 다음 세션부터 인식
- 비엔지니어 역할(UX, PM, PO, Quant Researcher)도 에이전트로 정의하면 전문 관점 활용 가능

## Google Gemini REST API (감성 분석)
- REST endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- API 키는 query parameter로 전달: `?key={GOOGLE_API_KEY}`
- 응답 구조: `result["candidates"][0]["content"]["parts"][0]["text"]`
- Gemini는 JSON을 마크다운 코드블록(```json)으로 감싸서 반환할 수 있으므로 ``` 제거 필요
- `maxOutputTokens`가 너무 작으면 JSON이 잘림 — Gemini 2.5 Flash는 thinking 토큰이 포함되므로 2048 이상 권장
- API 키 없음/오류 시 예외를 전파하지 말고 `None` 반환 — 감성 분석은 선택적 기능

## OpenDART API 통합
- OpenDART는 공시(실적, 배당, 유증), 재무제표, 대주주 데이터 제공
- **외인/기관 일별 순매수 데이터는 미제공** — 네이버 금융 크롤링을 대체할 수 없음
- stock_code(거래소 티커)와 corp_code(DART 고유 ID)는 다름 — 매핑 테이블 필요
- API 키 없으면 graceful하게 빈 배열 반환 (에러가 아님)
- 응답 status "000"이 정상, "013"은 데이터 없음
- 일일 한도 10,000건 — 캐싱 필수 (5분+ TTL)

## API 부분 실패 패턴 (Partial Failure)
- 여러 데이터 소스를 동시 호출할 때, 하나 실패해도 나머지 데이터는 반환해야 함
- `Promise.all`에서 개별 `.catch()`로 실패를 격리하고 `warnings` 배열에 기록
- 프론트엔드에서 `data.warnings`가 있으면 노란색 배너로 표시
- OHLCV(필수)만 실패 시 전체 에러, VIX/투자자(선택적)는 부분 실패 허용

## 네이버 금융 크롤링 패턴
- URL: `https://finance.naver.com/item/news_news.nhn?code={ticker}`
- 인코딩: euc-kr (requests에서 `response.encoding = "euc-kr"` 설정 필요)
- 파싱: lxml + XPath, 뉴스 제목은 `<a>` 태그 text로 추출
- data/investor.py와 data/news.py가 동일 패턴 사용

## 감성 분석 통합 설계
- 감성 분석은 선택적 부가 기능 — 실패해도 기존 시그널 알림에 영향 없어야 함
- `_collect_stock_data()` 내에서 try/except으로 완전 격리
- `news_sentiment` 키가 None이면 포맷터에서 블록 생략
- 시그널 방향과 뉴스 감성 불일치 시 ⚠️ 경고 표시 (매수+부정, 매도+긍정)

## 로깅 사각지대
- `print()` 사용은 로그 파일에 남지 않음 — 반드시 `logger.warning()/error()` 사용
- 외부 호출(send_message 등)의 반환값을 확인하지 않으면 실패를 알 수 없음
- 모듈별 child logger 사용: `logging.getLogger("signalight.telegram")`

## 라이트/다크 모드 대응
- 다크모드 전용으로 만든 `bg-zinc-*`, `text-zinc-*`는 라이트모드에서 깨짐
- 모든 색상에 `dark:` prefix 추가: `bg-white dark:bg-zinc-800/50`
- CSS 변수(`--card`, `--muted` 등)를 적극 활용하면 유지보수 쉬움
- 차트(lightweight-charts)는 `isDark` 분기로 색상 전환: `isDark ? "#0f0f0f" : "#ffffff"`
- 시맨틱 색상(매수=빨강, 매도=파랑)은 양쪽 모드에서 동일하게 유지

## Vercel 배포
- 웹 앱에 `process.env` 참조 없으면 환경변수 설정 불필요 → 즉시 배포 가능
- 네이버 금융 크롤링은 Vercel 해외 서버에서 IP 차단됨 → `.catch(() => null)` 패턴으로 graceful degradation
- 서버리스 in-memory 캐시는 cold start마다 초기화 → 캐시 효과 제한적
- `vercel --yes --prod` 명령으로 CLI 배포, Root Directory 설정 필요 (모노레포)

## Python ↔ TypeScript 지표 포팅
- Python pandas `rolling().mean()` → TS에서 직접 for 루프로 구현
- Python pandas `ewm(span=n).mean()` → TS에서 `alpha = 2/(span+1)` EMA 수동 구현
- RSI 계산 시 `delta = closes.diff()` → TS에서 `closes[i] - closes[i-1]`
- MACD는 EMA 기반이라 데이터 초반부터 값이 존재 (rolling MA와 다름)

## 자율매매 config 분리
- `signals/strategy.py`가 `config.py`에서 직접 import하면 자율매매와 일반 봇이 설정값을 공유하게 됨
- 해결: strategy.py에 로컬 기본값 정의 + `strategy_settings` dict로 런타임 오버라이드
- 자율매매는 `autonomous/config.py`의 `AutonomousConfig`에서 모든 파라미터 통합 관리
- 공유 모듈은 기본값만 갖고, 호출자가 필요시 오버라이드하는 패턴이 가장 깔끔

## 웹-파이썬 데이터 연동
- Next.js(Vercel)에서 Python SQLite DB 직접 접근 불가 → JSON export 패턴 사용
- `scripts/export_auto_data.py`로 DB → JSON, pipeline 사이클 후 자동 실행
- `web/public/data/`에 저장하면 API Route에서 fs.readFileSync로 읽기 가능
- Vercel 배포 시에는 이 파일이 없으므로 graceful fallback 필수

## 글로벌 매크로 데이터 통합
- Yahoo Finance v8 chart API로 매크로 지표 수집 (yfinance 패키지 미사용, raw urllib)
- 티커에 특수문자(`^`, `=`) 포함 시 `urllib.parse.quote(ticker, safe="")` 필수
- 매크로 시그널 합류 점수는 최대 1.5점 cap — 기술적 시그널(7점+)을 압도 방지
- 섹터 연관성 기반 점수: 유가 급등 → 에너지 수혜(+), 항공 피해(-)
- macro_data=None이면 기존 동작 그대로 유지 (하위호환 필수)
- `fetch_all_macro_prices()`는 내부 4시간 캐시, analyzer에서 사이클 단위 캐시 추가
- formatter가 기대하는 데이터 형식과 fetcher 반환 형식 일치시킬 것 (dict of dicts)

## Alpaca Paper Trading API
- Base URL: paper-api.alpaca.markets (모의투자), api.alpaca.markets (실전)
- 인증: APCA-API-KEY-ID + APCA-API-SECRET-KEY 헤더 (OAuth 불필요, 매우 간단)
- 시장 시간 확인: GET /v2/clock → {"is_open": true/false} (가장 간단한 방법)
- Paper Trading은 $100,000 가상 자금 제공
- 장외 시간 주문: status="pending_new" → 장 열리면 자동 체결
- Data API 엔드포인트가 Trading API와 다름: data.alpaca.markets vs paper-api.alpaca.markets

## 미국 주식 데이터 통합 패턴
- Yahoo Finance로 OHLCV 가져온 후 한글 컬럼명(종가/고가/저가/시가/거래량)으로 변환
- 이렇게 하면 analyze_detailed() 등 기존 전략 코드를 수정 없이 재활용 가능
- investor_df=None으로 전달 — 미국 주식은 외인/기관 데이터 없음 (graceful degradation)

## 저장소 운영 규칙 우선순위
- 사용자/프로젝트가 별도 orchestration 규칙을 주면 `CLAUDE.md`와 로컬 기억 저장소 둘 다 동기화해야 다음 세션에 유지된다.
- 비단순 작업은 plan-first, verification-first, role separation 원칙으로 취급하는 편이 충돌이 적다.
- `tasks/worklog-template.md`가 없어도 `tasks/worklogs/YYYY-MM-DD-{주제}.md` 형식의 로그는 남겨야 한다.

## 자율매매 대시보드 실시간화
- Vercel 같은 정적/서버리스 배포에서는 로컬 SQLite에 직접 붙을 수 없으므로 `DB 우선 + JSON fallback` 구조가 안전하다.
- `better-sqlite3`를 쓰는 API route는 `runtime = "nodejs"`와 `dynamic = "force-dynamic"`를 명시하는 편이 예측 가능하다.
- US 거래 로그는 cents, 가상 포지션 가격은 dollars로 저장돼 있어 대시보드 변환 규칙을 분리해야 한다.
