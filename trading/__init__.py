from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Order:
    ticker: str
    name: str
    side: str  # "buy" or "sell"
    quantity: int
    price: int
    order_type: str = "market"  # "market" or "limit"
    status: str = "pending"  # "pending", "filled", "rejected", "cancelled", "simulated"
    order_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    reason: str = ""  # rejection reason or signal trigger


@dataclass
class TradingConfig:
    dry_run: bool = True  # True = paper trading (no real orders)
    daily_loss_limit_pct: float = 3.0  # max daily loss %
    max_single_position_pct: float = 30.0  # max single stock weight %
    max_order_amount: int = 5_000_000  # max single order KRW
    account_no: str = ""
    use_mock: bool = True  # True = 키움 모의투자
