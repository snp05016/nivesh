"""LLM-02: paid AI routes need a login, every LLM call lands in the llm_usage ledger, and the
per-user (429) and global (503) daily budgets refuse a call before the LLM is reached."""
import contextvars
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy import func

import core.dashboard_state as ds
import services.llm_utils as llm_utils
from database import get_session
from models.db_models import LlmUsage
from services import llm_budget

BRAINSTORM = {"topic": "EV batteries", "risk_tolerance": "Moderate"}
_TIERS = ("FREE", "PRO", "SUPER_PRO")


@pytest.fixture(autouse=True)
def _ledger(monkeypatch, tmp_path):
    """Fresh 60 s memo and a temp token log per test; delete the ledger rows a test adds so
    they cannot trip the budget checks of later tests sharing the session user and DB."""
    monkeypatch.setattr(llm_budget, "_global_cache", None)
    monkeypatch.setattr(ds, "TOKEN_LOG_PATH", str(tmp_path / "token_log.jsonl"))
    with get_session() as session:
        start_id = session.query(func.max(LlmUsage.id)).scalar() or 0
    yield
    with get_session() as session:
        session.query(LlmUsage).filter(LlmUsage.id > start_id).delete()
        session.commit()


@pytest.fixture
def deepseek(monkeypatch):
    """Every DeepSeek call builds its client through llm_utils.get_deepseek_client."""
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ideas": []}', reasoning_content=None))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )
    factory = Mock(return_value=client)
    monkeypatch.setattr(llm_utils, "get_deepseek_client", factory)
    return factory


def _spend(cost_usd, user_id=None):
    with get_session() as session:
        session.add(LlmUsage(user_id=user_id, feature="test", model="claude-sonnet-4-6", cost_usd=cost_usd))
        session.commit()


def _latest_row():
    with get_session() as session:
        row = session.query(LlmUsage).order_by(LlmUsage.id.desc()).first()
        assert row is not None
        return SimpleNamespace(user_id=row.user_id, feature=row.feature, model=row.model,
                               input_tokens=row.input_tokens, output_tokens=row.output_tokens)


@pytest.mark.parametrize("path, body", [
    ("/api/v1/copilot/chat", {"user_message": "hi"}),
    ("/brainstorm", BRAINSTORM),
    ("/api/v1/youtube/summary", {"url": "https://youtu.be/dQw4w9WgXcQ", "force_refresh": True}),
])
def test_paid_routes_reject_missing_token(client, deepseek, path, body):
    resp = client.post(path, json=body)
    assert resp.status_code == 401
    deepseek.assert_not_called()


def test_user_over_daily_cap_gets_429_without_llm_call(client, auth_headers, test_user_id, deepseek, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "1000000")
    for tier in _TIERS:
        monkeypatch.setenv(f"LLM_USER_DAILY_BUDGET_USD_{tier}", "1")
    _spend(5.0, user_id=test_user_id)

    resp = client.post("/brainstorm", json=BRAINSTORM, headers=auth_headers)

    assert resp.status_code == 429
    assert resp.json()["detail"]["error_code"] == "AI_QUOTA_EXCEEDED"
    deepseek.assert_not_called()


def test_global_breaker_returns_503_without_llm_call(client, auth_headers, deepseek, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "0.01")
    _spend(1.0)

    resp = client.post("/brainstorm", json=BRAINSTORM, headers=auth_headers)

    assert resp.status_code == 503
    deepseek.assert_not_called()


def test_global_breaker_stops_new_anonymous_analysis_jobs(client, spawned_jobs, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "0.01")
    _spend(1.0)

    resp = client.post("/analyze", json={"ticker": "LLMBUDGET", "exchange": "NSE"})

    assert resp.status_code == 503
    assert spawned_jobs == []


def test_paid_route_attributes_spend_to_the_caller(client, auth_headers, test_user_id, deepseek, monkeypatch):
    # require_llm_budget binds in the request context; the sync endpoint's thread must inherit it.
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "1000000")
    for tier in _TIERS:
        monkeypatch.setenv(f"LLM_USER_DAILY_BUDGET_USD_{tier}", "1000000")

    resp = client.post("/brainstorm", json=BRAINSTORM, headers=auth_headers)

    assert resp.status_code == 200
    deepseek.assert_called_once()
    row = _latest_row()
    assert (row.user_id, row.feature, row.input_tokens, row.output_tokens) == (test_user_id, "brainstorm", 10, 5)


def test_cost_usd_prices_tokens_and_fails_safe():
    sonnet = "claude-sonnet-4-6"
    assert llm_budget.cost_usd(sonnet, SimpleNamespace(input_tokens=1_000_000)) == pytest.approx(3.0)
    assert llm_budget.cost_usd(sonnet, SimpleNamespace(output_tokens=1_000_000)) == pytest.approx(15.0)
    assert llm_budget.cost_usd(sonnet, SimpleNamespace(cache_read_input_tokens=1_000_000)) == pytest.approx(0.30)
    assert llm_budget.cost_usd(sonnet, SimpleNamespace(cache_creation_input_tokens=1_000_000)) == pytest.approx(3.75)
    # An unpriced model is charged as Sonnet, never as free.
    assert llm_budget.cost_usd("mystery-model", SimpleNamespace(prompt_tokens=1_000_000)) == pytest.approx(3.0)
    # Non-numeric usage fields (e.g. a MagicMock) count as zero tokens.
    assert llm_budget.cost_usd("deepseek-chat", MagicMock()) == 0.0


def test_deepseek_chat_meters_unlabelled_calls(deepseek, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "1000000")

    def call():
        llm_budget.bind(None, None)  # a fresh context: nothing bound by earlier tests
        assert llm_utils.deepseek_chat([{"role": "user", "content": "hi"}]) == '{"ideas": []}'

    contextvars.copy_context().run(call)

    row = _latest_row()
    assert (row.feature, row.model, row.input_tokens, row.output_tokens, row.user_id) == \
        ("deepseek_unlabelled", "deepseek-chat", 10, 5, None)


def test_deepseek_chat_refuses_over_global_budget(deepseek, monkeypatch):
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "0.01")
    _spend(1.0)

    with pytest.raises(llm_budget.LlmBudgetExceeded):
        llm_utils.deepseek_chat([{"role": "user", "content": "hi"}])
    deepseek.assert_not_called()


def test_record_usage_attributes_the_bound_user():
    def call():
        llm_budget.bind(42, "x")
        llm_budget.record_usage("unit_test", "deepseek-chat", SimpleNamespace(prompt_tokens=1, completion_tokens=1))

    contextvars.copy_context().run(call)

    row = _latest_row()
    assert (row.user_id, row.feature) == (42, "unit_test")


def test_analysis_job_spend_is_not_charged_to_the_client_supplied_user(deepseek, monkeypatch):
    """POST /analyze still trusts req.user_id (auth is Phase B), so a job's spend must not land
    on that id, or an anonymous caller could exhaust any user's daily budget."""
    import database
    import services.job_worker as jw
    monkeypatch.setenv("LLM_GLOBAL_DAILY_BUDGET_USD", "1000000")
    monkeypatch.setattr(jw, "_start_wallclock_watchdog", lambda *a, **k: None)
    monkeypatch.setattr(jw, "_start_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr("services.orchestrator.analyze",
                        lambda *a, **k: {"text": llm_utils.deepseek_chat([{"role": "user", "content": "hi"}])})
    # Stub user seeded by conftest; 'deep' keeps clear of test_worker's active 'standard' slot.
    job = database.create_job(11_111_111, "INFY", "NSE", "deep")

    contextvars.copy_context().run(jw.run_job, job["job_id"], "INFY", "NSE", 11_111_111, False, "deep")

    finished = database.get_job(job["job_id"])
    assert finished is not None and finished["status"] == "SUCCEEDED"
    row = _latest_row()
    assert (row.user_id, row.feature) == (None, "analysis_deep")


def test_deepseek_prices_follow_the_env_override(monkeypatch):
    monkeypatch.delenv("LLM_PRICE_DEEPSEEK_IN", raising=False)
    monkeypatch.delenv("LLM_PRICE_DEEPSEEK_OUT", raising=False)
    assert ds.estimate_cost_usd("deepseek-chat", 1_000_000, 1_000_000) == pytest.approx(0.14 + 0.28)
    monkeypatch.setenv("LLM_PRICE_DEEPSEEK_IN", "1")
    monkeypatch.setenv("LLM_PRICE_DEEPSEEK_OUT", "2")
    usage = SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert llm_budget.cost_usd("deepseek-chat", usage) == pytest.approx(3.0)
    assert llm_budget.cost_usd("deepseek-reasoner", usage) == pytest.approx(3.0)
    assert ds.estimate_cost_usd("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.0)
