from .kalshi_client import KalshiClient
from .position_manager import PositionManager
from .order_manager import OrderManager
from .quoter import Quoter
from .models import Side, Fill
from . import config
from .logging_config import UILogHandler
from src.error.exceptions import AuthenticationError
from dotenv import load_dotenv
import os
import asyncio
import logging
import time
from typing import List

load_dotenv()
KEY = os.getenv("KEY")
KEY_ID = os.getenv("KEY_ID")

logger = logging.getLogger(__name__)


class MarketMakerBot:
    def __init__(self):
        """Initialize the Market Maker Bot with API client"""
        if not KEY or not KEY_ID:
            raise AuthenticationError("Missing API credentials. Check KEY and KEY_ID in .env file")

        self.client = KalshiClient(KEY_ID, KEY)
        self.position_manager = PositionManager(self.client)
        self.order_manager = OrderManager(self.client)
        self.quoter = Quoter(self)

        # Track recent fills for UI display
        self._recent_fills: List[dict] = []

        logger.info("MarketMakerBot initialized successfully")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()

        # Initialize position manager on startup
        await self.position_manager.initialize()

        # Register quoter to receive fill notifications
        self.position_manager.register_fill_callback(self.quoter.on_fill)

        # Register UI fill callback to track fills for display
        self.position_manager.register_fill_callback(self._on_fill_for_ui)

        # Start background fill polling
        await self.position_manager.start_polling()

        return self

    async def _on_fill_for_ui(self, fill: Fill) -> None:
        """Track fills for UI display."""
        fill_data = {
            "time": fill.created_time.strftime("%H:%M:%S") if fill.created_time else "",
            "action": fill.action.value if fill.action else "",
            "qty": fill.count,
            "side": fill.side.value if fill.side else "",
            "price": fill.yes_price,
            "order_id": fill.order_id,
        }
        self._recent_fills.append(fill_data)
        # Keep only last 20 fills
        if len(self._recent_fills) > 20:
            self._recent_fills = self._recent_fills[-20:]

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup"""
        # Stop polling before closing
        await self.position_manager.stop_polling()

        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def get_market(self, ticker: str = None) -> dict:
        """Fetch info for a single market"""
        ticker = ticker or config.MARKET_TICKER
        response = await self.client.get_market(ticker)
        return response["market"]

    async def get_orderbook(self, ticker: str = None, depth: int = 10) -> dict:
        """Fetch orderbook for a market"""
        ticker = ticker or config.MARKET_TICKER
        response = await self.client.get_orderbook(ticker, depth)
        return response["orderbook"]

    # ========================================================================
    # POSITION/BALANCE CONVENIENCE METHODS
    # ========================================================================

    def get_position(self, ticker: str = None):
        """Get current position for a market"""
        ticker = ticker or config.MARKET_TICKER
        return self.position_manager.get_position(ticker)

    @property
    def available_balance(self) -> float:
        """Available balance in dollars"""
        return self.position_manager.available_balance_dollars

    def can_place_order(
        self,
        ticker: str,
        side: str,
        contracts: int,
        price_cents: int
    ) -> tuple[bool, str]:
        """Check if an order can be placed given current limits"""
        side_enum = Side.YES if side.lower() == "yes" else Side.NO
        return self.position_manager.can_add_position(
            ticker, side_enum, contracts, price_cents
        )

    def max_order_size(
        self,
        ticker: str,
        side: str,
        price_cents: int
    ) -> int:
        """Calculate maximum order size given limits"""
        side_enum = Side.YES if side.lower() == "yes" else Side.NO
        return self.position_manager.calculate_max_order_size(
            ticker, side_enum, price_cents
        )

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    async def place_order(
        self,
        action: str,
        side: str,
        count: int,
        price_cents: int,
        ticker: str = None,
        skip_limit_check: bool = False
    ) -> str:
        """
        Place a limit order.

        Args:
            action: "buy" or "sell"
            side: "yes" or "no"
            count: Number of contracts
            price_cents: Limit price in cents (1-99)
            ticker: Market ticker (defaults to config.MARKET_TICKER)
            skip_limit_check: If True, bypass position/exposure limits (use with caution)

        Returns:
            order_id string

        Raises:
            ValueError: If order would exceed position/exposure limits
        """
        ticker = ticker or config.MARKET_TICKER

        # Enforce position/exposure limits unless explicitly skipped
        if not skip_limit_check:
            # Determine exposure side and price based on action
            # BUY YES = YES exposure, SELL YES = NO exposure
            # BUY NO = NO exposure, SELL NO = YES exposure
            if action.lower() == "buy":
                exposure_side = side
                exposure_price = price_cents
            else:  # sell
                exposure_side = "no" if side.lower() == "yes" else "yes"
                exposure_price = 100 - price_cents

            can_place, reason = self.can_place_order(
                ticker=ticker,
                side=exposure_side,
                contracts=count,
                price_cents=exposure_price
            )
            if not can_place:
                raise ValueError(f"Order blocked by limits: {reason}")

        return await self.order_manager.place_order(
            ticker=ticker,
            action=action,
            side=side,
            price=price_cents,
            size=count
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order by ID."""
        return await self.order_manager.cancel_order(order_id)

    async def cancel_all_orders(self, order_ids: list[str] = None, ticker: str = None) -> int:
        """
        Cancel orders. Pass order_ids if known, otherwise queries API (best effort).

        Args:
            order_ids: List of order IDs to cancel (preferred)
            ticker: Fallback - query API for this ticker's orders

        Returns:
            Count canceled
        """
        if order_ids is None:
            # Best effort: query API (may miss orders due to eventual consistency)
            ticker = ticker or config.MARKET_TICKER
            response = await self.client.get_orders(ticker=ticker, status="resting")
            order_ids = [o["order_id"] for o in response.get("orders", [])]

        return await self.order_manager.cancel_all(order_ids)

    async def get_open_orders(self, ticker: str = None) -> list[dict]:
        """Get open orders from API."""
        ticker = ticker or config.MARKET_TICKER
        response = await self.client.get_orders(ticker=ticker, status="resting")
        return response.get("orders", [])

    # ========================================================================
    # MAIN TRADING LOOP
    # ========================================================================

    async def run(self, update_callback=None):
        """
        Main trading loop - runs until MAX_RUNTIME.

        Args:
            update_callback: Optional async callable to receive state updates.
                            Used by UI to display live data.
        """
        start_time = time.time()
        iteration = 0

        logger.info(
            f"Starting trading loop | "
            f"ticker={config.MARKET_TICKER} | "
            f"spread={config.SPREAD_WIDTH}c | "
            f"size={config.QUOTE_SIZE} | "
            f"requote_threshold={config.REQUOTE_THRESHOLD}c | "
            f"max_runtime={config.MAX_RUNTIME}s"
        )

        try:
            while time.time() - start_time < config.MAX_RUNTIME:
                iteration += 1
                elapsed = time.time() - start_time

                try:
                    # Fetch current market state
                    market = await self.get_market()
                    orderbook = await self.get_orderbook(depth=5)
                    position = self.get_position()

                    # Extract best bid/ask
                    best_bid = market.get("yes_bid", 0)
                    best_ask = market.get("yes_ask", 0)
                    market_status = market.get("status", "")

                    # Calculate inventory skew
                    # Positive position (long YES) -> positive skew -> lower prices to sell
                    inventory_skew = position.position * config.INVENTORY_SKEW_PER_CONTRACT

                    # Only quote if market is active and has valid prices
                    if market_status == "active" and best_bid > 0 and best_ask > 0:
                        # Check if we should requote (pass skew so calculation matches)
                        should_update, reason = self.quoter.should_requote(
                            best_bid, best_ask, inventory_skew
                        )

                        # Log iteration summary
                        if self.quoter.has_active_quotes:
                            quote_status = f"{self.quoter.state.bid_price}/{self.quoter.state.ask_price} (resting)"
                        elif self.quoter.has_any_quotes:
                            # One side only (partial)
                            bid_str = str(self.quoter.state.bid_price) if self.quoter.state.bid_price else "-"
                            ask_str = str(self.quoter.state.ask_price) if self.quoter.state.ask_price else "-"
                            quote_status = f"{bid_str}/{ask_str} (partial)"
                        else:
                            quote_status = "none"

                        requote_str = f"Yes ({reason})" if should_update else "No"
                        logger.info(
                            f"Market: {best_bid}/{best_ask} | "
                            f"Quotes: {quote_status} | "
                            f"Requote: {requote_str}"
                        )

                        if should_update:
                            await self.quoter.update_quotes(
                                best_bid=best_bid,
                                best_ask=best_ask,
                                inventory_skew=inventory_skew
                            )
                    else:
                        # Market not active - cancel any existing quotes
                        if self.quoter.has_any_quotes:
                            logger.warning(f"Market not active ({market_status}), canceling quotes")
                            await self.quoter.cancel_quotes()

                    # Send update to UI if callback provided
                    if update_callback:
                        quote_state = self.quoter.get_state_summary()

                        # Get open orders data for UI
                        orders_data = {
                            "bid": {
                                "id": quote_state.get("bid_order_id"),
                                "price": quote_state.get("bid_price"),
                                "size": config.QUOTE_SIZE,
                            } if quote_state.get("bid_order_id") else None,
                            "ask": {
                                "id": quote_state.get("ask_order_id"),
                                "price": quote_state.get("ask_price"),
                                "size": config.QUOTE_SIZE,
                            } if quote_state.get("ask_order_id") else None,
                        }

                        # Get recent logs from UI handler
                        log_handler = UILogHandler.get_instance()
                        recent_logs = log_handler.get_recent_logs(10) if log_handler else []

                        await update_callback({
                            "market": market,
                            "orderbook": orderbook,
                            "position": position,
                            "balance": self.available_balance,
                            "exposure": self.position_manager.total_exposure_dollars,
                            "iteration": iteration,
                            "elapsed": elapsed,
                            "quotes": quote_state,
                            "inventory_skew": inventory_skew,
                            "fills": self._recent_fills[-10:],
                            "orders": orders_data,
                            "logs": recent_logs,
                        })

                except Exception as e:
                    logger.error(f"Loop iteration {iteration} error: {e}")
                    if update_callback:
                        await update_callback({"error": str(e)})

                await asyncio.sleep(config.LOOP_INTERVAL)

        finally:
            # Graceful shutdown: cancel all quotes
            elapsed_total = time.time() - start_time
            logger.info(f"Shutting down after {elapsed_total:.1f}s ({iteration} iterations)")
            try:
                await self.quoter.cancel_quotes(force_clear=True, reason="shutdown")
            except Exception as e:
                logger.error(f"Error canceling quotes on shutdown: {e}")

            # Log final position
            final_pos = self.get_position()
            logger.info(
                f"Final state | "
                f"position={final_pos.position} | "
                f"balance=${self.available_balance:.2f}"
            )


async def main(bid_price: int, ask_price: int, nonstop: bool = False):
    """Run interactive demo tests."""
    from src.demo import run_order_tests, run_quoter_tests

    async with MarketMakerBot() as bot:
        # Show account info
        print(f"Balance: ${bot.available_balance:.2f}")

        pos = bot.get_position()
        print(f"Position: {pos.position} ({pos.side.value if pos.side else 'flat'})")

        market = await bot.get_market()
        print(f"Market: {market['ticker']} - Yes: {market['yes_bid']}/{market['yes_ask']}c")

        # Run order tests
        await run_order_tests(bot, bid_price=bid_price, ask_price=ask_price, nonstop=nonstop)

        # Run quoter tests
        await run_quoter_tests(bot, bid_price=bid_price, ask_price=ask_price, nonstop=nonstop)


if __name__ == "__main__":
    asyncio.run(main())