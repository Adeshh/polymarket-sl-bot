#!/usr/bin/env python3
"""
Polymarket Stop-Loss Monitoring Bot

Monitors a single position opened via Polymarket UI and automatically
closes it at market value when the stop-loss threshold is triggered.
"""

import sys

from bot.logger import get_logger
from bot.monitor import run_monitor


def main() -> None:
    """Entry point for the bot."""
    logger = get_logger()

    try:
        logger.info("=" * 50)
        logger.info("Polymarket Stop-Loss Bot Starting")
        logger.info("=" * 50)
        run_monitor()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
