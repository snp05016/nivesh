"""DPDP s.11 access right: a JSON export of everything stored about one user.

Tables come from ORM metadata (every table with a foreign key to users.id, plus the
EXTRA_USER_COLUMNS of compliance_service), so the export grows with the schema. Each table is
filtered on one owner column only, and every other user-id column is set to null, so an export
never reveals who blocked or reported the user. Not behind a flag: it is a rights surface.
"""
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select

from database import get_session
from models.db_models import Base, User
from services import audit_service, compliance_service
from services.disclosure_service import CONSENT_PURPOSES

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

SCHEMA_VERSION = "nivesh-export.v1"
ROW_CAP = 5000
STRING_CAP = 20000
SECRET_COLUMNS = frozenset({"password_hash", "token_version", "refresh_token_hash"})

# Tables with two or more user columns name the one that owns the row.
EXPORT_OWNER_COLUMN: dict[str, str] = {"user_blocks": "blocker_user_id"}

# The seven "WHAT WE STORE" rows, exactly as PrivacyCenterView.swift shows them.
STORED_DATA_ROWS: tuple[str, ...] = (
    "Your account: username, display name, settings and subscription",
    "Holdings, transactions, watchlists, alerts and journal notes you add, and the values and tax reports we calculate from them",
    "Loan, deposit, bank-account and finance-tracker records, if you use those features",
    "Posts, votes, reports and blocks in the community forum",
    "Your device ID and push token, your consent choices and security records, with the IP address on them",
    "Your notifications, analyses and AI research requests",
    "Usage events, only if you turn on usage analytics",
)

_GROUP_TABLES = {
    1: ("users", "user_preferences", "user_subscriptions"),
    2: ("portfolio", "portfolio_groups", "portfolio_transactions", "multi_asset_transactions", "import_batches",
        "watchlists", "price_targets", "earnings_alerts", "trade_journal", "dividend_ledger", "tax_reports",
        "portfolio_valuation_history", "net_worth_ledger"),
    3: ("linked_bank_accounts", "loan_applications", "loan_disbursements", "fixed_deposit_bookings",
        "finance_tracker_accounts"),
    4: ("forum_threads", "forum_posts", "forum_votes", "forum_reports", "user_blocks"),
    5: ("device_tokens", "device_bindings", "device_binding_attempts", "kyc_consents", "audit_log_entries",
        "data_deletion_requests"),
    6: ("in_app_notifications", "analysis_history", "analysis_jobs", "research_reports", "llm_usage"),
    7: ("user_events",),
}
# table -> row number (1..7) of STORED_DATA_ROWS. A new user-linked table must be added here.
TABLE_GROUPS: dict[str, int] = {t: n for n, tables in _GROUP_TABLES.items() for t in tables}

PROCESSORS: list[dict[str, str]] = [
    {
        "name": "DeepSeek", "country": "PRC",
        "purpose": "AI text for AI features, only with the AI processing consent",
        "data": "tickers, company names, percentage moves, chat text",
        "legal_basis": "consent",
    },
    {
        "name": "Anthropic", "country": "USA",
        "purpose": "AI text for AI features, only with the AI processing consent",
        "data": "tickers, company names, percentage moves, chat text",
        "legal_basis": "consent",
    },
    {
        "name": "Apple Push Notification service", "country": "USA",
        "purpose": "push notification delivery",
        "data": "device token, notification text",
        "legal_basis": "consent",
    },
    {
        "name": "Operations alert relay (owner-chosen)",
        "country": "depends on the relay the owner configures; a self-hosted relay keeps it in India",
        "purpose": "alerting the operator when a scheduled job fails",
        "data": "scrubbed error text only, at most 300 characters",
        "legal_basis": "not applicable: no personal data is intended; errors are scrubbed before sending",
    },
]

NOTES: list[str] = [
    "Backups keep data up to 14 days after deletion",
    "Consent and audit records are kept after deletion without IP",
    "Usage events are deleted when you turn usage analytics off",
]


def user_columns(table) -> list[str]:
    """Columns of `table` that hold a user id: FKs to users.id plus EXTRA_USER_COLUMNS."""
    cols = [c.name for c in table.columns if any(fk.column.table.name == "users" for fk in c.foreign_keys)]
    extra = compliance_service.EXTRA_USER_COLUMNS.get(table.name)
    if extra and extra[0] not in cols and extra[0] in table.c:
        cols.append(extra[0])
    return cols


def owner_column(table) -> str | None:
    """The one column rows are selected on; None when the table has none or is ambiguous."""
    cols = user_columns(table)
    if table.name in EXPORT_OWNER_COLUMN:
        return EXPORT_OWNER_COLUMN[table.name]
    if len(cols) == 1:
        return cols[0]
    if len(cols) > 1:
        logger.warning("privacy export: %s has %d user columns and no EXPORT_OWNER_COLUMN entry; skipped",
                       table.name, len(cols))
    return None


def exported_tables() -> list:
    return [t for t in Base.metadata.sorted_tables if t.name != "users" and owner_column(t)]


def _convert(name: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.isoformat() + "Z"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<omitted: binary>"
    if isinstance(value, str):
        if name == "token" or name.endswith("_token"):
            return "..." + value[-4:]
        return value if len(value) <= STRING_CAP else value[:STRING_CAP] + "...[truncated]"
    if isinstance(value, (dict, list)):
        return _convert_json(value)
    return value


def _convert_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _convert_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_json(v) for v in value]
    return _convert("", value)


def _row(table, mapping, owner: str, others: set[str]) -> dict:
    out = {}
    for col in table.columns:
        if col.name in SECRET_COLUMNS:
            continue
        out[col.name] = None if col.name in others else _convert(col.name, mapping[col.name])
    return out


def _table_export(session, table, user_id: int) -> dict:
    owner = owner_column(table)
    others = {c for c in user_columns(table) if c != owner}
    stmt = (
        select(table)
        .where(table.c[owner] == user_id)
        .order_by(*[c.desc() for c in table.primary_key.columns])
        .limit(ROW_CAP + 1)
    )
    fetched = session.execute(stmt).mappings().all()
    truncated = len(fetched) > ROW_CAP
    rows = [_row(table, r, owner, others) for r in fetched[:ROW_CAP]]
    group = TABLE_GROUPS.get(table.name)
    return {
        "group": STORED_DATA_ROWS[group - 1] if group else None,
        "rows": rows,
        "truncated": truncated,
    }


def export_filename(now: datetime | None = None) -> str:
    """nivesh-my-data-YYYY-MM-DD.json with the IST date."""
    now = now or datetime.now(timezone.utc)
    return f"nivesh-my-data-{now.astimezone(IST).date().isoformat()}.json"


def record_export(user_id: int, export: dict) -> None:
    """Write the 'data_exported' audit row (counts only, never the data)."""
    tables = export["tables"]
    with get_session() as session:
        audit_service.audit(session, user_id, "data_exported", {
            "tables": len(tables), "rows": sum(len(t["rows"]) for t in tables.values()),
        })
        session.commit()


def build_user_export(user_id: int) -> dict:
    """Everything stored for the user. Raises LookupError when the account is missing or deleted."""
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None or user.deleted_at is not None:
            raise LookupError("account not available")
        user_row = _row(User.__table__, {c.name: getattr(user, c.name) for c in User.__table__.columns},
                        "id", set())
        tables = {t.name: _table_export(session, t, user_id) for t in exported_tables()}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "user": {k: user_row[k] for k in ("id", "username", "display_name", "created_at")},
        "tables": tables,
        "purposes": dict(CONSENT_PURPOSES),
        "processors": PROCESSORS,
        "notes": NOTES,
    }

