"""
Nivesh Portfolio Snapshot
Takes a daily valuation snapshot for all users.
Uses the same yfinance price logic as the /portfolio endpoint.
Run nightly at 4:30 PM IST (market close + 30 min settlement).

Also provides pregen_morning_briefs_all_users() — pre-generates morning briefs
for all users at 6:30 AM IST so the /morning-summary endpoint is instant.
"""
import yfinance as yf
import logging
from datetime import datetime, date
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_session, Portfolio, PortfolioValuationHistory, User, AnalysisHistory
from services.llm_utils import contains_devanagari

logger = logging.getLogger(__name__)

# Disk-cache namespace for pre-generated morning briefs
_MORNING_BRIEF_NS = "morning_brief"

def get_current_price(ticker: str) -> float | None:
    """Fetch latest price with NSE → BSE fallback."""
    for suffix in [".NS", ".BO"]:
        try:
            t = yf.Ticker(ticker + suffix)
            hist = t.history(period="2d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
        except Exception:
            continue
    return None

async def snapshot_all_users():
    """Take valuation snapshot for all users."""
    today_str = date.today().isoformat()

    # Fetch NIFTY close for benchmark outside the per-user loop
    try:
        nifty = yf.Ticker("^NSEI")
        nifty_hist = nifty.history(period="2d")
        nifty_close = float(nifty_hist["Close"].iloc[-1]) if not nifty_hist.empty else None
    except Exception:
        nifty_close = None

    with get_session() as db:
        users = db.query(User).all()

        for user in users:
            try:
                # Skip if snapshot already exists for today
                existing = db.query(PortfolioValuationHistory).filter(
                    PortfolioValuationHistory.user_id == user.id,
                    PortfolioValuationHistory.snapshot_date == today_str
                ).first()
                if existing:
                    continue

                holdings = db.query(Portfolio).filter(
                    Portfolio.user_id == user.id,
                    Portfolio.group_name == "holdings"
                ).all()

                if not holdings:
                    continue

                total_invested = sum(h.shares * h.buy_price for h in holdings)
                total_value = 0.0

                for holding in holdings:
                    price = get_current_price(holding.ticker)
                    if price:
                        total_value += holding.shares * price
                    else:
                        # Fall back to cost basis if price unavailable
                        total_value += holding.shares * holding.buy_price

                pnl = total_value - total_invested
                pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0.0

                snapshot = PortfolioValuationHistory(
                    user_id=user.id,
                    snapshot_date=today_str,
                    total_value=round(total_value, 2),
                    total_invested=round(total_invested, 2),
                    total_pnl=round(pnl, 2),
                    pnl_percent=round(pnl_pct, 2),
                    nifty_close=nifty_close,
                )
                db.add(snapshot)
                db.commit()
                logger.info(f"Snapshot saved: user={user.id} value=₹{total_value:,.0f}")

            except Exception as e:
                logger.error(f"Snapshot error for user {user.id}: {e}")
                db.rollback()
                continue


async def pregen_morning_briefs_all_users() -> dict:
    """
    Pre-generate morning briefs for every user who has holdings.
    Called at 6:30 AM IST so the endpoint returns instantly when the user opens the app.
    Stores results in disk_cache under 'morning_brief' namespace keyed by user_id.

    Returns {"generated": int, "skipped": int, "errors": int}.
    """
    from services.disk_cache import set as cache_set
    from services.llm_utils import deepseek_chat as _deepseek_chat

    generated = 0
    skipped = 0
    errors = 0

    with get_session() as db:
        users = db.query(User).all()

        for user in users:
            try:
                holdings = db.query(Portfolio).filter_by(
                    user_id=user.id, group_name="holdings"
                ).all()

                if not holdings:
                    skipped += 1
                    continue

                # Gather last AI signals
                last_signals: dict[str, str] = {}
                for h in holdings:
                    row = (
                        db.query(AnalysisHistory)
                        .filter(
                            AnalysisHistory.user_id == user.id,
                            AnalysisHistory.ticker == h.ticker,
                        )
                        .order_by(AnalysisHistory.created_at.desc())
                        .first()
                    )
                    if row:
                        last_signals[h.ticker] = row.signal

                # Fetch live prices
                holding_lines = []
                mover_tickers = []
                significant_movers_lines = []

                for h in holdings:
                    ns_sym = f"{h.ticker}.NS" if not h.ticker.endswith((".NS", ".BO")) else h.ticker
                    try:
                        t = yf.Ticker(ns_sym)
                        hist = t.history(period="2d")
                        if not hist.empty and len(hist) >= 2:
                            current_price = float(hist["Close"].iloc[-1])
                            prev_close = float(hist["Close"].iloc[-2])
                        elif not hist.empty:
                            current_price = float(hist["Close"].iloc[-1])
                            prev_close = current_price
                        else:
                            current_price = prev_close = None
                    except Exception:
                        current_price = prev_close = None

                    day_pct = None
                    if current_price and prev_close and prev_close > 0:
                        day_pct = round((current_price - prev_close) / prev_close * 100, 2)

                    invested = h.shares * h.buy_price
                    current_value = h.shares * current_price if current_price else None
                    pnl_inr = (current_value - invested) if current_value else None
                    pnl_pct = ((current_value - invested) / invested * 100) if current_value and invested > 0 else None

                    price_str = f"₹{current_price:.2f}" if current_price else "N/A"
                    day_str = (f"+{day_pct:.1f}%" if day_pct and day_pct >= 0 else f"{day_pct:.1f}%") if day_pct is not None else "N/A"
                    pnl_str = ""
                    if pnl_inr is not None and pnl_pct is not None:
                        sign = "+" if pnl_inr >= 0 else ""
                        pnl_str = f", overall P&L: {sign}₹{pnl_inr:.0f} ({sign}{pnl_pct:.1f}%)"

                    holding_lines.append(
                        f"{h.ticker} ({h.company_name or h.ticker}): {price_str}, day: {day_str}{pnl_str}"
                    )

                    if day_pct is not None and abs(day_pct) >= 2.0:
                        mover_tickers.append(h.ticker)
                        significant_movers_lines.append(
                            f"{h.ticker}: {day_str} ({'UP' if day_pct > 0 else 'DOWN'})"
                        )

                signal_lines = [
                    f"{h.ticker}: {last_signals.get(h.ticker, 'No analysis yet')}"
                    for h in holdings
                ]

                portfolio_text = "\n".join(holding_lines) or "No holdings."
                movers_text = "\n".join(significant_movers_lines) or "None today"
                signals_text = "\n".join(signal_lines) or "No analysis available."

                prompt = (
                    "You are a friendly Indian stock market advisor. Write a short morning brief "
                    "(4-6 bullet points) for an investor. Write ONLY in English — never use Hindi. Be specific. "
                    "Mention big movers. Flag anything concerning. End with one sentence on market mood. "
                    "Use Indian number format (lakhs/crores). Be warm.\n\n"
                    f"Portfolio:\n{portfolio_text}\n\n"
                    f"Significant movers (±2%+):\n{movers_text}\n\n"
                    f"Last AI signals:\n{signals_text}\n\n"
                    'Return ONLY JSON: {"summary": "• Point 1\\n• Point 2", '
                    '"movers": ["TICKER1"], "mood": "positive"}\n'
                    'mood must be: "positive", "cautious", or "negative"'
                )

                raw = await _deepseek_chat(prompt, max_tokens=600)

                # Parse JSON from response
                brief = None
                try:
                    # Strip markdown fences if present
                    clean = raw.strip()
                    if "```" in clean:
                        clean = clean.split("```")[1]
                        if clean.startswith("json"):
                            clean = clean[4:]
                    start = clean.find("{")
                    end = clean.rfind("}") + 1
                    if start != -1 and end > start:
                        brief = json.loads(clean[start:end])
                except Exception:
                    pass

                if not brief:
                    brief = {
                        "summary": "• Market data loaded. Brief generation failed — please refresh.",
                        "movers": mover_tickers,
                        "mood": "cautious",
                    }
                elif contains_devanagari(brief.get("summary", "")):
                    logger.warning("[morning_brief] Rejected Hindi pre-generated brief for user_id=%s", user.id)
                    brief = {
                        "summary": "• Market data loaded. Brief generation returned non-English text - please refresh.",
                        "movers": mover_tickers,
                        "mood": "cautious",
                    }

                brief["generated_at"] = datetime.utcnow().strftime("%H:%M")
                brief["pregen"] = True

                cache_set(_MORNING_BRIEF_NS, str(user.id), brief)
                generated += 1
                logger.info(f"[morning_brief] Pre-generated for user_id={user.id}")

            except Exception as e:
                errors += 1
                logger.error(f"[morning_brief] Error for user_id={user.id}: {e}")
                continue

    logger.info(
        f"[morning_brief] Pre-gen complete: generated={generated} skipped={skipped} errors={errors}"
    )
    return {"generated": generated, "skipped": skipped, "errors": errors}
