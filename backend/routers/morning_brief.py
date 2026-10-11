"""Morning brief route: GET /morning-summary/{user_id}.

Split out of routers/portfolio.py (ARCH-14); path, handler name and tags are unchanged.
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from core.security import require_user_match
from helpers import (
    get_session, _to_ns, _yf_price, _dcache_get, _dcache_set, User,
    Portfolio, AnalysisHistory, SignalEvent, PriceTarget, _extract_json_from_text,
    _log_token_usage,
)
import os
from services.llm_utils import contains_devanagari
from services.kyc_consent_service import AI_PROCESSING_CONSENT, has_active_consent
from services import llm_budget
from services.portfolio_service import _get_indices_data
from database import latest_per_ticker
from services.yfinance_client import get_quotes
from config.settings import MORNING_BRIEF_TTL as _MORNING_CACHE_TTL

router = APIRouter(tags=["Portfolio"])

# Canned text when no AI brief could be built; the push route refuses to send it.
FALLBACK_SUMMARY = "• Market data loaded. AI brief unavailable at this time."
MOODS = ("positive", "cautious", "negative")
# FAKE-22: mood of a brief nobody computed. A string, not null: shipped iOS builds
# decode mood as a non-optional String.
MOOD_UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# 4. GET /morning-summary/{user_id}
# ---------------------------------------------------------------------------
@router.get("/morning-summary/{user_id}")
def morning_summary_endpoint(user_id: int, _caller: int = Depends(require_user_match)):
    return build_morning_summary(user_id)


def build_morning_summary(user_id: int) -> dict:
    """The brief for user_id, no auth: callers check ownership. Shared by the
    route and services.user_service.push_morning_summary (GH-651)."""
    # FINSEC-04: holdings go to the LLM processor only with the opt-in consent.
    # Not cached, so granting consent takes effect on the next request.
    if not has_active_consent(user_id, AI_PROCESSING_CONSENT):
        return {
            "summary": "• Enable 'AI processing' in Settings > Account Security > KYC Consents to get an AI morning brief.",
            "movers": [],
            "mood": MOOD_UNAVAILABLE,  # no brief was computed, so no mood either
            "generated_at": datetime.now(timezone.utc).strftime("%H:%M"),
        }
    now = time.time()

    # Check in-memory cache first
    # Redis-backed shared cache (works across all 12 workers)
    cached = _dcache_get("morning_brief", str(user_id))
    # SILENT-14: a degraded (canned) brief is never served from cache, so the
    # next request regenerates once the cause is fixed.
    if cached and isinstance(cached, dict) and not cached.get("degraded"):
        if not contains_devanagari(cached.get("summary", "")):
            return cached

    generated_at = datetime.now(timezone.utc).strftime("%H:%M")

    # FAKE-22: canned content carries no mood and is never cached, so a transient
    # LLM failure does not pin it for the whole MORNING_BRIEF_TTL.
    fallback = {
        "summary": FALLBACK_SUMMARY,
        "movers": [],
        "mood": MOOD_UNAVAILABLE,
        "generated_at": generated_at,
        "degraded": True,
    }

    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()

            # Last known signal per ticker: one windowed query, newest row only (PERF-08)
            tickers = [h.ticker.upper() for h in holdings]
            last_signals: dict[str, str] = {
                t: rows[0].signal for t, rows in latest_per_ticker(session, tickers, user_id=user_id).items()
            }

        # Fetch prices and compute movers
        holding_lines = []
        mover_tickers = []
        significant_movers_lines = []

        # All holdings' quotes in one concurrent, cached batch (PERF-07).
        ns_by_ticker = {h.ticker: _to_ns(h.ticker) for h in holdings}
        quotes = get_quotes(ns_by_ticker.values())

        for h in holdings:
            current_price, prev_close = quotes.get(ns_by_ticker[h.ticker], (None, None))

            day_pct = None
            if current_price and prev_close and prev_close > 0:
                day_pct = round((current_price - prev_close) / prev_close * 100, 2)

            invested = h.shares * h.buy_price
            current_value = h.shares * current_price if current_price else None
            pnl_pct = ((current_value - invested) / invested * 100) if current_value and invested > 0 else None

            # Data minimisation for the LLM processor: % moves only, never
            # share counts, prices or rupee P&L.
            day_str = (f"+{day_pct:.1f}%" if day_pct and day_pct >= 0 else f"{day_pct:.1f}%") if day_pct is not None else "N/A"
            pnl_str = f", overall P&L: {'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%" if pnl_pct is not None else ""

            company = h.company_name or h.ticker
            holding_lines.append(f"{h.ticker} ({company}): day change: {day_str}{pnl_str}")

            if day_pct is not None and abs(day_pct) >= 2.0:
                mover_tickers.append(h.ticker)
                direction = "UP" if day_pct > 0 else "DOWN"
                significant_movers_lines.append(f"{h.ticker}: {day_str} ({direction})")

        # Get signals text
        signal_lines = []
        for h in holdings:
            sig = last_signals.get(str(h.ticker), "No analysis yet")
            signal_lines.append(f"{h.ticker}: {sig}")

        # Get market indices
        indices_lines = []
        try:
            indices_data = _get_indices_data()
            for idx in indices_data.get("indices", []):
                if idx["name"] in ("Nifty 50", "Sensex"):
                    chg = idx["change_pct"]
                    chg_str = (f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%")
                    indices_lines.append(f"{idx['name']}: {idx['value']:.2f} ({chg_str})")
        except Exception as e:
            logging.warning("[morning-summary] index data unavailable: %s", e)

        portfolio_text = "\n".join(holding_lines) if holding_lines else "No holdings found."
        movers_text = "\n".join(significant_movers_lines) if significant_movers_lines else "None today"
        signals_text = "\n".join(signal_lines) if signal_lines else "No analysis available."
        indices_text = "\n".join(indices_lines) if indices_lines else "Data unavailable."

        prompt = f"""You are a friendly Indian stock market advisor. Write a short morning brief (4-6 bullet points) for an investor based on their portfolio data. Write ONLY in English — never use Hindi or any other language. Be specific about which stocks to watch and why. Mention any big movers. Flag anything concerning. End with one sentence on overall market mood. Use Indian number format (lakhs/crores). Be warm and helpful.

Portfolio holdings today:
{portfolio_text}

Significant movers (±2%+):
{movers_text}

Last AI signals:
{signals_text}

Market indices:
{indices_text}

Return ONLY a JSON object (no markdown):
{{"summary": "• Point 1\\n• Point 2\\n• Point 3\\n• Point 4", "movers": ["TICKER1", "TICKER2"], "mood": "positive"}}

mood must be exactly: "positive", "cautious", or "negative"
"""
        from services.llm_utils import claude_messages, HAIKU_MODEL
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "placeholder":
            logging.warning("[morning-summary] ANTHROPIC_API_KEY missing - serving degraded brief")
            return fallback  # not cached: SILENT-14
        try:
            llm_budget.guard(user_id, "morning_summary")
        except Exception:
            return fallback  # over budget: plain brief, not cached, so it regenerates once allowed

        response = claude_messages(
            model=HAIKU_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
            feature="morning_summary",
        )

        raw = _extract_json_from_text(response.content[0].text)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.warning(f"[morning-summary] Failed to parse brief JSON for user {user_id}: {e}")
            return fallback  # not cached: SILENT-14

        raw_summary = parsed.get("summary", fallback["summary"])
        if contains_devanagari(raw_summary):
            logging.warning(f"[morning-summary] Rejected Hindi brief output for user {user_id}")
            return fallback  # not cached: SILENT-14
        degraded = raw_summary == FALLBACK_SUMMARY  # never cache the canned brief

        # Normalize inline bullets ("• A • B • C") to newline-separated ("• A\n• B\n• C")
        if raw_summary and "\n" not in raw_summary and raw_summary.count("•") > 1:
            parts = [p.strip() for p in raw_summary.split("•") if p.strip()]
            raw_summary = "\n".join(f"• {p}" for p in parts)

        result = {
            "summary": raw_summary,
            "movers": parsed.get("movers", mover_tickers),
            "mood": parsed.get("mood", MOOD_UNAVAILABLE),
            "generated_at": generated_at,
        }

        # Validate mood value: an unusable one is reported as unavailable, not "cautious".
        if result["mood"] not in MOODS:
            result["mood"] = MOOD_UNAVAILABLE

        # Build prioritised action list for today
        # Fix 2.36: Signal flips (BULL→BEAR, BEAR→BULL) take TOP priority
        # over minor percentage movement alerts. Trend changes matter more.
        priority_items = []

        # Priority 1: Signal flips in last 24h for held stocks
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            with get_session() as session:
                held_tickers = {h.ticker for h in session.query(Portfolio).filter(
                    Portfolio.user_id == user_id,
                    Portfolio.group_name == "holdings"
                ).all()}
                flips = session.query(SignalEvent).filter(
                    SignalEvent.created_at >= cutoff,
                    SignalEvent.ticker.in_(held_tickers)
                ).all()
                for f in flips:
                    is_trend_flip = (
                        (f.from_signal in ("BULLISH", "BUY") and f.to_signal in ("BEARISH", "SELL")) or
                        (f.from_signal in ("BEARISH", "SELL") and f.to_signal in ("BULLISH", "BUY"))
                    )
                    priority_items.append({
                        "priority": 1 if is_trend_flip else 2,
                        "type": "trend_flip" if is_trend_flip else "signal_change",
                        "ticker": f.ticker,
                        "message": f"Signal changed: {f.ticker} {f.from_signal} → {f.to_signal}",
                    })
        except Exception as e:
            logging.info(f"[MORNING] Signal flip check failed: {e}")

        # Priority 2: Triggered price alerts
        try:
            with get_session() as session:
                triggered = session.query(PriceTarget).filter(
                    PriceTarget.user_id == user_id,
                    PriceTarget.triggered == True
                ).all()
                for a in triggered:
                    priority_items.append({
                        "priority": 2,
                        "type": "alert_triggered",
                        "ticker": a.ticker,
                        "message": f"Price alert triggered: {a.ticker} {a.direction} ₹{a.target_price:.0f}",
                    })
        except Exception as e:
            logging.info(f"[MORNING] Alert priority check failed: {e}")

        priority_items.sort(key=lambda x: x["priority"])
        result["priority_items"] = priority_items

        if not degraded:
            _dcache_set("morning_brief", str(user_id), result, ttl=_MORNING_CACHE_TTL)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logging.warning(f"[morning-summary] Brief generation failed for user {user_id}: {e}", exc_info=True)
        return fallback  # not cached: SILENT-14
