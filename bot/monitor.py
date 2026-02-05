"""Main monitoring loop for stop-loss detection."""

from __future__ import annotations

import time
from typing import Optional, Dict, Any
from requests.exceptions import RequestException, Timeout

from bot.config import load_config
from bot.database import log_trade, init_tables
from bot.logger import get_logger
from bot.notifications import (
    notify_error,
    notify_position_closed,
    notify_start,
    notify_stop_loss,
    send_telegram,
)
from bot.position import calculate_stop_loss_trigger, get_positions
from bot.trading import close_position

logger = get_logger()

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds


def notify_new_position(
    title: str,
    outcome: str,
    entry_price: float,
    size: float,
    stop_loss_pct: float,
) -> None:
    """Send notification when a new position is detected."""
    sl_price = entry_price * (1 - stop_loss_pct / 100)
    msg = (
        f"<b>NEW POSITION DETECTED</b>\n\n"
        f"Market: {title}\n"
        f"Outcome: {outcome}\n"
        f"Entry: {entry_price:.4f}\n"
        f"Size: {size:.2f} shares\n"
        f"Stop-Loss: {stop_loss_pct}% (triggers at {sl_price:.4f})"
    )
    send_telegram(msg)


def run_monitor() -> None:
    """Run the main monitoring loop."""
    config = load_config()
    stop_loss_pct = config["stop_loss"]["percentage"]
    poll_interval = config["monitoring"]["position_poll_interval_ms"] / 1000

    # Initialize database on startup
    logger.info("=" * 60)
    logger.info("POLYMARKET STOP-LOSS BOT")
    logger.info("=" * 60)
    logger.info(f"Stop-Loss Threshold: {stop_loss_pct}%")
    logger.info(f"Poll Interval: {poll_interval} seconds")

    try:
        init_tables()
        logger.info("Database: Connected successfully")
    except Exception as e:
        logger.warning(f"Database: Connection failed - {e}")
        logger.warning("Continuing without database logging...")

    logger.info("=" * 60)
    notify_start(stop_loss_pct)

    consecutive_errors = 0
    current_position_id: Optional[str] = None  # Track current position
    # Store position details for notification when position closes
    tracked_position: Dict[str, Any] = {}

    while True:
        try:
            positions = get_positions()

            if not positions:
                if current_position_id is not None:
                    logger.info("=" * 60)
                    logger.info("POSITION CLOSED")
                    logger.info("=" * 60)
                    # Send notification about position closure
                    if tracked_position:
                        notify_position_closed(
                            title=tracked_position.get("title", "Unknown"),
                            outcome=tracked_position.get("outcome", ""),
                            entry_price=tracked_position.get("entry_price", 0),
                            last_price=tracked_position.get("last_price", 0),
                            size=tracked_position.get("size", 0),
                        )
                    current_position_id = None
                    tracked_position = {}
                logger.info("Waiting for positions...")
                time.sleep(poll_interval)
                consecutive_errors = 0
                continue

            # Find the first active position (with valid current price)
            active_pos = None
            for pos in positions:
                cur_price = float(pos.get("curPrice", 0))
                entry = float(pos.get("avgPrice", 0))
                if cur_price > 0 and entry > 0:
                    active_pos = pos
                    break

            if active_pos is None:
                # Market resolved - position no longer has valid prices
                if current_position_id is not None:
                    logger.info("=" * 60)
                    logger.info("MARKET RESOLVED - Position closed")
                    logger.info("=" * 60)
                    if tracked_position:
                        notify_position_closed(
                            title=tracked_position.get("title", "Unknown"),
                            outcome=tracked_position.get("outcome", ""),
                            entry_price=tracked_position.get("entry_price", 0),
                            last_price=tracked_position.get("last_price", 0),
                            size=tracked_position.get("size", 0),
                            reason="Market Resolved",
                        )
                    current_position_id = None
                    tracked_position = {}
                else:
                    logger.info("No active positions with valid prices (markets may be resolved)")
                time.sleep(poll_interval)
                continue

            pos = active_pos
            entry_price = float(pos.get("avgPrice", 0))
            current_price = float(pos.get("curPrice", 0))
            size = float(pos.get("size", 0))
            token_id = pos.get("asset", "")
            title = pos.get("title", "Unknown Market")
            outcome = pos.get("outcome", "")

            # Update tracked position details (for notifications on close)
            tracked_position = {
                "title": title,
                "outcome": outcome,
                "entry_price": entry_price,
                "last_price": current_price,
                "size": size,
                "token_id": token_id,
            }

            # Check if this is a new position
            if token_id != current_position_id:
                logger.info("=" * 60)
                logger.info("NEW POSITION DETECTED!")
                logger.info(f"Market: {title}")
                logger.info(f"Outcome: {outcome}")
                logger.info(f"Entry Price: {entry_price:.4f}")
                logger.info(f"Position Size: {size:.2f} shares")
                sl_trigger_price = entry_price * (1 - stop_loss_pct / 100)
                logger.info(f"Stop-Loss will trigger at: {sl_trigger_price:.4f} ({stop_loss_pct}% drop)")
                logger.info("=" * 60)

                # Send Telegram notification for new position
                notify_new_position(title, outcome, entry_price, size, stop_loss_pct)
                current_position_id = token_id

            should_trigger, price_drop_pct = calculate_stop_loss_trigger(
                entry_price, current_price, stop_loss_pct
            )

            # Determine status emoji/indicator
            if price_drop_pct >= stop_loss_pct:
                status_indicator = "STOP-LOSS HIT!"
            elif price_drop_pct > 0:
                status_indicator = "IN LOSS"
            else:
                status_indicator = "IN PROFIT"

            logger.info(
                f"[{status_indicator}] {title[:35]} | "
                f"{outcome} | "
                f"Entry: {entry_price:.4f} | "
                f"Now: {current_price:.4f} | "
                f"P/L: {-price_drop_pct:.2f}%"
            )

            if should_trigger:
                logger.warning("=" * 60)
                logger.warning(f"STOP-LOSS TRIGGERED!")
                logger.warning(f"Price dropped {price_drop_pct:.2f}% (threshold: {stop_loss_pct}%)")
                logger.warning(f"Closing position: {size:.2f} shares at market price")
                logger.warning("=" * 60)

                result = close_position(token_id, size)

                order_id = result.get("orderID") or result.get("order_id")
                # Check success: orderID present means order was placed, or explicit success=False for errors
                if result.get("success") is False:
                    success = False
                else:
                    success = order_id is not None
                status = "SUCCESS" if success else "FAILED"

                logger.info(f"Order result: success={success}, order_id={order_id}, status={status}")

                # Log to database
                try:
                    trade_id = log_trade(
                        market_title=title,
                        token_id=token_id,
                        outcome=outcome,
                        action="STOP_LOSS",
                        entry_price=entry_price,
                        exit_price=current_price,
                        shares=size,
                        loss_percentage=price_drop_pct,
                        order_id=order_id,
                        status=status,
                    )
                    if trade_id:
                        logger.info(f"Trade logged to database (ID: {trade_id})")
                    else:
                        logger.warning("Trade logged but no ID returned")
                except Exception as e:
                    logger.error(f"Failed to log trade to database: {e}")

                # Send notification with order status
                notify_stop_loss(
                    market_title=title,
                    outcome=outcome,
                    entry_price=entry_price,
                    exit_price=current_price,
                    loss_pct=price_drop_pct,
                    shares=size,
                    order_id=order_id,
                    success=success,
                )

                if success:
                    logger.info("Position closed successfully!")
                    logger.info(f"Order ID: {order_id}")
                    current_position_id = None  # Reset so we detect next position
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Failed to close position: {error_msg}")
                    notify_error(f"Failed to close position: {error_msg}")

            consecutive_errors = 0
            time.sleep(poll_interval)

        except Timeout as e:
            consecutive_errors += 1
            logger.warning(f"Request timeout (attempt {consecutive_errors}): {e}")
            time.sleep(min(RETRY_DELAY * consecutive_errors, 60))

        except RequestException as e:
            consecutive_errors += 1
            logger.error(f"Network error (attempt {consecutive_errors}): {e}")
            if consecutive_errors >= MAX_RETRIES:
                notify_error(f"Network issues: {e}")
            time.sleep(min(RETRY_DELAY * consecutive_errors, 60))

        except KeyboardInterrupt:
            logger.info("=" * 60)
            logger.info("Bot stopped by user (Ctrl+C)")
            logger.info("=" * 60)
            send_telegram("Polymarket SL Bot stopped by user.")
            break

        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            notify_error(str(e))
            time.sleep(poll_interval)
