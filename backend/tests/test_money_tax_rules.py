"""money-tax-engine: versioned capital-gains rules (pure)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from services import money_tax_rules as r


def test_version_and_constants():
    assert r.RULES_VERSION == "in-cg-2026.1"
    assert r.FA2024_CUTOFF == date(2024, 7, 23)
    assert r.GRANDFATHER_LAST_ACQ == date(2018, 1, 31)
    assert r.NEW_ACT_START == date(2026, 4, 1)


@pytest.mark.parametrize("fy,bounds", [
    ("2025-26", (date(2025, 4, 1), date(2026, 3, 31))),
    ("2018-19", (date(2018, 4, 1), date(2019, 3, 31))),
    ("2099-00", None),
])
def test_fy_bounds_valid(fy, bounds):
    today = date(2026, 10, 12)
    if bounds is None:
        with pytest.raises(ValueError):
            r.fy_bounds(fy, today)
    else:
        assert r.fy_bounds(fy, today) == bounds


@pytest.mark.parametrize("fy", ["2025-27", "2025-2026", "25-26", "", "2017-18", "2027-28", "abcd-ef", "2025/26"])
def test_fy_bounds_invalid(fy):
    with pytest.raises(ValueError):
        r.fy_bounds(fy, date(2026, 10, 12))


def test_current_fy_and_century_wrap():
    assert r.current_fy(date(2026, 3, 31)) == "2025-26"
    assert r.current_fy(date(2026, 4, 1)) == "2026-27"
    assert r.fy_label(2099) == "2099-00"
    assert r.fy_of(date(2024, 1, 5)) == "2023-24"


def test_add_months_clamps_to_month_end():
    assert r.add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert r.add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert r.add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert r.add_months(date(2024, 11, 30), 3) == date(2025, 2, 28)


def test_twelve_month_boundary():
    acq = date(2024, 3, 1)
    assert r.is_long_term(acq, date(2025, 3, 1)) is False   # exactly 12 months: still short
    assert r.is_long_term(acq, date(2025, 3, 2)) is True
    assert r.is_long_term(date(2024, 2, 29), date(2025, 2, 28)) is False
    assert r.is_long_term(date(2024, 2, 29), date(2025, 3, 1)) is True


def test_rates_split_at_23_july_2024():
    assert r.rate_period(date(2024, 7, 22)) == "pre_2024_07_23"
    assert r.rate_period(date(2024, 7, 23)) == "post_2024_07_23"
    assert (r.rate_pct("STCG", date(2024, 7, 22)), r.rate_pct("LTCG", date(2024, 7, 22))) == (Decimal(15), Decimal(10))
    assert (r.rate_pct("STCG", date(2024, 7, 23)), r.rate_pct("LTCG", date(2024, 7, 23))) == (Decimal(20), Decimal("12.5"))


def test_sections_switch_on_1_april_2026():
    assert (r.section("STCG", date(2026, 3, 31)), r.section("LTCG", date(2026, 3, 31))) == ("111A", "112A")
    assert (r.section("STCG", date(2026, 4, 1)), r.section("LTCG", date(2026, 4, 1))) == ("196", "198")


def test_exemption_by_fy():
    assert r.ltcg_exemption("2023-24") == Decimal(100000)
    assert r.ltcg_exemption("2018-19") == Decimal(100000)
    assert r.ltcg_exemption("2024-25") == Decimal(125000)
    assert r.ltcg_exemption("2026-27") == Decimal(125000)


def test_grandfathered_cost_three_cases():
    # FMV below actual cost: actual wins.
    assert r.grandfathered_cost(Decimal(1000), Decimal(800), Decimal(1500)) == Decimal(1000)
    # FMV between actual cost and sale value: FMV is the cost.
    assert r.grandfathered_cost(Decimal(1000), Decimal(1200), Decimal(1500)) == Decimal(1200)
    # FMV above the sale value: capped at the sale value (no artificial loss).
    assert r.grandfathered_cost(Decimal(1000), Decimal(2000), Decimal(1500)) == Decimal(1500)
