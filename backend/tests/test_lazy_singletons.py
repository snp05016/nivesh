"""REL-20: lazy model singletons load once under concurrency and memoize failures."""
import sys
import threading
from types import SimpleNamespace

import pytest

from services import confidence_fusion, sentiment_engine


@pytest.fixture
def fresh_classifier(monkeypatch):
    monkeypatch.setattr(sentiment_engine, "_classifier", None)
    monkeypatch.setattr(sentiment_engine, "_load_failed_at", None)


def test_finbert_single_load_under_concurrency(monkeypatch, fresh_classifier):
    calls = []
    count_lock = threading.Lock()

    def fake_pipeline(*args, **kwargs):
        with count_lock:
            calls.append(1)
        threading.Event().wait(0.05)
        return object()

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(pipeline=fake_pipeline))

    n = 20
    barrier = threading.Barrier(n)
    results: list[object] = [None] * n

    def worker(i):
        barrier.wait()
        results[i] = sentiment_engine.get_classifier()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(calls) == 1
    assert results[0] is not None
    assert all(r is results[0] for r in results)


def test_finbert_failure_backoff(monkeypatch, fresh_classifier):
    calls = []

    def failing_pipeline(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("HF download failed")

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(pipeline=failing_pipeline))
    clock = [1000.0]
    monkeypatch.setattr(sentiment_engine, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    for _ in range(5):
        assert sentiment_engine.get_classifier() is None
    assert len(calls) == 1

    clock[0] += sentiment_engine._RETRY_AFTER_SEC + 1
    assert sentiment_engine.get_classifier() is None
    assert len(calls) == 2


def test_dynamic_weights_cached_when_not_confident(monkeypatch):
    import services.prediction_calibration_service as pcs

    calls = []

    def fake_recs(min_sample=100):
        calls.append(min_sample)
        return {"is_confident": False}

    monkeypatch.setenv("FUSION_DYNAMIC_WEIGHTS_ENABLED", "true")  # off by default (ML-04)
    monkeypatch.setattr(pcs, "get_fusion_weight_recommendations", fake_recs)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE", None)
    monkeypatch.setattr(confidence_fusion, "_WEIGHTS_CACHE_TIME", 0.0)

    for _ in range(3):
        assert confidence_fusion._get_dynamic_weights() is None
    assert len(calls) == 1
