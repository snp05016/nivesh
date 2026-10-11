"""AUTH-10 / GH-627: GET /api/v1/earnings/alerts needs a bearer token and only
returns the caller's own alerts, whatever ?user_id= says."""
from uuid import uuid4

_URL = "/api/v1/earnings/alerts"


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"ea_{uuid4().hex[:12]}", password_hash="x", display_name="Earnings Alert Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_anonymous_get_is_401(client):
    assert client.get(_URL).status_code == 401
    assert client.get(_URL, params={"user_id": 1}).status_code == 401


def test_get_returns_only_callers_alerts(client):
    a_id, a_headers = _new_user()
    b_id, b_headers = _new_user()
    for uid, headers, ticker in ((a_id, a_headers, "TCS"), (b_id, b_headers, "INFY")):
        resp = client.post(_URL, json={"user_id": uid, "ticker": ticker, "earnings_date": "2026-11-15"}, headers=headers)
        assert resp.status_code == 200, resp.text

    for params in ({}, {"user_id": a_id}, {"user_id": 0}):
        resp = client.get(_URL, params=params, headers=b_headers)
        assert resp.status_code == 200, resp.text
        alerts = resp.json()["alerts"]
        assert [a["user_id"] for a in alerts] == [b_id]
        assert alerts[0]["ticker"] == "INFY"
