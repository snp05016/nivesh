"""Signal configuration loader — reads from DB first, falls back to JSON."""
import json
import os
from pathlib import Path

_CONFIG_PATH = Path(os.getenv("SIGNAL_CONFIG_PATH", Path(__file__).parent.parent / "config" / "signal_config.json"))


def load_signal_map() -> dict:
    """Load signal map from config file.

    Returns:
        dict: A dictionary mapping signal types to their configuration.
    """
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
            return data.get("signal_map", {})
    return {}  # fallback


def load_bullish_signals() -> list:
    """Load bullish signal list from config.

    Returns:
        list: A list of bullish signal strings.
    """
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
            return data.get("bullish_signals", [])
    return []
