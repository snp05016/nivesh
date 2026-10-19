"""GH-646: the multi_asset_transactions table rejects invalid financial rows; its POST
is retired (money C4, 410) and the history GET still serves existing rows."""
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
    [{}, {"asset_type": "mf", "transaction_type": "buy", "symbol": "INF109K01VQ1"}, {"quantity": -1}],
)
def test_post_is_retired_and_writes_nothing(client, auth_headers, test_user_id, overrides):
    """Money C4: portfolio_transactions is the only ledger; the POST answers 410."""
    import database

    with database.get_session() as session:
        before = session.query(PortfolioTransaction).count()
    response = client.post(_URL, json=_payload(test_user_id, **overrides), headers=auth_headers)
    assert response.status_code == 410
    assert response.json()["detail"] == {"code": "ENDPOINT_RETIRED", "message": "Use POST /portfolio/add."}
    with database.get_session() as session:
        assert session.query(PortfolioTransaction).count() == before


def test_history_still_lists_existing_rows(client, auth_headers, test_user_id):
    import database

    with database.get_session() as session:
        tx = PortfolioTransaction(
            user_id=test_user_id, asset_type="MF", symbol="INF109K01VQ1",
            transaction_type="BUY", quantity=10, price=25.0, fees=0.0,
        )
        session.add(tx)
        session.commit()
        tx_id = tx.id

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
