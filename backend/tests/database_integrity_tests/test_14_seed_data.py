"""
test_14_seed_data.py
====================
Tests the database seed data (init_db) behavior:
- Seed users are created (saumya, nirav, ankur)
- Nirav's portfolio holdings are seeded with correct values
- Running init_db() twice is idempotent (does not duplicate data)
- Password hashes are valid bcrypt format
- All seeded tickers match the expected portfolio positions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from _base import TestRunner, make_test_engine, Base, User, Portfolio
from sqlalchemy.orm import sessionmaker

EXPECTED_SEED_USERS = ["saumya", "nirav", "ankur"]
EXPECTED_NIRAV_TICKERS = {
    "BGRENERGY", "MCLEODRUSS", "JITFINFRA", "CDSL", "GAUDIUMIVF",
    "SBIN", "TATAELXSI", "OMPOWER", "AVANTEL", "ABBOTINDIA",
    "SUZLON", "POLYCAB", "HAL", "IDEA", "APOLLO", "BSE",
}


def run():
    runner = TestRunner("14_seed_data")

    # Use a fresh in-memory DB and run init_db against it
    engine = make_test_engine()
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Patch the DATABASE_URL so init_db uses our engine
    import database as db_module
    original_engine = db_module.ENGINE
    original_session_local = db_module.SessionLocal
    db_module.ENGINE = engine
    db_module.SessionLocal = SessionFactory

    try:
        from database import init_db
        init_db()

        session = SessionFactory()

        # ---- All seed users created
        for username in EXPECTED_SEED_USERS:
            user = session.query(User).filter_by(username=username).first()
            if user:
                runner.ok(f"seed_user_{username}", f"User '{username}' seeded with id={user.id}")
            else:
                runner.fail(
                    f"seed_user_{username}",
                    f"Seed user '{username}' not found after init_db(). "
                    f"Check SEED_USERS list in database.py."
                )

        # ---- Nirav's holdings
        nirav = session.query(User).filter_by(username="nirav").first()
        if nirav:
            holdings = session.query(Portfolio).filter_by(
                user_id=nirav.id, group_name="holdings"
            ).all()
            seeded_tickers = {h.ticker for h in holdings}

            if seeded_tickers == EXPECTED_NIRAV_TICKERS:
                runner.ok("nirav_portfolio_tickers", f"All {len(seeded_tickers)} holdings seeded correctly")
            else:
                missing = EXPECTED_NIRAV_TICKERS - seeded_tickers
                extra = seeded_tickers - EXPECTED_NIRAV_TICKERS
                runner.fail(
                    "nirav_portfolio_tickers",
                    f"Portfolio mismatch. Missing: {missing}. Extra: {extra}. "
                    f"Check DAD_HOLDINGS list in database.py."
                )

            # ---- Verify shares and buy_price are positive for all holdings
            for h in holdings:
                if h.shares <= 0:
                    runner.fail(
                        f"nirav_holding_shares_{h.ticker}",
                        f"Seeded holding {h.ticker} has shares={h.shares} (not positive)"
                    )
                if h.buy_price <= 0:
                    runner.fail(
                        f"nirav_holding_buy_price_{h.ticker}",
                        f"Seeded holding {h.ticker} has buy_price={h.buy_price} (not positive)"
                    )
            runner.ok("nirav_holdings_positive_values", "All seeded holdings have positive shares and buy_price")
        else:
            runner.fail("nirav_portfolio_tickers", "User 'nirav' not found — cannot check portfolio")

        # ---- Password hash format is bcrypt
        for username in EXPECTED_SEED_USERS:
            u = session.query(User).filter_by(username=username).first()
            if u and u.password_hash.startswith("$2"):
                runner.ok(f"seed_user_bcrypt_{username}", "Password hash is bcrypt format")
            elif u:
                runner.fail(
                    f"seed_user_bcrypt_{username}",
                    f"Password hash for '{username}' is NOT bcrypt (starts with '{u.password_hash[:5]}'). "
                    f"verify_password() will use the wrong comparison algorithm and authentication will fail."
                )

        session.close()

        # ---- Idempotency: running init_db() again should not add duplicate rows
        init_db()
        session2 = SessionFactory()
        user_count = session2.query(User).count()
        session2.close()

        if user_count == len(EXPECTED_SEED_USERS):
            runner.ok("init_db_idempotent", f"init_db() is idempotent: still {user_count} users after second call")
        else:
            runner.fail(
                "init_db_idempotent",
                f"init_db() is NOT idempotent: user_count={user_count} after second call "
                f"(expected {len(EXPECTED_SEED_USERS)}). "
                f"Running init_db() on app restart will duplicate seed data."
            )

    finally:
        db_module.ENGINE = original_engine
        db_module.SessionLocal = original_session_local
        engine.dispose()

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
