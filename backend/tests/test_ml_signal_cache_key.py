"""ML-24: the ml-signal cache key carries the deployed model_version.

A model swap must not serve the previous model's cached signal for an hour.
No network: the version probe, the signal call and the cache are all stubbed.
"""
import asyncio
import sys
import types

import services.ml_signal_service as svc
from schemas.ml_signal import MLSignalResponse


def _ready(symbol: str, version: str) -> MLSignalResponse:
    return MLSignalResponse(
        symbol=symbol,
        direction=1,
        direction_label="BULLISH",
        confidence=0.6,
        confidence_pct=60,
        model_version=version,
        ml_engine_mode="trained_lightgbm_baseline",
        lightgbm_loaded=True,
        generated_at="2026-10-11T00:00:00+00:00",
        status="ready",
        signal_state="ok",
    )


def test_cache_key_changes_with_model_version(monkeypatch):
    store: dict = {}
    keys_set: list = []
    fake_cache = types.SimpleNamespace(
        get=lambda ns, key: store.get((ns, key)),
        set=lambda ns, key, value, ttl=None: (keys_set.append(key), store.__setitem__((ns, key), value)),
    )
    monkeypatch.setitem(sys.modules, "services.disk_cache", fake_cache)

    versions = iter(["v1", "v1", "v2"])
    current = {}

    async def _version():
        current["v"] = next(versions)
        return current["v"]

    calls = []

    async def _signal(symbol):
        calls.append(symbol)
        return _ready(symbol, current["v"])

    monkeypatch.setattr(svc, "get_ml_model_version", _version)
    monkeypatch.setattr(svc, "get_ml_signal", _signal)

    first = asyncio.run(svc.get_ml_signal_cached("tcs"))
    again = asyncio.run(svc.get_ml_signal_cached("TCS"))   # same version: cache hit
    swapped = asyncio.run(svc.get_ml_signal_cached("TCS"))  # new version: miss

    assert calls == ["tcs", "TCS"]
    assert first.model_version == again.model_version == "v1"
    assert swapped.model_version == "v2"
    assert len(keys_set) == 2
    assert "v1" in keys_set[0] and "TCS" in keys_set[0]
    assert "v2" in keys_set[1]


def test_unavailable_is_not_cached(monkeypatch):
    keys_set: list = []
    fake_cache = types.SimpleNamespace(
        get=lambda ns, key: None,
        set=lambda ns, key, value, ttl=None: keys_set.append(key),
    )
    monkeypatch.setitem(sys.modules, "services.disk_cache", fake_cache)

    async def _version():
        return None

    async def _signal(symbol):
        return svc._build_unavailable_response(symbol, "ML engine is not running")

    monkeypatch.setattr(svc, "get_ml_model_version", _version)
    monkeypatch.setattr(svc, "get_ml_signal", _signal)

    result = asyncio.run(svc.get_ml_signal_cached("INFY"))
    assert result.status == "unavailable"
    assert keys_set == []
