# Signalight TODO

## Python 백엔드 (텔레그램 봇)
- [x] 프로젝트 구조 생성
- [x] 기본 시그널 로직 (MA 크로스, RSI, MACD)
- [x] GitHub 레포 연결 및 초기 커밋
- [x] 장중 30분 간격 시그널 체크 + 키움/DART API 환경 설정
- [x] 텔레그램 봇 설정 (BotFather → 토큰 발급 → .env 설정)
- [x] 실서비스 테스트 (텔레그램 알림 수신 확인)

## Next.js 웹 대시보드
- [x] Next.js 14 프로젝트 초기화 (web/)
- [x] 데이터 레이어 구현 (yahoo-finance.ts, indicators.ts, strategy.ts)
- [x] API Route 구현 (api/stock/[ticker]/route.ts)
- [x] 차트 컴포넌트 구현 (CandleChart, RSIChart, MACDChart)
- [x] 대시보드 페이지 조립 (page.tsx + PriceInfo + SignalPanel)
- [x] 빌드 성공 확인 + API 실데이터 테스트 (삼성전자 005930)
- [ ] Vercel 배포 (Root Directory: web)
- [ ] 모바일/PC 브라우저 접속 테스트

## 백테스팅 엔진 (Phase 1 - 완료)
- [x] fetcher.py 기간 파라미터 확장 (start_date/end_date)
- [x] Signal/Trade/BacktestResult 데이터 모델 정의 (backtest/__init__.py)
- [x] generate_signals() 전체 기간 시그널 생성 (signals/strategy.py)
- [x] BacktestEngine 핵심 엔진 구현 (backtest/engine.py)
  - 다음 거래일 시가 체결, 수수료 0.015% + 슬리피지 0.1%
  - MDD/승률/equity curve 계산, 미체결 포지션 강제 청산
- [x] 백테스트 리포트 생성 (backtest/report.py)
  - 텍스트 리포트 + 텔레그램 메시지 포맷
- [x] CLI 러너 구현 (backtest/runner.py)
  - `python3 -m backtest.runner [종목코드] [종목명] [--days N] [--capital N]`

## Phase 2 - 전략 고도화 (진행 중) + 인프라 안정화

### 전략 고도화
- [x] VIX(공포지수) + 외인/기관 매매동향 지표 추가 (웹 대시보드)
- [x] 거래량 비율 지표 추가 (Python + TS 동기화)
- [x] 시그널 구조화 (문자열 → 구조화된 dict, 합류 점수)
- [x] 텔레그램 포맷터 분리 (bot/formatter.py, 상세 근거 메시지)
- [x] 일일 종합 브리핑 (평일 16:00, 전 종목 요약)
- [x] 주간 리포트 (금요일 16:30, 주간 등락률 + 시그널 요약)
- [x] systemd 서비스 등록 (자동 시작 + 자동 재시작)
- [ ] 신규 지표 추가 (볼린저밴드, OBV 등) + TS 동기화
- [ ] 복합 전략 프레임워크 (멀티 시그널 조합)
- [ ] 파라미터 최적화 (MA 조합 탐색)
- [ ] 백테스트 결과 웹 대시보드 표시

### 인프라 안정화 (Phase 2 신규)
- [ ] systemd 재시작 정책 확인 및 설정
- [ ] 구조화 로깅 구현 (`infra/logging_config.py`)
- [ ] Python 봇 timeout + 재시도 로직
- [ ] 헬스체크 메시지 추가 (매일 09:00)
- [ ] Vercel 배포 및 API 캐싱
- [ ] 네이버 금융 크롤링 캐시 + OpenDART 시범
- 참고: `DEVOPS_ANALYSIS.md`

## LLM 파이프라인 (Phase 1 - 완료)
- [x] anthropic 패키지 설치
- [x] signals/sentiment.py 구현 (Claude Haiku 감성 분석)
- [x] config.py에 ANTHROPIC_API_KEY 추가
- [x] data/news.py 구현 (네이버 금융 뉴스 크롤러)
- [x] bot/formatter.py에 [뉴스 감성] 블록 추가 (감성+신뢰도+요약+불일치 경고)
- [x] main.py에 뉴스+감성 통합 (실패 격리, 기존 기능 영향 없음)
- [x] systemd 서비스 재시작 확인

## Phase 3 - 운영 안정화 (예정)
- [ ] 텔레그램 인터랙티브 (명령어로 종목 추가/백테스트 실행)
- [ ] Docker 배포
- [ ] 모바일 최적화

## Backlog
- [ ] 미국 주식 지원 추가
- [ ] 감시 종목 동적 관리 (텔레그램 명령어로 추가/삭제)
- 개선사항은 `tasks/improvements.md` 참고
