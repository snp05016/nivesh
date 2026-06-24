import pytest
from schemas.alpha_validation import CostAssumptions, BacktestParams
from services.alpha_validation_service import _calculate_frictions_bps, _compute_metrics

def test_calculate_frictions_zero():
    cost = CostAssumptions(
        brokerage_bps=0.0, stt_bps=0.0, exchange_charges_bps=0.0,
        sebi_charges_bps=0.0, gst_pct=0.0, stamp_duty_bps=0.0,
        slippage_bps=0.0, liquidity_penalty_bps=0.0, turnover_penalty_bps=0.0
    )
    assert _calculate_frictions_bps(cost) == 0.0

def test_calculate_frictions_retail():
    cost = CostAssumptions(
        brokerage_bps=10.0, stt_bps=10.0, exchange_charges_bps=0.32,
        sebi_charges_bps=0.1, gst_pct=18.0, stamp_duty_bps=1.5,
        slippage_bps=15.0, liquidity_penalty_bps=5.0, turnover_penalty_bps=10.0
    )
    
    # Entry = 10 + 0.32 + 0.1 + 1.5 + (10 * 1.18) + 15 = 11.92 + 11.8 + 15 = 38.72
    # Exit = 10 + 0.32 + 0.1 + (10 * 1.18) + 15 = 10.42 + 11.8 + 15 = 37.22
    # Turnover = 10
    # Total = 38.72 + 37.22 + 10 = 85.94
    expected = 85.94
    assert abs(_calculate_frictions_bps(cost) - expected) < 0.01

def test_compute_metrics_positive_returns():
    gross = [0.05, 0.10, 0.15]
    frictions = 100.0 # 100 bps = 1%
    metrics = _compute_metrics(gross, frictions, holding_days=30)
    
    # avg gross = 0.10
    # net returns = [0.04, 0.09, 0.14] -> avg net = 0.09
    assert abs(metrics.gross_return - 0.10) < 0.001
    assert abs(metrics.net_return - 0.09) < 0.001
    assert metrics.hit_rate == 1.0
    assert metrics.average_loss == 0.0
    assert metrics.profit_factor == float('inf')

def test_compute_metrics_mixed_returns():
    gross = [0.05, -0.05, 0.0]
    frictions = 50.0 # 50 bps = 0.5%
    metrics = _compute_metrics(gross, frictions, holding_days=30)
    
    # avg gross = 0.0
    # net returns = [0.045, -0.055, -0.005] -> avg net = -0.005
    assert abs(metrics.gross_return - 0.0) < 0.001
    assert abs(metrics.net_return - -0.005) < 0.001
    assert abs(metrics.hit_rate - 0.3333) < 0.01
    
def test_compute_metrics_max_drawdown():
    gross = [0.10, -0.20, 0.30]
    metrics = _compute_metrics(gross, 0.0, holding_days=30)
    
    # 1 * 1.1 = 1.1
    # 1.1 * 0.8 = 0.88 -> DD = (1.1 - 0.88)/1.1 = 0.20
    # 0.88 * 1.3 = 1.144
    assert abs(metrics.max_drawdown - 0.20) < 0.001
