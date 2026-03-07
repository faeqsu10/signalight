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

## Python ↔ TypeScript 지표 포팅
- Python pandas `rolling().mean()` → TS에서 직접 for 루프로 구현
- Python pandas `ewm(span=n).mean()` → TS에서 `alpha = 2/(span+1)` EMA 수동 구현
- RSI 계산 시 `delta = closes.diff()` → TS에서 `closes[i] - closes[i-1]`
- MACD는 EMA 기반이라 데이터 초반부터 값이 존재 (rolling MA와 다름)
