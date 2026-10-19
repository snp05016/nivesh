"""GET /api/v1/compliance/my-data and the export/erasure completeness guards."""
import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.rate_limiter as rate_limiter
import core.security as security
from database import ENGINE, get_session
from models.db_models import (
    AuditLogEntry, Base, DeviceToken, FeatureFlag, KYCConsent, LlmUsage, Portfolio, ResearchReportRow,
    User, UserBlock, UserEvent,
)
from routers import compliance as compliance_router
from services import compliance_service, privacy_export


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    Base.metadata.create_all(ENGINE)
    rate_limiter._rate_limit_store.clear()
    monkeypatch.setattr(security, "verify_access_token", lambda t: int(t) if t.isdigit() else None)
    yield
    rate_limiter._rate_limit_store.clear()


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(compliance_router.router)
    return TestClient(app)


def _user() -> int:
    with get_session() as s:
        u = User(username=f"exp_{uuid4().hex[:12]}", password_hash="secret-hash", display_name="Exp")
        s.add(u)
        s.commit()
        return int(u.id)


def _hdr(uid):
    return {"Authorization": f"Bearer {uid}"}


def _seed(uid, token="tok-" + "x" * 40 + "ABCD"):
    with get_session() as s:
        s.add_all([
            Portfolio(user_id=uid, ticker="TCS", company_name="TCS " + "z" * 25000, shares=1, buy_price=100),
            KYCConsent(user_id=uid, consent_type="ai_processing", granted=True),
            DeviceToken(user_id=uid, device_token=token + uuid4().hex[:4]),
        ])
        s.commit()


def test_export_has_own_rows_only():
    a, b = _user(), _user()
    _seed(a)
    _seed(b)
    out = privacy_export.build_user_export(a)
    assert out["schema_version"] == "nivesh-export.v1"
    assert len(out["tables"]["portfolio"]["rows"]) == 1
    assert out["tables"]["portfolio"]["rows"][0]["user_id"] == a
    assert [r["user_id"] for r in out["tables"]["kyc_consents"]["rows"]] == [a]
    assert out["user"]["id"] == a and set(out["user"]) == {"id", "username", "display_name", "created_at"}


def test_blocks_never_reveal_the_blocker():
    a, b = _user(), _user()
    with get_session() as s:
        s.add(UserBlock(blocker_user_id=b, blocked_user_id=a))
        s.commit()
    a_export = privacy_export.build_user_export(a)
    assert a_export["tables"]["user_blocks"]["rows"] == []
    for table in a_export["tables"].values():
        for row in table["rows"]:
            for col, val in row.items():
                if col == "user_id" or col.endswith("_user_id"):
                    assert val != b
    b_rows = privacy_export.build_user_export(b)["tables"]["user_blocks"]["rows"]
    assert len(b_rows) == 1 and b_rows[0]["blocker_user_id"] == b and b_rows[0]["blocked_user_id"] is None


def test_secrets_masked_and_truncated():
    uid = _user()
    _seed(uid)
    text = json.dumps(privacy_export.build_user_export(uid))
    assert "secret-hash" not in text and "password_hash" not in text and "token_version" not in text
    token_row = privacy_export.build_user_export(uid)["tables"]["device_tokens"]["rows"][0]
    assert token_row["device_token"].startswith("...") and len(token_row["device_token"]) == 7
    name = privacy_export.build_user_export(uid)["tables"]["portfolio"]["rows"][0]["company_name"]
    assert name.endswith("...[truncated]") and len(name) < 20100


def test_row_cap(monkeypatch):
    uid = _user()
    with get_session() as s:
        s.add_all([Portfolio(user_id=uid, ticker=f"T{i}", company_name="x", shares=1, buy_price=1) for i in range(3)])
        s.commit()
    monkeypatch.setattr(privacy_export, "ROW_CAP", 2)
    table = privacy_export.build_user_export(uid)["tables"]["portfolio"]
    assert table["truncated"] is True and len(table["rows"]) == 2


def test_every_user_table_exports_with_a_group():
    out = privacy_export.build_user_export(_user())
    fk_tables = {t.name for t, _c in compliance_service.user_fk_columns()}
    assert fk_tables <= set(out["tables"])
    for name, entry in out["tables"].items():
        assert entry["group"] in privacy_export.STORED_DATA_ROWS, name


def test_export_after_flags_cleared(monkeypatch):
    monkeypatch.setenv("FEATURE_ANALYTICS", "0")
    with get_session() as s:
        s.query(FeatureFlag).delete()
        s.commit()
    assert privacy_export.build_user_export(_user())["tables"]


def test_deleted_user_not_exportable():
    uid = _user()
    with get_session() as s:
        s.get(User, uid).deleted_at = datetime.now(timezone.utc)
        s.commit()
    with pytest.raises(LookupError):
        privacy_export.build_user_export(uid)
    with pytest.raises(LookupError):
        privacy_export.build_user_export(10**9)


def test_route_headers_audit_and_rate_limit(api):
    uid = _user()
    r = api.get("/api/v1/compliance/my-data", headers=_hdr(uid))
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="nivesh-my-data-')
    assert r.headers["content-disposition"].endswith('.json"')
    assert r.headers["cache-control"] == "no-store"
    assert r.json()["processors"][-1]["name"] == "Operations alert relay (owner-chosen)"
    with get_session() as s:
        assert s.query(AuditLogEntry).filter_by(user_id=uid, action="data_exported").count() == 1
    codes = [api.get("/api/v1/compliance/my-data", headers=_hdr(uid)).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 200, 429]  # the sixth export in 24 h


def test_route_auth_and_404(api):
    assert api.get("/api/v1/compliance/my-data").status_code == 401
    r = api.get("/api/v1/compliance/my-data", headers=_hdr(10**9))
    assert r.status_code == 404 and r.json() == {"detail": "Not available"}


# --- completeness guards -------------------------------------------------------

def _user_cols(table):
    return [c for c in table.columns if c.name == "user_id" or c.name.endswith("_user_id")]


def test_guard_non_fk_user_columns_are_registered():
    for table in Base.metadata.sorted_tables:
        for col in _user_cols(table):
            has_fk = any(fk.column.table.name == "users" for fk in col.foreign_keys)
            if not has_fk:
                entry = compliance_service.EXTRA_USER_COLUMNS.get(table.name)
                assert entry and entry[0] == col.name, (
                    f"{table.name}.{col.name} holds a user id without a foreign key: "
                    "add it to compliance_service.EXTRA_USER_COLUMNS"
                )


def test_guard_multi_user_column_tables_have_an_owner():
    for table in Base.metadata.sorted_tables:
        if table.name == "users":
            continue
        cols = privacy_export.user_columns(table)
        if len(cols) >= 2:
            assert privacy_export.EXPORT_OWNER_COLUMN.get(table.name) in cols, (
                f"{table.name} has several user columns {cols}: add an EXPORT_OWNER_COLUMN entry"
            )


def test_guard_every_exported_table_is_in_a_stored_data_row():
    for table in privacy_export.exported_tables():
        n = privacy_export.TABLE_GROUPS.get(table.name)
        assert n in range(1, 8), (
            f"{table.name}: add it to TABLE_GROUPS; if no row describes it, add a row here and in PrivacyCenterView.swift"
        )


def test_guard_ios_view_lists_the_stored_data_rows():
    view = Path(__file__).resolve().parents[2] / "ios/StockApp/stockme/stockme/Views/PrivacyCenterView.swift"
    if not view.exists():
        pytest.skip("PrivacyCenterView.swift not present")
    text = view.read_text(encoding="utf-8")
    for row in privacy_export.STORED_DATA_ROWS:
        assert row in text, row


def test_erase_user_nulls_extra_columns():
    uid, other = _user(), _user()
    with get_session() as s:
        s.add(ResearchReportRow(
            report_uid=str(uuid4()), symbol="T" + uuid4().hex[:8], as_of_date=date(2026, 10, 1), engine_version="t",
            origin="on_demand", status="ok", in_universe=True, requested_by_user_id=uid, report_json={},
        ))
        s.add_all([LlmUsage(user_id=uid, feature="f", model="m"), LlmUsage(user_id=other, feature="f", model="m")])
        s.commit()
    compliance_service.erase_user(uid)
    with get_session() as s:
        assert s.query(ResearchReportRow).filter_by(requested_by_user_id=uid).count() == 0
        assert s.query(LlmUsage).filter_by(user_id=uid).count() == 0
        assert s.query(LlmUsage).filter_by(user_id=other).count() == 1


def test_runbook_has_rule_8_3_with_decision():
    text = (Path(__file__).resolve().parents[2] / "docs/compliance/DPDP_RUNBOOK.md").read_text(encoding="utf-8")
    assert "Rule 8(3)" in text and "Narrow reading" in text and "Broad reading" in text and "Decision:" in text
