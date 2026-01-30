"""
Logging configuration for the Kalshi Market Maker.

Provides centralized logging setup with:
- Console output for real-time monitoring
- Rotating file logging for post-mortem analysis
- UI handler for live display in the terminal UI
- Custom formatter: HH:MM:SS | message
"""
import logging
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict

from . import config


class UILogHandler(logging.Handler):
    """
    Custom logging handler that buffers messages for UI display.

    Thread-safe buffer that stores recent log records for the UI to consume.
    """

    _instance = None

    def __init__(self, max_records: int = 100):
        super().__init__()
        self._buffer: deque = deque(maxlen=max_records)
        UILogHandler._instance = self

    @classmethod
    def get_instance(cls) -> "UILogHandler":
        """Get the singleton instance of the UI log handler."""
        return cls._instance

    def emit(self, record: logging.LogRecord) -> None:
        """Store formatted log record in buffer."""
        try:
            msg = self.format(record)
            self._buffer.append({
                "time": self.formatter.formatTime(record, "%H:%M:%S") if self.formatter else "",
                "level": record.levelname,
                "message": record.getMessage(),
                "formatted": msg,
            })
        except Exception:
            self.handleError(record)

    def get_recent_logs(self, count: int = 10) -> List[Dict]:
        """Get the most recent log entries."""
        return list(self._buffer)[-count:]

    def clear(self) -> None:
        """Clear the log buffer."""
        self._buffer.clear()


class TradingFormatter(logging.Formatter):
    """Custom formatter for trading logs: HH:MM:SS | message"""

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp as HH:MM:SS
        timestamp = self.formatTime(record, "%H:%M:%S")
        return f"{timestamp} | {record.getMessage()}"


def setup_logging(use_console: bool = True) -> None:
    """
    Configure logging for the trading application.

    Sets up:
    - Console handler with trading formatter (optional, disable for UI mode)
    - Rotating file handler for persistent logs

    Args:
        use_console: If True, logs to stdout. Set to False when running with
                     the Textual UI to prevent log output corrupting the display.
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / config.LOG_FILE
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    # Create formatter
    formatter = TradingFormatter()

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Console handler (skip when UI is active to prevent display corruption)
    if use_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    root_logger.addHandler(file_handler)

    # UI handler for live display
    ui_handler = UILogHandler(max_records=100)
    ui_handler.setFormatter(formatter)
    ui_handler.setLevel(log_level)
    root_logger.addHandler(ui_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info(f"Logging initialized - level={config.LOG_LEVEL}, file={log_file}")
