"""Server-side feature flags: the one choke point for every new surface.

Each flag is an env var read on every call, so changing one needs a backend
restart (systemd reloads backend/.env), never an App Store release. iOS reads
the same values from GET /api/v1/features and treats unknown keys as off.

Register a flag here, document it in backend/.env.example, and gate its routes
with Depends(require_flag("key")). GET /api/v1/app-config (iOS cluster) serves
the iOS flags with their effective rules, the research mode and the minimum
iOS build; ios_min_build() is also the value any 426 version gate must use.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# key -> (env var, default). Money cluster (docs: spec_money 2.1). Family
# portfolios (I36) are not built and have no flag.
FLAGS: dict[str, tuple[str, bool]] = {
    "money_holding_detail": ("FEATURE_MONEY_HOLDING_DETAIL", True),
    "money_xirr_card": ("FEATURE_MONEY_XIRR_CARD", True),
    "money_journal_scoring": ("FEATURE_MONEY_JOURNAL_SCORING", True),
    "money_cas_import": ("FEATURE_MONEY_CAS_IMPORT", False),
    "money_xray": ("FEATURE_MONEY_XRAY", False),
    "money_commission_drag": ("FEATURE_MONEY_COMMISSION_DRAG", False),
    "money_tax_report": ("FEATURE_MONEY_TAX_REPORT", False),
    "money_crisis_replay": ("FEATURE_MONEY_CRISIS_REPLAY", False),
    # Habit cluster (docs: spec_habit 0.2).
    "notif_prefs_v2": ("FEATURE_NOTIF_PREFS_V2", False),
    "today_brief": ("FEATURE_TODAY_BRIEF", False),
    "event_radar": ("FEATURE_EVENT_RADAR", False),
    "watchlist_v2": ("FEATURE_WATCHLIST_V2", False),
    "widget_snapshot": ("FEATURE_WIDGET_SNAPSHOT", True),  # kill switch
    # iOS cluster (spec_ios 1). The three research-data flags show Yahoo Finance
    # fundamentals: on only after legal item (f) and RESEARCH_ENGINE_MODE=on.
    "stock_action_bar": ("FEATURE_STOCK_ACTION_BAR", True),
    "stock_key_facts": ("FEATURE_STOCK_KEY_FACTS", False),
    "stock_peers": ("FEATURE_STOCK_PEERS", False),
    "compare": ("FEATURE_COMPARE", False),
    "onboarding_v2": ("FEATURE_ONBOARDING_V2", True),
    "home_bell_inbox": ("FEATURE_HOME_BELL_INBOX", True),
    "hindi_glossary": ("FEATURE_HINDI_GLOSSARY", False),
    "hindi_brief": ("FEATURE_HINDI_BRIEF", False),
}

# Flags that also accept "shadow": the backend does the work (e.g. ingest) but
# nothing reaches users. Shadow reads as off everywhere except mode().
TRI_STATE: frozenset[str] = frozenset({"event_radar"})

# app-config flag name -> registry key. cas_import is the money cluster's CAS
# import (I28), so FEATURE_MONEY_CAS_IMPORT drives both surfaces.
IOS_FLAGS: dict[str, str] = {
    "stock_action_bar": "stock_action_bar",
    "stock_key_facts": "stock_key_facts",
    "stock_peers": "stock_peers",
    "compare": "compare",
    "onboarding_v2": "onboarding_v2",
    "home_bell_inbox": "home_bell_inbox",
    "hindi_glossary": "hindi_glossary",
    "hindi_brief": "hindi_brief",
    "cas_import": "money_cas_import",
}
_RESEARCH_GATED = frozenset({"stock_key_facts", "stock_peers", "compare"})
_APP_STORE_PREFIX = "https://apps.apple.com/"

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_warned: set[str] = set()  # keys already warned about an unparseable value


def mode(key: str) -> str:
    """'on', 'off', or 'shadow' (TRI_STATE keys only). Unknown key -> KeyError (a typo must not ungate a route)."""
    env_name, default = FLAGS[key]
    raw = os.environ.get(env_name)
    if raw is not None:
        token = raw.strip().lower()
        if token in _TRUE:
            return "on"
        if token in _FALSE:
            return "off"
        if token == "shadow" and key in TRI_STATE:
            return "shadow"
        if key not in _warned:
            _warned.add(key)
            logger.warning("%s has an unrecognised value; using the default (%s)", env_name, default)
    return "on" if default else "off"


def is_enabled(key: str) -> bool:
    """Current value of flag `key`; shadow reads as off."""
    return mode(key) == "on"


def _warn_once(tag: str, level: int, msg: str, *args) -> None:
    if tag not in _warned:
        _warned.add(tag)
        logger.log(level, msg, *args)


def research_mode() -> str:
    """Effective research engine mode (off|shadow|on); 'off' on any failure."""
    try:
        from services.research import config as research_config

        mode = research_config.CONFIG.mode
    except Exception:
        return "off"
    return mode if mode in ("off", "shadow", "on") else "off"


def effective(key: str) -> bool:
    """is_enabled(key) plus the cross-flag rules (spec_ios 1)."""
    value = is_enabled(key)
    if key in _RESEARCH_GATED:
        return value and research_mode() == "on"
    if key == "hindi_brief" and value:
        if is_enabled("hindi_glossary") and hindi_lexicon_version() is not None:
            return True
        _warn_once("hindi_brief:forced_off", logging.WARNING,
                   "FEATURE_HINDI_BRIEF is on but needs FEATURE_HINDI_GLOSSARY and "
                   "HINDI_LEXICON_VERSION; serving it off")
        return False
    return value


def client_flags() -> dict[str, bool]:
    """Every registered flag with its effective value, for GET /api/v1/features."""
    return {key: effective(key) for key in FLAGS}


def effective_flags() -> dict[str, bool]:
    """The iOS flags, by app-config name, with their effective values."""
    return {name: effective(key) for name, key in IOS_FLAGS.items()}


def ios_app_store_url() -> Optional[str]:
    """IOS_APP_STORE_URL when it is an App Store link, else None."""
    url = (os.environ.get("IOS_APP_STORE_URL") or "").strip()
    return url if url.startswith(_APP_STORE_PREFIX) else None


def ios_min_build() -> int:
    """The one minimum iOS build (CFBundleVersion), for app-config and any 426 gate.

    Bad or negative values serve 0. A positive value without a valid
    IOS_APP_STORE_URL also serves 0: a forced update with no way to update is a
    dead end.
    """
    raw = (os.environ.get("IOS_MIN_BUILD") or "").strip()
    if not raw:
        return 0
    try:
        build = int(raw)
    except ValueError:
        build = -1
    if build < 0:
        _warn_once("IOS_MIN_BUILD:invalid", logging.ERROR,
                   "IOS_MIN_BUILD is not a non-negative integer; serving min_build 0")
        return 0
    if build > 0 and ios_app_store_url() is None:
        _warn_once("IOS_MIN_BUILD:no_store_url", logging.ERROR,
                   "IOS_MIN_BUILD=%d ignored: IOS_APP_STORE_URL is not a valid App Store URL; "
                   "serving min_build 0", build)
        return 0
    return build


def hindi_lexicon_version() -> Optional[str]:
    return (os.environ.get("HINDI_LEXICON_VERSION") or "").strip() or None


def app_config_payload(now: Optional[datetime] = None) -> dict:
    """Body of GET /api/v1/app-config (contract: spec_ios 1). No secrets, no user data."""
    now = now or datetime.now(timezone.utc)
    flags = effective_flags()
    return {
        "schema_version": 1,
        "generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "research_mode": research_mode(),
        "flags": flags,
        "content_languages": ["en", "hi"] if flags["hindi_glossary"] else ["en"],
        "ios": {"min_build": ios_min_build(), "app_store_url": ios_app_store_url()},
    }


def require_flag(key: str):
    """FastAPI dependency: 404 FEATURE_DISABLED while `key` is effectively off.

    Uses effective(), so the gate always agrees with /features and /app-config
    (e.g. stock_peers stays 404 until RESEARCH_ENGINE_MODE=on).

    Raises KeyError at route definition for an unregistered key, so a typo fails
    app import instead of silently shipping an ungated route.
    """
    if key not in FLAGS:
        raise KeyError(f"unknown feature flag: {key!r}")

    def _dependency() -> None:
        if not effective(key):  # same value the flag endpoints serve
            raise HTTPException(
                status_code=404,
                detail={"code": "FEATURE_DISABLED", "message": "This feature isn't available."},
            )

    return _dependency
