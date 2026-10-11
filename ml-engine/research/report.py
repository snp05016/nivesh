"""Report assembly (spec 2.2 steps 5-8, 6.2, 6.5): one ``ResearchReport`` and its ledger ``Prediction`` rows.

Everything here is pure: :class:`Context` carries the night's snapshot (panel up
to the market date D, PIT membership, raw fv1 features, the benchmark, verified
artefacts and their scores), built once by ``pipeline.build_context``.

- Snapshot facts read ``px_idx`` (price returns, dividends excluded) against
  ``NIFTY50_PR``; the 52-week high and low are display closes back-adjusted to
  D via ``close_D * px_s / px_D`` (3.3).
- Outlooks carry the artefact tier only (D10): ``out_of_universe`` off the
  universe; ``unavailable`` with ``manifest_invalid``, ``data_quality_flag``
  (own close suspect) or ``insufficient_history``; a non-PIT universe forces
  ``no_reliable_edge`` with ``survivorship_biased_universe`` (D2). A cohort is
  attached only for ``validated_edge`` with gate P passed (D9). Fallback rows
  add ``prices_fallback_yfinance``. Backend fields stay null.
- The model card is a summary (data period, limitations); gates are admin-only.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from . import config
from .contract import (
    HORIZON_LABELS,
    REPORT_ENGINE_VERSION,
    SCHEMA_VERSION,
    ArtefactTier,
    AsOf,
    Cohort,
    Coverage,
    Fact,
    Fundamentals,
    HorizonOutlook,
    ModelCard,
    ModelCardHorizon,
    PipelineStage,
    Prediction,
    Provenance,
    ReasonCode,
    ResearchReport,
    Risk,
    Snapshot,
    Source,
    SourceStatus,
    UniverseQuality,
    outlook_event,
)
from .factor_profile import factor_profile
from .formatting import make_fact
from .fundamentals import fundamentals_block, market_cap_cr, sector, unavailable_fundamentals
from .registry import Artefact
from .risk import risk_block

__all__ = [
    "Context",
    "as_timestamp",
    "HorizonModel",
    "LABEL_DEFINITION",
    "assemble_report",
    "expected_maturity",
    "predictions_for",
]

FundamentalsMode = Literal["fetch", "skip"]

LABEL_DEFINITION = (
    "Centred percentile rank of the next 21- or 63-trading-day log price return "
    "(dividends excluded) within the 200 most-traded NSE stocks"
)
LIMITATIONS = [
    "Prices exclude dividends.",
    "Fundamentals come from Yahoo Finance and are not point-in-time.",
    "Statistical patterns found in past data can weaken or vanish.",
]
SURVIVORSHIP_LIMITATION = (
    "Development data: the stock list contains only companies listed today, "
    "so it leaves out companies that were delisted."
)
ARTEFACT_TIERS: tuple[str, ...] = ("validated_edge", "weak_evidence", "no_reliable_edge")
_ARTEFACT_REASON = re.compile(r"^(gate_failed:G[0-6]|survivorship_biased_universe)$")
_PRICE_SOURCE: dict[str, Source] = {"nse_bhavcopy": "nse_bhavcopy", "yfinance": "yfinance"}
_TURNOVER_WINDOW = 63
_MIN_WINDOW_SHARE = config.FEATURE_RULES["min_window_coverage"]
_RETURN_LOOKBACKS = {"r_1m_pct": 21, "r_3m_pct": 63, "r_6m_pct": 126, "r_12m_pct": 252}
_STAGES = ("prices", "universe", "features", "scores", "risk", "fundamentals", "assemble")


@dataclass
class HorizonModel:
    """The active artefact for one horizon and its scores on D (indexed by entity_id).

    ``artefact`` is None when verification failed (``problems`` says why); then no
    outlook tier and no prediction exists for that horizon (``manifest_invalid``).
    ``scores`` columns: score, rank_pct, bucket, p_top_half, feature_hash; only
    traded, non-suspect rows with at most 30% NaN features are scored.
    """

    horizon: int
    artefact: Artefact | None = None
    problems: list[str] = field(default_factory=list)
    scores: pd.DataFrame | None = None


@dataclass
class Context:
    """One snapshot (market date D) shared by every report of a run or an on-demand compute."""

    as_of: date
    panel: pd.DataFrame  # 3.3 panel, dates <= D
    calendar: pd.DatetimeIndex
    raw_day: pd.DataFrame  # raw fv1 features on D, indexed (date, entity_id)
    membership_day: pd.DataFrame  # membership rows on D
    universe: frozenset[str]  # entity ids in U_D
    universe_vol_pct: np.ndarray  # vol_252 in % of every U_D member (risk.vol_pctl reference)
    quality: UniverseQuality
    index: pd.Series | None  # NIFTY50_PR closes up to D
    data_sha256: str
    models: dict[int, HorizonModel]
    computed_at: datetime
    git_sha: str | None
    sources: list[SourceStatus]
    run_reasons: list[str] = field(default_factory=list)  # run-wide degraded reasons
    _rows: dict[str, np.ndarray] = field(default_factory=dict, repr=False)

    def entity_rows(self, entity_id: str) -> pd.DataFrame:
        """The entity's panel rows up to D, sorted by date (empty when unknown)."""
        if not self._rows:
            self._rows = {str(k): v for k, v in self.panel.groupby("entity_id", sort=False).indices.items()}
        pos = self._rows.get(entity_id)
        if pos is None:
            return self.panel.iloc[0:0]
        return self.panel.iloc[pos].sort_values("date", kind="stable")


# ── small helpers ───────────────────────────────────────────────────────────


def _finite(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _fact(fid: str, value: float | None, *, source: Source, as_of: date | None, stale: bool = False,
          missing: ReasonCode = "insufficient_history", method: str | None = None) -> Fact:
    """Catalogue fact; ``missing`` is the reason when there is no value, ``stale`` marks an old row."""
    v = _finite(value)
    if v is None:
        return make_fact(fid, None, source=source, as_of=as_of, method=method, reason=missing)
    return make_fact(fid, v, source=source, as_of=as_of, method=method, status="stale" if stale else None)


def as_timestamp(value: Any) -> pd.Timestamp:
    """``pd.Timestamp(value)`` for a value known not to be NaT (narrows ``Timestamp | NaTType``)."""
    return cast(pd.Timestamp, pd.Timestamp(value))


def _day(value: Any) -> date:
    return as_timestamp(value).date()


def _pos(cal: pd.DatetimeIndex, ts: pd.Timestamp) -> int:
    """Position of a session in the (unique, sorted) calendar."""
    return int(cast(int, cal.get_loc(ts)))


def _last_on_or_before(series: pd.Series, ts: pd.Timestamp) -> tuple[pd.Timestamp, float] | None:
    """(date, value) of the last finite value on or before ``ts``; ``series`` is date-indexed and sorted."""
    s = series.loc[:ts].dropna()
    if s.empty:
        return None
    return as_timestamp(s.index[-1]), float(s.iloc[-1])


def expected_maturity(as_of: date, h: int) -> date:
    """Weekday projection of session t+h (3.8); the scorer uses the true session calendar."""
    return np.busday_offset(np.datetime64(as_of, "D"), h, roll="forward").astype(object)


def feature_hash(values: Sequence[float] | np.ndarray) -> str:
    """sha256 of the ranked fv1 feature vector the model scored (float64 bytes, FEATURES order)."""
    data = np.ascontiguousarray(np.asarray(values, dtype="float64")).tobytes()
    return hashlib.sha256(config.FEATURE_VERSION.encode() + b"|" + data).hexdigest()


# ── snapshot ────────────────────────────────────────────────────────────────


def _snapshot(ctx: Context, rows: pd.DataFrame, payload: Mapping[str, Any] | None, suspect: bool) -> Snapshot:
    D = ctx.as_of
    last = rows.iloc[-1]
    T = as_timestamp(last["date"])
    stale = T.date() < D
    price_src = _PRICE_SOURCE.get(str(last["source"]), "computed")
    cal = ctx.calendar
    pos = _pos(cal, T)
    px = pd.Series(rows["px_idx"].to_numpy(dtype=float), index=pd.DatetimeIndex(rows["date"])).where(lambda s: s > 0)
    px_T = _finite(px.loc[T]) if T in px.index else None
    close_T = float(last["close"])
    first_date = as_timestamp(rows["date"].iloc[0])

    def price(fid: str, value: float | None, source: Source) -> Fact:
        if suspect:  # the close itself is a bad tick: nothing derived from it is shown
            return make_fact(fid, None, source=source, as_of=D, reason="data_quality_flag")
        return _fact(fid, value, source=source, as_of=T.date(), stale=stale)

    def back(k: int) -> float | None:
        if pos - k < 0 or px_T is None:
            return None
        hit = _last_on_or_before(px, as_timestamp(cal[pos - k]))
        return None if hit is None else (px_T / hit[1] - 1.0) * 100.0

    prev = back(1) if pos >= 1 and px_T is not None else None
    returns = {name: back(k) for name, k in _RETURN_LOOKBACKS.items()}

    high = low = below = None
    if px_T is not None and pos >= 251 and first_date <= cal[pos - 251]:
        window = px.loc[cal[pos - 251]:T].dropna()
        if len(window):
            high = close_T * float(window.max()) / px_T
            low = close_T * float(window.min()) / px_T
            below = max(0.0, (1.0 - close_T / high) * 100.0)

    turnover = None
    tw = rows.loc[pd.DatetimeIndex(rows["date"]) >= cal[max(0, pos - _TURNOVER_WINDOW + 1)], "turnover_inr"]
    tw = tw.where(tw > 0).dropna()
    if pos >= _TURNOVER_WINDOW - 1 and len(tw) >= math.ceil(_MIN_WINDOW_SHARE * _TURNOVER_WINDOW):
        turnover = float(tw.median()) / 1e7

    nifty: Fact
    nifty_reason: ReasonCode = "source_unavailable"
    n12 = None
    nifty_stale = False
    nifty_asof: date | None = None
    if ctx.index is not None and not ctx.index.dropna().empty:
        nifty_reason = "insufficient_history"
        idx = ctx.index.sort_index()
        day = as_timestamp(D)
        end = _last_on_or_before(idx, day)
        d_pos = _pos(cal, day) if day in cal else pos
        base = _last_on_or_before(idx, as_timestamp(cal[d_pos - 252])) if d_pos >= 252 else None
        if end is not None and base is not None and base[0] < end[0]:
            n12 = (end[1] / base[1] - 1.0) * 100.0
            nifty_stale = end[0].date() < D
            nifty_asof = end[0].date()
    nifty = _fact("snapshot.nifty50_r_12m_pct", n12, source="yfinance", as_of=nifty_asof or D,
                  stale=nifty_stale, missing=nifty_reason)
    r12 = returns["r_12m_pct"]
    excess = None if suspect or r12 is None or n12 is None else r12 - n12
    excess_reason: ReasonCode = (
        "data_quality_flag" if suspect else nifty_reason if n12 is None else "insufficient_history"
    )
    cap = market_cap_cr(dict(payload)) if payload is not None else None
    fetched = _day(payload["fetched_at"]) if payload is not None and payload.get("fetched_at") else None

    return Snapshot(
        benchmark_id="NIFTY50_PR",
        last_close=price("snapshot.last_close", close_T, price_src),
        day_change_pct=price("snapshot.day_change_pct", prev, price_src),
        r_1m_pct=price("snapshot.r_1m_pct", returns["r_1m_pct"], "computed"),
        r_3m_pct=price("snapshot.r_3m_pct", returns["r_3m_pct"], "computed"),
        r_6m_pct=price("snapshot.r_6m_pct", returns["r_6m_pct"], "computed"),
        r_12m_pct=price("snapshot.r_12m_pct", r12, "computed"),
        nifty50_r_12m_pct=nifty,
        excess_12m_vs_nifty50_pp=_fact("snapshot.excess_12m_vs_nifty50_pp", excess, source="computed",
                                       as_of=D, stale=stale or nifty_stale, missing=excess_reason),
        high_52w=price("snapshot.high_52w", high, "computed"),
        low_52w=price("snapshot.low_52w", low, "computed"),
        pct_below_52w_high=price("snapshot.pct_below_52w_high", below, "computed"),
        median_turnover_63d_cr=_fact("snapshot.median_turnover_63d_cr", turnover, source=price_src,
                                     as_of=T.date(), stale=stale),
        market_cap_cr=_fact("snapshot.market_cap_cr", cap, source="yfinance", as_of=fetched,
                            missing="source_unavailable"),
    )


# ── outlooks ────────────────────────────────────────────────────────────────


def _artefact_tier(art: Artefact, quality: UniverseQuality) -> tuple[ArtefactTier, list[str]]:
    """The artefact's gate tier and reasons; a non-PIT universe forces no_reliable_edge (D2)."""
    tier = art.tier if art.tier in ARTEFACT_TIERS else "no_reliable_edge"
    reasons = [str(r) for r in art.gate_result.get("reason_codes") or [] if _ARTEFACT_REASON.match(str(r))]
    if quality != "pit":
        tier = "no_reliable_edge"
        reasons = ["survivorship_biased_universe"] + [r for r in reasons if r != "survivorship_biased_universe"]
    return cast(ArtefactTier, tier), list(dict.fromkeys(reasons))


def _cohort(art: Artefact, h: int, bucket: Any, as_of: date) -> Cohort | None:
    """The reserved cohort block: validated_edge and gate P only (checked by the caller)."""
    c = art.calibrator.cohort_for(bucket)
    if c is None:
        return None

    def prob(name: str) -> Fact:
        return _fact(f"outlook.{h}.cohort.{name}", c[name], source="model", as_of=as_of, missing="source_unavailable")

    return Cohort(
        bucket=int(c["bucket"]), frequency=prob("frequency"), ci_low=prob("ci_low"), ci_high=prob("ci_high"),
        cases=_fact(f"outlook.{h}.cohort.cases", float(c["cases"]), source="model", as_of=as_of),
        period=str(c["period"]), neutral=bool(c["neutral"]),
    )


def _outlook(ctx: Context, h: int, entity_id: str, in_u: bool, suspect: bool, fallback: bool) -> HorizonOutlook:
    hm = ctx.models.get(h) or HorizonModel(h)
    art = hm.artefact
    score_row = None
    if hm.scores is not None and entity_id in hm.scores.index:
        score_row = hm.scores.loc[entity_id]
    cohort = None
    if not in_u:
        tier, reasons, proc, model_id = "out_of_universe", ["not_in_universe"], None, None
    elif art is None:
        tier, reasons, proc, model_id = "unavailable", ["manifest_invalid"], config.PROCEDURE_ID, None
    elif suspect:
        tier, reasons, proc, model_id = "unavailable", ["data_quality_flag"], config.PROCEDURE_ID, art.model_id
    elif score_row is None or _finite(score_row["score"]) is None:
        tier, reasons, proc, model_id = "unavailable", ["insufficient_history"], config.PROCEDURE_ID, art.model_id
    else:
        tier, reasons = _artefact_tier(art, ctx.quality)
        proc, model_id = config.PROCEDURE_ID, art.model_id
        if fallback:
            reasons = [*reasons, "prices_fallback_yfinance"]
        if tier == "validated_edge" and art.gate_result.get("probability_display_passed") is True:
            cohort = _cohort(art, h, score_row["bucket"], ctx.as_of)
    return HorizonOutlook(
        horizon_days=cast(Any, h), horizon_label=cast(Any, HORIZON_LABELS[h]), event=outlook_event(h),
        evidence_tier=cast(Any, tier), reason_codes=reasons, cohort=cohort,
        procedure_id=proc, model_id=model_id,
    )


# ── risk, fundamentals, model card ──────────────────────────────────────────


def _blank_facts(node: Any, reason: ReasonCode) -> Any:
    """Every Fact dict inside ``node`` (a model_dump) made unavailable with ``reason``."""
    if isinstance(node, dict):
        if {"id", "unit", "display", "status", "reason"} <= set(node):
            return {**node, "value": None, "display": None, "status": "unavailable", "reason": reason}
        return {k: _blank_facts(v, reason) for k, v in node.items()}
    if isinstance(node, list):
        return [_blank_facts(v, reason) for v in node]
    return node


def _unavailable_risk(risk: Risk, reason: ReasonCode) -> Risk:
    """The same block with every fact unavailable (a suspect close, 2.6): no VaR rows, no series."""
    d = risk.model_dump()
    d["var_status"], d["var_1d"] = "unavailable", []
    d["drawdown_series"]["points"] = []
    for rr in d["return_ranges"]:
        rr["text"] = None
    return Risk.model_validate(_blank_facts(d, reason))


def _fundamentals(payload: Mapping[str, Any] | None, mode: FundamentalsMode, as_of: date,
                  peer_pes: Sequence[float] | None) -> tuple[Fundamentals, PipelineStage]:
    if mode == "skip":
        return (unavailable_fundamentals("source_unavailable"),
                PipelineStage(stage="fundamentals", status="skipped", detail="fundamentals not requested"))
    block = fundamentals_block(dict(payload) if payload is not None else None, as_of=as_of, peer_pes=peer_pes)
    if block.status == "unavailable":
        return block, PipelineStage(stage="fundamentals", status="failed", detail="no usable Yahoo Finance data")
    if block.status == "stale":
        return block, PipelineStage(stage="fundamentals", status="degraded", detail="statements older than 15 months")
    return block, PipelineStage(stage="fundamentals", status="ok", detail=None)


def _model_card(ctx: Context) -> ModelCard:
    arts = [m.artefact for h in config.HORIZONS if (m := ctx.models.get(h)) is not None and m.artefact is not None]
    first = arts[0] if arts else None
    trained = first.manifest.get("trained_through") if first else None
    limitations = list(LIMITATIONS)
    if ctx.quality != "pit":
        limitations.append(SURVIVORSHIP_LIMITATION)
    return ModelCard(
        procedure_id=config.PROCEDURE_ID if first else None,
        feature_version="fv1", universe_id="NSE_LIQ200", universe_quality=ctx.quality,
        label_definition=LABEL_DEFINITION,
        data_period=str(first.manifest["data_period"]) if first and first.manifest.get("data_period") else None,
        trained_through=date.fromisoformat(str(trained)) if trained else None,
        manifest_sha256=first.manifest_sha256 if first else None,
        limitations=limitations,
        horizons=[ModelCardHorizon(horizon_days=cast(Any, h)) for h in config.HORIZONS],
    )


def _provenance(ctx: Context) -> Provenance:
    return Provenance(
        engine_version=REPORT_ENGINE_VERSION,
        git_sha=ctx.git_sha,
        data_snapshot_id=f"snap-{ctx.as_of:%Y%m%d}-{ctx.data_sha256[:8]}",
        data_sha256=ctx.data_sha256,
        feature_version="fv1",
        cost_model_version=config.COST_MODEL_VERSION,
        config_sha256=config.config_sha256(),
        sources=list(ctx.sources),
    )


# ── assembly ────────────────────────────────────────────────────────────────


def assemble_report(
    ctx: Context,
    entity_id: str,
    *,
    payload: Mapping[str, Any] | None = None,
    fundamentals_mode: FundamentalsMode = "fetch",
    peer_pes: Sequence[float] | None = None,
    origin: Literal["nightly", "on_demand"] = "nightly",
) -> ResearchReport:
    """The contract report of ``entity_id`` on ``ctx.as_of``.

    ``payload`` is the ``fundamentals.fetch_fundamentals`` result (None when the
    fetch failed); ``fundamentals_mode="skip"`` leaves the block unavailable and
    the stage skipped. ``peer_pes`` are the sector peers' trailing P/Es in U_D.
    """
    rows = ctx.entity_rows(entity_id)
    if rows.empty:
        raise KeyError(f"entity {entity_id!r} has no rows on or before {ctx.as_of}")
    D = ctx.as_of
    last = rows.iloc[-1]
    on_day = _day(last["date"]) == D
    flags = str(last["quality_flags"]) if on_day else ""
    suspect = "suspect" in flags
    fallback = on_day and (str(last["source"]) == "yfinance" or "fallback" in flags)
    mrow = ctx.membership_day.loc[ctx.membership_day["entity_id"] == entity_id]
    in_u = on_day and entity_id in ctx.universe
    rank = mrow["turnover_rank"].iloc[0] if len(mrow) else None
    turnover_rank = None if rank is None or pd.isna(rank) else int(rank)

    outlooks = [_outlook(ctx, h, entity_id, in_u, suspect, fallback) for h in config.HORIZONS]
    risk = risk_block(rows, ctx.index, ctx.universe_vol_pct)
    if suspect:
        risk = _unavailable_risk(risk, "data_quality_flag")
    fundamentals, fund_stage = _fundamentals(payload, fundamentals_mode, D, peer_pes)

    coverage_reason: ReasonCode | None = (
        "not_in_universe" if not in_u else "data_quality_flag" if suspect else None
    )
    manifest_invalid = in_u and any(o.reason_codes == ["manifest_invalid"] for o in outlooks)
    problems = sorted({p for h in config.HORIZONS if (m := ctx.models.get(h)) for p in m.problems})

    reasons = list(ctx.run_reasons)
    if not on_day:
        reasons.append("stale_prices")
    if fallback:
        reasons.append("prices_fallback_yfinance")
    if suspect:
        reasons.append("data_quality_flag")
    if manifest_invalid:
        reasons.append("manifest_invalid")
    if fund_stage.status == "failed":
        reasons.append("fundamentals_unavailable")
    reasons = list(dict.fromkeys(reasons))

    stage: dict[str, PipelineStage] = {s: PipelineStage(stage=cast(Any, s), status="ok", detail=None) for s in _STAGES}
    if not on_day:
        stage["prices"] = PipelineStage(stage="prices", status="degraded", detail="no price row for the market date")
    elif fallback:
        stage["prices"] = PipelineStage(stage="prices", status="degraded", detail="yfinance fallback prices")
    if ctx.quality != "pit":
        stage["universe"] = PipelineStage(stage="universe", status="ok", detail="survivorship-biased development universe")
    if not in_u:
        stage["scores"] = PipelineStage(stage="scores", status="skipped", detail="not in the universe")
    elif manifest_invalid:
        stage["scores"] = PipelineStage(stage="scores", status="failed",
                                        detail=("; ".join(problems) or "artefact verification failed")[:300])
    elif suspect:
        stage["scores"] = PipelineStage(stage="scores", status="skipped", detail="suspect close on the market date")
    if suspect:
        stage["risk"] = PipelineStage(stage="risk", status="degraded", detail="suspect close on the market date")
    stage["fundamentals"] = fund_stage

    isin = str(last["isin"]) if str(last["source"]) != "local_csv" and str(last["isin"]) else None
    symbol = str(last["symbol"])
    return ResearchReport(
        schema_version=SCHEMA_VERSION,
        report_id=uuid.uuid4(),
        engine_version=REPORT_ENGINE_VERSION,
        origin=origin,
        status="degraded" if reasons else "ok",
        degraded_reasons=reasons,
        symbol=symbol,
        exchange="NSE",
        isin=isin,
        company_name=symbol,
        sector=sector(dict(payload)) if payload is not None else None,
        as_of=AsOf(market_date=D, computed_at=ctx.computed_at),
        coverage=Coverage(
            universe_id="NSE_LIQ200", in_universe=in_u, universe_quality=ctx.quality,
            turnover_rank=turnover_rank, outlook_eligible=in_u and not suspect, reason=coverage_reason,
        ),
        snapshot=_snapshot(ctx, rows, payload, suspect),
        outlooks=outlooks,
        factor_profile=factor_profile(ctx.raw_day, ctx.membership_day, entity_id, D),
        risk=risk,
        fundamentals=fundamentals,
        model_card=_model_card(ctx),
        provenance=_provenance(ctx),
        pipeline=[stage[s] for s in _STAGES],
    )


def predictions_for(ctx: Context, entity_id: str, report: ResearchReport) -> list[Prediction]:
    """Ledger rows (6.5) for every horizon whose outlook carries an artefact tier.

    That is exactly the in-universe, artefact-verified, quality-ok, scored case
    (8.2). ``entry_close`` is the raw close on D from the same snapshot; the
    maturity date is a weekday projection. No range fields (D11).
    """
    rows = ctx.entity_rows(entity_id)
    if rows.empty or _day(rows["date"].iloc[-1]) != ctx.as_of:
        return []
    entry_close = float(rows["close"].iloc[-1])
    out: list[Prediction] = []
    for o in report.outlooks:
        hm = ctx.models.get(o.horizon_days)
        if o.evidence_tier not in ARTEFACT_TIERS or hm is None or hm.artefact is None or hm.scores is None:
            continue
        s = hm.scores.loc[entity_id]
        bucket = _finite(s["bucket"])
        p = _finite(s["p_top_half"])
        out.append(Prediction(
            horizon_days=o.horizon_days,
            procedure_id=o.procedure_id or config.PROCEDURE_ID,
            model_id=hm.artefact.model_id,
            manifest_sha256=hm.artefact.manifest_sha256,
            universe_id="NSE_LIQ200",
            evidence_tier=cast(ArtefactTier, o.evidence_tier),
            reason_codes=list(o.reason_codes),
            score=float(s["score"]),
            rank_pct=float(s["rank_pct"]),
            bucket=None if bucket is None else int(bucket),
            p_top_half=p,
            entry_close=entry_close,
            feature_hash=str(s["feature_hash"]),
            expected_maturity_date=expected_maturity(ctx.as_of, o.horizon_days),
        ))
    return out
