"""
Logging configuration for the Kalshi Market Maker.

Provides centralized logging setup with:
- Console output for real-time monitoring
- Rotating file logging for post-mortem analysis
- Custom formatter: HH:MM:SS | message
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config


class TradingFormatter(logging.Formatter):
    """Custom formatter for trading logs: HH:MM:SS | message"""

    def format(self, record: logging.LogRecord) -> str:
        # Format timestamp as HH:MM:SS
        timestamp = self.formatTime(record, "%H:%M:%S")
        return f"{timestamp} | {record.getMessage()}"


def setup_logging() -> None:
    """
    Configure logging for the trading application.

    Sets up:
    - Console handler with trading formatter
    - Rotating file handler for persistent logs
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(config.LOG_DIR)
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / config.LOG_FILE
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    # Create formatter
    formatter = TradingFormatter()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

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

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.info(f"Logging initialized - level={config.LOG_LEVEL}, file={log_file}")
