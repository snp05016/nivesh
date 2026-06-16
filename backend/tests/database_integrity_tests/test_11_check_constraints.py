"""
test_11_check_constraints.py
============================
Boundary-value tests for every CheckConstraint in db_models.py.
Tests both the rejection boundary (value AT the limit) and
the acceptance boundary (value just beyond the limit).

Constraints:
- ck_portfolio_shares_positive: shares > 0 OR group_name='watchlist'
- ck_portfolio_buy_price_positive: buy_price > 0 OR group_name='watchlist'
- ck_price_targets_positive: target_price > 0
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from _base import TestRunner, User, Portfolio, PriceTarget
from sqlalchemy.exc import IntegrityError


def run():
    runner = TestRunner("11_check_constraints")
    runner.setup()
    session = runner.session

    u = User(username="check_constraint_user", password_hash="x" * 60, display_name="CC User")
    session.add(u)
    session.commit()
    uid = u.id

    # =========================================================
    # ck_portfolio_shares_positive: shares > 0 OR group_name='watchlist'
    # =========================================================

    # --- Reject: shares=0 in holdings
    try:
        session.add(Portfolio(user_id=uid, ticker="TST001", company_name="T", shares=0.0, buy_price=100.0, group_name="holdings"))
        session.commit()
        runner.fail("ck_shares_zero_holdings", "shares=0 in holdings was accepted (should be rejected)")
    except IntegrityError:
        session.rollback()
        runner.ok("ck_shares_zero_holdings", "shares=0 in holdings correctly rejected")

    # --- Reject: shares=-1 in holdings
    try:
        session.add(Portfolio(user_id=uid, ticker="TST002", company_name="T", shares=-1.0, buy_price=100.0, group_name="holdings"))
        session.commit()
        runner.fail("ck_shares_negative_holdings", "shares=-1 in holdings was accepted (should be rejected)")
    except IntegrityError:
        session.rollback()
        runner.ok("ck_shares_negative_holdings", "shares=-1 in holdings correctly rejected")

    # --- Accept: shares=0.001 in holdings (smallest positive)
    try:
        session.add(Portfolio(user_id=uid, ticker="TST003", company_name="T", shares=0.001, buy_price=100.0, group_name="holdings"))
        session.commit()
        runner.ok("ck_shares_tiny_positive_accepted", "shares=0.001 in holdings accepted")
    except IntegrityError as e:
        session.rollback()
        runner.fail("ck_shares_tiny_positive_accepted", f"shares=0.001 was wrongly rejected: {e}")
    except Exception as e:
        session.rollback()
        runner.fail("ck_shares_tiny_positive_accepted", str(e), e)

    # --- Accept: shares=0 in watchlist
    try:
        session.add(Portfolio(user_id=uid, ticker="TST004", company_name="T", shares=0.0, buy_price=0.0, group_name="watchlist"))
        session.commit()
        runner.ok("ck_shares_zero_watchlist_accepted", "shares=0 in watchlist correctly accepted")
    except Exception as e:
        session.rollback()
        runner.fail("ck_shares_zero_watchlist_accepted", f"shares=0 in watchlist was wrongly rejected: {e}", e)

    # =========================================================
    # ck_portfolio_buy_price_positive: buy_price > 0 OR group_name='watchlist'
    # =========================================================

    # --- Reject: buy_price=0 in holdings
    try:
        session.add(Portfolio(user_id=uid, ticker="TST005", company_name="T", shares=10.0, buy_price=0.0, group_name="holdings"))
        session.commit()
        runner.fail("ck_buy_price_zero_holdings", "buy_price=0 in holdings was accepted (division by zero risk in P&L%)")
    except IntegrityError:
        session.rollback()
        runner.ok("ck_buy_price_zero_holdings", "buy_price=0 in holdings correctly rejected")

    # --- Reject: buy_price=-500 in holdings
    try:
        session.add(Portfolio(user_id=uid, ticker="TST006", company_name="T", shares=10.0, buy_price=-500.0, group_name="holdings"))
        session.commit()
        runner.fail("ck_buy_price_negative_holdings", "buy_price=-500 in holdings was accepted")
    except IntegrityError:
        session.rollback()
        runner.ok("ck_buy_price_negative_holdings", "buy_price=-500 in holdings correctly rejected")

    # --- Accept: buy_price=0.01 in holdings
    try:
        session.add(Portfolio(user_id=uid, ticker="TST007", company_name="T", shares=10.0, buy_price=0.01, group_name="holdings"))
        session.commit()
        runner.ok("ck_buy_price_tiny_positive_accepted", "buy_price=0.01 in holdings accepted")
    except IntegrityError as e:
        session.rollback()
        runner.fail("ck_buy_price_tiny_positive_accepted", f"buy_price=0.01 was wrongly rejected: {e}")
    except Exception as e:
        session.rollback()
        runner.fail("ck_buy_price_tiny_positive_accepted", str(e), e)

    # =========================================================
    # ck_price_targets_positive: target_price > 0
    # =========================================================

    # --- Reject: target_price=0
    try:
        session.add(PriceTarget(user_id=uid, ticker="TGTTST", target_price=0.0, direction="BUY"))
        session.commit()
        runner.fail("ck_target_price_zero", "target_price=0 was accepted (alerts will fire on any price movement)")
    except IntegrityError:
        session.rollback()
        runner.ok("ck_target_price_zero", "target_price=0 correctly rejected")

    # --- Reject: target_price=-100
    try:
        session.add(PriceTarget(user_id=uid, ticker="TGTTST2", target_price=-100.0, direction="SELL"))
        session.commit()
        runner.fail("ck_target_price_negative", "target_price=-100 was accepted")
    except IntegrityError:
        session.rollback()
        runner.ok("ck_target_price_negative", "target_price=-100 correctly rejected")

    # --- Accept: target_price=0.01
    try:
        session.add(PriceTarget(user_id=uid, ticker="TGTTST3", target_price=0.01, direction="BUY"))
        session.commit()
        runner.ok("ck_target_price_tiny_positive", "target_price=0.01 accepted")
    except IntegrityError as e:
        session.rollback()
        runner.fail("ck_target_price_tiny_positive", f"target_price=0.01 wrongly rejected: {e}")
    except Exception as e:
        session.rollback()
        runner.fail("ck_target_price_tiny_positive", str(e), e)

    # --- Accept: very large target_price (no upper bound)
    try:
        session.add(PriceTarget(user_id=uid, ticker="TGTTST4", target_price=9_999_999.99, direction="BUY"))
        session.commit()
        runner.ok("ck_target_price_very_large", "target_price=9,999,999.99 accepted (no upper bound constraint)")
    except Exception as e:
        session.rollback()
        runner.fail("ck_target_price_very_large", f"Large target_price unexpectedly rejected: {e}", e)

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "db_integrity_latest.txt")
    runner.teardown()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
