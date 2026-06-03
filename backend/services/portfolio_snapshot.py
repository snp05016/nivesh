"""
Nivesh Portfolio Snapshot
Takes a daily valuation snapshot for all users.
Uses the same yfinance price logic as the /portfolio endpoint.
Run nightly at 4:30 PM IST (market close + 30 min settlement).
"""
import yfinance as yf
import logging
from datetime import datetime, date
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import SessionLocal, Portfolio, PortfolioValuationHistory, User

logger = logging.getLogger(__name__)

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
    db = SessionLocal()
    today_str = date.today().isoformat()

    try:
        users = db.query(User).all()

        # Fetch NIFTY close for benchmark
        try:
            nifty = yf.Ticker("^NSEI")
            nifty_hist = nifty.history(period="2d")
            nifty_close = float(nifty_hist["Close"].iloc[-1]) if not nifty_hist.empty else None
        except Exception:
            nifty_close = None

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

    finally:
        db.close()
