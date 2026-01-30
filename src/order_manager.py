"""
Order Manager - handles order CRUD operations
"""
from typing import Dict, List, Optional
from datetime import datetime
import logging
import asyncio

from .kalshi_client import KalshiClient
from .position_manager import PositionManager
from .models import Order, OrderStatus, OrderType, Side, Action

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages order lifecycle: place, cancel, track.

    Integrates with PositionManager for pre-trade validation.
    """

    def __init__(self, client: KalshiClient, position_manager: PositionManager):
        self.client = client
        self.position_manager = position_manager
        self._open_orders: Dict[str, Order] = {}  # order_id -> Order

    @property
    def open_orders(self) -> List[Order]:
        """Get list of locally tracked open orders."""
        return list(self._open_orders.values())

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get a tracked order by ID."""
        return self._open_orders.get(order_id)

    async def place_order(
        self,
        ticker: str,
        action: str,
        side: str,
        count: int,
        price_cents: int,
        skip_validation: bool = False
    ) -> Order:
        """
        Place a limit order.

        Args:
            ticker: Market ticker
            action: "buy" or "sell"
            side: "yes" or "no"
            count: Number of contracts
            price_cents: Limit price in cents (1-99)
            skip_validation: Skip position manager validation

        Returns:
            Order object

        Raises:
            ValueError: If validation fails or order rejected
        """
        # Validate with position manager (unless skipped)
        if not skip_validation:
            side_enum = Side.YES if side.lower() == "yes" else Side.NO
            can_place, reason = self.position_manager.can_add_position(
                ticker, side_enum, count, price_cents
            )
            if not can_place:
                raise ValueError(f"Order validation failed: {reason}")

        logger.info(f"Placing order: {action} {count} {side} @ {price_cents}c on {ticker}")

        # Place via API
        response = await self.client.place_order(
            ticker=ticker,
            action=action,
            side=side,
            count=count,
            price_cents=price_cents,
            order_type="limit"
        )

        # Parse response into Order object
        order_data = response.get("order", response)
        # DEBUG: Print API response fields to understand structure
        print(f"  DEBUG API response: {order_data}")
        order = self._parse_order(order_data)

        # Track if open
        if order.is_open:
            self._open_orders[order.order_id] = order
            logger.info(f"Order placed: {order.order_id}")
        else:
            logger.info(f"Order immediately filled/rejected: {order.order_id} status={order.status}")

        return order

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order.

        Args:
            order_id: The order ID to cancel

        Returns:
            True if canceled successfully
        """
        logger.info(f"Canceling order: {order_id}")

        try:
            await self.client.cancel_order(order_id)
            # Remove from local tracking
            if order_id in self._open_orders:
                del self._open_orders[order_id]
            logger.info(f"Order canceled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    async def cancel_all(self, ticker: str = None) -> int:
        """
        Cancel all open orders.

        Args:
            ticker: Optional - only cancel orders for this market

        Returns:
            Number of orders canceled
        """
        logger.info(f"Canceling all orders{f' for {ticker}' if ticker else ''}")

        # Save local cache before refresh (in case API returns empty due to eventual consistency)
        local_order_ids = [
            oid for oid, order in self._open_orders.items()
            if ticker is None or order.ticker == ticker
        ]

        # Try to get fresh orders from API
        await self.refresh_orders(ticker)

        # Get order IDs - prefer API result, fallback to local cache
        if ticker:
            order_ids = [
                oid for oid, order in self._open_orders.items()
                if order.ticker == ticker
            ]
        else:
            order_ids = list(self._open_orders.keys())

        # If API returned empty but we had local orders, use those
        if not order_ids and local_order_ids:
            logger.debug(f"API returned empty, using {len(local_order_ids)} locally tracked orders")
            order_ids = local_order_ids

        if not order_ids:
            logger.info("No matching orders to cancel")
            return 0

        # Batch cancel (up to 20 at a time)
        canceled = 0
        for i in range(0, len(order_ids), 20):
            batch = order_ids[i:i+20]
            try:
                await self.client.batch_cancel_orders(batch)
                canceled += len(batch)
                # Remove from local tracking
                for oid in batch:
                    self._open_orders.pop(oid, None)
            except Exception as e:
                logger.error(f"Failed to cancel batch: {e}")
                raise

        logger.info(f"Canceled {canceled} orders")
        return canceled

    async def refresh_orders(
        self,
        ticker: str = None,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ) -> List[Order]:
        """
        Sync local order cache with API.

        Args:
            ticker: Optional - only refresh for this market
            max_retries: Number of retries if API returns empty but we expect orders
            retry_delay: Delay between retries in seconds

        Returns:
            List of current open orders
        """
        logger.debug("Refreshing orders from API")

        # Track what we expect to find (for retry logic)
        expected_count = len([
            o for o in self._open_orders.values()
            if ticker is None or o.ticker == ticker
        ])

        orders_data = []
        for attempt in range(max_retries):
            # Kalshi uses "resting" for open orders, not "open"
            response = await self.client.get_orders(ticker=ticker, status="resting")
            orders_data = response.get("orders", [])

            # If we got orders OR we didn't expect any, we're done
            if orders_data or expected_count == 0:
                break

            # API returned empty but we expected orders - eventual consistency
            if attempt < max_retries - 1:
                logger.debug(
                    f"API returned 0 orders but expected {expected_count}, "
                    f"retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5  # Exponential backoff

        # If API still returns empty but we expected orders, keep local cache
        if not orders_data and expected_count > 0:
            logger.debug(
                f"API still empty after retries, keeping {expected_count} locally tracked orders"
            )
            return self.open_orders

        # Rebuild cache from API response
        if ticker:
            # Only update orders for this ticker
            self._open_orders = {
                oid: order for oid, order in self._open_orders.items()
                if order.ticker != ticker
            }
        else:
            self._open_orders.clear()

        for order_data in orders_data:
            order = self._parse_order(order_data)
            if order.is_open:
                self._open_orders[order.order_id] = order

        logger.debug(f"Refreshed: {len(self._open_orders)} open orders")
        return self.open_orders

    async def get_order_from_api(self, order_id: str) -> Order:
        """Fetch a specific order from API."""
        response = await self.client.get_order(order_id)
        order_data = response.get("order", response)
        return self._parse_order(order_data)

    def _parse_order(self, data: dict) -> Order:
        """Parse API response into Order model."""
        # Handle status mapping
        status_str = data.get("status", "open").lower()
        status_map = {
            "resting": OrderStatus.OPEN,
            "open": OrderStatus.OPEN,
            "pending": OrderStatus.PENDING,
            "filled": OrderStatus.FILLED,
            "canceled": OrderStatus.CANCELED,
            "cancelled": OrderStatus.CANCELED,
            "rejected": OrderStatus.REJECTED,
        }
        status = status_map.get(status_str, OrderStatus.OPEN)

        # Parse timestamps
        created_time = None
        if "created_time" in data:
            try:
                created_time = datetime.fromisoformat(
                    data["created_time"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Get price - API may use yes_price/no_price
        side_str = data.get("side", "yes").lower()
        price_cents = data.get("yes_price") if side_str == "yes" else data.get("no_price")
        if price_cents is None:
            price_cents = data.get("price", 0)

        # Get count - API uses different field names
        # Try: count, original_count, remaining_count (for new unfilled orders)
        count = data.get("count") or data.get("original_count") or data.get("remaining_count", 0)
        remaining = data.get("remaining_count", count)  # Default to count if not specified

        return Order(
            order_id=data.get("order_id", data.get("id", "")),
            ticker=data.get("ticker", ""),
            action=Action(data.get("action", "buy").lower()),
            side=Side(side_str),
            type=OrderType(data.get("type", "limit").lower()),
            price_cents=price_cents,
            count=count,
            remaining_count=remaining,
            status=status,
            created_time=created_time,
        )
