"""
Nivesh PKScreener Runner
Runs PKScreener nightly for all portfolio + watchlist tickers.
Stores structured signals for injection into the Claude analysis pipeline.
"""
import subprocess
import json
import logging
import re
import sys
from datetime import date, datetime
from database import SessionLocal, PKScreenerSignal, Portfolio

logger = logging.getLogger(__name__)

def get_all_tracked_tickers(db) -> list:
    """Returns all tickers from all users' portfolios.

    Args:
        db: The database session object.

    Returns:
        list: A list of unique ticker strings.
    """
    portfolio_tickers = {h.ticker for h in db.query(Portfolio).all()}
    return list(portfolio_tickers)


def normalize_technical_score(signals: dict) -> float:
    """Convert PKScreener signal fields into a normalized 0.0-1.0 score.

    0.0 = Strong Sell, 0.5 = Neutral, 1.0 = Strong Buy.

    Args:
        signals (dict): A dictionary containing PKScreener technical signals.

    Returns:
        float: The normalized technical score.
    """
    score = 0.5  # Start neutral

    rsi = signals.get("rsi")
    if rsi is not None:
        if rsi < 30:    score += 0.15
        elif rsi > 70:  score -= 0.10
        elif 40 < rsi < 60: score += 0.05

    macd = signals.get("macd_signal", "")
    if macd == "BUY":    score += 0.15
    elif macd == "SELL": score -= 0.15

    ma = signals.get("ma_signal", "")
    if ma and "Above200MA" in ma:  score += 0.12
    elif ma and "Above50MA" in ma: score += 0.07
    elif ma and "Below50MA" in ma: score -= 0.07
    elif ma and "DeathCross" in ma: score -= 0.15

    if signals.get("breakout"):    score += 0.08
    if signals.get("consolidating"): score += 0.03

    if signals.get("volume_signal") == "HighVolume" and signals.get("breakout"):
        score += 0.05

    return round(max(0.0, min(1.0, score)), 3)


# Fix 2.2: SME platform tickers cause PKScreener to hang (30s timeout).
# Detect and skip them before subprocess spawn.
_SME_TICKER_PATTERNS = ["-SM", "-SME", "BSE_SME"]


def _is_sme_ticker(ticker: str) -> bool:
    """Check if ticker belongs to SME platform — these hang PKScreener.

    Args:
        ticker (str): The ticker symbol to check.

    Returns:
        bool: True if it is an SME ticker, False otherwise.
    """
    upper = ticker.upper().strip()
    return any(p in upper for p in _SME_TICKER_PATTERNS)


def run_pkscreener_for_ticker(ticker: str) -> dict:
    """Run the PKScreener subprocess for a specific ticker.

    Args:
        ticker (str): The ticker symbol.

    Returns:
        dict: A parsed dictionary of PKScreener signals, or None if it fails.
    """
    # Fix 2.2: skip SME tickers — they cause silent 30s timeouts
    if _is_sme_ticker(ticker):
        logger.info(f"PKScreener: skipping SME ticker {ticker}")
        return None

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pkscreener", "-t", ticker],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()

        if not output:
            logger.warning(f"PKScreener produced no output for {ticker}")
            return None

        return parse_pkscreener_output(ticker, output)

    except subprocess.TimeoutExpired:
        logger.warning(f"PKScreener timeout for {ticker}")
        return None
    except Exception as e:
        logger.error(f"PKScreener error for {ticker}: {e}")
        return None


def parse_pkscreener_output(ticker: str, output: str) -> dict:
    """Parse PKScreener stdout into a structured dict.

    Args:
        ticker (str): The ticker symbol.
        output (str): The raw standard output from the PKScreener subprocess.

    Returns:
        dict: A structured dictionary of extracted technical signals.
    """
    signals = {
        "ticker": ticker,
        "screen_result": output[:500],
        "breakout": False,
        "consolidating": False,
        "rsi": None,
        "macd_signal": None,
        "ma_signal": None,
        "volume_signal": None,
        "pattern": None,
    }

    # Try JSON parse first
    try:
        data = json.loads(output)
        signals["rsi"] = data.get("rsi") or data.get("RSI")
        signals["breakout"] = bool(data.get("breakout") or data.get("Breakout"))
        signals["consolidating"] = bool(data.get("consolidating") or data.get("Consolidating"))
        signals["pattern"] = data.get("pattern") or data.get("Pattern")
        return signals
    except (json.JSONDecodeError, TypeError):
        pass

    # Text output parsing
    output_lower = output.lower()

    rsi_match = re.search(r'rsi[:\s]+(\d+\.?\d*)', output_lower)
    if rsi_match:
        signals["rsi"] = float(rsi_match.group(1))

    if "breakout" in output_lower:
        signals["breakout"] = True
    if "consolidat" in output_lower:
        signals["consolidating"] = True

    if "200ma" in output_lower or "200 ma" in output_lower:
        signals["ma_signal"] = "Above200MA" if "above" in output_lower else "Below200MA"
    elif "50ma" in output_lower or "50 ma" in output_lower:
        signals["ma_signal"] = "Above50MA" if "above" in output_lower else "Below50MA"
    if "death cross" in output_lower:
        signals["ma_signal"] = "DeathCross"

    if "macd" in output_lower:
        if "buy" in output_lower:   signals["macd_signal"] = "BUY"
        elif "sell" in output_lower: signals["macd_signal"] = "SELL"
        else:                        signals["macd_signal"] = "NEUTRAL"

    if "high volume" in output_lower or "highvol" in output_lower:
        signals["volume_signal"] = "HighVolume"

    patterns = ["bull flag", "cup and handle", "double bottom", "head and shoulders",
                "ascending triangle", "descending triangle", "hammer", "doji"]
    for p in patterns:
        if p in output_lower:
            signals["pattern"] = p.title()
            break

    return signals


async def run_nightly_screen():
    """Run the nightly PKScreener job for all tracked tickers.

    Returns:
        int: The number of tickers successfully processed.
    """
    from database import get_session
    today = date.today().isoformat()
    processed = 0
    errors = 0

    with get_session() as db:
        tickers = get_all_tracked_tickers(db)
        logger.info(f"PKScreener: screening {len(tickers)} tickers for {today}")

        for ticker in tickers:
            try:
                existing = db.query(PKScreenerSignal).filter(
                    PKScreenerSignal.ticker == ticker,
                    PKScreenerSignal.signal_date == today
                ).first()
                if existing:
                    continue

                signals = run_pkscreener_for_ticker(ticker)
                if not signals:
                    continue

                tech_score = normalize_technical_score(signals)

                row = PKScreenerSignal(
                    ticker=ticker,
                    signal_date=today,
                    screen_result=signals.get("screen_result"),
                    breakout=signals.get("breakout", False),
                    consolidating=signals.get("consolidating", False),
                    rsi=signals.get("rsi"),
                    macd_signal=signals.get("macd_signal"),
                    ma_signal=signals.get("ma_signal"),
                    volume_signal=signals.get("volume_signal"),
                    pattern=signals.get("pattern"),
                    technical_score=tech_score,
                )
                db.add(row)
                db.commit()
                processed += 1
                logger.info(f"{ticker}: score={tech_score}, breakout={signals.get('breakout')}")

            except Exception as e:
                logger.error(f"Error screening {ticker}: {e}")
                db.rollback()
                errors += 1
                continue

    logger.info(f"PKScreener run complete. processed={processed}, errors={errors}")
    return processed
