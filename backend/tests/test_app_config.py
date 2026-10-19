"""iOS flags in core/feature_flags.py and GET /api/v1/app-config (spec_ios 1).

Hermetic: env vars are set per test with monkeypatch and research_mode() is
patched, so the host env and the research engine config never leak in.
"""
import logging
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import feature_flags as ff
from routers import features as features_router
from services.research import config as research_config

IOS_DEFAULTS = {
    "stock_action_bar": True,
    "stock_key_facts": False,
    "stock_peers": False,
    "compare": False,
    "onboarding_v2": True,
    "home_bell_inbox": True,
    "hindi_glossary": False,
    "hindi_brief": False,
    "cas_import": False,
}
RESEARCH_GATED = ("stock_key_facts", "stock_peers", "compare")
STORE_URL = "https://apps.apple.com/in/app/id1234567890"
_REAL_RESEARCH_MODE = ff.research_mode  # captured before the autouse patch


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for env_name, _default in ff.FLAGS.values():
        monkeypatch.delenv(env_name, raising=False)
    for name in ("IOS_MIN_BUILD", "IOS_APP_STORE_URL", "HINDI_LEXICON_VERSION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(ff, "_warned", set())
    monkeypatch.setattr(ff, "research_mode", lambda: "off")


def _env(monkeypatch, app_name, value):
    monkeypatch.setenv(ff.FLAGS[ff.IOS_FLAGS[app_name]][0], value)


def test_defaults_when_nothing_is_set():
    assert ff.effective_flags() == IOS_DEFAULTS
    payload = ff.app_config_payload()
    assert payload["flags"] == IOS_DEFAULTS
    assert payload["research_mode"] == "off"
    assert payload["content_languages"] == ["en"]
    assert payload["ios"] == {"min_build": 0, "app_store_url": None}
    assert ff.ios_min_build() == 0


def test_env_names_follow_feature_convention():
    for key in ff.IOS_FLAGS.values():
        assert ff.FLAGS[key][0] == "FEATURE_" + key.upper()
    assert ff.IOS_FLAGS["cas_import"] == "money_cas_import"  # one CAS flag for both clusters


@pytest.mark.parametrize("raw,expected", [("TRUE", True), (" 0 ", False), ("garbage", True)])
def test_parsing(monkeypatch, raw, expected):
    _env(monkeypatch, "onboarding_v2", raw)  # default on
    assert ff.effective_flags()["onboarding_v2"] is expected


def test_garbage_falls_back_to_default_off(monkeypatch):
    _env(monkeypatch, "hindi_glossary", "garbage")
    assert ff.effective_flags()["hindi_glossary"] is False


def test_unknown_flag_is_not_served():
    assert "typo" not in ff.effective_flags()
    with pytest.raises(KeyError):  # registry contract: a typo must not ungate a route
        ff.is_enabled("typo")


@pytest.mark.parametrize("mode,expected", [("off", False), ("shadow", False), ("on", True)])
def test_research_gated_flags(monkeypatch, mode, expected):
    for name in RESEARCH_GATED:
        _env(monkeypatch, name, "true")
    monkeypatch.setattr(ff, "research_mode", lambda: mode)
    flags = ff.effective_flags()
    assert all(flags[name] is expected for name in RESEARCH_GATED)
    assert {k: ff.client_flags()[k] for k in RESEARCH_GATED} == {k: expected for k in RESEARCH_GATED}
    assert ff.app_config_payload()["research_mode"] == mode


def test_research_gated_flags_stay_off_when_env_off(monkeypatch):
    monkeypatch.setattr(ff, "research_mode", lambda: "on")
    assert not any(ff.effective_flags()[name] for name in RESEARCH_GATED)


def test_research_mode_reads_effective_engine_mode(monkeypatch):
    monkeypatch.setattr(research_config, "CONFIG", research_config.ResearchConfig(mode="shadow"))
    assert _REAL_RESEARCH_MODE() == "shadow"
    monkeypatch.setattr(research_config, "CONFIG", research_config.ResearchConfig(mode="bogus"))
    assert _REAL_RESEARCH_MODE() == "off"


@pytest.mark.parametrize("brief,glossary,lexicon,expected", [
    ("true", "false", "", False),
    ("true", "true", "", False),
    ("true", "false", "v1", False),
    ("false", "true", "v1", False),
    ("true", "true", "  ", False),
    ("true", "true", "v1", True),
])
def test_hindi_brief_needs_glossary_and_lexicon(monkeypatch, brief, glossary, lexicon, expected):
    _env(monkeypatch, "hindi_brief", brief)
    _env(monkeypatch, "hindi_glossary", glossary)
    monkeypatch.setenv("HINDI_LEXICON_VERSION", lexicon)
    assert ff.effective_flags()["hindi_brief"] is expected


def test_hindi_brief_forced_off_warns_once(monkeypatch, caplog):
    _env(monkeypatch, "hindi_brief", "true")
    with caplog.at_level(logging.WARNING, logger=ff.logger.name):
        for _ in range(3):
            assert ff.effective_flags()["hindi_brief"] is False
    warnings = [r for r in caplog.records if r.name == ff.logger.name and r.levelno == logging.WARNING]
    assert len(warnings) == 1


@pytest.mark.parametrize("glossary,languages", [("true", ["en", "hi"]), ("false", ["en"])])
def test_content_languages_follow_hindi_glossary(monkeypatch, glossary, languages):
    _env(monkeypatch, "hindi_glossary", glossary)
    assert ff.app_config_payload()["content_languages"] == languages


@pytest.mark.parametrize("raw", ["abc", "-3", "4.5"])
def test_bad_min_build_becomes_zero(monkeypatch, caplog, raw):
    monkeypatch.setenv("IOS_APP_STORE_URL", STORE_URL)
    monkeypatch.setenv("IOS_MIN_BUILD", raw)
    with caplog.at_level(logging.ERROR, logger=ff.logger.name):
        assert ff.ios_min_build() == 0
    errors = [r.getMessage() for r in caplog.records if r.name == ff.logger.name and r.levelno == logging.ERROR]
    assert errors == ["IOS_MIN_BUILD is not a non-negative integer; serving min_build 0"]


@pytest.mark.parametrize("url", [
    "http://apps.apple.com/in/app/id1234567890",
    "https://play.google.com/store/apps/details?id=x",
    "https://apps.apple.com.evil.example/app",
    "",
])
def test_non_app_store_url_is_none(monkeypatch, url):
    monkeypatch.setenv("IOS_APP_STORE_URL", url)
    assert ff.ios_app_store_url() is None
    assert ff.app_config_payload()["ios"]["app_store_url"] is None


def test_min_build_without_store_url_serves_zero_and_logs_error(monkeypatch, caplog):
    monkeypatch.setenv("IOS_MIN_BUILD", "50")
    with caplog.at_level(logging.ERROR, logger=ff.logger.name):
        assert ff.app_config_payload()["ios"]["min_build"] == 0
        assert ff.ios_min_build() == 0
    errors = [r.getMessage() for r in caplog.records if r.name == ff.logger.name and r.levelno == logging.ERROR]
    assert errors == [  # logged once, not per call
        "IOS_MIN_BUILD=50 ignored: IOS_APP_STORE_URL is not a valid App Store URL; serving min_build 0"
    ]


def test_min_build_with_store_url(monkeypatch):
    monkeypatch.setenv("IOS_MIN_BUILD", " 50 ")
    monkeypatch.setenv("IOS_APP_STORE_URL", STORE_URL)
    assert ff.ios_min_build() == 50
    assert ff.app_config_payload()["ios"] == {"min_build": 50, "app_store_url": STORE_URL}


def test_config_path_is_the_same_registry(monkeypatch):
    # core/version_gate.py imports `from config import feature_flags`: the 426
    # gate and app-config must read one min-build value from one module.
    from config import feature_flags as gate_config

    assert gate_config is ff
    monkeypatch.setenv("IOS_MIN_BUILD", "50")
    monkeypatch.setenv("IOS_APP_STORE_URL", STORE_URL)
    assert gate_config.ios_min_build() == 50


def test_generated_at_is_utc_z():
    now = datetime(2026, 10, 11, 9, 30, 0, 123456, tzinfo=timezone.utc)
    assert ff.app_config_payload(now)["generated_at"] == "2026-10-11T09:30:00Z"


def test_payload_matches_contract_shape():
    payload = ff.app_config_payload(datetime(2026, 10, 11, 9, 30, tzinfo=timezone.utc))
    assert payload == {
        "schema_version": 1,
        "generated_at": "2026-10-11T09:30:00Z",
        "research_mode": "off",
        "flags": IOS_DEFAULTS,
        "content_languages": ["en"],
        "ios": {"min_build": 0, "app_store_url": None},
    }


def test_endpoint_without_auth_on_bare_router(monkeypatch):
    app = FastAPI()
    app.include_router(features_router.router)
    _env(monkeypatch, "compare", "true")
    resp = TestClient(app).get("/api/v1/app-config")
    assert resp.status_code == 200
    assert resp.json()["flags"]["compare"] is False  # research_mode is off


def test_endpoint_is_wired_into_main_app(client):
    resp = client.get("/api/v1/app-config")
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "public, max-age=300"
    body = resp.json()
    assert set(body) == {"schema_version", "generated_at", "research_mode", "flags", "content_languages", "ios"}
    assert body["flags"] == IOS_DEFAULTS
    assert body["ios"] == {"min_build": 0, "app_store_url": None}


def _gated_client(key):
    from fastapi import Depends

    app = FastAPI()

    @app.get("/gated", dependencies=[Depends(ff.require_flag(key))])
    def _gated():
        return {"ok": True}

    return TestClient(app)


@pytest.mark.parametrize("mode,status", [("off", 404), ("shadow", 404), ("on", 200)])
def test_require_flag_honours_research_rule(monkeypatch, mode, status):
    _env(monkeypatch, "stock_peers", "true")
    monkeypatch.setattr(ff, "research_mode", lambda: mode)
    resp = _gated_client("stock_peers").get("/gated")
    assert resp.status_code == status
    if status == 404:
        assert resp.json()["detail"]["code"] == "FEATURE_DISABLED"


@pytest.mark.parametrize("lexicon,status", [(None, 404), ("v1", 200)])
def test_require_flag_honours_hindi_brief_rule(monkeypatch, lexicon, status):
    _env(monkeypatch, "hindi_brief", "true")
    _env(monkeypatch, "hindi_glossary", "true")
    if lexicon:
        monkeypatch.setenv("HINDI_LEXICON_VERSION", lexicon)
    assert _gated_client("hindi_brief").get("/gated").status_code == status
