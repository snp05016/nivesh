"""GH-646: the multi-asset transaction endpoint and table reject invalid financial rows."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# conftest.py patches heavy modules before any app import — rely on that here.
from models.db_models import Base, PortfolioTransaction, User

_URL = "/portfolio/multi-asset/transaction"


def _payload(user_id, **overrides):
    body = {
        "user_id": user_id,
        "asset_type": "STOCK",
        "symbol": "RELIANCE",
        "transaction_type": "BUY",
        "quantity": 10,
        "price": 2500.0,
        "fees": 20.0,
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize(
    "overrides",
    [
        {"asset_type": "CRYPTO"},
        {"transaction_type": "GIFT"},
        {"quantity": 0},
        {"quantity": -1},
        {"price": -5},
        {"fees": -1},
        {"symbol": ""},
        {"notes": "x" * 501},
    ],
)
def test_rejects_invalid_payload(client, auth_headers, test_user_id, overrides):
    response = client.post(_URL, json=_payload(test_user_id, **overrides), headers=auth_headers)
    assert response.status_code == 422


def test_accepts_valid_lowercase_payload(client, auth_headers, test_user_id):
    response = client.post(
        _URL,
        json=_payload(test_user_id, asset_type="mf", transaction_type="buy", symbol="INF109K01VQ1"),
        headers=auth_headers,
    )
    assert response.status_code == 200
    tx_id = response.json()["transaction_id"]
    assert isinstance(tx_id, int)

    history = client.get(
        f"/portfolio/multi-asset/transactions/{test_user_id}", headers=auth_headers
    )
    assert history.status_code == 200
    row = next(tx for tx in history.json() if tx["id"] == tx_id)
    assert row["asset_type"] == "MF"
    assert row["transaction_type"] == "BUY"


def test_db_check_rejects_negative_quantity():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        user = User(username="ma_tx_user", password_hash="x", display_name="MA")
        session.add(user)
        session.flush()
        session.add(
            PortfolioTransaction(
                user_id=user.id,
                asset_type="STOCK",
                symbol="TCS",
                transaction_type="BUY",
                quantity=-1,
                price=100.0,
                fees=0.0,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
    finally:
        session.close()
        engine.dispose()
