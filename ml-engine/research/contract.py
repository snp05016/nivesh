"""ResearchReport contract ``research.v1`` (spec 6). Source of truth for every consumer.

Pydantic v2, ``extra="forbid"`` everywhere. Within v1 changes are additive only.
``python -m research.export_contract`` writes the JSON Schema and fixtures.

Never-exist names (REG-02, UX-22): no field is named signal, rating, zone, flag
or gates, or starts with target/upside/downside/stop/entry/confidence, and no
field contains "coverage" except the top-level universe ``coverage`` block of
``ResearchReport`` (universe membership, not a statistical coverage figure).
Two 6.2 fields were renamed to honour that rule: ``ModelCard.target`` is
``label_definition`` and the always-"green" VaR ``backtest.zone`` is dropped
(only green methods are ever shown).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import (
    UUID4,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from . import ENGINE_VERSION
from .config import FEATURE_VERSION

SCHEMA_VERSION = "research.v1"
REPORT_ENGINE_VERSION = f"re-{ENGINE_VERSION}+{FEATURE_VERSION}"

Unit = Literal["inr", "inr_cr", "pct", "pp", "prob", "pctl", "ratio", "x", "count", "sessions"]
FactStatus = Literal["ok", "stale", "unavailable"]
Source = Literal["nse_bhavcopy", "yfinance", "computed", "model"]
ReasonCode = Literal[
    "source_unavailable",
    "stale_source",
    "insufficient_history",
    "data_quality_flag",
    "not_applicable_financials",
    "source_not_integrated",
    "not_in_universe",
    "backtest_failed",
    "policy_hidden",
]
Horizon = Literal[21, 63]
UniverseQuality = Literal["pit", "survivorship_biased"]
EvidenceTier = Literal[
    "validated_edge", "weak_evidence", "no_reliable_edge", "out_of_universe", "unavailable"
]
ArtefactTier = Literal["validated_edge", "weak_evidence", "no_reliable_edge"]

OutlookReasonCode = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^(gate_failed:G[0-6]|survivorship_biased_universe|manifest_invalid"
            r"|insufficient_history|data_quality_flag|not_in_universe|live_under_review"
            r"|live_shadow_collecting|snapshot_expired|policy_hidden|prices_fallback_yfinance)$"
        )
    ),
]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]

HORIZON_LABELS: dict[int, str] = {
    21: "about 1 month (21 trading days)",
    63: "about 3 months (63 trading days)",
}

# Spec 4.8 (the family order here is the fixed display order).
FAMILY_LABELS: dict[str, str] = {
    "momentum": "Momentum (higher = rose more over the past 3 to 12 months)",
    "reversal": "Recent short-term move (higher = rose more)",
    "risk": "Risk (higher = more volatile)",
    "liquidity": "Liquidity (higher = easier to trade)",
    "trend": "Trend (higher = stronger recent uptrend)",
}
Family = Literal["momentum", "reversal", "risk", "liquidity", "trend"]


def outlook_event(horizon_days: int) -> str:
    """The fixed HorizonOutlook.event text (6.2)."""
    return (
        "finishes in the top half of the 200 most-traded NSE stocks by price return "
        f"(dividends excluded) over the next {horizon_days} trading days"
    )


def _build_fact_catalogue() -> dict[str, tuple[str, Unit, int, bool]]:
    """Spec 6.3: fact id -> (label, unit, decimals, signed).

    ``factor.{feature_id}.value|pctl`` facts are not catalogued: their labels and
    display units come from the factor-profile code (4.8).
    """
    cat: dict[str, tuple[str, Unit, int, bool]] = {}

    def add(fid: str, label: str, unit: Unit, decimals: int, signed: bool = False) -> None:
        cat[fid] = (label, unit, decimals, signed)

    s = "snapshot."
    add(s + "last_close", "Last close", "inr", 2)
    add(s + "day_change_pct", "Change on the day", "pct", 2, True)
    for key, period in (("1m", "1 month"), ("3m", "3 months"), ("6m", "6 months"), ("12m", "12 months")):
        add(f"{s}r_{key}_pct", f"Price return, last {period} (dividends excluded)", "pct", 1, True)
    add(s + "nifty50_r_12m_pct", "Nifty 50 price return, last 12 months", "pct", 1, True)
    add(
        s + "excess_12m_vs_nifty50_pp",
        "Price return above or below the Nifty 50, last 12 months (dividends excluded)",
        "pp", 1, True,
    )
    add(s + "high_52w", "52-week high (adjusted for splits and bonuses)", "inr", 2)
    add(s + "low_52w", "52-week low (adjusted for splits and bonuses)", "inr", 2)
    add(s + "pct_below_52w_high", "Distance below the 52-week high", "pct", 1)
    add(s + "median_turnover_63d_cr", "Median daily value traded, last 3 months", "inr_cr", 1)
    add(s + "market_cap_cr", "Market capitalisation", "inr_cr", 0)

    r = "risk."
    add(r + "vol_ewma_ann_pct", "Annualised volatility (recent-weighted)", "pct", 1)
    add(r + "vol_63d_ann_pct", "Annualised volatility, last 3 months", "pct", 1)
    add(r + "vol_252d_ann_pct", "Annualised volatility, last 12 months", "pct", 1)
    add(r + "vol_pctl", "Volatility compared with the 200 most-traded NSE stocks", "pctl", 0)
    add(r + "beta.raw", "Beta to the Nifty 50", "ratio", 2)
    add(r + "beta.se", "Standard error of the beta to the Nifty 50", "ratio", 2)
    add(r + "beta.blume_adjusted", "Beta to the Nifty 50, adjusted towards 1", "ratio", 2)
    for level in (95, 99):
        for method in ("historical_500d", "fhs_ewma"):
            base = f"{r}var_1d.{level}.{method}."
            add(base + "var_pct", f"One-day loss threshold, {level}%", "pct", 2, True)
            add(base + "cvar_pct", f"Average loss beyond the one-day threshold, {level}%", "pct", 2, True)
    for key, period in (("1y", "1 year"), ("3y", "3 years"), ("5y", "5 years")):
        add(f"{r}drawdown.max_{key}_pct", f"Largest fall from a peak, last {period}", "pct", 1, True)
    add(r + "drawdown.current_pct", "Current distance from the last peak", "pct", 1, True)
    add(r + "drawdown.days_since_peak", "Trading days since the last peak", "sessions", 0)
    add(r + "drawdown.ulcer_1y", "Ulcer index, last 1 year", "ratio", 1)
    for h in (21, 63):
        add(f"{r}range.{h}.low_pct",
            f"Low end of this stock's past {h}-trading-day returns (10th percentile)", "pct", 1, True)
        add(f"{r}range.{h}.high_pct",
            f"High end of this stock's past {h}-trading-day returns (90th percentile)", "pct", 1, True)

    for family, label in FAMILY_LABELS.items():
        name = label.split(" (", 1)[0]
        add(f"factor.{family}.pctl", f"{name} compared with the 200 most-traded NSE stocks", "pctl", 0)

    f = "fund."
    add(f + "pe_ttm", "Price to earnings, trailing 12 months", "x", 1)
    add(f + "pb", "Price to book value", "x", 1)
    add(f + "ev_ebitda", "Enterprise value to EBITDA", "x", 1)
    add(f + "dividend_yield_pct", "Dividend yield", "pct", 2)
    add(f + "pe_sector_pctl", "Price to earnings compared with sector peers", "pctl", 0)
    add(f + "roe_pct", "Return on equity", "pct", 1)
    add(f + "operating_margin_pct", "Operating margin", "pct", 1)
    add(f + "debt_to_equity", "Debt to equity", "ratio", 2)
    add(f + "cfo_to_pat", "Operating cash flow to net profit", "ratio", 2)
    add(f + "piotroski.f_score", "Piotroski F-score", "count", 0)
    add(f + "piotroski.max_possible", "Piotroski checks available", "count", 0)
    add(f + "altman_z_em", "Altman Z″-score, emerging markets", "ratio", 2)
    add(f + "beneish_m", "Beneish M-score", "ratio", 2)

    # Reserved (no v1 UI, never in the LLM payload).
    for h in (21, 63):
        c = f"outlook.{h}.cohort."
        add(c + "frequency", "Share of past cases in this group that finished in the top half", "prob", 0)
        add(c + "ci_low", "Lower end of the 95% interval for that share", "prob", 0)
        add(c + "ci_high", "Upper end of the 95% interval for that share", "prob", 0)
        add(c + "cases", "Past cases in this group", "count", 0)
    return cat


FACT_CATALOGUE = _build_fact_catalogue()
FACT_LABELS: dict[str, str] = {fid: spec[0] for fid, spec in FACT_CATALOGUE.items()}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── 6.1 Fact ────────────────────────────────────────────────────────────────


class Fact(_Model):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.]+$")]
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    value: float | None
    unit: Unit
    decimals: Annotated[int, Field(ge=0, le=4)]
    signed: bool
    display: str | None
    status: FactStatus
    reason: ReasonCode | None
    source: Source
    as_of: date | None
    method: str | None

    @field_validator("value")
    @classmethod
    def _finite(cls, v: float | None) -> float | None:
        if v is not None and not math.isfinite(v):
            raise ValueError("value must be finite (use status 'unavailable' instead)")
        return v

    @model_validator(mode="after")
    def _invariants(self) -> Fact:
        if (self.value is None) != (self.display is None):
            raise ValueError(f"{self.id}: display must be null iff value is null")
        if self.status == "unavailable":
            if self.value is not None:
                raise ValueError(f"{self.id}: an unavailable fact carries no value")
            if self.reason is None:
                raise ValueError(f"{self.id}: an unavailable fact needs a reason")
        else:
            if self.value is None:
                raise ValueError(f"{self.id}: an {self.status} fact needs a value and display")
            if (self.reason is None) != (self.status == "ok"):
                raise ValueError(f"{self.id}: reason must be non-null iff status != ok")
        return self


def iter_facts(obj: Any) -> Iterator[Fact]:
    """Yield every Fact nested anywhere inside a contract model or list."""
    if isinstance(obj, Fact):
        yield obj
    elif isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            yield from iter_facts(getattr(obj, name))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from iter_facts(item)


# ── 6.2 Report blocks ───────────────────────────────────────────────────────


class AsOf(_Model):
    market_date: date
    computed_at: AwareDatetime


class Coverage(_Model):
    """Universe membership of the symbol (not a statistical coverage figure)."""

    universe_id: Literal["NSE_LIQ200"]
    in_universe: bool
    universe_quality: UniverseQuality
    turnover_rank: int | None
    outlook_eligible: bool
    reason: ReasonCode | None


class Snapshot(_Model):
    benchmark_id: Literal["NIFTY50_PR"]
    last_close: Fact
    day_change_pct: Fact
    r_1m_pct: Fact
    r_3m_pct: Fact
    r_6m_pct: Fact
    r_12m_pct: Fact
    nifty50_r_12m_pct: Fact
    excess_12m_vs_nifty50_pp: Fact
    high_52w: Fact
    low_52w: Fact
    pct_below_52w_high: Fact
    median_turnover_63d_cr: Fact
    market_cap_cr: Fact


class Cohort(_Model):
    """Reserved: no v1 UI; served only under an effective cohort_frequency (D9)."""

    bucket: Annotated[int, Field(ge=1, le=5)]
    frequency: Fact
    ci_low: Fact
    ci_high: Fact
    cases: Fact
    period: str
    neutral: bool


class HorizonOutlook(_Model):
    horizon_days: Horizon
    horizon_label: Literal["about 1 month (21 trading days)", "about 3 months (63 trading days)"]
    event: str
    evidence_tier: EvidenceTier
    reason_codes: list[OutlookReasonCode]
    tier_text: str | None = None  # backend-owned
    cohort: Cohort | None = None
    procedure_id: str | None
    model_id: str | None
    prediction_id: int | None = None  # backend-owned

    @model_validator(mode="after")
    def _consistent(self) -> HorizonOutlook:
        if self.horizon_label != HORIZON_LABELS[self.horizon_days]:
            raise ValueError("horizon_label does not match horizon_days")
        if self.event != outlook_event(self.horizon_days):
            raise ValueError("event must be the fixed 6.2 text for this horizon")
        if self.cohort is not None and self.evidence_tier != "validated_edge":
            raise ValueError("a cohort is only allowed for validated_edge (D9, D10)")
        return self


class FactorMetric(_Model):
    feature_id: str
    label: str
    value: Fact
    pctl: Fact


class FactorFamily(_Model):
    family: Family
    label: str
    pctl: Fact
    metrics: list[FactorMetric]

    @model_validator(mode="after")
    def _label(self) -> FactorFamily:
        if self.label != FAMILY_LABELS[self.family]:
            raise ValueError(f"family label must be FAMILY_LABELS[{self.family!r}]")
        return self


class FactorProfile(_Model):
    universe_id: Literal["NSE_LIQ200"]
    families: list[FactorFamily]

    @field_validator("families")
    @classmethod
    def _order(cls, v: list[FactorFamily]) -> list[FactorFamily]:
        if [f.family for f in v] != list(FAMILY_LABELS):
            raise ValueError(f"families must be exactly {list(FAMILY_LABELS)} in that order")
        return v


class Beta(_Model):
    benchmark_id: Literal["NIFTY50_PR"]
    method: Literal["dimson_lag1_daily_252"]
    raw: Fact
    se: Fact
    blume_adjusted: Fact


class VarBacktest(_Model):
    window_days: Literal[250]
    exceptions: Annotated[int, Field(ge=0)]
    expected: float
    kupiec_p: float
    christoffersen_p: float


class VarRow(_Model):
    level: float
    method: Literal["historical_500d", "fhs_ewma"]
    var_pct: Fact
    cvar_pct: Fact
    backtest: VarBacktest

    @field_validator("level")
    @classmethod
    def _level(cls, v: float) -> float:
        if v not in (0.95, 0.99):
            raise ValueError("level must be 0.95 or 0.99")
        return v


class Drawdown(_Model):
    max_1y_pct: Fact
    max_3y_pct: Fact
    max_5y_pct: Fact
    current_pct: Fact
    days_since_peak: Fact
    ulcer_1y: Fact


class DrawdownSeries(_Model):
    freq: Literal["W"]
    unit: Literal["pct"]
    points: Annotated[list[tuple[date, float]], Field(max_length=160)]


class ReturnRange(_Model):
    """Descriptive historical range (4.5, D11). No coverage figure, not a forecast."""

    horizon_days: Horizon
    low_pct: Fact
    high_pct: Fact
    window_sessions: Annotated[int, Field(ge=0)]
    text: str | None
    method: Literal["empirical_rolling_756d"]


class Risk(_Model):
    vol_ewma_ann_pct: Fact
    vol_63d_ann_pct: Fact
    vol_252d_ann_pct: Fact
    vol_pctl: Fact
    beta: Beta
    var_status: Literal["ok", "backtest_failed", "unavailable"]
    var_1d: list[VarRow]
    drawdown: Drawdown
    drawdown_series: DrawdownSeries
    return_ranges: list[ReturnRange]

    @model_validator(mode="after")
    def _shape(self) -> Risk:
        if [r.horizon_days for r in self.return_ranges] != [21, 63]:
            raise ValueError("return_ranges must be [21, 63] in that order")
        if (self.var_status == "ok") != bool(self.var_1d):
            raise ValueError("var_1d rows are present iff var_status is ok (only green methods)")
        return self


class Valuation(_Model):
    pe_ttm: Fact
    pb: Fact
    ev_ebitda: Fact
    dividend_yield_pct: Fact
    pe_sector_pctl: Fact


class Quality(_Model):
    roe_pct: Fact
    operating_margin_pct: Fact
    debt_to_equity: Fact
    cfo_to_pat: Fact


class PiotroskiCheck(_Model):
    id: str
    value: Literal[0, 1] | None


class Piotroski(_Model):
    """Shown as "f of max_possible available checks"; no grade (4.7)."""

    f_score: Fact
    max_possible: Fact
    signals: list[PiotroskiCheck]


class ScoreValue(_Model):
    """Altman / Beneish value only; zones and thresholds are never emitted."""

    applicable: bool
    value: Fact


class Fundamentals(_Model):
    status: FactStatus
    reason: ReasonCode | None
    source: Literal["yfinance"]
    fetched_at: AwareDatetime | None
    fiscal_period_end: date | None
    point_in_time: Literal[False]
    statement_basis: Literal["consolidated", "standalone", "unknown"]
    is_financial: bool | None
    valuation: Valuation
    quality: Quality
    piotroski: Piotroski
    altman_z_em: ScoreValue
    beneish_m: ScoreValue

    @model_validator(mode="after")
    def _reason(self) -> Fundamentals:
        if (self.reason is None) != (self.status == "ok"):
            raise ValueError("fundamentals reason must be non-null iff status != ok")
        return self


class ModelCardHorizon(_Model):
    horizon_days: Horizon
    tier_text: str | None = None  # backend-owned


class ModelCard(_Model):
    """Summary only; gates are admin-only (GET /model-card?detail=full)."""

    procedure_id: str | None
    feature_version: Literal["fv1"]
    universe_id: Literal["NSE_LIQ200"]
    universe_quality: UniverseQuality
    label_definition: str  # spec 6.2 "target", renamed (never-exist rule)
    data_period: str | None
    trained_through: date | None
    manifest_sha256: Sha256 | None
    limitations: list[str]
    horizons: list[ModelCardHorizon]


class SourceStatus(_Model):
    id: Source
    last_success: date | None
    status: Literal["ok", "fallback", "failed"]
    note: str | None


class Provenance(_Model):
    engine_version: str
    git_sha: str | None
    data_snapshot_id: Annotated[str, StringConstraints(pattern=r"^snap-\d{8}-[0-9a-f]{8}$")]
    data_sha256: Sha256
    feature_version: Literal["fv1"]
    cost_model_version: str
    config_sha256: Sha256
    sources: list[SourceStatus]


class PipelineStage(_Model):
    stage: Literal["prices", "universe", "features", "scores", "risk", "fundamentals", "assemble"]
    status: Literal["ok", "degraded", "failed", "skipped"]
    detail: str | None


# ── Backend-owned blocks (null in ml-engine output) ─────────────────────────


class Staleness(_Model):
    sessions_old: Annotated[int, Field(ge=0)]
    state: Literal["fresh", "stale", "expired"]


class NarrativeSection(_Model):
    id: Literal["risk", "factor_profile", "fundamentals"]
    text: str


class Narrative(_Model):
    status: Literal["llm_validated", "template"]
    language: Literal["en"]
    summary: str
    sections: list[NarrativeSection]
    prompt_version: Literal["rf-1"]
    validator_version: Literal["gv-1"]
    attempts: Annotated[int, Field(ge=0)]
    facts_hash: str


class LiveHorizon(_Model):
    horizon_days: Horizon
    state: Literal["collecting", "ok", "under_review"]
    since: date | None
    matured_dates: Annotated[int, Field(ge=0)]
    independent_periods: Annotated[int, Field(ge=0)]
    min_periods_required: Literal[12]


class LiveTrackRecord(_Model):
    """States only; never rates or IC (8.6)."""

    visible: bool
    horizons: list[LiveHorizon]


class Compliance(_Model):
    mode: Literal["unregistered_educational"]
    disclaimer_id: Literal["research_v1"]
    disclaimer_text: str
    ai_disclosure: str
    outlook_display: Literal["tier_only", "cohort_frequency"]
    track_record_visible: bool
    lexicon_version: Literal["lx-1"]


class ResearchReport(_Model):
    schema_version: Literal["research.v1"]
    report_id: UUID4
    engine_version: Annotated[str, StringConstraints(pattern=r"^re-\d+\.\d+\.\d+\+fv\d+$")]
    origin: Literal["nightly", "on_demand"]
    status: Literal["ok", "degraded"]
    degraded_reasons: list[str]
    symbol: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9&-]{1,20}$")]
    exchange: Literal["NSE"]
    isin: str | None
    company_name: str
    sector: str | None
    as_of: AsOf
    coverage: Coverage
    snapshot: Snapshot
    outlooks: list[HorizonOutlook]
    factor_profile: FactorProfile
    risk: Risk
    fundamentals: Fundamentals
    model_card: ModelCard
    provenance: Provenance
    pipeline: list[PipelineStage]
    staleness: Staleness | None = None
    narrative: Narrative | None = None
    live_track_record: LiveTrackRecord | None = None
    compliance: Compliance | None = None

    @model_validator(mode="after")
    def _report(self) -> ResearchReport:
        if [o.horizon_days for o in self.outlooks] != [21, 63]:
            raise ValueError("outlooks must be [21, 63] in that order")
        seen: set[str] = set()
        for fact in iter_facts(self):
            if fact.id in seen:
                raise ValueError(f"duplicate fact id {fact.id!r}")
            seen.add(fact.id)
        return self


# ── 6.5 Internal shapes ─────────────────────────────────────────────────────


class Prediction(_Model):
    horizon_days: Horizon
    procedure_id: str
    model_id: str
    manifest_sha256: Sha256
    universe_id: Literal["NSE_LIQ200"]
    evidence_tier: ArtefactTier
    reason_codes: list[OutlookReasonCode]
    score: float
    rank_pct: Annotated[float, Field(ge=0.0, le=1.0)]
    bucket: Annotated[int, Field(ge=1, le=5)] | None
    p_top_half: Annotated[float, Field(ge=0.0, le=1.0)] | None
    entry_close: Annotated[float, Field(gt=0.0)]  # raw close at as_of, same snapshot
    feature_hash: str | None
    expected_maturity_date: date


class RunItem(_Model):
    """One symbol of a nightly run; predictions only for in-universe, verified, quality-ok symbols."""

    report: ResearchReport
    predictions: list[Prediction]


class RunCounts(_Model):
    reports: int = 0
    predictions: int = 0
    degraded: int = 0
    quarantined: int = 0
    ca_unverified: int = 0


class RunStatus(_Model):
    run_id: str
    market_date: date
    status: Literal["running", "ok", "degraded", "failed", "skipped_holiday"]
    stage: str | None
    counts: RunCounts
    error: str | None  # e.g. "engine_restarted"
    started_at: AwareDatetime
    finished_at: AwareDatetime | None


class OutcomeRequestItem(_Model):
    prediction_id: int
    isin: str | None
    symbol: str
    as_of: date
    horizon_days: Horizon
    entry_close: Annotated[float, Field(gt=0.0)]


class OutcomeResult(_Model):
    prediction_id: int
    outcome_status: Literal["matured", "void", "pending"]
    void_reason: Literal["entry_price_mismatch", "suspect_price"] | None
    realized_return_pct: float | None
    realized_excess_pp: float | None
    realized_top_half: bool | None
    nifty50_return_pct: float | None
    stale_exit: bool | None
    scorer_version: Literal["os-2"]

    @model_validator(mode="after")
    def _void(self) -> OutcomeResult:
        if (self.void_reason is None) != (self.outcome_status != "void"):
            raise ValueError("void_reason must be non-null iff outcome_status is void")
        return self


class LiveMetricsRow(_Model):
    as_of: date
    symbol: str
    score: float
    rank_pct: float
    bucket: int | None
    p_top_half: float | None
    outcome_status: Literal["matured", "void", "pending"]
    realized_excess_pp: float | None
    realized_top_half: bool | None
    stale_exit: bool | None


class LiveMetricsRequest(_Model):
    procedure_id: str
    horizon_days: Horizon
    rows: list[LiveMetricsRow]


class LiveMetrics(_Model):
    rank_ic_mean: float | None
    rank_ic_hac_t: float | None
    rank_ic_ci95: tuple[float, float] | None
    oos_rank_ic_mean: float | None
    hit_rate_directional: float | None
    brier: float | None
    bss: float | None
    ece: float | None  # null unless n_eff >= 500
    window: str | None


class LiveAlarm(_Model):
    code: Literal["rolling_ic_negative", "calibrator_drift", "psi_warning"]
    detail: str | None


class LiveMetricsResponse(_Model):
    live_status: Literal["collecting", "ok", "under_review"]
    matured_n: int
    void_n: int
    stale_exit_n: int
    matured_dates: int
    independent_periods: int
    live_gate_passed: bool
    metrics: LiveMetrics
    alarms: list[LiveAlarm]
