"""Platform flags (services/feature_flags.py) and GET /api/v1/flags.

Distinct from tests/test_feature_flags.py, which covers the env-only core flags.
"""
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import ENGINE, get_session
from models.db_models import FeatureFlag
from routers import flags as flags_router
from services import feature_flags as ff


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    FeatureFlag.__table__.create(ENGINE, checkfirst=True)
    monkeypatch.delenv("FEATURE_ANALYTICS", raising=False)
    with get_session() as s:
        s.query(FeatureFlag).delete()
        s.commit()
    ff._reset_cache()
    yield
    with get_session() as s:
        s.query(FeatureFlag).delete()
        s.commit()
    ff._reset_cache()


def test_default_off():
    assert ff.is_enabled("analytics") is False
    assert ff.client_flags() == {"analytics": False}
    entry = ff.list_flags()[0]
    assert entry["source"] == "default" and entry["client_visible"] is True


def test_env_override(monkeypatch):
    monkeypatch.setenv("FEATURE_ANALYTICS", "On")
    assert ff.is_enabled("analytics") is True
    assert ff.list_flags()[0]["source"] == "env"


def test_garbage_env_ignored(monkeypatch):
    monkeypatch.setenv("FEATURE_ANALYTICS", "maybe")
    assert ff.is_enabled("analytics") is False


def test_db_beats_env(monkeypatch):
    monkeypatch.setenv("FEATURE_ANALYTICS", "true")
    ff.set_flag("analytics", False, actor_id=7)
    assert ff.is_enabled("analytics") is False
    entry = ff.list_flags()[0]
    assert entry["source"] == "db" and entry["updated_by"] == 7 and entry["updated_at"].endswith("Z")


def test_unregistered_key_false_and_set_raises():
    assert ff.is_enabled("nope") is False
    with pytest.raises(KeyError):
        ff.set_flag("nope", True, 1)


def test_unregistered_db_row_listed():
    with get_session() as s:
        from datetime import datetime
        s.add(FeatureFlag(key="stale_key", enabled=True, updated_at=datetime.utcnow()))
        s.commit()
    ff._reset_cache()
    stale = [f for f in ff.list_flags() if f["key"] == "stale_key"][0]
    assert stale["description"] == "unregistered" and stale["client_visible"] is False


def test_set_flag_visible_immediately():
    assert ff.is_enabled("analytics") is False
    out = ff.set_flag("analytics", True, actor_id=1)
    assert out["enabled"] is True
    assert ff.is_enabled("analytics") is True


def test_db_outage_falls_back(monkeypatch):
    @contextmanager
    def boom():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(ff, "get_session", boom)
    monkeypatch.setenv("FEATURE_ANALYTICS", "true")
    ff._reset_cache()
    assert ff.is_enabled("analytics") is True
    monkeypatch.delenv("FEATURE_ANALYTICS")
    ff._reset_cache()
    assert ff.client_flags() == {"analytics": False}


def test_public_endpoint_body_and_headers():
    app = FastAPI()
    app.include_router(flags_router.router)
    r = TestClient(app).get("/api/v1/flags")
    assert r.status_code == 200
    assert r.json() == {"flags": {"analytics": False}}
    assert "no-store" in r.headers["cache-control"] and "private" in r.headers["cache-control"]
    assert r.headers["vary"] == "Authorization"


def test_no_forbidden_names():
    src = open(ff.__file__).read()
    for word in ("get_value", "privacy_center", "ops_model_canary"):
        assert word not in src
