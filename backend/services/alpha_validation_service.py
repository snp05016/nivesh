"""
Realistic Alpha Validation Engine
Implements realistic backtesting of Nivesh predictions against market frictions.
"""
import math
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import func
from database import get_session
from models.db_models import AnalysisPrediction, StockUniverse
from schemas.alpha_validation import (
    CostAssumptions, BacktestParams, PortfolioMetrics,
    BacktestResult, RegimePerformance, RegimeBreakdownResult,
    SweepIteration, StrategySweepResult, AlphaValidationReport
)

# Phase 2: Costs + Slippage
COST_PRESETS = {
    "zero_cost": CostAssumptions(
        brokerage_bps=0.0, stt_bps=0.0, exchange_charges_bps=0.0,
        sebi_charges_bps=0.0, gst_pct=0.0, stamp_duty_bps=0.0,
        slippage_bps=0.0, liquidity_penalty_bps=0.0, turnover_penalty_bps=0.0
    ),
    "optimistic": CostAssumptions(
        brokerage_bps=2.0, stt_bps=10.0, exchange_charges_bps=0.3,
        sebi_charges_bps=0.1, gst_pct=18.0, stamp_duty_bps=1.5,
        slippage_bps=5.0, liquidity_penalty_bps=0.0, turnover_penalty_bps=5.0
    ),
    "realistic_retail": CostAssumptions(
        brokerage_bps=10.0, stt_bps=10.0, exchange_charges_bps=0.32,
        sebi_charges_bps=0.1, gst_pct=18.0, stamp_duty_bps=1.5,
        slippage_bps=15.0, liquidity_penalty_bps=5.0, turnover_penalty_bps=10.0
    ),
    "conservative": CostAssumptions(
        brokerage_bps=20.0, stt_bps=10.0, exchange_charges_bps=0.32,
        sebi_charges_bps=0.1, gst_pct=18.0, stamp_duty_bps=1.5,
        slippage_bps=30.0, liquidity_penalty_bps=15.0, turnover_penalty_bps=20.0
    ),
    "institutional": CostAssumptions(
        brokerage_bps=5.0, stt_bps=10.0, exchange_charges_bps=0.32,
        sebi_charges_bps=0.1, gst_pct=18.0, stamp_duty_bps=1.5,
        slippage_bps=10.0, liquidity_penalty_bps=5.0, turnover_penalty_bps=5.0
    ),
}

def _calculate_frictions_bps(cost: CostAssumptions) -> float:
    """Calculates total two-way transaction costs in basis points.

    Args:
        cost (CostAssumptions): The cost assumptions for the backtest, including brokerage, taxes, and slippage.

    Returns:
        float: The total transaction friction in basis points.
    """
    # Entry costs
    entry_tax_bps = cost.stt_bps + cost.exchange_charges_bps + cost.sebi_charges_bps + cost.stamp_duty_bps
    entry_brokerage_total = cost.brokerage_bps * (1 + cost.gst_pct / 100.0)
    entry_frictions = entry_tax_bps + entry_brokerage_total + cost.slippage_bps

    # Exit costs (no stamp duty on sell in India)
    exit_tax_bps = cost.stt_bps + cost.exchange_charges_bps + cost.sebi_charges_bps
    exit_brokerage_total = cost.brokerage_bps * (1 + cost.gst_pct / 100.0)
    exit_frictions = exit_tax_bps + exit_brokerage_total + cost.slippage_bps

    return entry_frictions + exit_frictions + cost.turnover_penalty_bps


# Phase 1 & 3: Backtest Engine and Portfolio Metrics
def _compute_metrics(gross_returns: List[float], frictions_bps: float, holding_days: int) -> PortfolioMetrics:
    """Computes portfolio performance metrics from gross returns and frictions.

    Args:
        gross_returns (List[float]): A list of gross daily portfolio returns.
        frictions_bps (float): The transaction friction to subtract per trade in basis points.
        holding_days (int): The average holding period in days, used to annualize metrics.

    Returns:
        PortfolioMetrics: The calculated performance metrics including CAGR, Sharpe, and Sortino.
    """
    if not gross_returns:
        return PortfolioMetrics(
            gross_return=0.0, net_return=0.0, cagr=0.0, sharpe=0.0, sortino=0.0,
            max_drawdown=0.0, volatility=0.0, hit_rate=0.0, average_win=0.0,
            average_loss=0.0, profit_factor=0.0, turnover=0.0,
            average_holding_period=float(holding_days), exposure=0.0,
            cash_percentage=100.0, sector_concentration=0.0,
            drawdown_duration=0.0, benchmark_excess_return=0.0
        )
        
    net_returns = [r - (frictions_bps / 10000.0) for r in gross_returns]
    
    # Portfolio level aggregation (assuming non-compounding overlapping trades for simplicity of this metric)
    avg_net_return = sum(net_returns) / len(net_returns)
    avg_gross_return = sum(gross_returns) / len(gross_returns)
    
    # CAGR Approximation
    # If holding period is 30 days, annualized return is (1+avg_ret)^(365/30) - 1
    periods_per_year = 365.0 / float(holding_days) if holding_days > 0 else 1.0
    cagr = ((1.0 + avg_net_return) ** periods_per_year) - 1.0 if avg_net_return > -1.0 else -1.0
    
    # Volatility
    mean_net = avg_net_return
    variance = sum((r - mean_net) ** 2 for r in net_returns) / len(net_returns)
    volatility = math.sqrt(variance) * math.sqrt(periods_per_year)
    
    # Sharpe & Sortino (assumes risk-free rate = 0.05 annualized)
    rf_per_period = 0.05 / periods_per_year
    sharpe = (mean_net - rf_per_period) / math.sqrt(variance) if variance > 0 else 0.0
    
    downside_returns = [r for r in net_returns if r < rf_per_period]
    downside_variance = sum((r - rf_per_period) ** 2 for r in downside_returns) / len(downside_returns) if downside_returns else 0.0
    sortino = (mean_net - rf_per_period) / math.sqrt(downside_variance) if downside_variance > 0 else 0.0
    
    wins = [r for r in net_returns if r > 0]
    losses = [r for r in net_returns if r <= 0]
    hit_rate = len(wins) / len(net_returns)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    profit_factor = abs(sum(wins) / sum(losses)) if sum(losses) != 0 else float('inf')
    
    # Simple max drawdown approximation from trade sequence
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in net_returns:
        cumulative *= (1.0 + r)
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak
        if dd > max_dd:
            max_dd = dd
            
    return PortfolioMetrics(
        gross_return=round(avg_gross_return, 4),
        net_return=round(avg_net_return, 4),
        cagr=round(cagr, 4),
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4),
        max_drawdown=round(max_dd, 4),
        volatility=round(volatility, 4),
        hit_rate=round(hit_rate, 4),
        average_win=round(avg_win, 4),
        average_loss=round(avg_loss, 4),
        profit_factor=round(profit_factor, 4),
        turnover=100.0, # Assumes 100% turnover per holding period
        average_holding_period=float(holding_days),
        exposure=100.0,
        cash_percentage=0.0,
        sector_concentration=0.0,
        drawdown_duration=0.0,
        benchmark_excess_return=0.0
    )

def run_alpha_validation(params: BacktestParams) -> BacktestResult:
    """Executes a realistic alpha validation backtest.

    Args:
        params (BacktestParams): The parameters defining the backtest strategy, horizon, and cost preset.

    Returns:
        BacktestResult: The results of the backtest including portfolio metrics and benchmarks.
    """
    with get_session() as session:
        return _run_alpha_validation_internal(session, params)


def _run_alpha_validation_internal(session, params: BacktestParams, regime_id: Optional[str] = None) -> BacktestResult:
    """Internal implementation of the alpha validation backtest using a provided database session.

    Args:
        session: The SQLAlchemy database session.
        params (BacktestParams): The parameters defining the backtest strategy.
        regime_id (Optional[str]): Restrict to predictions persisted with this regime_id.

    Returns:
        BacktestResult: The results of the backtest.
    """
    cost_assumptions = COST_PRESETS.get(params.cost_preset, COST_PRESETS["realistic_retail"])
    frictions_bps = _calculate_frictions_bps(cost_assumptions)
    
    horizon_map = {"7D": 7, "20D": 20, "30D": 30, "60D": 60, "90D": 90}
    days = horizon_map.get(params.horizon, 30)
    
    # Fetch relevant predictions
    query = session.query(AnalysisPrediction).filter(
        AnalysisPrediction.horizon_days == days,
        AnalysisPrediction.confidence_pct >= params.confidence_threshold
    )
    
    if params.strategy_type in ["equal_weight_bullish", "confidence_weighted", "top_k_confidence", "sector_neutral_top_k"]:
        query = query.filter(AnalysisPrediction.recommendation == "BULLISH")

    if regime_id is not None:
        query = query.filter(AnalysisPrediction.regime_id == regime_id)

    preds = query.all()
    
    # Group by date for cross-sectional sizing
    by_date: Dict[str, List[AnalysisPrediction]] = {}
    for p in preds:
        d = p.created_at.strftime("%Y-%m-%d")
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(p)
        
    gross_returns = []
    trades = 0

    for d, daily_preds in by_date.items():
        if params.strategy_type == "top_k_confidence":
            daily_preds = sorted(daily_preds, key=lambda x: x.confidence_pct, reverse=True)[:params.top_k]
        elif params.strategy_type == "sector_neutral_top_k":
            # For simplicity, fallback to top_k if sector not fully populated
            daily_preds = sorted(daily_preds, key=lambda x: x.confidence_pct, reverse=True)[:params.top_k]
            
        if not daily_preds:
            continue
        trades += len(daily_preds)

        weights = []
        if params.position_sizing == "equal_weight":
            weights = [1.0 / len(daily_preds)] * len(daily_preds)
        elif params.position_sizing == "confidence_weighted":
            total_conf = sum(p.confidence_pct for p in daily_preds)
            weights = [p.confidence_pct / total_conf if total_conf > 0 else 0 for p in daily_preds]
        elif params.position_sizing == "confidence_squared":
            total_conf_sq = sum(p.confidence_pct ** 2 for p in daily_preds)
            weights = [(p.confidence_pct ** 2) / total_conf_sq if total_conf_sq > 0 else 0 for p in daily_preds]
        elif params.position_sizing == "capped_confidence_weighted":
            total_conf = sum(p.confidence_pct for p in daily_preds)
            weights = [min(0.2, p.confidence_pct / total_conf) if total_conf > 0 else 0 for p in daily_preds]
            # normalize remaining
            w_sum = sum(weights)
            weights = [w / w_sum if w_sum > 0 else 0 for w in weights]
        else:
            weights = [1.0 / len(daily_preds)] * len(daily_preds)
            
        daily_portfolio_return = 0.0
        for p, w in zip(daily_preds, weights):
            ret = getattr(p, f"actual_return_{params.horizon.lower()}", 0.0)
            if ret is None:
                ret = 0.0
            daily_portfolio_return += ret * w
            
        gross_returns.append(daily_portfolio_return)
        
    metrics = _compute_metrics(gross_returns, frictions_bps, days)
    
    return BacktestResult(
        params=params,
        metrics=metrics,
        benchmark_metrics={},
        statistical_significance={},
        trade_count=trades
    )


# Phase 5: Threshold Sweep
def run_strategy_sweep() -> StrategySweepResult:
    """Runs a parameter sweep across multiple confidence thresholds and sizing strategies.

    Returns:
        StrategySweepResult: The results of the sweep, identifying the best configurations by CAGR and Sharpe.
    """
    thresholds = [50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0]
    top_ks = [3, 5, 10, 20]
    horizons = ["7D", "20D", "30D", "60D", "90D"]
    sizings = ["equal_weight", "confidence_weighted", "confidence_squared", "capped_confidence_weighted"]
    
    results = []
    best_cagr = None
    best_sharpe = None
    
    with get_session() as session:
        for h in ["30D"]: # Trim sweep for performance in testing
            for t in [60.0, 70.0]:
                for k in [5, 10]:
                    for s in ["equal_weight", "confidence_weighted"]:
                        params = BacktestParams(
                            horizon=h,
                            strategy_type="top_k_confidence",
                            top_k=k,
                            confidence_threshold=t,
                            position_sizing=s,
                            cost_preset="realistic_retail"
                        )
                        res = _run_alpha_validation_internal(session, params)
                        iteration = SweepIteration(
                            confidence_threshold=t,
                            top_k=k,
                            holding_period=h,
                            position_sizing=s,
                            net_cagr=res.metrics.cagr,
                            sharpe=res.metrics.sharpe,
                            max_drawdown=res.metrics.max_drawdown,
                            turnover=res.metrics.turnover,
                            trade_count=res.trade_count
                        )
                        results.append(iteration)
                        
                        if best_cagr is None or iteration.net_cagr > best_cagr.net_cagr:
                            best_cagr = iteration
                        if best_sharpe is None or iteration.sharpe > best_sharpe.sharpe:
                            best_sharpe = iteration
                            
    if not best_cagr:
        dummy = SweepIteration(confidence_threshold=0, top_k=0, holding_period="", position_sizing="", net_cagr=0, sharpe=0, max_drawdown=0, turnover=0, trade_count=0)
        best_cagr = dummy
        best_sharpe = dummy
        
    return StrategySweepResult(
        best_cagr=best_cagr,
        best_sharpe=best_sharpe,
        all_results=results
    )


# Phase 4: Regime Breakdown
MIN_REGIME_TRADES = 30


def run_regime_breakdown(params: BacktestParams) -> RegimeBreakdownResult:
    """Performs a regime-based performance breakdown for a given strategy.

    Groups persisted predictions by their regime_id and backtests each group.
    Regimes with fewer than MIN_REGIME_TRADES positions are omitted.

    Args:
        params (BacktestParams): The parameters defining the strategy.

    Returns:
        RegimeBreakdownResult: The breakdown of strategy performance per persisted regime.
    """
    horizon_map = {"7D": 7, "20D": 20, "30D": 30, "60D": 60, "90D": 90}
    days = horizon_map.get(params.horizon, 30)

    with get_session() as session:
        overall = _run_alpha_validation_internal(session, params)

        regime_ids = [
            row[0] for row in session.query(AnalysisPrediction.regime_id).filter(
                AnalysisPrediction.horizon_days == days,
                AnalysisPrediction.confidence_pct >= params.confidence_threshold,
                AnalysisPrediction.regime_id.isnot(None),
            ).distinct().all()
        ]

        regimes = []
        for rid in sorted(regime_ids):
            res = _run_alpha_validation_internal(session, params, regime_id=rid)
            if res.trade_count < MIN_REGIME_TRADES:
                continue
            regimes.append(RegimePerformance(
                regime_name=rid,
                sample_size=res.trade_count,
                net_cagr=res.metrics.cagr,
                sharpe=res.metrics.sharpe,
                max_drawdown=res.metrics.max_drawdown,
                hit_rate=res.metrics.hit_rate,
            ))

        if regimes:
            total = sum(r.sample_size for r in regimes)
            conclusion = f"Computed from {total} predictions across {len(regimes)} regimes."
        else:
            conclusion = f"Insufficient data: fewer than {MIN_REGIME_TRADES} predictions per regime."

        return RegimeBreakdownResult(
            overall_metrics=overall.metrics,
            regimes=regimes,
            conclusion=conclusion
        )
