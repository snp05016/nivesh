"""
CQRS Ledger Service — event-sourced portfolio write path.

record_transaction()  — inserts an immutable Transaction and immediately
                         re-derives the Portfolio read-model via WAC.
adjust_position() / close_position() — ledger-backed edit/remove (internal
                         ADJUST entry: absolute restatement of shares @ price,
                         never accepted from clients).
_recalculate_portfolio_snapshot() — pure WAC engine, never called from routers.

Holdings rows written outside the ledger (seeds, scripts, the pre-ledger API,
pre-fix PUT/DELETE) are reconciled on their next ledger write: an opening BUY
when no ledger exists, an internal ADJUST when the replay disagrees with the
row, so a replay never overwrites, deletes or resurrects them.

Rules (AGENTS.md §3.1):
- No HTTP concerns here; callers handle auth and validation.
- All DB access via the session passed in from get_session() context.
- Floats are rounded to 6 decimal places; the read-model stores them at that
  precision (display rounding happens in API responses).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, cast

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.db_models import Portfolio, PortfolioGroup, Transaction


class LedgerError(ValueError):
    """A write that would make the ledger inconsistent (e.g. selling more
    shares than held on the trade date). Routers map it to HTTP 422."""


def get_or_create_default_group(
    session: Session, user_id: int, name: str = "Core Holdings"
) -> PortfolioGroup:
    """Return the user's default PortfolioGroup (lowest id; at most one exists,
    uq_portfolio_groups_one_default), creating one named `name` if absent."""
    group = (
        session.query(PortfolioGroup)
        .filter_by(user_id=user_id, is_default=True)
        .order_by(PortfolioGroup.id.asc())
        .first()
    )
    if group is None:
        group = PortfolioGroup(
            user_id=user_id,
            name=name,
            is_default=True,
        )
        session.add(group)
        session.flush()
    return group


def _as_utc(dt: datetime) -> datetime:
    """Naive DB datetimes are UTC by convention; make them comparable with aware ones."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def parse_trade_date(value: Optional[str]) -> Optional[datetime]:
    """purchase_date ('YYYY-MM-DD', or legacy 'dd-MMM-yyyy') -> aware UTC midnight.

    None/blank -> None. ValueError when unparseable or in the future (one day
    of slack: IST runs ahead of UTC).
    """
    if value is None or not value.strip():
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y"):
        try:
            parsed = datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            continue
    else:
        raise ValueError("Invalid purchase_date. Use YYYY-MM-DD.")
    if parsed.date() > (datetime.now(timezone.utc) + timedelta(days=1)).date():
        raise ValueError("purchase_date cannot be in the future.")
    return parsed


def _lock_position(session: Session, user_id: int, ticker: str) -> None:
    """Serialise ledger writes per (user, ticker) for the rest of the transaction."""
    # ponytail: Postgres only (transaction-scoped advisory lock). SQLite already
    # serialises writers; a stale concurrent writer gets SQLITE_BUSY ("database is
    # locked") rather than a double-apply.
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return
    digest = hashlib.blake2b(f"{user_id}:{ticker}".encode(), digest_size=8).digest()
    session.execute(
        text("SELECT pg_advisory_xact_lock(:k)"),
        {"k": int.from_bytes(digest, "big", signed=True)},
    )


def _ledger_rows(session: Session, user_id: int, ticker: str) -> list[Transaction]:
    """The (user, ticker) ledger across all groups: the holdings read-model has
    one row per (user, ticker), so every group's lots replay into it."""
    return (
        session.query(Transaction)
        .filter_by(user_id=user_id, ticker=ticker)
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )


def _replay(
    transactions: list[Transaction], strict_from: Optional[Transaction] = None
) -> tuple[float, float]:
    """WAC replay of a date-ordered ledger → (shares, wac). Rules in
    _recalculate_portfolio_snapshot's docstring.

    From `strict_from` (the trade being written) onwards, a SELL of more
    shares than held at that point raises LedgerError: that rejects backdated
    SELLs and SELLs that would invalidate a later one. Earlier rows keep the
    legacy clamp so an old inconsistent ledger does not block every new write.
    """
    total_shares: float = 0.0
    total_cost: float = 0.0
    strict = False

    for tx in transactions:
        strict = strict or (strict_from is not None and tx is strict_from)
        t = tx.transaction_type.upper()
        qty = cast(float, tx.quantity) if tx.quantity is not None else 0.0
        prc = cast(float, tx.price) if tx.price is not None else 0.0
        fee = cast(float, tx.fees) if tx.fees is not None else 0.0

        if t == "BUY":
            total_cost += qty * prc + fee
            total_shares += qty
        elif t == "SELL":
            if strict and qty > total_shares + 1e-9:
                when = _as_utc(tx.date).date().isoformat() if tx.date is not None else "that date"  # type: ignore[arg-type]
                raise LedgerError(
                    f"Cannot SELL {qty} of {tx.ticker}: only {round(total_shares, 4)} shares held on {when}."
                )
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
        elif t == "ADJUST":
            total_shares = qty
            total_cost = qty * prc

    total_shares = round(total_shares, 6)
    wac = round(total_cost / total_shares, 6) if total_shares > 0 else 0.0
    return total_shares, wac


def _reconcile_with_read_model(
    session: Session, user_id: int, group_id: int, ticker: str, as_of: datetime
) -> None:
    """Make the ledger agree with the holdings row before a new ledger write.

    The read-model was also written outside the ledger (seeds, scripts, the
    pre-ledger API, pre-fix PUT/DELETE, populate_portfolio). Replaying only the
    ledger would then overwrite, delete or resurrect the position. So:

    - no ledger rows, holdings row with shares > 0 → opening BUY for the row's
      shares @ buy_price, dated before both the row and the new trade;
    - ledger rows exist but their replay disagrees with the row (row absent while
      the replay holds shares, or shares/buy_price differ at 2 dp) → internal
      ADJUST restating to the row (0 when absent), dated `as_of` so it replays
      right before the new trade (same timestamp, lower id).

    Keyed like the replay (user, ticker); a no-op when the two agree. Callers
    hold _lock_position, so concurrent first writes cannot both seed.
    """
    row = session.query(Portfolio).filter_by(
        user_id=user_id, ticker=ticker, group_name="holdings"
    ).first()
    row_shares = float(cast(float, row.shares) or 0.0) if row is not None else 0.0
    row_price = float(cast(float, row.buy_price) or 0.0) if row is not None else 0.0
    transactions = _ledger_rows(session, user_id, ticker)

    if not transactions:
        if row is None or row_shares <= 0:
            return
        opened = _as_utc(as_of)
        created_at = cast(Optional[datetime], row.created_at)
        if created_at is not None:
            opened = min(opened, _as_utc(created_at))
        tx_type, qty, prc = "BUY", row_shares, row_price
        when, note = opened - timedelta(seconds=1), "Opening balance (pre-ledger holding)"
    else:
        shares, wac = _replay(transactions)
        if row is None:
            if shares <= 0:
                return
            qty = prc = 0.0
        elif round(shares, 2) == round(row_shares, 2) and (
            shares <= 0 or round(wac, 2) == round(row_price, 2)
        ):
            return
        else:
            qty, prc = max(row_shares, 0.0), row_price
        tx_type, when, note = "ADJUST", as_of, "Reconciled to holdings (edited outside the ledger)"

    session.add(Transaction(
        user_id=user_id,
        group_id=group_id,
        ticker=ticker,
        transaction_type=tx_type,
        quantity=qty,
        price=prc,
        fees=0.0,
        date=when,
        notes=note,
    ))
    session.flush()


def record_transaction(
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
    client_request_id: Optional[str] = None,
) -> Transaction:
    """
    Insert an immutable Transaction and refresh the Portfolio read-model.

    Args:
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
        client_request_id: Client Idempotency-Key; a repeat returns the first
                          Transaction instead of inserting another.

    Returns:
        The committed Transaction (the existing one for a repeated
        client_request_id).

    Raises:
        LedgerError: a SELL exceeds the shares held on its trade date, or
                     invalidates a later SELL. Nothing is written.
    """
    from database import get_session
    with get_session() as session:
        _lock_position(session, user_id, ticker)
        if client_request_id is not None:
            existing_tx = _find_client_request(session, user_id, client_request_id)
            if existing_tx is not None:
                return existing_tx

        resolved_group_id: int
        if group_id is None:
            group = get_or_create_default_group(session, user_id)
            resolved_group_id = cast(int, group.id)
        else:
            resolved_group_id = group_id

        now = datetime.now(timezone.utc)
        # Never future-date a trade: adjust/close date their ADJUST at now(), so a
        # future-dated BUY would replay after it and resurrect a removed holding.
        tx_date = min(_as_utc(date), now) if date is not None else now
        # A back-dated trade keeps its trade date: the replay runs in date order
        # and validates it strictly (_replay), so splits and SELLs see real chronology.
        # A reconcile ADJUST restates the row as it is now, so it goes after the
        # whole ledger, not at the trade's date.
        latest = session.query(Transaction.date).filter_by(
            user_id=user_id, ticker=ticker
        ).order_by(Transaction.date.desc()).first()
        reconcile_at = tx_date
        if latest is not None and latest[0] is not None:
            reconcile_at = max(tx_date, _as_utc(latest[0]))
        _reconcile_with_read_model(session, user_id, resolved_group_id, ticker, reconcile_at)
        # ponytail: ADJUST is an absolute restatement (edit/remove), so a trade dated
        # before it would be silently absorbed; such trades are dated at the restatement.
        last_adjust = session.query(Transaction.date).filter_by(
            user_id=user_id, ticker=ticker, transaction_type="ADJUST"
        ).order_by(Transaction.date.desc()).first()
        if last_adjust is not None and last_adjust[0] is not None and tx_date < _as_utc(last_adjust[0]):
            tx_date = _as_utc(last_adjust[0])

        tx = Transaction(
            user_id=user_id,
            group_id=resolved_group_id,
            ticker=ticker,
            transaction_type=transaction_type.upper(),
            quantity=quantity,
            price=price,
            fees=fees,
            date=tx_date,
            notes=notes,
            client_request_id=client_request_id,
        )
        session.add(tx)
        try:
            session.flush()
        except IntegrityError:
            # A concurrent request with the same Idempotency-Key won the insert.
            session.rollback()
            existing_tx = (
                _find_client_request(session, user_id, client_request_id)
                if client_request_id is not None else None
            )
            if existing_tx is None:
                raise
            return existing_tx

        # Replays the whole (user, ticker) ledger in date order, so a backdated
        # SELL is validated against the position held on its own date.
        _recalculate_portfolio_snapshot(
            session=session,
            user_id=user_id,
            group_id=resolved_group_id,
            ticker=ticker,
            company_name=company_name,
            target_price=target_price,
            purchase_date=purchase_date,
            is_virtual=is_virtual,
            new_tx=tx,
        )
        session.commit()
        session.refresh(tx)
        return tx


def _find_client_request(session: Session, user_id: int, client_request_id: str) -> Optional[Transaction]:
    return (
        session.query(Transaction)
        .filter_by(user_id=user_id, client_request_id=client_request_id)
        .first()
    )


def _recalculate_portfolio_snapshot(
    session: Session,
    user_id: int,
    group_id: int,
    ticker: str,
    company_name: str = "",
    target_price: Optional[float] = None,
    purchase_date: Optional[str] = None,
    is_virtual: bool = False,
    new_tx: Optional[Transaction] = None,
) -> None:
    """
    Recompute the Portfolio read-model for one ticker using WAC.

    WAC rules:
    - BUY:    total_cost += qty * price + fees; total_shares += qty
    - SELL:   total_shares -= qty  (WAC unchanged — cost basis not adjusted)
    - SPLIT:  total_shares *= qty; wac /= qty  (price field holds the split ratio)
    - BONUS:  total_shares += qty  (bonus shares at zero cost)
    - DIVIDEND: no share or cost change — ignored here (recorded for income tracking)
    - ADJUST: total_shares = qty; total_cost = qty * price  (internal restatement)

    The replay covers the (user, ticker) ledger across groups; `new_tx` (the
    trade being written) and every later row are validated strictly, see
    _replay. The row's group_id is the group of the latest transaction.

    After iterating all transactions:
    - no transactions → leave the Portfolio row untouched (never wipe a ledger-less row)
    - shares <= 0  → delete Portfolio row (position closed)
    - shares > 0   → UPSERT Portfolio row with new shares + wac
    """
    transactions = _ledger_rows(session, user_id, ticker)
    if not transactions:
        return
    total_shares, wac = _replay(transactions, strict_from=new_tx)
    group_id = cast(Optional[int], transactions[-1].group_id) or group_id

    existing: Optional[Portfolio] = session.query(Portfolio).filter_by(
        user_id=user_id, ticker=ticker, group_name="holdings"
    ).first()

    if total_shares <= 0:
        if existing is not None:
            session.delete(existing)
        return

    if existing is not None:
        existing.shares = total_shares  # type: ignore[assignment]
        existing.buy_price = wac  # type: ignore[assignment]
        if group_id is not None:
            existing.group_id = group_id  # type: ignore[assignment]
        # Old clients send 0.0 for "no target": never let that wipe a real one.
        if target_price is not None and target_price > 0:
            existing.target_price = target_price  # type: ignore[assignment]
    else:
        new_row = Portfolio(
            user_id=user_id,
            ticker=ticker,
            company_name=company_name,
            shares=total_shares,
            buy_price=wac,
            group_name="holdings",
            group_id=group_id,
            target_price=target_price if target_price is not None and target_price > 0 else None,
            purchase_date=purchase_date,
            is_virtual=is_virtual,
        )
        session.add(new_row)


def adjust_position(
    user_id: int,
    ticker: str,
    shares: float,
    buy_price: float,
    target_price: Optional[float] = None,
    purchase_date: Optional[str] = None,
    notes: str = "Position edited",
) -> Optional[str]:
    """Restate a holding to exactly `shares` @ `buy_price` via an ADJUST entry.

    Ledger-backed PUT /portfolio/update, so the next BUY/SELL replay keeps the
    edit instead of reverting it. Uses the same default group as
    record_transaction so later trades replay on top of the restatement.

    Returns the holding's company_name, or None if the user has no holdings row
    for `ticker`.
    """
    from database import get_session
    with get_session() as session:
        _lock_position(session, user_id, ticker)
        row = session.query(Portfolio).filter_by(
            user_id=user_id, ticker=ticker, group_name="holdings"
        ).first()
        if row is None:
            return None
        company_name = cast(str, row.company_name) or ""
        group_id = cast(int, get_or_create_default_group(session, user_id).id)
        now = datetime.now(timezone.utc)
        _reconcile_with_read_model(session, user_id, group_id, ticker, now)
        session.add(Transaction(
            user_id=user_id,
            group_id=group_id,
            ticker=ticker,
            transaction_type="ADJUST",
            quantity=shares,
            price=buy_price,
            fees=0.0,
            date=now,
            notes=notes,
        ))
        session.flush()
        _recalculate_portfolio_snapshot(
            session=session,
            user_id=user_id,
            group_id=group_id,
            ticker=ticker,
            company_name=company_name,
            target_price=target_price,
        )
        if shares > 0 and purchase_date is not None:
            row.purchase_date = purchase_date  # type: ignore[assignment]
        session.commit()
        return company_name


def close_position(user_id: int, ticker: str) -> bool:
    """Ledger-backed DELETE /portfolio/remove: ADJUST to zero shares, so a later
    BUY replays from zero instead of resurrecting the old lots.

    Returns False if the user has no holdings row for `ticker`.
    """
    return adjust_position(user_id, ticker, 0.0, 0.0, notes="Position removed") is not None


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
                "date": t.date.isoformat() if t.date is not None else None,
                "notes": t.notes,
            }
            for t in rows
        ]
