"""NSE capital-market bhavcopy: URLs, a polite downloader and parsers (spec 3.1, 3.2).

Both the legacy file (to 2024-07-05) and the UDiFF file (from 2024-07-08) are
parsed into the same common columns, keeping only ``series == "EQ"``. A missing
column raises ``BhavcopySchemaError``, which fails the run closed.

The downloader identifies itself honestly as
``NiveshResearch/1.0 (+{RESEARCH_HTTP_CONTACT})`` and refuses to run without that
variable. If NSE blocks it, never disguise the client: use a licensed vendor.
Unit tests never use the downloader.
"""

from __future__ import annotations

import io
import os
import random
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date

import pandas as pd

LEGACY_LAST = date(2024, 7, 5)  # last legacy file; UDiFF from 2024-07-08
MIN_INTERVAL_S = 2.5  # one request per 2.5 s plus jitter
MAX_FILE_BYTES = 64 * 1024 * 1024  # refuse anything larger (a bhavcopy is ~1 MB unzipped)

COMMON_COLUMNS = (
    "date", "symbol", "series", "isin", "open", "high", "low", "close",
    "prev_close", "volume", "turnover_inr", "trades",
)
_NUMERIC = ("open", "high", "low", "close", "prev_close", "volume", "turnover_inr", "trades")

# Source column -> common column.
LEGACY_COLUMNS = {
    "SYMBOL": "symbol", "SERIES": "series", "ISIN": "isin",
    "OPEN": "open", "HIGH": "high", "LOW": "low", "CLOSE": "close",
    "PREVCLOSE": "prev_close", "TOTTRDQTY": "volume", "TOTTRDVAL": "turnover_inr",
    "TOTALTRADES": "trades", "TIMESTAMP": "date",
}
# [verify on the first live file] (spec 3.2)
UDIFF_COLUMNS = {
    "TckrSymb": "symbol", "SctySrs": "series", "ISIN": "isin",
    "OpnPric": "open", "HghPric": "high", "LwPric": "low", "ClsPric": "close",
    "PrvsClsgPric": "prev_close", "TtlTradgVol": "volume", "TtlTrfVal": "turnover_inr",
    "TtlNbOfTxsExctd": "trades", "TradDt": "date",
}
_DATE_FORMATS = {"legacy": "%d-%b-%Y", "udiff": "%Y-%m-%d"}
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


class BhavcopySchemaError(ValueError):
    """The file does not have the columns (or value formats) this parser expects.

    The format changed under us, so the run fails closed.
    """


class BadBhavcopyFile(ValueError):
    """Not a readable bhavcopy (bad zip, HTML error page, oversized). Treated as missing."""


def bhavcopy_url(d: date) -> str:
    """Archive URL of the CM bhavcopy for session ``d`` (legacy or UDiFF by date)."""
    if d <= LEGACY_LAST:
        mon = _MONTHS[d.month - 1]
        return (
            "https://nsearchives.nseindia.com/content/historical/EQUITIES/"
            f"{d.year}/{mon}/cm{d.day:02d}{mon}{d.year}bhav.csv.zip"
        )
    return (
        "https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
    )


def _csv_bytes(data: bytes) -> bytes:
    if not data.startswith(b"PK"):
        if data.lstrip()[:1] == b"<":
            raise BadBhavcopyFile("got an HTML/XML page instead of a bhavcopy")
        return data
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.infolist() if m.filename.lower().endswith(".csv")]
        if len(members) != 1:
            raise BadBhavcopyFile(f"expected one CSV in the zip, found {len(members)}")
        if members[0].file_size > MAX_FILE_BYTES:
            raise BadBhavcopyFile("bhavcopy CSV is implausibly large")
        return zf.read(members[0])


def parse_bhavcopy(data: bytes) -> pd.DataFrame:
    """Parse a zipped (or plain) legacy or UDiFF bhavcopy into ``COMMON_COLUMNS``.

    Only EQ rows are kept. Prices, volume, turnover and trades are float64,
    ``date`` is datetime64[ns]. Raises ``BhavcopySchemaError`` on a missing column
    or bad value and ``BadBhavcopyFile`` when the bytes are not a readable CSV.
    """
    try:
        raw = pd.read_csv(io.BytesIO(_csv_bytes(data)), dtype=str, skipinitialspace=True)
    except (zipfile.BadZipFile, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise BadBhavcopyFile(f"unreadable bhavcopy: {exc}") from exc
    raw.columns = [str(c).strip() for c in raw.columns]
    kind, mapping = ("udiff", UDIFF_COLUMNS) if "TckrSymb" in raw.columns else ("legacy", LEGACY_COLUMNS)
    missing = sorted(set(mapping) - set(raw.columns))
    if missing:
        raise BhavcopySchemaError(f"{kind} bhavcopy is missing columns: {', '.join(missing)}")
    df = raw.loc[:, list(mapping)].rename(columns=mapping)
    for col in ("symbol", "series", "isin"):
        df[col] = df[col].fillna("").str.strip()
    df = df.loc[df["series"] == "EQ"].copy()
    try:
        df["date"] = pd.to_datetime(df["date"].str.strip(), format=_DATE_FORMATS[kind])
        for col in _NUMERIC:
            df[col] = df[col].str.strip().astype("float64")
    except (ValueError, TypeError) as exc:
        raise BhavcopySchemaError(f"bad value in {kind} bhavcopy: {exc}") from exc
    df["date"] = df["date"].astype("datetime64[ns]")
    return df.loc[:, list(COMMON_COLUMNS)].sort_values("symbol", kind="stable").reset_index(drop=True)


def user_agent() -> str:
    """The honest User-Agent. Raises if RESEARCH_HTTP_CONTACT is unset."""
    contact = os.environ.get("RESEARCH_HTTP_CONTACT", "").strip()
    if not contact:
        raise RuntimeError("RESEARCH_HTTP_CONTACT is not set; the bhavcopy downloader refuses to run")
    return f"NiveshResearch/1.0 (+{contact})"


class Downloader:
    """Throttled bhavcopy fetcher: at most one request per 2.5 s plus jitter."""

    def __init__(self, min_interval: float = MIN_INTERVAL_S, timeout: float = 30.0) -> None:
        self.user_agent = user_agent()
        self.min_interval = min_interval
        self.timeout = timeout
        self._last = 0.0

    def fetch(self, d: date) -> bytes | None:
        """Raw zip bytes for session ``d``; None on 404 (no session). Other errors raise."""
        wait = self._last + self.min_interval + random.uniform(0.0, 1.0) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            bhavcopy_url(d), headers={"User-Agent": self.user_agent, "Accept": "*/*"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read(MAX_FILE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        finally:
            self._last = time.monotonic()
        if len(body) > MAX_FILE_BYTES:
            raise BadBhavcopyFile("bhavcopy download is implausibly large")
        return body
