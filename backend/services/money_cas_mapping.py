"""CAS statement -> fund balances (spec 3.5). Pure: no DB, no network, no PDF.

``normalize`` keeps only what Nivesh stores (scheme name, ISIN, AMFI code, AMC, units and the
statement's valuation) and drops everything personal: investor name, PAN, email, address,
mobile, KYC, nominees, advisor, folio numbers and transactions. ``plan`` turns the
normalized statement into one balance restatement per ISIN.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

ZERO_UNITS = 0.0005
_DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y", "%d-%m-%Y")


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _dec(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def to_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _iso(value: Any) -> Optional[str]:
    d = to_date(value)
    return d.isoformat() if d else None


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split())[:200]


def _f(value: Optional[Decimal], places: int = 4) -> Optional[float]:
    return None if value is None else round(float(value), places)


def normalize(cas: Any) -> dict:
    """The privacy-minimal statement: ``{statement, schemes}`` with folios combined per ISIN."""
    period = _get(cas, "statement_period") or {}
    statement = {
        "from": _iso(_get(period, "from") or _get(period, "from_")),
        "to": _iso(_get(period, "to")),
        "source": str(_get(cas, "file_type") or "UNKNOWN"),
        "type": str(_get(cas, "cas_type") or "UNKNOWN"),
    }
    combined: dict[str, dict] = {}
    order: list[str] = []
    for folio in _get(cas, "folios") or []:
        amc = _clean(_get(folio, "amc"))
        for scheme in _get(folio, "schemes") or []:
            isin = (_get(scheme, "isin") or "").strip().upper() or None
            name = _clean(_get(scheme, "scheme"))
            key = isin or f"noisin:{name}:{len(order)}"
            val = _get(scheme, "valuation") or {}
            units = _dec(_get(scheme, "close")) or Decimal(0)
            value = _dec(_get(val, "value")) or Decimal(0)
            cost = _dec(_get(val, "cost"))
            nav = _dec(_get(val, "nav"))
            vdate = to_date(_get(val, "date"))
            empty = units <= Decimal(str(ZERO_UNITS))
            cost_known = empty or (cost is not None and cost > 0)
            cost = cost if cost is not None else Decimal(0)
            row = combined.get(key)
            if row is None:
                order.append(key)
                combined[key] = {
                    "amc": amc, "name": name, "isin": isin, "amfi": _get(scheme, "amfi") or None,
                    "units": units, "value": value, "cost": cost,
                    "cost_ok": cost_known, "date": vdate, "nav": nav,
                }
                continue
            row["units"] += units
            row["value"] += value
            row["cost_ok"] = row["cost_ok"] and cost_known
            row["cost"] = row["cost"] + cost
            if vdate and (row["date"] is None or vdate >= row["date"]):
                row["date"], row["nav"] = vdate, nav
    schemes = []
    for key in order:
        r = combined[key]
        schemes.append({
            "amc": r["amc"], "name": r["name"], "isin": r["isin"], "amfi": r["amfi"],
            "close": _f(r["units"], 4),
            "valuation": {"date": r["date"].isoformat() if r["date"] else None, "nav": _f(r["nav"], 4),
                          "value": _f(r["value"], 2), "cost": _f(r["cost"], 2) if r["cost_ok"] else None},
        })
    return {"statement": statement, "schemes": schemes}


def adjust_key(isin: str, to: str, close: float) -> str:
    return "casbal:" + hashlib.sha256(f"{isin}|{to}|{close:.3f}".encode()).hexdigest()[:48]


def plan(normalized: dict, existing_cas: Mapping[str, date], manual: set[str]) -> list[dict]:
    """One entry per scheme: ``mode`` 'balance' (with ``adjust``) or 'skipped' (with ``reason``)."""
    to_str = normalized["statement"]["to"]
    to = to_date(to_str)
    out: list[dict] = []
    for s in normalized["schemes"]:
        isin, units = s["isin"], float(s["close"] or 0.0)
        val = s["valuation"]
        entry = {
            "isin": isin, "name": s["name"], "amc": s["amc"], "amfi": s.get("amfi"), "units": round(units, 3),
            "valuation": {"date": val["date"], "nav": val["nav"], "value_inr": val["value"], "cost_inr": val["cost"]},
            "mode": "skipped", "reason": None, "flags": [], "adjust": None,
        }
        existing = existing_cas.get(isin) if isin else None
        if not isin:
            entry["reason"] = "isin_missing"
        elif isin in manual:
            entry["reason"] = "manual_entries_exist"
        elif existing is not None and to is not None and existing >= to:
            entry["reason"] = "older_statement"
        elif units <= ZERO_UNITS and existing is None:
            entry["reason"] = "zero_balance"
        else:
            closing = units <= ZERO_UNITS
            cost, nav = val["cost"], val["nav"]
            if closing:
                price = 0.0
            elif cost and units > 0:
                price = round(cost / units, 4)
            else:
                price = float(nav or 0.0)
                entry["flags"].append("cost_unknown")
            qty = 0.0 if closing else round(units, 3)
            entry["mode"] = "balance"
            entry["adjust"] = {"quantity": qty, "price": price, "date": to_str, "key": adjust_key(isin, to_str, qty)}
        out.append(entry)
    return out


def preview_summary(plans: list[dict]) -> dict:
    balance = [p for p in plans if p["mode"] == "balance"]
    return {
        "schemes": len(plans), "balance": len(balance), "skipped": len(plans) - len(balance),
        "value_inr": round(sum(float(p["valuation"]["value_inr"] or 0.0) for p in balance), 2),
    }
