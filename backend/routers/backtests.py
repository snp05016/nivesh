from fastapi import APIRouter, Depends, HTTPException
from schemas.alpha_validation import (
    BacktestParams, BacktestResult, RegimeBreakdownResult,
    StrategySweepResult, CostAssumptions,
    CostPresetResult, CostSensitivityResponse
)
from services.alpha_validation_service import (
    run_alpha_validation, run_strategy_sweep, run_regime_breakdown
)

router = APIRouter()

@router.post("/alpha-validation", response_model=BacktestResult)
def backtest_alpha_validation(params: BacktestParams):
    """
    Run the Realistic Alpha Validation Engine over historical predictions.
    """
    try:
        return run_alpha_validation(params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/strategy-sweep", response_model=StrategySweepResult)
def backtest_strategy_sweep():
    """
    Sweep across parameters (confidence, holding period, position sizing, top_k)
    to find the optimal robust strategy.
    """
    try:
        return run_strategy_sweep()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/regime-breakdown", response_model=RegimeBreakdownResult)
def backtest_regime_breakdown(params: BacktestParams):
    """
    Slice backtest results by market regimes (bull vs bear vs choppy).
    """
    try:
        return run_regime_breakdown(params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cost-sensitivity", response_model=CostSensitivityResponse)
def backtest_cost_sensitivity():
    """
    Check alpha degradation across 'zero_cost', 'optimistic', 'realistic_retail',
    'institutional', and 'conservative' cost assumptions.
    """
    results = {}
    presets: list[str] = ["zero_cost", "optimistic", "realistic_retail", "conservative", "institutional"]
    for preset in presets:
        params = BacktestParams(cost_preset=preset, strategy_type="top_k_confidence", top_k=10)  # type: ignore[arg-type]
        try:
            res = run_alpha_validation(params)
            results[preset] = CostPresetResult(
                cagr=res.metrics.cagr,
                sharpe=res.metrics.sharpe,
                max_drawdown=res.metrics.max_drawdown,
                net_return=res.metrics.net_return,
                gross_return=res.metrics.gross_return,
                turnover=res.metrics.turnover,
            )
        except Exception as e:
            results[preset] = CostPresetResult(error=str(e))

    return CostSensitivityResponse(presets=results)
