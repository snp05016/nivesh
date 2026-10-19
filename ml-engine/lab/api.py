"""ml-engine internal Lab API, ``/lab/v1``. Stateless: callers send (config, actions).

Same auth as ``/research/v1`` (``X-ML-Engine-Key``). The backend owns users, stores the
action log and decides who may see what; this service only computes.
"""
from __future__ import annotations

import json
import os
import string
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from research.api import require_key

from . import autopsy as ap
from . import events as evs
from . import hypothesis as hy
from . import school as sch
from .data import MarketData, PITView
from .featurelang import FDLError, compile_program, panel_schema
from .loaders import DEV_WARNINGS, liquid_universe, load_market
from .metrics import performance
from .sim import ActionError, Sim, SimConfig, replay

router = APIRouter(prefix="/lab/v1", tags=["lab"], dependencies=[Depends(require_key)])
SCENARIOS = Path(__file__).with_name("scenarios.json")
MAX_ACTIONS = 5000


class SimConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: date
    end: date
    universe: list[str] = Field(min_length=1, max_length=30)
    capital: float = Field(1_000_000.0, ge=10_000, le=1e9)
    max_participation: float = Field(0.10, gt=0, le=0.25)
    impact_coef: float = Field(0.7, ge=0, le=3)
    brokerage_flat: float = Field(20.0, ge=0, le=1000)
    brokerage_pct: float = Field(0.0003, ge=0, le=0.01)
    hide_identity: bool = False

    def to_cfg(self) -> SimConfig:
        if self.end <= self.start:
            raise HTTPException(422, "end must be after start")
        if (self.end - self.start).days > 366 * 5:
            raise HTTPException(422, "a simulation can span at most five years")
        newest = date.today() - timedelta(days=min_data_age_days())
        if self.end > newest:
            raise HTTPException(422, f"simulations must end on or before {newest.isoformat()}: price data younger than {min_data_age_days()} days is not used for simulation")
        return SimConfig(**self.model_dump())


class SessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: SimConfigIn
    actions: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_ACTIONS)


class AutopsyIn(SessionIn):
    order_id: str | None = None


class HistoryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: SimConfigIn
    asof: date
    symbol: str
    bars: int = Field(250, ge=5, le=1500)


def min_data_age_days() -> int:
    """Embargo on recent prices in simulations (SEBI price-data-for-education lag; see docs/platform/research/verified-facts.md)."""
    try:
        return max(0, int(os.environ.get("LAB_MIN_DATA_AGE_DAYS", "30")))
    except ValueError:
        return 30


def _source() -> Literal["auto", "store", "local_csv"]:
    v = os.environ.get("RESEARCH_PANEL_SOURCE", "auto").strip() or "auto"
    return v if v in ("auto", "store", "local_csv") else "auto"  # type: ignore[return-value]


@lru_cache(maxsize=16)
def _market(start: date, end: date, symbols: tuple[str, ...], source: str) -> MarketData:
    return load_market(start, end, list(symbols) if symbols else None, source=source)


def market_for(cfg: SimConfigIn) -> MarketData:
    try:
        return _market(cfg.start, cfg.end, tuple(sorted(cfg.universe)), _source())
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(503, f"market data unavailable: {e}") from None


# ---------------------------------------------------------------- blind mode
def _aliases(cfg: SimConfigIn) -> dict[str, str]:
    letters = string.ascii_uppercase
    return {s: f"STOCK-{letters[i]}" for i, s in enumerate(sorted(cfg.universe))} if cfg.hide_identity else {}


def _unalias_actions(cfg: SimConfigIn, actions: list[dict]) -> list[dict]:
    back = {v: k for k, v in _aliases(cfg).items()}
    return [{**a, "symbol": back.get(a.get("symbol", ""), a.get("symbol"))} if "symbol" in a else a for a in actions]


def _alias_json(cfg: SimConfigIn, obj: Any) -> Any:
    m = _aliases(cfg)
    if not m:
        return obj
    text = json.dumps(obj, default=str)
    for real, alias in sorted(m.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(f'"{real}"', f'"{alias}"')
    return json.loads(text)


# ---------------------------------------------------------------- helpers
def _replay(body: SessionIn) -> tuple[SimConfig, MarketData, Sim, list[dict]]:
    cfg = body.config.to_cfg()
    md = market_for(body.config)
    acts = _unalias_actions(body.config, body.actions)
    try:
        return cfg, md, replay(cfg, md, acts), acts
    except ActionError as e:
        raise HTTPException(422, str(e)) from None


def _watchlist(sim: Sim) -> list[dict]:
    v = sim.view()
    rows = []
    for s in sim.cfg.universe:
        h = v.history(s)[-21:]
        if not h:
            rows.append({"symbol": s, "listed": False})
            continue
        last = h[-1]
        rows.append({
            "symbol": s, "listed": True, "date": last.d.isoformat(), "close": last.close, "volume": last.volume,
            "chg_1d": round(last.close / h[-2].close - 1, 4) if len(h) > 1 else None,
            "chg_20d": round(last.close / h[0].close - 1, 4) if len(h) > 20 else None,
            "stale": last.d != sim.clock,
        })
    return rows


def _session_payload(body: SessionIn, md: MarketData, sim: Sim) -> dict:
    out = {
        "state": sim.state(), "performance": performance(sim), "watchlist": _watchlist(sim),
        "provenance": md.provenance, "benchmark": md.benchmark,
        "news": [{"date": n.published.isoformat(), "symbol": n.symbol, "title": n.title, "source": n.source, "url": n.url}
                 for n in reversed(sim.view().news(limit=20))],
    }
    return _alias_json(body.config, out)


# ---------------------------------------------------------------- routes
@router.post("/sim/state")
def sim_state(body: SessionIn) -> dict:
    """Replay the action log and return the session as of its clock. 422 names the first bad action."""
    _, md, sim, _ = _replay(body)
    return _session_payload(body, md, sim)


@router.post("/sim/history")
def sim_history(body: HistoryIn) -> dict:
    """Daily bars for one symbol up to `asof` (never later)."""
    cfg = body.config
    if not (cfg.start <= body.asof <= cfg.end):
        raise HTTPException(422, "asof must lie inside the simulation window")
    sym = {v: k for k, v in _aliases(cfg).items()}.get(body.symbol, body.symbol)
    if sym not in cfg.universe:
        raise HTTPException(422, "symbol is not in this simulation's universe")
    bars = PITView(market_for(cfg), body.asof).history(sym)[-body.bars:]
    rows = [{"d": b.d.isoformat(), "o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume} for b in bars]
    return _alias_json(cfg, {"symbol": sym, "asof": body.asof.isoformat(), "bars": rows})


@router.post("/sim/autopsy")
def sim_autopsy(body: AutopsyIn) -> dict:
    """Trade autopsies (one order or all closed trades), counterfactuals and behaviour flags."""
    cfg, md, sim, acts = _replay(body)
    trades = [t for t in sim.trades if body.order_id in (None, t.entry_order_id)]
    if body.order_id and not trades:
        raise HTTPException(404, "no closed trade for that order yet")
    autopsies = [ap.trade_autopsy(sim, t) for t in trades]
    cfs = ap.counterfactuals(cfg, md, acts, body.order_id) if body.order_id else []
    out = {
        "clock": sim.clock.isoformat(), "trades": autopsies, "counterfactuals": cfs,
        "counterfactual_note": "Hindsight comparison: each alternative is evaluated knowing what happened next. Only size and the stop plan were choosable in advance.",
        "behaviour": ap.behaviour(sim), "performance": performance(sim), "provenance": md.provenance,
    }
    return _alias_json(body.config, out)


@router.get("/scenarios")
def scenarios() -> dict:
    if not SCENARIOS.exists():
        return {"version": None, "scenarios": []}
    doc = json.loads(SCENARIOS.read_text())
    try:
        _, prov = _panel(_source())
        first, last = prov["first"], prov["last"]
    except HTTPException:
        first = last = None
    newest = (date.today() - timedelta(days=min_data_age_days())).isoformat()
    for sc in doc.get("scenarios", []):
        covered = bool(first and last and first <= sc["start"] and sc["end"] <= last)
        sc["data_available"] = covered and sc["end"] <= newest
    doc["data_window"] = [first, last]
    return doc


@router.get("/universe")
def universe(start: date, n: int = Query(20, ge=1, le=30)) -> dict:
    """The n most liquid stocks on `start`, chosen with data available on that date."""
    md = _market(start, start, (), _source())
    return {"asof": start.isoformat(), "symbols": liquid_universe(md, start, n), "provenance": md.provenance}


# ---------------------------------------------------------------- research lab
class SpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field("", max_length=2000)
    program: str = Field(max_length=20_000)
    score: str = Field(max_length=64)
    start: date
    end: date
    horizon: int = 5
    direction: Literal[1, -1] = 1
    universe_n: int = Field(50, ge=5, le=500)
    min_names: int = Field(15, ge=5, le=500)
    n_quantiles: int = Field(5, ge=2, le=10)
    filter: str | None = None
    holdout_months: int = Field(12, ge=0, le=36)
    use_holdout: bool = False
    trials_so_far: int = Field(1, ge=1, le=100_000)
    permutations: int = Field(300, ge=50, le=2000)

    def to_spec(self) -> hy.Spec:
        return hy.Spec(**self.model_dump())


class CandidateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: str = Field(max_length=20_000)
    score: str = Field(max_length=64)


class CompareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base: SpecIn
    candidates: list[CandidateIn] = Field(min_length=2, max_length=12)


class ProgramIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: str = Field(max_length=20_000)


@lru_cache(maxsize=2)
def _panel(source: str) -> tuple[Any, dict]:
    import pandas as pd
    from research.marketdata import store

    p = pd.DataFrame()
    used = source
    if source in ("auto", "store"):
        p, used = store.load_panel(source="store"), "store"
    if p.empty and source in ("auto", "local_csv"):
        p, used = store.load_panel(source="local_csv"), "local_csv"
    if p.empty:
        raise HTTPException(503, "no market data panel available")
    return p, {"source": used, "warnings": list(DEV_WARNINGS) if used == "local_csv" else [], "rows": len(p),
               "first": str(p["date"].min().date()), "last": str(p["date"].max().date())}


@router.get("/hypothesis/templates")
def hypothesis_templates() -> dict:
    return {"templates": hy.TEMPLATES, "fields": panel_schema(),
            "unavailable_fields_note": "Delivery quantities, sector labels, fundamentals and earnings revisions are not in the price panel yet; hypotheses that need them cannot be tested until those datasets are ingested."}


@router.post("/hypothesis/run")
def hypothesis_run(body: SpecIn) -> dict:
    panel, prov = _panel(_source())
    try:
        return hy.run_experiment(body.to_spec(), panel, prov)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/hypothesis/compare")
def hypothesis_compare(body: CompareIn) -> dict:
    panel, prov = _panel(_source())
    base = body.base.model_dump()
    specs = [hy.Spec(**{**base, "program": c.program, "score": c.score}) for c in body.candidates]
    try:
        return hy.compare(specs, panel, prov)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post("/features/compile")
def features_compile(body: ProgramIn) -> dict:
    try:
        prog = compile_program(body.program, panel_schema())
    except FDLError as e:
        return {"ok": False, "error": str(e), "line": e.line, "col": e.col}
    return {"ok": True, "fingerprint": prog.fingerprint, "nodes": len(prog.nodes),
            "outputs": [{"name": n, "lineage": sorted(prog.lineage(n)), "warmup_bars": prog.warmup(n), "availability": prog.availability(n)} for n in prog.outputs]}


class TimelineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(max_length=32)
    start: date
    end: date


@router.post("/events/timeline")
def events_timeline(body: TimelineIn) -> dict:
    """Price/volume anomalies, corporate actions and sourced events for one stock, labelled by evidence type."""
    if body.end <= body.start or (body.end - body.start).days > 366 * 3:
        raise HTTPException(422, "window must be positive and at most three years")
    md = _market(body.start, body.end, (body.symbol,), _source())
    if body.symbol not in md.bars:
        raise HTTPException(404, "no data for that symbol in this window")
    return {**evs.timeline(md, body.symbol, body.start, body.end), "provenance": md.provenance}


# ---------------------------------------------------------------- trader school
class GradeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lesson_id: str = Field(max_length=80)
    answers: list[int] = Field(max_length=20)
    state: dict[str, Any] | None = None


class NextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: dict[str, Any] | None = None
    weaknesses: list[str] = Field(default_factory=list, max_length=50)
    k: int = Field(3, ge=1, le=10)


class PlacementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers_by_lesson: dict[str, list[int]]
    state: dict[str, Any] | None = None


def _summary(les: dict) -> dict:
    return {k: les[k] for k in ("id", "track", "title", "minutes", "prereqs", "concepts", "summary")}


@router.get("/school/curriculum")
def school_curriculum() -> dict:
    cur = sch.load_curriculum()
    return {"version": cur.get("version"), "tracks": cur["tracks"], "concepts": cur["concepts"], "lessons": [_summary(l) for l in cur["lessons"]]}


@router.get("/school/lessons/{lesson_id}")
def school_lesson(lesson_id: str) -> dict:
    try:
        les = sch.get_lesson(lesson_id)
    except (KeyError, sch.CurriculumError):
        raise HTTPException(404, "unknown lesson") from None
    quiz = [{"id": q["id"], "q": q["q"], "choices": q["choices"]} for q in les["quiz"]]  # answers stay server-side
    return {**{k: v for k, v in les.items() if k != "quiz"}, "quiz": quiz}


@router.post("/school/grade")
def school_grade(body: GradeIn) -> dict:
    try:
        return sch.grade_quiz(body.lesson_id, body.answers, body.state)
    except KeyError:
        raise HTTPException(404, "unknown lesson") from None
    except (ValueError, sch.CurriculumError) as e:
        raise HTTPException(422, str(e)) from None


@router.post("/school/next")
def school_next(body: NextIn) -> dict:
    return {"lessons": [{"id": l["lesson_id"], **l} for l in sch.next_lessons(body.state, body.weaknesses, body.k)]}


@router.post("/school/placement")
def school_placement(body: PlacementIn) -> dict:
    try:
        return sch.placement(body.answers_by_lesson, body.state)
    except (KeyError, ValueError, sch.CurriculumError) as e:
        raise HTTPException(422, str(e)) from None


class SweepIn(BaseModel):
    """Generate variants of one idea by substituting `{n}` and test them all with search-aware corrections."""
    model_config = ConfigDict(extra="forbid")
    base: SpecIn
    template: str = Field(max_length=2000, description="FDL program containing {n}; must define `score`")
    values: list[int] = Field(min_length=2, max_length=12)


@router.post("/hypothesis/sweep")
def hypothesis_sweep(body: SweepIn) -> dict:
    if "{n}" not in body.template:
        raise HTTPException(422, "template must contain {n}")
    if any(not 1 <= v <= 756 for v in body.values) or len(set(body.values)) != len(body.values):
        raise HTTPException(422, "values must be distinct integers in [1, 756]")
    cands = [CandidateIn(program=body.template.replace("{n}", str(v)).replace(body.base.score, f"{body.base.score}_{v}"),
                         score=f"{body.base.score}_{v}") for v in body.values]
    out = hypothesis_compare(CompareIn(base=body.base, candidates=cands))
    out["note"] = (f"{len(body.values)} variants were searched. Each extra variant raises the bar: the corrected p-values and the "
                   "probability of backtest overfitting account for the whole search, not just the winner.")
    return out
