from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import List, Optional


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Signal:
    date: date
    ticker: str
    name: str
    signal_type: SignalType
    source: str              # "MA_CROSS", "RSI", "MACD"
    strength: float          # 0.0 ~ 1.0
    description: str
    price: float


@dataclass
class Trade:
    ticker: str
    name: str
    entry_date: date
    entry_price: float
    entry_signal: str
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    exit_signal: Optional[str] = None
    shares: int = 0
    pnl: float = 0.0
    return_pct: float = 0.0


@dataclass
class BacktestResult:
    ticker: str
    name: str
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    total_return_pct: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_return_per_trade: float
    trades: List[Trade]
    equity_curve: List[float]
