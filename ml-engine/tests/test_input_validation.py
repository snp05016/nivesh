"""ML-11: inference-boundary validation and train/serve feature parity."""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

import lightgbm  # noqa: F401  load in the main thread; first import in TestClient's portal thread segfaults on macOS
import numpy as np
import pandas as pd
import polars as pl
import pytest
from fastapi.testclient import TestClient

from config import FEATURE_LIST
from main import OHLCVRow, _ohlcv_to_polars, app
from pipeline.feature_computer import FeatureComputer, InvalidOHLCVError


def _frame(n: int, end: date | None = None, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    end = end or date.today()
    closes = 1500.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))
    spread = rng.uniform(0.001, 0.02, n)
    return pd.DataFrame({
        "date": [end - timedelta(days=n - 1 - i) for i in range(n)],
        "open": closes * (1.0 + rng.uniform(-0.01, 0.01, n)),
        "high": closes * (1.0 + spread),
        "low": closes * (1.0 - spread),
        "close": closes,
        "volume": rng.uniform(1e6, 5e7, n),
    })


def _payload(df: pd.DataFrame) -> list[dict]:
    rows = df.to_dict("records")
    for r in rows:
        r["date"] = r["date"].isoformat()
    return rows


def _post(rows: list[dict]):
    with TestClient(app) as client:
        return client.post("/predict/single", json={"ticker": "TEST", "ohlcv_data": rows})


def test_59_rows_insufficient_history() -> None:
    resp = _post(_payload(_frame(59)))
    assert resp.status_code == 422
    assert resp.json()["detail"] == "insufficient_history"


def test_60_rows_ok() -> None:
    assert _post(_payload(_frame(60))).status_code == 200


def test_shuffled_dates_invalid() -> None:
    rows = _payload(_frame(80))
    last = rows[-1]
    head = rows[:-1]
    random.Random(1).shuffle(head)
    resp = _post(head + [last])  # keep the newest date last so staleness passes
    assert resp.status_code == 422
    assert resp.json()["detail"] == "invalid_ohlcv"


def test_stale_input_rejected() -> None:
    resp = _post(_payload(_frame(80, end=date(2020, 6, 30))))
    assert resp.status_code == 422
    assert resp.json()["detail"] == "stale_input"


def test_nonpositive_price_invalid() -> None:
    rows = _payload(_frame(80))
    rows[10]["low"] = 0.0
    resp = _post(rows)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "invalid_ohlcv"


def test_nan_close_raises() -> None:
    df = pl.from_pandas(_frame(80)).with_columns(
        pl.when(pl.int_range(pl.len()) == 40).then(float("nan")).otherwise(pl.col("close")).alias("close")
    )
    with pytest.raises(InvalidOHLCVError):
        FeatureComputer(feature_list=FEATURE_LIST).compute_all(df)


def test_train_serve_parity_including_vwap0() -> None:
    """Training slices tail(120) of a no-vwap frame; serving gets the same rows without vwap."""
    fc = FeatureComputer(feature_list=FEATURE_LIST)
    window = _frame(150).tail(120)
    train = fc.compute_all(pl.from_pandas(window))
    serve = fc.compute_all(_ohlcv_to_polars([OHLCVRow(**r) for r in _payload(window)]))
    assert train.columns == serve.columns == FEATURE_LIST
    for col in FEATURE_LIST:
        a, b = float(train[col][0]), float(serve[col][0])
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12), col
