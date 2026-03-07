# 개선사항 추적

> 우선순위: P0(긴급) > P1(높음) > P2(보통) > P3(낮음)

## P0 - LLM 파이프라인 (진행 중)

> 상세 로드맵: `tasks/llm-pipeline-roadmap.md`

### Phase 1: 뉴스 감성 분석 (진행 중)
- [x] `signals/sentiment.py` 구현 — Claude Haiku `claude-haiku-4-5-20251001` 호출
- [x] `config.py`에 `ANTHROPIC_API_KEY` 추가
- [ ] 네이버 금융 뉴스 크롤러 구현 (fetcher 확장)
- [ ] 텔레그램 알림에 [뉴스 감성] 블록 추가
- 비용: 월 ~400원 | 기간: 1-2주

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

### 볼린저 밴드 지표 추가
- 현재: MA, RSI, MACD 3개 지표만 지원
- 개선: 볼린저 밴드 (20일 MA ± 2σ) 추가
- Python indicators.py + TS indicators.ts 양쪽 구현 필요

### 시그널 히스토리
- 현재: 최신 시그널만 표시
- 개선: 최근 30일 시그널 이력을 타임라인으로 표시
- 차트에 시그널 발생 시점 마커 추가

## P2 - UX 개선

### 종목 즐겨찾기
- localStorage로 사용자별 관심 종목 저장
- 드롭다운에 즐겨찾기 종목 우선 표시

### 차트 기간 선택
- 현재: 120일 고정
- 개선: 1개월 / 3개월 / 6개월 / 1년 선택 버튼

### 로딩/에러 UX
- 현재: 텍스트만 표시 ("데이터 로딩 중...")
- 개선: 스켈레톤 UI + 에러 시 재시도 버튼

### 모바일 최적화
- 차트 높이 반응형 조정 (모바일에서 400px는 과도)
- 터치 제스처 지원 확인
- RSI/MACD 차트 모바일에서 세로 배치 확인

## P2 - 기술 품질

### RSI 계산 방식 개선
- 현재: 단순 rolling mean 방식 (SMA 기반 RSI)
- 개선: Wilder's smoothing (EMA 기반) 방식으로 변경
- 대부분의 트레이딩 플랫폼이 Wilder's 방식 사용
- Python과 TS 양쪽 동시 변경 필요

### API 에러 핸들링 강화
- Yahoo Finance API 요청 제한(rate limit) 대응
- 장 마감/공휴일 시 빈 데이터 처리
- API 실패 시 캐시된 데이터 표시

### 데이터 캐싱
- 현재: 매 요청마다 Yahoo Finance API 호출
- 개선: Next.js API Route에서 in-memory 캐시 (5분)
- Vercel 배포 시 Edge Cache 활용 가능

## P3 - 향후 확장

### 미국 주식 지원
- Yahoo Finance 티커 형식 그대로 사용 가능 (AAPL, TSLA 등)
- constants.ts에 US_WATCH_LIST 추가
- 통화 표시 ($) 분기 처리
- 시간대 처리 (KST vs EST)

### 알림 연동
- 웹 대시보드에서 시그널 발생 시 브라우저 알림
- 또는 텔레그램 봇과 연동하여 웹에서 알림 설정

### 다크/라이트 모드 토글
- 현재: 다크모드 고정
- 개선: 시스템 설정 연동 + 수동 토글 버튼

### 멀티 종목 비교 뷰
- 2~3개 종목을 나란히 비교하는 레이아웃
- 시그널 요약 테이블
