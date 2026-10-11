"""Write the research.v1 JSON Schema and the three contract fixtures (spec 6, 6.7).

    python -m research.export_contract          # (re)write the files
    python -m research.export_contract --check  # exit 1 on any byte difference

Fixtures are deterministic: fixed uuids, dates, numbers and the exact 6.4
texts. Companies are fictional; numbers are illustrative, not market data.
``validated_cohort.json`` is stored ml-engine output (backend blocks null);
the other two are served reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from .config import COST_MODEL_VERSION, FEATURE_VERSION, PROCEDURE_ID, config_sha256
from .contract import (
    FAMILY_LABELS,
    HORIZON_LABELS,
    REPORT_ENGINE_VERSION,
    SCHEMA_VERSION,
    AsOf,
    Beta,
    Cohort,
    Compliance,
    Coverage,
    Drawdown,
    DrawdownSeries,
    EvidenceTier,
    Fact,
    FactorFamily,
    FactorMetric,
    FactorProfile,
    Fundamentals,
    HorizonOutlook,
    LiveHorizon,
    LiveTrackRecord,
    ModelCard,
    ModelCardHorizon,
    Narrative,
    NarrativeSection,
    PiotroskiCheck,
    Piotroski,
    PipelineStage,
    Provenance,
    Quality,
    ReasonCode,
    ResearchReport,
    ReturnRange,
    Risk,
    ScoreValue,
    Snapshot,
    SourceStatus,
    Source,
    Staleness,
    Valuation,
    VarBacktest,
    VarRow,
    iter_facts,
    outlook_event,
)
from .formatting import make_fact, range_text

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "docs" / "research" / "contract"
SCHEMA_PATH = CONTRACT_DIR / "research_report.v1.schema.json"
FIXTURE_DIR = CONTRACT_DIR / "fixtures"

MARKET_DATE = date(2026, 10, 9)  # a Friday
COMPUTED_AT = datetime(2026, 10, 9, 14, 20, tzinfo=timezone.utc)  # 19:50 IST
FUND_FETCHED_AT = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
AS_OF_DISPLAY = "9 Oct 2026"

# Exact 6.4 texts (backend templates.py holds the canonical copies).
TIER_TEXT: dict[str, str] = {
    "validated_edge": "This method met all of its pre-set statistical checks at this horizon. "
    "It is not a forecast for this stock.",
    "weak_evidence": "Testing found some evidence at this horizon, but not enough to show a "
    "stock-level estimate.",
    "no_reliable_edge": "No reliable edge at this horizon: in testing, the model did not rank stocks "
    "better than simple rules with enough confidence, so no stock-level estimate is shown. "
    "This says nothing good or bad about this stock.",
    "out_of_universe": "Outlooks are computed only for the 200 most-traded NSE stocks. "
    "The figures below are descriptive.",
    "unavailable": "The outlook is unavailable for this report.",
}
DISCLAIMER_TEXT = (
    "Nivesh is not registered with SEBI as a research analyst or investment adviser. This stock "
    "report is general, educational information computed from public market data. It is not "
    "investment advice, a research report or a recommendation to buy, sell or hold any security, "
    "and it does not consider your finances or goals. Figures describe the past; statistical "
    "patterns can weaken or vanish. Investments in the securities market are subject to market "
    "risks. Read all related documents carefully before investing."
)
AI_DISCLOSURE = (
    "An AI language model (DeepSeek) turns the computed figures into sentences. It does not "
    "compute or choose any number; an automated checker verifies every sentence, and a fixed "
    "template is shown if the check fails. Only public market data is sent to the AI provider."
)

GIT_SHA = "4f1d2c3b5a6e7f8091a2b3c4d5e6f708192a3b4c"
DATA_SHA256 = "5e8c1f2a" + "9b3d4e6f" * 7
MANIFEST_SHA256 = {21: "a3" * 32, 63: "b7" * 32}

# (feature_id, family, label, unit, decimals, signed, value, pctl)
_FEATURES: tuple[tuple[str, str, str, Any, int, bool, float, float], ...] = (
    ("mom_12_1", "momentum", "Price return from 12 months to 1 month ago", "pct", 1, True, 18.4, 71),
    ("mom_6_1", "momentum", "Price return from 6 months to 1 month ago", "pct", 1, True, 11.2, 66),
    ("mom_3_1", "momentum", "Price return from 3 months to 1 month ago", "pct", 1, True, 7.9, 62),
    ("mom_12_1_vs", "momentum", "12-to-1-month return per unit of volatility", "ratio", 2, True, 0.71, 68),
    ("dist_52wh", "momentum", "Distance from the 52-week high", "pct", 1, True, -7.9, 58),
    ("rev_5", "reversal", "Price return, last 5 trading days", "pct", 1, True, -1.8, 34),
    ("rev_21", "reversal", "Price return, last 21 trading days", "pct", 1, True, -3.1, 29),
    ("vol_21", "risk", "Annualised volatility, last 21 trading days", "pct", 1, False, 22.4, 55),
    ("vol_63", "risk", "Annualised volatility, last 63 trading days", "pct", 1, False, 24.1, 52),
    ("vol_252", "risk", "Annualised volatility, last 252 trading days", "pct", 1, False, 26.3, 49),
    ("beta_252", "risk", "Beta to the average of the 200 most-traded NSE stocks", "ratio", 2, False, 0.94, 47),
    ("idio_vol_63", "risk", "Stock-specific volatility, last 63 trading days", "pct", 1, False, 18.7, 51),
    ("max_ret_21", "risk", "Largest one-day return, last 21 trading days", "pct", 1, True, 3.4, 44),
    ("downside_vol_63", "risk", "Downside volatility, last 63 trading days", "pct", 1, False, 15.2, 50),
    ("log_adv_63", "liquidity", "Median daily value traded, last 63 trading days", "inr_cr", 1, False, 412.6, 81),
    ("amihud_63", "liquidity", "Average price move per ₹100 crore traded", "pct", 2, False, 0.42, 79),
    ("turnover_ratio_21_126", "liquidity", "Recent value traded compared with the 6-month median", "pct", 1, True, 6.3, 61),
    ("ma50_ma200", "trend", "50-day average price above or below the 200-day average", "pct", 1, True, 4.1, 63),
    ("rsi_14", "trend", "Relative strength index, 14 days", "ratio", 0, False, 46.0, 41),
)
_FAMILY_PCTL = {"momentum": 68, "reversal": 31, "risk": 50, "liquidity": 80, "trend": 54}

# Weekly drawdown points (%), oldest first, ending on MARKET_DATE.
_DRAWDOWN_POINTS = (
    -12.4, -10.9, -9.8, -11.6, -14.2, -16.8, -18.6, -15.3, -12.1, -9.4, -7.2, -5.1, -3.8,
    -2.2, 0.0, -1.4, -3.6, -2.9, -0.8, 0.0, -1.9, -4.4, -6.1, -5.3, -6.8, -7.9,
)


def _fact(fid: str, value: float | None, source: Source, *, as_of: date | None = MARKET_DATE,
          reason: ReasonCode | None = None, status: Literal["stale"] | None = None,
          method: str | None = None) -> Fact:
    """Catalogue fact; ``reason`` applies only when the value is missing or the fact is stale."""
    if value is not None and status is None:
        reason = None
    return make_fact(fid, value, source=source, as_of=as_of, reason=reason, status=status, method=method)


def _band(p: float, ref: str = "the 200 most-traded NSE stocks") -> str:
    """7.2 band phrase (fixture narratives only; the backend owns the real one)."""
    if p < 20:
        return f"among the lowest fifth of {ref}"
    if p < 40:
        return f"below the middle of {ref}"
    if p < 60:
        return f"around the middle of {ref}"
    if p < 80:
        return f"above the middle of {ref}"
    return f"among the highest fifth of {ref}"


def _snapshot(close: float, high: float, low: float, turnover_cr: float,
              market_cap: Fact, r_12m: float) -> Snapshot:
    nifty_12m = 8.43
    return Snapshot(
        benchmark_id="NIFTY50_PR",
        last_close=_fact("snapshot.last_close", close, "nse_bhavcopy"),
        day_change_pct=_fact("snapshot.day_change_pct", 1.27, "nse_bhavcopy"),
        r_1m_pct=_fact("snapshot.r_1m_pct", -3.14, "computed"),
        r_3m_pct=_fact("snapshot.r_3m_pct", 4.62, "computed"),
        r_6m_pct=_fact("snapshot.r_6m_pct", 9.85, "computed"),
        r_12m_pct=_fact("snapshot.r_12m_pct", r_12m, "computed"),
        nifty50_r_12m_pct=_fact("snapshot.nifty50_r_12m_pct", nifty_12m, "yfinance"),
        excess_12m_vs_nifty50_pp=_fact(
            "snapshot.excess_12m_vs_nifty50_pp", round(r_12m - nifty_12m, 2), "computed"
        ),
        high_52w=_fact("snapshot.high_52w", high, "computed"),
        low_52w=_fact("snapshot.low_52w", low, "computed"),
        pct_below_52w_high=_fact(
            "snapshot.pct_below_52w_high", round((1 - close / high) * 100, 2), "computed"
        ),
        median_turnover_63d_cr=_fact("snapshot.median_turnover_63d_cr", turnover_cr, "nse_bhavcopy"),
        market_cap_cr=market_cap,
    )


def _outlook(h: int, tier: EvidenceTier, reasons: list[str], *, served: bool,
             in_universe: bool = True, prediction_id: int | None = None,
             cohort: Cohort | None = None) -> HorizonOutlook:
    return HorizonOutlook(
        horizon_days=h,  # type: ignore[arg-type]
        horizon_label=HORIZON_LABELS[h],  # type: ignore[arg-type]
        event=outlook_event(h),
        evidence_tier=tier,
        reason_codes=reasons,
        tier_text=TIER_TEXT[tier] if served else None,
        cohort=cohort,
        procedure_id=PROCEDURE_ID if in_universe else None,
        model_id=f"{PROCEDURE_ID}-h{h}-20260630" if in_universe else None,
        prediction_id=prediction_id if served else None,
    )


def _factor_profile(overrides: dict[str, tuple[float, float]] | None = None,
                    family_pctl: dict[str, float] | None = None) -> FactorProfile:
    """Shared illustrative profile; ``overrides`` maps feature_id -> (value, pctl)."""
    overrides = overrides or {}
    fam_pctl = {**_FAMILY_PCTL, **(family_pctl or {})}
    rows = [(fid, fam, lab, unit, dec, sig, *overrides.get(fid, (val, pct)))
            for fid, fam, lab, unit, dec, sig, val, pct in _FEATURES]
    families = []
    for family, label in FAMILY_LABELS.items():
        metrics = [
            FactorMetric(
                feature_id=fid,
                label=flabel,
                value=make_fact(f"factor.{fid}.value", value, unit, source="computed", as_of=MARKET_DATE,
                                decimals=decimals, signed=signed, label=flabel, method=FEATURE_VERSION),
                pctl=make_fact(f"factor.{fid}.pctl", pctl, "pctl", source="computed", as_of=MARKET_DATE,
                               decimals=0, signed=False,
                               label=f"{flabel}, percentile",
                               method=FEATURE_VERSION),
            )
            for fid, fam, flabel, unit, decimals, signed, value, pctl in rows
            if fam == family
        ]
        families.append(FactorFamily(
            family=family,  # type: ignore[arg-type]
            label=label,
            pctl=_fact(f"factor.{family}.pctl", fam_pctl[family], "computed", method=FEATURE_VERSION),
            metrics=metrics,
        ))
    return FactorProfile(universe_id="NSE_LIQ200", families=families)


def _return_range(h: int, window: int, low: float | None, high: float | None) -> ReturnRange:
    reason: ReasonCode | None = None if low is not None else "insufficient_history"
    low_f = _fact(f"risk.range.{h}.low_pct", low, "computed", reason=reason, method="empirical_rolling_756d")
    high_f = _fact(f"risk.range.{h}.high_pct", high, "computed", reason=reason, method="empirical_rolling_756d")
    return ReturnRange(
        horizon_days=h,  # type: ignore[arg-type]
        low_pct=low_f, high_pct=high_f, window_sessions=window,
        text=range_text(h, window, low_f, high_f), method="empirical_rolling_756d",
    )


def _var_rows() -> list[VarRow]:
    rows = []
    # (level, method, var, cvar, exceptions, expected, kupiec_p, christoffersen_p)
    for level, method, var, cvar, exc, exp, kp, cp in (
        (0.95, "historical_500d", -2.31, -3.18, 13, 12.5, 0.89, 0.41),
        (0.95, "fhs_ewma", -2.18, -2.97, 14, 12.5, 0.67, 0.52),
        (0.99, "historical_500d", -3.92, -4.85, 3, 2.5, 0.76, 0.79),
        (0.99, "fhs_ewma", -3.61, -4.40, 4, 2.5, 0.37, 0.72),
    ):
        base = f"risk.var_1d.{int(level * 100)}.{method}."
        rows.append(VarRow(
            level=level, method=method,  # type: ignore[arg-type]
            var_pct=_fact(base + "var_pct", var, "computed", method=method),
            cvar_pct=_fact(base + "cvar_pct", cvar, "computed", method=method),
            backtest=VarBacktest(window_days=250, exceptions=exc, expected=exp, kupiec_p=kp,
                                 christoffersen_p=cp),
        ))
    return rows


def _risk(*, vol_ewma: float, vol_63: float, vol_252: float, vol_pctl: float, var_ok: bool, max_3y: float | None,
          max_5y: float | None, ranges: list[ReturnRange]) -> Risk:
    no_history: ReasonCode = "insufficient_history"
    start = MARKET_DATE - timedelta(weeks=len(_DRAWDOWN_POINTS) - 1)
    return Risk(
        vol_ewma_ann_pct=_fact("risk.vol_ewma_ann_pct", vol_ewma, "computed", method="ewma_0.94"),
        vol_63d_ann_pct=_fact("risk.vol_63d_ann_pct", vol_63, "computed"),
        vol_252d_ann_pct=_fact("risk.vol_252d_ann_pct", vol_252, "computed"),
        vol_pctl=_fact("risk.vol_pctl", vol_pctl, "computed"),
        beta=Beta(
            benchmark_id="NIFTY50_PR", method="dimson_lag1_daily_252",
            raw=_fact("risk.beta.raw", 0.97, "computed", method="dimson_lag1_daily_252"),
            se=_fact("risk.beta.se", 0.06, "computed", method="dimson_lag1_daily_252"),
            blume_adjusted=_fact("risk.beta.blume_adjusted", 0.98, "computed", method="blume_0.67"),
        ),
        var_status="ok" if var_ok else "backtest_failed",
        var_1d=_var_rows() if var_ok else [],
        drawdown=Drawdown(
            max_1y_pct=_fact("risk.drawdown.max_1y_pct", -18.6, "computed"),
            max_3y_pct=_fact("risk.drawdown.max_3y_pct", max_3y, "computed", reason=no_history),
            max_5y_pct=_fact("risk.drawdown.max_5y_pct", max_5y, "computed", reason=no_history),
            current_pct=_fact("risk.drawdown.current_pct", -7.9, "computed"),
            days_since_peak=_fact("risk.drawdown.days_since_peak", 14, "computed"),
            ulcer_1y=_fact("risk.drawdown.ulcer_1y", 6.2, "computed"),
        ),
        drawdown_series=DrawdownSeries(
            freq="W", unit="pct",
            points=[(start + timedelta(weeks=i), v) for i, v in enumerate(_DRAWDOWN_POINTS)],
        ),
        return_ranges=ranges,
    )


_PIOTROSKI_IDS = ("roa_positive", "cfo_positive", "roa_improving", "accruals", "leverage_down",
                  "liquidity_up", "no_dilution", "gross_margin_up", "asset_turnover_up")


def _fundamentals(*, financial: bool) -> Fundamentals:
    y = "yfinance"
    fetched = FUND_FETCHED_AT.date()
    na: ReasonCode = "not_applicable_financials"
    signals = [PiotroskiCheck(id=sid, value=v)
               for sid, v in zip(_PIOTROSKI_IDS, (1, 1, 1, 0, 1, None, 1, 0, 1))]
    return Fundamentals(
        status="ok", reason=None, source="yfinance", fetched_at=FUND_FETCHED_AT,
        fiscal_period_end=date(2026, 3, 31), point_in_time=False,
        statement_basis="consolidated", is_financial=financial,
        valuation=Valuation(
            pe_ttm=_fact("fund.pe_ttm", 24.6, y, as_of=fetched),
            pb=_fact("fund.pb", 3.8, y, as_of=fetched),
            ev_ebitda=_fact("fund.ev_ebitda", None if financial else 14.2, y, as_of=fetched, reason=na),
            dividend_yield_pct=_fact("fund.dividend_yield_pct", 0.85, y, as_of=fetched),
            pe_sector_pctl=_fact("fund.pe_sector_pctl", 58, "computed", as_of=fetched),
        ),
        quality=Quality(
            roe_pct=_fact("fund.roe_pct", 16.4, y, as_of=fetched),
            operating_margin_pct=_fact("fund.operating_margin_pct", 18.9, y, as_of=fetched),
            debt_to_equity=_fact("fund.debt_to_equity", None if financial else 0.42, y, as_of=fetched,
                                 reason=na),
            cfo_to_pat=_fact("fund.cfo_to_pat", 1.08, y, as_of=fetched),
        ),
        piotroski=Piotroski(
            f_score=_fact("fund.piotroski.f_score", 6, "computed", as_of=fetched),
            max_possible=_fact("fund.piotroski.max_possible", 8, "computed", as_of=fetched),
            signals=signals,
        ),
        altman_z_em=ScoreValue(
            applicable=not financial,
            value=_fact("fund.altman_z_em", None if financial else 5.12, "computed", as_of=fetched,
                        reason=na),
        ),
        beneish_m=ScoreValue(
            applicable=not financial,
            value=_fact("fund.beneish_m", None if financial else -2.41, "computed", as_of=fetched,
                        reason=na),
        ),
    )


def _fundamentals_unavailable() -> Fundamentals:
    why: ReasonCode = "source_unavailable"
    y = "yfinance"

    def na(fid: str, source: Source = y) -> Fact:
        return _fact(fid, None, source, as_of=None, reason=why)

    return Fundamentals(
        status="unavailable", reason=why, source="yfinance", fetched_at=None, fiscal_period_end=None,
        point_in_time=False, statement_basis="unknown", is_financial=None,
        valuation=Valuation(pe_ttm=na("fund.pe_ttm"), pb=na("fund.pb"), ev_ebitda=na("fund.ev_ebitda"),
                            dividend_yield_pct=na("fund.dividend_yield_pct"),
                            pe_sector_pctl=na("fund.pe_sector_pctl", "computed")),
        quality=Quality(roe_pct=na("fund.roe_pct"), operating_margin_pct=na("fund.operating_margin_pct"),
                        debt_to_equity=na("fund.debt_to_equity"), cfo_to_pat=na("fund.cfo_to_pat")),
        piotroski=Piotroski(f_score=na("fund.piotroski.f_score", "computed"),
                            max_possible=na("fund.piotroski.max_possible", "computed"), signals=[]),
        altman_z_em=ScoreValue(applicable=True, value=na("fund.altman_z_em", "computed")),
        beneish_m=ScoreValue(applicable=True, value=na("fund.beneish_m", "computed")),
    )


def _model_card(tier_21: str | None, tier_63: str | None) -> ModelCard:
    return ModelCard(
        procedure_id=PROCEDURE_ID,
        feature_version="fv1",
        universe_id="NSE_LIQ200",
        universe_quality="pit",
        label_definition=(
            "Centred percentile rank of the next 21- or 63-trading-day log price return "
            "(dividends excluded) within the 200 most-traded NSE stocks"
        ),
        data_period="2008-01-01 to 2026-06-30",
        trained_through=date(2026, 6, 30),
        manifest_sha256=MANIFEST_SHA256[21],
        limitations=[
            "Prices exclude dividends.",
            "Fundamentals come from Yahoo Finance and are not point-in-time.",
            "Statistical patterns found in past data can weaken or vanish.",
        ],
        horizons=[
            ModelCardHorizon(horizon_days=21, tier_text=tier_21),
            ModelCardHorizon(horizon_days=63, tier_text=tier_63),
        ],
    )


def _provenance(*, yfinance_ok: bool) -> Provenance:
    return Provenance(
        engine_version=REPORT_ENGINE_VERSION,
        git_sha=GIT_SHA,
        data_snapshot_id=f"snap-{MARKET_DATE:%Y%m%d}-{DATA_SHA256[:8]}",
        data_sha256=DATA_SHA256,
        feature_version="fv1",
        cost_model_version=COST_MODEL_VERSION,
        config_sha256=config_sha256(),
        sources=[
            SourceStatus(id="nse_bhavcopy", last_success=MARKET_DATE, status="ok", note=None),
            SourceStatus(
                id="yfinance",
                last_success=MARKET_DATE if yfinance_ok else date(2026, 10, 8),
                status="ok" if yfinance_ok else "failed",
                note=None if yfinance_ok else "Fundamentals request returned no statements.",
            ),
        ],
    )


def _pipeline(fundamentals_ok: bool) -> list[PipelineStage]:
    stages = ("prices", "universe", "features", "scores", "risk", "fundamentals", "assemble")
    return [
        PipelineStage(stage=s, status="ok", detail=None)  # type: ignore[arg-type]
        if s != "fundamentals" or fundamentals_ok
        else PipelineStage(stage="fundamentals", status="failed", detail="yfinance returned no statements")
        for s in stages
    ]


def _render(raw: str, report: ResearchReport) -> str:
    """Substitute {{id}}, {{id.band}} and {{as_of}} placeholders (fixture narratives)."""
    out = raw.replace("{{as_of}}", AS_OF_DISPLAY)
    for fact in iter_facts(report):
        if fact.display is None:
            continue
        if fact.unit == "pctl" and fact.value is not None:
            out = out.replace("{{" + fact.id + ".band}}", _band(fact.value))
        out = out.replace("{{" + fact.id + "}}", fact.display)
    if "{{" in out:
        raise ValueError(f"unrendered placeholder in fixture narrative: {out}")
    return out


def _facts_hash(report: ResearchReport) -> str:
    rows = [[f.id, f.display] for f in iter_facts(report) if f.status == "ok" and not f.id.startswith("outlook.")]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _narrative(report: ResearchReport, status: Literal["llm_validated", "template"],
               attempts: int, summary: str, sections: dict[str, str]) -> Narrative:
    return Narrative(
        status=status, language="en", summary=_render(summary, report),
        sections=[NarrativeSection(id=k, text=_render(v, report))  # type: ignore[arg-type]
                  for k, v in sections.items()],
        prompt_version="rf-1", validator_version="gv-1", attempts=attempts,
        facts_hash=_facts_hash(report),
    )


def _live_track_record() -> LiveTrackRecord:
    since = date(2026, 7, 6)
    return LiveTrackRecord(visible=False, horizons=[
        LiveHorizon(horizon_days=21, state="collecting", since=since, matured_dates=47,
                    independent_periods=2, min_periods_required=12),
        LiveHorizon(horizon_days=63, state="collecting", since=since, matured_dates=6,
                    independent_periods=0, min_periods_required=12),
    ])


def _compliance() -> Compliance:
    return Compliance(
        mode="unregistered_educational", disclaimer_id="research_v1", disclaimer_text=DISCLAIMER_TEXT,
        ai_disclosure=AI_DISCLOSURE, outlook_display="tier_only", track_record_visible=False,
        lexicon_version="lx-1",
    )


# ── Fixtures ────────────────────────────────────────────────────────────────


def no_edge() -> ResearchReport:
    """Served, in-universe; both horizons no_reliable_edge; LLM narrative; fresh."""
    gates = ["gate_failed:G1", "gate_failed:G2"]
    report = ResearchReport(
        schema_version=SCHEMA_VERSION,
        report_id="3f1c2a9e-5b7d-4e2a-9c1f-0a6b8d4e2f71",  # type: ignore[arg-type]
        engine_version=REPORT_ENGINE_VERSION,
        origin="nightly", status="ok", degraded_reasons=[],
        symbol="DEMOIND", exchange="NSE", isin="INE000D01019",
        company_name="Demo Industries Ltd", sector="Industrials",
        as_of=AsOf(market_date=MARKET_DATE, computed_at=COMPUTED_AT),
        coverage=Coverage(universe_id="NSE_LIQ200", in_universe=True, universe_quality="pit",
                          turnover_rank=37, outlook_eligible=True, reason=None),
        snapshot=_snapshot(2875.40, 3120.55, 2310.10, 412.6,
                           _fact("snapshot.market_cap_cr", 194532, "yfinance", as_of=FUND_FETCHED_AT.date()),
                           14.21),
        outlooks=[
            _outlook(21, "no_reliable_edge", gates, served=True, prediction_id=120481),
            _outlook(63, "no_reliable_edge", gates, served=True, prediction_id=120482),
        ],
        factor_profile=_factor_profile(),
        risk=_risk(vol_ewma=23.8, vol_63=24.1, vol_252=26.3, vol_pctl=52, var_ok=True, max_3y=-27.4, max_5y=-35.2,
                   ranges=[_return_range(21, 756, -6.2, 8.9), _return_range(63, 756, -10.8, 17.3)]),
        fundamentals=_fundamentals(financial=False),
        model_card=_model_card(TIER_TEXT["no_reliable_edge"], TIER_TEXT["no_reliable_edge"]),
        provenance=_provenance(yfinance_ok=True),
        pipeline=_pipeline(True),
        staleness=Staleness(sessions_old=0, state="fresh"),
        live_track_record=_live_track_record(),
        compliance=_compliance(),
    )
    report.narrative = _narrative(
        report, "llm_validated", 1,
        "Demo Industries Ltd last closed at {{snapshot.last_close}} on {{as_of}}. "
        "Its price return over the past year was {{snapshot.r_12m_pct}}, against "
        "{{snapshot.nifty50_r_12m_pct}} for the Nifty 50.",
        {
            "risk": "Annualised volatility (recent-weighted): {{risk.vol_ewma_ann_pct}}. Volatility was "
            "{{risk.vol_pctl.band}}. Largest fall from a peak, last 3 years: {{risk.drawdown.max_3y_pct}}.",
            "factor_profile": "Liquidity was {{factor.liquidity.pctl.band}}. Momentum was "
            "{{factor.momentum.pctl.band}}.",
            "fundamentals": "Price to earnings, trailing 12 months: {{fund.pe_ttm}}. Return on equity: "
            "{{fund.roe_pct}}. Piotroski F-score: {{fund.piotroski.f_score}} of "
            "{{fund.piotroski.max_possible}} available checks.",
        },
    )
    return ResearchReport.model_validate(report.model_dump())


def validated_cohort() -> ResearchReport:
    """Stored ml-engine output: 21d validated_edge with a cohort, 63d weak_evidence; backend blocks null."""
    cohort = Cohort(
        bucket=4,
        frequency=_fact("outlook.21.cohort.frequency", 0.54, "model", method="cohort_calibrator_5bin"),
        ci_low=_fact("outlook.21.cohort.ci_low", 0.52, "model", method="block_bootstrap_2000"),
        ci_high=_fact("outlook.21.cohort.ci_high", 0.56, "model", method="block_bootstrap_2000"),
        cases=_fact("outlook.21.cohort.cases", 9840, "model"),
        period="2023-07-01 to 2026-06-30",
        neutral=False,
    )
    return ResearchReport(
        schema_version=SCHEMA_VERSION,
        report_id="8d2b6f4a-1c3e-4f5a-8b7d-2e9c0a1f3b64",  # type: ignore[arg-type]
        engine_version=REPORT_ENGINE_VERSION,
        origin="nightly", status="ok", degraded_reasons=[],
        symbol="SAMPLEFIN", exchange="NSE", isin="INE000S01016",
        company_name="Sample Finance Ltd", sector="Financial Services",
        as_of=AsOf(market_date=MARKET_DATE, computed_at=COMPUTED_AT),
        coverage=Coverage(universe_id="NSE_LIQ200", in_universe=True, universe_quality="pit",
                          turnover_rank=12, outlook_eligible=True, reason=None),
        snapshot=_snapshot(1642.75, 1788.20, 1290.45, 1218.4,
                           _fact("snapshot.market_cap_cr", 286410, "yfinance", as_of=FUND_FETCHED_AT.date()),
                           19.62),
        outlooks=[
            _outlook(21, "validated_edge", [], served=False, cohort=cohort),
            _outlook(63, "weak_evidence", ["gate_failed:G1"], served=False),
        ],
        factor_profile=_factor_profile(),
        risk=_risk(vol_ewma=23.8, vol_63=24.1, vol_252=26.3, vol_pctl=52, var_ok=True, max_3y=-27.4, max_5y=-35.2,
                   ranges=[_return_range(21, 756, -6.2, 8.9), _return_range(63, 756, -10.8, 17.3)]),
        fundamentals=_fundamentals(financial=True),
        model_card=_model_card(None, None),
        provenance=_provenance(yfinance_ok=True),
        pipeline=_pipeline(True),
    )


def out_of_universe_degraded() -> ResearchReport:
    """Served on-demand report: off-universe, fundamentals unavailable, VaR backtest failed,
    63d range unavailable, degraded, stale by one session."""
    oou = ["not_in_universe"]
    report = ResearchReport(
        schema_version=SCHEMA_VERSION,
        report_id="c7e5a3d1-9f2b-4c6e-a8d0-5b3f1e7a9c22",  # type: ignore[arg-type]
        engine_version=REPORT_ENGINE_VERSION,
        origin="on_demand", status="degraded", degraded_reasons=["fundamentals_unavailable"],
        symbol="SMALLCO", exchange="NSE", isin="INE000M01013",
        company_name="Smallco Industries Ltd", sector=None,
        as_of=AsOf(market_date=MARKET_DATE, computed_at=COMPUTED_AT),
        coverage=Coverage(universe_id="NSE_LIQ200", in_universe=False, universe_quality="pit",
                          turnover_rank=None, outlook_eligible=False, reason="not_in_universe"),
        snapshot=_snapshot(412.35, 455.80, 251.20, 6.8,
                           _fact("snapshot.market_cap_cr", 3184, "yfinance", status="stale",
                                 as_of=date(2026, 9, 18)),
                           18.4),
        outlooks=[
            _outlook(21, "out_of_universe", oou, served=True, in_universe=False),
            _outlook(63, "out_of_universe", oou, served=True, in_universe=False),
        ],
        factor_profile=_factor_profile(
            {"log_adv_63": (6.8, 9), "amihud_63": (3.85, 8), "vol_21": (39.5, 90), "vol_63": (41.0, 91),
             "vol_252": (43.2, 92), "idio_vol_63": (35.1, 93), "downside_vol_63": (28.4, 89)},
            {"risk": 92, "liquidity": 9},
        ),
        risk=_risk(vol_ewma=41.2, vol_63=41.0, vol_252=43.2, vol_pctl=91, var_ok=False, max_3y=None, max_5y=None,
                   ranges=[_return_range(21, 279, -11.4, 14.9), _return_range(63, 237, None, None)]),
        fundamentals=_fundamentals_unavailable(),
        model_card=_model_card(TIER_TEXT["out_of_universe"], TIER_TEXT["out_of_universe"]),
        provenance=_provenance(yfinance_ok=False),
        pipeline=_pipeline(False),
        staleness=Staleness(sessions_old=1, state="stale"),
        live_track_record=_live_track_record(),
        compliance=_compliance(),
    )
    report.narrative = _narrative(
        report, "template", 0,
        "Smallco Industries Ltd last closed at {{snapshot.last_close}} on {{as_of}}. "
        "Price return, last 12 months (dividends excluded): {{snapshot.r_12m_pct}}. "
        "Volatility compared with the 200 most-traded NSE stocks: {{risk.vol_pctl.band}}.",
        {
            "risk": "Annualised volatility (recent-weighted): {{risk.vol_ewma_ann_pct}}. "
            "Low end of this stock's past 21-trading-day returns (10th percentile): {{risk.range.21.low_pct}}. "
            "High end of this stock's past 21-trading-day returns (90th percentile): {{risk.range.21.high_pct}}.",
            "factor_profile": "Momentum compared with the 200 most-traded NSE stocks: "
            "{{factor.momentum.pctl.band}}. Risk compared with the 200 most-traded NSE stocks: "
            "{{factor.risk.pctl.band}}. Liquidity compared with the 200 most-traded NSE stocks: "
            "{{factor.liquidity.pctl.band}}.",
            "fundamentals": "",
        },
    )
    return ResearchReport.model_validate(report.model_dump())


FIXTURES = {
    "no_edge.json": no_edge,
    "validated_cohort.json": validated_cohort,
    "out_of_universe_degraded.json": out_of_universe_degraded,
}


def _dumps(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def render_all() -> dict[Path, bytes]:
    """Every generated file and its exact bytes."""
    out = {SCHEMA_PATH: _dumps(ResearchReport.model_json_schema())}
    for name, build in FIXTURES.items():
        out[FIXTURE_DIR / name] = _dumps(build().model_dump(mode="json"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="fail if any generated file differs")
    args = parser.parse_args(argv)
    stale = []
    for path, data in render_all().items():
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"wrote {path.relative_to(REPO_ROOT)}")
    for path in stale:
        print(f"out of date: {path.relative_to(REPO_ROOT)} (run python -m research.export_contract)",
              file=sys.stderr)
    return 1 if stale else 0

if __name__ == "__main__":
    sys.exit(main())
