"""Database operations for trade history using Turso HTTP API."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, List, Optional

import requests

from bot.config import get_env
from bot.logger import get_logger

logger = get_logger()

_initialized = False


def _get_db_url() -> str:
    """Get the HTTP API URL from the libsql URL."""
    db_url = get_env("TURSO_DATABASE_URL")
    # Convert libsql:// to https://
    if db_url.startswith("libsql://"):
        db_url = db_url.replace("libsql://", "https://")
    return db_url


def _execute(sql: str, args: Optional[List] = None) -> dict:
    """Execute a SQL statement via Turso HTTP API."""
    db_url = _get_db_url()
    auth_token = get_env("TURSO_AUTH_TOKEN")

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }

    # Build request body for Turso HTTP API
    # Format: {"statements": [{"q": "...", "params": [...]}]}
    statement = {"q": sql}
    if args:
        # Params are simple values (strings, numbers, or null)
        statement["params"] = [str(v) if v is not None else None for v in args]

    body = {
        "statements": [statement]
    }

    response = requests.post(
        db_url,
        json=body,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def init_tables() -> None:
    """Initialize database tables."""
    global _initialized

    if _initialized:
        return

    sql = """
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            market_title TEXT NOT NULL,
            token_id TEXT NOT NULL,
            outcome TEXT,
            action TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            shares REAL NOT NULL,
            loss_percentage REAL NOT NULL,
            order_id TEXT,
            status TEXT
        )
    """

    try:
        _execute(sql)
        _initialized = True
        logger.debug("Database tables initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def log_trade(
    market_title: str,
    token_id: str,
    outcome: Optional[str],
    action: str,
    entry_price: float,
    exit_price: float,
    shares: float,
    loss_percentage: float,
    order_id: Optional[str],
    status: str,
) -> Optional[int]:
    """Log a trade to the database."""
    init_tables()

    sql = """
        INSERT INTO trade_history
        (timestamp, market_title, token_id, outcome, action, entry_price,
         exit_price, shares, loss_percentage, order_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    args = [
        datetime.utcnow().isoformat(),
        market_title,
        token_id,
        outcome,
        action,
        entry_price,
        exit_price,
        shares,
        loss_percentage,
        order_id,
        status,
    ]

    try:
        result = _execute(sql, args)
        logger.info(f"Trade logged to database: action={action}, status={status}")
        # Response is a list of results
        if result and len(result) > 0:
            return result[0].get("results", {}).get("last_insert_rowid")
        return None
    except Exception as e:
        logger.error(f"Failed to log trade to database: {e}")
        return None


def get_trade_history(limit: int = 100) -> List[dict]:
    """Retrieve recent trade history."""
    init_tables()

    sql = f"""
        SELECT * FROM trade_history
        ORDER BY timestamp DESC
        LIMIT {limit}
    """

    try:
        result = _execute(sql)

        # Response is a list: [{"results": {"columns": [...], "rows": [...]}}]
        if not result or len(result) == 0:
            return []

        results = result[0].get("results", {})
        columns = results.get("columns", [])
        rows = results.get("rows", [])

        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get trade history: {e}")
        return []
