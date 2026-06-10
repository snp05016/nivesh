"""
reset_mock_user.py — Delete all records for snp050106@gmail.com, then reinsert complete mock data.

Usage: python backend/scripts/reset_mock_user.py

Deletes in dependency order:
  PortfolioValuationHistory → TradeJournal → Portfolio → EarningsAlert
  → PriceTarget → DeviceToken → AnalysisHistory → User

Then recreates:
  - 1 User (Saumya Patel, email: snp050106@gmail.com)
  - 1 Portfolio with 12 holdings
  - 90 daily valuation snapshots
  - 28 transactions (24 BUY + 4 SELL)
"""

import sys
import os
import random
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import (
    init_db,
    get_session,
    User,
    Portfolio,
    TradeJournal,
    PortfolioValuationHistory,
    PriceTarget,
    DeviceToken,
    AnalysisHistory,
    EarningsAlert,
    _hash_password,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_EMAIL = "snp050106@gmail.com"
USER_NAME = "saumya"
USER_DISPLAY = "Saumya Patel"
USER_PASSWORD = "StrongPass@123"

# 12 specified holdings
HOLDINGS = [
    # ticker, exchange, company_name, qty, avg_buy, sector
    ("RELIANCE",   "NSE", "Reliance Industries Ltd",     500,  2628.00, "Energy"),
    ("TCS",        "NSE", "Tata Consultancy Services",    200,  3377.00, "IT"),
    ("HDFCBANK",   "NSE", "HDFC Bank Ltd",                150,  1677.00, "Finance"),
    ("INFY",       "NSE", "Infosys Ltd",                  400,  1788.00, "IT"),
    ("TATAMOTORS", "NSE", "Tata Motors Ltd",              300,   876.00, "Auto"),
    ("BAJFINANCE", "NSE", "Bajaj Finance Ltd",             80,  6950.00, "Finance"),
    ("ICICIBANK",  "NSE", "ICICI Bank Ltd",               250,  1020.00, "Finance"),
    ("WIPRO",      "NSE", "Wipro Ltd",                    600,   478.00, "IT"),
    ("AXISBANK",   "NSE", "Axis Bank Ltd",                200,  1087.00, "Finance"),
    ("MARUTI",     "NSE", "Maruti Suzuki India Ltd",        25, 10240.00, "Auto"),
    ("ADANIENT",   "NSE", "Adani Enterprises Ltd",        100,  2890.00, "Infra"),
    ("TITAN",      "NSE", "Titan Company Ltd",              75,  3320.00, "Consumer"),
]

TODAY = datetime.now(tz=None).date()

# Invested value = sum(qty * avg_buy for all holdings)
INVESTED_VALUE = sum(qty * buy for _, _, _, qty, buy, _ in HOLDINGS)

# Valuation trajectory anchor points
START_VALUE = 760_000.0
MID1_VALUE  = 795_000.0
MID2_VALUE  = 840_000.0
DIP_VALUE   = 820_000.0
END_VALUE   = 874_250.0

# Transaction descriptions
BUY_REASONS = [
    "Accumulating on dips — long-term conviction play",
    "Strong QoQ earnings growth — revenue up 18% YoY",
    "Technical breakout above 50-day SMA with volume support",
    "Sector tailwinds — favourable policy changes expected",
    "Adding to core position — rupee cost averaging",
    "Promoter buying detected — insider confidence signal",
    "Peer analysis shows 15% undervaluation vs sector",
    "New product launch catalyst — pre-positioning",
    "Fundamental strength — ROE > 18%, low debt",
    "Market correction created attractive entry point",
    "DII accumulation trend — following smart money",
    "Export order book expansion — revenue visibility improved",
]

SELL_REASONS = [
    "Booking partial profits — up 22% in 3 months, trimming position",
    "Valuation stretched — P/E crossed 2 std dev above 5yr mean",
    "Sector rotation — reducing cyclicals, adding defensives",
    "Stop-loss discipline — protecting capital on weakness",
]

MOODS = ["Confident", "Cautious", "Bullish", "Neutral", "Satisfied"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_weekday(d):
    """Return True if d is Monday-Friday."""
    return d.weekday() < 5


def random_trading_time(d):
    """Return datetime d with a random time between 09:15 and 15:30."""
    if isinstance(d, date) and not isinstance(d, datetime):
        d = datetime.combine(d, datetime.min.time())
    hour = random.randint(9, 14)
    if hour == 9:
        minute = random.randint(15, 59)
    elif hour == 14:
        minute = random.randint(0, 30)
    else:
        minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return d.replace(hour=hour, minute=minute, second=second)


def nearest_weekday(d):
    """If d is a weekend, push back to the previous Friday."""
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def generate_valuation_trajectory():
    """
    Generate 90 daily snapshots following the specified trajectory.
    Returns [(date_str, total_value), ...] in chronological order.
    """
    snapshots = []
    for day in range(90):
        snap_date = TODAY - timedelta(days=90 - day - 1)
        date_str = snap_date.isoformat()

        if day == 0:
            value = START_VALUE
        elif day == 89:
            value = END_VALUE
        else:
            prev_value = snapshots[-1][1]
            noise = random.gauss(0.003, 0.012)
            # Phase-dependent drift
            if day < 30:
                drift = (MID1_VALUE - START_VALUE) / 30 / START_VALUE
            elif day < 60:
                drift = (MID2_VALUE - MID1_VALUE) / 30 / MID1_VALUE
            elif day < 75:
                drift = (DIP_VALUE - MID2_VALUE) / 15 / MID2_VALUE
            else:
                drift = (END_VALUE - DIP_VALUE) / 15 / DIP_VALUE
            value = prev_value * (1 + drift + noise)
            value = max(value, prev_value * 0.97)
            value = min(value, prev_value * 1.03)

        snapshots.append((date_str, round(value, 2)))

    # Pin anchor points exactly
    snapshots[0]  = (snapshots[0][0],  START_VALUE)
    snapshots[29] = (snapshots[29][0], MID1_VALUE)
    snapshots[59] = (snapshots[59][0], MID2_VALUE)
    snapshots[74] = (snapshots[74][0], DIP_VALUE)
    snapshots[89] = (snapshots[89][0], END_VALUE)
    return snapshots


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    init_db()
    random.seed(42)  # Reproducible mock data

    with get_session() as session:
        # ── 0.1: Delete existing records ────────────────────────────────────
        existing_user = session.query(User).filter(
            User.username == USER_NAME
        ).first()

        if existing_user:
            uid = existing_user.id
            session.query(PortfolioValuationHistory).filter(
                PortfolioValuationHistory.user_id == uid
            ).delete()
            session.query(TradeJournal).filter(
                TradeJournal.user_id == uid
            ).delete()
            session.query(EarningsAlert).filter(
                EarningsAlert.user_id == uid
            ).delete()
            session.query(Portfolio).filter(
                Portfolio.user_id == uid
            ).delete()
            session.query(PriceTarget).filter(
                PriceTarget.user_id == uid
            ).delete()
            session.query(DeviceToken).filter(
                DeviceToken.user_id == uid
            ).delete()
            session.query(AnalysisHistory).filter(
                AnalysisHistory.user_id == uid
            ).delete()
            session.delete(existing_user)
            session.commit()
            print(f"[0.1] Deleted all records for user_id={uid}")

        # ── 0.2: Recreate user ──────────────────────────────────────────────
        created_at = TODAY - timedelta(days=90)
        user = User(
            username=USER_NAME,
            password_hash=_hash_password(USER_PASSWORD),
            display_name=USER_DISPLAY,
            created_at=created_at,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"[0.2] Created user: {user.username} (id={user.id})")

        # ── 0.3: Insert holdings ────────────────────────────────────────────
        holdings_added = []
        for ticker, exchange, company, qty, buy_price, sector in HOLDINGS:
            h = Portfolio(
                user_id=user.id,
                ticker=ticker,
                company_name=company,
                shares=float(qty),
                buy_price=float(buy_price),
                group_name="holdings",
                notes=f"Sector: {sector}",
            )
            session.add(h)
            holdings_added.append(h)
        session.commit()
        print(f"[0.3] Added {len(holdings_added)} holdings")

        # ── 0.4: Insert 90 valuation snapshots ──────────────────────────────
        snapshots = generate_valuation_trajectory()
        nifty_base = 22450.0
        for date_str, total_value in snapshots:
            pnl = total_value - INVESTED_VALUE
            pnl_pct = (pnl / INVESTED_VALUE) * 100
            nifty_val = nifty_base * (total_value / START_VALUE) * random.uniform(0.98, 1.02)
            session.add(PortfolioValuationHistory(
                user_id=user.id,
                snapshot_date=date_str,
                total_value=total_value,
                total_invested=INVESTED_VALUE,
                total_pnl=round(pnl, 2),
                pnl_percent=round(pnl_pct, 2),
                nifty_close=round(nifty_val, 2),
            ))
        session.commit()
        print(f"[0.4] Added 90 valuation snapshots "
              f"(start=₹{START_VALUE:,.0f}, end=₹{END_VALUE:,.0f})")

        # ── 0.5: Insert transactions ────────────────────────────────────────
        holding_map = {h.ticker: h for h in holdings_added}
        tx_count = 0

        # 24 BUY transactions (2 per holding = DCA simulation)
        for ticker, exchange, company, qty, avg_buy, sector in HOLDINGS:
            # First buy: ~60 days ago
            buy1_dt = nearest_weekday(TODAY - timedelta(days=random.randint(55, 85)))
            buy1_dt = random_trading_time(buy1_dt)
            buy1_price = round(avg_buy * random.uniform(0.93, 0.98), 2)
            session.add(TradeJournal(
                user_id=user.id, ticker=ticker, action="BUY",
                price_at_time=buy1_price,
                reason_text=random.choice(BUY_REASONS),
                outcome_text=f"Initial entry. Sector: {sector}",
                company_name=company,
                mood=random.choice(["Confident", "Bullish"]),
                created_at=buy1_dt,
            ))
            tx_count += 1

            # Second buy: ~30 days ago
            buy2_dt = nearest_weekday(TODAY - timedelta(days=random.randint(20, 40)))
            buy2_dt = random_trading_time(buy2_dt)
            buy2_price = round(avg_buy * random.uniform(0.96, 1.04), 2)
            session.add(TradeJournal(
                user_id=user.id, ticker=ticker, action="BUY",
                price_at_time=buy2_price,
                reason_text="Adding to position — DCA, conviction intact",
                outcome_text=f"Average buy now ₹{avg_buy:.2f}",
                company_name=company,
                mood=random.choice(["Confident", "Neutral"]),
                created_at=buy2_dt,
            ))
            tx_count += 1

        # 4 SELL transactions (partial profit-taking)
        sell_tickers = random.sample([h[0] for h in HOLDINGS], 4)
        for ticker in sell_tickers:
            holding = holding_map[ticker]
            sell_dt = nearest_weekday(TODAY - timedelta(days=random.randint(5, 25)))
            sell_dt = random_trading_time(sell_dt)
            sell_price = round(holding.buy_price * random.uniform(1.08, 1.25), 2)
            session.add(TradeJournal(
                user_id=user.id, ticker=ticker, action="SELL",
                price_at_time=sell_price,
                reason_text=random.choice(SELL_REASONS),
                outcome_text=f"Partial exit at +{((sell_price/holding.buy_price)-1)*100:.1f}% gain",
                company_name=holding.company_name,
                mood=random.choice(["Satisfied", "Cautious"]),
                created_at=sell_dt,
            ))
            tx_count += 1

        session.commit()
        print(f"[0.5] Added {tx_count} transactions (24 BUY + 4 SELL)")

        # ── Verification ────────────────────────────────────────────────────
        h_count = session.query(Portfolio).filter(
            Portfolio.user_id == user.id
        ).count()
        v_count = session.query(PortfolioValuationHistory).filter(
            PortfolioValuationHistory.user_id == user.id
        ).count()
        t_count = session.query(TradeJournal).filter(
            TradeJournal.user_id == user.id
        ).count()

        print()
        print("=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        print(f"  User:                {user.username} (id={user.id})")
        print(f"  Email:               {USER_EMAIL}")
        print(f"  Holdings:            {h_count} (expected 12)")
        print(f"  Valuation snapshots: {v_count} (expected 90)")
        print(f"  Transactions:        {t_count} (expected 28)")
        print(f"  Invested:            ₹{INVESTED_VALUE:,.2f}")
        print(f"  Current value:       ₹{END_VALUE:,.2f}")
        print(f"  Total P&L:           ₹{END_VALUE - INVESTED_VALUE:,.2f}")
        print(f"  Password:            {USER_PASSWORD}")
        print("=" * 60)

        all_ok = True
        if h_count != 12:
            print(f"  ❌ Holdings: {h_count} (expected 12)")
            all_ok = False
        else:
            print(f"  ✅ Holdings: {h_count}")
        if v_count != 90:
            print(f"  ❌ Snapshots: {v_count} (expected 90)")
            all_ok = False
        else:
            print(f"  ✅ Snapshots: {v_count}")
        if t_count != 28:
            print(f"  ❌ Transactions: {t_count} (expected 28)")
            all_ok = False
        else:
            print(f"  ✅ Transactions: {t_count}")

        if all_ok:
            print("\n✅ ALL CHECKS PASSED")
        else:
            print("\n⚠️  Some checks failed — review above")

        print(f"\nLogin: {USER_EMAIL} / {USER_PASSWORD}")


if __name__ == "__main__":
    main()
