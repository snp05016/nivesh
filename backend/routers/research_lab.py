"""Research Lab API (docs/platform/api-contract.md): ``/api/v1/research-lab``.

Thin routes over ``services.research_lab``. Every route needs a signed-in user and
the ``research_lab`` flag: auth runs first (401), then the flag (404
FEATURE_DISABLED while off). Sessions and experiments are owner-only (another
user's id reads as 404). Engine rejections pass through as 422 with the engine's
reason; an unreachable engine is 503 LAB_ENGINE_UNAVAILABLE.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Response
from pydantic import BaseModel, Field, field_validator

from core.feature_flags import require_flag
from core.security import require_auth
from services.research_lab import client, mentor, research, school, sessions

router = APIRouter(
    prefix="/api/v1/research-lab",
    tags=["research-lab"],
    # Order matters: auth before the flag, so anonymous callers always get 401.
    dependencies=[Depends(require_auth), Depends(require_flag("research_lab"))],
)

_ID = r"^[A-Za-z0-9_-]{1,64}$"
_SYMBOL = r"^[A-Z0-9&-]{1,32}$"
_ORDER_ID = r"^o[0-9]{1,6}$"
_MAX_JSON_CHARS = 4000


def _bounded(value: dict) -> dict:
    if len(json.dumps(value, default=str)) > _MAX_JSON_CHARS:
        raise ValueError(f"must serialise to at most {_MAX_JSON_CHARS} characters")
    return value


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    scenario_id: Optional[str] = Field(None, pattern=_ID)
    config: dict[str, Any]

    @field_validator("config")
    @classmethod
    def _config_bounded(cls, v: dict) -> dict:
        return _bounded(v)


class ActionIn(BaseModel):
    action: dict[str, Any]
    client_action_id: Optional[str] = Field(None, pattern=_ID)

    @field_validator("action")
    @classmethod
    def _action_bounded(cls, v: dict) -> dict:
        return _bounded(v)


class HistoryIn(BaseModel):
    symbol: str = Field(pattern=_SYMBOL)
    bars: int = Field(250, ge=5, le=1500)


class MentorIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    order_id: Optional[str] = Field(None, pattern=_ORDER_ID)


class TimelineIn(BaseModel):
    symbol: str = Field(pattern=_SYMBOL)
    start: date
    end: date


class GradeIn(BaseModel):
    answers: list[int] = Field(max_length=50)


class ProgramIn(BaseModel):
    program: str = Field(min_length=1, max_length=20_000)


class TranslateIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class SpecIn(BaseModel):
    """Experiment spec. trials_so_far is not accepted: the server fills it from the ledger."""
    question: str = Field("", max_length=2000)
    program: str = Field(min_length=1, max_length=20_000)
    score: str = Field(min_length=1, max_length=64)
    start: date
    end: date
    horizon: Literal[1, 5, 10, 20, 60] = 5
    direction: Literal[1, -1] = 1
    universe_n: int = 50
    min_names: int = 15
    n_quantiles: int = 5
    filter: Optional[str] = Field(None, max_length=2000)
    holdout_months: int = 12
    use_holdout: bool = False
    permutations: int = 300


class CandidateIn(BaseModel):
    program: str = Field(min_length=1, max_length=20_000)
    score: str = Field(min_length=1, max_length=64)


class CompareIn(BaseModel):
    base: SpecIn
    candidates: list[CandidateIn] = Field(min_length=2, max_length=12)


class SweepIn(BaseModel):
    base: SpecIn
    template: str = Field(min_length=1, max_length=2000)
    values: list[int] = Field(min_length=2, max_length=12)


# ---------------------------------------------------------------------------
# Time Machine
# ---------------------------------------------------------------------------

@router.get("/scenarios")
def get_scenarios() -> dict:
    return client.scenarios()


@router.get("/universe")
def get_universe(start: date, n: int = Query(20, ge=1, le=30)) -> dict:
    return client.universe(start.isoformat(), n)


@router.post("/sessions")
def create_session(body: SessionCreate, user_id: int = Depends(require_auth)) -> dict:
    return sessions.create(user_id, body.config, body.title, body.scenario_id)


@router.get("/sessions")
def list_sessions(user_id: int = Depends(require_auth)) -> list[dict]:
    return sessions.list_sessions(user_id)


@router.get("/sessions/{session_id}")
def read_session(session_id: int, user_id: int = Depends(require_auth)) -> dict:
    return sessions.get(user_id, session_id)


@router.post("/sessions/{session_id}/actions")
def append_action(session_id: int, body: ActionIn, user_id: int = Depends(require_auth)) -> dict:
    return sessions.append_action(user_id, session_id, body.action, body.client_action_id)


@router.post("/sessions/{session_id}/history")
def session_history(session_id: int, body: HistoryIn, user_id: int = Depends(require_auth)) -> dict:
    return sessions.history(user_id, session_id, body.symbol, body.bars)


@router.get("/sessions/{session_id}/autopsy")
def session_autopsy(
    session_id: int, order_id: Optional[str] = Query(None, pattern=_ORDER_ID), user_id: int = Depends(require_auth),
) -> dict:
    return sessions.autopsy(user_id, session_id, order_id)


@router.post("/sessions/{session_id}/mentor")
def session_mentor(session_id: int, body: MentorIn, user_id: int = Depends(require_auth)) -> dict:
    return mentor.ask(user_id, session_id, body.question, body.order_id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, user_id: int = Depends(require_auth)) -> Response:
    sessions.delete(user_id, session_id)
    return Response(status_code=204)


@router.post("/events/timeline")
def events_timeline(body: TimelineIn) -> dict:
    return client.events_timeline(body.symbol, body.start.isoformat(), body.end.isoformat())


# ---------------------------------------------------------------------------
# School
# ---------------------------------------------------------------------------

@router.get("/school/curriculum")
def get_curriculum() -> dict:
    return client.curriculum()


@router.get("/school/lessons/{lesson_id}")
def get_lesson(lesson_id: str = Path(pattern=_ID)) -> dict:
    return client.lesson(lesson_id)


@router.post("/school/lessons/{lesson_id}/grade")
def grade_lesson(body: GradeIn, lesson_id: str = Path(pattern=_ID), user_id: int = Depends(require_auth)) -> dict:
    return school.grade(user_id, lesson_id, body.answers)


@router.get("/school/progress")
def get_progress(user_id: int = Depends(require_auth)) -> dict:
    return school.progress(user_id)


@router.get("/school/next")
def get_next_lessons(k: int = Query(3, ge=1, le=10), user_id: int = Depends(require_auth)) -> dict:
    return school.next_lessons(user_id, k)


# ---------------------------------------------------------------------------
# Hypothesis Lab
# ---------------------------------------------------------------------------

@router.get("/research/templates")
def get_templates() -> dict:
    return client.templates()


@router.post("/research/compile")
def compile_program(body: ProgramIn) -> dict:
    return client.compile_program(body.program)


@router.post("/research/translate")
def translate_question(body: TranslateIn, user_id: int = Depends(require_auth)) -> dict:
    return research.translate(user_id, body.question)


@router.post("/research/experiments")
def run_experiment(body: SpecIn, user_id: int = Depends(require_auth)) -> dict:
    return research.run_experiment(user_id, body.model_dump(mode="json"))


@router.get("/research/experiments")
def list_experiments(user_id: int = Depends(require_auth)) -> list[dict]:
    return research.list_experiments(user_id)


@router.get("/research/experiments/{experiment_id}")
def get_experiment(experiment_id: int, user_id: int = Depends(require_auth)) -> dict:
    return research.get_experiment(user_id, experiment_id)


@router.post("/research/compare")
def compare_candidates(body: CompareIn, user_id: int = Depends(require_auth)) -> dict:
    return research.compare(user_id, body.model_dump(mode="json"))


@router.post("/research/sweep")
def sweep_variants(body: SweepIn, user_id: int = Depends(require_auth)) -> dict:
    return research.sweep(user_id, body.model_dump(mode="json"))
