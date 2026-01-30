"""
Order Manager - simple order CRUD operations
"""
import logging
from .kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages order lifecycle: place, cancel.

    Kalshi semantics:
    - action: "buy" or "sell"
    - side: "yes" or "no"
    - sell YES without position = short YES (position goes negative)
    - buy NO = economically equivalent to sell YES
    """

    def __init__(self, client: KalshiClient):
        self.client = client

    async def place_order(
        self,
        ticker: str,
        action: str,
        side: str,
        price: int,
        size: int
    ) -> str:
        """
        Place a limit order.

        Args:
            ticker: Market ticker
            action: "buy" or "sell"
            side: "yes" or "no"
            price: Limit price in cents (1-99)
            size: Number of contracts

        Returns:
            order_id string
        """
        logger.info(f"Placing order: {action} {size} {side} @ {price}c on {ticker}")

        response = await self.client.place_order(
            ticker=ticker,
            action=action,
            side=side,
            count=size,
            price_cents=price,
            order_type="limit"
        )

        order_id = response.get("order", {}).get("order_id")
        logger.info(f"Order placed: {order_id}")
        return order_id

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order.

        Args:
            order_id: The order ID to cancel

        Returns:
            True if successful
        """
        logger.info(f"Canceling order: {order_id}")
        await self.client.cancel_order(order_id)
        logger.info(f"Order canceled: {order_id}")
        return True

    async def cancel_all(self, order_ids: list[str]) -> int:
        """
        Cancel multiple orders by ID.

        Args:
            order_ids: List of order IDs to cancel

        Returns:
            Number of orders canceled
        """
        if not order_ids:
            logger.info("No orders to cancel")
            return 0

        # Batch cancel (API supports up to 20 at a time)
        for i in range(0, len(order_ids), 20):
            batch = order_ids[i:i+20]
            await self.client.batch_cancel_orders(batch)

        logger.info(f"Canceled {len(order_ids)} orders")
        return len(order_ids)
