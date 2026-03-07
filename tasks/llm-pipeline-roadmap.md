# LLM 기반 퀀트 파이프라인 로드맵

> 2026-03-08 전문가 에이전트 3인 (퀀트 리서처, 전략 아키텍트, 프로덕트 오너) 합의 결과

## 배경

idea.txt / idea.jpg 분석 → "LLM 기반 퀀트 자동매매 시스템 구현 파이프라인" 4단계 구조를
Signalight에 단계적으로 적용하는 로드맵.

## 우선순위 (3인 만장일치)

| 순위 | 기능 | 비용/월 | 난이도 | 효과 | 기간 |
|------|------|---------|--------|------|------|
| 1 | 뉴스/공시 감성 분석 | ~400원 | 낮음 | 상 | 1-2주 |
| 2 | LLM 종합 판단 (상충 시그널 해석) | ~2,000원 | 중 | 상 | 2-3주 |
| 3 | 사후 분석 + 시그널 이력 DB | 0원 | 중 | 중 | 2주 |
| 4 | 모의투자 자동매매 (키움 REST API) | 0원 | 중상 | 상 | 3-4주 |
| 5 | 멀티팩터 스코어링 | 0원 | 중 | 중 | 2주 |
| 6 | 종목 자동 스캐닝 | 0원 | 높 | 중 | 4주 |
| 7 | 포트폴리오 비중 관리 | 0원 | 중 | 낮(현재) | E 이후 |
| 8 | 차트 비전 분석 | ~4,000원 | 높 | 불확실 | 보류 |

## 킬러 피처

"LLM이 설명해주는 매매 시그널" = 수치 근거 + 뉴스 맥락 + LLM 자연어 해석
→ 현재 어떤 개인투자자용 서비스도 제공하지 않는 형태

## Phase 1: 뉴스 감성 분석 (1-2주)

### 파일 변경 계획
- [신규] `data/news.py` — 네이버 금융 뉴스 크롤링
- [신규] `signals/sentiment.py` — Claude Haiku로 감성 분류
- [수정] `bot/formatter.py` — [뉴스 감성] 블록 추가
- [수정] `main.py` — 시그널 체크에 뉴스 분석 통합
- [수정] `config.py` — ANTHROPIC_API_KEY 환경변수

### 기술 결정
- 뉴스 소스: 네이버 금융 종목별 뉴스 (investor.py 크롤링 패턴 재활용)
- LLM 모델: Claude Haiku 4.5 (비용 최소화, 감성 분류에 충분)
- 비용: 하루 ~20원, 월 ~400원
- 실패 격리: 뉴스 수집/분석 실패 시 기존 알림 정상 동작 (try/except)

### 메시지 형태
```
[뉴스 감성] 긍정 (신뢰도 85%)
 • HBM4 양산 본격화, AI 반도체 수요 증가 전망
```

### 수락 기준
- 뉴스 수집 실패 시 블록 생략 (장애 아님)
- Claude API 3초 타임아웃
- 감성과 시그널 방향 불일치 시 경고 표시

## Phase 2: LLM 하이브리드 판단 + DB (3-4주)

### 파일 변경 계획
- [신규] `signals/llm_analyzer.py` — Claude API 종합 판단
- [신규] `storage/db.py` — SQLite (시그널 이력, 매매 기록)
- [신규] `signals/scorer.py` — 멀티팩터 스코어링
- [수정] `bot/formatter.py` — LLM 해석 블록 추가

### 기술 결정
- LLM 호출 조건: 상충 시그널 있을 때 OR confluence >= 2일 때만
- 모델: Claude Sonnet (종합 판단에는 더 높은 품질 필요)
- DB: SQLite (단일 프로세스, 쓰기 빈도 낮음, 배포 단순)
- 할루시네이션 완화: JSON 스키마 강제, temperature 0, 수치 데이터만 입력

### DB 테이블
1. signal_history — 시그널 이력
2. trade_history — 매매 이력 (dry-run 포함)
3. news_sentiment — 뉴스 감성 분석 결과

## Phase 3: 키움 모의투자 자동매매 (4-6주)

### 파일 변경 계획
- [신규] `trading/__init__.py` — Order, TradingConfig dataclass
- [신규] `trading/kiwoom_client.py` — 키움 REST API 래퍼
- [신규] `trading/executor.py` — 주문 실행 + 안전장치
- [신규] `trading/portfolio.py` — 포트폴리오 비중

### 안전장치
- dry-run 기본값 True
- 일일 손실 한도 3%
- 단일 종목 최대 비중 30%
- 텔레그램 확인 후 실행 (인라인 키보드)
- kill switch (/stop 명령어)

### 신뢰 구축 단계
1. 페이퍼 트레이딩 (2-4주)
2. 확인 후 실행 (4-8주)
3. 반자동 (8-12주)
4. 완전 자동 (12주+, 선택적)

## 리서치 근거

| 항목 | 발견 |
|------|------|
| 뉴스 감성 | 한국 시장에서 뉴스 감성이 주가 예측에 유효 (학술 논문) |
| LLM 트레이딩 | 멀티모달 결합 시 최강 성능, 장기 백테스트에서 우위 약화 주의 |
| 차트 비전 | VISTA(2025) 89% 향상 보고, 과적합 위험 경고 |
| 비용 | Claude Haiku 기준 전체 파이프라인 월 5,000원 이하 |
| 할루시네이션 | 구조화 출력 + temperature 0 + 수치 입력으로 완화 |

## 참고 논문/자료
- News media sentiment and asset prices in Korea (2019)
- VISTA: Vision-Language Stock Time-Series Analysis (2025)
- The New Quant: LLMs in Financial Prediction (2025)
- StockBench: Can LLM Agents Trade Stocks Profitably? (2025)
- Can LLM-based Strategies Outperform the Market Long Run? (2025)

## 아키텍처 확장 구조

```
signalight/
├── config.py                    # + ANTHROPIC_API_KEY
├── main.py                      # + 뉴스/LLM 플로우 통합
├── data/
│   ├── fetcher.py               # [기존 유지]
│   ├── investor.py              # [기존 유지]
│   ├── news.py                  # [Phase 1] 뉴스 크롤링
│   └── chart_renderer.py        # [Phase 2] 차트 이미지 (선택)
├── signals/
│   ├── indicators.py            # [기존 유지]
│   ├── strategy.py              # [기존 유지]
│   ├── sentiment.py             # [Phase 1] 뉴스 감성 분석
│   ├── llm_analyzer.py          # [Phase 2] Claude 종합 판단
│   └── scorer.py                # [Phase 2] 멀티팩터 스코어링
├── trading/
│   ├── __init__.py              # [Phase 3] 데이터 모델
│   ├── kiwoom_client.py         # [Phase 3] 키움 API
│   ├── executor.py              # [Phase 3] 주문 실행
│   └── portfolio.py             # [Phase 3] 포트폴리오
├── storage/
│   ├── db.py                    # [Phase 2] SQLite
│   └── signalight.db            # [Phase 2] (.gitignore)
├── backtest/                    # [기존 유지]
├── bot/
│   ├── telegram.py              # [Phase 3] 콜백 핸들러
│   └── formatter.py             # [Phase 1-2] 뉴스/LLM 블록
└── web/                         # [기존 유지]
```
