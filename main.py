"""
Main entry point for Kalshi Market Maker
"""
import sys
import asyncio


def run_ui():
    """Run the terminal UI"""
    from src.ui.app import MarketMakerApp
    app = MarketMakerApp()
    app.run()


def run_demo(nonstop: bool = False):
    """Run the demo/test mode (no UI)"""
    from src.market_maker import main
    asyncio.run(main(nonstop=nonstop))


if __name__ == "__main__":
    if "--demo" in sys.argv:
        nonstop = "--nonstop" in sys.argv
        print(f"Running in demo mode (nonstop={nonstop})...")
        run_demo(nonstop=nonstop)
    else:
        run_ui()
