"""Results digest: the NSE financial-results RSS link plus three numbers from Yahoo Finance.

For held and watched stocks only: the RSS gives the filing link and quarter, yfinance
quarterly statements give revenue, net profit and EPS with year-on-year change. No
generated text of any kind: the payload carries figures, dates, a link and a source
note, and the filing stays the official source.
"""
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

from config import settings

logger = logging.getLogger(__name__)

FIN_RESULTS_RSS = "https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml"
MAX_FEED_BYTES = 2 * 1024 * 1024
PENDING_GIVE_UP_DAYS = 10
MAX_HELD_SYMBOLS = 500
_DATE_RE = re.compile(r"\b(\d{1,2})-([A-Za-z]{3})-(\d{4})\b")
_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))
_REVENUE_LABELS = ("Total Revenue", "Operating Revenue")
_PROFIT_LABELS = ("Net Income", "Net Income Common Stockholders",
                  "Net Income From Continuing Operation Net Minority Interest")
_EPS_LABELS = ("Diluted EPS", "Basic EPS")
_CURRENT_WINDOW_DAYS = 5
_YEAR_AGO_WINDOW_DAYS = 10

_feed_state: dict[str, Optional[str]] = {"etag": None, "last_modified": None}


# ── feed ────────────────────────────────────────────────────────────────────

def fetch_feed(timeout: int = 20) -> Optional[bytes]:
    """Conditional GET of the RSS; None when it has not changed (304)."""
    headers = {"User-Agent": settings.get_user_agent()}
    if _feed_state["etag"]:
        headers["If-None-Match"] = _feed_state["etag"]
    if _feed_state["last_modified"]:
        headers["If-Modified-Since"] = _feed_state["last_modified"]
    resp = requests.get(FIN_RESULTS_RSS, headers=headers, timeout=timeout)
    if resp.status_code == 304:
        return None
    resp.raise_for_status()
    if len(resp.content) > MAX_FEED_BYTES:
        raise RuntimeError("Financial results feed larger than 2 MB")
    _feed_state["etag"] = resp.headers.get("ETag")
    _feed_state["last_modified"] = resp.headers.get("Last-Modified")
    return resp.content


def parse_feed(xml) -> list[dict]:
    """Items of channel/item as {title, link, description, published}; malformed items are skipped."""
    raw = xml if isinstance(xml, bytes) else str(xml).encode("utf-8")
    if len(raw) > MAX_FEED_BYTES or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        logger.warning("results feed is not valid XML")
        return []
    items: list[dict] = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        if not title or not link:
            continue
        try:
            published = parsedate_to_datetime((node.findtext("pubDate") or "").strip())
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        items.append({"title": title, "link": link, "published": published,
                      "description": (node.findtext("description") or "").strip()})
    return items


# ── symbol and period ───────────────────────────────────────────────────────

def _normalise_name(name: str) -> str:
    text = name.upper().replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+(LIMITED|LTD)$", "", text).strip()


def _name_index(session) -> dict[str, list[str]]:
    from models.db_models import Instrument

    index: dict[str, list[str]] = {}
    rows = session.query(Instrument.symbol, Instrument.name).filter(
        Instrument.asset_class == "EQ", Instrument.status == "active", Instrument.symbol.isnot(None)
    )
    for symbol, name in rows:
        index.setdefault(_normalise_name(name), []).append(symbol)
    return index


def item_symbol(item: dict, session, name_index: Optional[dict[str, list[str]]] = None) -> Optional[str]:
    """The NSE symbol from the link's `symbol` parameter, else a company name matching exactly one active EQ row."""
    # [verify on the first live fetch] the real feed's link shape is unconfirmed.
    params = parse_qs(urlparse(item["link"]).query)
    for key, values in params.items():
        if key.lower() == "symbol" and values and re.match(r"^[A-Za-z0-9&-]{1,20}$", values[0].strip()):
            return values[0].strip().upper()
    company = _normalise_name(item["title"].split(" - ")[0])
    if not company:
        return None
    matches = (name_index if name_index is not None else _name_index(session)).get(company, [])
    return matches[0] if len(set(matches)) == 1 else None


def _last_quarter_end(before: date, inclusive: bool) -> date:
    candidates = [date(y, m, d) for y in (before.year - 1, before.year) for m, d in _QUARTER_ENDS]
    ok = [c for c in candidates if (c <= before if inclusive else c < before)]
    return max(ok)


def item_period_end(item: dict) -> date:
    """The latest quarter-end date in the description that is not after the publish date; else the last one before it."""
    published = item["published"].date()
    found: list[date] = []
    for day, mon, year in _DATE_RE.findall(item["description"]):
        try:
            d = datetime.strptime(f"{day}-{mon.title()}-{year}", "%d-%b-%Y").date()
        except ValueError:
            continue
        if (d.month, d.day) in _QUARTER_ENDS and d <= published:
            found.append(d)
    return max(found) if found else _last_quarter_end(published, inclusive=False)


# ── jobs ────────────────────────────────────────────────────────────────────

def poll_feed_job() -> dict:
    """Record a pending digest for each new (held or watched symbol, quarter) in the feed."""
    from database import get_session
    from models.db_models import ResultsDigest
    from repositories import research_repo
    from services import data_flags

    if not data_flags.any_enabled("data_results_digest"):
        return {"skipped": "flag_off"}
    try:
        body = fetch_feed()
    except Exception as exc:
        logger.warning("results feed unavailable: %s", exc)
        return {"error": "feed_unavailable"}
    if body is None:
        return {"status": "not_modified"}
    counts = {"items": 0, "inserted": 0, "unmatched": 0}
    with get_session() as session:
        held = set(research_repo.extra_symbols(session, cap=MAX_HELD_SYMBOLS))
        index = _name_index(session)
        for item in parse_feed(body):
            counts["items"] += 1
            symbol = item_symbol(item, session, index)
            if symbol is None or symbol not in held:
                counts["unmatched"] += 1
                continue
            period_end = item_period_end(item)
            exists = session.query(ResultsDigest.id).filter_by(symbol=symbol, period_end=period_end).first()
            if exists:
                continue  # first item wins
            session.add(ResultsDigest(
                symbol=symbol, period_end=period_end, filing_url=item["link"][:500],
                filing_title=item["title"][:300],
                announced_at=item["published"].astimezone(timezone.utc).replace(tzinfo=None),
                numbers_status="pending",
            ))
            session.flush()
            counts["inserted"] += 1
        session.commit()
    return counts


def _quarterly_income(symbol: str):
    """Yahoo quarterly income statement (labels as rows, period-end dates as columns); None on failure."""
    import yfinance as yf

    from services.rate_limiter import yf_acquire

    yf_acquire()
    return yf.Ticker(symbol + ".NS").quarterly_income_stmt


def _column_near(frame, target: date, window_days: int):
    best, best_gap = None, None
    for col in frame.columns:
        try:
            d = col.date() if hasattr(col, "date") else date.fromisoformat(str(col)[:10])
        except ValueError:
            continue
        gap = abs((d - target).days)
        if gap <= window_days and (best_gap is None or gap < best_gap):
            best, best_gap = col, gap
    return best


def _value(frame, col, labels: tuple[str, ...]) -> Optional[float]:
    if col is None:
        return None
    for label in labels:
        if label in frame.index:
            raw = frame.at[label, col]
            try:
                number = float(raw)
            except (TypeError, ValueError):
                continue
            if number == number:  # not NaN
                return number
    return None


def _yoy(cur: Optional[float], prev: Optional[float]) -> Optional[float]:
    if cur is None or prev is None or prev <= 0:
        return None
    return round((cur - prev) / prev * 100, 1)


def _dec(value: Optional[float]) -> Optional[Decimal]:
    return None if value is None else Decimal(str(round(value, 2)))


def fill_pending_numbers(today: Optional[date] = None, max_calls: int = 150) -> dict:
    """Fetch the three numbers for pending digests; rows pending past 10 days after the announcement give up."""
    from core.timeutil import ist_today, utcnow
    from database import get_session
    from models.db_models import ResultsDigest
    from services import data_flags

    if not data_flags.any_enabled("data_results_digest"):
        return {"skipped": "flag_off"}
    today = today or ist_today()
    counts = {"filled": 0, "unavailable": 0, "still_pending": 0, "calls": 0}
    now = utcnow().replace(tzinfo=None)
    with get_session() as session:
        pending = session.query(ResultsDigest).filter_by(numbers_status="pending").order_by(ResultsDigest.id).all()
        for row in pending:
            announced = row.announced_at.date() if row.announced_at else row.period_end
            too_old = (today - announced).days > PENDING_GIVE_UP_DAYS
            if counts["calls"] >= max_calls:
                counts["still_pending"] += 1
                continue
            counts["calls"] += 1
            filled = False
            try:
                frame = _quarterly_income(row.symbol)
                col = _column_near(frame, row.period_end, _CURRENT_WINDOW_DAYS) if frame is not None else None
                if col is not None:
                    prev_col = _column_near(frame, row.period_end - timedelta(days=365), _YEAR_AGO_WINDOW_DAYS)
                    cur = {k: _value(frame, col, labels) for k, labels in
                           (("rev", _REVENUE_LABELS), ("profit", _PROFIT_LABELS), ("eps", _EPS_LABELS))}
                    prev = {k: _value(frame, prev_col, labels) for k, labels in
                            (("rev", _REVENUE_LABELS), ("profit", _PROFIT_LABELS), ("eps", _EPS_LABELS))}
                    if cur["rev"] is not None and cur["profit"] is not None:
                        row.revenue_inr, row.net_profit_inr, row.eps = _dec(cur["rev"]), _dec(cur["profit"]), _dec(cur["eps"])
                        row.revenue_yoy_pct = _yoy(cur["rev"], prev["rev"])
                        row.net_profit_yoy_pct = _yoy(cur["profit"], prev["profit"])
                        row.eps_yoy_pct = _yoy(cur["eps"], prev["eps"])
                        row.numbers_status, row.numbers_source, row.numbers_fetched_at = "ok", "yahoo_finance", now
                        counts["filled"] += 1
                        filled = True
            except Exception:
                logger.exception("results numbers for %s failed", row.symbol)
                counts["still_pending"] += 1
                continue  # a per-symbol failure leaves the row pending
            if not filled:
                if too_old:
                    row.numbers_status = "unavailable"
                    counts["unavailable"] += 1
                else:
                    counts["still_pending"] += 1
        session.commit()
    return counts


# ── API payload ─────────────────────────────────────────────────────────────

def _fmt_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _num(value) -> Optional[float]:
    return None if value is None else float(value)


def digest_payload(row) -> dict:
    """The API body for one digest row: figures, dates, filing link and the source note."""
    if row.numbers_status == "ok":
        fetched = row.numbers_fetched_at.date() if row.numbers_fetched_at else row.period_end
        note = (f"Figures from Yahoo Finance quarterly statements, fetched {_fmt_date(fetched)}. "
                "The company's exchange filing is the official source.")
    elif row.numbers_status == "unavailable":
        note = "Figures aren't available from our data source. See the company's filing."
    else:
        note = "Figures are still being collected from our data source. See the company's filing."
    return {
        "symbol": row.symbol,
        "period_end": row.period_end.isoformat(),
        "period_label": f"Quarter ended {_fmt_date(row.period_end)}",
        "filing_url": row.filing_url,
        "filing_title": row.filing_title,
        "announced_at": row.announced_at.isoformat() if row.announced_at else None,
        "numbers_status": row.numbers_status,
        "revenue_inr": _num(row.revenue_inr),
        "revenue_yoy_pct": row.revenue_yoy_pct,
        "net_profit_inr": _num(row.net_profit_inr),
        "net_profit_yoy_pct": row.net_profit_yoy_pct,
        "eps": _num(row.eps),
        "eps_yoy_pct": row.eps_yoy_pct,
        "numbers_source_text": note,
    }


def latest_digest(symbol: str) -> Optional[dict]:
    from database import get_session
    from models.db_models import ResultsDigest

    with get_session() as session:
        row = session.query(ResultsDigest).filter_by(symbol=symbol).order_by(ResultsDigest.period_end.desc()).first()
        return digest_payload(row) if row is not None else None
