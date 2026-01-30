"""
Simple Kalshi API client - no external SDK dependency
"""
import aiohttp
import base64
import time
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from . import config


class KalshiClient:
    # API path prefix (used in signature)
    API_PREFIX = "/trade-api/v2"

    def __init__(self, key_id: str, private_key_pem: str):
        self.key_id = key_id
        self.private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )
        self.base_url = config.API_BASE_URL.rstrip("/")
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _sign(self, timestamp_ms: int, method: str, path: str) -> str:
        """Create RSA-PSS signature for request"""
        message = f"{timestamp_ms}{method}{path}"
        signature = self.private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def _headers(self, method: str, path: str) -> dict:
        """Generate authenticated headers"""
        timestamp_ms = int(time.time() * 1000)
        signature = self._sign(timestamp_ms, method, path)
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json"
        }

    async def get(self, path: str, params: dict = None) -> dict:
        """Make authenticated GET request"""
        full_path = f"{self.API_PREFIX}{path}"
        headers = self._headers("GET", full_path)
        url = f"{self.base_url}{full_path}"
        async with self.session.get(url, headers=headers, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def post(self, path: str, data: dict = None) -> dict:
        """Make authenticated POST request"""
        full_path = f"{self.API_PREFIX}{path}"
        headers = self._headers("POST", full_path)
        url = f"{self.base_url}{full_path}"
        async with self.session.post(url, headers=headers, json=data) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def delete(self, path: str) -> dict:
        """Make authenticated DELETE request"""
        full_path = f"{self.API_PREFIX}{path}"
        headers = self._headers("DELETE", full_path)
        url = f"{self.base_url}{full_path}"
        async with self.session.delete(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Convenience methods
    async def get_balance(self) -> dict:
        return await self.get("/portfolio/balance")

    async def get_market(self, ticker: str) -> dict:
        return await self.get(f"/markets/{ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        return await self.get(f"/markets/{ticker}/orderbook", {"depth": depth})
