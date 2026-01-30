"""
Configuration and global settings for Kalshi Market Maker Bot
"""

# ============================================================================
# MARKET SELECTION
# ============================================================================

# Specific market ticker to trade
MARKET_TICKER = "KXHIGHTSFO-26JAN30-B63.5"

# ============================================================================
# MARKET MAKER PARAMETERS
# ============================================================================

# Maximum position size per market (number of contracts)
MAX_POSITION_SIZE = 30

# Maximum total exposure across all markets (in dollars)
MAX_TOTAL_EXPOSURE = 5

# ============================================================================
# QUOTER PARAMETERS
# ============================================================================

# Total spread width in cents (our bid at mid - SPREAD_WIDTH/2, ask at mid + SPREAD_WIDTH/2)
SPREAD_WIDTH = 4

# Number of contracts per quote side
QUOTE_SIZE = 1

# Requote when midpoint moves by this many cents
REQUOTE_THRESHOLD = 1

# Cents to skew quotes per contract of inventory
# Positive inventory (long YES) -> positive skew -> lower bid/ask to encourage selling
INVENTORY_SKEW_PER_CONTRACT = 1

# ============================================================================
# LOOP CONTROL
# ============================================================================

# How long to wait between loop iterations (seconds)
LOOP_INTERVAL = 5

# Maximum runtime (seconds) - for testing
MAX_RUNTIME = 1000

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

# ============================================================================
# KILL SWITCH SETTINGS
# ============================================================================

# Cancel all orders after this many consecutive API errors
KILL_SWITCH_ERROR_THRESHOLD = 3

# Cancel all orders if a single fill exceeds this many contracts
KILL_SWITCH_LARGE_FILL_THRESHOLD = 5

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Directory for log files (relative to project root)
LOG_DIR = "logs"

# Log file name
LOG_FILE = "trading.log"

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL = "INFO"

# Max log file size before rotation (5 MB)
LOG_MAX_BYTES = 5 * 1024 * 1024

# Number of backup log files to keep
LOG_BACKUP_COUNT = 5