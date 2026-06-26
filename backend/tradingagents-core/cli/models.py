"""Models and enumerations for the CLI interface."""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel


class AnalystType(str, Enum):
    """Enumeration of available analyst types."""
    MARKET = "market"
    # Wire value stays "social" for saved-config and string-keyed-caller
    # back-compat; the user-facing label is "Sentiment Analyst".
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"


class AssetType(str, Enum):
    """Enumeration of supported asset types."""
    STOCK = "stock"
    CRYPTO = "crypto"
