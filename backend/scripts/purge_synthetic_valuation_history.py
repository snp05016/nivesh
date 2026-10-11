"""List, and with --apply delete, valuation-history rows back-filled by GET valuation-history.

CMON-05 / MATH-09: before REL-10, a user with no snapshots got up to 30 rows written in
one burst from TODAY's share counts and cost basis times past closes. Those rows have no
nifty_close and were created more than a day after their snapshot_date. The nightly
writer (services/portfolio_snapshot.py) stamps the current date, so its rows are never
more than a day older than their created_at. The newest back-filled row of each burst is
dated within a day of its creation and is left alone: it matches what the nightly job
would have written for that day.

Run from backend/ after taking a backup; dry run first, review, then apply:
    ../venv/bin/python scripts/backup_db.py
    ../venv/bin/python scripts/purge_synthetic_valuation_history.py
    ../venv/bin/python scripts/purge_synthetic_valuation_history.py --apply
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from models.db_models import PortfolioValuationHistory  # noqa: E402


def is_synthetic(row) -> bool:
    """True for a back-filled row: no NIFTY close and written over a day after its date."""
    if row.nifty_close is not None or row.created_at is None:
        return False
    try:
        snap = date.fromisoformat(str(row.snapshot_date)[:10])
    except ValueError:
        return False
    return row.created_at.date() > snap + timedelta(days=1)


def select_synthetic_rows(session) -> list[PortfolioValuationHistory]:
    candidates = (
        session.query(PortfolioValuationHistory)
        .filter(PortfolioValuationHistory.nifty_close.is_(None))
        .order_by(PortfolioValuationHistory.user_id, PortfolioValuationHistory.snapshot_date)
        .all()
    )
    return [row for row in candidates if is_synthetic(row)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge back-filled portfolio valuation-history rows.")
    parser.add_argument("--apply", action="store_true", help="delete the rows (default: dry run)")
    args = parser.parse_args()

    # Resolve DATABASE_URL like the service does (WorkingDirectory=backend, backend/.env).
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env", override=False)
    from database import get_session  # reads DATABASE_URL at import, so after .env

    with get_session() as session:
        rows = select_synthetic_rows(session)
        dates: dict[int, list[str]] = {}
        for row in rows:
            dates.setdefault(int(row.user_id), []).append(str(row.snapshot_date))  # type: ignore[arg-type]
        for user_id, ds in sorted(dates.items()):
            print(f"user {user_id}: {len(ds)} row(s), snapshot_date {min(ds)} .. {max(ds)}")
        print(f"{len(rows)} back-filled portfolio_valuation_history row(s) found.")
        if not args.apply:
            print("Dry run: nothing deleted. Re-run with --apply to delete them.")
            return 0
        for row in rows:
            session.delete(row)
        session.commit()
        print(f"Deleted {len(rows)} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
