"""
Main entry point for Kalshi Market Maker
"""
import sys
import asyncio

from src.logging_config import setup_logging


def run_ui():
    """Run the terminal UI"""
    from src.ui.app import MarketMakerApp
    app = MarketMakerApp()
    app.run()


def run_demo(bid_price: int, ask_price: int, nonstop: bool = False):
    """Run the demo/test mode (no UI)"""
    from src.market_maker import main
    asyncio.run(main(bid_price=bid_price, ask_price=ask_price, nonstop=nonstop))


if __name__ == "__main__":
    # Initialize logging before anything else
    setup_logging()

    if "--demo" in sys.argv:
        # Parse: python main.py --demo <bid> <ask> [--nonstop]
        demo_idx = sys.argv.index("--demo")
        try:
            bid_price = int(sys.argv[demo_idx + 1])
            ask_price = int(sys.argv[demo_idx + 2])
        except (IndexError, ValueError):
            print("Usage: python main.py --demo <bid_price> <ask_price> [--nonstop]")
            print("Example: python main.py --demo 10 90 --nonstop")
            sys.exit(1)

        nonstop = "--nonstop" in sys.argv
        print(f"Running in demo mode (bid={bid_price}, ask={ask_price}, nonstop={nonstop})...")
        run_demo(bid_price=bid_price, ask_price=ask_price, nonstop=nonstop)
    else:
        run_ui()
