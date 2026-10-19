"""FINSEC-13: paid plans lapse at renews_at (cancelled or not) and first-access
row creation survives a race. Rows are seeded through the ORM."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from services import entitlement_service, subscription_service


def _new_user_id() -> int:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"sub_{uuid4().hex[:12]}", password_hash="x", display_name="Subscription Test")
        session.add(user)
        session.commit()
        return int(user.id)  # type: ignore[arg-type]


def _set_renews_at(user_id: int, renews_at: datetime) -> None:
    import database
    from models.db_models import UserSubscription  # pyright: ignore[reportMissingImports]

    with database.get_session() as session:
        session.query(UserSubscription).filter(UserSubscription.user_id == user_id).update({"renews_at": renews_at})
        session.commit()


def _naive_utc(delta: timedelta) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + delta


def _seed_plan(user_id: int, *, is_active: bool = True, renews_in: timedelta = timedelta(days=30)) -> None:
    """Give the user a PRO row through the ORM (there is no purchase route; paid tiers come from App Store verification)."""
    from database import get_session
    from models.db_models import UserSubscription  # pyright: ignore[reportMissingImports]
    from services import subscription_service

    subscription_service.get_or_create_subscription(user_id)
    with get_session() as session:
        session.query(UserSubscription).filter(UserSubscription.user_id == user_id).update({
            "tier": "pro",
            "billing_cycle": "monthly",
            "is_active": is_active,
            "renews_at": datetime.now(timezone.utc).replace(tzinfo=None) + renews_in,
        })
        session.commit()


def test_active_plan_with_past_renews_at_is_free():
    user_id = _new_user_id()
    _seed_plan(user_id)
    _set_renews_at(user_id, _naive_utc(-timedelta(days=1)))  # is_active stays True

    assert entitlement_service.get_effective_tier(user_id) == "free"
    row = subscription_service.get_or_create_subscription(user_id)
    assert row["tier"] == "free"
    assert row["renews_at"] is None and row["billing_cycle"] is None


def test_cancelled_until_period_end_keeps_tier():
    user_id = _new_user_id()
    _seed_plan(user_id, is_active=False)  # cancelled, paid period still running
    assert entitlement_service.get_effective_tier(user_id) == "pro"

    _set_renews_at(user_id, _naive_utc(-timedelta(seconds=1)))
    assert entitlement_service.get_effective_tier(user_id) == "free"


def test_get_or_create_handles_integrity_error(monkeypatch):
    """A concurrent first request inserted the row between our read and our
    insert: the unique user_id collision must return that row, not 500."""
    from sqlalchemy.orm import Query

    user_id = _new_user_id()
    subscription_service.get_or_create_subscription(user_id)  # the "other request" wins

    real_first = Query.first
    calls = {"n": 0}

    def first_misses_once(self):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_first(self)

    monkeypatch.setattr(Query, "first", first_misses_once)
    row = subscription_service.get_or_create_subscription(user_id)
    assert row["user_id"] == user_id and row["tier"] == "free"
    assert calls["n"] >= 1  # the patched miss was exercised
