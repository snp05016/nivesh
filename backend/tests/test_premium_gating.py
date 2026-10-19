"""Growth cluster: every PRO route answers 402 to a fresh free user (the beta comp is off)."""
from uuid import uuid4

import pytest

PREMIUM_ROUTES = {
    "/api/v1/market/sector-rotation": "sector_rotation",
    "/api/v1/options/payoff": "ideas_for_profit",
    "/api/v1/analysis/backtest": "technical_picks",
    "/analysis/backtest": "technical_picks",
}

_PAYOFF = {"spot_price": 100.0, "legs": [{"type": "CALL", "position": "LONG", "strike": 100.0, "premium": 5.0}]}
_BACKTEST = {"ticker": "TCS.NS", "strategy_id": "sma_crossover", "years": 1}
_BODIES = {"/api/v1/options/payoff": _PAYOFF, "/api/v1/analysis/backtest": _BACKTEST, "/analysis/backtest": _BACKTEST}


def _free_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"gate_{uuid4().hex[:12]}", password_hash="x", display_name="Gating Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


@pytest.mark.parametrize("path", sorted(PREMIUM_ROUTES))
def test_free_user_gets_402(client, path):
    headers = _free_user_headers()
    if path == "/api/v1/market/sector-rotation":
        resp = client.get(path, headers=headers)
    else:
        resp = client.post(path, json=_BODIES[path], headers=headers)
    assert resp.status_code == 402, resp.text
    detail = resp.json()["detail"]
    assert detail["required_tier"] == "pro" and detail["current_tier"] == "free"
    assert PREMIUM_ROUTES[path] in detail["message"]


@pytest.mark.parametrize("path", sorted(PREMIUM_ROUTES))
def test_anonymous_is_rejected(client, path):
    resp = client.get(path) if path == "/api/v1/market/sector-rotation" else client.post(path, json={})
    assert resp.status_code in (401, 403)
