"""Trader School: curriculum validation and adaptive progression.

Mastery is tracked per concept with Bayesian Knowledge Tracing (Corbett & Anderson, 1994).
Everything is pure and deterministic. Learner state is a plain JSON-serialisable dict:

    {"version": 1, "mastery": {concept_id: p_known}, "completed": [lesson_id], "skipped": [lesson_id]}

Functions never mutate the state they are given; they return a new one.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

CURRICULUM_PATH = Path(__file__).with_name("curriculum.json")
TRACKS = ("foundation", "intermediate", "advanced", "professional")
SECTION_KINDS = frozenset({"text", "example", "formula", "interactive"})
WIDGETS = frozenset({"cost_calculator", "position_sizer", "return_distribution", "calibration_game",
                     "overfitting_demo", "order_book_toy", "drawdown_math", "compounding"})
DEFAULT_PARAMS = {"p_init": 0.2, "p_learn": 0.15, "p_slip": 0.1, "p_guess": 0.25}
MASTERY = 0.95      # concept counts as known at or above this posterior
PASS_SCORE = 0.8    # quiz score that marks a lesson completed
_EPS = 1e-6         # keep probabilities strictly inside (0, 1)

# Behaviour flags emitted by the simulator mentor -> concepts that address them.
BEHAVIOUR_TO_CONCEPTS = {
    "overtrading": ["overconfidence", "trading_costs"],
    "concentration": ["diversification", "portfolio_construction"],
    "disposition_effect": ["disposition_effect"],
    "chasing_momentum": ["market_regimes", "technical_analysis"],
    "ignored_costs": ["trading_costs", "transaction_cost_model"],
    "stop_discipline": ["stop_discipline", "drawdown"],
    "oversized_positions": ["position_sizing", "drawdown"],
    "no_thesis": ["investment_thesis"],
    "poor_calibration": ["calibration"],
    "hindsight_risk": ["hindsight_bias", "backtest_bias"],
}


class CurriculumError(ValueError):
    """The curriculum file is structurally invalid."""


# ---------------------------------------------------------------- curriculum

def load_curriculum(path: str | Path | None = None) -> dict:
    with open(path or CURRICULUM_PATH, encoding="utf-8") as f:
        cur = json.load(f)
    validate(cur)
    return cur


@lru_cache(maxsize=1)
def _default_curriculum() -> dict:
    return load_curriculum()


def _cur(curriculum: dict | None) -> dict:
    return curriculum if curriculum is not None else _default_curriculum()


def validate(curriculum: dict) -> None:
    """Raise CurriculumError on any structural problem; return None if valid."""
    concepts = curriculum.get("concepts")
    if not isinstance(concepts, dict) or not concepts:
        raise CurriculumError("missing top-level 'concepts' registry")
    lessons = curriculum.get("lessons")
    if not isinstance(lessons, list) or not lessons:
        raise CurriculumError("no lessons")

    ids: set[str] = set()
    qids: set[str] = set()
    for les in lessons:
        lid = les.get("id")
        if not lid or lid in ids:
            raise CurriculumError(f"duplicate or missing lesson id: {lid!r}")
        ids.add(lid)
        if les.get("track") not in TRACKS:
            raise CurriculumError(f"{lid}: unknown track {les.get('track')!r}")
        if not les.get("concepts"):
            raise CurriculumError(f"{lid}: no concepts")
        for c in les["concepts"]:
            if c not in concepts:
                raise CurriculumError(f"{lid}: concept {c!r} not declared in registry")
        if not les.get("body"):
            raise CurriculumError(f"{lid}: empty body")
        for sec in les["body"]:
            if sec.get("kind") not in SECTION_KINDS:
                raise CurriculumError(f"{lid}: unknown section kind {sec.get('kind')!r}")
            if sec["kind"] == "interactive" and sec.get("widget") not in WIDGETS:
                raise CurriculumError(f"{lid}: unknown widget {sec.get('widget')!r}")
        if not les.get("quiz"):
            raise CurriculumError(f"{lid}: empty quiz")
        for q in les["quiz"]:
            qid = q.get("id")
            if not qid or qid in qids:
                raise CurriculumError(f"{lid}: duplicate or missing question id {qid!r}")
            qids.add(qid)
            choices, ans = q.get("choices") or [], q.get("answer")
            if len(choices) < 2:
                raise CurriculumError(f"{qid}: needs at least two choices")
            if type(ans) is not int or not 0 <= ans < len(choices):
                raise CurriculumError(f"{qid}: answer index {ans!r} out of range")
            if q.get("concept") is not None and q["concept"] not in les["concepts"]:
                raise CurriculumError(f"{qid}: question concept not among lesson concepts")

    for les in lessons:
        for p in les.get("prereqs", []):
            if p not in ids:
                raise CurriculumError(f"{les['id']}: unknown prereq {p!r}")

    # Kahn's algorithm: anything left unsorted sits on a cycle.
    indeg = {les["id"]: len(les.get("prereqs", [])) for les in lessons}
    children: dict[str, list[str]] = {i: [] for i in ids}
    for les in lessons:
        for p in les.get("prereqs", []):
            children[p].append(les["id"])
    ready = [i for i, d in indeg.items() if d == 0]
    while ready:
        for ch in children[ready.pop()]:
            indeg[ch] -= 1
            if indeg[ch] == 0:
                ready.append(ch)
    cyclic = sorted(i for i, d in indeg.items() if d > 0)
    if cyclic:
        raise CurriculumError(f"prereq cycle among: {cyclic}")


def get_lesson(lesson_id: str, curriculum: dict | None = None) -> dict:
    for les in _cur(curriculum)["lessons"]:
        if les["id"] == lesson_id:
            return les
    raise KeyError(f"unknown lesson {lesson_id!r}")


# ---------------------------------------------------------------- BKT state

def new_state() -> dict:
    return {"version": 1, "mastery": {}, "completed": [], "skipped": []}


def _norm(state: dict | None) -> dict:
    st = new_state()
    if state:
        st.update(copy.deepcopy(state))
    return st


def mastery(state: dict | None, concept: str, params: dict | None = None) -> float:
    prm = params or DEFAULT_PARAMS
    return float((state or {}).get("mastery", {}).get(concept, prm["p_init"]))


def update(state: dict | None, concept: str, correct: bool, *, guess: float | None = None,
           params: dict | None = None) -> dict:
    """One BKT step: Bayesian posterior given the answer, then the learning transition."""
    prm = {**DEFAULT_PARAMS, **(params or {})}
    p = mastery(state, concept, prm)
    g = prm["p_guess"] if guess is None else guess
    s = prm["p_slip"]
    if correct:
        post = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
    else:
        post = p * s / (p * s + (1 - p) * (1 - g))
    p_new = post + (1 - post) * prm["p_learn"]
    st = _norm(state)
    st["mastery"][concept] = min(1 - _EPS, max(_EPS, p_new))
    return st


def _concepts_mastered(state: dict, les: dict) -> bool:
    return all(mastery(state, c) >= MASTERY for c in les["concepts"])


def lesson_done(state: dict | None, les: dict) -> bool:
    st = state or {}
    return les["id"] in st.get("completed", []) or les["id"] in st.get("skipped", []) or _concepts_mastered(st, les)


def _add(lst: list, item: str) -> list:
    return sorted(set(lst) | {item})


# ---------------------------------------------------------------- grading

def _apply_answers(les: dict, answers, state: dict) -> tuple[list[dict], int, dict]:
    qs = les["quiz"]
    if isinstance(answers, dict):
        picks = [answers.get(q["id"]) for q in qs]
    else:
        picks = list(answers)
        if len(picks) > len(qs):
            raise ValueError(f"{les['id']}: {len(picks)} answers for {len(qs)} questions")
        picks += [None] * (len(qs) - len(picks))
    per, n_ok, st = [], 0, state
    for q, pick in zip(qs, picks):
        ok = type(pick) is int and pick == q["answer"]  # unanswered counts as wrong
        n_ok += ok
        for c in ([q["concept"]] if q.get("concept") else les["concepts"]):
            st = update(st, c, ok, guess=1 / len(q["choices"]))
        per.append({"id": q["id"], "correct": ok, "answer": q["answer"], "explain": q["explain"]})
    return per, n_ok, st


def grade_quiz(lesson_id: str, answers, state: dict | None = None, curriculum: dict | None = None) -> dict:
    """Grade a quiz. `answers` is a list of choice indices in question order, or {question_id: index}."""
    les = get_lesson(lesson_id, curriculum)
    per, n_ok, st = _apply_answers(les, answers, _norm(state))
    score = n_ok / len(les["quiz"])
    if score >= PASS_SCORE:
        st["completed"] = _add(st["completed"], lesson_id)
    return {
        "lesson_id": lesson_id,
        "score": score,
        "passed": score >= PASS_SCORE,
        "per_question": per,
        "mastery_updates": {c: st["mastery"][c] for c in les["concepts"]},
        "state": st,
    }


def placement(answers_by_lesson: dict, state: dict | None = None, curriculum: dict | None = None) -> dict:
    """Test-out: grade the given quizzes, then mark every lesson whose concepts all reach MASTERY as skipped."""
    cur = _cur(curriculum)
    known = {les["id"] for les in cur["lessons"]}
    unknown = sorted(set(answers_by_lesson) - known)
    if unknown:
        raise KeyError(f"unknown lessons: {unknown}")
    st = _norm(state)
    for les in cur["lessons"]:  # curriculum order keeps the result independent of dict order
        if les["id"] in answers_by_lesson:
            st = _apply_answers(les, answers_by_lesson[les["id"]], st)[2]
    skippable = [les["id"] for les in cur["lessons"] if _concepts_mastered(st, les)]
    st["skipped"] = sorted(set(st["skipped"]) | set(skippable))
    return {"state": st, "skippable": skippable}


# ---------------------------------------------------------------- recommendation

def weak_concepts(weaknesses: list[str], curriculum: dict | None = None) -> list[str]:
    """Expand behaviour flags and/or concept ids into an ordered, de-duplicated concept list.
    Unknown flags are ignored so a newer simulator cannot break older curricula."""
    registry = _cur(curriculum)["concepts"]
    out: list[str] = []
    for w in weaknesses:
        for c in BEHAVIOUR_TO_CONCEPTS.get(w, [w]):
            if c in registry and c not in out:
                out.append(c)
    return out


def next_lessons(state: dict | None, weaknesses: list[str] = (), k: int = 3, curriculum: dict | None = None) -> list[dict]:
    """Up to k unlocked lessons. Lessons teaching a weak concept come first (new before review),
    then unlocked prerequisites on the path to a weak concept, then the normal sequence."""
    cur = _cur(curriculum)
    st = _norm(state)
    lessons = cur["lessons"]
    by_id = {les["id"]: les for les in lessons}
    weak = weak_concepts(list(weaknesses), cur)
    rank = {c: i for i, c in enumerate(weak)}

    direct = {les["id"] for les in lessons if rank.keys() & set(les["concepts"])}
    ancestors: set[str] = set()
    stack = [p for d in direct for p in by_id[d].get("prereqs", [])]
    while stack:
        lid = stack.pop()
        if lid not in ancestors:
            ancestors.add(lid)
            stack.extend(by_id[lid].get("prereqs", []))

    scored = []
    for idx, les in enumerate(lessons):
        if not all(lesson_done(st, by_id[p]) for p in les.get("prereqs", [])):
            continue
        done = lesson_done(st, les)
        if done and les["id"] not in direct:
            continue
        tier = 2 if les["id"] in direct else 1 if les["id"] in ancestors else 0
        wrank = min((rank[c] for c in les["concepts"] if c in rank), default=len(rank))
        avg = sum(mastery(st, c) for c in les["concepts"]) / len(les["concepts"])
        reason = ("review: weakness" if done else "weakness") if tier == 2 else \
                 "prerequisite for weakness" if tier == 1 else "next in sequence"
        scored.append(((-tier, done, wrank, avg, idx), {
            "lesson_id": les["id"], "title": les["title"], "track": les["track"],
            "concepts": list(les["concepts"]), "reason": reason}))
    scored.sort(key=lambda t: t[0])
    return [rec for _, rec in scored[:k]]
