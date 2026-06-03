"""
Nivesh Epistemic Feedback Injector
-------------------------------------
Injects historical analysis performance into the LangGraph debate
to prevent the pipeline from repeating structural errors.

ARCHITECTURE:
  - Called BEFORE the Bull/Bear debate (pre-graph step)
  - Output injected into VOLATILE HumanMessage layer ONLY
  - NEVER injected into static INDIAN_MARKET_SYSTEM_PROMPT
  - Falls back silently if no history exists

COST: ~200-400 tokens per cache-miss run. Zero cost on cache hits.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_feedback_block(ticker: str, db_session=None) -> str:
    """
    Fetch the most recent analysis for a ticker, compute the price delta
    since that analysis, and return a structured feedback string.

    Returns empty string if no prior analysis exists.
    """
    try:
        from database import AnalysisHistory, get_session
        import json
        import gzip

        if db_session is None:
            with get_session() as session:
                return get_feedback_block(ticker, db_session=session)

        last_analysis = (
            db_session.query(AnalysisHistory)
            .filter(AnalysisHistory.ticker == ticker.upper())
            .order_by(AnalysisHistory.created_at.desc())
            .first()
        )

        if not last_analysis:
            return ""

        try:
            raw = last_analysis.full_json
            if isinstance(raw, (bytes, memoryview)):
                report_str = gzip.decompress(bytes(raw)).decode("utf-8")
            else:
                report_str = raw
            report = json.loads(report_str)
        except Exception as e:
            logger.warning(f"[feedback_injector] {ticker}: Could not parse stored report: {e}")
            return ""

        prev_signal     = report.get("signal", "UNKNOWN")
        prev_confidence = report.get("confidence_pct") or report.get("confidence_score", "N/A")
        tp              = report.get("target_prices") or {}
        prev_target_3m  = tp.get("short_term_3m") or report.get("target_3m")
        prev_target_12m = tp.get("medium_term_12m") or report.get("target_12m")
        prev_price      = report.get("current_price") or report.get("price")
        prev_date       = last_analysis.created_at

        current_price = None
        try:
            import yfinance as yf
            hist = yf.download(f"{ticker}.NS", period="2d", auto_adjust=True, progress=False)
            if hist is None or len(hist) == 0:
                hist = yf.download(f"{ticker}.BO", period="2d", auto_adjust=True, progress=False)
            if hist is not None and len(hist) > 0:
                current_price = round(float(hist["Close"].iloc[-1]), 2)
        except Exception:
            pass

        outcome_line = ""
        if current_price and prev_price:
            try:
                prev_price_f = float(prev_price)
                delta_pct    = round(((current_price - prev_price_f) / prev_price_f) * 100, 2)
                direction    = "UP" if delta_pct > 0 else "DOWN"
                outcome_line = (
                    f"  Actual outcome: Stock moved {direction} {abs(delta_pct):.1f}% "
                    f"(₹{prev_price_f:.0f} → ₹{current_price:.0f})"
                )

                try:
                    last_analysis.outcome_delta_pct  = delta_pct
                    last_analysis.outcome_checked_at = datetime.utcnow()
                    last_analysis.was_correct = (
                        (prev_signal in ("BUY", "BULLISH") and delta_pct > 0) or
                        (prev_signal in ("SELL", "BEARISH") and delta_pct < 0)
                    )
                    db_session.commit()
                except Exception:
                    db_session.rollback()
            except Exception:
                pass

        days_ago = (datetime.utcnow() - prev_date).days if prev_date else "?"
        date_str = prev_date.strftime("%Y-%m-%d") if prev_date else "unknown"

        lines = [
            "=== EPISTEMIC FEEDBACK: PREVIOUS ANALYSIS AUDIT ===",
            f"This ticker was last analyzed {days_ago} days ago ({date_str}).",
            f"Previous signal:     {prev_signal} (confidence: {prev_confidence})",
        ]
        if prev_price:
            lines.append(f"Previous price:      ₹{prev_price}")
        if prev_target_3m:
            lines.append(f"3-month target set:  ₹{prev_target_3m}")
        if prev_target_12m:
            lines.append(f"12-month target set: ₹{prev_target_12m}")
        if outcome_line:
            lines.append(outcome_line)
        lines += [
            "",
            "MANDATORY AUDIT REQUIREMENT:",
            "Both the Bull Researcher and Bear Researcher MUST address before presenting their cases:",
            "1. Was the previous signal directionally correct? Cite the outcome above.",
            "2. Which assumption in the previous thesis proved wrong?",
            "3. What information was available then that should have predicted a different outcome?",
            "Ignoring prior predictions and repeating the same structural errors is the primary failure mode.",
            "=== END EPISTEMIC FEEDBACK ===",
        ]

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"[feedback_injector] {ticker}: Error building feedback block: {e}")
        return ""
