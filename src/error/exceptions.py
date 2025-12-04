class MarketMakerError(Exception):
    """Base exception for all market maker errors"""
    pass

# API/Client Errors
class APIError(MarketMakerError):
    """Base class for API-related errors"""
    pass

class AuthenticationError(APIError):
    """Failed to authenticate with Kalshi"""
    pass

class RateLimitError(APIError):
    """Hit API rate limit"""
    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after: {retry_after}s")