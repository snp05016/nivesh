"""CMKT-05: quarterly chart labels must be unique Indian fiscal quarters, not 'Q%q 2025'."""
import re

import pandas as pd

from routers import market
from services.market_service import quarter_label, quarterly_rows

_LABEL = re.compile(r"^Q[1-4] FY\d{2}$")


def _fin() -> pd.DataFrame:
    cols = [pd.Timestamp(d) for d in
            ("2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31")]
    return pd.DataFrame(
        [[5.0e10, 4.0e10, 3.0e10, 2.0e10, 1.0e10],
         [5.0e9, 4.0e9, 3.0e9, float("nan"), 1.0e9]],
        index=["Total Revenue", "Net Income"], columns=cols,
    )


def test_quarter_label_indian_fy():
    assert quarter_label(pd.Timestamp("2025-06-30")) == "Q1 FY26"
    assert quarter_label(pd.Timestamp("2025-09-30")) == "Q2 FY26"
    assert quarter_label(pd.Timestamp("2025-12-31")) == "Q3 FY26"
    assert quarter_label(pd.Timestamp("2026-03-31")) == "Q4 FY26"
    assert quarter_label("2025-06") == "2025-06"


def test_quarterly_rows_unique_labels():
    rows = quarterly_rows(_fin())
    labels = [r["label"] for r in rows]
    assert labels == ["Q4 FY26", "Q3 FY26", "Q2 FY26", "Q1 FY26", "Q4 FY25"]
    assert all(_LABEL.match(lbl) for lbl in labels)
    assert rows[0]["revenue"] == 5000.0  # 5e10 rupees = 5,000 crore
    assert rows[0]["net_profit"] == 500.0
    assert rows[3]["net_profit"] == 0.0  # NaN -> 0.0 (iOS field is non-optional)
    assert quarterly_rows(None) == []
    assert quarterly_rows(pd.DataFrame()) == []


def test_quarterly_financials_endpoint_labels(monkeypatch):
    monkeypatch.setattr(market, "_dcache_get", lambda namespace, key: None)
    monkeypatch.setattr(market, "_dcache_set", lambda *a, **k: None)
    monkeypatch.setattr(market, "_resolve_ticker", lambda t, e: f"{t}.NS")
    monkeypatch.setattr(market, "_get_quarterly_fin", lambda full_ticker: (None, _fin()))

    payload = market.quarterly_financials_endpoint("TCS")
    labels = [q["label"] for q in payload["quarters"]]
    assert len(labels) == 5
    assert len(set(labels)) == len(labels)
    assert all(_LABEL.match(lbl) for lbl in labels)
