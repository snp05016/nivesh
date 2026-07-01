"""
Pure-Python mutual fund calculation engines: SIP, SWP, STP, and rolling returns.

IMPORTANT: These are pure, deterministic functions with NO side effects.
No DB session, no I/O, no network access, no yfinance/LLM calls. They operate
strictly on numeric/date inputs supplied by the caller so that other services
(e.g. routers or higher-level services) can import and call them directly
without incurring any DB/network dependency.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, TypedDict


class SIPResult(TypedDict):
    invested_amount: float
    estimated_returns: float
    total_value: float


class SWPResult(TypedDict):
    final_corpus: float
    total_withdrawn: float
    corpus_depleted_month: Optional[int]


class STPResult(TypedDict):
    source_final: float
    target_final: float


class NAVPoint(TypedDict):
    date: date
    nav: float


class RollingReturnPoint(TypedDict):
    start_date: date
    end_date: date
    cagr_pct: float


def calculate_sip_returns(
    monthly_amount: float,
    annual_return_pct: float,
    years: float,
) -> SIPResult:
    """
    Calculate the future value of a monthly SIP (Systematic Investment Plan)
    using the standard SIP future-value formula with monthly compounding,
    assuming each installment is invested at the start of the month
    (annuity-due).

    Formula:
        i = (annual_return_pct / 100) / 12          # monthly rate
        n = years * 12                               # number of installments
        FV = monthly_amount * ( ((1 + i)^n - 1) / i ) * (1 + i)

    Where:
        FV                 = total_value (maturity value of the SIP)
        invested_amount     = monthly_amount * n
        estimated_returns   = FV - invested_amount

    Args:
        monthly_amount: SIP installment amount invested each month (₹).
        annual_return_pct: Expected annual rate of return, in percent (e.g. 12 for 12%).
        years: Investment tenure in years (may be fractional).

    Returns:
        SIPResult with invested_amount, estimated_returns, total_value.
    """
    n_months = years * 12
    invested_amount = monthly_amount * n_months

    monthly_rate = (annual_return_pct / 100.0) / 12.0

    if monthly_rate == 0:
        total_value = invested_amount
    else:
        n_whole = round(n_months)
        total_value = (
            monthly_amount
            * (((1 + monthly_rate) ** n_whole - 1) / monthly_rate)
            * (1 + monthly_rate)
        )

    estimated_returns = total_value - invested_amount

    return {
        "invested_amount": round(invested_amount, 2),
        "estimated_returns": round(estimated_returns, 2),
        "total_value": round(total_value, 2),
    }


def calculate_swp(
    initial_corpus: float,
    monthly_withdrawal: float,
    annual_return_pct: float,
    years: float,
) -> SWPResult:
    """
    Simulate a monthly SWP (Systematic Withdrawal Plan) against a corpus that
    continues to earn a fixed annual return (compounded monthly), withdrawing
    a fixed amount at the end of every month:

        i = (annual_return_pct / 100) / 12
        corpus_(m) = corpus_(m-1) * (1 + i) - monthly_withdrawal

    Iterated month by month for n = years * 12 months. If the corpus is
    fully depleted (drops to <= 0) before the tenure ends, withdrawals stop
    at that month and corpus_depleted_month records the 1-indexed month in
    which depletion occurred.

    Args:
        initial_corpus: Starting corpus (₹).
        monthly_withdrawal: Fixed amount withdrawn at the end of each month (₹).
        annual_return_pct: Expected annual rate of return on the remaining corpus, in percent.
        years: Withdrawal tenure in years (may be fractional).

    Returns:
        SWPResult with final_corpus, total_withdrawn, corpus_depleted_month
        (None if the corpus survives the full tenure).
    """
    n_months = round(years * 12)
    monthly_rate = (annual_return_pct / 100.0) / 12.0

    corpus = initial_corpus
    total_withdrawn = 0.0
    corpus_depleted_month: Optional[int] = None

    for month in range(1, n_months + 1):
        corpus = corpus * (1 + monthly_rate)

        if corpus <= 0:
            corpus_depleted_month = month
            corpus = 0.0
            break

        withdrawal = min(monthly_withdrawal, corpus)
        corpus -= withdrawal
        total_withdrawn += withdrawal

        if corpus <= 0:
            corpus = 0.0
            corpus_depleted_month = month
            break

    return {
        "final_corpus": round(corpus, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "corpus_depleted_month": corpus_depleted_month,
    }


def calculate_stp(
    source_corpus: float,
    monthly_transfer: float,
    source_return_pct: float,
    target_return_pct: float,
    years: float,
) -> STPResult:
    """
    Simulate a monthly STP (Systematic Transfer Plan): a fixed amount is
    transferred out of the source fund into the target fund at the end of
    every month. Both funds compound monthly at their own annual rates:

        i_source = (source_return_pct / 100) / 12
        i_target = (target_return_pct / 100) / 12

        source_(m) = source_(m-1) * (1 + i_source) - transfer_(m)
        target_(m) = (target_(m-1) + transfer_(m)) * (1 + i_target)

    where transfer_(m) = min(monthly_transfer, available source balance).
    If the source corpus is exhausted, transfers simply stop (0) for the
    remaining months, but the target corpus continues to compound.

    Args:
        source_corpus: Starting corpus in the source fund (₹).
        monthly_transfer: Fixed amount transferred out of source into target each month (₹).
        source_return_pct: Expected annual rate of return of the source fund, in percent.
        target_return_pct: Expected annual rate of return of the target fund, in percent.
        years: Transfer tenure in years (may be fractional).

    Returns:
        STPResult with source_final and target_final.
    """
    n_months = round(years * 12)
    i_source = (source_return_pct / 100.0) / 12.0
    i_target = (target_return_pct / 100.0) / 12.0

    source = source_corpus
    target = 0.0

    for _ in range(n_months):
        source = source * (1 + i_source)
        transfer = min(monthly_transfer, max(source, 0.0))
        source -= transfer
        target = (target + transfer) * (1 + i_target)

    return {
        "source_final": round(source, 2),
        "target_final": round(target, 2),
    }


def calculate_rolling_returns(
    nav_history: list[NAVPoint],
    window_years: float,
) -> list[RollingReturnPoint]:
    """
    Compute the CAGR (Compound Annual Growth Rate) over every rolling window
    of length `window_years` across the supplied NAV history.

    For each NAV point (as a prospective window start), the nearest NAV point
    at or after (start_date + window_years) is used as the window end, and:

        cagr_pct = ((end_nav / start_nav) ** (1 / window_years) - 1) * 100

    NAV history is sorted by date first. A rolling window is only emitted if
    an end point exists whose date is >= start_date + window_years (i.e. the
    window is fully covered by available data); windows that would run past
    the end of the available history are skipped.

    Args:
        nav_history: List of {"date": date, "nav": float}, need not be pre-sorted.
        window_years: Length of each rolling window in years (may be fractional).

    Returns:
        List of RollingReturnPoint (start_date, end_date, cagr_pct), one per
        valid rolling window, ordered by start_date ascending.
    """
    if window_years <= 0 or not nav_history:
        return []

    sorted_history = sorted(nav_history, key=lambda p: p["date"])
    window_days = window_years * 365.25

    results: list[RollingReturnPoint] = []
    end_idx = 0
    n = len(sorted_history)

    for start_idx in range(n):
        start_point = sorted_history[start_idx]
        target_end_date = _add_days(start_point["date"], window_days)

        if end_idx < start_idx:
            end_idx = start_idx

        while end_idx < n and sorted_history[end_idx]["date"] < target_end_date:
            end_idx += 1

        if end_idx >= n:
            break

        end_point = sorted_history[end_idx]
        start_nav = start_point["nav"]

        if start_nav <= 0:
            continue

        cagr_pct = ((end_point["nav"] / start_nav) ** (1.0 / window_years) - 1) * 100

        results.append(
            {
                "start_date": start_point["date"],
                "end_date": end_point["date"],
                "cagr_pct": round(cagr_pct, 4),
            }
        )

    return results


def _add_days(base: date, days: float):
    """Internal helper: add a (possibly fractional) number of days to a date."""
    from datetime import timedelta

    return base + timedelta(days=days)
