"""ML-15: one outcome label definition over the full signal vocabulary."""
import pytest

from services.outcome_labels import direction_hit, signal_direction


@pytest.mark.parametrize("signal", ["BULLISH", "CAUTIOUSLY BULLISH", "BUY", "STRONG_BUY", "accumulate"])
@pytest.mark.parametrize("ret, expected", [(0.08, True), (-0.03, False), (0.0, False)])
def test_bullish_vocabulary(signal, ret, expected):
    assert direction_hit(signal, ret) is expected


@pytest.mark.parametrize("signal", ["BEARISH", "CAUTIOUSLY BEARISH", "SELL", "AVOID", "REDUCE", "EXIT"])
@pytest.mark.parametrize("ret, expected", [(-0.05, True), (0.04, False), (0.0, False)])
def test_bearish_vocabulary(signal, ret, expected):
    assert direction_hit(signal, ret) is expected


@pytest.mark.parametrize("signal", ["HOLD", "NEUTRAL", "", None, "SOMETHING ELSE"])
@pytest.mark.parametrize("ret", [0.08, -0.08, 0.0])
def test_non_directional_calls_abstain(signal, ret):
    assert signal_direction(signal) == 0
    assert direction_hit(signal, ret) is None


def test_missing_return_abstains():
    assert direction_hit("BULLISH", None) is None
    assert direction_hit("BULLISH", float("nan")) is None
