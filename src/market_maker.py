from kalshi_python_async import Configuration, KalshiClient
from . import config
from src.error.exceptions import AuthenticationError, APIError, RateLimitError
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
        
        try:
            client_config = Configuration(
                host=config.API_BASE_URL
            )
            client_config.api_key_id = KEY_ID
            client_config.private_key_pem = KEY
            self.client = KalshiClient(client_config)

            logger.info("MarketMakerBot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise AuthenticationError(f"Failed to initialize Kalshi client: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup"""
        await self.close()

    async def close(self):
        """Cleanup connection"""
        try:
            if hasattr(self.client, 'close'):
                await self.client.close()
                logger.info("MarketMakerBot connection closed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

async def main():
    async with MarketMakerBot() as bot:
        # Your bot logic here
        pass

if __name__ == "__main__":
    asyncio.run(main())