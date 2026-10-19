"""services/data_flags.py: defaults, env cohort allowlists and require(). Hermetic."""
import logging

import pytest
from fastapi import HTTPException

from core import feature_flags as ff
from services import data_flags

KEYS = ["data_instruments", "data_eod_prices", "data_eod_display",
        "data_mf_universe", "data_corp_actions_confirm", "data_results_digest"]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(ff.FLAGS[key][0], raising=False)
        monkeypatch.delenv("FEATURE_" + key.upper() + "_USERS", raising=False)
    monkeypatch.setattr(data_flags, "_warned", set())


def test_defaults():
    assert [ff.FLAGS[k][1] for k in KEYS] == [True, True, False, True, False, False]
    assert [data_flags.enabled(k) for k in KEYS] == [True, True, False, True, False, False]


def test_allowlisted_id_enabled_while_flag_off(monkeypatch):
    monkeypatch.setenv("FEATURE_DATA_RESULTS_DIGEST_USERS", "5, 9")
    assert not data_flags.enabled("data_results_digest")
    assert data_flags.enabled_for("data_results_digest", 5)
    assert not data_flags.enabled_for("data_results_digest", 6)
    assert not data_flags.enabled_for("data_results_digest", None)


def test_parse_and_warn_once(monkeypatch, caplog):
    monkeypatch.setenv("FEATURE_DATA_RESULTS_DIGEST_USERS", " 12, abc ,7")
    with caplog.at_level(logging.WARNING, logger=data_flags.logger.name):
        assert data_flags._allowlist("data_results_digest") == frozenset({12, 7})
        assert data_flags._allowlist("data_results_digest") == frozenset({12, 7})
    assert len([r for r in caplog.records if "abc" in r.getMessage()]) == 1


def test_non_positive_ignored(monkeypatch):
    monkeypatch.setenv("FEATURE_DATA_RESULTS_DIGEST_USERS", "0,-3,4")
    assert data_flags._allowlist("data_results_digest") == frozenset({4})


def test_any_enabled_with_only_allowlist(monkeypatch):
    assert not data_flags.any_enabled("data_corp_actions_confirm")
    monkeypatch.setenv("FEATURE_DATA_CORP_ACTIONS_CONFIRM_USERS", "3")
    assert data_flags.any_enabled("data_corp_actions_confirm")
    assert data_flags.any_enabled("data_instruments")


def test_require(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        data_flags.require("data_corp_actions_confirm", 1)
    assert exc.value.status_code == 404
    assert exc.value.detail == {"code": "FEATURE_DISABLED", "feature": "data_corp_actions_confirm"}
    monkeypatch.setenv("FEATURE_DATA_CORP_ACTIONS_CONFIRM_USERS", "1")
    assert data_flags.require("data_corp_actions_confirm", 1) is None
    assert data_flags.require("data_instruments") is None
