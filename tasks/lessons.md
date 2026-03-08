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
