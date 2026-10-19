"""money-tax-engine: FIFO lots from a ledger (pure)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from services.money_tax_lots import Row, TaxLedgerError, fifo_match

_ids = iter(range(1, 10_000))


def row(kind, day, qty, price=0.0, fees=0.0, notes=None, ticker="INFY"):
    return Row(id=next(_ids), date=datetime(day.year, day.month, day.day), type=kind, quantity=qty, price=price,
               fees=fees, notes=notes, ticker=ticker)


def test_fifo_across_two_buys_with_fees():
    rows = [
        row("BUY", date(2024, 1, 10), 10, 100.0, fees=10.0),   # unit cost 101
        row("BUY", date(2024, 2, 10), 10, 120.0, fees=20.0),   # unit cost 122
        row("SELL", date(2024, 6, 10), 15, 150.0, fees=15.0),
    ]
    matches, open_lots = fifo_match(rows)
    assert [(m.lot.acquired_on, m.quantity) for m in matches] == [(date(2024, 1, 10), Decimal(10)), (date(2024, 2, 10), Decimal(5))]
    assert matches[0].lot.unit_cost == Decimal(101) and matches[1].lot.unit_cost == Decimal(122)
    assert [m.sale_value for m in matches] == [Decimal(1500), Decimal(750)]
    assert [m.transfer_expenses for m in matches] == [Decimal(10), Decimal(5)]  # fees pro rata to quantity
    assert len(open_lots) == 1 and open_lots[0].quantity == Decimal(5)


def test_sell_more_than_held_raises():
    with pytest.raises(TaxLedgerError):
        fifo_match([row("BUY", date(2024, 1, 10), 5, 100.0), row("SELL", date(2024, 2, 10), 6, 110.0)])


def test_split_after_2018_scales_lots_and_records_factor():
    rows = [
        row("BUY", date(2017, 5, 1), 10, 1000.0),
        row("SPLIT", date(2019, 6, 1), 2),
        row("SELL", date(2020, 1, 1), 20, 600.0),
    ]
    matches, _ = fifo_match(rows)
    lot = matches[0].lot
    assert matches[0].quantity == Decimal(20) and lot.unit_cost == Decimal(500)
    assert lot.split_factor_after_2018 == Decimal(2)


def test_split_before_2018_does_not_change_factor():
    rows = [row("BUY", date(2016, 5, 1), 10, 1000.0), row("SPLIT", date(2017, 6, 1), 2), row("SELL", date(2020, 1, 1), 20, 600.0)]
    matches, _ = fifo_match(rows)
    assert matches[0].lot.split_factor_after_2018 == Decimal(1)


def test_duplicate_auto_splits_apply_once_and_are_flagged():
    note = "auto: corporate action ex 2023-05-01 (yfinance)"
    rows = [
        row("BUY", date(2023, 1, 1), 10, 100.0),
        row("SPLIT", date(2023, 5, 1), 2, notes=note),
        row("SPLIT", date(2023, 5, 1), 2, notes=note),   # a second per-group row for the same event
        row("SELL", date(2023, 8, 1), 20, 60.0),
    ]
    matches, open_lots = fifo_match(rows)
    assert matches[0].quantity == Decimal(20) and open_lots == []
    assert matches[0].lot.auto_split is True


def test_bonus_is_a_nil_cost_lot_with_review():
    rows = [row("BUY", date(2023, 1, 1), 10, 100.0), row("BONUS", date(2023, 3, 1), 10), row("SELL", date(2023, 4, 1), 20, 50.0)]
    matches, _ = fifo_match(rows)
    bonus = matches[1].lot
    assert bonus.unit_cost == Decimal(0) and bonus.review == ("stt_on_acquisition_unverified",)
    assert bonus.acquired_on == date(2023, 3, 1)


def test_opening_balance_with_date_is_computed():
    rows = [row("BUY", date(2026, 9, 1), 10, 100.0, notes="Opening balance (pre-ledger holding)"),
            row("SELL", date(2026, 9, 20), 10, 120.0)]
    matches, _ = fifo_match(rows, opening_balance_date=date(2022, 2, 3))
    lot = matches[0].lot
    assert lot.acquired_on == date(2022, 2, 3) and lot.uncertain is None
    assert lot.review == ("user_entered_date", "stt_on_acquisition_unverified")


def test_opening_balance_without_date_is_uncertain():
    rows = [row("BUY", date(2026, 9, 1), 10, 100.0, notes="Opening balance (pre-ledger holding)"),
            row("SELL", date(2026, 9, 20), 10, 120.0)]
    lot = fifo_match(rows)[0][0].lot
    assert lot.acquired_on is None and lot.uncertain == "opening_balance"
    assert lot.review == ("stt_on_acquisition_unverified",)


def test_legacy_backfill_row_is_an_opening_balance():
    rows = [row("BUY", date(2026, 9, 1), 10, 100.0, notes="Legacy migration backfill"),
            row("SELL", date(2026, 9, 20), 5, 120.0)]
    matches, open_lots = fifo_match(rows, opening_balance_date=date(2021, 1, 4))
    assert matches[0].lot.acquired_on == date(2021, 1, 4) and open_lots[0].quantity == Decimal(5)


def test_noop_adjust_keeps_lots():
    rows = [row("BUY", date(2024, 1, 1), 10, 100.0),
            row("ADJUST", date(2024, 2, 1), 10, 100.0),   # same shares, same per-unit cost
            row("SELL", date(2024, 3, 1), 10, 110.0)]
    matches, _ = fifo_match(rows)
    assert matches[0].lot.acquired_on == date(2024, 1, 1) and matches[0].lot.uncertain is None


def test_close_then_buy_starts_fresh():
    rows = [row("BUY", date(2024, 1, 1), 10, 100.0), row("ADJUST", date(2024, 2, 1), 0, 0.0),
            row("BUY", date(2024, 3, 1), 4, 90.0), row("SELL", date(2024, 4, 1), 4, 95.0)]
    matches, open_lots = fifo_match(rows)
    assert len(matches) == 1 and matches[0].lot.acquired_on == date(2024, 3, 1) and open_lots == []


def test_restate_makes_one_uncertain_lot():
    rows = [row("BUY", date(2024, 1, 1), 10, 100.0), row("ADJUST", date(2024, 2, 1), 8, 105.0),
            row("SELL", date(2024, 3, 1), 8, 110.0)]
    lot = fifo_match(rows)[0][0].lot
    assert lot.uncertain == "adjust" and lot.unit_cost == Decimal("105")


def test_dividends_are_ignored():
    rows = [row("BUY", date(2024, 1, 1), 10, 100.0), row("DIVIDEND", date(2024, 2, 1), 10, 5.0)]
    matches, open_lots = fifo_match(rows)
    assert matches == [] and open_lots[0].quantity == Decimal(10)


def test_rows_are_sorted_by_date_then_id():
    sell = row("SELL", date(2024, 3, 1), 5, 110.0)
    buy = row("BUY", date(2024, 1, 1), 5, 100.0)
    assert fifo_match([sell, buy])[0][0].quantity == Decimal(5)
