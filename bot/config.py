"""Configuration loader for the Polymarket Stop-Loss Bot."""

from __future__ import annotations

import os
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()

_config_cache: dict[str, Any] = {}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """Load configuration from YAML file with environment variable overrides."""
    global _config_cache

    if _config_cache:
        return _config_cache

    # Default config
    config = {
        "stop_loss": {
            "percentage": 10.0,
            "min_position_size": 1.0,
        },
        "monitoring": {
            "position_poll_interval_ms": 30000,
            "price_poll_interval_ms": 5000,
        },
        "telegram": {
            "enabled": True,
            "notify_on_start": True,
            "notify_on_stop_loss": True,
            "notify_on_error": True,
        },
        "logging": {
            "level": "INFO",
            "file": "logs/bot.log",
            "max_size_mb": 10,
            "backup_count": 5,
        },
    }

    # Load from YAML if exists
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f) or {}
            config = deep_merge(config, yaml_config)

    # Environment variable overrides
    if os.getenv("POSITION_POLL_INTERVAL_MS"):
        config["monitoring"]["position_poll_interval_ms"] = int(
            os.getenv("POSITION_POLL_INTERVAL_MS")
        )
    if os.getenv("PRICE_POLL_INTERVAL_MS"):
        config["monitoring"]["price_poll_interval_ms"] = int(
            os.getenv("PRICE_POLL_INTERVAL_MS")
        )

    _config_cache = config
    return config


def get_env(key: str, required: bool = True) -> Optional[str]:
    """Get environment variable with optional requirement check."""
    value = os.getenv(key)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value
