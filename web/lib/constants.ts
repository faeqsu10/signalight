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
