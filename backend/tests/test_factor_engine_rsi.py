"""MATH-23: numpy RSI fallback must use Wilder smoothing and return 100 on no losses."""
import numpy as np
import pandas as pd
import pytest

from services.factor_engine import _rsi_numpy


def test_strictly_increasing_is_100():
    assert _rsi_numpy(pd.Series(np.arange(1.0, 31.0))) == 100.0


def test_strictly_decreasing_is_0():
    assert _rsi_numpy(pd.Series(np.arange(30.0, 0.0, -1.0))) == 0.0


def test_insufficient_history_is_neutral():
    assert _rsi_numpy(pd.Series([100.0, 101.0, 102.0])) == 50.0


def test_matches_ta_wilder_rsi():
    ta_momentum = pytest.importorskip("ta.momentum")
    rng = np.random.default_rng(1)
    close = pd.Series(100.0 + np.cumsum(rng.normal(0.0, 1.0, 60)))
    expected = float(ta_momentum.RSIIndicator(close=close, window=14).rsi().iloc[-1])
    assert abs(_rsi_numpy(close) - expected) < 0.01
