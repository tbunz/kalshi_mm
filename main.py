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


def run_demo():
    """Run the demo/test mode (no UI)"""
    from src.market_maker import main
    asyncio.run(main())


if __name__ == "__main__":
    if "--demo" in sys.argv:
        print("Running in demo mode (no UI)...")
        run_demo()
    else:
        run_ui()
