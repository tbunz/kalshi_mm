"""Quoter test suite."""
from .runner import DemoRunner
from src.quoter import Quoter, QuoteState
from src import config


# ============================================================================
# UNIT TESTS (no network, pure calculation)
# ============================================================================

def test_quote_calculation():
    """Test calculate_quotes math - no network required."""
    print("\n[UNIT] Testing quote calculation...")

    # Create a mock bot (not used for calculation)
    class MockBot:
        pass

    quoter = Quoter(MockBot(), ticker="TEST")

    # Test 1: Standard case - market at 32/33 with 6-cent spread
    # Midpoint = 32.5, half_spread = 3
    # bid = 32.5 - 3 = 29.5 -> 30 (rounded), but clamped to <= best_bid (32)
    # ask = 32.5 + 3 = 35.5 -> 36 (rounded), and >= best_ask (33) ok
    bid, ask = quoter.calculate_quotes(best_bid=32, best_ask=33)
    assert bid <= 32, f"Bid should be <= best_bid 32, got {bid}"
    assert ask >= 33, f"Ask should be >= best_ask 33, got {ask}"
    print(f"  Pass: 32/33 market -> {bid}/{ask}")

    # Test 2: Wider market - spread wider than our spread
    bid, ask = quoter.calculate_quotes(best_bid=45, best_ask=55)
    # Midpoint = 50, half_spread = 3
    # raw_bid = 50 - 3 = 47, raw_ask = 50 + 3 = 53
    # Clamped: bid <= best_bid (45), ask >= best_ask (55)
    assert bid == 45, f"Expected bid=45 (clamped to best_bid), got {bid}"
    assert ask == 55, f"Expected ask=55 (clamped to best_ask), got {ask}"
    print(f"  Pass: 45/55 market -> {bid}/{ask} (clamped to market)")

    # Test 3: Market at 50/52 with 6-cent spread
    # Midpoint = 51, half_spread = 3
    # bid = 51 - 3 = 48, ask = 51 + 3 = 54
    bid, ask = quoter.calculate_quotes(best_bid=50, best_ask=52)
    assert bid == 48, f"Expected bid=48, got {bid}"
    assert ask == 54, f"Expected ask=54, got {ask}"
    print(f"  Pass: 50/52 market -> {bid}/{ask}")

    # Test 4: Edge case near lower boundary
    # Market at 5/6, midpoint = 5.5, half_spread = 3
    # raw_bid = 5.5 - 3 = 2.5 -> 2 (rounded)
    # raw_ask = 5.5 + 3 = 8.5 -> 8 (rounded)
    # Clamped: bid <= 5 (2 OK), ask >= 6 (8 OK)
    bid, ask = quoter.calculate_quotes(best_bid=5, best_ask=6)
    assert bid >= 1, f"Bid should be >= 1, got {bid}"
    assert bid <= 5, f"Bid should be <= best_bid 5, got {bid}"
    assert ask >= 6, f"Ask should be >= best_ask 6, got {ask}"
    assert ask <= 99, f"Ask should be <= 99, got {ask}"
    print(f"  Pass: 5/6 market -> {bid}/{ask} (near lower boundary)")

    # Test 5: Edge case near upper boundary
    # Market at 95/96, midpoint = 95.5, half_spread = 3
    # bid = 95.5 - 3 = 92.5 -> 92 or 93
    # ask = 95.5 + 3 = 98.5 -> 98 or 99
    bid, ask = quoter.calculate_quotes(best_bid=95, best_ask=96)
    assert ask <= 99, f"Ask should be <= 99, got {ask}"
    assert ask >= 96, f"Ask should be >= best_ask 96, got {ask}"
    print(f"  Pass: 95/96 market -> {bid}/{ask} (near upper boundary)")

    # Test 6: Extreme low - don't go below 1
    # Market at 3/7, midpoint = 5, half_spread = 3
    # bid = 5 - 3 = 2, clamped to <= 3 -> 2
    bid, ask = quoter.calculate_quotes(best_bid=3, best_ask=7)
    assert bid >= 1, f"Bid should never be < 1, got {bid}"
    assert bid <= 3, f"Bid should be <= best_bid 3, got {bid}"
    print(f"  Pass: 3/7 market -> {bid}/{ask} (extreme low)")

    # Test 7: Extreme high - don't go above 99
    # Market at 93/97, midpoint = 95, half_spread = 3
    # bid = 95 - 3 = 92, ask = 95 + 3 = 98
    bid, ask = quoter.calculate_quotes(best_bid=93, best_ask=97)
    assert ask <= 99, f"Ask should never be > 99, got {ask}"
    assert ask >= 97, f"Ask should be >= best_ask 97, got {ask}"
    print(f"  Pass: 93/97 market -> {bid}/{ask} (extreme high)")

    print("  [UNIT] All calculation tests passed!")
    return True


async def test_fill_callback():
    """Test on_fill clears quote state - no network required."""
    print("\n[UNIT] Testing fill callback...")

    class MockBot:
        pass

    quoter = Quoter(MockBot(), ticker="TEST")

    # Set up quote state with known order IDs
    quoter.state = QuoteState(
        bid_order_id="bid-order-123",
        ask_order_id="ask-order-456",
        bid_price=45,
        ask_price=55,
        last_midpoint=50.0
    )

    # Create a mock fill matching the bid order
    class MockFill:
        order_id = "bid-order-123"
        count = 5
        yes_price = 45

    # Test 1: Fill on bid should clear bid state
    assert quoter.state.bid_order_id is not None, "Setup: bid should be set"
    await quoter.on_fill(MockFill())
    assert quoter.state.bid_order_id is None, "Bid order_id should be cleared after fill"
    assert quoter.state.bid_price is None, "Bid price should be cleared after fill"
    assert quoter.state.ask_order_id == "ask-order-456", "Ask should be unchanged"
    print("  Pass: Bid fill clears bid state, leaves ask")

    # Test 2: Fill on ask should clear ask state
    quoter.state = QuoteState(
        bid_order_id="bid-order-789",
        ask_order_id="ask-order-999",
        bid_price=45,
        ask_price=55,
        last_midpoint=50.0
    )

    class MockAskFill:
        order_id = "ask-order-999"
        count = 3
        yes_price = 55

    await quoter.on_fill(MockAskFill())
    assert quoter.state.ask_order_id is None, "Ask order_id should be cleared after fill"
    assert quoter.state.ask_price is None, "Ask price should be cleared after fill"
    assert quoter.state.bid_order_id == "bid-order-789", "Bid should be unchanged"
    print("  Pass: Ask fill clears ask state, leaves bid")

    # Test 3: Fill with unrelated order_id should not change state
    quoter.state = QuoteState(
        bid_order_id="bid-order-aaa",
        ask_order_id="ask-order-bbb",
        bid_price=45,
        ask_price=55,
        last_midpoint=50.0
    )

    class MockUnrelatedFill:
        order_id = "some-other-order"
        count = 10
        yes_price = 50

    await quoter.on_fill(MockUnrelatedFill())
    assert quoter.state.bid_order_id == "bid-order-aaa", "Bid unchanged for unrelated fill"
    assert quoter.state.ask_order_id == "ask-order-bbb", "Ask unchanged for unrelated fill"
    print("  Pass: Unrelated fill leaves state unchanged")

    # Test 4: After fill, should_requote should return True
    quoter.state = QuoteState(
        bid_order_id="bid-123",
        ask_order_id="ask-456",
        bid_price=45,
        ask_price=55,
        last_midpoint=50.0
    )

    # Both quotes active - should not requote
    should, _ = quoter.should_requote(best_bid=45, best_ask=55)
    assert not should, "Should not requote when both quotes active"

    # Fill the bid
    class MockBidFill:
        order_id = "bid-123"
        count = 1
        yes_price = 45

    await quoter.on_fill(MockBidFill())

    # Now should requote (only one side active)
    should, reason = quoter.should_requote(best_bid=45, best_ask=55)
    assert should, "Should requote after fill (partial quotes)"
    print(f"  Pass: After fill, should_requote=True ({reason})")

    print("  [UNIT] All fill callback tests passed!")
    return True


def test_requote_logic():
    """Test should_requote logic - no network required."""
    print("\n[UNIT] Testing requote logic...")

    class MockBot:
        pass

    quoter = Quoter(MockBot(), ticker="TEST")

    # Test 1: No quotes -> should requote
    should, reason = quoter.should_requote(best_bid=45, best_ask=55)
    assert should, f"Should requote with no quotes, got {should}"
    assert "No active" in reason
    print(f"  Pass: No quotes -> requote ({reason})")

    # Test 2: Simulate having quotes, midpoint stable
    # Our quotes must be at or inside the market (bid <= best_bid, ask >= best_ask)
    quoter.state = QuoteState(
        bid_order_id="bid123",
        ask_order_id="ask123",
        bid_price=43,  # Below best_bid of 45
        ask_price=57,  # Above best_ask of 55
        last_midpoint=50.0
    )
    should, reason = quoter.should_requote(best_bid=45, best_ask=55)
    assert not should, f"Should NOT requote when stable, got {should}"
    print(f"  Pass: Stable market -> no requote ({reason})")

    # Test 3: Midpoint moved 1 tick (below threshold)
    quoter.state = QuoteState(
        bid_order_id="bid123",
        ask_order_id="ask123",
        bid_price=43,
        ask_price=57,
        last_midpoint=50.0
    )
    should, reason = quoter.should_requote(best_bid=45, best_ask=56)
    # New midpoint = 50.5, change = 0.5 < REQUOTE_THRESHOLD(2)
    assert not should, f"Should NOT requote on small move, got {should}"
    print(f"  Pass: Small move -> no requote ({reason})")

    # Test 4: Midpoint moved beyond threshold
    quoter.state = QuoteState(
        bid_order_id="bid123",
        ask_order_id="ask123",
        bid_price=43,
        ask_price=57,
        last_midpoint=50.0
    )
    should, reason = quoter.should_requote(best_bid=48, best_ask=58)
    # New midpoint = 53, change = 3 >= REQUOTE_THRESHOLD(2)
    assert should, f"Should requote on midpoint move, got {should}"
    assert "moved" in reason.lower()
    print(f"  Pass: Midpoint moved -> requote ({reason})")

    # Test 5: Our bid is through the market (dangerous)
    quoter.state = QuoteState(
        bid_order_id="bid123",
        ask_order_id="ask123",
        bid_price=48,
        ask_price=53,
        last_midpoint=50.0
    )
    should, reason = quoter.should_requote(best_bid=46, best_ask=55)
    # Our bid at 48 > best_bid 46 -> through market
    assert should, f"Should requote when bid through market"
    assert "through" in reason.lower() or "bid" in reason.lower()
    print(f"  Pass: Bid through market -> requote ({reason})")

    # Test 6: Our ask is through the market (dangerous)
    quoter.state = QuoteState(
        bid_order_id="bid123",
        ask_order_id="ask123",
        bid_price=43,  # Safe: below best_bid of 45
        ask_price=52,  # Dangerous: below best_ask of 54
        last_midpoint=50.0
    )
    should, reason = quoter.should_requote(best_bid=45, best_ask=54)
    # Our ask at 52 < best_ask 54 -> through market
    assert should, f"Should requote when ask through market"
    assert "ask" in reason.lower(), f"Reason should mention ask, got: {reason}"
    print(f"  Pass: Ask through market -> requote ({reason})")

    # Test 7: Partial quote (only bid) - not both active
    quoter.state = QuoteState(
        bid_order_id="bid123",
        ask_order_id=None,
        bid_price=47,
        ask_price=None,
        last_midpoint=50.0
    )
    should, reason = quoter.should_requote(best_bid=45, best_ask=55)
    assert should, f"Should requote when not both quotes active"
    print(f"  Pass: Partial quote -> requote ({reason})")

    print("  [UNIT] All requote logic tests passed!")
    return True


# ============================================================================
# INTEGRATION TESTS (with live API)
# ============================================================================

async def run_quoter_tests(bot, bid_price: int, ask_price: int, nonstop: bool = False):
    """
    Interactive quoter tests using live API.

    Args:
        bot: Initialized MarketMakerBot
        bid_price: Safe passive bid price (well below market)
        ask_price: Safe passive ask price (well above market)
        nonstop: Run without pausing

    Tests:
        1. Unit tests (no network)
        2. Place quotes at safe prices
        3. Verify quotes are active
        4. Check requote logic
        5. Update quotes
        6. Cancel all quotes
        7. Verify clean state
    """
    demo = DemoRunner("QUOTER TESTS", nonstop=nonstop)
    demo.header()

    # ---- Unit tests first (no network) ----
    demo.show("Running unit tests...")

    passed = test_quote_calculation()
    if not passed:
        demo.footer(passed=False)
        return False

    passed = test_requote_logic()
    if not passed:
        demo.footer(passed=False)
        return False

    passed = await test_fill_callback()
    if not passed:
        demo.footer(passed=False)
        return False

    demo.show("\nUnit tests passed! Starting integration tests...\n")

    # ---- Integration tests ----
    quoter = Quoter(bot)

    # Test: Get market state
    market = await demo.step(
        "Fetch market data",
        bot.get_market
    )
    demo.show(f"Market: {market['yes_bid']}/{market['yes_ask']}c")

    # Test: Calculate quotes (no order placement)
    calc_bid, calc_ask = quoter.calculate_quotes(
        best_bid=market['yes_bid'],
        best_ask=market['yes_ask']
    )
    demo.show(f"Calculated quotes: {calc_bid}/{calc_ask}c")

    # Test: Place quotes at SAFE prices (from CLI args)
    demo.show(f"\nUsing safe test prices: bid={bid_price}c, ask={ask_price}c")

    # Override calculate_quotes temporarily by placing at safe prices
    async def place_safe_quotes():
        # We'll place at safe prices to avoid fills
        quoter.state = QuoteState()  # Reset state

        bid_order_id = await bot.place_order(
            action="buy",
            side="yes",
            count=1,
            price_cents=bid_price,
            ticker=quoter.ticker
        )

        ask_order_id = await bot.place_order(
            action="sell",
            side="yes",
            count=1,
            price_cents=ask_price,
            ticker=quoter.ticker
        )

        # Manually set state to track these orders
        # Use market midpoint (not quote midpoint) for requote tracking
        market_midpoint = (market['yes_bid'] + market['yes_ask']) / 2
        quoter.state = QuoteState(
            bid_order_id=bid_order_id,
            ask_order_id=ask_order_id,
            bid_price=bid_price,
            ask_price=ask_price,
            last_midpoint=market_midpoint
        )

        return bid_order_id, ask_order_id

    bid_id, ask_id = await demo.step(
        f"Place safe quotes: bid={bid_price}c, ask={ask_price}c, size=1",
        place_safe_quotes
    )
    demo.show(f"Bid order: {bid_id}")
    demo.show(f"Ask order: {ask_id}")

    # Test: Verify state
    state = quoter.get_state_summary()
    demo.show(f"\nQuote state: has_active={state['has_active_quotes']}")
    demo.show(f"  bid: {state['bid_price']}c (order: {state['bid_order_id'][:12] if state['bid_order_id'] else 'None'}...)")
    demo.show(f"  ask: {state['ask_price']}c (order: {state['ask_order_id'][:12] if state['ask_order_id'] else 'None'}...)")

    # Test: Check if API shows our orders
    orders = await demo.step(
        "Verify orders via API",
        bot.get_open_orders
    )
    demo.show(f"Found {len(orders)} open order(s)")
    our_order_ids = {bid_id, ask_id}
    api_order_ids = {o['order_id'] for o in orders}
    orders_match = our_order_ids.issubset(api_order_ids)
    demo.show(f"Our orders in API: {orders_match}")

    # Test: should_requote with stable market (same prices)
    should, reason = quoter.should_requote(best_bid=bid_price, best_ask=ask_price)
    demo.show(f"\nShould requote (stable): {should} - {reason}")

    # Test: should_requote with market move
    shifted_bid = bid_price + 5
    shifted_ask = ask_price + 5
    should_shift, reason_shift = quoter.should_requote(best_bid=shifted_bid, best_ask=shifted_ask)
    demo.show(f"Should requote (market shifted +5c): {should_shift} - {reason_shift}")

    # Test: Cancel quotes
    canceled = await demo.step(
        "Cancel all quotes",
        quoter.cancel_quotes
    )
    demo.show(f"Canceled {canceled} order(s)")

    # Test: Verify clean state
    orders = await demo.step(
        "Verify orders canceled",
        bot.get_open_orders
    )
    demo.show(f"Remaining orders: {len(orders)}")

    # Test: Verify quoter state cleared
    state = quoter.get_state_summary()
    demo.show(f"Quote state cleared: has_active={state['has_active_quotes']}")

    # Test: cancel_quotes when no quotes (should not error)
    canceled_empty = await demo.step(
        "Cancel quotes (no active quotes - should be safe)",
        quoter.cancel_quotes
    )
    demo.show(f"Canceled {canceled_empty} order(s) from empty state")

    passed = len(orders) == 0 and not state['has_active_quotes']
    demo.footer(passed)
    return passed
