"""
Phase 2 backfill: convert legacy Portfolio snapshots to Transaction ledger entries.

Idempotent: safe to run multiple times. A holding whose (user, ticker)
already has ledger rows is skipped. Backfilled rows go into the user's single
default group (created as 'Legacy Holdings' only if the user has none), never a
second default group (DB-09).

Run from backend/ directory:
    ../venv/bin/python -m scripts.migrate_ledger
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from database import get_session
from models.db_models import Portfolio, Transaction
from services.ledger_service import get_or_create_default_group


def backfill_user(session, uid: int) -> int:
    """
    Backfill one user's legacy Portfolio rows into the Transaction ledger.

    Returns the number of transactions inserted (0 if already done — idempotent).
    Callers are responsible for calling session.commit().
    """
    holdings = (
        session.query(Portfolio)
        .filter(
            Portfolio.user_id == uid,
            Portfolio.group_name != "watchlist",
            Portfolio.shares > 0,
        )
        .all()
    )
    ledgered = {
        row[0] for row in session.query(Transaction.ticker).filter(Transaction.user_id == uid).distinct()
    }
    holdings = [h for h in holdings if h.ticker not in ledgered]
    if not holdings:
        return 0  # nothing left to backfill

    group = get_or_create_default_group(session, uid, name="Legacy Holdings")

    inserted = 0
    for h in holdings:
        tx_date = h.created_at if h.created_at is not None else datetime.now(timezone.utc)
        tx = Transaction(
            user_id=uid,
            group_id=group.id,
            ticker=h.ticker,
            transaction_type="BUY",
            quantity=h.shares,
            price=h.buy_price,
            fees=0.0,
            date=tx_date,
            notes="Legacy migration backfill",
        )
        session.add(tx)
        h.group_id = group.id  # type: ignore[assignment]
        inserted += 1

    return inserted


def main() -> None:
    total_transactions = 0

    with get_session() as session:
        user_ids = [row[0] for row in session.query(Portfolio.user_id).distinct().all()]

    print(f"Found {len(user_ids)} user(s) to backfill.")

    for uid in user_ids:
        with get_session() as session:
            inserted = backfill_user(session, uid)
            if inserted == 0:
                print(f"User {uid}: already backfilled. Skipping.")
            else:
                session.commit()
                total_transactions += inserted
                print(f"User {uid}: inserted {inserted} transactions.")

    print(f"\nDone. Total transactions inserted: {total_transactions}")


if __name__ == "__main__":
    main()
