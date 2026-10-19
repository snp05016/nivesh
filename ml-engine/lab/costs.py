"""Effective-date-aware Indian cash-equity (delivery) trading charges.

Rates live in `india_charges.json` with a source for every row; this module only
does the arithmetic. Brokerage is broker-specific, so it is a parameter.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

SCHEDULE_PATH = Path(__file__).with_name("india_charges.json")
CRORE = 1e7


@dataclass(frozen=True)
class Brokerage:
    """Default = typical discount-broker delivery pricing: min(flat, pct * value). Set both 0 for zero-brokerage."""
    flat_inr: float = 20.0
    pct: float = 0.0003

    def fee(self, value: float) -> float:
        return min(self.flat_inr, self.pct * value) if self.pct else self.flat_inr


@lru_cache(maxsize=4)
def load_schedule(path: str = str(SCHEDULE_PATH)) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _row(rows: list[dict], d: date) -> dict:
    iso = d.isoformat()
    hits = [r for r in rows if r["effective_from"] <= iso and (r.get("effective_to") in (None, "") or iso < r["effective_to"])]
    if not hits:
        raise LookupError(f"no charge row effective on {iso}")
    return max(hits, key=lambda r: r["effective_from"])


def charges(side: str, value: float, d: date, brokerage: Brokerage = Brokerage(), schedule: dict | None = None) -> dict:
    """Charges in INR for one delivery fill of `value` rupees on trading day `d`.

    Returns a breakdown plus `total` and the source ids used, so a contract note
    can be shown to the user.
    """
    if side not in ("BUY", "SELL"):
        raise ValueError(side)
    s = (schedule or load_schedule())["components"]
    buy = side == "BUY"
    stt_r = _row(s["stt"], d)
    exc_r = _row(s["exchange_txn_nse"], d)
    sebi_r = _row(s["sebi_turnover_fee"], d)
    stamp_r = _row(s["stamp_duty"], d)
    gst_r = _row(s["gst"], d)

    brk = brokerage.fee(value)
    stt = value * (stt_r["delivery_buy_rate"] if buy else stt_r["delivery_sell_rate"])
    exc = value * exc_r["rate"]
    sebi = value / CRORE * sebi_r["rate_per_crore_inr"]
    stamp = value * stamp_r["delivery_buy_rate"] if buy else 0.0
    taxable = {"brokerage": brk, "exchange_txn": exc, "sebi_fee": sebi}
    gst = gst_r["rate"] * sum(v for k, v in taxable.items() if k in gst_r.get("applies_to", taxable))
    out = {"brokerage": brk, "stt": stt, "exchange_txn": exc, "sebi_fee": sebi, "stamp_duty": stamp, "gst": gst}
    out = {k: round(v, 2) for k, v in out.items()}
    out["total"] = round(sum(out.values()), 2)
    out["sources"] = sorted({r.get("source_id", "") for r in (stt_r, exc_r, sebi_r, stamp_r, gst_r)} - {""})
    return out
