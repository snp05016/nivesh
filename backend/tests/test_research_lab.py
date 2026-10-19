"""Research Lab backend (/api/v1/research-lab, docs/platform/api-contract.md).

Hermetic: every ml-engine call is a monkeypatched function on
services.research_lab.client and the LLM is never reached for real. Users are
created directly in the test DB and get tokens from create_access_token.
"""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

import database
from models.db_models import LabExperiment, LabLearnerProgress, LabSession, User
from services import llm_budget
from services.advisory_guard import NON_ADVISORY_RULES
from services.research_lab import LabError, client as lab_client, mentor

BASE = "/api/v1/research-lab"
CONFIG = {"start": "2020-02-03", "end": "2020-06-30", "universe": ["RELIANCE", "HDFCBANK"], "capital": 1000000}
SPEC = {"question": "Does momentum work?", "program": "m = lag(px_idx, 21) / lag(px_idx, 252) - 1",
        "score": "m", "start": "2015-01-01", "end": "2020-12-31", "horizon": 20, "direction": 1}


def _user() -> tuple[int, dict]:
    with database.get_session() as s:
        user = User(username=f"lab_{uuid4().hex[:12]}", password_hash="x", display_name="Lab Tester")
        s.add(user)
        s.commit()
        uid = int(user.id)
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


class FakeEngine:
    """/sim/state: rejects actions of type "bad" with 422, advances the clock by "advance" days."""

    def __init__(self):
        self.state_calls: list[list[dict]] = []
        self.history_calls: list[tuple] = []

    def sim_state(self, config, actions):
        for i, action in enumerate(actions, 1):
            if action.get("type") == "bad":
                raise LabError(422, f"action {i}: unknown action type")
        self.state_calls.append(actions)
        days = sum(int(a.get("days", 0)) for a in actions if a.get("type") == "advance")
        clock = date.fromisoformat(config["start"]) + timedelta(days=days)
        return {"state": {"clock": clock.isoformat(), "finished": False, "equity": 1000000.0},
                "performance": {}, "watchlist": [], "provenance": {}, "benchmark": None, "news": []}

    def sim_history(self, config, asof, symbol, bars):
        self.history_calls.append((asof, symbol, bars))
        return {"symbol": symbol, "asof": asof, "bars": []}


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setenv("FEATURE_RESEARCH_LAB", "true")
    monkeypatch.delenv("NIVESH_FLAG_LLM_ENABLED", raising=False)
    fake = FakeEngine()
    monkeypatch.setattr(lab_client, "sim_state", fake.sim_state)
    monkeypatch.setattr(lab_client, "sim_history", fake.sim_history)
    return fake


def _create(client, headers) -> int:
    resp = client.post(f"{BASE}/sessions", json={"title": "Covid crash", "config": CONFIG}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "Covid crash" and body["state"]["clock"] == "2020-02-03" and body["news"] == []
    return body["id"]


def _stored_actions(session_id: int) -> list:
    with database.get_session() as s:
        return list(s.get(LabSession, session_id).actions)


# -- access ------------------------------------------------------------------

def test_auth_required_even_when_flag_is_off(client, monkeypatch):
    monkeypatch.delenv("FEATURE_RESEARCH_LAB", raising=False)
    assert client.get(f"{BASE}/sessions").status_code == 401
    assert client.post(f"{BASE}/sessions", json={"config": CONFIG}).status_code == 401


def test_flag_off_is_404_for_signed_in_user(client, monkeypatch):
    monkeypatch.delenv("FEATURE_RESEARCH_LAB", raising=False)
    _uid, headers = _user()
    resp = client.get(f"{BASE}/sessions", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_other_users_session_reads_as_missing(client, engine):
    _a, owner = _user()
    _b, other = _user()
    sid = _create(client, owner)

    assert [s["id"] for s in client.get(f"{BASE}/sessions", headers=owner).json()] == [sid]
    assert client.get(f"{BASE}/sessions", headers=other).json() == []
    assert client.get(f"{BASE}/sessions/{sid}", headers=other).status_code == 404
    assert client.post(f"{BASE}/sessions/{sid}/actions", json={"action": {"type": "advance", "days": 1}},
                       headers=other).status_code == 404
    assert client.delete(f"{BASE}/sessions/{sid}", headers=other).status_code == 404
    assert client.get(f"{BASE}/sessions/{sid}", headers=owner).status_code == 200
    assert client.delete(f"{BASE}/sessions/{sid}", headers=owner).status_code == 204
    assert client.get(f"{BASE}/sessions/{sid}", headers=owner).status_code == 404


def test_invalid_config_is_rejected_with_engine_reason(client, engine, monkeypatch):
    def reject(config, actions):
        raise LabError(422, "a simulation can span at most five years")

    monkeypatch.setattr(lab_client, "sim_state", reject)
    _uid, headers = _user()
    resp = client.post(f"{BASE}/sessions", json={"config": CONFIG}, headers=headers)
    assert resp.status_code == 422
    assert resp.json() == {"detail": "a simulation can span at most five years"}


# -- action log --------------------------------------------------------------

def test_action_appended_only_when_engine_accepts(client, engine):
    _uid, headers = _user()
    sid = _create(client, headers)

    bad = client.post(f"{BASE}/sessions/{sid}/actions", json={"action": {"type": "bad"}}, headers=headers)
    assert bad.status_code == 422
    assert bad.json() == {"detail": "action 1: unknown action type"}
    assert _stored_actions(sid) == []

    ok = client.post(f"{BASE}/sessions/{sid}/actions",
                     json={"action": {"type": "advance", "days": 5}, "client_action_id": "c-1"}, headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["state"]["clock"] == "2020-02-08"
    assert _stored_actions(sid) == [{"type": "advance", "days": 5, "client_action_id": "c-1"}]
    assert engine.state_calls[-1] == [{"type": "advance", "days": 5}]  # client_action_id never reaches the engine
    with database.get_session() as s:
        row = s.get(LabSession, sid)
        assert row.clock == date(2020, 2, 8) and float(row.equity) == 1000000.0 and row.finished is False


def test_client_action_id_is_idempotent(client, engine):
    _uid, headers = _user()
    sid = _create(client, headers)
    body = {"action": {"type": "advance", "days": 1}, "client_action_id": "retry-me"}

    first = client.post(f"{BASE}/sessions/{sid}/actions", json=body, headers=headers)
    second = client.post(f"{BASE}/sessions/{sid}/actions", json=body, headers=headers)

    assert first.status_code == second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["state"]["clock"] == first.json()["state"]["clock"] == "2020-02-04"
    assert len(_stored_actions(sid)) == 1


def test_history_asof_is_the_stored_clock(client, engine):
    _uid, headers = _user()
    sid = _create(client, headers)
    client.post(f"{BASE}/sessions/{sid}/actions", json={"action": {"type": "advance", "days": 10}}, headers=headers)

    resp = client.post(f"{BASE}/sessions/{sid}/history", json={"symbol": "RELIANCE", "bars": 60}, headers=headers)

    assert resp.status_code == 200, resp.text
    assert engine.history_calls == [("2020-02-13", "RELIANCE", 60)]


# -- research ledger ---------------------------------------------------------

def test_trials_so_far_comes_from_the_ledger(client, engine, monkeypatch):
    seen = []

    def run(spec):
        seen.append(spec)
        return {"status": "ok", "fingerprint": "f" * 64, "verdict": {"label": "fragile", "text": "t"}}

    monkeypatch.setattr(lab_client, "run_hypothesis", run)
    uid, headers = _user()
    _other, other = _user()

    first = client.post(f"{BASE}/research/experiments", json={**SPEC, "trials_so_far": 99}, headers=headers)
    second = client.post(f"{BASE}/research/experiments", json=SPEC, headers=headers)

    assert first.status_code == second.status_code == 200, first.text
    assert [s["trials_so_far"] for s in seen] == [1, 2]
    assert second.json()["verdict"] == "fragile" and second.json()["report"]["status"] == "ok"
    with database.get_session() as s:
        assert s.query(LabExperiment).filter_by(user_id=uid).count() == 2
    assert len(client.get(f"{BASE}/research/experiments", headers=headers).json()) == 2
    assert client.get(f"{BASE}/research/experiments", headers=other).json() == []
    eid = first.json()["id"]
    assert client.get(f"{BASE}/research/experiments/{eid}", headers=headers).status_code == 200
    assert client.get(f"{BASE}/research/experiments/{eid}", headers=other).status_code == 404


def test_sweep_and_compare_count_one_trial_per_variant(client, engine, monkeypatch):
    seen = []

    def record(body):
        seen.append(body["base"]["trials_so_far"])
        return {"status": "ok", "candidates": []}

    monkeypatch.setattr(lab_client, "run_hypothesis",
                        lambda spec: seen.append(spec["trials_so_far"]) or {"status": "ok", "verdict": {"label": "fragile"}})
    monkeypatch.setattr(lab_client, "sweep", record)
    monkeypatch.setattr(lab_client, "compare", record)
    uid, headers = _user()
    sweep = {"base": SPEC, "template": "m = lag(px_idx, 21) / lag(px_idx, {n}) - 1", "values": [63, 126, 252]}
    compare = {"base": SPEC, "candidates": [{"program": "a = px_idx", "score": "a"}, {"program": "b = volume", "score": "b"}]}

    assert client.post(f"{BASE}/research/experiments", json=SPEC, headers=headers).status_code == 200
    resp = client.post(f"{BASE}/research/sweep", json=sweep, headers=headers)
    assert resp.status_code == 200, resp.text
    assert "experiment_id" in resp.json()
    assert client.post(f"{BASE}/research/compare", json=compare, headers=headers).status_code == 200
    assert client.post(f"{BASE}/research/experiments", json=SPEC, headers=headers).status_code == 200

    # 1 experiment, then a 3-variant sweep, then a 2-candidate compare: 1, 1+1, 1+3+1, 1+3+2+1.
    assert seen == [1, 2, 5, 7]
    with database.get_session() as s:
        verdicts = sorted(r.verdict for r in s.query(LabExperiment).filter_by(user_id=uid))
    assert verdicts == ["compare", "fragile", "fragile", "sweep"]


def test_translate_names_missing_data_without_an_llm(client, engine, monkeypatch):
    monkeypatch.setattr(lab_client, "templates", lambda: {"templates": [], "fields": {"close": {}},
                                                          "unavailable_fields_note": "not in the panel"})
    monkeypatch.setattr(mentor, "deepseek_chat", _no_llm)
    _uid, headers = _user()
    resp = client.post(f"{BASE}/research/translate",
                       json={"question": "Do stocks with rising delivery volume beat their sector?"}, headers=headers)
    body = resp.json()
    assert resp.status_code == 200, resp.text
    assert body["spec"] is None and body["mode"] == "rules"
    assert set(body["missing_data"]) == {"delivery volume", "sector labels"}


def test_translate_rules_fallback_matches_a_template(client, engine, monkeypatch):
    tpl = {"id": "momentum_12_1", "title": "12-1 month momentum", "score": "mom_12_1", "horizon": 20,
           "program": "mom_12_1 = lag(px_idx, 21) / lag(px_idx, 252) - 1", "reference": "Jegadeesh & Titman (1993)"}
    monkeypatch.setattr(lab_client, "templates", lambda: {"templates": [tpl], "fields": {}})
    _uid, headers = _user()  # no AI consent: rules only
    body = client.post(f"{BASE}/research/translate", json={"question": "Do past year winners keep winning on momentum?"},
                       headers=headers).json()
    assert body["mode"] == "rules"
    assert body["spec"]["score"] == "mom_12_1" and body["spec"]["horizon"] == 20


# -- mentor ------------------------------------------------------------------

_AUTOPSY = {
    "clock": "2020-03-02",
    "trades": [{"symbol": "RELIANCE", "verdict": {"quadrant": "bad_break", "text": "Sound plan, unlucky outcome."},
                "process": {"score": 60, "checks": [{"id": "stop", "passed": False, "text": "No planned stop."},
                                                    {"id": "thesis", "passed": True, "text": "Thesis written."}]}}],
    "behaviour": [{"id": "overtrading", "severity": "high", "evidence": {}, "text": "You traded 40 times in 20 sessions."}],
    "performance": {"total_return": -0.05},
}


def _no_llm(*_args, **_kwargs):
    raise AssertionError("the LLM must not be called")


def test_mentor_rules_mode_without_consent(client, engine, monkeypatch):
    monkeypatch.setattr(lab_client, "sim_autopsy", lambda config, actions, order_id=None: _AUTOPSY)
    monkeypatch.setattr(mentor, "deepseek_chat", _no_llm)
    _uid, headers = _user()
    sid = _create(client, headers)

    resp = client.post(f"{BASE}/sessions/{sid}/mentor", json={"question": "Why did I lose?"}, headers=headers)

    body = resp.json()
    assert resp.status_code == 200, resp.text
    assert body["mode"] == "rules"
    for text in ("Sound plan, unlucky outcome.", "No planned stop.", "You traded 40 times in 20 sessions."):
        assert text in body["answer"]
    assert "Thesis written." not in body["answer"]  # passed checks are not faults
    assert body["grounded_on"]["behaviour"][0]["id"] == "overtrading"
    assert "not investment advice" in body["disclaimer"]


def test_mentor_rules_mode_when_budget_is_spent(client, engine, monkeypatch):
    monkeypatch.setattr(lab_client, "sim_autopsy", lambda config, actions, order_id=None: _AUTOPSY)
    monkeypatch.setattr(mentor, "has_active_consent", lambda uid, kind: True)
    monkeypatch.setattr(llm_budget, "guard", lambda uid, feature: (_ for _ in ()).throw(HTTPException(429)))
    monkeypatch.setattr(mentor, "deepseek_chat", _no_llm)
    _uid, headers = _user()
    sid = _create(client, headers)

    body = client.post(f"{BASE}/sessions/{sid}/mentor", json={"question": "Why?"}, headers=headers).json()
    assert body["mode"] == "rules"


def test_mentor_llm_mode_is_grounded_and_non_advisory(client, engine, monkeypatch):
    prompts = []

    def llm(messages, **kwargs):
        prompts.append(messages)
        return "Your stop was missing at entry; the loss itself was partly hindsight."

    monkeypatch.setattr(lab_client, "sim_autopsy", lambda config, actions, order_id=None: _AUTOPSY)
    monkeypatch.setattr(mentor, "has_active_consent", lambda uid, kind: True)
    monkeypatch.setattr(llm_budget, "guard", lambda uid, feature: None)
    monkeypatch.setattr(mentor, "deepseek_chat", llm)
    _uid, headers = _user()
    sid = _create(client, headers)

    body = client.post(f"{BASE}/sessions/{sid}/mentor", json={"question": "Why?", "order_id": "o1"},
                       headers=headers).json()

    assert body["mode"] == "llm" and body["answer"].startswith("Your stop was missing")
    system, user = prompts[0]
    assert NON_ADVISORY_RULES in system["content"] and "ONLY the facts" in system["content"]
    assert "No planned stop." in user["content"] and "<facts>" in user["content"]


# -- proxies, school, erasure ------------------------------------------------

def test_events_timeline_proxy(client, engine, monkeypatch):
    calls = []
    monkeypatch.setattr(lab_client, "events_timeline",
                        lambda symbol, start, end: calls.append((symbol, start, end)) or {"symbol": symbol, "items": []})
    _uid, headers = _user()
    resp = client.post(f"{BASE}/events/timeline", json={"symbol": "RELIANCE", "start": "2020-01-01", "end": "2020-06-30"},
                       headers=headers)
    assert resp.status_code == 200 and resp.json() == {"symbol": "RELIANCE", "items": []}
    assert calls == [("RELIANCE", "2020-01-01", "2020-06-30")]
    assert client.post(f"{BASE}/events/timeline", json={"symbol": "RELIANCE", "start": "2020-01-01", "end": "2020-06-30"}
                       ).status_code == 401


def test_school_grade_saves_state_and_next_uses_behaviour_flags(client, engine, monkeypatch):
    graded, asked = [], []
    monkeypatch.setattr(lab_client, "grade", lambda lesson_id, answers, state: graded.append(state) or {
        "score": 1.0, "per_question": [], "state": {"version": 1, "mastery": {"costs": 0.97, "risk": 0.5},
                                                     "completed": [lesson_id], "skipped": []}})
    monkeypatch.setattr(lab_client, "sim_autopsy", lambda config, actions, order_id=None: _AUTOPSY)
    monkeypatch.setattr(lab_client, "next_lessons",
                        lambda state, weaknesses, k: asked.append((state, weaknesses, k)) or {"lessons": []})
    uid, headers = _user()
    _create(client, headers)

    assert client.post(f"{BASE}/school/lessons/costs-101/grade", json={"answers": [0, 2]}, headers=headers).status_code == 200
    assert graded == [{}]
    progress = client.get(f"{BASE}/school/progress", headers=headers).json()
    assert progress["mastered"] == ["costs"] and progress["completed"] == ["costs-101"]
    with database.get_session() as s:
        assert s.get(LabLearnerProgress, uid) is not None

    assert client.get(f"{BASE}/school/next", headers=headers).status_code == 200
    assert asked[0][1] == ["overtrading"] and asked[0][2] == 3


def test_lab_tables_are_erased_with_the_user():
    from services.compliance_service import ERASURE_POLICY, erase_user

    for key in ("lab_sessions.user_id", "lab_experiments.user_id", "lab_learner_progress.user_id"):
        assert ERASURE_POLICY[key] == "delete"
    uid, _headers = _user()
    with database.get_session() as s:
        s.add_all([
            LabSession(user_id=uid, title="t", config=CONFIG, actions=[]),
            LabExperiment(user_id=uid, question="q", spec={}, verdict="fragile", report={}),
            LabLearnerProgress(user_id=uid, state={"completed": []}),
        ])
        s.commit()

    erase_user(uid)

    with database.get_session() as s:
        for model in (LabSession, LabExperiment, LabLearnerProgress):
            assert s.query(model).filter_by(user_id=uid).count() == 0, model.__tablename__
