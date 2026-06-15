"""
One-time migration: delete FK-orphaned rows from analysis_jobs and analysis_history.

Orphan rows have user_id values (99999, 99998, 99997, 99996, 99992, etc.) that
reference no entry in the users table — these were created by test runs that
wrote directly to the production DB.

Run once: python3 backend/scripts/migrate_fix_fk_orphans.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import ENGINE, SessionLocal, AnalysisJob, AnalysisHistory, User

def run():
    db = SessionLocal()
    try:
        valid_user_ids = {u.id for u in db.query(User.id).all()}

        # Delete orphaned analysis_jobs
        orphan_jobs = db.query(AnalysisJob).filter(
            AnalysisJob.user_id.isnot(None),
            ~AnalysisJob.user_id.in_(valid_user_ids)
        ).all()
        print(f"Deleting {len(orphan_jobs)} orphaned analysis_jobs rows")
        for row in orphan_jobs:
            db.delete(row)

        # Delete orphaned analysis_history
        orphan_hist = db.query(AnalysisHistory).filter(
            AnalysisHistory.user_id.isnot(None),
            ~AnalysisHistory.user_id.in_(valid_user_ids)
        ).all()
        print(f"Deleting {len(orphan_hist)} orphaned analysis_history rows")
        for row in orphan_hist:
            db.delete(row)

        db.commit()
        print("Done. FK orphans removed.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run()
