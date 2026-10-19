"""Compare every holdings row with its ledger replay; with --apply, fix the ledger.

For each (user, ticker) with a holdings row or ledger rows (stocks and funds),
the displayed holding (portfolio, group_name 'holdings') is compared with the
replay of portfolio_transactions (services.ledger_service._replay). Kinds:

  row_without_ledger    holding shown, no ledger rows
  ledger_without_row    ledger holds shares, no holding shown
  quantity_mismatch     shares differ by more than 1e-6
  cost_mismatch         same shares, average cost differs by more than 0.01
  duplicate_auto_split  repeated auto corporate-action SPLITs (same date and
                        ratio) and the holding disagrees with the replay

--apply fixes, one (user, ticker) per transaction:
  row_without_ledger    opening BUY (ledger_service._reconcile_with_read_model)
  ledger_without_row    ADJUST to 0 (the user sees no holding, so none comes back)
  quantity/cost         ADJUST to the displayed holding
  duplicate_auto_split  recompute only: the deduplicated replay is right and the
                        displayed holding is wrong

The CSV (user_id, ticker, kind, read_shares, read_avg_cost, ledger_shares,
ledger_avg_cost) goes to --out or stdout; counts go to stderr. Only ids,
tickers and numbers are written.

Run from backend/ on a restored backup first, review the CSV, then on
production after a backup (OPS-03):
    ../venv/bin/python scripts/reconcile_ledger.py --out /tmp/reconcile.csv
    ../venv/bin/python scripts/reconcile_ledger.py --apply --out /tmp/applied.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, cast

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.env import load_backend_env  # noqa: E402

FIELDS = ["user_id", "ticker", "kind", "read_shares", "read_avg_cost", "ledger_shares", "ledger_avg_cost"]
RESTATE_NOTE = "reconcile: restated to displayed holding"
_QTY_TOL = 1e-6
_COST_TOL = 0.01


def _pairs(session, user_id: Optional[int]) -> list[tuple[int, str]]:
    from models.db_models import Portfolio, Transaction

    rows = session.query(Portfolio.user_id, Portfolio.ticker).execution_options(include_mf=True).filter(
        Portfolio.group_name == "holdings"
    )
    ledger = session.query(Transaction.user_id, Transaction.ticker)
    if user_id is not None:
        rows = rows.filter(Portfolio.user_id == user_id)
        ledger = ledger.filter(Transaction.user_id == user_id)
    found = {(int(u), str(t)) for u, t in rows.distinct().all()}
    found |= {(int(u), str(t)) for u, t in ledger.distinct().all()}
    return sorted(found)


def check_position(session, user_id: int, ticker: str) -> Optional[dict]:
    """The discrepancy of one (user, ticker) as a CSV row dict, or None when consistent."""
    from services.ledger_service import _holdings_row, _ledger_rows, _replay, dedupe_auto_splits

    row = _holdings_row(session, user_id, ticker)
    ledger = _ledger_rows(session, user_id, ticker)
    read_shares = float(cast(float, row.shares) or 0.0) if row is not None else 0.0
    read_avg = float(cast(float, row.buy_price) or 0.0) if row is not None else 0.0
    ledger_shares, ledger_avg = _replay(ledger) if ledger else (0.0, 0.0)

    if row is not None and not ledger:
        kind = "row_without_ledger" if read_shares > 0 else None
    elif row is None:
        kind = "ledger_without_row" if ledger_shares > _QTY_TOL else None
    elif abs(read_shares - ledger_shares) > _QTY_TOL:
        kind = "quantity_mismatch"
    elif ledger_shares > 0 and abs(read_avg - ledger_avg) > _COST_TOL:
        kind = "cost_mismatch"
    else:
        kind = None
    if kind in ("quantity_mismatch", "cost_mismatch") and len(dedupe_auto_splits(ledger)) < len(ledger):
        kind = "duplicate_auto_split"
    if kind is None:
        return None
    return {
        "user_id": user_id, "ticker": ticker, "kind": kind,
        "read_shares": read_shares, "read_avg_cost": read_avg,
        "ledger_shares": ledger_shares, "ledger_avg_cost": ledger_avg,
    }


def apply_fix(session, item: dict) -> None:
    """Fix one reported discrepancy in `session` (flushes; the caller commits)."""
    from models.db_models import Transaction
    from services.ledger_service import (
        _as_utc, _holdings_row, _ledger_rows, _lock_position, _recalculate_portfolio_snapshot,
        _reconcile_with_read_model, get_or_create_default_group,
    )

    user_id, ticker, kind = int(item["user_id"]), str(item["ticker"]), item["kind"]
    _lock_position(session, user_id, ticker)
    group_id = cast(int, get_or_create_default_group(session, user_id).id)
    now = datetime.now(timezone.utc)
    if kind == "row_without_ledger":
        _reconcile_with_read_model(session, user_id, group_id, ticker, now)
    elif kind in ("ledger_without_row", "quantity_mismatch", "cost_mismatch"):
        row = _holdings_row(session, user_id, ticker)
        ledger = _ledger_rows(session, user_id, ticker)
        # After the whole ledger, so it restates the position as it is now.
        when = max([now] + [_as_utc(cast(datetime, t.date)) for t in ledger if t.date is not None])
        if row is None:
            qty, price, asset_class = 0.0, 0.0, cast(Optional[str], ledger[-1].asset_class) if ledger else None
        else:
            qty, price = float(cast(float, row.shares)), float(cast(float, row.buy_price))
            asset_class = cast(Optional[str], row.asset_class)
        session.add(Transaction(
            user_id=user_id, group_id=group_id, ticker=ticker, transaction_type="ADJUST",
            quantity=qty, price=price, fees=0.0, date=when, notes=RESTATE_NOTE,
            asset_class=asset_class or "EQ",
        ))
        session.flush()
    _recalculate_portfolio_snapshot(session=session, user_id=user_id, group_id=group_id, ticker=ticker)
    session.flush()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare holdings with the transaction ledger.")
    parser.add_argument("--user-id", type=int, default=None, help="only this user")
    parser.add_argument("--apply", action="store_true", help="fix the ledger (default: report only)")
    parser.add_argument("--out", default=None, help="CSV path (default: stdout)")
    args = parser.parse_args(argv)

    load_backend_env()
    import database

    with database.get_session() as session:
        pairs = _pairs(session, args.user_id)
        items = [item for item in (check_position(session, u, t) for u, t in pairs) if item is not None]

    applied = failed = 0
    if args.apply:
        for item in items:
            with database.get_session() as session:
                try:
                    apply_fix(session, item)
                    session.commit()
                    applied += 1
                except Exception as exc:  # one bad position must not stop the rest
                    session.rollback()
                    failed += 1
                    print(f"failed: user {item['user_id']} {item['ticker']}: {type(exc).__name__}", file=sys.stderr)

    out = open(args.out, "w", newline="") if args.out else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(items)
    finally:
        if args.out:
            out.close()

    counts = Counter(item["kind"] for item in items)
    summary = ", ".join(f"{kind}={n}" for kind, n in sorted(counts.items())) or "none"
    print(f"positions checked: {len(pairs)}; discrepancies: {summary}", file=sys.stderr)
    if args.apply:
        print(f"applied: {applied}; failed: {failed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
