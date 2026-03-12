export const SHORT_MA = 10;
export const LONG_MA = 50;
export const RSI_PERIOD = 14;
export const RSI_OVERSOLD = 30;
export const RSI_OVERBOUGHT = 70;
export const DATA_PERIOD_DAYS = 120;

// VIX (공포지수) thresholds
export const VIX_EXTREME_FEAR = 30;
export const VIX_FEAR = 25;
export const VIX_EXTREME_GREED = 12;

// 외인/기관 연속 매수/매도 판단 기준 일수
export const INVESTOR_CONSEC_DAYS = 3;

// Stochastic RSI 설정
export const STOCH_RSI_PERIOD = 14;
export const STOCH_RSI_SMOOTH_K = 3;
export const STOCH_RSI_SMOOTH_D = 3;
export const STOCH_RSI_OVERSOLD = 20;
export const STOCH_RSI_OVERBOUGHT = 80;

// 10종목, 5+ 섹터 분산
export const WATCH_LIST = [
  { ticker: "005930", name: "삼성전자" },       // 반도체
  { ticker: "000660", name: "SK하이닉스" },     // 반도체
  { ticker: "373220", name: "LG에너지솔루션" },  // 2차전지
  { ticker: "006400", name: "삼성SDI" },        // 2차전지
  { ticker: "207940", name: "삼성바이오로직스" },  // 바이오
  { ticker: "068270", name: "셀트리온" },        // 바이오
  { ticker: "105560", name: "KB금융" },          // 금융
  { ticker: "005380", name: "현대차" },          // 자동차
  { ticker: "035420", name: "NAVER" },          // IT/플랫폼
  { ticker: "035720", name: "카카오" },          // IT/플랫폼
] as const;

// 미국 주식
export const US_WATCH_LIST = [
  { ticker: "AAPL", name: "Apple" },
  { ticker: "NVDA", name: "NVIDIA" },
  { ticker: "TSLA", name: "Tesla" },
  { ticker: "MSFT", name: "Microsoft" },
  { ticker: "AMZN", name: "Amazon" },
] as const;

// 전체 종목 (한국 + 미국)
export type MarketType = "KR" | "US";

export interface StockItem {
  ticker: string;
  name: string;
  market: MarketType;
}

export const ALL_WATCH_LIST: StockItem[] = [
  ...WATCH_LIST.map((s) => ({ ticker: s.ticker, name: s.name, market: "KR" as MarketType })),
  ...US_WATCH_LIST.map((s) => ({ ticker: s.ticker, name: s.name, market: "US" as MarketType })),
];

// ── 글로벌 매크로 데이터 설정 ──

export const MACRO_INDICATORS: Record<string, {
  ticker: string
  name: string
  unit: string
  threshold_pct: number
}> = {
  WTI: { ticker: 'CL=F', name: 'WTI 원유', unit: 'USD/bbl', threshold_pct: 5.0 },
  BRENT: { ticker: 'BZ=F', name: '브렌트유', unit: 'USD/bbl', threshold_pct: 5.0 },
  USDKRW: { ticker: 'KRW=X', name: '원달러 환율', unit: 'KRW', threshold_pct: 1.5 },
  US10Y: { ticker: '^TNX', name: '미국 10년 국채', unit: '%', threshold_pct: 5.0 },
  GOLD: { ticker: 'GC=F', name: '금', unit: 'USD/oz', threshold_pct: 3.0 },
  DXY: { ticker: 'DX-Y.NYB', name: '달러 인덱스', unit: 'pt', threshold_pct: 1.5 },
}

export const MACRO_SIGNAL_MAX_SCORE = 1.5

export const MACRO_SECTOR_IMPACT: Record<string, { buy: string[]; sell: string[] }> = {
  oil_surge: { buy: ['에너지', '정유', '조선'], sell: ['항공', '운송', '화학'] },
  oil_crash: { buy: ['항공', '운송', '화학'], sell: ['에너지', '정유'] },
  fx_krw_weak: { buy: ['반도체', '자동차', '조선'], sell: ['항공', '여행'] },
  fx_krw_strong: { buy: ['항공', '여행', '내수'], sell: ['반도체', '자동차'] },
  rate_hike: { buy: ['금융', '보험'], sell: ['성장주', 'IT', '2차전지', '바이오'] },
  rate_cut: { buy: ['성장주', 'IT', '2차전지', '바이오'], sell: ['금융'] },
  gold_surge: { buy: ['금광', '안전자산'], sell: [] },
  dollar_strong: { buy: ['반도체', '자동차'], sell: ['내수'] },
}
