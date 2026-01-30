from .kalshi_client import KalshiClient
from .position_manager import PositionManager
from .models import Side
from . import config
from src.error.exceptions import AuthenticationError
from dotenv import load_dotenv
import os
import asyncio
import logging
import time

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
        logger.info("MarketMakerBot initialized successfully")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()

        # Initialize position manager on startup
        await self.position_manager.initialize()

        # Start background fill polling
        await self.position_manager.start_polling()

        return self

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
        ticker: str = None
    ):
        """Place a limit order. TODO: Implement with new OrderManager."""
        raise NotImplementedError("OrderManager not yet implemented")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order by ID."""
        raise NotImplementedError("OrderManager not yet implemented")

    async def cancel_all_orders(self, ticker: str = None) -> int:
        """Cancel all open orders."""
        raise NotImplementedError("OrderManager not yet implemented")

    async def get_open_orders(self, ticker: str = None) -> list:
        """Get open orders from API."""
        raise NotImplementedError("OrderManager not yet implemented")

    @property
    def open_orders(self) -> list:
        """Get locally tracked open orders."""
        raise NotImplementedError("OrderManager not yet implemented")

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

        logger.info(f"Starting trading loop (max runtime: {config.MAX_RUNTIME}s)")

        while time.time() - start_time < config.MAX_RUNTIME:
            iteration += 1
            elapsed = time.time() - start_time

            try:
                # Fetch current market state
                market = await self.get_market()
                orderbook = await self.get_orderbook(depth=5)
                position = self.get_position()

                # Send update to UI if callback provided
                if update_callback:
                    await update_callback({
                        "market": market,
                        "orderbook": orderbook,
                        "position": position,
                        "balance": self.available_balance,
                        "exposure": self.position_manager.total_exposure_dollars,
                        "iteration": iteration,
                        "elapsed": elapsed,
                    })

                # TODO: Trading strategy logic goes here
                # - Analyze spread vs TARGET_SPREAD
                # - Check liquidity vs MIN_LIQUIDITY
                # - Place/adjust quotes
                # - Manage risk

            except Exception as e:
                logger.error(f"Loop iteration {iteration} error: {e}")
                if update_callback:
                    await update_callback({"error": str(e)})

            await asyncio.sleep(config.LOOP_INTERVAL)

        logger.info(f"Trading loop finished after {iteration} iterations")


async def main():
    """Demo: display account, position, and market info."""
    async with MarketMakerBot() as bot:
        # Balance is automatically loaded on startup
        print(f"Available Balance: ${bot.available_balance:.2f}")

        # Get current position
        pos = bot.get_position()
        print(f"\nPosition in {config.MARKET_TICKER}:")
        print(f"  Net: {pos.position} ({pos.side.value if pos.side else 'flat'})")
        print(f"  Contracts: {pos.contracts}")
        print(f"  Exposure: ${pos.exposure_cents / 100:.2f}")

        # Get market info
        market = await bot.get_market()
        print(f"\nMarket: {market['ticker']}")
        print(f"  Status: {market['status']}")
        print(f"  Yes Bid: {market['yes_bid']}c")
        print(f"  Yes Ask: {market['yes_ask']}c")
        print(f"  Volume: {market['volume']}")

        # Get orderbook
        orderbook = await bot.get_orderbook(depth=5)
        print(f"\nOrderbook:")
        print(f"  YES side: {orderbook.get('yes', [])[:3]}")
        print(f"  NO side: {orderbook.get('no', [])[:3]}")


if __name__ == "__main__":
    asyncio.run(main())