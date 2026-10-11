from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Literal, Any


class CostAssumptions(BaseModel):
    """Cost assumptions for backtesting alpha strategies."""
    brokerage_bps: float = Field(0.0, description="Brokerage in basis points")
    stt_bps: float = Field(0.0, description="Securities Transaction Tax in bps")
    exchange_charges_bps: float = Field(0.0, description="Exchange charges in bps")
    sebi_charges_bps: float = Field(0.0, description="SEBI turnover fees in bps")
    gst_pct: float = Field(0.0, description="GST percentage on charges")
    stamp_duty_bps: float = Field(0.0, description="Stamp duty in bps")
    slippage_bps: float = Field(0.0, description="Assumed execution slippage in bps")
    liquidity_penalty_bps: float = Field(0.0, description="Penalty for illiquid stocks in bps")
    turnover_penalty_bps: float = Field(0.0, description="Penalty for high portfolio turnover in bps")


class BacktestParams(BaseModel):
    """Parameters defining a backtest scenario. Accepts both backend and iOS naming conventions."""
    horizon: str = Field("30D", description="Holding period horizon (7D/7d, 20D/20d, 30D/30d, 60D/60d, 90D/90d)")

    @field_validator("horizon", mode="before")
    @classmethod
    def normalize_horizon(cls, v: str) -> str:
        """Accept both '30d' and '30D' — normalize to uppercase. Reject invalid."""
        VALID = {"7D", "7d", "20D", "20d", "30D", "30d", "60D", "60d", "90D", "90d"}
        if isinstance(v, str) and v not in VALID:
            raise ValueError(f"Invalid horizon '{v}'. Must be one of: {sorted(VALID)}")
        return v.upper() if isinstance(v, str) else v

    strategy_type: str = Field("confidence_weighted", description="Type of strategy to test")

    @field_validator("strategy_type", mode="before")
    @classmethod
    def normalize_strategy_type(cls, v: str) -> str:
        """Accept iOS values like 'momentum' → normalize to 'confidence_weighted'."""
        ios_map = {"momentum": "confidence_weighted"}
        return ios_map.get(v.lower().strip() if isinstance(v, str) else "", v)

    top_k: int = Field(10, description="Top K stocks to hold")
    confidence_threshold: float = Field(50.0, description="Minimum confidence threshold")

    position_sizing: str = Field("confidence_weighted", description="Position sizing method")

    @field_validator("position_sizing", mode="before")
    @classmethod
    def normalize_position_sizing(cls, v: str) -> str:
        """Accept iOS 'equal' → normalize to 'equal_weight'."""
        ios_map = {"equal": "equal_weight"}
        return ios_map.get(v.lower().strip() if isinstance(v, str) else "", v)

    cost_preset: str = Field("realistic_retail", description="Cost assumption preset")

    @field_validator("cost_preset", mode="before")
    @classmethod
    def normalize_cost_preset(cls, v: str) -> str:
        """Accept iOS 'medium' → normalize to 'realistic_retail'."""
        ios_map = {"medium": "realistic_retail", "low": "optimistic", "high": "conservative"}
        return ios_map.get(v.lower().strip() if isinstance(v, str) else "", v)


class PortfolioMetrics(BaseModel):
    """Aggregated metrics for a portfolio backtest."""
    gross_return: float = Field(..., description="Gross return percentage")
    net_return: float = Field(..., description="Net return percentage after costs")
    cagr: float = Field(..., description="Compound Annual Growth Rate")
    sharpe: float = Field(..., description="Sharpe ratio")
    sortino: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown percentage")
    volatility: float = Field(..., description="Annualized volatility")
    hit_rate: float = Field(..., description="Percentage of winning trades")
    average_win: float = Field(..., description="Average return of winning trades")
    average_loss: float = Field(..., description="Average return of losing trades")
    profit_factor: float = Field(..., description="Ratio of gross profit to gross loss")
    turnover: float = Field(..., description="Portfolio turnover percentage")
    average_holding_period: float = Field(..., description="Average holding period in days")
    exposure: float = Field(..., description="Market exposure percentage")
    cash_percentage: float = Field(..., description="Average cash percentage")
    sector_concentration: float = Field(..., description="Sector concentration metric")
    drawdown_duration: float = Field(..., description="Longest drawdown duration in days")
    benchmark_excess_return: float = Field(..., description="Return relative to benchmark")


class BacktestResult(BaseModel):
    """Complete results of a backtest run."""
    params: BacktestParams = Field(..., description="Parameters used for backtest")
    metrics: PortfolioMetrics = Field(..., description="Resulting portfolio metrics")
    benchmark_metrics: Dict[str, Any] = Field(..., description="Metrics of the benchmark")
    statistical_significance: Dict[str, Any] = Field(..., description="Statistical significance metrics")
    trade_count: int = Field(0, description="Number of prediction positions used")


class RegimePerformance(BaseModel):
    """Performance metrics broken down by market regime."""
    regime_name: str = Field(..., description="Name of the market regime")
    sample_size: int = Field(..., description="Number of samples in regime")
    net_cagr: float = Field(..., description="Net CAGR during regime")
    sharpe: float = Field(..., description="Sharpe ratio during regime")
    max_drawdown: float = Field(..., description="Max drawdown during regime")
    hit_rate: float = Field(..., description="Hit rate during regime")


class RegimeBreakdownResult(BaseModel):
    """Backtest results grouped by market regime."""
    overall_metrics: PortfolioMetrics = Field(..., description="Overall metrics across all regimes")
    regimes: List[RegimePerformance] = Field(..., description="Performance per regime")
    conclusion: str = Field(..., description="Conclusion on regime robustness")


class SweepIteration(BaseModel):
    """A single iteration in a parameter sweep."""
    confidence_threshold: float = Field(..., description="Confidence threshold used")
    top_k: int = Field(..., description="Top K stocks parameter")
    holding_period: str = Field(..., description="Holding period horizon")
    position_sizing: str = Field(..., description="Position sizing method")
    net_cagr: float = Field(..., description="Net CAGR achieved")
    sharpe: float = Field(..., description="Sharpe ratio achieved")
    max_drawdown: float = Field(..., description="Maximum drawdown achieved")
    turnover: float = Field(..., description="Turnover percentage")
    trade_count: int = Field(..., description="Number of trades executed")


class StrategySweepResult(BaseModel):
    """Results from a multi-parameter strategy sweep."""
    best_cagr: SweepIteration = Field(..., description="Iteration with best CAGR")
    best_sharpe: SweepIteration = Field(..., description="Iteration with best Sharpe ratio")
    all_results: List[SweepIteration] = Field(..., description="All sweep iterations")


class CostPresetResult(BaseModel):
    """Backtest performance under a specific cost preset."""
    cagr: Optional[float] = Field(None, description="CAGR under this cost preset")
    sharpe: Optional[float] = Field(None, description="Sharpe ratio under this cost preset")
    max_drawdown: Optional[float] = Field(None, description="Max drawdown under this cost preset")
    net_return: Optional[float] = Field(None, description="Net return under this cost preset")
    gross_return: Optional[float] = Field(None, description="Gross return under this cost preset")
    turnover: Optional[float] = Field(None, description="Turnover under this cost preset")
    error: Optional[str] = Field(None, description="Error message if evaluation failed")


class CostSensitivityResponse(BaseModel):
    """Sensitivity analysis across different cost presets."""
    presets: Dict[str, CostPresetResult] = Field(..., description="Results per cost preset")
    status: str = Field("ready", description="Status of the sensitivity analysis")
    warning: Optional[str] = Field(None, description="Warning message if applicable")


class AlphaValidationReport(BaseModel):
    """Comprehensive alpha validation report."""
    has_alpha_before_costs: bool = Field(..., description="Whether strategy has alpha before costs")
    survives_retail_costs: bool = Field(..., description="Whether strategy survives retail costs")
    survives_conservative_costs: bool = Field(..., description="Whether strategy survives conservative costs")
    best_strategy: str = Field(..., description="Best performing strategy type")
    best_confidence_threshold: float = Field(..., description="Optimal confidence threshold")
    best_holding_period: str = Field(..., description="Optimal holding period")
    confidence_improves_sizing: bool = Field(..., description="Whether confidence-weighting improves sizing")
    survives_regime_shifts: bool = Field(..., description="Whether strategy is robust across regimes")
    is_statistically_significant: bool = Field(..., description="Whether performance is statistically significant")
    verdict: Literal["DEPLOY", "PAPER_TRADE", "REJECT"] = Field(..., description="Final validation verdict")
    baseline_comparison: Dict[str, PortfolioMetrics] = Field(..., description="Comparison against baseline strategies")
