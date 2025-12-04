"""
Main entry point
"""

import asyncio
from src.market_maker import main

if __name__ == "__main__":
    print("BEGIN")
    print()
    asyncio.run(main())