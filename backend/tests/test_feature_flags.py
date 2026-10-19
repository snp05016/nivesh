"""Server-side feature flags (core/feature_flags.py, services/feature_flags.py) and GET /api/v1/features.

Hermetic: env vars are set per test with monkeypatch; route tests mount routers
on a fresh FastAPI() except the wiring test, which uses the shared app client.
"""
import logging

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from core import feature_flags as ff
from routers import features as features_router

DEFAULTS = {
    "money_holding_detail": True,
    "money_xirr_card": True,
    "money_journal_scoring": True,
    "money_cas_import": False,
    "money_xray": False,
    "money_commission_drag": False,
    "money_tax_report": False,
    "money_crisis_replay": False,
    "notif_prefs_v2": False,
    "today_brief": False,
    "event_radar": False,
    "watchlist_v2": False,
    "widget_snapshot": True,
    # iOS cluster (served with their effective rules; see test_app_config.py)
    "stock_action_bar": True,
    "stock_key_facts": False,
    "stock_peers": False,
    "compare": False,
    "onboarding_v2": True,
    "home_bell_inbox": True,
    "hindi_glossary": False,
    "hindi_brief": False,
}


@pytest.fixture(autouse=True)
def _clean_flag_env(monkeypatch):
    """Every FEATURE_* var unset and the warn-once memory empty, whatever the host has."""
    for env_name, _default in ff.FLAGS.values():
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setattr(ff, "_warned", set())


def _set(monkeypatch, key, value):
    monkeypatch.setenv(ff.FLAGS[key][0], value)


def test_registry_matches_spec():
    assert {k: d for k, (_env, d) in ff.FLAGS.items()} == DEFAULTS
    assert all(env == "FEATURE_" + key.upper() for key, (env, _d) in ff.FLAGS.items())


def test_defaults_when_unset():
    assert {key: ff.is_enabled(key) for key in DEFAULTS} == DEFAULTS
    assert ff.client_flags() == DEFAULTS


@pytest.mark.parametrize("raw,expected", [
    ("TRUE", True), (" on ", True), ("1", True), ("Yes", True),
    ("0", False), ("false", False), (" OFF ", False), ("no", False),
])
def test_tokens_parse(monkeypatch, raw, expected):
    _set(monkeypatch, "money_cas_import", raw)        # default off
    _set(monkeypatch, "money_holding_detail", raw)    # default on
    assert ff.is_enabled("money_cas_import") is expected
    assert ff.is_enabled("money_holding_detail") is expected


def test_read_on_every_call(monkeypatch):
    assert ff.is_enabled("money_xray") is False
    _set(monkeypatch, "money_xray", "true")
    assert ff.is_enabled("money_xray") is True


def test_invalid_value_falls_back_with_one_warning(monkeypatch, caplog):
    _set(monkeypatch, "money_tax_report", "enabled")
    _set(monkeypatch, "money_xirr_card", "")
    with caplog.at_level(logging.WARNING, logger=ff.logger.name):
        for _ in range(3):
            assert ff.is_enabled("money_tax_report") is False
            assert ff.is_enabled("money_xirr_card") is True
    warnings = [r for r in caplog.records if r.name == ff.logger.name and r.levelno == logging.WARNING]
    assert len(warnings) == 2  # one per key, not one per call
    assert "FEATURE_MONEY_TAX_REPORT" in warnings[0].getMessage()
    assert "enabled" not in warnings[0].getMessage()  # raw value is not echoed


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        ff.is_enabled("money_typo")
    with pytest.raises(KeyError):
        ff.require_flag("money_typo")


def _features_app():
    app = FastAPI()
    app.include_router(features_router.router)
    return TestClient(app)


def test_features_endpoint_without_auth(monkeypatch):
    _set(monkeypatch, "money_crisis_replay", "on")
    resp = _features_app().get("/api/v1/features")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 1
    assert body["ttl_seconds"] == 300
    assert set(body["flags"]) == set(DEFAULTS)
    assert all(isinstance(v, bool) for v in body["flags"].values())
    assert body["flags"] == {**DEFAULTS, "money_crisis_replay": True}
    assert resp.headers["cache-control"] == "private, max-age=300"


def test_features_endpoint_is_wired_into_main_app(client):
    resp = client.get("/api/v1/features")
    assert resp.status_code == 200
    assert resp.json() == {"flags": DEFAULTS, "version": 1, "ttl_seconds": 300}
    # SecurityHeadersMiddleware keeps the route's own Cache-Control.
    assert resp.headers["cache-control"] == "private, max-age=300"


def _guarded_app(key="money_xray"):
    app = FastAPI()

    @app.get("/dummy", dependencies=[Depends(ff.require_flag(key))])
    def dummy():
        return {"ok": True}

    return TestClient(app)


def test_require_flag_off_returns_404_feature_disabled():
    resp = _guarded_app().get("/dummy")
    assert resp.status_code == 404
    assert resp.json() == {
        "detail": {"code": "FEATURE_DISABLED", "message": "This feature isn't available."}
    }


def test_require_flag_on_returns_200(monkeypatch):
    _set(monkeypatch, "money_xray", "true")
    resp = _guarded_app().get("/dummy")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# ── Habit cluster: tri-state event_radar and the services.feature_flags path ──

def test_mode_parses_on_off(monkeypatch):
    assert ff.mode("widget_snapshot") == "on"
    assert ff.mode("today_brief") == "off"
    _set(monkeypatch, "widget_snapshot", "no")
    _set(monkeypatch, "today_brief", " YES ")
    assert ff.mode("widget_snapshot") == "off"
    assert ff.mode("today_brief") == "on"


def test_event_radar_shadow_reads_as_off(monkeypatch):
    _set(monkeypatch, "event_radar", " Shadow ")
    assert ff.mode("event_radar") == "shadow"
    assert ff.is_enabled("event_radar") is False
    assert ff.client_flags()["event_radar"] is False
    resp = _guarded_app("event_radar").get("/dummy")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_shadow_on_two_state_flag_falls_back_with_one_warning(monkeypatch, caplog):
    _set(monkeypatch, "today_brief", "shadow")
    with caplog.at_level(logging.WARNING, logger=ff.logger.name):
        assert ff.mode("today_brief") == "off"
        assert ff.mode("today_brief") == "off"
    warnings = [r for r in caplog.records if r.name == ff.logger.name and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "FEATURE_TODAY_BRIEF" in warnings[0].getMessage()


def test_require_flag_dependency_direct(monkeypatch):
    dep = ff.require_flag("notif_prefs_v2")
    with pytest.raises(HTTPException) as exc:
        dep()
    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "FEATURE_DISABLED", "message": "This feature isn't available."}
    _set(monkeypatch, "notif_prefs_v2", "on")
    assert dep() is None


def test_services_path_is_the_same_registry(monkeypatch):
    from services import feature_flags as sff
    assert sff.mode is ff.mode and sff.is_enabled is ff.is_enabled and sff.require_flag is ff.require_flag
    _set(monkeypatch, "watchlist_v2", "1")
    assert sff.public_flags() == {**DEFAULTS, "watchlist_v2": True}
    with pytest.raises(KeyError):
        sff.mode("habit_typo")
