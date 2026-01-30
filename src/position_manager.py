"""
Position and balance tracking for the market maker.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List, Callable, Awaitable

from .kalshi_client import KalshiClient
from .models import MarketPosition, Fill, BalanceInfo, TrackedPosition, Side, Action
from . import config

logger = logging.getLogger(__name__)


class PositionManager:
    """
    Manages position tracking and balance monitoring.

    Responsibilities:
    - Query and cache current positions on startup
    - Poll for new fills to update positions
    - Track available balance and margin
    - Provide position checks for order sizing
    """

    def __init__(self, client: KalshiClient):
        self.client = client

        # Position state
        self._positions: Dict[str, TrackedPosition] = {}  # ticker -> position
        self._last_fill_ts: Optional[int] = None
        self._last_fill_id: Optional[str] = None

        # Balance state
        self._balance: Optional[BalanceInfo] = None

        # Sync state
        self._initialized: bool = False
        self._polling_task: Optional[asyncio.Task] = None

        # Fill callbacks for notifying other components (e.g., Quoter)
        self._fill_callbacks: List[Callable[[Fill], Awaitable[None]]] = []

    def register_fill_callback(self, callback: Callable[[Fill], Awaitable[None]]) -> None:
        """
        Register an async callback to be invoked on new fills.

        Args:
            callback: Async function that takes a Fill object
        """
        self._fill_callbacks.append(callback)
        logger.debug(f"Registered fill callback: {callback}")

    # ========================================================================
    # INITIALIZATION
    # ========================================================================

    async def initialize(self) -> None:
        """
        Initialize position manager on startup.

        1. Fetch current balance
        2. Fetch all existing positions
        3. Fetch recent fills to establish baseline
        """
        logger.info("Initializing PositionManager...")

        # Step 1: Get balance
        await self.refresh_balance()

        # Step 2: Get existing positions from API
        await self._load_positions_from_api()

        # Step 3: Get recent fills to track last fill timestamp
        await self._load_recent_fills()

        self._initialized = True
        logger.info(
            f"PositionManager initialized. "
            f"Balance: ${self.available_balance_dollars:.2f}, "
            f"Positions: {len(self._positions)}"
        )

    async def _load_positions_from_api(self) -> None:
        """Load existing positions from Kalshi API"""
        try:
            response = await self.client.get_positions(count_filter="position")
            market_positions = response.get("market_positions", [])

            for pos_data in market_positions:
                pos = MarketPosition(**pos_data)
                if pos.position != 0:
                    self._positions[pos.ticker] = TrackedPosition(
                        ticker=pos.ticker,
                        position=pos.position,
                        avg_entry_price=0.0,  # Unknown from positions endpoint
                        realized_pnl_cents=pos.realized_pnl,
                    )

            logger.info(f"Loaded {len(self._positions)} positions from API")

        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            raise

    async def _load_recent_fills(self) -> None:
        """Load recent fills to establish baseline timestamp"""
        try:
            response = await self.client.get_fills(limit=10)
            fills = response.get("fills", [])

            if fills:
                latest = fills[0]
                self._last_fill_id = latest.get("fill_id")
                created_time = latest.get("created_time", "")
                if created_time:
                    dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                    self._last_fill_ts = int(dt.timestamp())
                logger.debug(f"Baseline fill: {self._last_fill_id}")

        except Exception as e:
            logger.warning(f"Could not load recent fills: {e}")

    # ========================================================================
    # BALANCE OPERATIONS
    # ========================================================================

    async def refresh_balance(self) -> BalanceInfo:
        """Fetch current balance from API"""
        response = await self.client.get_balance()
        self._balance = BalanceInfo(**response)
        logger.debug(f"Balance refreshed: ${self._balance.balance_dollars:.2f}")
        return self._balance

    @property
    def balance(self) -> Optional[BalanceInfo]:
        """Current cached balance info"""
        return self._balance

    @property
    def available_balance_cents(self) -> int:
        """Available balance in cents"""
        return self._balance.balance if self._balance else 0

    @property
    def available_balance_dollars(self) -> float:
        """Available balance in dollars"""
        return self.available_balance_cents / 100

    # ========================================================================
    # POSITION QUERIES
    # ========================================================================

    def get_position(self, ticker: str) -> TrackedPosition:
        """Get position for a market (returns zero position if none)"""
        if ticker not in self._positions:
            self._positions[ticker] = TrackedPosition(ticker=ticker)
        return self._positions[ticker]

    def get_all_positions(self) -> Dict[str, TrackedPosition]:
        """Get all tracked positions"""
        return self._positions.copy()

    def get_net_position(self, ticker: str) -> int:
        """Get net position: positive=YES, negative=NO, 0=flat"""
        return self.get_position(ticker).position

    def get_position_contracts(self, ticker: str) -> int:
        """Get absolute number of contracts held"""
        return abs(self.get_net_position(ticker))

    @property
    def total_exposure_cents(self) -> int:
        """Total exposure across all positions"""
        return sum(p.exposure_cents for p in self._positions.values())

    @property
    def total_exposure_dollars(self) -> float:
        """Total exposure in dollars"""
        return self.total_exposure_cents / 100

    # ========================================================================
    # POSITION LIMIT CHECKS
    # ========================================================================

    def can_add_position(
        self,
        ticker: str,
        side: Side,
        contracts: int,
        price_cents: int
    ) -> tuple[bool, str]:
        """
        Check if adding a position is allowed by risk limits.

        Returns:
            (allowed: bool, reason: str)
        """
        current_pos = self.get_position(ticker)

        # Calculate resulting position
        delta = contracts if side == Side.YES else -contracts
        new_position = current_pos.position + delta
        new_contracts = abs(new_position)

        # Allow risk-reducing orders that move position toward zero
        if current_pos.position > 0 and side == Side.NO:  # Selling YES / buying NO
            if new_contracts < abs(current_pos.position):
                return (True, "Risk-reducing order allowed")

        if current_pos.position < 0 and side == Side.YES:  # Buying YES to cover short
            if new_contracts < abs(current_pos.position):
                return (True, "Risk-reducing order allowed")

        # Check 1: Max position size per market
        if new_contracts > config.MAX_POSITION_SIZE:
            return (
                False,
                f"Exceeds max position size: {new_contracts} > {config.MAX_POSITION_SIZE}"
            )

        # Check 2: Calculate new exposure
        if new_position > 0:  # Would hold YES
            new_exposure_cents = new_contracts * price_cents
        elif new_position < 0:  # Would hold NO
            new_exposure_cents = new_contracts * (100 - price_cents)
        else:
            new_exposure_cents = 0

        # Calculate total exposure if we made this trade
        other_exposure = sum(
            p.exposure_cents for t, p in self._positions.items()
            if t != ticker
        )
        total_new_exposure = other_exposure + new_exposure_cents
        max_exposure_cents = config.MAX_TOTAL_EXPOSURE * 100

        if total_new_exposure > max_exposure_cents:
            return (
                False,
                f"Exceeds max total exposure: "
                f"${total_new_exposure/100:.2f} > ${config.MAX_TOTAL_EXPOSURE}"
            )

        return (True, "OK")

    def calculate_max_order_size(
        self,
        ticker: str,
        side: Side,
        price_cents: int
    ) -> int:
        """
        Calculate maximum contracts that can be ordered given limits.

        Considers:
        - MAX_POSITION_SIZE per market
        - MAX_TOTAL_EXPOSURE across portfolio
        - Available balance for margin
        """
        current_pos = self.get_position(ticker)

        # Limit 1: Position size limit
        if side == Side.YES:
            if current_pos.position >= 0:
                max_from_pos_limit = config.MAX_POSITION_SIZE - current_pos.position
            else:
                max_from_pos_limit = config.MAX_POSITION_SIZE + abs(current_pos.position)
        else:  # side == NO
            if current_pos.position <= 0:
                max_from_pos_limit = config.MAX_POSITION_SIZE - abs(current_pos.position)
            else:
                max_from_pos_limit = config.MAX_POSITION_SIZE + current_pos.position

        # Limit 2: Total exposure limit
        current_total_exposure = self.total_exposure_cents
        max_exposure_cents = config.MAX_TOTAL_EXPOSURE * 100
        remaining_exposure = max_exposure_cents - current_total_exposure

        if side == Side.YES:
            cost_per_contract = price_cents
        else:
            cost_per_contract = 100 - price_cents

        if cost_per_contract > 0:
            max_from_exposure = remaining_exposure // cost_per_contract
        else:
            max_from_exposure = config.MAX_POSITION_SIZE

        # Limit 3: Available balance
        if cost_per_contract > 0:
            max_from_balance = self.available_balance_cents // cost_per_contract
        else:
            max_from_balance = config.MAX_POSITION_SIZE

        # Return minimum of all limits
        return max(0, min(max_from_pos_limit, max_from_exposure, max_from_balance))

    # ========================================================================
    # FILL POLLING & POSITION UPDATES
    # ========================================================================

    async def poll_fills(self) -> List[Fill]:
        """
        Poll for new fills and update positions.

        Returns list of new fills found.
        """
        try:
            params = {"limit": config.FILL_POLL_LIMIT}
            if self._last_fill_ts:
                params["min_ts"] = self._last_fill_ts

            response = await self.client.get_fills(**params)
            fills_data = response.get("fills", [])

            new_fills = []
            for fill_data in fills_data:
                fill = Fill(**fill_data)

                # Skip if we've already processed this fill
                if self._last_fill_id and fill.fill_id == self._last_fill_id:
                    break

                new_fills.append(fill)
                await self._apply_fill(fill)

            # Update tracking state
            if new_fills:
                latest = new_fills[0]
                self._last_fill_id = latest.fill_id
                self._last_fill_ts = int(latest.created_time.timestamp())
                logger.info(f"Processed {len(new_fills)} new fills")

                # Refresh balance after fills
                await self.refresh_balance()

            return new_fills

        except Exception as e:
            logger.error(f"Error polling fills: {e}")
            return []

    async def _apply_fill(self, fill: Fill) -> None:
        """Apply a fill to update position state and notify callbacks."""
        ticker = fill.ticker
        pos = self.get_position(ticker)

        # Determine position change based on action only
        # BUY = going long = +position
        # SELL = going short = -position
        # Note: We ignore fill.side because Kalshi's internal book mechanics
        # can return confusing side values (e.g., "sell YES" may return side=no
        # because a YES ask is equivalent to a NO bid at complementary price)
        if fill.action == Action.BUY:
            delta = fill.count
        else:  # SELL
            delta = -fill.count

        old_position = pos.position
        new_position = old_position + delta

        # Update average price and track realized P&L
        if old_position == 0 or (old_position * delta > 0):
            # Opening or adding to position
            old_cost = abs(old_position) * pos.avg_entry_price
            new_cost = fill.count * fill.yes_price  # Always use yes_price for consistency
            total_contracts = abs(new_position)
            if total_contracts > 0:
                pos.avg_entry_price = (old_cost + new_cost) / total_contracts
        else:
            # Reducing/closing position - calculate realized P&L
            contracts_closed = min(abs(old_position), abs(delta))
            if old_position > 0:  # Was long YES, now selling
                realized = (fill.yes_price - pos.avg_entry_price) * contracts_closed
            else:  # Was short (long NO), now buying back
                realized = (pos.avg_entry_price - fill.yes_price) * contracts_closed
            pos.realized_pnl_cents += int(realized)
            logger.info(f"Realized P&L: {int(realized)}c on {contracts_closed} contracts")

        pos.position = new_position
        pos.last_fill_id = fill.fill_id
        pos.last_updated = datetime.utcnow()

        # Log fill with yes_price only (ignore side - Kalshi returns counterparty perspective)
        logger.info(
            f"Fill: {fill.action.value} {fill.count} @ {fill.yes_price}c | "
            f"Position: {old_position} -> {new_position}"
        )

        # Notify registered callbacks
        for callback in self._fill_callbacks:
            try:
                await callback(fill)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")

    # ========================================================================
    # BACKGROUND POLLING
    # ========================================================================

    async def start_polling(self, interval_seconds: float = None) -> None:
        """Start background fill polling task"""
        if self._polling_task and not self._polling_task.done():
            logger.warning("Polling already running")
            return

        interval = interval_seconds or config.FILL_POLL_INTERVAL
        self._polling_task = asyncio.create_task(self._polling_loop(interval))
        logger.info(f"Started fill polling (interval: {interval}s)")

    async def stop_polling(self) -> None:
        """Stop background fill polling"""
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
            logger.info("Stopped fill polling")

    async def _polling_loop(self, interval: float) -> None:
        """Background loop to poll for fills"""
        while True:
            try:
                await self.poll_fills()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(interval)
