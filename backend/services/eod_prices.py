"""Postgres mirror of the ml-engine's end-of-day export, plus display-gated price accessors.

The engine owns the one NSE downloader; this module only reads its read-only
GET /eod/{date} export into `daily_prices`. EQ and INDEX closes are returned to
user-facing callers only while the data_eod_display flag is on (NSE data rights);
mutual-fund NAVs are always returned. Callers must handle None by keeping their
existing source and labelling what they show.
"""
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from core.timeutil import IST, ist_today, utcnow

logger = logging.getLogger(__name__)

MIN_ROWS = 1000
MIRROR_DAYS = 15
_DUE_HOUR, _DUE_MINUTE = 21, 30
_ISIN_RE = re.compile(r"^IN[A-Z0-9]{10}$")
_NAV_DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y")


@dataclass(frozen=True)
class PriceFact:
    close: Decimal
    trade_date: date
    source: str
    instrument_id: int


def _last_due(now: Optional[datetime] = None) -> date:
    """The IST date once its bhavcopy is due (>= 21:30 IST), else the previous weekday."""
    now = now or utcnow()
    if now.tzinfo is None:
        now = now.replace(tzinfo=utcnow().tzinfo)
    local = now.astimezone(IST)
    if (local.hour, local.minute) >= (_DUE_HOUR, _DUE_MINUTE):
        return local.date()
    d = local.date() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _client():
    from services.research.client import MLEngineClient

    return MLEngineClient()


def _dec(value) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


# ── mirror ──────────────────────────────────────────────────────────────────

def mirror_date(d: date, *, client=None) -> int:
    """Write the engine's rows for `d` into daily_prices (replacing that date's bhavcopy rows). Returns rows written."""
    from database import get_session
    from models.db_models import DailyPrice
    from services import instruments

    client = client or _client()
    payload = client.eod(d)
    if not payload or payload.get("status") != "ok":
        return 0
    rows = payload.get("rows") or []
    if len(rows) < MIN_ROWS:
        logger.warning("eod mirror %s: only %d rows; not writing", d, len(rows))
        return 0
    now = utcnow().replace(tzinfo=None)
    with get_session() as session:
        ids: dict[str, int] = {}  # per call: nothing is cached across dates
        records: dict[int, dict] = {}
        for row in rows:
            close = _dec(row.get("close"))
            if close is None or close <= 0:
                continue
            key = row.get("entity_id") or row.get("isin") or row.get("symbol")
            if not key:
                continue
            inst_id = ids.get(key)
            if inst_id is None:
                inst = instruments.upsert_eq_identity(
                    session, symbol=row.get("symbol"), isin=row.get("isin"), entity_id=row.get("entity_id") or None,
                    seen_on=d, source="bhavcopy",
                )
                inst_id = ids[key] = inst.id
            if inst_id in records:
                continue
            records[inst_id] = {
                "instrument_id": inst_id, "trade_date": d, "open": _dec(row.get("open")),
                "high": _dec(row.get("high")), "low": _dec(row.get("low")), "close": close,
                "prev_close": _dec(row.get("prev_close")),
                "volume": int(row["volume"]) if row.get("volume") is not None else None,
                "turnover_inr": _dec(row.get("turnover_inr")),
                "trades": int(row["trades"]) if row.get("trades") is not None else None,
                "source": "nse_bhavcopy", "event": row.get("event") or None,
                "quality_flags": row.get("quality_flags") or None, "ingested_at": now,
            }
        session.query(DailyPrice).filter(
            DailyPrice.trade_date == d, DailyPrice.source == "nse_bhavcopy"
        ).delete(synchronize_session=False)
        session.flush()
        if records:
            session.bulk_insert_mappings(DailyPrice, list(records.values()))
        written = len(records)
        nifty = _dec((payload.get("index_closes") or {}).get("NIFTY50"))
        if nifty is not None and nifty > 0:
            idx = instruments.get_or_create_index(session)
            session.query(DailyPrice).filter(
                DailyPrice.instrument_id == idx.id, DailyPrice.trade_date == d
            ).delete(synchronize_session=False)
            session.add(DailyPrice(instrument_id=idx.id, trade_date=d, close=nifty, source="yfinance",
                                   ingested_at=now))
        session.commit()
    return written


def mirror_recent(*, client=None, now: Optional[datetime] = None) -> dict:
    """Mirror the last 15 calendar days ascending, asking the engine for a gap-fill first while research is off."""
    from services import data_flags
    from services.research import config as research_config
    from services.research.client import MLEngineUnavailable

    if not data_flags.enabled("data_eod_prices"):
        return {"skipped": "flag_off"}
    cfg = research_config.CONFIG
    if not cfg.ml_engine_api_key:
        return {"skipped": "ml_engine_unconfigured"}
    client = client or _client()
    last_due = _last_due(now)
    sync = "skipped:research_runs"  # research runs gap-fill themselves
    dates_written = 0
    rows = 0
    try:
        if cfg.mode == "off":
            sync = client.marketdata_sync(last_due)
        for offset in range(MIRROR_DAYS - 1, -1, -1):
            n = mirror_date(last_due - timedelta(days=offset), client=client)
            if n:
                dates_written += 1
                rows += n
    except MLEngineUnavailable:
        return {"error": "ml_engine_unavailable", "sync": sync, "dates_written": dates_written}
    return {"sync": sync, "dates_written": dates_written, "rows": rows}


# ── accessors ───────────────────────────────────────────────────────────────

def _parse_nav_date(raw) -> Optional[date]:
    for fmt in _NAV_DATE_FORMATS:
        try:
            return datetime.strptime(str(raw).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _display_allowed(asset_class: str, for_display: bool) -> bool:
    from services import data_flags

    return asset_class == "MF" or not for_display or data_flags.enabled("data_eod_display")


def _latest_by_instrument(session, ids: Iterable[int], lo: date, hi: date) -> dict[int, "PriceFact"]:
    from models.db_models import DailyPrice

    out: dict[int, PriceFact] = {}
    rows = (
        session.query(DailyPrice)
        .filter(DailyPrice.instrument_id.in_(list(ids)), DailyPrice.trade_date >= lo, DailyPrice.trade_date <= hi)
        .order_by(DailyPrice.trade_date.desc())
        .all()
    )
    for r in rows:
        if r.instrument_id in out or "suspect" in (r.quality_flags or ""):
            continue
        out[r.instrument_id] = PriceFact(Decimal(str(r.close)), r.trade_date, r.source, r.instrument_id)
    return out


def _mf_nav_fallback(session, inst, lo: date, hi: date) -> Optional[PriceFact]:
    from models.db_models import MutualFund

    if not inst.amfi_scheme_code:
        return None
    mf = session.query(MutualFund).filter(MutualFund.scheme_code == inst.amfi_scheme_code).first()
    if mf is None or mf.nav is None or not mf.nav_date:
        return None
    nav_date = _parse_nav_date(mf.nav_date)
    if nav_date is None or not (lo <= nav_date <= hi) or mf.nav <= 0:
        return None
    return PriceFact(Decimal(str(mf.nav)), nav_date, "amfi_latest", inst.id)


def get_close(symbol: Optional[str] = None, *, isin: Optional[str] = None, on: Optional[date] = None,
              max_age_days: int = 7, for_display: bool = True) -> Optional[PriceFact]:
    """Latest stored close within `max_age_days` of `on` (default today IST), or None.

    EQ and INDEX closes are withheld from user-facing callers (for_display=True)
    while data_eod_display is off; MF NAVs are always served. Suspect rows are
    skipped. On None callers keep their existing source (today yfinance) and label
    what they show.
    """
    from database import get_session
    from services import instruments

    inst = instruments.resolve(symbol=symbol, isin=isin)
    if inst is None or not _display_allowed(inst.asset_class, for_display):
        return None
    hi = on or ist_today()
    lo = hi - timedelta(days=max_age_days)
    with get_session() as session:
        fact = _latest_by_instrument(session, [inst.id], lo, hi).get(inst.id)
        if fact is None and inst.asset_class == "MF":
            fact = _mf_nav_fallback(session, inst, lo, hi)
        return fact


def get_closes(identifiers: Iterable[str], *, on: Optional[date] = None, max_age_days: int = 7,
               for_display: bool = True) -> dict[str, Optional[PriceFact]]:
    """get_close for many identifiers (ISINs match ^IN[A-Z0-9]{10}$, anything else is a symbol) with one price query."""
    from database import get_session
    from services import instruments

    resolved: dict[str, object] = {}
    for ident in dict.fromkeys(i for i in identifiers if i):
        norm = ident.strip().upper()
        inst = instruments.resolve(isin=norm) if _ISIN_RE.match(norm) else instruments.resolve(symbol=ident)
        if inst is not None and _display_allowed(inst.asset_class, for_display):
            resolved[ident] = inst
    hi = on or ist_today()
    lo = hi - timedelta(days=max_age_days)
    out: dict[str, Optional[PriceFact]] = {i: None for i in dict.fromkeys(i for i in identifiers if i)}
    if not resolved:
        return out
    with get_session() as session:
        facts = _latest_by_instrument(session, {i.id for i in resolved.values()}, lo, hi)
        for ident, inst in resolved.items():
            fact = facts.get(inst.id)
            if fact is None and inst.asset_class == "MF":
                fact = _mf_nav_fallback(session, inst, lo, hi)
            out[ident] = fact
    return out


def index_close(code: str = "NIFTY50", on: Optional[date] = None, max_age_days: int = 7,
                for_display: bool = True) -> Optional[PriceFact]:
    return get_close(code, on=on, max_age_days=max_age_days, for_display=for_display)
