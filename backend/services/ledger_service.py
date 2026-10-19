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

Money C4: every row carries asset_class ('EQ' | 'MF', MF tickers are ISINs) and,
for statement imports, import_batch_id. Every Portfolio query here opts in with
execution_options(include_mf=True) so fund rows stay visible to the ledger once
the ORM guard that hides them from other readers lands.

Rules (AGENTS.md §3.1):
- No HTTP concerns here; callers handle auth and validation.
- All DB access via the session passed in from get_session() context.
- Floats are rounded to 6 decimal places; the read-model stores them at that
  precision (display rounding happens in API responses).
"""

from __future__ import annotations

import hashlib
from datetime import date as _date, datetime, time, timedelta, timezone
from typing import Optional, cast

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.db_models import Portfolio, PortfolioGroup, Transaction

ASSET_CLASSES = ("EQ", "MF")
_AUTO_SPLIT_PREFIX = "auto: corporate action"
_OPENING_PREFIXES = ("opening balance", "legacy migration backfill")
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class LedgerError(ValueError):
    """A write that would make the ledger inconsistent (e.g. selling more
    shares than held on the trade date). Routers map it to HTTP 422."""


def _check_asset_class(asset_class: str) -> str:
    if asset_class not in ASSET_CLASSES:
        raise ValueError(f"asset_class must be one of {ASSET_CLASSES}, got {asset_class!r}")
    return asset_class


def _holdings_row(session: Session, user_id: int, ticker: str) -> Optional[Portfolio]:
    return (
        session.query(Portfolio)
        .execution_options(include_mf=True)
        .filter_by(user_id=user_id, ticker=ticker, group_name="holdings")
        .first()
    )


def _notes_start(tx: Transaction, prefixes) -> bool:
    return str(tx.notes or "").strip().lower().startswith(prefixes)


def is_opening_balance(tx: Transaction) -> bool:
    """A BUY that stands for a holding entered before the ledger (fix-track opening
    balance or scripts/migrate_ledger.py backfill), dated at app entry, not at purchase."""
    return str(tx.transaction_type or "").upper() == "BUY" and _notes_start(tx, _OPENING_PREFIXES)


def _is_auto_split(tx: Transaction) -> bool:
    return str(tx.transaction_type or "").upper() == "SPLIT" and _notes_start(tx, _AUTO_SPLIT_PREFIX)


def _sort_key(tx: Transaction) -> tuple:
    when = _as_utc(cast(datetime, tx.date)) if tx.date is not None else _EPOCH
    return (when, cast(Optional[int], tx.id) or 0)


def dedupe_auto_splits(rows: list[Transaction]) -> list[Transaction]:
    """`rows` without repeated auto corporate-action SPLITs: the first per (date, ratio)
    is kept. MATH-07 rows written per group (or by a re-run) must apply only once."""
    seen: set = set()
    kept: list[Transaction] = []
    for tx in rows:
        if _is_auto_split(tx) and tx.date is not None:
            key = (_as_utc(cast(datetime, tx.date)).date(), round(float(cast(float, tx.quantity) or 0.0), 9))
            if key in seen:
                continue
            seen.add(key)
        kept.append(tx)
    return kept


def _step(shares: float, cost: float, tx: Transaction, strict: bool) -> tuple[float, float]:
    """One replay step on (shares, total cost). Rules in _recalculate_portfolio_snapshot."""
    t = tx.transaction_type.upper()
    qty = cast(float, tx.quantity) if tx.quantity is not None else 0.0
    prc = cast(float, tx.price) if tx.price is not None else 0.0
    fee = cast(float, tx.fees) if tx.fees is not None else 0.0

    if t == "BUY":
        cost += qty * prc + fee
        shares += qty
    elif t == "SELL":
        if strict and qty > shares + 1e-9:
            when = _as_utc(tx.date).date().isoformat() if tx.date is not None else "that date"  # type: ignore[arg-type]
            raise LedgerError(
                f"Cannot SELL {qty} of {tx.ticker}: only {round(shares, 4)} shares held on {when}."
            )
        if shares > 0:
            sell_qty = min(qty, shares)
            # Proportionally reduce cost basis
            cost -= sell_qty * (cost / shares)
            shares -= sell_qty
    elif t == "SPLIT":
        if qty > 0 and shares > 0:
            shares *= qty
            # cost basis unchanged; WAC recalculated below
    elif t == "BONUS":
        shares += qty
        # bonus shares at zero cost — WAC diluted
    elif t == "ADJUST":
        shares = qty
        cost = qty * prc
    return shares, cost


def adjust_kinds(rows: list[Transaction]) -> dict[int, str]:
    """Classify each ADJUST of one (user, ticker) ledger against the running replay.

    'close' (restated to 0 shares), 'noop' (same shares within 1e-6 and the same
    per-unit cost within 0.006: e.g. a PUT /portfolio/update that only changed the
    target or notes) or 'restate'. Keyed by transaction id.
    """
    kinds: dict[int, str] = {}
    shares = cost = 0.0
    for tx in dedupe_auto_splits(sorted(rows, key=_sort_key)):
        if tx.transaction_type.upper() == "ADJUST":
            q = float(cast(float, tx.quantity) or 0.0)
            p = float(cast(float, tx.price) or 0.0)
            if q <= 1e-9:
                kind = "close"
            elif shares > 0 and abs(q - shares) <= 1e-6 and abs(p - cost / shares) <= 0.006:
                kind = "noop"
            else:
                kind = "restate"
            kinds[cast(int, tx.id)] = kind
        shares, cost = _step(shares, cost, tx, strict=False)
    return kinds


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
    _recalculate_portfolio_snapshot's docstring; repeated auto SPLITs apply
    once (dedupe_auto_splits).

    From `strict_from` (the trade being written) onwards, a SELL of more
    shares than held at that point raises LedgerError: that rejects backdated
    SELLs and SELLs that would invalidate a later one. Earlier rows keep the
    legacy clamp so an old inconsistent ledger does not block every new write.
    """
    total_shares: float = 0.0
    total_cost: float = 0.0
    strict = False

    for tx in dedupe_auto_splits(transactions):
        strict = strict or (strict_from is not None and tx is strict_from)
        total_shares, total_cost = _step(total_shares, total_cost, tx, strict)

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
    row = _holdings_row(session, user_id, ticker)
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

    if row is not None:
        asset_class = cast(Optional[str], row.asset_class) or "EQ"
    else:
        asset_class = cast(Optional[str], transactions[-1].asset_class) or "EQ"
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
        asset_class=asset_class,
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
    session: Optional[Session] = None,
    *,
    asset_class: str = "EQ",
    import_batch_id: Optional[int] = None,
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
        session:          Optional caller-owned session: the write is flushed into
                          it and the caller commits. Default: own get_session() + commit.
        asset_class:      'EQ' (default) or 'MF' (ticker is the ISIN); ValueError otherwise.
        import_batch_id:  The ImportBatch that wrote this row (statement imports only).

    Returns:
        The committed Transaction (flushed only, when `session` is passed; the
        existing one for a repeated client_request_id).

    Raises:
        LedgerError: a SELL exceeds the shares held on its trade date, or
                     invalidates a later SELL. Nothing is written.
    """
    args = (user_id, ticker, transaction_type, quantity, price, group_id, fees, date, notes,
            company_name, target_price, purchase_date, is_virtual, client_request_id)
    kwargs = {"asset_class": asset_class, "import_batch_id": import_batch_id}
    if session is not None:
        # ponytail: an idempotency-key race rolls back the caller's whole transaction
        # (session.rollback below); only tests pass a session today.
        return _record_in_session(session, *args, **kwargs)
    from database import get_session
    with get_session() as own:
        tx = _record_in_session(own, *args, **kwargs)
        own.commit()
        own.refresh(tx)
        return tx


def _record_in_session(
    session: Session,
    user_id: int,
    ticker: str,
    transaction_type: str,
    quantity: float,
    price: float,
    group_id: Optional[int],
    fees: float,
    date: Optional[datetime],
    notes: Optional[str],
    company_name: str,
    target_price: Optional[float],
    purchase_date: Optional[str],
    is_virtual: bool,
    client_request_id: Optional[str],
    *,
    asset_class: str = "EQ",
    import_batch_id: Optional[int] = None,
) -> Transaction:
    """record_transaction's body: writes and flushes in `session`, never commits."""
    _check_asset_class(asset_class)
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
        asset_class=asset_class,
        import_batch_id=import_batch_id,
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
    _replay. The row's group_id and asset_class are the latest transaction's.

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
    asset_class = cast(Optional[str], transactions[-1].asset_class) or "EQ"

    existing = _holdings_row(session, user_id, ticker)

    if total_shares <= 0:
        if existing is not None:
            session.delete(existing)
        return

    if existing is not None:
        existing.shares = total_shares  # type: ignore[assignment]
        existing.buy_price = wac  # type: ignore[assignment]
        existing.asset_class = asset_class  # type: ignore[assignment]
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
            asset_class=asset_class,
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
        row = _holdings_row(session, user_id, ticker)
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
            asset_class=cast(Optional[str], row.asset_class) or "EQ",
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


def restate_position(
    session: Session,
    user_id: int,
    ticker: str,
    quantity: float,
    price: float,
    *,
    date: Optional[datetime] = None,
    notes: Optional[str] = None,
    asset_class: str = "EQ",
    import_batch_id: Optional[int] = None,
    client_request_id: Optional[str] = None,
    company_name: str = "",
) -> Optional[Transaction]:
    """Restate (user, ticker) to exactly `quantity` @ `price` with an ADJUST row
    (statement imports: one balance per fund). Flushes and recomputes the holding
    in `session`; never commits.

    Returns None, writing nothing, when the user already has a row with
    `client_request_id` (the same balance imported again). LedgerError when the
    restatement would leave a later SELL short.
    """
    _lock_position(session, user_id, ticker)
    if client_request_id is not None and _find_client_request(session, user_id, client_request_id) is not None:
        return None
    return _record_in_session(
        session, user_id, ticker, "ADJUST", quantity, price, None, 0.0, date, notes,
        company_name, None, None, False, client_request_id,
        asset_class=asset_class, import_batch_id=import_batch_id,
    )


def remove_import_batch(session: Session, user_id: int, batch_id: int) -> int:
    """Delete the ledger rows import batch `batch_id` wrote for `user_id` and
    recompute each affected holding (undo of an import). Flushes; never commits.

    The rows after the earliest removed one are replayed strictly, so an undo that
    would leave a later SELL short raises LedgerError (nothing is flushed past the
    deletes; the caller rolls back). A holding whose ledger becomes empty was
    created by the import, so its row is removed too. Returns rows deleted.
    """
    rows = (
        session.query(Transaction)
        .filter_by(user_id=user_id, import_batch_id=batch_id)
        .all()
    )
    tickers = sorted({str(t.ticker) for t in rows})
    for ticker in tickers:  # sorted: a fixed lock order, no deadlock between two undos
        _lock_position(session, user_id, ticker)
    earliest: dict[str, tuple] = {}
    for tx in rows:
        key = _sort_key(tx)
        earliest[str(tx.ticker)] = min(earliest.get(str(tx.ticker), key), key)
        session.delete(tx)
    session.flush()

    for ticker in tickers:
        remaining = _ledger_rows(session, user_id, ticker)
        if not remaining:
            row = _holdings_row(session, user_id, ticker)
            if row is not None:
                session.delete(row)
            continue
        strict_from = next((t for t in remaining if _sort_key(t) >= earliest[ticker]), None)
        _recalculate_portfolio_snapshot(
            session=session,
            user_id=user_id,
            group_id=cast(int, remaining[-1].group_id),
            ticker=ticker,
            new_tx=strict_from,
        )
    session.flush()
    return len(rows)


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


_IST = timezone(timedelta(hours=5, minutes=30))


def _split_effective_at(ex_date: _date) -> datetime:
    """The instant a split takes effect in the ledger: one second before IST midnight
    of the ex-date, so a trade on the ex-date (trade-date midnight UTC, or now())
    replays after it and a trade on the day before replays before it."""
    return (datetime.combine(ex_date, time(0, 0), tzinfo=_IST) - timedelta(seconds=1)).astimezone(timezone.utc)


def apply_split_events(user_id: int, ticker: str, events: list[tuple[_date, float]]) -> int:
    """Write each split/bonus (ex_date, ratio) as a ledger SPLIT row and re-derive the holding (MATH-07).

    A SPLIT multiplies only the shares held before the ex-date (_replay), so a BUY
    on or after the ex-date is not multiplied. Idempotent: one SPLIT per effective
    instant per (user, ticker); the replay spans all groups, so per-group rows would
    double-apply. Only ex-dates after the position was first recorded in the app
    (earliest of the holdings row's and its ledger rows' created_at) apply: earlier
    ones are already in the quantity the user entered, whatever trade date it carries.
    A holding with no ledger first gets its opening BUY. Nothing is written when no
    event applies. Returns SPLIT rows added.
    """
    if not events:
        return 0
    from database import get_session
    added = 0
    with get_session() as session:
        _lock_position(session, user_id, ticker)
        row = _holdings_row(session, user_id, ticker)
        if row is None:
            return 0
        now = datetime.now(timezone.utc)
        # When the app first knew of this position. Quantities entered after an ex-date
        # are the broker's already-adjusted ones (trade date is user-entered and may be
        # backdated), so only ex-dates after this instant are applied automatically.
        # ponytail: per position, not per BUY; a backdated BUY recorded later still
        # replays before an older SPLIT row; upgrade: compare each BUY's created_at to the ex-date.
        known = [cast(Optional[datetime], row.created_at)]
        known += [cast(Optional[datetime], t.created_at) for t in _ledger_rows(session, user_id, ticker)]
        recorded_at = min((_as_utc(c) for c in known if c is not None), default=now)
        group_id = cast(int, get_or_create_default_group(session, user_id).id)
        _reconcile_with_read_model(session, user_id, group_id, ticker, now)
        ledger = _ledger_rows(session, user_id, ticker)
        done = {_as_utc(t.date) for t in ledger if t.transaction_type.upper() == "SPLIT" and t.date is not None}  # type: ignore[arg-type]
        for ex_date, ratio in sorted(events):
            effective = _split_effective_at(ex_date)
            if effective in done or effective > now or effective <= recorded_at:
                continue
            held, _ = _replay([t for t in ledger if t.date is not None and _as_utc(t.date) < effective])  # type: ignore[arg-type]
            if held <= 0:
                continue
            session.add(Transaction(
                user_id=user_id, group_id=group_id, ticker=ticker, transaction_type="SPLIT",
                quantity=ratio, price=0.0, fees=0.0, date=effective,
                notes=f"auto: corporate action ex {ex_date.isoformat()} (yfinance)",
                asset_class=cast(Optional[str], row.asset_class) or "EQ",
            ))
            session.flush()
            ledger = _ledger_rows(session, user_id, ticker)
            done.add(effective)
            added += 1
        if not added:
            session.rollback()  # drop an opening BUY / ADJUST that nothing needed
            return 0
        _recalculate_portfolio_snapshot(session=session, user_id=user_id, group_id=group_id, ticker=ticker)
        session.commit()
    return added


def sync_corporate_actions_all_users() -> dict:
    """Daily job: apply Yahoo splits/bonuses to every holding recorded before their ex-date (MATH-07).

    Reads (user, ticker) pairs in one short session, fetches each ticker's splits
    once with no session open, then applies per holding. Errors are per ticker.
    """
    import logging
    from database import get_session
    from services.portfolio_service import fetch_split_events

    log = logging.getLogger(__name__)
    with get_session() as session:
        # Stocks only: fund ISINs never go to yfinance.
        pairs = session.query(Portfolio.user_id, Portfolio.ticker).execution_options(include_mf=True).filter(
            Portfolio.group_name == "holdings", Portfolio.shares > 0, Portfolio.asset_class == "EQ",
        ).distinct().all()
    by_ticker: dict[str, list[int]] = {}
    for user_id, ticker in pairs:
        by_ticker.setdefault(str(ticker), []).append(int(user_id))

    counts = {"tickers": len(by_ticker), "splits_added": 0, "errors": 0}
    for ticker, user_ids in by_ticker.items():
        events = fetch_split_events(ticker)
        for user_id in user_ids:
            try:
                counts["splits_added"] += apply_split_events(user_id, ticker, events)
            except Exception:
                counts["errors"] += 1
                log.exception("[corporate-actions] %s for user %s failed", ticker, user_id)
    log.info(f"[corporate-actions] {counts}")
    return counts
