"""Position fetching from Polymarket Data API."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import requests

from bot.config import get_env, load_config
from bot.logger import get_logger

logger = get_logger()

DATA_API_URL = "https://data-api.polymarket.com/positions"


def get_positions() -> List[Dict[str, Any]]:
    """
    Fetch current positions from Polymarket Data API.

    Returns:
        List of position dictionaries with keys:
        - asset (token_id)
        - avgPrice (entry price)
        - curPrice (current price)
        - size (number of shares)
        - title (market name)
        - outcome (YES/NO)
        - currentValue, initialValue, cashPnl, percentPnl, etc.
    """
    config = load_config()
    min_size = config["stop_loss"]["min_position_size"]

    funder_address = get_env("POLYMARKET_FUNDER_ADDRESS")

    params = {
        "user": funder_address,
        "sizeThreshold": min_size,
        "sortBy": "TOKENS",
        "sortDirection": "DESC",
        "limit": 10,
    }

    logger.debug(f"Fetching positions for {funder_address}")

    response = requests.get(DATA_API_URL, params=params, timeout=30)
    response.raise_for_status()

    positions = response.json()

    logger.debug(f"Found {len(positions)} positions")

    return positions


def calculate_stop_loss_trigger(
    entry_price: float,
    current_price: float,
    stop_loss_pct: float,
) -> Tuple[bool, float]:
    """
    Calculate if stop-loss should trigger.

    Args:
        entry_price: Average price paid for position (avgPrice from API)
        current_price: Current market price (curPrice from API)
        stop_loss_pct: Configured stop-loss percentage (e.g., 10.0 for 10%)

    Returns:
        Tuple of (should_trigger: bool, price_drop_percentage: float)

    Example:
        entry_price = 0.65 (bought at 65 cents)
        current_price = 0.55 (now at 55 cents)
        stop_loss_pct = 10.0

        price_drop = (0.65 - 0.55) / 0.65 * 100 = 15.38%
        15.38% >= 10% -> TRIGGER
    """
    if entry_price <= 0:
        return False, 0.0

    price_drop_pct = ((entry_price - current_price) / entry_price) * 100
    should_trigger = price_drop_pct >= stop_loss_pct

    return should_trigger, price_drop_pct
