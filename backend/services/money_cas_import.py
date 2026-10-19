"""CAS import (spec 3.5): preview, commit, cancel, undo and list.

v1 imports every fund as a balance: one restating ADJUST per ISIN. A statement is parsed in a
killable child (money_cas_parser); only fund name, ISIN, units and valuation are kept, the PDF
and its password never touch disk, the DB or the logs. Fund rows are read with include_mf.
Nothing here calls an LLM.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError

from core.timeutil import utcnow
from database import get_session
from models.db_models import ImportBatch, Portfolio, Transaction
from services import compliance_service, ledger_service, money_cas_mapping
from services.money_cas_parser import CASParseError, parse_cas_pdf

logger = logging.getLogger(__name__)

NOTICE_VERSION = "cas-v1"
MAX_PDF_BYTES = 10_000_000
MAX_BODY_BYTES = 15_000_000
PREVIEW_TTL = timedelta(hours=24)
DAILY_ATTEMPTS = 10
MAX_PASSWORD_LEN = 64
_STALE_STATUSES = ("parsing", "previewed", "failed", "cancelled")

MESSAGES = {
    "CONSENT_REQUIRED": "Please confirm the statement is yours and agree to the notice to continue.",
    "WRONG_PASSWORD": "That password didn't open the statement. CAS passwords are set when you request the statement.",
    "UNSUPPORTED_STATEMENT": "This doesn't look like a CAMS or KFintech CAS. Request a Detailed CAS and try again.",
    "DEMAT_CAS_NOT_SUPPORTED": "Demat (NSDL/CDSL) statements aren't supported yet.",
    "ALREADY_IMPORTED": "You've already imported this statement.",
    "QUOTA_EXCEEDED": "You've reached today's import limit. Try again tomorrow.",
    "FILE_TOO_LARGE": "This file is larger than 10 MB.",
    "NOT_A_PDF": "That file isn't a PDF.",
    "PARSE_TIMEOUT": "Reading the statement took too long. Please try again.",
    "PARSE_BUSY": "We're reading other statements. Try again in a minute.",
    "NOT_FOUND": "We couldn't find that import.",
    "ALREADY_COMMITTED": "This import was already added to your portfolio.",
    "PREVIEW_EXPIRED": "This preview has expired. Upload the statement again.",
    "LEDGER_CONFLICT": "These balances conflict with your existing transactions.",
    "UNDO_WOULD_OVERSELL": "This import can't be undone because later transactions depend on it.",
}
_PARSE_STATUS = {
    "WRONG_PASSWORD": 422, "UNSUPPORTED_STATEMENT": 422, "DEMAT_CAS_NOT_SUPPORTED": 422,
    "PARSE_TIMEOUT": 504, "PARSE_BUSY": 503,
}


class CasImportError(Exception):
    def __init__(self, code: str, status: int, retry_after: Optional[int] = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after

    @property
    def message(self) -> str:
        return MESSAGES.get(self.code, "Something went wrong.")


def _now():
    return utcnow().replace(tzinfo=None)


def _iso_z(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _decode_pdf(pdf_base64: str) -> bytes:
    if len(pdf_base64) > MAX_PDF_BYTES * 4 // 3 + 8:
        raise CasImportError("FILE_TOO_LARGE", 413)
    try:
        data = base64.b64decode(pdf_base64, validate=True)
    except (binascii.Error, ValueError):
        raise CasImportError("NOT_A_PDF", 415) from None
    if len(data) > MAX_PDF_BYTES:
        raise CasImportError("FILE_TOO_LARGE", 413)
    if not data.startswith(b"%PDF"):
        raise CasImportError("NOT_A_PDF", 415)
    return data


def _purge_and_check_quota(user_id: int) -> None:
    now = _now()
    with get_session() as session:
        session.query(ImportBatch).filter(
            ImportBatch.status.in_(_STALE_STATUSES), ImportBatch.created_at < now - PREVIEW_TTL
        ).delete(synchronize_session=False)
        session.commit()
        recent = (
            session.query(ImportBatch.created_at)
            .filter(ImportBatch.user_id == user_id, ImportBatch.created_at >= now - PREVIEW_TTL)
            .order_by(ImportBatch.created_at)
            .all()
        )
        if len(recent) >= DAILY_ATTEMPTS:
            wait = (recent[0][0] + PREVIEW_TTL - now).total_seconds()
            raise CasImportError("QUOTA_EXCEEDED", 429, retry_after=max(1, math.ceil(wait)))


def _start_batch(user_id: int, sha: str, notice: str) -> int:
    now = _now()
    with get_session() as session:
        if session.query(ImportBatch.id).filter_by(user_id=user_id, file_sha256=sha, status="committed").first():
            raise CasImportError("ALREADY_IMPORTED", 409)
        session.query(ImportBatch).filter_by(user_id=user_id, file_sha256=sha, status="previewed").update(
            {"status": "cancelled", "preview_json": None}, synchronize_session=False
        )
        batch = ImportBatch(
            user_id=user_id, source="cams_kfintech", status="parsing", file_sha256=sha,
            consent_notice_version=notice, consented_at=now, created_at=now,
        )
        session.add(batch)
        session.commit()
        return int(batch.id)


def _fail(batch_id: int, code: str) -> None:
    with get_session() as session:
        batch = session.get(ImportBatch, batch_id)
        if batch is not None:
            batch.status, batch.error_code, batch.preview_json = "failed", code, None
            session.commit()


def _existing_and_manual(session, user_id: int) -> tuple[dict[str, Any], set[str]]:
    existing: dict[str, Any] = {}
    manual: set[str] = set()
    rows = session.query(Transaction.ticker, Transaction.transaction_type, Transaction.date, Transaction.import_batch_id).filter(
        Transaction.user_id == user_id, Transaction.asset_class == "MF"
    ).all()
    for ticker, kind, when, batch_id in rows:
        if batch_id is None:
            manual.add(str(ticker))
        elif kind == "ADJUST" and when is not None:
            if ticker not in existing or when.date() > existing[ticker]:
                existing[str(ticker)] = when.date()
    # a fund row with no ledger rows at all was entered by hand
    held = session.query(Portfolio.ticker).execution_options(include_mf=True).filter(
        Portfolio.user_id == user_id, Portfolio.asset_class == "MF"
    ).all()
    manual |= {str(t) for (t,) in held if str(t) not in existing}
    return existing, manual


def _public_scheme(plan: dict) -> dict:
    return {k: plan[k] for k in ("isin", "name", "amc", "units", "valuation", "mode", "reason", "flags")}


def _preview_payload(batch_id: int, created_at: datetime, stored: dict) -> dict:
    plans = stored["plans"]
    return {
        "batch_id": batch_id,
        "expires_at": _iso_z(created_at + PREVIEW_TTL),
        "statement": stored["statement"],
        "schemes": [_public_scheme(p) for p in plans],
        "totals": money_cas_mapping.preview_summary(plans),
    }


def preview(user_id: int, pdf_base64: str, password: str, consent_notice_version: str, attest_own_statement: bool) -> dict:
    if consent_notice_version != NOTICE_VERSION or attest_own_statement is not True:
        raise CasImportError("CONSENT_REQUIRED", 422)
    if len(password or "") > MAX_PASSWORD_LEN:
        raise CasImportError("WRONG_PASSWORD", 422)
    _purge_and_check_quota(user_id)
    data = _decode_pdf(pdf_base64)
    sha = hashlib.sha256(data).hexdigest()
    batch_id = _start_batch(user_id, sha, consent_notice_version)
    try:
        normalized = parse_cas_pdf(data, password)
    except CASParseError as exc:
        _fail(batch_id, exc.code)
        raise CasImportError(
            exc.code, _PARSE_STATUS.get(exc.code, 422), retry_after=30 if exc.code == "PARSE_BUSY" else None
        ) from None
    except Exception as exc:
        logger.warning("cas preview failed: %s", type(exc).__name__)
        _fail(batch_id, "UNSUPPORTED_STATEMENT")
        raise CasImportError("UNSUPPORTED_STATEMENT", 422) from None
    with get_session() as session:
        existing, manual = _existing_and_manual(session, user_id)
        plans = money_cas_mapping.plan(normalized, existing, manual)
        stored = {"plans": plans, "statement": normalized["statement"], "cas_type": normalized["statement"]["type"],
                  "schemes_total": len(plans)}
        batch = session.get(ImportBatch, batch_id)
        batch.status = "previewed"
        batch.preview_json = stored
        batch.cas_type = str(normalized["statement"]["type"])[:10]
        batch.statement_from = money_cas_mapping.to_date(normalized["statement"]["from"])
        batch.statement_to = money_cas_mapping.to_date(normalized["statement"]["to"])
        batch.schemes_total = len(plans)
        session.commit()
        return _preview_payload(batch_id, batch.created_at, stored)


def _own_batch(session, user_id: int, batch_id: int) -> ImportBatch:
    batch = session.query(ImportBatch).filter_by(id=batch_id, user_id=user_id).first()
    if batch is None:
        raise CasImportError("NOT_FOUND", 404)
    return batch


def commit(user_id: int, batch_id: int) -> dict:
    now = _now()
    with get_session() as session:
        batch = _own_batch(session, user_id, batch_id)
        if batch.status == "committed":
            raise CasImportError("ALREADY_COMMITTED", 409)
        if batch.status == "cancelled" or (batch.status == "previewed" and batch.created_at < now - PREVIEW_TTL):
            raise CasImportError("PREVIEW_EXPIRED", 410)
        if batch.status != "previewed" or not batch.preview_json:
            raise CasImportError("NOT_FOUND", 404)
        plans = [p for p in batch.preview_json["plans"] if p["mode"] == "balance"]
        inserted = skipped = 0
        try:
            for p in plans:
                adjust = p["adjust"]
                when = datetime.combine(money_cas_mapping.to_date(adjust["date"]), datetime.min.time())
                tx = ledger_service.restate_position(
                    session, user_id, p["isin"], adjust["quantity"], adjust["price"],
                    date=when, notes="CAS balance", asset_class="MF", import_batch_id=batch.id,
                    client_request_id=adjust["key"], company_name=p["name"],
                )
                if tx is None:
                    skipped += 1
                else:
                    inserted += 1
            batch.status = "committed"
            batch.committed_at = now
            batch.schemes_imported = inserted
            batch.inserted_rows = inserted
            batch.skipped_rows = skipped
            batch.preview_json = None
            compliance_service._log_action(
                session, user_id, "cas_import_committed",
                {"batch_id": batch.id, "schemes": len(plans), "rows": inserted},
            )
            session.flush()
        except IntegrityError:
            session.rollback()
            raise CasImportError("ALREADY_IMPORTED", 409) from None
        except ledger_service.LedgerError:
            session.rollback()
            raise CasImportError("LEDGER_CONFLICT", 409) from None
        session.commit()
        return {"batch_id": batch_id, "inserted_transactions": inserted, "skipped_duplicates": skipped,
                "schemes_imported": inserted}


def cancel(user_id: int, batch_id: int) -> None:
    with get_session() as session:
        batch = _own_batch(session, user_id, batch_id)
        if batch.status != "previewed":
            raise CasImportError("NOT_FOUND", 404)
        batch.status, batch.preview_json = "cancelled", None
        session.commit()


def undo(user_id: int, batch_id: int) -> dict:
    with get_session() as session:
        batch = _own_batch(session, user_id, batch_id)
        if batch.status != "committed":
            raise CasImportError("NOT_FOUND", 404)
        try:
            deleted = ledger_service.remove_import_batch(session, user_id, batch_id)
        except ledger_service.LedgerError:
            session.rollback()
            raise CasImportError("UNDO_WOULD_OVERSELL", 409) from None
        compliance_service._log_action(session, user_id, "cas_import_undone", {"batch_id": batch_id, "rows": deleted})
        session.delete(batch)
        session.commit()
        return {"deleted_transactions": deleted}


def list_imports(user_id: int) -> list[dict]:
    cutoff = _now() - PREVIEW_TTL
    with get_session() as session:
        rows = (
            session.query(ImportBatch)
            .filter(ImportBatch.user_id == user_id, ImportBatch.status.in_(("previewed", "committed")))
            .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
            .all()
        )
        return [
            {
                "batch_id": b.id, "source": b.source,
                "statement_to": b.statement_to.isoformat() if b.statement_to else None,
                "status": b.status, "schemes_imported": b.schemes_imported,
                "inserted_transactions": b.inserted_rows, "created_at": _iso_z(b.created_at),
            }
            for b in rows
            if b.status == "committed" or b.created_at >= cutoff
        ]
