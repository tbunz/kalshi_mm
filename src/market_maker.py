from .kalshi_client import KalshiClient
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
        logger.info("MarketMakerBot initialized successfully")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup"""
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

async def main():
    async with MarketMakerBot() as bot:
        # Get balance
        balance = await bot.client.get_balance()
        print(f"Balance: ${balance['balance'] / 100:.2f}")

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
        print(f"  YES side (price, qty):")
        for level in orderbook.get('yes', []):
            print(f"    {level[0]}c - {level[1]} contracts")
        print(f"  NO side (price, qty):")
        for level in orderbook.get('no', []):
            print(f"    {level[0]}c - {level[1]} contracts")

if __name__ == "__main__":
    asyncio.run(main())