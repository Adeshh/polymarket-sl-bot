"""Telegram notification service."""

from __future__ import annotations

import os
from typing import Optional

import requests

from bot.config import load_config
from bot.logger import get_logger

logger = get_logger()

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(message: str) -> bool:
    """
    Send a Telegram notification.

    Returns True if successful, False otherwise.
    Fails silently if Telegram is not configured or disabled.
    """
    config = load_config()
    telegram_config = config.get("telegram", {})

    if not telegram_config.get("enabled", True):
        logger.debug("Telegram notifications disabled")
        return False

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.debug("Telegram not configured, skipping notification")
        return False

    try:
        url = TELEGRAM_API_URL.format(token=token)
        payload = {
            "chat_id": int(chat_id),  # Ensure chat_id is an integer
            "text": message,
            "parse_mode": "HTML",
        }

        response = requests.post(url, json=payload, timeout=10)

        if not response.ok:
            logger.error(f"Telegram API error: {response.text}")
            return False

        logger.debug(f"Telegram notification sent: {message[:50]}...")
        return True

    except requests.RequestException as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False
    except ValueError as e:
        logger.error(f"Invalid TELEGRAM_CHAT_ID format: {e}")
        return False


def notify_start(stop_loss_pct: float) -> None:
    """Send bot startup notification."""
    config = load_config()
    if config.get("telegram", {}).get("notify_on_start", True):
        send_telegram(f"Polymarket SL Bot started. Monitoring for {stop_loss_pct}% stop-loss.")


def notify_stop_loss(
    market_title: str,
    outcome: str,
    entry_price: float,
    exit_price: float,
    loss_pct: float,
    shares: float,
    order_id: Optional[str] = None,
    success: bool = True,
) -> None:
    """Send stop-loss execution notification."""
    config = load_config()
    if config.get("telegram", {}).get("notify_on_stop_loss", True):
        status_emoji = "✅" if success else "❌"
        status_text = "EXECUTED" if success else "FAILED"

        msg = (
            f"<b>{status_emoji} STOP-LOSS {status_text}</b>\n\n"
            f"<b>Market:</b> {market_title}\n"
            f"<b>Outcome:</b> {outcome}\n"
            f"<b>Entry Price:</b> ${entry_price:.4f}\n"
            f"<b>Exit Price:</b> ${exit_price:.4f}\n"
            f"<b>Loss:</b> -{loss_pct:.2f}%\n"
            f"<b>Shares Sold:</b> {shares:.2f}\n"
        )

        if order_id:
            msg += f"<b>Order ID:</b> <code>{order_id}</code>"
        elif not success:
            msg += "<b>Note:</b> Order may need manual intervention"

        send_telegram(msg)


def notify_position_closed(
    title: str,
    outcome: str,
    entry_price: float,
    last_price: float,
    size: float,
    reason: str = "Position Closed",
) -> None:
    """Send notification when a tracked position closes (win/loss/manual)."""
    config = load_config()
    if not config.get("telegram", {}).get("enabled", True):
        return

    # Calculate P/L
    if entry_price > 0:
        pnl_pct = ((last_price - entry_price) / entry_price) * 100
    else:
        pnl_pct = 0.0

    # Determine if it was a win or loss
    if last_price >= 1.0:
        status_emoji = "🎉"
        result = "WON"
    elif last_price <= 0.0:
        status_emoji = "📉"
        result = "LOST"
    elif pnl_pct >= 0:
        status_emoji = "✅"
        result = "PROFIT"
    else:
        status_emoji = "📊"
        result = "CLOSED"

    pnl_sign = "+" if pnl_pct >= 0 else ""

    msg = (
        f"<b>{status_emoji} POSITION {result}</b>\n\n"
        f"<b>Market:</b> {title}\n"
        f"<b>Outcome:</b> {outcome}\n"
        f"<b>Entry Price:</b> ${entry_price:.4f}\n"
        f"<b>Final Price:</b> ${last_price:.4f}\n"
        f"<b>P/L:</b> {pnl_sign}{pnl_pct:.2f}%\n"
        f"<b>Shares:</b> {size:.2f}\n"
        f"<b>Reason:</b> {reason}"
    )

    send_telegram(msg)


def notify_error(error_message: str) -> None:
    """Send error notification."""
    config = load_config()
    if config.get("telegram", {}).get("notify_on_error", True):
        send_telegram(f"<b>Bot Error:</b> {error_message}")
