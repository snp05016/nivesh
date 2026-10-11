"""FINSEC-13: paid plans lapse at renews_at (cancelled or not), replaying an
upgrade never extends access, and first-access row creation survives a race."""
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


def test_active_plan_with_past_renews_at_is_free():
    user_id = _new_user_id()
    subscription_service.mock_upgrade(user_id, "pro", "monthly")
    _set_renews_at(user_id, _naive_utc(-timedelta(days=1)))  # is_active stays True

    assert entitlement_service.get_effective_tier(user_id) == "free"
    row = subscription_service.get_or_create_subscription(user_id)
    assert row["tier"] == "free"
    assert row["renews_at"] is None and row["billing_cycle"] is None


def test_cancelled_until_period_end_keeps_tier():
    user_id = _new_user_id()
    subscription_service.mock_upgrade(user_id, "pro", "monthly")
    cancelled = subscription_service.mock_cancel(user_id)
    assert cancelled["is_active"] is False
    assert entitlement_service.get_effective_tier(user_id) == "pro"

    _set_renews_at(user_id, _naive_utc(-timedelta(seconds=1)))
    assert entitlement_service.get_effective_tier(user_id) == "free"


def test_repeat_upgrade_does_not_extend():
    user_id = _new_user_id()
    first = subscription_service.mock_upgrade(user_id, "pro", "monthly")
    second = subscription_service.mock_upgrade(user_id, "pro", "monthly")
    assert second["renews_at"] == first["renews_at"]


def test_cancel_then_upgrade_same_tier_does_not_extend():
    user_id = _new_user_id()
    first = subscription_service.mock_upgrade(user_id, "pro", "monthly")
    subscription_service.mock_cancel(user_id)
    resumed = subscription_service.mock_upgrade(user_id, "pro", "monthly")
    assert resumed["renews_at"] == first["renews_at"]
    assert resumed["is_active"] is True and resumed["cancelled_at"] is None


def test_upgrade_after_lapse_starts_new_period():
    user_id = _new_user_id()
    subscription_service.mock_upgrade(user_id, "pro", "monthly")
    _set_renews_at(user_id, _naive_utc(-timedelta(days=1)))
    renewed = subscription_service.mock_upgrade(user_id, "pro", "monthly")
    renews_at = renewed["renews_at"]
    if renews_at.tzinfo is None:
        renews_at = renews_at.replace(tzinfo=timezone.utc)
    assert renews_at > datetime.now(timezone.utc) + timedelta(days=29)
    assert renewed["tier"] == "pro"


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


def test_upgrade_to_free_422(client, monkeypatch):
    import database

    monkeypatch.setenv("ALLOW_MOCK_PURCHASES", "1")
    headers = {"Authorization": f"Bearer {database.create_access_token(_new_user_id())}"}
    resp = client.post("/api/v1/subscription/upgrade", json={"tier": "free", "billing_cycle": "monthly"}, headers=headers)
    assert resp.status_code == 422
