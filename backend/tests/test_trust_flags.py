"""Trust-cluster flags in services/feature_flags.py (C2, I04, I02).

Hermetic: no DB, no network. Every NIVESH_FLAG_* var for these keys is unset per
test and the flag cache is reset before and after each case.
"""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from services import feature_flags

LLM_KEYS = [
    "llm_enabled", "llm_copilot", "llm_analysis", "llm_screener",
    "llm_youtube_summary", "llm_portfolio_insights", "llm_research_prose", "llm_harvest",
]
EXPECTED = {
    **{key: (True, False) for key in LLM_KEYS},  # (default, client)
    "forum": (False, True),
    "ipo_hub": (False, True),
}
PROBE_PATH = "/_trust_flag_probe"  # variable path: TEST-20's route inventory ignores it


@pytest.fixture(autouse=True)
def _clean_flags(monkeypatch):
    for key in EXPECTED:
        monkeypatch.delenv(f"NIVESH_FLAG_{key.upper()}", raising=False)
    feature_flags._reset_cache()
    yield
    feature_flags._reset_cache()


def test_trust_keys_registered_with_defaults_and_visibility():
    for key, (default, client) in EXPECTED.items():
        spec = feature_flags.FLAG_DEFAULTS[key]
        assert spec["default"] is default, key
        assert spec["client"] is client, key
        assert spec["description"], key
    assert "harvester reformatter" in feature_flags.FLAG_DEFAULTS["llm_harvest"]["description"]


def test_client_flags_show_forum_and_ipo_hub_off_and_hide_llm_switches():
    flags = feature_flags.client_flags()
    assert flags["forum"] is False
    assert flags["ipo_hub"] is False
    assert not any(key in flags for key in LLM_KEYS)


def _probe_client():
    app = FastAPI()
    app.add_api_route(PROBE_PATH, lambda: {"ok": True}, methods=["GET"],
                      dependencies=[Depends(feature_flags.require_flag("forum"))])
    return TestClient(app)


def test_require_flag_off_returns_404_feature_disabled():
    resp = _probe_client().get(PROBE_PATH)
    assert resp.status_code == 404
    assert resp.json() == {"detail": {"code": "FEATURE_DISABLED", "feature": "forum"}}


def test_require_flag_on_via_env_returns_200(monkeypatch):
    monkeypatch.setenv("NIVESH_FLAG_FORUM", "true")
    feature_flags._reset_cache()
    resp = _probe_client().get(PROBE_PATH)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_require_flag_rejects_unregistered_key():
    with pytest.raises(KeyError):
        feature_flags.require_flag("forum_typo")
