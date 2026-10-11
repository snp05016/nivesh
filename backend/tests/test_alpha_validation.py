import math
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, AnalysisPrediction
from schemas.alpha_validation import CostAssumptions, BacktestParams, BacktestResult
from services import alpha_validation_service as svc
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

    # GST = (10 + 0.32 + 0.1) * 0.18 = 1.8756 per side
    # Side = 10 + 10 + 0.32 + 0.1 + 1.8756 + 15 = 37.2956
    # Entry = 37.2956 + 1.5 stamp duty = 38.7956; Exit = 37.2956 (no DP charge set)
    # Total = 38.7956 + 37.2956 + 5 liquidity + 10 turnover = 91.0912
    expected = 91.0912
    assert abs(_calculate_frictions_bps(cost) - expected) < 0.01


def test_calculate_frictions_includes_liquidity_penalty_and_dp_charge():
    base = CostAssumptions(brokerage_bps=10.0, stt_bps=10.0, slippage_bps=15.0)
    with_liquidity = base.model_copy(update={"liquidity_penalty_bps": 5.0})
    with_dp = base.model_copy(update={"dp_charge_bps": 1.6})

    assert abs(_calculate_frictions_bps(with_liquidity) - _calculate_frictions_bps(base) - 5.0) < 1e-9
    assert abs(_calculate_frictions_bps(with_dp) - _calculate_frictions_bps(base) - 1.6) < 1e-9


def test_cost_presets_charge_dp_and_stcg():
    for name, preset in svc.COST_PRESETS.items():
        if name == "zero_cost":
            assert preset.dp_charge_bps == 0.0 and preset.stcg_tax_pct == 0.0
        else:
            assert preset.dp_charge_bps > 0.0
            assert preset.stcg_tax_pct == 20.0

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


def test_compute_metrics_taxes_only_profitable_cohorts():
    assert abs(_compute_metrics([0.10], 0.0, 30, stcg_tax_pct=20.0).net_return - 0.08) < 1e-9
    assert abs(_compute_metrics([-0.10], 0.0, 30, stcg_tax_pct=20.0).net_return - -0.10) < 1e-9


def test_compute_metrics_annualizes_sharpe_like_volatility():
    gross = [0.05, 0.10, 0.15]
    metrics = _compute_metrics(gross, 0.0, holding_days=30)

    ppy = 365.0 / 30
    std = math.sqrt(sum((r - 0.10) ** 2 for r in gross) / 3)
    assert abs(metrics.volatility - std * math.sqrt(ppy)) < 1e-4
    assert abs(metrics.sharpe - (0.10 - 0.05 / ppy) / std * math.sqrt(ppy)) < 1e-4
    # Three non-overlapping 30-day cohorts compound over 90 days.
    growth = 1.05 * 1.10 * 1.15
    assert abs(metrics.cagr - (growth ** (365.0 / 90) - 1.0)) < 1e-4


# ── Horizon validation ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("horizon", ["20D", "20d", "60D", "60d", "15d"])
def test_untracked_horizons_rejected(horizon):
    with pytest.raises(ValidationError, match="Unsupported horizon"):
        BacktestParams(horizon=horizon)


@pytest.mark.parametrize("horizon,expected", [("7d", "7D"), ("30D", "30D"), ("90d", "90D")])
def test_tracked_horizons_normalized(horizon, expected):
    assert BacktestParams(horizon=horizon).horizon == expected


# ── Backtest over persisted predictions ───────────────────────────────────────

@pytest.fixture()
def TestSession():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, autocommit=False)
    engine.dispose()


@pytest.fixture()
def patched_session(TestSession):
    @contextmanager
    def _test_get_session():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with patch("services.alpha_validation_service.get_session", _test_get_session):
        yield TestSession


def _seed(TestSession, rows):
    """rows: iterable of (day_offset, symbol, actual_return_30d, actual_return_7d)."""
    session = TestSession()
    base = datetime(2026, 1, 1, 10, 0)
    for day, symbol, r30, r7 in rows:
        session.add(AnalysisPrediction(
            symbol=symbol,
            created_at=base + timedelta(days=day),
            horizon_days=20,  # ML label horizon: unrelated to which outcome column is backtested
            recommendation="BULLISH",
            confidence_pct=70,
            actual_return_30d=r30,
            actual_return_7d=r7,
        ))
    session.commit()
    session.close()


def _equal_top10(horizon="30D"):
    return BacktestParams(horizon=horizon, strategy_type="top_k_confidence", top_k=10,
                          confidence_threshold=50.0, position_sizing="equal_weight",
                          cost_preset="realistic_retail")


def test_golden_net_return_after_costs_and_tax(patched_session):
    gross = [0.05, -0.03, 0.02, 0.08, -0.01, 0.04, 0.00, -0.06, 0.03, 0.07]
    _seed(patched_session, [(31 * i, f"SYM{i}.NS", r, None) for i, r in enumerate(gross)])

    result = svc.run_alpha_validation(_equal_top10())

    friction = _calculate_frictions_bps(svc.COST_PRESETS["realistic_retail"]) / 1e4
    after_costs = [r - friction for r in gross]
    net = [n - 0.20 * max(n, 0.0) for n in after_costs]
    assert result.status == "ok"
    assert result.cohorts_used == 10
    assert result.matured_trades == 10
    assert result.trade_count == 10
    assert abs(result.metrics.gross_return - sum(gross) / 10) < 1e-4
    assert abs(result.metrics.net_return - sum(net) / 10) < 1e-4
    assert abs(result.metrics.cagr - (math.prod(1 + n for n in net) ** (365.0 / 300) - 1)) < 1e-4


def test_unmatured_rows_are_excluded(patched_session):
    _seed(patched_session, [
        (0, "A.NS", 0.04, None),
        (40, "B.NS", 0.02, None),
        (80, "C.NS", None, None),   # 30-day outcome not recorded yet
        (120, "D.NS", None, None),
    ])

    result = svc.run_alpha_validation(_equal_top10())

    assert result.matured_trades == 2
    assert result.cohorts_used == 2
    assert abs(result.metrics.gross_return - 0.03) < 1e-4


def test_all_unmatured_is_insufficient_data(patched_session):
    _seed(patched_session, [(i, f"SYM{i}.NS", None, None) for i in range(5)])

    result = svc.run_alpha_validation(_equal_top10())

    assert result.status == "insufficient_data"
    assert result.matured_trades == 0
    assert result.cohorts_used == 0
    assert result.metrics.cagr == 0.0
    assert result.metrics.net_return == 0.0


def test_overlapping_daily_cohorts_collapse(patched_session):
    _seed(patched_session, [(i, f"SYM{i}.NS", 0.01 * i, 0.01) for i in range(10)])

    res_30 = svc.run_alpha_validation(_equal_top10())
    res_7 = svc.run_alpha_validation(_equal_top10("7D"))

    # Ten consecutive signal days fit inside one 30-day holding window ...
    assert res_30.cohorts_used == 1
    assert res_30.trade_count == 10
    assert abs(res_30.metrics.gross_return - 0.0) < 1e-4  # only the day-0 cohort is held
    # ... and inside two 7-day windows (day 0 and day 7).
    assert res_7.cohorts_used == 2


def test_duplicate_same_day_analyses_count_once(patched_session):
    _seed(patched_session, [(0, "RELIANCE.NS", 0.05, None), (0, "RELIANCE.NS", 0.05, None)])

    result = svc.run_alpha_validation(_equal_top10())

    assert result.matured_trades == 1
    assert result.trade_count == 1


# ── Cost-sensitivity route ─────────────────────────────────────────────────────

def test_cost_sensitivity_reports_insufficient_data(client, auth_headers):
    empty = BacktestResult(
        params=BacktestParams(), metrics=_compute_metrics([], 0.0, 30),
        benchmark_metrics={}, statistical_significance={}, trade_count=0,
        status="insufficient_data", matured_trades=0, cohorts_used=0,
    )
    with patch("routers.backtests.run_alpha_validation", return_value=empty):
        resp = client.get("/api/v1/backtests/cost-sensitivity", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "insufficient_data"
    assert body["warning"]
