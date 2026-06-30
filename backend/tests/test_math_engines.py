import pytest
from app.engines.altman import altman_z_score
from app.engines.dupont import dupont_analysis

def test_altman_z_score_healthy():
    data = {
        "working_capital": 1000,
        "total_assets": 2000,
        "retained_earnings": 500,
        "ebit": 300,
        "market_value_equity": 1500,
        "total_liabilities": 800,
        "sales": 2500
    }
    # A = WC/TA = 1000/2000 = 0.5
    # B = RE/TA = 500/2000 = 0.25
    # C = EBIT/TA = 300/2000 = 0.15
    # D = MVE/TL = 1500/800 = 1.875
    # E = S/TA = 2500/2000 = 1.25
    # Z-Score = 1.2*0.5 + 1.4*0.25 + 3.3*0.15 + 0.6*1.875 + 1.0*1.25 = 0.6 + 0.35 + 0.495 + 1.125 + 1.25 = 3.82
    
    result = altman_z_score(data)
    assert 'score' in result
    assert result['score'] > 2.99 # Indicates healthy zone

def test_altman_z_score_distressed():
    data = {
        "working_capital": -500,
        "total_assets": 2000,
        "retained_earnings": -100,
        "ebit": -50,
        "market_value_equity": 200,
        "total_liabilities": 1800,
        "sales": 500
    }
    # Should result in a low Z-score
    result = altman_z_score(data)
    assert 'score' in result
    assert result['score'] < 1.8 # Indicates distress zone

def test_dupont_analysis_standard():
    data = {
        "net_income": 100,
        "sales": 1000,
        "total_assets": 2000,
        "shareholder_equity": 500
    }
    # Net Profit Margin = 100 / 1000 = 0.1
    # Asset Turnover = 1000 / 2000 = 0.5
    # Equity Multiplier = 2000 / 500 = 4.0
    # ROE = 0.1 * 0.5 * 4.0 = 0.2
    
    result = dupont_analysis(data)
    
    assert 'roe' in result
    assert 'net_profit_margin' in result
    assert 'asset_turnover' in result
    assert 'equity_multiplier' in result
    
    assert result['roe'] == pytest.approx(0.2)
    assert result['net_profit_margin'] == pytest.approx(0.1)
    assert result['asset_turnover'] == pytest.approx(0.5)
    assert result['equity_multiplier'] == pytest.approx(4.0)

def test_dupont_analysis_zero_equity():
    data = {
        "net_income": 100,
        "sales": 1000,
        "total_assets": 2000,
        "shareholder_equity": 0
    }
    # Should handle division by zero safely if implemented correctly
    with pytest.raises(Exception):
        dupont_analysis(data)
