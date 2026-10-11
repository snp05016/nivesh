"""Earnings-date alerts for a user (GH-615: first router cluster moved out of routers/).

Every function is scoped to the caller's user_id; no function reads another user's rows.
"""
from database import get_session
from models.db_models import EarningsAlert


def _serialize(alert: EarningsAlert) -> dict:
    return {
        "id": alert.id,
        "user_id": alert.user_id,
        "ticker": alert.ticker,
        "earnings_date": alert.earnings_date,
        "created_at": alert.created_at.isoformat() if alert.created_at is not None else None,
    }


def list_alerts(user_id: int) -> list[dict]:
    """The user's alerts, soonest earnings date first."""
    with get_session() as session:
        rows = session.query(EarningsAlert).filter(
            EarningsAlert.user_id == user_id
        ).order_by(EarningsAlert.earnings_date.asc()).all()
        return [_serialize(r) for r in rows]


def create_alert(user_id: int, ticker: str, earnings_date: str) -> dict:
    """Create an alert; an existing user/ticker/date row is returned instead of duplicated.

    The result carries status "created" or "already_exists".
    """
    with get_session() as session:
        existing = session.query(EarningsAlert).filter(
            EarningsAlert.user_id == user_id,
            EarningsAlert.ticker == ticker,
            EarningsAlert.earnings_date == earnings_date,
        ).first()
        if existing:
            return {**_serialize(existing), "status": "already_exists"}

        entry = EarningsAlert(user_id=user_id, ticker=ticker, earnings_date=earnings_date)
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return {**_serialize(entry), "status": "created"}


def delete_alert(user_id: int, alert_id: int) -> bool:
    """Delete the user's alert. False when it does not exist or belongs to someone else."""
    with get_session() as session:
        entry = session.query(EarningsAlert).filter(
            EarningsAlert.id == alert_id,
            EarningsAlert.user_id == user_id,
        ).first()
        if not entry:
            return False
        session.delete(entry)
        session.commit()
        return True
