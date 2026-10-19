"""ml-engine internal Lab API, ``/lab/v1``. Stateless: callers send (config, actions).

Same auth as ``/research/v1`` (``X-ML-Engine-Key``). The backend owns users, stores the
action log and decides who may see what; this service only computes.
"""
from __future__ import annotations

import json
import os
import string
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from research.api import require_key

from . import autopsy as ap
from .data import MarketData, PITView
from .loaders import liquid_universe, load_market
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
    return json.loads(SCENARIOS.read_text())


@router.get("/universe")
def universe(start: date, n: int = Query(20, ge=1, le=30)) -> dict:
    """The n most liquid stocks on `start`, chosen with data available on that date."""
    md = _market(start, start, (), _source())
    return {"asof": start.isoformat(), "symbols": liquid_universe(md, start, n), "provenance": md.provenance}
