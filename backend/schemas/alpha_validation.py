from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any


class CostAssumptions(BaseModel):
    brokerage_bps: float = 0.0
    stt_bps: float = 0.0
    exchange_charges_bps: float = 0.0
    sebi_charges_bps: float = 0.0
    gst_pct: float = 0.0
    stamp_duty_bps: float = 0.0
    slippage_bps: float = 0.0
    liquidity_penalty_bps: float = 0.0
    turnover_penalty_bps: float = 0.0


class BacktestParams(BaseModel):
    horizon: Literal["7D", "20D", "30D", "60D", "90D"] = "30D"
    strategy_type: Literal[
        "equal_weight_bullish",
        "confidence_weighted",
        "top_k_confidence",
        "sector_neutral_top_k",
        "long_short",
        "cash_filter"
    ] = "confidence_weighted"
    top_k: int = 10
    confidence_threshold: float = 50.0
    position_sizing: Literal[
        "equal_weight",
        "confidence_weighted",
        "confidence_squared",
        "capped_confidence_weighted"
    ] = "confidence_weighted"
    cost_preset: Literal["zero_cost", "optimistic", "realistic_retail", "conservative", "institutional"] = "realistic_retail"


class PortfolioMetrics(BaseModel):
    gross_return: float
    net_return: float
    cagr: float
    sharpe: float
    sortino: float
    max_drawdown: float
    volatility: float
    hit_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    turnover: float
    average_holding_period: float
    exposure: float
    cash_percentage: float
    sector_concentration: float
    drawdown_duration: float
    benchmark_excess_return: float


class BacktestResult(BaseModel):
    params: BacktestParams
    metrics: PortfolioMetrics
    benchmark_metrics: Dict[str, Any]
    statistical_significance: Dict[str, Any]


class RegimePerformance(BaseModel):
    regime_name: str
    sample_size: int
    net_cagr: float
    sharpe: float
    max_drawdown: float
    hit_rate: float


class RegimeBreakdownResult(BaseModel):
    overall_metrics: PortfolioMetrics
    regimes: List[RegimePerformance]
    conclusion: str


class SweepIteration(BaseModel):
    confidence_threshold: float
    top_k: int
    holding_period: str
    position_sizing: str
    net_cagr: float
    sharpe: float
    max_drawdown: float
    turnover: float
    trade_count: int


class StrategySweepResult(BaseModel):
    best_cagr: SweepIteration
    best_sharpe: SweepIteration
    all_results: List[SweepIteration]


class CostPresetResult(BaseModel):
    cagr: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    net_return: Optional[float] = None
    gross_return: Optional[float] = None
    turnover: Optional[float] = None
    error: Optional[str] = None


class CostSensitivityResponse(BaseModel):
    presets: Dict[str, CostPresetResult]
    status: str = "ready"
    warning: Optional[str] = None


class AlphaValidationReport(BaseModel):
    has_alpha_before_costs: bool
    survives_retail_costs: bool
    survives_conservative_costs: bool
    best_strategy: str
    best_confidence_threshold: float
    best_holding_period: str
    confidence_improves_sizing: bool
    survives_regime_shifts: bool
    is_statistically_significant: bool
    verdict: Literal["DEPLOY", "PAPER_TRADE", "REJECT"]
    baseline_comparison: Dict[str, PortfolioMetrics]
