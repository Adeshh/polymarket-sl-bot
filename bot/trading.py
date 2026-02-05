"""Trading operations using Polymarket CLOB client."""

from __future__ import annotations

from typing import Any, Dict, Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL

from bot.config import get_env
from bot.logger import get_logger

logger = get_logger()

CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon mainnet

_clob_client: Optional[ClobClient] = None


def get_clob_client(force_new: bool = False, signature_type: int = 2) -> ClobClient:
    """Initialize and return CLOB client with credentials."""
    global _clob_client

    if _clob_client is not None and not force_new:
        return _clob_client

    private_key = get_env("POLYMARKET_WALLET_PRIVATE_KEY")
    funder = get_env("POLYMARKET_FUNDER_ADDRESS")

    # Strip 0x prefix if present (some versions require it without)
    if private_key.startswith("0x"):
        private_key_clean = private_key[2:]
    else:
        private_key_clean = private_key

    # signature_type: 0=EOA, 1=POLY_PROXY, 2=POLY_GNOSIS_SAFE
    sig_type_names = {0: "EOA", 1: "POLY_PROXY", 2: "POLY_GNOSIS_SAFE"}
    logger.info(f"Deriving API credentials with signature_type={signature_type} ({sig_type_names.get(signature_type, 'unknown')})...")

    client = ClobClient(
        CLOB_HOST,
        key=private_key_clean,
        chain_id=CHAIN_ID,
        signature_type=signature_type,
        funder=funder,
    )
    client.set_api_creds(client.create_or_derive_api_creds())
    logger.info("API credentials derived successfully")

    _clob_client = client
    return client


def close_position(token_id: str, size: float, signature_type: int = 2) -> Dict[str, Any]:
    """
    Close a position by selling all shares at market price.

    Args:
        token_id: The asset/token ID from the position
        size: Number of shares to sell
        signature_type: Signature type to use (0=EOA, 1=POLY_PROXY, 2=POLY_GNOSIS_SAFE)

    Returns:
        API response from order submission
    """
    logger.info(f"Closing position: token={token_id}, size={size}, sig_type={signature_type}")

    # Get client with specified signature type
    client = get_clob_client(force_new=True, signature_type=signature_type)

    # Round size to 2 decimal places for FOK orders (known py-clob-client issue)
    rounded_size = round(size, 2)

    if rounded_size <= 0:
        logger.warning("Position size too small to close")
        return {"success": False, "error": "Size too small"}

    order_args = MarketOrderArgs(
        token_id=token_id,
        amount=rounded_size,
        side=SELL,
    )

    logger.debug(f"Creating market sell order: token={token_id}, amount={rounded_size}")

    try:
        signed_order = client.create_market_order(order_args)
        logger.debug("Posting FOK order...")
        response = client.post_order(signed_order, orderType=OrderType.FOK)
        logger.info(f"Order response: {response}")
        return response

    except Exception as e:
        error_msg = str(e)

        # Handle no orderbook
        if "No orderbook exists" in error_msg or "404" in error_msg:
            logger.error("Market has no active orderbook - cannot close position")
            return {"success": False, "error": "No active orderbook for this market"}

        # Handle signature errors - try different signature types
        if "invalid signature" in error_msg.lower():
            if signature_type == 1:
                logger.warning("Signature failed with POLY_PROXY, trying EOA (signature_type=0)...")
                return close_position(token_id, size, signature_type=0)
            elif signature_type == 0:
                logger.warning("Signature failed with EOA, trying POLY_GNOSIS_SAFE (signature_type=2)...")
                return close_position(token_id, size, signature_type=2)
            else:
                logger.error(f"All signature types failed: {error_msg}")
                return {"success": False, "error": f"Signature failed: {error_msg}"}

        # Handle auth errors
        if "401" in error_msg or "Unauthorized" in error_msg or "Invalid api key" in error_msg:
            logger.error(f"Auth failed: {error_msg}")
            return {"success": False, "error": f"Authentication failed: {error_msg}"}

        raise
