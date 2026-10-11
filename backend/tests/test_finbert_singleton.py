"""LLM-23: forum sentiment tagging reuses one FinBERT pipeline instead of building one per post."""
import sys
from types import SimpleNamespace

import pytest

from services import sentiment_engine
from services.forum_moderation_service import tag_sentiment


@pytest.fixture
def fresh_classifier(monkeypatch):
    monkeypatch.setattr(sentiment_engine, "_classifier", None)
    monkeypatch.setattr(sentiment_engine, "_load_failed_at", None)


def test_tag_sentiment_builds_pipeline_once(monkeypatch, fresh_classifier):
    calls = []

    def factory(*args, **kwargs):
        calls.append(kwargs)
        return lambda texts: [{"label": "positive", "score": 0.9} for _ in texts]

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(pipeline=factory))

    for _ in range(5):
        assert tag_sentiment("stock to the moon") == "bullish"
    assert len(calls) == 1


def test_failed_load_not_retried_inside_window(monkeypatch, fresh_classifier):
    calls = []

    def failing(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("HF hub unreachable")

    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(pipeline=failing))
    clock = [1000.0]
    monkeypatch.setattr(sentiment_engine, "time", SimpleNamespace(monotonic=lambda: clock[0]))

    tag_sentiment("results were fine")  # lexicon fallback
    tag_sentiment("results were fine")
    assert len(calls) == 1

    clock[0] += sentiment_engine._RETRY_AFTER_SEC + 1
    tag_sentiment("results were fine")
    assert len(calls) == 2
