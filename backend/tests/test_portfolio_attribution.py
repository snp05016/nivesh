"""Sector attribution is in percentage points of the invested base (MATH-15).

Pure function, no DB or network.
"""
import pytest

from services.portfolio_service import compute_sector_attribution


def _by_sector(result: dict) -> dict:
    return {s["sector"]: s for s in result["sectors"]}


def test_contributions_keep_sign_and_sum_to_portfolio_return():
    # IT +10,000 and Banking -30,000 on a 2,00,000 base: total P&L is negative,
    # yet the winning sector must still show a positive contribution.
    result = compute_sector_attribution([
        ("IT", 100_000.0, 110_000.0),
        ("Banking", 100_000.0, 70_000.0),
    ])
    sectors = _by_sector(result)

    assert sectors["IT"]["contribution_pp"] == pytest.approx(5.0)
    assert sectors["Banking"]["contribution_pp"] == pytest.approx(-15.0)
    assert sectors["IT"]["contribution_to_total_pnl_pct"] == pytest.approx(5.0)
    assert result["portfolio_return_pct"] == pytest.approx(-10.0)
    assert sum(s["contribution_pp"] for s in result["sectors"]) == pytest.approx(result["portfolio_return_pct"])
    assert sectors["IT"]["sector_return_pct"] == pytest.approx(10.0)
    assert sectors["Banking"]["sector_return_pct"] == pytest.approx(-30.0)
    # Sorted by absolute contribution, largest first.
    assert [s["sector"] for s in result["sectors"]] == ["Banking", "IT"]


def test_near_zero_total_pnl_does_not_explode():
    result = compute_sector_attribution([
        ("IT", 100_000.0, 150_000.0),
        ("Banking", 100_000.0, 51_000.0),
    ])
    sectors = _by_sector(result)
    assert sectors["IT"]["contribution_pp"] == pytest.approx(25.0)
    assert sectors["Banking"]["contribution_pp"] == pytest.approx(-24.5)


def test_rows_of_one_sector_are_aggregated():
    result = compute_sector_attribution([
        ("IT", 50_000.0, 55_000.0),
        ("IT", 50_000.0, 45_000.0),
    ])
    assert len(result["sectors"]) == 1
    assert result["sectors"][0]["total_pnl"] == pytest.approx(0.0)
    assert result["sectors"][0]["weight_pct"] == pytest.approx(100.0)


def test_zero_invested_and_empty_inputs():
    assert compute_sector_attribution([]) == {"sectors": [], "portfolio_return_pct": 0.0}
    result = compute_sector_attribution([("Unknown", 0.0, 0.0)])
    assert result["portfolio_return_pct"] == 0.0
    assert result["sectors"][0]["contribution_pp"] == 0.0
    assert result["sectors"][0]["sector_return_pct"] == 0.0
