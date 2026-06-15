"""
Pydantic schemas for API request/response validation.

ML Hybrid Pipeline — quant fields added to StockAnalysisResponse (2026-06-14).
"""

from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field


class StockAnalysisResponse(BaseModel):
    """Standard response shape for stock analysis endpoints.

    All fields map to AnalysisHistory columns + transient computed fields
    that the iOS client expects in the analysis JSON payload.
    """

    # ── Core identity ──────────────────────────────────────────────────
    ticker: str = Field(..., description="Stock ticker symbol (e.g., RELIANCE)")
    exchange: str = Field(..., description="Exchange (NSE or BSE)")
    company_name: str = Field("", description="Full company name")
    analysis_date: str = Field("", description="ISO date of analysis")

    # ── Signal & confidence ────────────────────────────────────────────
    signal: str = Field(..., description="BUY / SELL / HOLD / ACCUMULATE / REDUCE")
    confidence_pct: int = Field(0, ge=0, le=100, description="AI confidence (0-100)")

    # ── Prices & targets ───────────────────────────────────────────────
    current_price_inr: float = Field(0.0, description="Current market price in INR")
    target_prices: Dict[str, float] = Field(
        default_factory=lambda: {"short_term_3m": 0.0, "medium_term_12m": 0.0, "long_term_36m": 0.0}
    )
    upside_downside_pct: Dict[str, float] = Field(
        default_factory=lambda: {"short_term": 0.0, "medium_term": 0.0, "long_term": 0.0}
    )

    # ── Narrative blocks ───────────────────────────────────────────────
    bull_case: List[str] = Field(default_factory=list)
    bear_case: List[str] = Field(default_factory=list)
    key_risks: List[str] = Field(default_factory=list)
    what_to_watch: List[str] = Field(default_factory=list)
    disclaimer: str = Field("")

    # ── Factor analysis ────────────────────────────────────────────────
    key_factors: Dict[str, str] = Field(default_factory=dict)
    fundamentals_snapshot: Dict[str, Any] = Field(default_factory=dict)
    peer_comparison: List[Dict[str, Any]] = Field(default_factory=list)

    # ── Piotroski ──────────────────────────────────────────────────────
    piotroski_score: Optional[int] = Field(None)
    piotroski_flags: Dict[str, Any] = Field(default_factory=dict)

    # ── Performance history ────────────────────────────────────────────
    price_performance: Optional[Dict[str, Optional[float]]] = Field(None)
    recent_news: List[Dict[str, Any]] = Field(default_factory=list)

    # ── Advisor matrix ─────────────────────────────────────────────────
    advisor_matrix: List[Dict[str, Any]] = Field(default_factory=list)

    # ── Deep scan extras ───────────────────────────────────────────────
    deep_scan_used: bool = Field(False)
    pkscreener_signals: Optional[Any] = Field(None)

    # ── Extreme scan extras ────────────────────────────────────────────
    extreme_thesis: List[str] = Field(default_factory=list)
    extreme_factor_bundles: Optional[Dict[str, Any]] = Field(None)

    # ── ML Hybrid Pipeline — quant engine fields (added 2026-06-14) ───
    market_regime: str = Field("Unknown", description="Market volatility regime")
    calibrated_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Calibrated confidence score (0.0-1.0)")
    confidence_math_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Deterministic confidence math components from the quant engine",
    )
    conformal_target_upper_3m: Optional[float] = Field(None, description="3-month conformal upper bound")
    conformal_target_lower_3m: Optional[float] = Field(None, description="3-month conformal lower bound")
    quantitative_drivers: Dict[str, float] = Field(
        default_factory=dict, description="SHAP-style feature importance drivers"
    )
    tail_risk_flags: Dict[str, bool] = Field(
        default_factory=dict, description="Tail risk flags (e.g., high pledge danger)"
    )

    # ── Metadata ───────────────────────────────────────────────────────
    scan_type: str = Field("standard")
    analysis_checkpoints: Optional[List[Dict[str, Any]]] = Field(None)

    class Config:
        extra = "allow"
