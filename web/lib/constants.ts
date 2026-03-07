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

export const WATCH_LIST = [
  { ticker: "005930", name: "삼성전자" },
  { ticker: "000660", name: "SK하이닉스" },
] as const;
