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

    async def delete(self, path: str, params: dict = None, data: dict = None) -> dict:
        """Make authenticated DELETE request"""
        full_path = f"{self.API_PREFIX}{path}"
        # Signature is on path only, not query params
        headers = self._headers("DELETE", full_path)
        url = f"{self.base_url}{full_path}"
        async with self.session.delete(url, headers=headers, params=params, json=data) as resp:
            resp.raise_for_status()
            return await resp.json()

    # Convenience methods
    async def get_balance(self) -> dict:
        return await self.get("/portfolio/balance")

    async def get_market(self, ticker: str) -> dict:
        return await self.get(f"/markets/{ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> dict:
        return await self.get(f"/markets/{ticker}/orderbook", {"depth": depth})

    async def get_positions(
        self,
        ticker: str = None,
        count_filter: str = None,
        limit: int = 100,
        cursor: str = None
    ) -> dict:
        """
        Fetch portfolio positions.

        Args:
            ticker: Filter by specific market ticker
            count_filter: Filter positions - 'position' or 'total_traded'
            limit: Number of results (1-1000, default 100)
            cursor: Pagination cursor
        """
        params = {}
        if ticker:
            params['ticker'] = ticker
        if count_filter:
            params['count_filter'] = count_filter
        if limit != 100:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        return await self.get("/portfolio/positions", params or None)

    async def get_fills(
        self,
        ticker: str = None,
        order_id: str = None,
        min_ts: int = None,
        max_ts: int = None,
        limit: int = 100,
        cursor: str = None
    ) -> dict:
        """
        Fetch fill history (executed trades).

        Args:
            ticker: Filter by market ticker
            order_id: Filter by specific order
            min_ts: Unix timestamp - fills after this time
            max_ts: Unix timestamp - fills before this time
            limit: Number of results (1-200, default 100)
            cursor: Pagination cursor
        """
        params = {}
        if ticker:
            params['ticker'] = ticker
        if order_id:
            params['order_id'] = order_id
        if min_ts:
            params['min_ts'] = min_ts
        if max_ts:
            params['max_ts'] = max_ts
        if limit != 100:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        return await self.get("/portfolio/fills", params or None)

    # ========================================================================
    # ORDER MANAGEMENT
    # ========================================================================

    async def place_order(
        self,
        ticker: str,
        action: str,
        side: str,
        count: int,
        price_cents: int,
        order_type: str = "limit",
        client_order_id: str = None
    ) -> dict:
        """
        Place an order.

        Args:
            ticker: Market ticker
            action: "buy" or "sell"
            side: "yes" or "no"
            count: Number of contracts
            price_cents: Limit price in cents (1-99)
            order_type: "limit" or "market"
            client_order_id: Optional client-provided ID

        Returns:
            Order response with order_id
        """
        data = {
            "ticker": ticker,
            "action": action,
            "side": side,
            "count": count,
            "type": order_type,
        }
        # Only include price for limit orders
        if order_type == "limit":
            if side == "yes":
                data["yes_price"] = price_cents
            else:
                data["no_price"] = price_cents
        if client_order_id:
            data["client_order_id"] = client_order_id
        return await self.post("/portfolio/orders", data)

    async def cancel_order(self, order_id: str) -> dict:
        """Cancel a specific order by ID."""
        return await self.delete(f"/portfolio/orders/{order_id}")

    async def batch_cancel_orders(self, order_ids: list[str]) -> dict:
        """
        Cancel multiple orders at once (up to 20).

        Args:
            order_ids: List of order IDs to cancel
        """
        return await self.delete("/portfolio/orders/batched", data={"ids": order_ids})

    async def get_orders(
        self,
        ticker: str = None,
        status: str = None,
        limit: int = 100,
        cursor: str = None
    ) -> dict:
        """
        Get orders.

        Args:
            ticker: Filter by market ticker
            status: Filter by status (e.g., "open", "filled", "canceled")
            limit: Number of results
            cursor: Pagination cursor
        """
        params = {}
        if ticker:
            params['ticker'] = ticker
        if status:
            params['status'] = status
        if limit != 100:
            params['limit'] = limit
        if cursor:
            params['cursor'] = cursor
        return await self.get("/portfolio/orders", params or None)

    async def get_order(self, order_id: str) -> dict:
        """Get a specific order by ID."""
        return await self.get(f"/portfolio/orders/{order_id}")
