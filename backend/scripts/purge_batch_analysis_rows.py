"""List, and with --apply delete, analysis rows written by the removed /analyze/batch route.

LLM-03: that route asked Sonnet to "analyse" a bare ticker string with no market data and
saved the reply as the shared report via save_analysis(session, None, ticker, analysis).
Its rows therefore have no user, no raw_output and scan_type 'standard', and their
full_json has neither "confidence_breakdown" (the orchestrator's confidence fusion) nor
"_cache_type" (stamped by every orchestrator save path before it saves).

Run from backend/ after taking a backup; dry run first, review, then apply:
    ../venv/bin/python scripts/backup_db.py
    ../venv/bin/python scripts/purge_batch_analysis_rows.py
    ../venv/bin/python scripts/purge_batch_analysis_rows.py --apply
"""
import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from models.db_models import AnalysisHistory  # noqa: E402


def select_batch_rows(session) -> list[AnalysisHistory]:
    """Rows with the batch route's footprint (see module docstring), oldest first per ticker."""
    return (
        session.query(AnalysisHistory)
        .filter(
            AnalysisHistory.user_id.is_(None),
            AnalysisHistory.raw_output.is_(None),
            AnalysisHistory.scan_type == "standard",
            ~AnalysisHistory.full_json.like('%"confidence_breakdown"%'),
            ~AnalysisHistory.full_json.like('%"_cache_type"%'),
        )
        .order_by(AnalysisHistory.ticker, AnalysisHistory.created_at)
        .all()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge analysis rows saved by the removed /analyze/batch route.")
    parser.add_argument("--apply", action="store_true", help="delete the rows (default: dry run)")
    args = parser.parse_args()

    # Resolve DATABASE_URL like the service does (WorkingDirectory=backend, backend/.env).
    os.chdir(BACKEND)
    from dotenv import load_dotenv
    load_dotenv(BACKEND / ".env", override=False)
    from database import get_session  # reads DATABASE_URL at import, so after .env

    with get_session() as session:
        rows = select_batch_rows(session)
        dates: dict[str, list[str]] = {}
        for row in rows:
            dates.setdefault(str(row.ticker), []).append(str(row.analysis_date))
        for ticker, ds in sorted(dates.items()):
            print(f"{ticker}: {len(ds)} row(s), analysis_date {min(ds)} .. {max(ds)}")
        print(f"{len(rows)} batch-written analysis_history row(s) found.")
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
