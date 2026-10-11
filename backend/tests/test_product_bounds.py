"""GH-663: loan and FD bookings must respect the product's min/max limits and active flag."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from services.product_bounds import ProductBoundsError, check_product_bounds


def _product(**overrides):
    attrs = dict(
        is_active=True,
        min_amount=Decimal("10000"),
        max_amount=Decimal("500000"),
        min_tenure_months=6,
        max_tenure_months=60,
    )
    attrs.update(overrides)
    return SimpleNamespace(**attrs)


@pytest.mark.parametrize(
    "amount, tenure",
    [(10000, 6), (500000, 60), (250000, 24)],
)
def test_in_range_passes(amount, tenure):
    check_product_bounds(_product(), amount, tenure, "loan offer")


@pytest.mark.parametrize(
    "amount, tenure",
    [
        (9999.99, 24),       # below min amount
        (500000.01, 24),     # above max amount
        (100000, 5),         # below min tenure
        (100000, 61),        # above max tenure
        (100000, 10**9),     # absurd tenure (used to overflow timedelta -> 500)
        (float("nan"), 24),  # NaN never satisfies the range
    ],
)
def test_out_of_range_raises(amount, tenure):
    with pytest.raises(ProductBoundsError):
        check_product_bounds(_product(), amount, tenure, "FD scheme")


def test_inactive_product_raises():
    with pytest.raises(ProductBoundsError):
        check_product_bounds(_product(is_active=False), 100000, 24, "loan offer")


def test_amount_message_uses_indian_units():
    with pytest.raises(ProductBoundsError) as exc_info:
        check_product_bounds(_product(), 1, 24, "loan offer")
    message = str(exc_info.value)
    assert "Lakhs" in message
    assert "million" not in message.lower()


def test_is_value_error_subclass():
    assert issubclass(ProductBoundsError, ValueError)
