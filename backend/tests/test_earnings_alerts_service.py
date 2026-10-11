"""GH-615: earnings-alert queries live in services/earnings_alerts_service.py and stay
scoped to the caller. Runs against conftest's temporary test DB."""
from uuid import uuid4

import database
from services import earnings_alerts_service as svc


def _new_user() -> int:
    with database.get_session() as session:
        user = database.User(username=f"eas_{uuid4().hex[:12]}", password_hash="x",
                             display_name="Earnings Alert Service Test")
        session.add(user)
        session.commit()
        return int(user.id)  # type: ignore[arg-type]


def test_create_list_delete_round_trip():
    uid = _new_user()
    later = svc.create_alert(uid, "TCS", "2026-12-01")
    sooner = svc.create_alert(uid, "INFY", "2026-11-15")
    assert later["status"] == sooner["status"] == "created"
    assert set(later) == {"id", "user_id", "ticker", "earnings_date", "created_at", "status"}

    again = svc.create_alert(uid, "TCS", "2026-12-01")
    assert again["status"] == "already_exists"
    assert again["id"] == later["id"]

    alerts = svc.list_alerts(uid)
    assert [a["ticker"] for a in alerts] == ["INFY", "TCS"]  # earnings_date ascending
    assert all(a["user_id"] == uid for a in alerts)

    assert svc.delete_alert(uid, sooner["id"]) is True
    assert [a["id"] for a in svc.list_alerts(uid)] == [later["id"]]
    assert svc.delete_alert(uid, sooner["id"]) is False  # already gone


def test_other_users_alerts_are_invisible_and_undeletable():
    owner, other = _new_user(), _new_user()
    alert = svc.create_alert(owner, "HDFCBANK", "2026-11-20")

    assert svc.list_alerts(other) == []
    assert svc.delete_alert(other, alert["id"]) is False
    assert [a["id"] for a in svc.list_alerts(owner)] == [alert["id"]]
