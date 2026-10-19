import copy
import json
import re

import pytest
from lab.school import engine as S

CUR = S.load_curriculum()
LESSONS = CUR["lessons"]
FORBIDDEN = re.compile(r"\b(million|billion|trillion|guaranteed|sure-shot|multibagger|recommendation)\b", re.IGNORECASE)


def right(les):
    return [q["answer"] for q in les["quiz"]]


def wrong(les):
    return [(q["answer"] + 1) % len(q["choices"]) for q in les["quiz"]]


# ---------------------------------------------------------------- curriculum content

def test_curriculum_validates_and_has_four_tracks():
    S.validate(CUR)
    counts = {t: sum(l["track"] == t for l in LESSONS) for t in S.TRACKS}
    assert all(n >= 9 for n in counts.values()), counts
    assert len(LESSONS) >= 36


def test_every_lesson_has_body_quiz_and_kebab_id():
    for les in LESSONS:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", les["id"])
        assert 3 <= len(les["quiz"]) <= 5, les["id"]
        words = sum(len(s.get("md", "").split()) for s in les["body"])
        assert words >= 200, (les["id"], words)
        assert les["summary"] and les["minutes"] > 0
        for q in les["quiz"]:
            assert q["explain"].strip()
        if "practice" in les:
            assert les["practice"]["kind"] == "time_machine" and les["practice"]["scenario_hint"]


def test_no_forbidden_words_anywhere():
    text = json.dumps(CUR, ensure_ascii=False)
    assert not FORBIDDEN.findall(text)


def _toy():
    return {
        "concepts": {"a": {}, "b": {}},
        "lessons": [
            {"id": "x", "track": "foundation", "prereqs": [], "concepts": ["a"], "body": [{"kind": "text", "md": "t"}],
             "quiz": [{"id": "x1", "q": "?", "choices": ["p", "q"], "answer": 0, "explain": "e"}]},
            {"id": "y", "track": "foundation", "prereqs": ["x"], "concepts": ["b"], "body": [{"kind": "text", "md": "t"}],
             "quiz": [{"id": "y1", "q": "?", "choices": ["p", "q"], "answer": 1, "explain": "e"}]},
        ],
    }


@pytest.mark.parametrize("mutate", [
    lambda c: c["lessons"].append(copy.deepcopy(c["lessons"][0])),           # duplicate id
    lambda c: c["lessons"][1]["prereqs"].append("nope"),                       # unknown prereq
    lambda c: c["lessons"][0]["prereqs"].append("y"),                          # cycle x <-> y
    lambda c: c["lessons"][0]["quiz"][0].update(answer=2),                     # answer out of range
    lambda c: c["lessons"][0].update(quiz=[]),                                 # empty quiz
    lambda c: c["lessons"][0]["concepts"].append("undeclared"),                # concept not in registry
    lambda c: c["lessons"][0]["body"].append({"kind": "interactive", "widget": "slot_machine"}),
])
def test_validate_rejects(mutate):
    cur = _toy()
    S.validate(cur)
    mutate(cur)
    with pytest.raises(S.CurriculumError):
        S.validate(cur)


def test_behaviour_flags_map_to_existing_concepts():
    flags = {"overtrading", "concentration", "disposition_effect", "chasing_momentum", "ignored_costs",
             "stop_discipline", "oversized_positions", "no_thesis", "poor_calibration", "hindsight_risk"}
    assert set(S.BEHAVIOUR_TO_CONCEPTS) == flags
    taught = {c for les in LESSONS for c in les["concepts"]}
    for flag, concepts in S.BEHAVIOUR_TO_CONCEPTS.items():
        assert concepts and all(c in CUR["concepts"] and c in taught for c in concepts), flag


# ---------------------------------------------------------------- BKT

@pytest.mark.parametrize("p0", [0.05, 0.2, 0.5, 0.9])
def test_bkt_direction_and_bounds(p0):
    st = {"mastery": {"c": p0}}
    up = S.mastery(S.update(st, "c", True), "c")
    down = S.mastery(S.update(st, "c", False), "c")
    assert 0 < down < up < 1
    assert up > p0
    if p0 >= S.DEFAULT_PARAMS["p_init"]:  # below p_learn the learning step can outweigh one miss (standard BKT)
        assert down < p0


def test_bkt_saturates_inside_unit_interval_and_does_not_mutate():
    st = S.new_state()
    snap = copy.deepcopy(st)
    for _ in range(200):
        st = S.update(st, "c", True)
    assert 0.95 < S.mastery(st, "c") < 1
    for _ in range(200):
        st = S.update(st, "c", False)
    assert 0 < S.mastery(st, "c") < 0.5
    S.update(snap, "c", True)
    assert snap == S.new_state()


# ---------------------------------------------------------------- grading / placement

def test_grade_quiz_scores_and_explains():
    les = LESSONS[0]
    n = len(les["quiz"])
    res = S.grade_quiz(les["id"], right(les))
    assert res["score"] == 1 and res["passed"]
    assert all(pq["correct"] and pq["explain"] for pq in res["per_question"])
    assert les["id"] in res["state"]["completed"]
    assert all(p >= S.MASTERY for p in res["mastery_updates"].values())

    answers = right(les)
    answers[0] = wrong(les)[0]
    res = S.grade_quiz(les["id"], {q["id"]: a for q, a in zip(les["quiz"], answers)})
    assert res["score"] == pytest.approx((n - 1) / n)
    assert [pq["correct"] for pq in res["per_question"]] == [False] + [True] * (n - 1)

    res = S.grade_quiz(les["id"], [])  # unanswered = wrong
    assert res["score"] == 0 and not res["passed"] and les["id"] not in res["state"]["completed"]
    assert all(p < S.DEFAULT_PARAMS["p_init"] for p in res["mastery_updates"].values())


def test_placement_skips_only_mastered_lessons():
    found = [l for l in LESSONS if l["track"] == "foundation"]
    ans = {l["id"]: right(l) for l in found[:5]}
    ans[found[5]["id"]] = wrong(found[5])
    out = S.placement(ans)
    assert out["skippable"] == [l["id"] for l in found[:5]]
    assert out["state"]["skipped"] == sorted(out["skippable"])
    assert found[5]["id"] not in out["skippable"]
    json.dumps(out)  # state must be JSON-serialisable


# ---------------------------------------------------------------- recommendation

def _done(ids):
    return {"version": 1, "mastery": {}, "completed": sorted(ids), "skipped": []}


def _unlocked(state, lid):
    les = S.get_lesson(lid)
    return all(S.lesson_done(state, S.get_lesson(p)) for p in les["prereqs"])


def test_next_lessons_fresh_learner_starts_at_the_root():
    recs = S.next_lessons(S.new_state(), [])
    assert [r["lesson_id"] for r in recs] == ["f-what-is-a-share"]


def test_next_lessons_respects_prereqs_with_weaknesses():
    st = _done(["f-what-is-a-share"])
    recs = S.next_lessons(st, ["overtrading", "poor_calibration"], k=5)
    assert recs and all(_unlocked(st, r["lesson_id"]) for r in recs)
    assert "i-behavioural-biases" not in {r["lesson_id"] for r in recs}  # teaches overconfidence but is locked
    # the unlocked step towards trading costs is prioritised over plain sequence
    assert recs[0]["lesson_id"] == "f-exchanges-brokers-depositories"
    assert recs[0]["reason"] == "prerequisite for weakness"


def test_next_lessons_prioritises_weak_concepts():
    st = _done([l["id"] for l in LESSONS if l["track"] == "foundation"])
    plain = S.next_lessons(st, [], k=3)
    flagged = S.next_lessons(st, ["concentration", "poor_calibration"], k=3)
    assert flagged[0]["lesson_id"] == "i-portfolio-construction" and flagged[0]["reason"] == "weakness"
    assert flagged[1]["lesson_id"] == "f-diversification" and flagged[1]["reason"] == "review: weakness"
    assert flagged[2]["lesson_id"] == "i-technical-analysis-limits"  # first step towards calibration
    assert [r["lesson_id"] for r in plain] != [r["lesson_id"] for r in flagged]
    assert all(_unlocked(st, r["lesson_id"]) for r in flagged)


def test_concept_ids_also_accepted_as_weaknesses_and_unknown_ignored():
    st = _done([l["id"] for l in LESSONS if l["track"] == "foundation"])
    a = S.next_lessons(st, ["drawdown", "made_up_flag"], k=1)
    assert a[0]["lesson_id"] == "i-drawdown-math"


def test_deterministic():
    st = _done(["f-what-is-a-share", "f-exchanges-brokers-depositories"])
    a = S.grade_quiz("f-order-types", [0, 1, 2, 3], st)
    b = S.grade_quiz("f-order-types", [0, 1, 2, 3], st)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert S.next_lessons(st, ["overtrading"]) == S.next_lessons(copy.deepcopy(st), ["overtrading"])
    ans = {l["id"]: right(l) for l in LESSONS[:8]}
    rev = dict(reversed(list(ans.items())))
    assert S.placement(ans) == S.placement(rev)
