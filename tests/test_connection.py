# tests/test_connection.py
import pytest
from src.market_maker import MarketMakerBot

@pytest.fixture
async def bot():
    """Create bot for testing"""
    bot = MarketMakerBot()
    yield bot
    await bot.close()

async def test_balance(bot):
    """Test account balance retrieval"""
    balance = await bot.client.get_balance()
    assert balance is not None
    assert balance.balance >= 0
    print(f"✅ Balance: {balance}")

async def test_authenticated(bot):
    """Test that authentication works"""
    # If this doesn't raise an exception, auth is working
    balance = await bot.client.get_balance()
    assert balance is not None