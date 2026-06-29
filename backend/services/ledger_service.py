"""
CQRS Ledger Service — event-sourced portfolio write path.

record_transaction()  — inserts an immutable Transaction and immediately
                         re-derives the Portfolio read-model via WAC.
_recalculate_portfolio_snapshot() — pure WAC engine, never called from routers.

Rules (AGENTS.md §3.1):
- No HTTP concerns here; callers handle auth and validation.
- All DB access via the session passed in from get_session() context.
- Floats are rounded to 6 decimal places internally; the read-model stores
  rounded-to-2 values for display.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models.db_models import Portfolio, PortfolioGroup, Transaction


def get_or_create_default_group(session: Session, user_id: int) -> PortfolioGroup:
    """Return the user's default PortfolioGroup, creating one if absent."""
    group = session.query(PortfolioGroup).filter_by(user_id=user_id, is_default=True).first()
    if group is None:
        group = PortfolioGroup(
            user_id=user_id,
            name="Core Holdings",
            is_default=True,
        )
        session.add(group)
        session.flush()
    return group


def record_transaction(
    session: Session,
    user_id: int,
    ticker: str,
    transaction_type: str,
    quantity: float,
    price: float,
    group_id: Optional[int] = None,
    fees: float = 0.0,
    date: Optional[datetime] = None,
    notes: Optional[str] = None,
    company_name: str = "",
    target_price: Optional[float] = None,
    purchase_date: Optional[str] = None,
    is_virtual: bool = False,
) -> Transaction:
    """
    Insert an immutable Transaction and refresh the Portfolio read-model.

    Args:
        session:          Active SQLAlchemy session (from get_session() caller).
        user_id:          Authenticated user.
        ticker:           Normalised ticker symbol (caller must upper().strip()).
        transaction_type: One of BUY | SELL | SPLIT | BONUS | DIVIDEND.
        quantity:         Number of shares (positive).
        price:            Price per share at execution.
        group_id:         PortfolioGroup id; defaults to the user's default group.
        fees:             Brokerage / STT fees (default 0).
        date:             Trade date; defaults to now(UTC).
        notes:            Optional free-text annotation.
        company_name:     Used when creating a new Portfolio row (BUY only).
        target_price:     Optional price target stored on the Portfolio row.
        purchase_date:    Human-readable date string stored on Portfolio row.
        is_virtual:       Paper-trade flag forwarded to Portfolio row.

    Returns:
        The newly created Transaction ORM object (flushed, not yet committed).
    """
    if group_id is None:
        group = get_or_create_default_group(session, user_id)
        group_id = group.id

    tx = Transaction(
        user_id=user_id,
        group_id=group_id,
        ticker=ticker,
        transaction_type=transaction_type.upper(),
        quantity=quantity,
        price=price,
        fees=fees,
        date=date if date is not None else datetime.now(timezone.utc),
        notes=notes,
    )
    session.add(tx)
    session.flush()

    _recalculate_portfolio_snapshot(
        session=session,
        user_id=user_id,
        group_id=group_id,
        ticker=ticker,
        company_name=company_name,
        target_price=target_price,
        purchase_date=purchase_date,
        is_virtual=is_virtual,
    )
    return tx


def _recalculate_portfolio_snapshot(
    session: Session,
    user_id: int,
    group_id: int,
    ticker: str,
    company_name: str = "",
    target_price: Optional[float] = None,
    purchase_date: Optional[str] = None,
    is_virtual: bool = False,
) -> None:
    """
    Recompute the Portfolio read-model for one ticker using WAC.

    WAC rules:
    - BUY:    total_cost += qty * price + fees; total_shares += qty
    - SELL:   total_shares -= qty  (WAC unchanged — cost basis not adjusted)
    - SPLIT:  total_shares *= qty; wac /= qty  (price field holds the split ratio)
    - BONUS:  total_shares += qty  (bonus shares at zero cost)
    - DIVIDEND: no share or cost change — ignored here (recorded for income tracking)

    After iterating all transactions:
    - shares <= 0  → delete Portfolio row (position closed)
    - shares > 0   → UPSERT Portfolio row with new shares + wac
    """
    transactions: list[Transaction] = (
        session.query(Transaction)
        .filter_by(user_id=user_id, group_id=group_id, ticker=ticker)
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    total_shares: float = 0.0
    total_cost: float = 0.0

    for tx in transactions:
        t = tx.transaction_type.upper()
        qty = float(tx.quantity or 0)
        prc = float(tx.price or 0)
        fee = float(tx.fees or 0)

        if t == "BUY":
            total_cost += qty * prc + fee
            total_shares += qty
        elif t == "SELL":
            if total_shares > 0:
                sell_qty = min(qty, total_shares)
                # Proportionally reduce cost basis
                cost_per_share = total_cost / total_shares
                total_cost -= sell_qty * cost_per_share
                total_shares -= sell_qty
        elif t == "SPLIT":
            if qty > 0 and total_shares > 0:
                total_shares *= qty
                # cost basis unchanged; WAC recalculated below
        elif t == "BONUS":
            total_shares += qty
            # bonus shares at zero cost — WAC diluted

    total_shares = round(total_shares, 6)
    wac = round(total_cost / total_shares, 6) if total_shares > 0 else 0.0

    existing: Optional[Portfolio] = session.query(Portfolio).filter_by(
        user_id=user_id, ticker=ticker, group_name="holdings"
    ).first()

    if total_shares <= 0:
        if existing is not None:
            session.delete(existing)
        return

    if existing is not None:
        existing.shares = round(total_shares, 2)
        existing.buy_price = round(wac, 2)
        if group_id is not None:
            existing.group_id = group_id
        if target_price is not None:
            existing.target_price = target_price
    else:
        new_row = Portfolio(
            user_id=user_id,
            ticker=ticker,
            company_name=company_name,
            shares=round(total_shares, 2),
            buy_price=round(wac, 2),
            group_name="holdings",
            group_id=group_id,
            target_price=target_price,
            purchase_date=purchase_date,
            is_virtual=is_virtual,
        )
        session.add(new_row)


def get_transactions_for_ticker(user_id: int, ticker: str) -> list[dict]:
    """Return all transactions for a user+ticker, newest first."""
    from database import get_session
    with get_session() as session:
        rows = (
            session.query(Transaction)
            .filter_by(user_id=user_id, ticker=ticker)
            .order_by(Transaction.date.desc())
            .all()
        )
        return [
            {
                "id": t.id,
                "ticker": t.ticker,
                "transaction_type": t.transaction_type,
                "quantity": t.quantity,
                "price": t.price,
                "fees": t.fees,
                "date": t.date.isoformat() if t.date else None,
                "notes": t.notes,
            }
            for t in rows
        ]
