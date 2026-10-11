"""Server-side display strings for Facts (spec 6.1) and the rr-1 range sentence (4.5).

One formatter for every displayed number: iOS and the LLM payload only ever
show ``Fact.display``. Amounts use Indian digit grouping and lakh/crore words.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .contract import FACT_CATALOGUE, FACT_LABELS, Fact, FactStatus, ReasonCode, Source, Unit

MINUS = "−"  # U+2212, used for every negative display
LAKH_CRORE = 100_000.0  # 1,00,000 crore


def _group_indian(digits: str) -> str:
    """'12345678' -> '1,23,45,678' (last three digits, then groups of two)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def _round_half_up(value: float, decimals: int) -> str:
    """Round the shortest decimal repr half-up, so 9.85 shows as 9.9 (not binary 9.8)."""
    return str(Decimal(repr(abs(float(value)))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP))


def _magnitude(value: float, decimals: int) -> str:
    whole, _, frac = _round_half_up(value, decimals).partition(".")
    return _group_indian(whole) + (f".{frac}" if frac else "")


def _ordinal_suffix(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def format_value(value: float, unit: Unit, decimals: int, signed: bool) -> str:
    """Display string for a finite value (6.1 table).

    Negative values always carry U+2212. ``signed`` facts add "+" to positive
    values; a value that rounds to zero carries no sign.
    """
    scaled = value * 100.0 if unit == "prob" else value
    # Switch to lakh crore on the value as displayed, so 99,999.96 is not "1,00,000.0 crore".
    lakh_crore = unit == "inr_cr" and Decimal(_round_half_up(value, decimals)) >= Decimal(int(LAKH_CRORE))
    if lakh_crore:
        scaled, decimals = value / LAKH_CRORE, max(decimals, 1)
    number = _magnitude(scaled, decimals)
    is_zero = Decimal(_round_half_up(scaled, decimals)) == 0
    sign = "" if is_zero else MINUS if scaled < 0 else "+" if signed else ""

    if unit == "inr":
        return f"{sign}₹{number}"
    if unit == "inr_cr":
        word = "lakh crore" if lakh_crore else "crore"
        return f"{sign}₹{number} {word}"
    if unit in ("pct", "prob"):
        return f"{sign}{number}%"
    if unit == "pp":
        return f"{sign}{number} percentage points"
    if unit == "pctl":
        # Suffix from the shown number (half-up), never Python's half-even round().
        suffix = _ordinal_suffix(int(number.replace(",", ""))) if decimals == 0 else "th"
        return f"{sign}{number}{suffix} percentile"
    if unit == "x":
        return f"{sign}{number}x"
    if unit == "sessions":
        days = "trading day" if number == "1" else "trading days"
        return f"{sign}{number} {days}"
    return f"{sign}{number}"  # ratio, count


def make_fact(
    id: str,
    value: float | None,
    unit: Unit | None = None,
    *,
    source: Source,
    as_of: date | None,
    decimals: int | None = None,
    signed: bool | None = None,
    label: str | None = None,
    method: str | None = None,
    status: FactStatus | None = None,
    reason: ReasonCode | None = None,
) -> Fact:
    """Build a Fact with its server display string.

    ``unit``, ``decimals``, ``signed`` and ``label`` default to the 6.3
    catalogue entry for ``id``; ids outside it (``factor.{feature}.*``) must
    pass them. A missing or non-finite value, or ``status="unavailable"``,
    gives an unavailable fact, which requires an explicit ``reason`` (no silent
    fallbacks, SILENT-16). ``status="stale"`` defaults the reason to
    ``stale_source``.
    """
    spec = FACT_CATALOGUE.get(id)
    if spec is None and None in (unit, decimals, signed, label):
        raise ValueError(f"{id!r} is not in FACT_CATALOGUE: pass unit, decimals, signed and label")
    if spec is not None:
        _, cat_unit, cat_decimals, cat_signed = spec
        unit = cat_unit if unit is None else unit
        decimals = cat_decimals if decimals is None else decimals
        signed = cat_signed if signed is None else signed
        label = FACT_LABELS[id] if label is None else label
    assert unit is not None and decimals is not None and signed is not None and label is not None

    number = None if value is None else float(value)
    if number is None or not math.isfinite(number) or status == "unavailable":
        if reason is None:
            raise ValueError(f"{id}: an unavailable fact needs a reason")
        return Fact(
            id=id, label=label, value=None, unit=unit, decimals=decimals, signed=signed,
            display=None, status="unavailable", reason=reason, source=source, as_of=as_of,
            method=method,
        )
    final_status: FactStatus = status or "ok"
    if final_status == "stale" and reason is None:
        reason = "stale_source"
    return Fact(
        id=id, label=label, value=number, unit=unit, decimals=decimals, signed=signed,
        display=format_value(number, unit, decimals, signed), status=final_status,
        reason=reason, source=source, as_of=as_of, method=method,
    )


def range_text(h: int, window_sessions: int, low_fact: Fact, high_fact: Fact) -> str | None:
    """The fixed rr-1 sentence, or None when either end is unavailable."""
    if low_fact.display is None or high_fact.display is None:
        return None
    period = "the last 3 years" if window_sessions == 756 else f"the last {round(window_sessions / 21)} months"
    return (
        f"Over {period}, 8 in 10 of this stock's {h}-trading-day returns fell between "
        f"{low_fact.display} and {high_fact.display}. This is not a forecast."
    )
