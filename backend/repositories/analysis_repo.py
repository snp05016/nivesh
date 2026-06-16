"""Analysis history repository — query functions extracted from database.py."""

import json
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models.db_models import AnalysisHistory, SignalEvent


def save_analysis(session: Session, user_id: Optional[int], ticker: str, result: dict, raw_output: Optional[str] = None, scan_type: str = "standard") -> dict:
    """Save analysis. Returns result dict enriched with signal_changed and previous_signal."""
    ticker = ticker.upper()
    tp = result.get("target_prices") or {}
    new_signal = result.get("signal", "UNKNOWN")

    fundamentals = result.get("fundamentals_snapshot") or {}
    curr_pledged = fundamentals.get("promoter_pledged_pct")
    curr_pledged_trend = fundamentals.get("promoter_pledged_trend")

    # Intentionally cross-user: signal is market-wide; compare against latest analysis
    # for this ticker regardless of which user triggered it.
    prev_row = (
        session.query(AnalysisHistory)
        .filter(AnalysisHistory.ticker == ticker)
        .order_by(AnalysisHistory.created_at.desc())
        .first()
    )
    prev_signal = prev_row.signal if prev_row else None
    flipped = prev_signal is not None and prev_signal != new_signal

    # Promoter pledging increase logic (>5 percentage points)
    pledging_increased_warning = False
    if curr_pledged is not None and prev_row and prev_row.promoter_pledged_pct is not None:
        if (curr_pledged - prev_row.promoter_pledged_pct) > 5.0:
            flipped = True # Force signal_changed
            pledging_increased_warning = True

    if pledging_increased_warning:
        wtw = result.get("what_to_watch", [])
        if not any("PLEDGING INCREASED" in x for x in wtw):
            wtw.insert(0, "\u26a0 PLEDGING INCREASED: Significant jump in promoter pledging detected.")
            result["what_to_watch"] = wtw

    if flipped:
        session.add(SignalEvent(
            ticker=ticker,
            from_signal=prev_signal or "NONE",
            to_signal=new_signal,
            event_date=result.get("analysis_date", date.today().isoformat()),
        ))

    record = AnalysisHistory(
        user_id=user_id,
        ticker=ticker,
        analysis_date=date.today().isoformat(),  # always server date — never trust LLM's date field
        signal=new_signal,
        confidence_pct=result.get("confidence_pct"),
        target_short=tp.get("short_term_3m"),
        target_medium=tp.get("medium_term_12m"),
        target_long=tp.get("long_term_36m"),
        promoter_pledged_pct=curr_pledged,
        promoter_pledged_trend=curr_pledged_trend,
        raw_output=raw_output,
        full_json=json.dumps(result),
        scan_type=scan_type,
        # ML Hybrid Pipeline fields
        market_regime=result.get("market_regime", "Transition"),
        calibrated_confidence=result.get("calibrated_confidence", 0.0),
        confidence_math_breakdown=result.get("confidence_math_breakdown", {}),
        conformal_target_upper_3m=result.get("conformal_target_upper_3m"),
        conformal_target_lower_3m=result.get("conformal_target_lower_3m"),
        quantitative_drivers=result.get("quantitative_drivers", {}),
        tail_risk_flags=result.get("tail_risk_flags", {}),
    )
    session.add(record)
    session.commit()

    result["signal_changed"] = flipped
    result["previous_signal"] = prev_signal
    return result


def get_recent_analyses(
    session: Session, user_id: Optional[int], ticker: str, limit: int = 3
) -> list[dict]:
    q = session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker)
    if user_id is not None:
        q = q.filter(AnalysisHistory.user_id == user_id)
    rows = q.order_by(AnalysisHistory.created_at.desc()).limit(limit).all()
    return [json.loads(r.full_json) for r in reversed(rows)]


def get_analysis_for_date(session: Session, ticker: str, target_date: str, scan_type: str = "standard") -> Optional[dict]:
    """Return the last analysis for ticker+scan_type regardless of date.
    Includes _staleness_hours, _staleness_label, _staleness_score, and _staleness_urgency."""
    from services.staleness import compute_staleness as _cs
    row = (
        session.query(AnalysisHistory)
        .filter(
            AnalysisHistory.ticker == ticker.upper(),
            AnalysisHistory.scan_type == scan_type,
        )
        .order_by(AnalysisHistory.created_at.desc())
        .first()
    )
    if not row:
        return None
    res = json.loads(row.full_json)
    res.setdefault("confidence_math_breakdown", row.confidence_math_breakdown or {})
    res["raw_output"] = row.raw_output
    res["_cached_scan_type"] = scan_type
    if row.created_at:
        result = _cs(
            last_analysis_date=row.created_at,
            price_change_7d_pct=float(res.get("7d_price_change_pct", 0) or 0),
            signal=res.get("signal", "HOLD") or "HOLD",
        )
        res["_staleness_hours"] = round(
            (datetime.now(timezone.utc) - row.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600, 1
        )
        res["_staleness_label"] = result["urgency"].title()
        res["_staleness_score"] = result["score"]
        res["_staleness_urgency"] = result["urgency"]
        res["_staleness_reason"] = result["reason"]
    return res


def get_all_ticker_history(session: Session, ticker: str, user_id: Optional[int] = None, limit: int = 50) -> list[dict]:
    q = session.query(AnalysisHistory).filter(AnalysisHistory.ticker == ticker.upper())
    if user_id is not None:
        q = q.filter(AnalysisHistory.user_id == user_id)
    rows = q.order_by(AnalysisHistory.created_at.asc()).limit(limit).all()
    results = []
    for r in rows:
        res = json.loads(r.full_json)
        res.setdefault("confidence_math_breakdown", r.confidence_math_breakdown or {})
        res["raw_output"] = r.raw_output
        results.append(res)
    return results
