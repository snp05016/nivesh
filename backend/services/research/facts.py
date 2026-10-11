"""Facts payload for the research formatter (spec 7.1, 7.2). Pure functions on report dicts.

The payload is the only report data a language model ever sees: ok facts from
snapshot, risk, factor profile and fundamentals (as id, label and the server's
display string), band phrases for percentile facts, the as-of date, the company
name and symbol. Outlook and cohort facts, user ids, holdings and headlines are
never included (FINSEC-04).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any

from .templates import band_phrase

UNIVERSE_PHRASE = "the 200 most-traded NSE stocks"
# Reference group per percentile fact; anything not listed uses UNIVERSE_PHRASE.
BAND_REFERENCE: dict[str, str] = {
    "fund.pe_sector_pctl": "its sector peers in the 200 most-traded NSE stocks",
}
FACT_BLOCKS: tuple[str, ...] = ("snapshot", "risk", "factor_profile", "fundamentals")
PAYLOAD_PREFIXES: tuple[str, ...] = ("snapshot.", "risk.", "factor.", "fund.")
FIXED_ALLOWED_NAMES: tuple[str, ...] = ("Nifty 50", "NSE", UNIVERSE_PHRASE)

_FACT_KEYS = frozenset({"id", "value", "unit", "display", "status"})
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_UNSAFE_NAME_CHARS = re.compile(r"[{}\x00-\x1f\x7f]")
_MAX_NAME_CHARS = 120


def _is_fact(obj: object) -> bool:
    return isinstance(obj, Mapping) and _FACT_KEYS <= obj.keys()


def _walk(obj: object) -> Iterator[Mapping[str, Any]]:
    if _is_fact(obj):
        yield obj  # type: ignore[misc]
    elif isinstance(obj, Mapping):
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk(item)


def collect_facts(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Every Fact in the report except those under ``outlooks`` (cohort facts stay server-side).

    The contract holds Facts only in ``outlooks`` and the four blocks below, so
    walking just these is the same set for a valid report and never picks up a
    stray key added by a caller.
    """
    return [fact for block in FACT_BLOCKS for fact in _walk(report.get(block))]


def as_of_display(market_date: str | date) -> str:
    """'2026-10-09' -> '9 Oct 2026' (locale-independent)."""
    d = market_date if isinstance(market_date, date) else date.fromisoformat(str(market_date)[:10])
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def clean_name(value: object) -> str:
    """Company name or symbol as sent to the LLM: no braces or control characters, one line."""
    text = _UNSAFE_NAME_CHARS.sub(" ", str(value or ""))
    return " ".join(text.split())[:_MAX_NAME_CHARS].strip()


def band_reference(fact_id: str) -> str:
    return BAND_REFERENCE.get(fact_id, UNIVERSE_PHRASE)


def _sign(display: str) -> str:
    """Sign the reader sees: '+', '-' (U+2212 or ASCII) or '0' (rounds to zero)."""
    if display.startswith("+"):
        return "+"
    if display.startswith(("−", "-")):
        return "-"
    return "0"


def build_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    """The formatter payload (spec 7.2).

    ``facts``: ok facts only, as ``{id, label, unit, display, signed, sign}``
    (``sign`` is set for signed facts only). ``bands``: ``{"<pctl id>.band":
    phrase}`` for every ok percentile fact. ``as_of``: the market date as
    '9 Oct 2026'. ``allowed_names``: the only names the prose may contain.
    """
    facts: list[dict[str, Any]] = []
    bands: dict[str, str] = {}
    for fact in collect_facts(report):
        fid = str(fact["id"])
        if fact["status"] != "ok" or fact["display"] is None or not fid.startswith(PAYLOAD_PREFIXES):
            continue
        display = str(fact["display"])
        signed = bool(fact.get("signed"))
        facts.append({
            "id": fid,
            "label": str(fact.get("label") or fid),
            "unit": fact["unit"],
            "display": display,
            "signed": signed,
            "sign": _sign(display) if signed else None,
        })
        if fact["unit"] == "pctl" and fact["value"] is not None:
            bands[f"{fid}.band"] = band_phrase(float(fact["value"]), band_reference(fid))

    company_name = clean_name(report.get("company_name"))
    symbol = clean_name(report.get("symbol"))
    return {
        "company_name": company_name,
        "symbol": symbol,
        "as_of": as_of_display(report["as_of"]["market_date"]),
        "allowed_names": [company_name, symbol, *FIXED_ALLOWED_NAMES],
        "facts": facts,
        "bands": bands,
    }


def facts_hash(payload: Mapping[str, Any]) -> str:
    """sha256 of the canonical payload (facts sorted by id, keys sorted, compact UTF-8 JSON)."""
    canonical = {**payload, "facts": sorted(payload.get("facts", []), key=lambda f: f["id"])}
    blob = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
