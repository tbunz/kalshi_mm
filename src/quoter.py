"""
Quote management for market making.

Handles quote calculation, placement, and lifecycle tracking.
"""
from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .market_maker import MarketMakerBot
    from .models import Fill

from . import config

logger = logging.getLogger(__name__)


@dataclass
class QuoteState:
    """Current state of active quotes."""
    bid_order_id: Optional[str] = None
    ask_order_id: Optional[str] = None
    bid_price: Optional[int] = None
    ask_price: Optional[int] = None
    last_midpoint: Optional[float] = None


class Quoter:
    """
    Manages two-sided quoting for market making.

    Responsibilities:
    - Calculate optimal bid/ask prices
    - Place and track quote orders
    - Determine when to requote
    - Cancel quotes cleanly
    """

    def __init__(self, bot: "MarketMakerBot", ticker: str = None):
        """
        Initialize Quoter.

        Args:
            bot: MarketMakerBot instance for order execution
            ticker: Market ticker (defaults to config.MARKET_TICKER)
        """
        self.bot = bot
        self.ticker = ticker or config.MARKET_TICKER
        self.state = QuoteState()

    # ========================================================================
    # PURE CALCULATION METHODS
    # ========================================================================

    def calculate_quotes(
        self,
        best_bid: int,
        best_ask: int,
        inventory_skew: int = 0
    ) -> Tuple[int, int]:
        """
        Calculate bid and ask prices.

        Args:
            best_bid: Current best bid in market (cents)
            best_ask: Current best ask in market (cents)
            inventory_skew: Position skew adjustment (cents) - positive skews down

        Returns:
            (bid_price, ask_price) in cents

        Rules:
        - Midpoint = (best_bid + best_ask) / 2
        - Our bid = midpoint - SPREAD_WIDTH/2 - skew
        - Our ask = midpoint + SPREAD_WIDTH/2 - skew
        - Clamp to 1-99 range
        - Never bid above best_bid (would cross the spread)
        - Never ask below best_ask (would cross the spread)
        """
        midpoint = (best_bid + best_ask) / 2
        half_spread = config.SPREAD_WIDTH / 2

        # Raw prices
        raw_bid = midpoint - half_spread - inventory_skew
        raw_ask = midpoint + half_spread - inventory_skew

        # Round to integers
        bid_price = int(round(raw_bid))
        ask_price = int(round(raw_ask))

        # Clamp to valid range (1-99)
        bid_price = max(1, min(99, bid_price))
        ask_price = max(1, min(99, ask_price))

        # Safety: never cross ourselves (bid must be < ask)
        if bid_price >= ask_price:
            bid_price = int(midpoint) - 1
            ask_price = int(midpoint) + 1

        return bid_price, ask_price

    def should_requote(
        self,
        best_bid: int,
        best_ask: int,
        inventory_skew: int = 0
    ) -> Tuple[bool, str]:
        """
        Determine if quotes need to be refreshed.

        Args:
            best_bid: Current best bid in market
            best_ask: Current best ask in market
            inventory_skew: Position skew adjustment (must match what place_quotes will use)

        Returns:
            (should_requote: bool, reason: str)

        Triggers:
        1. No active quotes
        2. Calculated quotes differ from active quotes (handles rounding edge cases)
        3. Our quotes are crossed (bid >= ask) or through the market
        """
        # No quotes at all
        if not self.has_active_quotes:
            return True, "No active quotes"

        # Check if calculated quotes differ from active quotes
        new_bid, new_ask = self.calculate_quotes(best_bid, best_ask, inventory_skew)
        if new_bid != self.state.bid_price or new_ask != self.state.ask_price:
            mid = (best_bid + best_ask) / 2
            return True, (
                f"Quotes changed: {self.state.bid_price}/{self.state.ask_price} → {new_bid}/{new_ask} "
                f"(mkt={best_bid}/{best_ask}, mid={mid:.1f}, skew={inventory_skew})"
            )

        # Our bid is through the market (higher than best_bid = would be taken)
        if self.state.bid_price is not None and self.state.bid_price > best_bid:
            return True, f"Bid through market: {self.state.bid_price} > {best_bid}"

        # Our ask is through the market (lower than best_ask = would be taken)
        if self.state.ask_price is not None and self.state.ask_price < best_ask:
            return True, f"Ask through market: {self.state.ask_price} < {best_ask}"

        # Our quotes are crossed (shouldn't happen, but safety check)
        if (self.state.bid_price is not None and
            self.state.ask_price is not None and
            self.state.bid_price >= self.state.ask_price):
            return True, "Quotes crossed"

        return False, "Quotes OK"

    @property
    def has_active_quotes(self) -> bool:
        """Check if both quotes are active."""
        return (self.state.bid_order_id is not None and
                self.state.ask_order_id is not None)

    @property
    def has_any_quotes(self) -> bool:
        """Check if any quote is active."""
        return (self.state.bid_order_id is not None or
                self.state.ask_order_id is not None)

    # ========================================================================
    # ORDER EXECUTION METHODS
    # ========================================================================

    async def place_quotes(
        self,
        best_bid: int,
        best_ask: int,
        size: int = None,
        inventory_skew: int = 0
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Place both bid and ask quotes.

        Args:
            best_bid: Current market best bid
            best_ask: Current market best ask
            size: Contract size per side (defaults to config.QUOTE_SIZE)
            inventory_skew: Position skew adjustment

        Returns:
            (bid_order_id, ask_order_id) - may be None if placement fails or blocked by limits

        Side effects:
            Updates self.state with new order IDs and prices
        """
        size = size or config.QUOTE_SIZE
        bid_price, ask_price = self.calculate_quotes(best_bid, best_ask, inventory_skew)

        # Log placement intent
        logger.info(f"Placing: bid={bid_price}c, ask={ask_price}c, size={size}")

        bid_order_id = None
        ask_order_id = None

        # Check position limits before placing bid (buying YES)
        can_bid, bid_reason = self.bot.can_place_order(
            ticker=self.ticker,
            side="yes",
            contracts=size,
            price_cents=bid_price
        )
        if not can_bid:
            logger.warning(f"Bid blocked by limits: {bid_reason}")
        else:
            try:
                # Place bid: BUY YES at bid price
                bid_order_id = await self.bot.place_order(
                    action="buy",
                    side="yes",
                    count=size,
                    price_cents=bid_price,
                    ticker=self.ticker
                )
            except Exception as e:
                logger.error(f"Failed to place bid: {e}")

        # Check position limits before placing ask (selling YES)
        # Note: selling YES is equivalent to buying NO exposure
        can_ask, ask_reason = self.bot.can_place_order(
            ticker=self.ticker,
            side="no",  # Selling YES = NO exposure
            contracts=size,
            price_cents=100 - ask_price  # NO price is inverse of YES price
        )
        if not can_ask:
            logger.warning(f"Ask blocked by limits: {ask_reason}")
        else:
            try:
                # Place ask: SELL YES at ask price
                ask_order_id = await self.bot.place_order(
                    action="sell",
                    side="yes",
                    count=size,
                    price_cents=ask_price,
                    ticker=self.ticker
                )
            except Exception as e:
                logger.error(f"Failed to place ask: {e}")

        # Cancel lone order only if it adds risk (not if it reduces position)
        position = self.bot.get_position(self.ticker).position

        if bid_order_id and not ask_order_id:
            # Lone bid is OK if we're short (reduces risk), bad if flat or long
            if position >= 0:
                logger.warning("Partial placement - canceling lone bid to avoid one-sided exposure")
                try:
                    await self.bot.cancel_order(bid_order_id)
                    bid_order_id = None
                except Exception as e:
                    logger.error(f"Failed to cancel lone bid: {e}")
            else:
                logger.info(f"Allowing lone bid to reduce short position ({position})")

        elif ask_order_id and not bid_order_id:
            # Lone ask is OK if we're long (reduces risk), bad if flat or short
            if position <= 0:
                logger.warning("Partial placement - canceling lone ask to avoid one-sided exposure")
                try:
                    await self.bot.cancel_order(ask_order_id)
                    ask_order_id = None
                except Exception as e:
                    logger.error(f"Failed to cancel lone ask: {e}")
            else:
                logger.info(f"Allowing lone ask to reduce long position ({position})")

        # Log successful placement with order IDs
        if bid_order_id and ask_order_id:
            logger.info(f"Placed: bid={bid_order_id}, ask={ask_order_id}")
        elif bid_order_id or ask_order_id:
            logger.warning(f"Partial placed: bid={bid_order_id}, ask={ask_order_id}")

        # Update state
        midpoint = (best_bid + best_ask) / 2
        self.state = QuoteState(
            bid_order_id=bid_order_id,
            ask_order_id=ask_order_id,
            bid_price=bid_price if bid_order_id else None,
            ask_price=ask_price if ask_order_id else None,
            last_midpoint=midpoint
        )

        return bid_order_id, ask_order_id

    async def cancel_quotes(self, force_clear: bool = False, reason: str = "requote") -> int:
        """
        Cancel all active quotes.

        Args:
            force_clear: If True, clear state even on cancel failure (use when
                        you know orders are gone, e.g., market closed)
            reason: Why quotes are being canceled (for logging)

        Returns:
            Number of orders canceled

        Side effects:
            Clears self.state on success or if force_clear=True
        """
        order_ids = []
        if self.state.bid_order_id:
            order_ids.append(self.state.bid_order_id)
        if self.state.ask_order_id:
            order_ids.append(self.state.ask_order_id)

        if not order_ids:
            return 0

        # Log with order IDs for audit trail
        logger.info(
            f"Canceling: bid={self.state.bid_order_id}, ask={self.state.ask_order_id} | "
            f"reason={reason}"
        )

        try:
            count = await self.bot.cancel_all_orders(order_ids=order_ids)
            # Success - clear state
            self.state = QuoteState()
            return count
        except Exception as e:
            logger.error(f"Error canceling quotes: {e}")
            if force_clear:
                logger.warning("Force clearing quote state despite cancel failure")
                self.state = QuoteState()
            else:
                logger.warning("Quote state preserved - orders may still be resting")
            return 0

    async def update_quotes(
        self,
        best_bid: int,
        best_ask: int,
        size: int = None,
        inventory_skew: int = 0,
        reason: str = "requote"
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Cancel existing quotes and place new ones.

        Args:
            best_bid: Current market best bid
            best_ask: Current market best ask
            size: Contract size per side
            inventory_skew: Position skew adjustment
            reason: Why quotes are being updated (for logging)

        Returns:
            (bid_order_id, ask_order_id) from new quotes
        """
        await self.cancel_quotes(reason=reason)
        return await self.place_quotes(best_bid, best_ask, size, inventory_skew)

    # ========================================================================
    # STATE INSPECTION
    # ========================================================================

    def get_state_summary(self) -> dict:
        """Get current quote state as dict for debugging/display."""
        return {
            "bid_order_id": self.state.bid_order_id,
            "ask_order_id": self.state.ask_order_id,
            "bid_price": self.state.bid_price,
            "ask_price": self.state.ask_price,
            "last_midpoint": self.state.last_midpoint,
            "has_active_quotes": self.has_active_quotes,
        }

    async def on_fill(self, fill: "Fill") -> None:
        """
        Handle fill notification from PositionManager.

        Clears quote state if the filled order was one of our quotes,
        so should_requote() will trigger new quote placement.
        """
        if fill.order_id == self.state.bid_order_id:
            logger.info(
                f"Quote filled: BID {fill.count}@{fill.yes_price}c | "
                f"order={fill.order_id}"
            )
            self.state.bid_order_id = None
            self.state.bid_price = None
        elif fill.order_id == self.state.ask_order_id:
            logger.info(
                f"Quote filled: ASK {fill.count}@{fill.yes_price}c | "
                f"order={fill.order_id}"
            )
            self.state.ask_order_id = None
            self.state.ask_price = None
