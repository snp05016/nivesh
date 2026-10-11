"""Shared min/max/active checks for bookable products (loan offers, FD schemes)."""

from __future__ import annotations


class ProductBoundsError(ValueError):
    """Requested amount/tenure is outside the product's limits, or the product is inactive.

    Subclasses ValueError so existing callers keep working; routers catch it
    first and return 422 instead of the generic 404.
    """


def check_product_bounds(product, amount: float, tenure_months: int, label: str) -> None:
    """Raise ProductBoundsError unless the product is active and amount/tenure are in range.

    ``product`` needs is_active, min_amount, max_amount, min_tenure_months and
    max_tenure_months (LoanOffer and FixedDepositScheme both have them).
    """
    from helpers import format_indian_currency  # lazy: helpers pulls in the DB/market stack

    if not product.is_active:
        raise ProductBoundsError(f"This {label} is no longer available")

    min_amount, max_amount = float(product.min_amount), float(product.max_amount)
    if not (min_amount <= amount <= max_amount):
        raise ProductBoundsError(
            f"Amount must be between {format_indian_currency(min_amount)} and "
            f"{format_indian_currency(max_amount)} for this {label}"
        )

    min_tenure, max_tenure = int(product.min_tenure_months), int(product.max_tenure_months)
    if not (min_tenure <= tenure_months <= max_tenure):
        raise ProductBoundsError(
            f"Tenure must be between {min_tenure} and {max_tenure} months for this {label}"
        )
