from kalshi_python_async import Configuration, KalshiClient
from . import config
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
KEY = os.getenv("KEY")
KEY_ID = os.getenv("KEY_ID")

class MarketMakerBot:
    def __init__(self):
        """API Client"""
        client_config = Configuration(
            host=config.API_BASE_URL
        )
        client_config.api_key_id = KEY_ID
        client_config.private_key_pem = KEY
        self.client = KalshiClient(client_config)

    async def test_connection(self):
        """Test authenticated connection"""
        try:
            # Try getting your account balance or user info
            balance = await self.client.get_balance()  # adjust method name
            print(f"✅ Connection successful! Balance: {balance}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

async def main():
    print("mm.py")
    bot = MarketMakerBot()
    await bot.test_connection()


if __name__ == "__main__":
    asyncio.run(main())