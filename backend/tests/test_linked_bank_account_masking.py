"""GH-671: /api/finance/linked-bank-accounts accepts only masked account numbers,
and a duplicate mask is a 409, not an IntegrityError 500."""
from __future__ import annotations

from uuid import uuid4

_URL = "/api/finance/linked-bank-accounts"


def _new_user_headers() -> dict:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"mask_{uuid4().hex[:12]}", password_hash="x", display_name="Mask Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_rejects_unmasked_account_number(client):
    headers = _new_user_headers()
    for raw in ("123456789012345678", "1234", "XXXX12345", "XXXXABCD"):
        resp = client.post(_URL, json={"bank_name": "HDFC", "masked_account_number": raw}, headers=headers)
        assert resp.status_code == 422, raw
    assert client.get(_URL, headers=headers).json() == []


def test_accepts_masked_number(client):
    headers = _new_user_headers()
    resp = client.post(_URL, json={"bank_name": "HDFC", "masked_account_number": "XXXX1234"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["masked_account_number"] == "XXXX1234"


def test_duplicate_mask_returns_409(client):
    headers = _new_user_headers()
    body = {"bank_name": "HDFC", "masked_account_number": "****5678"}
    assert client.post(_URL, json=body, headers=headers).status_code == 200
    resp = client.post(_URL, json=body, headers=headers)
    assert resp.status_code == 409
    assert "already linked" in resp.json()["detail"]
