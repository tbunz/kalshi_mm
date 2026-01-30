from .kalshi_client import KalshiClient
from .position_manager import PositionManager
from .models import Side
from . import config
from src.error.exceptions import AuthenticationError
from dotenv import load_dotenv
import os
import asyncio
import logging

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

async def main():
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

        # Check order sizing
        yes_price = market.get('yes_ask', 50)
        max_yes = bot.max_order_size(config.MARKET_TICKER, "yes", yes_price)
        max_no = bot.max_order_size(config.MARKET_TICKER, "no", 100 - yes_price)
        print(f"\nMax order sizes at current prices:")
        print(f"  YES @ {yes_price}c: {max_yes} contracts")
        print(f"  NO @ {100 - yes_price}c: {max_no} contracts")

        # Check if we can place a specific order
        can_order, reason = bot.can_place_order(config.MARKET_TICKER, "yes", 5, yes_price)
        print(f"\nCan place 5 YES @ {yes_price}c: {can_order} - {reason}")

        # Get orderbook
        orderbook = await bot.get_orderbook(depth=5)
        print(f"\nOrderbook:")
        print(f"  YES side (price, qty):")
        for level in orderbook.get('yes', []):
            print(f"    {level[0]}c - {level[1]} contracts")
        print(f"  NO side (price, qty):")
        for level in orderbook.get('no', []):
            print(f"    {level[0]}c - {level[1]} contracts")

if __name__ == "__main__":
    asyncio.run(main())