import pytest


# A tiny schedule so tests do not depend on the real, evolving rate file.
SCHEDULE = {
    "components": {
        "stt": [{"effective_from": "2000-01-01", "effective_to": None, "delivery_buy_rate": 0.001, "delivery_sell_rate": 0.001, "intraday_buy_rate": 0, "intraday_sell_rate": 0.00025, "source_id": "t"}],
        "exchange_txn_nse": [
            {"effective_from": "2000-01-01", "effective_to": "2024-10-01", "rate": 0.0000322, "source_id": "t"},
            {"effective_from": "2024-10-01", "effective_to": None, "rate": 0.0000297, "source_id": "t2"},
        ],
        "sebi_turnover_fee": [{"effective_from": "2000-01-01", "effective_to": None, "rate_per_crore_inr": 10, "source_id": "t"}],
        "stamp_duty": [{"effective_from": "2000-01-01", "effective_to": None, "delivery_buy_rate": 0.00015, "intraday_buy_rate": 0.00003, "source_id": "t"}],
        "gst": [{"effective_from": "2000-01-01", "effective_to": None, "rate": 0.18, "applies_to": ["brokerage", "exchange_txn", "sebi_fee"], "source_id": "t"}],
    }
}


@pytest.fixture(autouse=True)
def _fixed_schedule(monkeypatch):
    import lab.costs as costs
    monkeypatch.setattr(costs, "load_schedule", lambda path=None: SCHEDULE)
