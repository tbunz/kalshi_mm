"""
Main Entry Point
"""

import time
from datetime import datetime, timedelta
from KalshiClientsBaseV2 import ExchangeClient

import config


class MarketMakerBot:
    def __init__(self):
        """Initialize the market maker bot"""
        self.client = None
        self.start_time = None
        self.running = False
        
    def initialize(self):
        """Set up API client and perform initial checks"""
        print("=" * 60)
        print("Kalshi Market Maker Bot - Initializing")
        print("=" * 60)
        
        # Initialize API client (public only for now)
        self.client = ExchangeClient(
            exchange_api_base=config.API_BASE_URL,
            key_id="",  # Empty for public endpoints
        )
        
        print(f"Target Series: {config.SERIES_TICKER}")
        print(f"Target Spread: {config.TARGET_SPREAD} cents")
        print(f"Loop Interval: {config.LOOP_INTERVAL} seconds")
        print(f"Max Runtime: {config.MAX_RUNTIME} seconds")
        print()
        
        self.start_time = time.time()
        self.running = True
        
    def should_continue(self):
        """Check if bot should keep running"""
        elapsed = time.time() - self.start_time
        
        if elapsed > config.MAX_RUNTIME:
            print(f"\nMax runtime ({config.MAX_RUNTIME}s) reached. Stopping.")
            return False
            
        return True
        
    def get_markets(self):
        """Fetch markets in the target series"""
        # TODO: Implement market fetching
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching markets for {config.SERIES_TICKER}...")
        pass
        
    def filter_markets(self, markets):
        """Filter markets based on our criteria (liquidity, time to close, etc.)"""
        # TODO: Implement market filtering
        pass
        
    def get_market_data(self, market_ticker):
        """Get current orderbook and market data"""
        # TODO: Implement data fetching
        pass
        
    def calculate_fair_value(self, market_data):
        """Calculate our fair value estimate for the market"""
        # TODO: Implement pricing logic (for now, just use midpoint)
        pass
        
    def manage_orders(self, market_ticker, fair_value):
        """Place/cancel orders to maintain our spread around fair value"""
        # TODO: Implement order management
        pass
        
    def run(self):
        """Main bot loop"""
        print("Starting main loop...")
        print("-" * 60)
        
        loop_count = 0
        
        try:
            while self.running and self.should_continue():
                loop_count += 1
                print(f"\n=== Loop Iteration {loop_count} ===")
                
                # Step 1: Get markets in our series
                markets = self.get_markets()
                
                # Step 2: Filter to tradeable markets
                # tradeable_markets = self.filter_markets(markets)
                
                # Step 3: For each market, get data and manage orders
                # for market in tradeable_markets:
                #     market_data = self.get_market_data(market)
                #     fair_value = self.calculate_fair_value(market_data)
                #     self.manage_orders(market, fair_value)
                
                # Step 4: Wait before next iteration
                print(f"Sleeping for {config.LOOP_INTERVAL} seconds...")
                time.sleep(config.LOOP_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n\nBot stopped by user (Ctrl+C)")
        except Exception as e:
            print(f"\n\nError in main loop: {e}")
            raise
        finally:
            self.shutdown()
            
    def shutdown(self):
        """Clean up and shut down gracefully"""
        print("\n" + "=" * 60)
        print("Shutting down bot...")
        
        # TODO: Cancel all open orders
        # TODO: Print summary (P&L, trades made, etc.)
        
        elapsed = time.time() - self.start_time
        print(f"Total runtime: {elapsed:.1f} seconds")
        print("=" * 60)


def main():
    """Entry point"""
    bot = MarketMakerBot()
    bot.initialize()
    bot.run()


if __name__ == "__main__":
    main()