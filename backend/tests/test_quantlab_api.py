import pytest

def test_quantlab_ml_signal(client, auth_headers):
    response = client.get("/api/v1/stocks/RELIANCE.NS/ml-signal", headers=auth_headers)
    assert response.status_code == 200

def test_quantlab_calibration(client, admin_headers):
    response = client.get("/api/v1/predictions/calibration?horizon=30d", headers=admin_headers)
    assert response.status_code == 200

def test_quantlab_pillar_attribution(client, admin_headers):
    response = client.get("/api/v1/predictions/pillar-attribution?horizon=30d", headers=admin_headers)
    assert response.status_code == 200

def test_quantlab_model_versions(client, admin_headers):
    response = client.get("/api/v1/predictions/model-versions?horizon=30d", headers=admin_headers)
    assert response.status_code == 200

def test_quantlab_alpha_validation(client, auth_headers):
    response = client.post("/api/v1/backtests/alpha-validation", json={}, headers=auth_headers)
    assert response.status_code == 200

def test_quantlab_strategy_sweep(client, auth_headers):
    response = client.get("/api/v1/backtests/strategy-sweep", headers=auth_headers)
    assert response.status_code == 200

def test_quantlab_regime_breakdown(client, auth_headers):
    response = client.post("/api/v1/backtests/regime-breakdown", json={}, headers=auth_headers)
    assert response.status_code == 200

def test_quantlab_cost_sensitivity(client, auth_headers):
    response = client.get("/api/v1/backtests/cost-sensitivity", headers=auth_headers)
    assert response.status_code == 200
