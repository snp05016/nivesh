"""ML-11: shared ml-engine OHLCV payload builder (pure function, no network)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from services.qlib_engine.ml_client import build_ml_ohlcv_payload

IST = ZoneInfo("Asia/Kolkata")
LAST_DAY = "2026-03-10"


def _hist(n: int, end: str = LAST_DAY, tz: str | None = None) -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=n, tz=tz)
    close = 100.0 + np.arange(n, dtype=float)
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1000.0},
        index=idx,
    )


def test_completed_history_is_emitted_ascending_without_vwap():
    out = build_ml_ohlcv_payload(_hist(130), now=datetime(2026, 3, 11, 10, 0, tzinfo=IST))
    assert len(out) == 130
    assert all("vwap" not in row for row in out)
    dates = [row["date"] for row in out]
    assert dates == sorted(dates) and len(set(dates)) == len(dates)
    assert dates[-1] == LAST_DAY
    assert set(out[0]) == {"date", "open", "high", "low", "close", "volume"}


def test_in_progress_bar_dropped_during_session():
    out = build_ml_ohlcv_payload(_hist(130), now=datetime(2026, 3, 10, 10, 0, tzinfo=IST))
    assert len(out) == 129
    assert out[-1]["date"] == "2026-03-09"


def test_todays_bar_kept_after_close():
    out = build_ml_ohlcv_payload(_hist(130), now=datetime(2026, 3, 10, 16, 0, tzinfo=IST))
    assert len(out) == 130
    assert out[-1]["date"] == LAST_DAY


def test_tz_aware_index_keeps_exchange_trading_date():
    out = build_ml_ohlcv_payload(
        _hist(130, tz="Asia/Kolkata"), now=datetime(2026, 3, 10, 10, 0, tzinfo=IST)
    )
    assert out[-1]["date"] == "2026-03-09"


def test_nan_and_duplicate_rows_removed_and_order_fixed():
    df = _hist(140)
    df.iloc[5, df.columns.get_loc("Close")] = np.nan
    df = pd.concat([df, df.iloc[[10]]]).iloc[::-1]  # duplicate date, reversed order
    out = build_ml_ohlcv_payload(df, now=datetime(2026, 3, 11, 10, 0, tzinfo=IST))
    dates = [row["date"] for row in out]
    assert len(out) == 139
    assert dates == sorted(dates) and len(set(dates)) == len(dates)


def test_short_history_returns_empty():
    now = datetime(2026, 3, 11, 10, 0, tzinfo=IST)
    assert build_ml_ohlcv_payload(_hist(100), now=now) == []
    assert build_ml_ohlcv_payload(None, now=now) == []
    assert build_ml_ohlcv_payload(pd.DataFrame(), now=now) == []


def test_capped_at_252_rows():
    out = build_ml_ohlcv_payload(_hist(400), now=datetime(2026, 3, 11, 10, 0, tzinfo=IST))
    assert len(out) == 252
