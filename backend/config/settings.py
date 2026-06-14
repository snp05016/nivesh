"""
Central configuration for the Nivesh backend.
All hardcoded constants that were previously scattered across routers and helpers
are collected here and made overridable via environment variables.

Usage:
    from config.settings import SECTOR_PE_MAP, ADVISOR_INSIGHTS_LOOKBACK_DAYS, ...
"""
import os
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Task 31: SECTOR_PE_MAP — Indian-market sector P/E benchmarks
# Overridable via SECTOR_PE_MAP_PATH pointing to a JSON file.
# ---------------------------------------------------------------------------
_SECTOR_PE_MAP_PATH = os.getenv("SECTOR_PE_MAP_PATH", "")
_SECTOR_PE_MAP_DEFAULTS: dict = {
    "Technology": 35,
    "Financial Services": 18,
    "Energy": 12,
    "Healthcare": 28,
    "Consumer Cyclical": 25,
    "Industrials": 22,
    "Basic Materials": 15,
    "Consumer Defensive": 30,
    "Utilities": 20,
    "Real Estate": 20,
    "Communication Services": 22,
}

if _SECTOR_PE_MAP_PATH and Path(_SECTOR_PE_MAP_PATH).exists():
    try:
        with open(_SECTOR_PE_MAP_PATH, "r") as _f:
            SECTOR_PE_MAP: dict = json.load(_f)
    except Exception:
        SECTOR_PE_MAP = _SECTOR_PE_MAP_DEFAULTS
else:
    SECTOR_PE_MAP = _SECTOR_PE_MAP_DEFAULTS

# ---------------------------------------------------------------------------
# Task 32: AdvisorInsights lookback window
# ---------------------------------------------------------------------------
ADVISOR_INSIGHTS_LOOKBACK_DAYS: int = int(os.getenv("ADVISOR_INSIGHTS_LOOKBACK_DAYS", 14))

# ---------------------------------------------------------------------------
# Task 33: Exchange suffixes — see also helpers.py EXCHANGE_SUFFIXES
# ---------------------------------------------------------------------------
EXCHANGE_SUFFIXES: dict = {
    "NSE": os.getenv("NSE_SUFFIX", ".NS"),
    "BSE": os.getenv("BSE_SUFFIX", ".BO"),
}

# ---------------------------------------------------------------------------
# Task 36: DeepSeek truncation limit
# ---------------------------------------------------------------------------
DEEPSEEK_MAX_CHARS: int = int(os.getenv("DEEPSEEK_MAX_CHARS", 8000))

# ---------------------------------------------------------------------------
# Task 37: LLM agent max tokens
# ---------------------------------------------------------------------------
LLM_AGENT_MAX_TOKENS: int = int(os.getenv("LLM_AGENT_MAX_TOKENS", 1000))

# ---------------------------------------------------------------------------
# Task 38: yfinance circuit breaker
# ---------------------------------------------------------------------------
YF_CIRCUIT_THRESHOLD: int = int(os.getenv("YF_CIRCUIT_THRESHOLD", 3))
YF_CIRCUIT_TIMEOUT: int = int(os.getenv("YF_CIRCUIT_TIMEOUT", 300))  # seconds

# ---------------------------------------------------------------------------
# Task 39: Cache TTLs (seconds)
# ---------------------------------------------------------------------------
QUICK_INFO_TTL: int = int(os.getenv("QUICK_INFO_TTL", 900))          # 15 min
ASM_GSM_CACHE_TTL: int = int(os.getenv("ASM_GSM_CACHE_TTL", 21600))  # 6 hours
INDICES_CACHE_TTL: int = int(os.getenv("INDICES_CACHE_TTL", 300))     # 5 min
MORNING_BRIEF_TTL: int = int(os.getenv("MORNING_BRIEF_TTL", 3600))   # 1 hour

# ---------------------------------------------------------------------------
# Task 40: yfinance backoff multiplier (used by tenacity / manual sleep)
# ---------------------------------------------------------------------------
YF_BACKOFF_MULTIPLIER: float = float(os.getenv("YF_BACKOFF_MULTIPLIER", 1.5))

# ---------------------------------------------------------------------------
# Task 42: NSE ticker overrides — loadable from JSON file
# ---------------------------------------------------------------------------
_NSE_TICKER_OVERRIDES_PATH = os.getenv("NSE_TICKER_OVERRIDES_PATH", "")
_NSE_TICKER_OVERRIDES_DEFAULTS: dict = {
    "JITFINFRA": "JITFINFRA.NS",
    "GAUDIUMIVF": "GAUDIUMIVF.NS",
}

if _NSE_TICKER_OVERRIDES_PATH and Path(_NSE_TICKER_OVERRIDES_PATH).exists():
    try:
        with open(_NSE_TICKER_OVERRIDES_PATH, "r") as _f:
            NSE_TICKER_OVERRIDES: dict = json.load(_f)
    except Exception:
        NSE_TICKER_OVERRIDES = _NSE_TICKER_OVERRIDES_DEFAULTS
else:
    NSE_TICKER_OVERRIDES = _NSE_TICKER_OVERRIDES_DEFAULTS

# ---------------------------------------------------------------------------
# Task 44: HTTP default timeout
# ---------------------------------------------------------------------------
HTTP_DEFAULT_TIMEOUT: int = int(os.getenv("HTTP_DEFAULT_TIMEOUT", 10))

# ---------------------------------------------------------------------------
# Task 45: Analysis strategy config — max_debate_rounds and max_risk_discuss_rounds
# ---------------------------------------------------------------------------
ANALYSIS_STRATEGY_CONFIG: dict = {
    "extreme": {
        "max_debate_rounds": int(os.getenv("MAX_DEBATE_ROUNDS_EXTREME", 2)),
        "max_risk_discuss_rounds": int(os.getenv("MAX_RISK_DISCUSS_ROUNDS_EXTREME", 1)),
    },
    "standard": {
        "max_debate_rounds": int(os.getenv("MAX_DEBATE_ROUNDS_NORMAL", 1)),
        "max_risk_discuss_rounds": int(os.getenv("MAX_RISK_DISCUSS_ROUNDS_NORMAL", 1)),
    },
}

# ---------------------------------------------------------------------------
# Task 54: yfinance rate limiter config
# ---------------------------------------------------------------------------
YF_RATE_LIMIT_TOKENS: float = float(os.getenv("YF_RATE_LIMIT_TOKENS", 30))
YF_RATE_LIMIT_PER_SEC: float = float(os.getenv("YF_RATE_LIMIT_PER_SEC", 0.5))
