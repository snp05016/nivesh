"""
Nightly outcome backfill for the epistemic calibration substrate.

Generalises the one-shot outcome pricing in feedback_injector.py (lines 68-99)
into a batch job that systematically resolves all unpriced AnalysisHistory rows.
This provides the labeled (predicted_confidence, was_correct) dataset that
Brier/ECE/Venn-Abers/conformal calibration engines consume.

Architecture:
  - Runs as an APScheduler cron job (03:00 daily, gated by ENABLE_SCHEDULER)
  - Uses get_session() per batch — never holds a long-lived session
  - Idempotent: rows with outcome_checked_at already set are skipped
  - yfinance fetch with .NS → .BO fallback (same as feedback_injector.py)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum trading days after analysis before we price the outcome.
# Prevents pricing during the initial volatility window.
_SETTLE_WINDOW_DAYS = 5

# Max rows per batch to avoid hammering yfinance or holding sessions too long.
_BATCH_SIZE = 50

# Delta cap (±30%) to match feedback_injector.py Fix 2.11
_DELTA_CAP = 30.0


def backfill_outcomes(
    lookback_days: int = 180,
    batch_size: int = _BATCH_SIZE,
    settle_days: int = _SETTLE_WINDOW_DAYS,
) -> dict:
    """Backfill outcome_delta_pct / was_correct for unresolved AnalysisHistory rows.

    Returns a summary dict: {processed, resolved, errors, skipped}.
    """
    from database import AnalysisHistory, get_session

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    settle_cutoff = datetime.now(timezone.utc) - timedelta(days=settle_days)

    stats = {"processed": 0, "resolved": 0, "errors": 0, "skipped": 0}

    with get_session() as session:
        rows = (
            session.query(AnalysisHistory)
            .filter(
                AnalysisHistory.outcome_checked_at.is_(None),
                AnalysisHistory.created_at >= cutoff,
                AnalysisHistory.created_at <= settle_cutoff,
            )
            .order_by(AnalysisHistory.created_at.asc())
            .limit(batch_size)
            .all()
        )

        if not rows:
            logger.info("[outcome_backfill] No unresolved rows found.")
            return stats

        logger.info("[outcome_backfill] Processing %d unresolved rows.", len(rows))

        for row in rows:
            stats["processed"] += 1
            try:
                _resolve_single(row, session)
                stats["resolved"] += 1
            except _SkipRow as e:
                logger.debug("[outcome_backfill] %s: skipped — %s", row.ticker, e)
                stats["skipped"] += 1
            except Exception as e:
                logger.warning("[outcome_backfill] %s (id=%s): error — %s", row.ticker, row.id, e)
                session.rollback()
                stats["errors"] += 1

    logger.info("[outcome_backfill] Done: %s", stats)
    return stats


class _SkipRow(Exception):
    """Raised when a row cannot be resolved but is not an error."""
    pass


def _resolve_single(row, session) -> None:
    """Price a single AnalysisHistory row's outcome. Commits on success."""
    import json
    import gzip

    # Parse the stored analysis to get previous price and signal
    raw = row.full_json
    if isinstance(raw, (bytes, memoryview)):
        report_str = gzip.decompress(bytes(raw)).decode("utf-8")
    else:
        report_str = raw

    report = json.loads(report_str)

    prev_price = report.get("current_price") or report.get("price")
    prev_signal = report.get("signal", "UNKNOWN")

    if not prev_price:
        raise _SkipRow("no previous price in stored report")

    prev_price_f = float(prev_price)
    if prev_price_f <= 0:
        raise _SkipRow("previous price <= 0")

    # Fetch current price — .NS then .BO fallback (mirrors feedback_injector.py:70-72)
    current_price = _fetch_current_price(row.ticker)
    if current_price is None:
        raise _SkipRow("could not fetch current price")

    delta_pct = round(((current_price - prev_price_f) / prev_price_f) * 100, 2)
    # Cap at ±30% — Fix 2.11 from feedback_injector.py
    delta_pct = max(-_DELTA_CAP, min(_DELTA_CAP, delta_pct))

    was_correct = (
        (prev_signal in ("BUY", "BULLISH") and delta_pct > 0)
        or (prev_signal in ("SELL", "BEARISH") and delta_pct < 0)
    )

    row.outcome_delta_pct = delta_pct
    row.was_correct = was_correct
    row.outcome_checked_at = datetime.now(timezone.utc)

    try:
        session.commit()
    except Exception as _e:
        session.rollback()
        raise


def _fetch_current_price(ticker: str) -> Optional[float]:
    """Fetch latest closing price via yfinance with .NS → .BO fallback."""
    import yfinance as yf

    for suffix in (".NS", ".BO"):
        try:
            hist = yf.download(
                f"{ticker}{suffix}",
                period="2d",
                auto_adjust=True,
                progress=False,
            )
            if hist is not None and len(hist) > 0:
                return round(float(hist["Close"].iloc[-1]), 2)
        except Exception as _e:
            continue
    return None
