"""FIFO lots from a ledger, for the capital-gains working (I29, spec 3.7).

The ledger stores a weighted-average position, so the FIFO lots a tax computation needs are
derived on read from one (user, ticker) transaction list. Pure: no DB, no network, Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from core.timeutil import ist_today
from services import ledger_service
from services.money_tax_rules import GRANDFATHER_LAST_ACQ

_AUTO_SPLIT = "auto: corporate action"
_EPS = Decimal("0.000000001")


class TaxLedgerError(ValueError):
    """The ledger sells more shares than the lots hold (a gap the user must fix)."""


@dataclass(frozen=True)
class Row:
    """One ledger transaction. Exposes the attribute names ledger_service's helpers read."""
    id: int
    date: datetime
    type: str
    quantity: float
    price: float
    fees: float = 0.0
    notes: Optional[str] = None
    import_batch_id: Optional[int] = None
    ticker: str = ""

    @property
    def transaction_type(self) -> str:
        return self.type


@dataclass(frozen=True)
class Lot:
    source_id: int
    acquired_on: Optional[date]
    quantity: Decimal
    unit_cost: Decimal
    # Why the acquisition date or cost cannot be trusted ('opening_balance', 'adjust'); None when computed.
    uncertain: Optional[str] = None
    review: tuple[str, ...] = ()
    # Product of split ratios applied after 31-Jan-2018 (to bring the 2018 price to today's share count).
    split_factor_after_2018: Decimal = Decimal(1)
    auto_split: bool = False


@dataclass(frozen=True)
class Match:
    sell_id: int
    sold_on: date
    quantity: Decimal
    sale_value: Decimal
    transfer_expenses: Decimal
    # The consumed part of the lot (quantity is the matched quantity).
    lot: Lot


def _d(value) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _day(row: Row) -> date:
    return ist_today(row.date)


def fifo_match(rows: list[Row], *, opening_balance_date: Optional[date] = None) -> tuple[list[Match], list[Lot]]:
    """Match every SELL against the oldest lots first. Returns (matches, lots still open).

    Raises TaxLedgerError when a SELL exceeds the lots held.
    """
    ordered = ledger_service.dedupe_auto_splits(sorted(rows, key=ledger_service._sort_key))
    kinds = ledger_service.adjust_kinds(ordered)
    lots: list[Lot] = []
    matches: list[Match] = []

    for row in ordered:
        kind = str(row.type).upper()
        qty, price, fees = _d(row.quantity), _d(row.price), _d(row.fees)
        day = _day(row)

        if kind == "BUY":
            if qty <= 0:
                continue
            unit_cost = (qty * price + fees) / qty
            if ledger_service.is_opening_balance(row):
                if opening_balance_date is not None:
                    lots.append(Lot(row.id, opening_balance_date, qty, unit_cost,
                                    review=("user_entered_date", "stt_on_acquisition_unverified")))
                else:
                    lots.append(Lot(row.id, None, qty, unit_cost, uncertain="opening_balance",
                                    review=("stt_on_acquisition_unverified",)))
            else:
                lots.append(Lot(row.id, day, qty, unit_cost))
        elif kind == "SELL":
            matches.extend(_consume(lots, row, qty, price, fees, day))
        elif kind == "SPLIT":
            if qty > 0:
                auto = str(row.notes or "").strip().lower().startswith(_AUTO_SPLIT)
                after_2018 = day > GRANDFATHER_LAST_ACQ
                lots[:] = [
                    replace(
                        lot, quantity=lot.quantity * qty, unit_cost=lot.unit_cost / qty,
                        split_factor_after_2018=lot.split_factor_after_2018 * qty if after_2018 else lot.split_factor_after_2018,
                        auto_split=lot.auto_split or auto,
                    )
                    for lot in lots
                ]
        elif kind == "BONUS":
            if qty > 0:
                lots.append(Lot(row.id, day, qty, Decimal(0), review=("stt_on_acquisition_unverified",)))
        elif kind == "ADJUST":
            what = kinds.get(row.id, "restate")
            if what == "noop":
                continue
            lots.clear()
            if what == "restate":
                lots.append(Lot(row.id, day, qty, price, uncertain="adjust"))
        # DIVIDEND and anything else: no effect on lots

    return matches, lots


def _consume(lots: list[Lot], row: Row, qty: Decimal, price: Decimal, fees: Decimal, day: date) -> list[Match]:
    held = sum((lot.quantity for lot in lots), Decimal(0))
    if qty > held + _EPS:
        raise TaxLedgerError(f"Cannot sell {qty} of {row.ticker or 'the holding'} on {day}: only {held} held.")
    out: list[Match] = []
    remaining = qty
    while remaining > _EPS and lots:
        lot = lots[0]
        take = min(lot.quantity, remaining)
        share = take / qty
        out.append(Match(
            sell_id=row.id, sold_on=day, quantity=take, sale_value=take * price,
            transfer_expenses=fees * share, lot=replace(lot, quantity=take),
        ))
        remaining -= take
        if take >= lot.quantity - _EPS:
            lots.pop(0)
        else:
            lots[0] = replace(lot, quantity=lot.quantity - take)
    return out
