"""CAS import API (spec 3.5): streamed upload, preview, commit, cancel, undo, list. No real PDF parsing."""
from __future__ import annotations

import base64
import copy
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import database
from models.db_models import AuditLogEntry, ImportBatch, Portfolio, Transaction, User
from services import money_cas_import as svc
from services import money_cas_mapping

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "cas_sample.json").read_text())
HDFC = "INF179K01VC4"
URL = "/api/v1/me/imports"


def _user():
    uid = random.randint(80_000_000, 89_999_999)
    with database.get_session() as session:
        session.add(User(id=uid, username=f"cas_{uid}", password_hash="x", display_name="CAS"))
        session.commit()
    return uid, {"Authorization": f"Bearer {database.create_access_token(uid)}"}


def _pdf(tag: str = "") -> str:
    return base64.b64encode(f"%PDF-1.4 {tag or uuid.uuid4().hex}".encode()).decode()


def _body(pdf=None, **over):
    body = {"pdf_base64": pdf or _pdf(), "password": "ABCDE1234F", "consent_notice_version": "cas-v1",
            "attest_own_statement": True}
    body.update(over)
    return body


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("FEATURE_MONEY_CAS_IMPORT", "true")
    state = {"cas": copy.deepcopy(FIXTURE), "calls": 0}

    def fake_parse(data, password, **_kw):
        state["calls"] += 1
        return money_cas_mapping.normalize(state["cas"])

    monkeypatch.setattr(svc, "parse_cas_pdf", fake_parse)
    return state


def _preview(client, headers, **over):
    return client.post(f"{URL}/cas/preview", json=_body(**over), headers=headers)


def _units(uid, isin=HDFC):
    with database.get_session() as session:
        row = session.query(Portfolio).execution_options(include_mf=True).filter_by(user_id=uid, ticker=isin).first()
        return None if row is None else round(float(row.shares), 3)


def _rows(uid, kind="ADJUST"):
    with database.get_session() as session:
        return session.query(Transaction).filter_by(user_id=uid, transaction_type=kind).all()


def test_flag_off_is_404(client, monkeypatch):
    monkeypatch.setenv("FEATURE_MONEY_CAS_IMPORT", "false")
    _, headers = _user()
    r = _preview(client, headers)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "FEATURE_DISABLED"


def test_requires_auth(client):
    assert client.post(f"{URL}/cas/preview", json=_body()).status_code == 401


def test_consent_required(client, env):
    _, headers = _user()
    for over in ({"attest_own_statement": False}, {"consent_notice_version": "cas-v0"}):
        r = _preview(client, headers, **over)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "CONSENT_REQUIRED"
    assert env["calls"] == 0


def test_non_pdf_is_415(client, env):
    _, headers = _user()
    r = _preview(client, headers, pdf=base64.b64encode(b"hello world").decode())
    assert r.status_code == 415 and r.json()["detail"]["code"] == "NOT_A_PDF"
    assert _preview(client, headers, pdf="***not base64***").status_code == 415
    assert env["calls"] == 0


def test_declared_oversize_body_is_413_without_parsing(client, env):
    _, headers = _user()
    r = client.post(f"{URL}/cas/preview", content=b"x" * 16_000_000, headers=headers)
    assert r.status_code == 413  # rejected on Content-Length by the body-cap middleware
    assert env["calls"] == 0


def test_chunked_oversize_body_is_413(client, env):
    _, headers = _user()

    def chunks():
        for _ in range(16):
            yield b"x" * 1_000_000

    r = client.post(f"{URL}/cas/preview", content=chunks(), headers=headers)
    assert r.status_code == 413 and r.json()["detail"]["code"] == "FILE_TOO_LARGE"
    assert env["calls"] == 0


def test_pdf_over_10mb_is_413(client, env):
    _, headers = _user()
    big = base64.b64encode(b"%PDF" + b"0" * 10_000_100).decode()
    r = _preview(client, headers, pdf=big)
    assert r.status_code == 413 and env["calls"] == 0


def test_long_password_rejected_and_not_echoed(client, env):
    _, headers = _user()
    secret = "p" * 65
    r = _preview(client, headers, password=secret)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "WRONG_PASSWORD"
    assert secret not in r.text and env["calls"] == 0


def test_malformed_json_is_invalid_request_without_echo(client):
    _, headers = _user()
    r = client.post(f"{URL}/cas/preview", content=b'{"pdf_base64": "SECRETVALUE", oops', headers=headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_REQUEST"
    assert "SECRETVALUE" not in r.text
    r = client.post(f"{URL}/cas/preview", json={"pdf_base64": 5, "password": "SECRETVALUE"}, headers=headers)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "INVALID_REQUEST" and "SECRETVALUE" not in r.text


def test_preview_shape_and_stored_json_has_no_pii(client, caplog):
    uid, headers = _user()
    with caplog.at_level(logging.DEBUG):
        r = _preview(client, headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["statement"] == {"from": "2016-01-01", "to": "2026-10-08", "source": "CAMS", "type": "DETAILED"}
    assert body["totals"] == {"schemes": 4, "balance": 2, "skipped": 2, "value_inr": 8638.07}
    hdfc = next(s for s in body["schemes"] if s["isin"] == HDFC)
    assert hdfc["mode"] == "balance" and hdfc["units"] == 123.456
    assert hdfc["valuation"] == {"date": "2026-10-08", "nav": 45.67, "value_inr": 5638.07, "cost_inr": 5000.0}
    assert "adjust" not in hdfc
    assert body["expires_at"].endswith("Z")
    with database.get_session() as session:
        stored = session.get(ImportBatch, body["batch_id"]).preview_json
    blob = json.dumps(stored)
    for needle in ("XXXXX0000X", "Test Investor", "PAN", "email", "folio"):
        assert needle not in blob
    assert "ABCDE1234F" not in caplog.text and "XXXXX0000X" not in caplog.text


def test_same_file_twice_supersedes(client):
    uid, headers = _user()
    pdf = _pdf()
    first = _preview(client, headers, pdf=pdf)
    second = _preview(client, headers, pdf=pdf)
    assert first.status_code == second.status_code == 200
    with database.get_session() as session:
        statuses = sorted(r.status for r in session.query(ImportBatch).filter_by(user_id=uid))
    assert statuses == ["cancelled", "previewed"]
    assert client.post(f"{URL}/{first.json()['batch_id']}/commit", headers=headers).status_code == 410


def test_commit_writes_one_adjust_per_scheme(client):
    uid, headers = _user()
    batch = _preview(client, headers).json()["batch_id"]
    r = client.post(f"{URL}/{batch}/commit", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"batch_id": batch, "inserted_transactions": 2, "skipped_duplicates": 0, "schemes_imported": 2}
    rows = _rows(uid)
    assert len(rows) == 2
    assert all(t.asset_class == "MF" and t.import_batch_id == batch and t.client_request_id.startswith("casbal:") for t in rows)
    assert _units(uid) == 123.456
    assert client.get("/api/v1/me/imports", headers=headers).json()[0]["status"] == "committed"
    with database.get_session() as session:
        assert session.get(ImportBatch, batch).preview_json is None
        actions = [a.action for a in session.query(AuditLogEntry).filter_by(user_id=uid)]
    assert "cas_import_committed" in actions
    assert client.post(f"{URL}/{batch}/commit", headers=headers).json()["detail"]["code"] == "ALREADY_COMMITTED"


def test_reimport_after_commit_is_409(client):
    _, headers = _user()
    pdf = _pdf()
    batch = _preview(client, headers, pdf=pdf).json()["batch_id"]
    client.post(f"{URL}/{batch}/commit", headers=headers)
    r = _preview(client, headers, pdf=pdf)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ALREADY_IMPORTED"


def test_later_statement_restates_and_undo_restores(client, env):
    uid, headers = _user()
    first = _preview(client, headers).json()["batch_id"]
    client.post(f"{URL}/{first}/commit", headers=headers)
    assert _units(uid) == 123.456

    later = copy.deepcopy(FIXTURE)
    later["statement_period"]["to"] = "2026-11-08"
    for folio in later["folios"][:2]:
        for scheme in folio["schemes"]:
            scheme["valuation"]["date"] = "2026-11-08"
    later["folios"][1]["schemes"][0]["close"] = "50.000"
    env["cas"] = later
    second = _preview(client, headers).json()
    hdfc = next(s for s in second["schemes"] if s["isin"] == HDFC)
    assert hdfc["mode"] == "balance" and hdfc["units"] == 150.0
    older = next(s for s in second["schemes"] if s["isin"] == "INF846K01DP8")
    assert older["mode"] == "balance"  # later date, so it restates too
    client.post(f"{URL}/{second['batch_id']}/commit", headers=headers)
    assert _units(uid) == 150.0

    r = client.delete(f"{URL}/{second['batch_id']}", headers=headers)
    assert r.status_code == 200 and r.json()["deleted_transactions"] == 2
    assert _units(uid) == 123.456
    # the second statement can be imported again after undo
    again = _preview(client, headers)
    assert again.status_code == 200
    assert client.post(f"{URL}/{again.json()['batch_id']}/commit", headers=headers).status_code == 200
    assert _units(uid) == 150.0


def test_older_statement_is_skipped(client, env):
    _, headers = _user()
    batch = _preview(client, headers).json()["batch_id"]
    client.post(f"{URL}/{batch}/commit", headers=headers)
    again = _preview(client, headers).json()  # a different PDF with the same statement date
    assert {s["reason"] for s in again["schemes"] if s["isin"] == HDFC} == {"older_statement"}


def test_manual_holding_is_not_overwritten(client):
    uid, headers = _user()
    with database.get_session() as session:
        session.add(Portfolio(user_id=uid, ticker=HDFC, company_name="Fund", shares=5, buy_price=10.0,
                              group_name="holdings", asset_class="MF"))
        session.commit()
    preview = _preview(client, headers).json()
    assert next(s for s in preview["schemes"] if s["isin"] == HDFC)["reason"] == "manual_entries_exist"


def test_cancel_and_quota(client):
    uid, headers = _user()
    for _ in range(10):
        batch = _preview(client, headers).json()["batch_id"]
        assert client.post(f"{URL}/{batch}/cancel", headers=headers).status_code == 204
    r = _preview(client, headers)
    assert r.status_code == 429 and r.json()["detail"]["code"] == "QUOTA_EXCEEDED"
    assert int(r.headers["Retry-After"]) > 0
    assert client.post(f"{URL}/{batch}/cancel", headers=headers).status_code == 404  # terminal state


def test_stale_rows_are_purged_at_preview(client):
    uid, headers = _user()
    old = datetime.utcnow() - timedelta(hours=30)
    with database.get_session() as session:
        for status in ("parsing", "previewed", "failed", "cancelled", "committed"):
            session.add(ImportBatch(user_id=uid, status=status, file_sha256=uuid.uuid4().hex, created_at=old))
        session.commit()
    assert _preview(client, headers).status_code == 200
    with database.get_session() as session:
        left = sorted(r.status for r in session.query(ImportBatch).filter_by(user_id=uid))
    assert left == ["committed", "previewed"]


def test_expired_preview_cannot_commit(client):
    uid, headers = _user()
    batch = _preview(client, headers).json()["batch_id"]
    with database.get_session() as session:
        session.get(ImportBatch, batch).created_at = datetime.utcnow() - timedelta(hours=25)
        session.commit()
    r = client.post(f"{URL}/{batch}/commit", headers=headers)
    assert r.status_code == 410 and r.json()["detail"]["code"] == "PREVIEW_EXPIRED"


def test_other_users_batch_is_404(client):
    _, headers = _user()
    _, other = _user()
    batch = _preview(client, headers).json()["batch_id"]
    assert client.post(f"{URL}/{batch}/commit", headers=other).status_code == 404
    assert client.post(f"{URL}/{batch}/cancel", headers=other).status_code == 404
    assert client.delete(f"{URL}/{batch}", headers=other).status_code == 404
    assert client.get(URL, headers=other).json() == []


def test_parse_errors_map_and_fail_the_batch(client, monkeypatch):
    from services.money_cas_parser import CASParseError

    uid, headers = _user()
    expected = {"WRONG_PASSWORD": 422, "UNSUPPORTED_STATEMENT": 422, "DEMAT_CAS_NOT_SUPPORTED": 422,
                "PARSE_TIMEOUT": 504, "PARSE_BUSY": 503}
    for code, status in expected.items():
        def boom(*_a, _code=code, **_k):
            raise CASParseError(_code)

        monkeypatch.setattr(svc, "parse_cas_pdf", boom)
        r = _preview(client, headers)
        assert r.status_code == status and r.json()["detail"]["code"] == code, code
        if code == "PARSE_BUSY":
            assert r.headers["Retry-After"] == "30"
    with database.get_session() as session:
        failed = session.query(ImportBatch).filter_by(user_id=uid, status="failed").count()
    assert failed == 5


def test_undo_that_would_oversell_is_409(client):
    uid, headers = _user()
    batch = _preview(client, headers).json()["batch_id"]
    client.post(f"{URL}/{batch}/commit", headers=headers)
    with database.get_session() as session:
        session.add(Transaction(user_id=uid, ticker=HDFC, transaction_type="SELL", quantity=100.0, price=50.0,
                                date=datetime(2026, 10, 20), asset_class="MF"))
        session.commit()
    r = client.delete(f"{URL}/{batch}", headers=headers)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "UNDO_WOULD_OVERSELL"
    assert _units(uid) is not None


def test_erase_user_removes_batches_and_imported_rows(client):
    from services.compliance_service import erase_user

    uid, headers = _user()
    batch = _preview(client, headers).json()["batch_id"]
    client.post(f"{URL}/{batch}/commit", headers=headers)
    _preview(client, headers)
    erase_user(uid)
    with database.get_session() as session:
        assert session.query(ImportBatch).filter_by(user_id=uid).count() == 0
        assert session.query(Transaction).filter_by(user_id=uid).count() == 0
        assert session.query(Portfolio).execution_options(include_mf=True).filter_by(user_id=uid).count() == 0
