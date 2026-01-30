"""
Configuration and global settings for Kalshi Market Maker Bot
"""

# ============================================================================
# MARKET SELECTION
# ============================================================================

# Specific market ticker to trade
MARKET_TICKER = "KXPRESNOMD-28-GN"

# ============================================================================
# MARKET MAKER PARAMETERS
# ============================================================================

# Maximum position size per market (number of contracts)
MAX_POSITION_SIZE = 10

# Maximum total exposure across all markets (in dollars)
MAX_TOTAL_EXPOSURE = 10

# ============================================================================
# QUOTER PARAMETERS
# ============================================================================

# Total spread width in cents (our bid at mid - SPREAD_WIDTH/2, ask at mid + SPREAD_WIDTH/2)
SPREAD_WIDTH = 6

# Number of contracts per quote side
QUOTE_SIZE = 5

# Requote when midpoint moves by this many cents
REQUOTE_THRESHOLD = 2

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

# ============================================================================
# POSITION TRACKING
# ============================================================================

# How often to poll for new fills (seconds)
FILL_POLL_INTERVAL = 2

# Maximum fills to fetch per poll request
FILL_POLL_LIMIT = 50