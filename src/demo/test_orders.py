"""Order management test suite."""
from .runner import DemoRunner


async def run_order_tests(bot, bid_price: int, ask_price: int, nonstop: bool = False):
    """
    Interactive order management tests.

    Tests:
        1. Place passive bid
        2. Query open orders
        3. Cancel by ID
        4. Verify canceled
        5. Place passive ask
        6. Cancel all
        7. Verify clean
    """
    demo = DemoRunner("ORDER MANAGEMENT TESTS", nonstop=nonstop)
    demo.header()

    # Test 1: Place bid
    order_id = await demo.step(
        f"Place passive bid: BUY 1 YES @ {bid_price}c",
        bot.place_order,
        action="buy", side="yes", count=1, price_cents=bid_price
    )
    demo.show(f"Order ID: {order_id}")

    # Test 2: Query orders
    orders = await demo.step(
        "Query open orders",
        bot.get_open_orders
    )
    demo.show(f"Found {len(orders)} order(s)")
    for o in orders:
        price = o.get('yes_price') or o.get('no_price')
        demo.show(f"  {o['order_id'][:12]}... {o['action']} {o['side']} @ {price}c")

    # Test 3: Cancel by ID
    await demo.step(
        f"Cancel order {order_id[:12]}...",
        bot.cancel_order,
        order_id
    )

    # Test 4: Verify empty
    orders = await demo.step(
        "Verify order was canceled",
        bot.get_open_orders
    )
    demo.show(f"Found {len(orders)} order(s)")

    # Test 5: Place ask
    order_id2 = await demo.step(
        f"Place passive ask: SELL 1 YES @ {ask_price}c",
        bot.place_order,
        action="sell", side="yes", count=1, price_cents=ask_price
    )
    demo.show(f"Order ID: {order_id2}")
    demo.show("NOTE: If this fills, position goes to -1 (short YES)")

    # Test 6: Cancel all
    count = await demo.step(
        "Cancel all orders",
        bot.cancel_all_orders,
        order_ids=[order_id2]
    )
    demo.show(f"Canceled {count} order(s)")

    # Test 7: Verify clean
    orders = await demo.step(
        "Verify book is clean",
        bot.get_open_orders
    )
    demo.show(f"Found {len(orders)} order(s)")

    passed = len(orders) == 0
    demo.footer(passed)
    return passed
