"""
Nivesh SEBI registry: the single source of SEBI registration claims.

Every INH (research analyst) / INA (investment adviser) number the backend serves
comes from REGISTERED_CHANNELS. No other backend module may contain one; the test
tests/test_sebi_registry_claims.py enforces it. Never add an entry without a number
confirmed on SEBI's recognised-intermediaries list (siportal.sebi.gov.in).

REGISTRY_VERIFIED_ON is a human attestation: SEBI publishes no machine-readable
export of RA/IA registrations, so someone re-checks every number by hand and records
the date. Badges fail closed: when the date is unset, in the future or more than
REGISTRY_MAX_AGE_DAYS (90) old, registration_for_channel returns None and
/api/v1/ideas/advisors is empty, so badges disappear on their own. The daily
sebi_registry_check job alerts from REGISTRY_REMIND_AFTER_DAYS (75) onwards.
Harvesting keeps using REGISTERED_CHANNELS regardless.
"""
from datetime import date

from core.timeutil import ist_today

# Date (YYYY-MM-DD) someone last re-checked every number below on SEBI's
# recognised-intermediaries list. None: not re-checked since the 2026-10 audit.
REGISTRY_VERIFIED_ON: str | None = None
REGISTRY_MAX_AGE_DAYS = 90
REGISTRY_REMIND_AFTER_DAYS = 75

# Owner's note: every entry verified against SEBI public RA/IA registry, June 2026.
# sebi_reg is mandatory. Only SEBI-registered advisors with 100k+ YouTube subscribers.
# channel_id is set only where the advisor harvester tracks the channel.
REGISTERED_CHANNELS = [
    {
        "name": "Finology with Pranjal",
        "channel_url": "https://www.youtube.com/@pranjalkamra/videos",
        "sebi_reg": "INH000024277",
        "entity": "Finology Ventures Pvt. Ltd.",
        "tags": ["education", "fundamental", "value_investing", "hindi"],
    },
    {
        "name": "Yadnya Investment Academy",
        "channel_url": "https://www.youtube.com/@InvestYadnya/videos",
        "sebi_reg": "INH000008349",
        "entity": "Yadnya Academy Pvt. Ltd.",
        "tags": ["education", "fundamental", "mutual_fund", "hindi"],
    },
    {
        "name": "Elearnmarkets",
        "channel_url": "https://www.youtube.com/c/Elearnmarkets/videos",
        "sebi_reg": "INH300007493",
        "entity": "StockEdge Fintech Pvt. Ltd.",
        "tags": ["education", "technical", "trading", "courses"],
    },
    {
        "name": "WeekendInvesting",
        "channel_url": "https://www.youtube.com/@AlokJain/videos",
        "sebi_reg": "INH100008717",
        "entity": "Weekendinvesting Analytics Pvt. Ltd.",
        "tags": ["momentum", "smallcase", "portfolio", "longterm"],
    },
    {
        "name": "Equityrush",
        "channel_url": "https://www.youtube.com/channel/UCEk5D5RfUgAJd3VfCz3vWTw/videos",
        "sebi_reg": "INH100001609",
        "entity": "Kunal Saraogi",
        "tags": ["technical", "trading", "price_action", "charts"],
    },
    {
        "name": "Capitalmind",
        "channel_url": "https://www.youtube.com/@CapitalmindHQ/videos",
        "sebi_reg": "INH000014003",
        "entity": "Capitalmind Research LLP",
        "tags": ["quant", "macro", "data_driven", "mutual_fund"],
    },
    {
        "name": "Finance With Sunil",
        "channel_url": "https://www.youtube.com/@financewithsunil1/videos",
        "sebi_reg": "INH000014261",
        "entity": "Alphamojo Financial Services Pvt. Ltd.",
        "tags": ["technical", "price_action", "trading", "breakout"],
    },
    {
        "name": "AryaaMoney",
        "channel_url": "https://www.youtube.com/@AryaaMoney/videos",
        "sebi_reg": "INA000002405",
        "entity": "Aryaa Money Pvt. Ltd.",
        "tags": ["education", "fundamental", "trading", "financial_literacy"],
    },
    {
        "name": "SOIC",
        "channel_url": "https://www.youtube.com/@soicfinance/videos",
        "channel_id": "UCB7GnQlJPIL6rBBqEoX87vA",
        "sebi_reg": "INH000012582",
        "entity": "SOIC Intelligent Research LLP",
        "tags": ["fundamental", "deep_dive", "smallcap", "microcap"],
    },
    {
        "name": "Basant Maheshwari",
        "channel_url": "https://www.youtube.com/@BMTheEquityDesk/videos",
        "channel_id": "UCqvuLvdIkUjAtSFrKw5LhXg",
        "sebi_reg": "INH000017949",
        "entity": "Basant Maheshwari Wealth Advisers LLP",
        "tags": ["portfolio", "largecap", "consumer", "longterm"],
    },
    {
        "name": "Anand Rathi",
        "channel_url": "https://www.youtube.com/@AnandRathiOfficial/videos",
        "sebi_reg": "INH000000834",
        "entity": "Anand Rathi Share and Stock Brokers Ltd",
        "tags": ["institutional", "research", "largecap", "sector_calls"],
    },
    {
        "name": "Motilal Oswal",
        "channel_url": "https://www.youtube.com/@motilaloswalofficial/videos",
        "sebi_reg": "INH000000412",
        "entity": "Motilal Oswal Financial Services Ltd",
        "tags": ["institutional", "bluechip", "research", "market_outlook"],
    },
]


def registration_for_channel(channel_id: str | None = None, name: str | None = None) -> str | None:
    """SEBI registration number of a registered channel, else None.

    A channel_id, when given, decides alone: it never falls back to the name, so an
    unregistered channel cannot borrow a registered entity's name. Returns None for
    every channel while the registry is not fresh (registry_is_fresh).
    """
    if not registry_is_fresh():
        return None
    if channel_id:
        matches = [c for c in REGISTERED_CHANNELS if c.get("channel_id") == channel_id]
    else:
        key = (name or "").strip().casefold()
        matches = [c for c in REGISTERED_CHANNELS if key and c["name"].casefold() == key]
    return matches[0]["sebi_reg"] if matches else None


def registry_age_days(today: date | None = None) -> int | None:
    """Days since REGISTRY_VERIFIED_ON (negative if in the future); None if unset or unparseable."""
    try:
        verified = date.fromisoformat(REGISTRY_VERIFIED_ON or "")
    except (TypeError, ValueError):
        return None
    return ((today or ist_today()) - verified).days


def registry_is_fresh(today: date | None = None) -> bool:
    """True when the registry was re-checked 0..REGISTRY_MAX_AGE_DAYS days ago (a future date is invalid)."""
    age = registry_age_days(today)
    return age is not None and 0 <= age <= REGISTRY_MAX_AGE_DAYS


def registration_type(sebi_reg: str) -> str:
    """'Research Analyst' for an INH number, 'Investment Adviser' for INA, else 'Unknown'."""
    prefix = (sebi_reg or "").strip().upper()[:3]
    return {"INH": "Research Analyst", "INA": "Investment Adviser"}.get(prefix, "Unknown")


def check_registry_freshness() -> dict:
    """Daily sebi_registry_check job: raise (so job_runs alerts) once a re-check is due.

    Raises from REGISTRY_REMIND_AFTER_DAYS onwards, and when the date is unset or in
    the future (badges are already off then); otherwise returns {'age_days': n}.
    """
    age = registry_age_days()
    if age is None or age < 0 or age >= REGISTRY_REMIND_AFTER_DAYS:
        if age is None or age < 0:
            when = "never (date unset, invalid or in the future)"
        else:
            when = f"{age} days ago"
        raise RuntimeError(
            f"SEBI registry last verified {when}; re-check every INH/INA number on SEBI's "
            "recognised intermediaries list and update REGISTRY_VERIFIED_ON"
        )
    return {"age_days": age}
