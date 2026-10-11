import logging
from datetime import date
from database import get_session
from models.db_models import EarningsSurpriseHistory
from routers.market import earnings_estimates_endpoint
from services.disk_cache import get as _dc_get, set as _dc_set

# Public, unauthenticated route: serve one computed result for an hour instead
# of 8 serial yfinance lookups + DB writes per request (REL-01). The key is a
# constant: `period` is untrusted query input and does not change the result,
# so keying on it would let callers bypass the cache with random values.
_SURPRISES_TTL_SEC = 3600
_SURPRISES_CACHE_KEY = "current_quarter"


def _fy_quarter_label(period_end: date) -> str:
    """Indian fiscal quarter of a period end date: Apr-Jun 2026 -> 'Q1 FY27'."""
    q = (period_end.month - 4) % 12 // 3 + 1
    fy = period_end.year + 1 if period_end.month >= 4 else period_end.year
    return f"Q{q} FY{fy % 100:02d}"


def _serial_pattern(ticker: str, quarter: str, classification: str):
    """Consecutive identical BEAT/MISS over distinct stored quarters, incl. this one."""
    if classification not in ("BEAT", "MISS"):
        return None
    with get_session() as session:
        rows = (session.query(EarningsSurpriseHistory)
                .filter(EarningsSurpriseHistory.ticker == ticker,
                        EarningsSurpriseHistory.quarter != quarter)
                .order_by(EarningsSurpriseHistory.created_at.desc())
                .with_entities(EarningsSurpriseHistory.quarter,
                               EarningsSurpriseHistory.classification).all())
    n, seen = 1, {quarter}
    for row_quarter, row_class in rows:
        if row_quarter in seen:
            continue
        seen.add(row_quarter)
        if row_class != classification:
            break
        n += 1
    return f"{n}x consecutive {classification.lower()}" if n >= 2 else None


def compute_surprise_for_ticker(ticker: str):
    """A surprise exists only for a real estimate/actual pair of one fiscal quarter.

    The estimates source must supply eps_estimate, eps_actual and period_end
    (ISO date of the quarter both refer to); otherwise there is nothing honest
    to report and this returns None (FAKE-11). Today no consensus feed exists,
    so eps_estimate is always None and this always returns None.
    """
    try:
        est_data = earnings_estimates_endpoint(ticker)
        estimated_eps = est_data.get("eps_estimate")
        actual_eps = est_data.get("eps_actual")
        period_end = est_data.get("period_end")
        if estimated_eps is None or actual_eps is None or not period_end or estimated_eps == 0:
            return None
        quarter = _fy_quarter_label(date.fromisoformat(str(period_end)[:10]))

        surprise_pct = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
        classification = "INLINE"
        if surprise_pct > 10:
            classification = "BEAT"
        elif surprise_pct < -10:
            classification = "MISS"

        return {
            "ticker": ticker,
            "company_name": est_data.get("company_name", ticker),
            "quarter": quarter,
            "estimated_eps": estimated_eps,
            "actual_eps": actual_eps,
            "surprise_pct": surprise_pct,
            "classification": classification,
            # ponytail: no announcement-date source, so no post-result reaction;
            # compute 1D/5D from the announcement close once a feed provides the date.
            "post_price_1d": None,
            "post_price_5d": None,
            "historical_score": None,
            "serial_pattern": _serial_pattern(ticker, quarter, classification),
        }
    except Exception as e:
        logging.info(f"Error computing surprise for {ticker}: {e}")
        return None

def get_all_surprises(period="current_quarter"):
    # `period` is accepted for API compatibility only; it is ignored.
    cached = _dc_get("earnings_surprise", _SURPRISES_CACHE_KEY)
    if cached is not None:
        return cached
    # Fixed large-cap tracker list; only verified surprises are returned and persisted.
    tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC"]
    results = []
    for t in tickers:
        data = compute_surprise_for_ticker(t)
        if data:
            results.append(data)
            
    # Persist
    with get_session() as session:
        for r in results:
            existing = session.query(EarningsSurpriseHistory).filter_by(ticker=r["ticker"], quarter=r["quarter"]).first()
            if existing:
                existing.estimated_eps = r["estimated_eps"]
                existing.actual_eps = r["actual_eps"]
                existing.surprise_pct = r["surprise_pct"]
                existing.classification = r["classification"]
                existing.post_price_1d = r["post_price_1d"]
                existing.post_price_5d = r["post_price_5d"]
                existing.historical_score = r["historical_score"]
                existing.serial_pattern = r["serial_pattern"]
            else:
                new_rec = EarningsSurpriseHistory(
                    ticker=r["ticker"],
                    company_name=r["company_name"],
                    quarter=r["quarter"],
                    estimated_eps=r["estimated_eps"],
                    actual_eps=r["actual_eps"],
                    surprise_pct=r["surprise_pct"],
                    classification=r["classification"],
                    post_price_1d=r["post_price_1d"],
                    post_price_5d=r["post_price_5d"],
                    historical_score=r["historical_score"],
                    serial_pattern=r["serial_pattern"]
                )
                session.add(new_rec)
        session.commit()
    _dc_set("earnings_surprise", _SURPRISES_CACHE_KEY, results, ttl=_SURPRISES_TTL_SEC)
    return results

def get_surprise_history(ticker: str):
    # Stored verified surprises only; nothing is computed or invented on a miss.
    with get_session() as session:
        records = session.query(EarningsSurpriseHistory).filter_by(ticker=ticker).order_by(EarningsSurpriseHistory.created_at.desc()).all()

    history = []
    for r in records:
        history.append({
            "ticker": r.ticker,
            "company_name": r.company_name,
            "quarter": r.quarter,
            "estimated_eps": r.estimated_eps,
            "actual_eps": r.actual_eps,
            "surprise_pct": r.surprise_pct,
            "classification": r.classification,
            "post_price_1d": r.post_price_1d,
            "post_price_5d": r.post_price_5d,
            "historical_score": r.historical_score,
            "serial_pattern": r.serial_pattern
        })
    return history
