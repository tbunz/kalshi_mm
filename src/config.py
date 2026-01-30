"""
Configuration and global settings for Kalshi Market Maker Bot
"""

# ============================================================================
# MARKET SELECTION
# ============================================================================

# Specific market ticker to trade
MARKET_TICKER = "KXHIGHTSFO-26JAN29-B63.5"

# ============================================================================
# MARKET MAKER PARAMETERS
# ============================================================================

# Spread to maintain (in cents) - distance from fair value to your bid/ask
TARGET_SPREAD = 2  # Quote 2 cents away from midpoint on each side

# Maximum position size per market (number of contracts)
MAX_POSITION_SIZE = 10

# Maximum total exposure across all markets (in dollars)
MAX_TOTAL_EXPOSURE = 10

# ============================================================================
# LOOP CONTROL
# ============================================================================

# How long to wait between loop iterations (seconds)
LOOP_INTERVAL = 5

# Maximum runtime (seconds) - for testing
MAX_RUNTIME = 1800  # 30 minutes

# ============================================================================
# API CONFIGURATION
# ============================================================================

# API base URL (domain only, path added by client)
API_BASE_URL = "https://api.elections.kalshi.com"

# Whether to use demo/paper trading mode
USE_DEMO_MODE = True

# ============================================================================
# RISK MANAGEMENT
# ============================================================================

# Minimum liquidity required (contracts on each side of book)
MIN_LIQUIDITY = 5

# Don't trade markets closing within this many minutes
MIN_MINUTES_TO_CLOSE = 30

# Maximum loss threshold to stop trading (dollars)
MAX_LOSS_THRESHOLD = 1