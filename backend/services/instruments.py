"""Instrument master: NSE EQUITY_L refresh, monotonic identity upserts and ISIN/symbol resolution.

An instrument keeps its id across renames and ISIN changes; the old value moves
to instrument_aliases. Every writer (EQUITY_L, the EOD mirror, AMFI) goes through
upsert_eq_identity / upsert_mf, which never let older data overwrite newer data.
Models and get_session are imported inside functions so scripts can import the
fetch and parse helpers without a database.
"""
import csv
import io
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

EQUITY_L_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
MIN_EQUITY_ROWS = 1500
MAX_BODY_BYTES = 5 * 1024 * 1024
_KEEP_SERIES = {"EQ", "BE", "BZ"}
_ISIN_RE = re.compile(r"^IN[A-Z0-9]{10}$")
_STALE_DAYS = 10
_forbidden_logged = False


# ── fetch and parse ─────────────────────────────────────────────────────────

def fetch_equity_list(timeout: int = 30) -> str:
    """Download EQUITY_L.csv with the honest bot User-Agent (never disguised; only the public archive file is requested)."""
    global _forbidden_logged
    resp = requests.get(EQUITY_L_URL, headers={"User-Agent": settings.get_user_agent()}, timeout=timeout)
    if resp.status_code == 403:
        if not _forbidden_logged:
            _forbidden_logged = True
            logger.warning("EQUITY_L.csv returned 403; waiting for the next scheduled run")
        raise RuntimeError("EQUITY_L.csv: HTTP 403")
    resp.raise_for_status()
    body = resp.content
    if len(body) > MAX_BODY_BYTES:
        raise RuntimeError(f"EQUITY_L.csv larger than {MAX_BODY_BYTES} bytes")
    return body.decode("utf-8", errors="replace")


def _parse_listing_date(raw: str) -> Optional[date]:
    try:
        return datetime.strptime(raw.strip(), "%d-%b-%Y").date()
    except (ValueError, AttributeError):
        return None


def parse_equity_list(text: str) -> list[dict]:
    """Rows of series EQ/BE/BZ with a valid ISIN as {symbol, name, series, isin, listing_date}."""
    out: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        row = {(k or "").strip().upper(): (v or "").strip() for k, v in raw.items() if k is not None}
        symbol = row.get("SYMBOL", "").upper()
        series = row.get("SERIES", "").upper()
        isin = row.get("ISIN NUMBER", "").upper()
        if not symbol or series not in _KEEP_SERIES or not _ISIN_RE.match(isin):
            continue
        out.append({
            "symbol": symbol,
            "name": row.get("NAME OF COMPANY", "") or symbol,
            "series": series,
            "isin": isin,
            "listing_date": _parse_listing_date(row.get("DATE OF LISTING", "")),
        })
    return out


# ── identity writes ─────────────────────────────────────────────────────────

def _add_alias(session, instrument_id: int, kind: str, value: str, valid_to: Optional[date]) -> None:
    """Idempotent alias write: an existing (kind, value, instrument) keeps the later valid_to (None is oldest)."""
    from models.db_models import InstrumentAlias

    if not value:
        return
    row = (
        session.query(InstrumentAlias)
        .filter_by(kind=kind, value=value, instrument_id=instrument_id)
        .first()
    )
    if row is None:
        session.add(InstrumentAlias(instrument_id=instrument_id, kind=kind, value=value, valid_to=valid_to))
        session.flush()
    elif valid_to is not None and (row.valid_to is None or valid_to > row.valid_to):
        row.valid_to = valid_to


def _match_eq(session, symbol: Optional[str], isin: Optional[str], entity_id: Optional[str]):
    from models.db_models import Instrument, InstrumentAlias

    q = session.query(Instrument).filter(Instrument.asset_class == "EQ")
    if entity_id:
        row = q.filter(Instrument.entity_id == entity_id).first()
        if row is not None:
            return row
    if isin:
        row = (
            q.filter((Instrument.isin == isin) | (Instrument.isin_alt == isin))
            .order_by(Instrument.status.asc(), Instrument.last_seen_on.desc())
            .first()
        )
        if row is not None:
            return row
        alias = (
            session.query(Instrument)
            .join(InstrumentAlias, InstrumentAlias.instrument_id == Instrument.id)
            .filter(Instrument.asset_class == "EQ", InstrumentAlias.kind == "isin", InstrumentAlias.value == isin)
            .first()
        )
        if alias is not None:
            return alias
    if symbol:
        return q.filter(Instrument.symbol == symbol, Instrument.status == "active").first()
    return None


def _free_symbol(session, symbol: str, keep_id: Optional[int], seen_on: date) -> bool:
    """Release `symbol` from another EQ row when `seen_on` is newer than that row's data. False if it stays held."""
    from models.db_models import Instrument

    holder = (
        session.query(Instrument)
        .filter(Instrument.asset_class == "EQ", Instrument.symbol == symbol)
        .first()
    )
    if holder is None or holder.id == keep_id:
        return True
    if holder.last_seen_on is not None and seen_on < holder.last_seen_on:
        logger.warning("symbol %s is held by newer instrument %s; not reassigning", symbol, holder.id)
        return False
    _add_alias(session, holder.id, "symbol", symbol, seen_on)
    holder.symbol = None
    holder.status = "inactive"
    session.flush()
    return True


def _upsert_eq(session, *, symbol, isin, seen_on, source, name=None, series=None, listing_date=None,
               entity_id=None):
    """Returns (instrument, outcome) with outcome in inserted, renamed, isin_changed, updated, unchanged."""
    from models.db_models import Instrument

    symbol = (symbol or "").strip().upper() or None
    isin = (isin or "").strip().upper() or None
    matched = _match_eq(session, symbol, isin, entity_id)

    if matched is None:
        if symbol and not _free_symbol(session, symbol, None, seen_on):
            symbol = None
        inst = Instrument(
            asset_class="EQ", symbol=symbol, isin=isin, entity_id=entity_id, name=name or symbol or isin or "",
            series=series, listing_date=listing_date, status="active", source=source, last_seen_on=seen_on,
        )
        session.add(inst)
        session.flush()
        return inst, "inserted"

    if matched.last_seen_on is not None and seen_on < matched.last_seen_on:
        return matched, "unchanged"  # older data never touches an identity

    outcomes: set[str] = set()
    if symbol and symbol != matched.symbol and _free_symbol(session, symbol, matched.id, seen_on):
        if matched.symbol:
            _add_alias(session, matched.id, "symbol", matched.symbol, seen_on)
            outcomes.add("renamed")
        matched.symbol = symbol
    if isin and isin not in (matched.isin, matched.isin_alt):
        if matched.isin:
            _add_alias(session, matched.id, "isin", matched.isin, seen_on)
            outcomes.add("isin_changed")
        matched.isin = isin
    if entity_id and not matched.entity_id:
        matched.entity_id = entity_id
    if name:
        matched.name = name
    if series:
        matched.series = series
    if listing_date:
        matched.listing_date = listing_date
    matched.status = "active"
    matched.last_seen_on = seen_on
    session.flush()
    return matched, (next(iter(sorted(outcomes))) if outcomes else "updated")


def upsert_eq_identity(session, *, symbol, isin, seen_on, source, name=None, series=None, listing_date=None,
                       entity_id=None):
    """Match or create the EQ instrument for (entity_id, isin, symbol); monotonic in `seen_on`. No commit."""
    inst, _ = _upsert_eq(session, symbol=symbol, isin=isin, seen_on=seen_on, source=source, name=name,
                         series=series, listing_date=listing_date, entity_id=entity_id)
    return inst


def upsert_mf(session, *, scheme_code, name, isin, isin_alt, seen_on, active=True):
    """Match or create the MF instrument keyed by AMFI scheme code. No commit."""
    from models.db_models import Instrument

    code = str(scheme_code)
    isin = (isin or "").strip().upper() or None
    isin_alt = (isin_alt or "").strip().upper() or None
    inst = session.query(Instrument).filter(Instrument.amfi_scheme_code == code).first()
    if inst is None:
        inst = Instrument(asset_class="MF", symbol=None, amfi_scheme_code=code, isin=isin, isin_alt=isin_alt,
                          name=name, status="active" if active else "inactive", source="amfi",
                          last_seen_on=seen_on)
        session.add(inst)
        session.flush()
        return inst
    for column, new in (("isin", isin), ("isin_alt", isin_alt)):
        old = getattr(inst, column)
        if new and new != old:
            if old:
                _add_alias(session, inst.id, "isin", old, seen_on)
            setattr(inst, column, new)
    inst.name = name or inst.name
    inst.status = "active" if active else "inactive"
    if inst.last_seen_on is None or seen_on > inst.last_seen_on:
        inst.last_seen_on = seen_on
    session.flush()
    return inst


def get_or_create_index(session, code: str = "NIFTY50", name: str = "Nifty 50 (price index)"):
    from models.db_models import Instrument

    inst = session.query(Instrument).filter_by(asset_class="INDEX", symbol=code).first()
    if inst is None:
        inst = Instrument(asset_class="INDEX", symbol=code, name=name, status="active", source="seed")
        session.add(inst)
        session.flush()
    return inst


# ── weekly refresh ──────────────────────────────────────────────────────────

def refresh_equity_master(today: Optional[date] = None) -> dict:
    """Upsert EQUITY_L into instruments and deactivate EQ rows that left the file."""
    from core.timeutil import ist_today
    from database import get_session
    from models.db_models import Instrument
    from services import data_flags

    if not data_flags.enabled("data_instruments"):
        return {"skipped": "flag_off"}
    rows = parse_equity_list(fetch_equity_list())
    if len(rows) < MIN_EQUITY_ROWS:
        raise RuntimeError(f"EQUITY_L.csv parsed {len(rows)} rows (< {MIN_EQUITY_ROWS}); keeping the master unchanged")
    today = today or ist_today()
    counts = {"inserted": 0, "updated": 0, "renamed": 0, "isin_changed": 0, "deactivated": 0}
    with get_session() as session:
        for r in rows:
            _, outcome = _upsert_eq(session, symbol=r["symbol"], isin=r["isin"], seen_on=today,
                                    source="nse_equity_l", name=r["name"], series=r["series"],
                                    listing_date=r["listing_date"])
            if outcome in counts:
                counts[outcome] += 1
        in_file_symbols = {r["symbol"] for r in rows}
        in_file_isins = {r["isin"] for r in rows}
        cutoff = today - timedelta(days=_STALE_DAYS)
        stale = (
            session.query(Instrument)
            .filter(Instrument.asset_class == "EQ", Instrument.status == "active",
                    Instrument.last_seen_on.isnot(None), Instrument.last_seen_on < cutoff)
            .all()
        )
        for inst in stale:
            if inst.symbol in in_file_symbols or inst.isin in in_file_isins:
                continue
            inst.status = "inactive"
            counts["deactivated"] += 1
        session.commit()
    logger.info("equity master refresh: %s", counts)
    return counts


# ── lookups ─────────────────────────────────────────────────────────────────

def resolve(symbol: Optional[str] = None, isin: Optional[str] = None):
    """The instrument for an ISIN (any class, aliases included) or a symbol (EQ/INDEX, aliases included); detached."""
    from database import get_session
    from models.db_models import Instrument, InstrumentAlias
    from repositories.research_repo import normalize_symbol

    with get_session() as session:
        inst = None
        isin = (isin or "").strip().upper()
        if isin:
            inst = (
                session.query(Instrument)
                .filter((Instrument.isin == isin) | (Instrument.isin_alt == isin))
                .order_by(Instrument.status.asc(), Instrument.last_seen_on.desc())
                .first()
            )
            if inst is None:
                inst = (
                    session.query(Instrument)
                    .join(InstrumentAlias, InstrumentAlias.instrument_id == Instrument.id)
                    .filter(InstrumentAlias.kind == "isin", InstrumentAlias.value == isin)
                    .first()
                )
        elif symbol:
            sym = normalize_symbol(symbol)
            if sym:
                inst = (
                    session.query(Instrument)
                    .filter(Instrument.asset_class.in_(("EQ", "INDEX")), Instrument.symbol == sym,
                            Instrument.status == "active")
                    .first()
                )
                if inst is None:
                    aliases = (
                        session.query(InstrumentAlias)
                        .filter(InstrumentAlias.kind == "symbol", InstrumentAlias.value == sym)
                        .all()
                    )
                    # An open-ended alias (no valid_to) sorts as the newest.
                    aliases.sort(key=lambda a: (a.valid_to is None, a.valid_to or date.min), reverse=True)
                    for alias in aliases:
                        inst = session.get(Instrument, alias.instrument_id)
                        if inst is not None:
                            break
        if inst is not None:
            session.expunge(inst)
        return inst


def resolve_isin(isin: str) -> Optional[dict]:
    """CAS entry point: {asset_class, symbol, amfi_scheme_code, name, status, instrument_id} or None."""
    inst = resolve(isin=isin)
    if inst is None:
        return None
    return {
        "asset_class": inst.asset_class,
        "symbol": inst.symbol,
        "amfi_scheme_code": inst.amfi_scheme_code,
        "name": inst.name,
        "status": inst.status,
        "instrument_id": inst.id,
    }


def search_new_listings(q: str, limit: int) -> list[dict]:
    """Active series-EQ instruments that the bundled JSON directory does not know, as search results."""
    from sqlalchemy import case, func

    from database import get_session
    from models.db_models import Instrument
    from services import stock_universe

    needle = (q or "").strip().upper()
    if not needle or limit <= 0:
        return []
    escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix = func.upper(Instrument.symbol).like(escaped + "%", escape="\\")
    contains = func.upper(Instrument.name).like("%" + escaped + "%", escape="\\")
    with get_session() as session:
        rows = (
            session.query(Instrument.symbol, Instrument.name)
            .filter(Instrument.asset_class == "EQ", Instrument.status == "active", Instrument.series == "EQ",
                    Instrument.symbol.isnot(None), prefix | contains)
            .order_by(case((prefix, 0), else_=1), Instrument.symbol)
            .limit(limit * 3)
            .all()
        )
    out: list[dict] = []
    for symbol, name in rows:
        if stock_universe.by_ticker(symbol) is not None:
            continue
        out.append({"ticker": symbol, "company_name": name, "sector": "", "exchange": "NSE"})
        if len(out) >= limit:
            break
    return out
