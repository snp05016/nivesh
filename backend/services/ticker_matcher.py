"""
ticker_matcher.py — Task 1.3 of Nivesh Advisor Intelligence Pipeline

Identifies NSE/BSE stock ticker mentions in Hinglish financial transcripts
using fuzzy matching (rapidfuzz).
"""

import logging
import os
import sqlite3
from typing import Optional

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Manual overrides: spoken / Hinglish aliases for common tickers
# ---------------------------------------------------------------------------

MANUAL_OVERRIDES: dict[str, list[str]] = {
    "TATAMOTORS": ["Tata Motors", "tata motor", "tata wala stock motors", "TM"],
    "HDFCBANK": ["HDFC Bank", "HDFC", "hdfc wala bank"],
    "INFY": ["Infosys", "Infy", "info sis"],
    "WIPRO": ["Wipro", "wipro wala"],
    "BAJFINANCE": ["Bajaj Finance", "bajaj fin", "baj fin"],
    "ADANIPORTS": ["Adani Ports", "adani port", "Adani"],
    "IRFC": ["IRFC", "Indian Railway Finance", "railway finance"],
    "SUZLON": ["Suzlon", "Suzlon Energy", "sujalon"],
    "RELIANCE": ["Reliance", "Reliance Industries", "RIL"],
    "HAL": ["HAL", "Hindustan Aeronautics", "hindustan aero"],
}

# ---------------------------------------------------------------------------
# Module-level alias tables built at import time
# ---------------------------------------------------------------------------

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "stockapp.db")


def _load_db_tickers(db_path: str) -> dict[str, str]:
    """Queries the database for (ticker, company_name) pairs.

    Pulls from `portfolio` (has company_name) and `analysis_history`
    (ticker only, no company_name). Returns {ticker: company_name}.
    company_name may be an empty string if only found in analysis_history.

    Args:
        db_path (str): The file path to the SQLite database.

    Returns:
        dict[str, str]: A dictionary mapping ticker symbols to their company names.
    """
    results: dict[str, str] = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # portfolio has both ticker and company_name
        cur.execute(
            "SELECT DISTINCT ticker, company_name FROM portfolio "
            "WHERE ticker IS NOT NULL AND ticker != '' "
            "AND COALESCE(asset_class, 'EQ') = 'EQ'"
        )
        for ticker, company_name in cur.fetchall():
            ticker = ticker.strip().upper()
            if ticker not in results:
                results[ticker] = (company_name or "").strip()

        # analysis_history has ticker only — add any new tickers not already known
        cur.execute(
            "SELECT DISTINCT ticker FROM analysis_history "
            "WHERE ticker IS NOT NULL AND ticker != ''"
        )
        for (ticker,) in cur.fetchall():
            ticker = ticker.strip().upper().replace(".NS", "").replace(".BO", "")
            if ticker not in results:
                results[ticker] = ""

        conn.close()
    except Exception as exc:
        logger.warning("ticker_matcher: failed to load DB tickers from %s: %s", db_path, exc)

    return results


def _build_alias_tables(
    db_tickers: dict[str, str],
    overrides: dict[str, list[str]],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Builds the alias tables for ticker matching.

    Args:
        db_tickers (dict[str, str]): Dictionary mapping tickers to company names.
        overrides (dict[str, list[str]]): Dictionary mapping tickers to manual aliases.

    Returns:
        tuple[dict[str, list[str]], dict[str, str]]: A tuple containing:
            - ticker_aliases: {ticker: [company_name, *manual_aliases]}
            - alias_to_ticker: {alias_lower: ticker}
    """
    ticker_aliases: dict[str, list[str]] = {}
    alias_to_ticker: dict[str, str] = {}

    for ticker, company_name in db_tickers.items():
        aliases: list[str] = []
        if company_name:
            aliases.append(company_name)
        aliases.extend(overrides.get(ticker, []))
        ticker_aliases[ticker] = aliases

        # Also register the ticker symbol itself as an alias
        alias_to_ticker[ticker.lower()] = ticker
        for alias in aliases:
            alias_to_ticker[alias.lower()] = ticker

    # Add manual override tickers that might not be in DB
    for ticker, manual_aliases in overrides.items():
        if ticker not in ticker_aliases:
            ticker_aliases[ticker] = manual_aliases
            alias_to_ticker[ticker.lower()] = ticker
            for alias in manual_aliases:
                alias_to_ticker[alias.lower()] = ticker

    return ticker_aliases, alias_to_ticker


# Build at import time
_db_tickers = _load_db_tickers(_DB_PATH)
TICKER_ALIASES: dict[str, list[str]] = {}
ALIAS_TO_TICKER: dict[str, str] = {}
TICKER_ALIASES, ALIAS_TO_TICKER = _build_alias_tables(_db_tickers, MANUAL_OVERRIDES)

# Flat list of all aliases for rapidfuzz matching
_ALL_ALIASES: list[str] = [
    alias
    for ticker, aliases in TICKER_ALIASES.items()
    for alias in aliases
] + list(TICKER_ALIASES.keys())  # include raw ticker symbols too

# Deduplicate while preserving order
_seen: set[str] = set()
_ALL_ALIASES_DEDUPED: list[str] = []
for _a in _ALL_ALIASES:
    if _a.lower() not in _seen:
        _seen.add(_a.lower())
        _ALL_ALIASES_DEDUPED.append(_a)
_ALL_ALIASES = _ALL_ALIASES_DEDUPED
del _seen, _ALL_ALIASES_DEDUPED


# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------

def extract_snippet(segments: list[dict], timestamp: float) -> str:
    """Returns joined text from segments within ±90 seconds of timestamp.
    
    Fix 2.20: Expanded from ±60s to ±90s to prevent sentiment inversion
    caused by mid-sentence audio cuts in transcript parsing.

    Args:
        segments (list[dict]): List of segment dicts with keys 'start', 'end', 'text'.
        timestamp (float): Centre timestamp in seconds.

    Returns:
        str: Single string of joined segment texts.
    """
    window_texts = [
        seg["text"]
        for seg in segments
        if abs(seg.get("start", 0) - timestamp) <= 90.0
    ]
    return " ".join(window_texts).strip()


# ---------------------------------------------------------------------------
# Timestamp approximation helpers
# ---------------------------------------------------------------------------

def _estimate_timestamp(
    word_index: int,
    total_words: int,
    duration_seconds: float,
    segments: list[dict],
) -> float:
    """Estimates the timestamp for a word at word_index.

    Uses linear interpolation based on the word index and total duration,
    then snaps to the nearest segment start.

    Args:
        word_index (int): The index of the matched word in the full text.
        total_words (int): The total number of words in the full text.
        duration_seconds (float): The total duration of the audio in seconds.
        segments (list[dict]): List of transcript segments.

    Returns:
        float: The estimated timestamp in seconds.
    """
    if total_words == 0 or duration_seconds <= 0:
        return 0.0

    estimated = (word_index / total_words) * duration_seconds

    if not segments:
        return estimated

    # Snap to nearest segment start
    nearest = min(segments, key=lambda s: abs(s.get("start", 0) - estimated))
    return float(nearest.get("start", estimated))


# ---------------------------------------------------------------------------
# Main match function
# ---------------------------------------------------------------------------

def find_tickers(transcript: dict) -> list[dict]:
    """Identifies ticker mentions in a transcript using sliding-window fuzzy matching.

    Args:
        transcript (dict): Dictionary from transcript_engine with keys:
            - 'segments' (list[dict]): List of {start, end, text}
            - 'full_text' (str): Full transcript text
            - 'duration_seconds' (float): Total duration

    Returns:
        list[dict]: List of matches sorted by timestamp_start ascending.
            Each dict contains:
            - "ticker" (str): The matched ticker symbol.
            - "timestamp_start" (float): The estimated timestamp.
            - "match_score" (int): The rapidfuzz match score.
            - "snippet" (str): The surrounding text snippet.
            Deduplicated: same ticker within 30 s → only highest-score entry kept.
    """
    if not _ALL_ALIASES:
        logger.warning("ticker_matcher: alias list is empty; no matches possible")
        return []

    full_text: str = transcript.get("full_text", "")
    segments: list[dict] = transcript.get("segments", [])
    duration_seconds: float = float(transcript.get("duration_seconds", 0.0))

    if not full_text.strip():
        return []

    words = full_text.split()
    total_words = len(words)

    if total_words == 0:
        return []

    # ------------------------------------------------------------------
    # Sliding window: size=6, step=3
    # ------------------------------------------------------------------
    WINDOW_SIZE = 6
    STEP = 3
    SCORE_CUTOFF = 82

    # Fix 2.9: generic English words that should NEVER be matched as tickers
    # even if rapidfuzz finds a high-scoring similarity
    _GENERIC_ENGLISH_WORDS = {
        "idea", "true", "false", "value", "growth",
        "market", "capital", "trust", "power", "light", "life",
        "future", "global", "prime", "star", "gold", "silver",
    }

    raw_matches: list[dict] = []

    for start_idx in range(0, max(1, total_words - WINDOW_SIZE + 1), STEP):
        window_words = words[start_idx: start_idx + WINDOW_SIZE]
        window_str = " ".join(window_words)

        result = process.extractOne(
            window_str,
            _ALL_ALIASES,
            scorer=fuzz.token_set_ratio,
            score_cutoff=SCORE_CUTOFF,
        )

        if result is None:
            continue

        matched_alias, score, _ = result

        # Fix 2.9: skip generic English words that rapidfuzz matched
        if matched_alias.lower().strip() in _GENERIC_ENGLISH_WORDS:
            continue

        # Resolve alias → ticker
        ticker = ALIAS_TO_TICKER.get(matched_alias.lower())
        if ticker is None:
            # Fallback: check if the matched string is itself a ticker symbol
            ticker = matched_alias.upper() if matched_alias.upper() in TICKER_ALIASES else None
        if ticker is None:
            continue

        timestamp = _estimate_timestamp(start_idx, total_words, duration_seconds, segments)
        snippet = extract_snippet(segments, timestamp)

        raw_matches.append(
            {
                "ticker": ticker,
                "timestamp_start": timestamp,
                "match_score": int(score),
                "snippet": snippet,
                "_start_idx": start_idx,
            }
        )

    if not raw_matches:
        return []

    # ------------------------------------------------------------------
    # Deduplication: same ticker within 30 s → keep highest score
    # ------------------------------------------------------------------
    # Sort by timestamp then score desc for grouping
    raw_matches.sort(key=lambda m: (m["timestamp_start"], -m["match_score"]))

    deduped: list[dict] = []
    for match in raw_matches:
        merged = False
        for existing in deduped:
            if (
                existing["ticker"] == match["ticker"]
                and abs(existing["timestamp_start"] - match["timestamp_start"]) <= 30.0
            ):
                # Keep higher score
                if match["match_score"] > existing["match_score"]:
                    existing["match_score"] = match["match_score"]
                    existing["timestamp_start"] = match["timestamp_start"]
                    existing["snippet"] = match["snippet"]
                merged = True
                break
        if not merged:
            deduped.append(match)

    # Strip internal key and sort by timestamp
    output = [
        {
            "ticker": m["ticker"],
            "timestamp_start": m["timestamp_start"],
            "match_score": m["match_score"],
            "snippet": m["snippet"],
        }
        for m in sorted(deduped, key=lambda m: m["timestamp_start"])
    ]

    return output
