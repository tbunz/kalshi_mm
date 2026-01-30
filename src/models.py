"""
Pydantic data models for position and balance tracking
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    YES = "yes"
    NO = "no"


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


# ============================================================================
# API RESPONSE MODELS
# ============================================================================

class MarketPosition(BaseModel):
    """Position in a single market (from Kalshi API)"""
    ticker: str
    position: int  # Net contracts: positive=YES, negative=NO
    market_exposure: int = 0  # Maximum potential loss in cents
    realized_pnl: int = 0  # Realized P&L in cents
    total_traded: int = 0  # Total contracts ever traded
    fees_paid: int = 0

    @property
    def side(self) -> Optional[Side]:
        """Determine which side we hold"""
        if self.position > 0:
            return Side.YES
        elif self.position < 0:
            return Side.NO
        return None

    @property
    def contracts(self) -> int:
        """Absolute number of contracts held"""
        return abs(self.position)


class Fill(BaseModel):
    """A single executed trade (from Kalshi API)"""
    fill_id: str
    order_id: str
    ticker: str
    side: Side
    action: Action
    count: int  # Number of contracts
    yes_price: int  # Price in cents
    no_price: int
    is_taker: bool
    created_time: datetime

    @property
    def price(self) -> int:
        """Get price based on side"""
        return self.yes_price if self.side == Side.YES else self.no_price


class BalanceInfo(BaseModel):
    """Account balance snapshot (from Kalshi API)"""
    balance: int  # Available balance in cents
    portfolio_value: int = 0  # Portfolio value in cents

    @property
    def balance_dollars(self) -> float:
        return self.balance / 100

    @property
    def portfolio_value_dollars(self) -> float:
        return self.portfolio_value / 100

    @property
    def total_equity_dollars(self) -> float:
        """Total account equity (balance + positions)"""
        return (self.balance + self.portfolio_value) / 100


class Order(BaseModel):
    """An order (from Kalshi API or local tracking)"""
    order_id: str
    ticker: str
    action: Action
    side: Side
    type: OrderType = OrderType.LIMIT
    price_cents: int  # Limit price
    count: int  # Contracts requested
    remaining_count: int = 0  # Contracts still open
    status: OrderStatus = OrderStatus.OPEN
    created_time: Optional[datetime] = None

    @property
    def filled_count(self) -> int:
        """Number of contracts filled"""
        return self.count - self.remaining_count

    @property
    def is_open(self) -> bool:
        return self.status == OrderStatus.OPEN

    @property
    def cost_cents(self) -> int:
        """Cost to place this order (margin required)"""
        return self.count * self.price_cents


# ============================================================================
# INTERNAL TRACKING MODELS
# ============================================================================

class TrackedPosition(BaseModel):
    """Internal position tracking with computed fields"""
    ticker: str
    position: int = 0  # Net: positive=YES, negative=NO
    avg_entry_price: float = 0.0  # Average entry price in cents
    realized_pnl_cents: int = 0
    last_fill_id: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def side(self) -> Optional[Side]:
        if self.position > 0:
            return Side.YES
        elif self.position < 0:
            return Side.NO
        return None

    @property
    def contracts(self) -> int:
        return abs(self.position)

    @property
    def exposure_cents(self) -> int:
        """Maximum potential loss"""
        if self.position == 0:
            return 0
        # For YES position: max loss = contracts * avg_price
        # For NO position: max loss = contracts * (100 - avg_price)
        if self.position > 0:  # YES
            return int(self.contracts * self.avg_entry_price)
        else:  # NO
            return int(self.contracts * (100 - self.avg_entry_price))
