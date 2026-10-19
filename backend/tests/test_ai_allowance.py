"""GET /api/v1/ai/allowance, Retry-After on 429/503 and the AI_PAUSED code (spec_ai 3.1)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import func

import services.llm_utils as llm_utils
from database import get_session
from models.db_models import LlmUsage
from services import entitlement_service, llm_budget

URL = "/api/v1/ai/allowance"
BRAINSTORM = {"topic": "EV batteries", "risk_tolerance": "Moderate"}


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(llm_budget, "_global_cache", None)
    monkeypatch.setenv("LLM_USER_DAILY_BUDGET_USD_FREE", "1.0")
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "1000000")
    monkeypatch.setattr(llm_budget, "get_effective_tier", lambda _uid: "free")
    monkeypatch.setattr(entitlement_service, "get_effective_tier", lambda _uid: "free")
    with get_session() as session:
        start_id = session.query(func.max(LlmUsage.id)).scalar() or 0
    yield
    with get_session() as session:
        session.query(LlmUsage).filter(LlmUsage.id > start_id).delete()
        session.commit()


def _spend(cost, user_id=None, created_at=None):
    with get_session() as session:
        row = LlmUsage(user_id=user_id, feature="test", model="claude-sonnet-4-6", cost_usd=cost)
        if created_at is not None:
            row.created_at = created_at
        session.add(row)
        session.commit()


def test_requires_token(client):
    assert client.get(URL).status_code == 401


def test_flag_off_is_404(client, auth_headers, monkeypatch):
    monkeypatch.setenv("FEATURE_AI_ALLOWANCE", "false")
    resp = client.get(URL, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_no_usage_is_ok(client, auth_headers):
    assert client.get(URL, headers=auth_headers).json() == {"used_pct": 0, "state": "ok"}


def test_low_at_85_percent(client, auth_headers, test_user_id):
    _spend(0.85, user_id=test_user_id)
    assert client.get(URL, headers=auth_headers).json() == {"used_pct": 85, "state": "low"}


def test_exhausted_caps_at_100(client, auth_headers, test_user_id):
    _spend(1.2, user_id=test_user_id)
    assert client.get(URL, headers=auth_headers).json() == {"used_pct": 100, "state": "exhausted"}


def test_global_breaker_is_paused(client, auth_headers, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "0.01")
    _spend(1.0, user_id=None)
    assert client.get(URL, headers=auth_headers).json()["state"] == "paused"


def test_yesterdays_usage_not_counted(client, auth_headers, test_user_id):
    before_midnight = llm_budget._today_start_utc() - timedelta(hours=1)
    _spend(5.0, user_id=test_user_id, created_at=before_midnight.replace(tzinfo=None))
    assert client.get(URL, headers=auth_headers).json() == {"used_pct": 0, "state": "ok"}


def test_zero_cap_is_exhausted(test_user_id, monkeypatch):
    monkeypatch.setenv("LLM_USER_DAILY_BUDGET_USD_FREE", "0")
    assert llm_budget.allowance(test_user_id) == {"used_pct": 100, "state": "exhausted"}


def test_response_keys_are_exactly_two(client, auth_headers, test_user_id):
    _spend(0.5, user_id=test_user_id)
    body = client.get(URL, headers=auth_headers).json()
    assert set(body) == {"used_pct", "state"}


@pytest.fixture
def deepseek(monkeypatch):
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ideas": []}', reasoning_content=None))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    factory = Mock(return_value=client)
    monkeypatch.setattr(llm_utils, "get_deepseek_client", factory)
    return factory


def test_over_cap_429_has_retry_after(client, auth_headers, test_user_id, deepseek):
    _spend(5.0, user_id=test_user_id)
    resp = client.post("/brainstorm", json=BRAINSTORM, headers=auth_headers)
    assert resp.status_code == 429
    assert resp.json()["detail"]["error_code"] == "AI_QUOTA_EXCEEDED"
    assert 1 <= int(resp.headers["Retry-After"]) <= 86400
    deepseek.assert_not_called()


def test_breaker_503_is_ai_paused_with_retry_after(client, auth_headers, deepseek, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "0.01")
    _spend(1.0, user_id=None)
    resp = client.post("/brainstorm", json=BRAINSTORM, headers=auth_headers)
    assert resp.status_code == 503
    assert resp.json()["detail"]["error_code"] == "AI_PAUSED"
    assert 1 <= int(resp.headers["Retry-After"]) <= 86400
    deepseek.assert_not_called()


def test_seconds_to_ist_midnight():
    # 18:29 UTC = 23:59 IST, one minute before the day rolls over.
    assert llm_budget.seconds_to_ist_midnight(datetime(2026, 10, 11, 18, 29, tzinfo=timezone.utc)) == 60
    assert llm_budget.seconds_to_ist_midnight(datetime(2026, 10, 11, 18, 30, tzinfo=timezone.utc)) == 86400
