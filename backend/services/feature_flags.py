"""Server-side boolean feature flags: the platform flag registry.

Resolution per key: DB row (feature_flags table, platform-flags), then env
NIVESH_FLAG_<KEY>, then FLAG_DEFAULTS. A key registered nowhere is off.
iOS sees only client=True keys, via client_flags().

Gate a route with Depends(require_flag("key")): 404 FEATURE_DISABLED while off.

Keys registered in core/feature_flags.py (money, habit) resolve there, so this
module is also the habit-cluster import path (mode, TRI_STATE, public_flags).
"""
import logging
import os

from fastapi import HTTPException

from core import feature_flags as _core
from core.feature_flags import FLAGS, TRI_STATE, mode  # noqa: F401  (habit-cluster import path)
from core.feature_flags import client_flags as public_flags  # noqa: F401

logger = logging.getLogger(__name__)

_LLM_SWITCH = "Kill switch for paid LLM calls made by {}. Off: those calls answer 503 AI_PAUSED and fall back to cached or template text."

FLAG_DEFAULTS: dict[str, dict] = {
    # Trust cluster (spec_trust section 0): C2 spend breaker, I04 focus cut, I02 honesty pass.
    "llm_enabled": {
        "default": True,
        "client": False,
        "description": "Master switch for every paid LLM call. Off: AI features answer 503 AI_PAUSED and fall back to cached or template text.",
    },
    "llm_copilot": {"default": True, "client": False, "description": _LLM_SWITCH.format("Copilot chat")},
    "llm_analysis": {"default": True, "client": False, "description": _LLM_SWITCH.format("stock analysis, daily action and smart-cache reformatting")},
    "llm_screener": {"default": True, "client": False, "description": _LLM_SWITCH.format("the natural-language screener")},
    "llm_youtube_summary": {"default": True, "client": False, "description": _LLM_SWITCH.format("YouTube video summaries")},
    "llm_portfolio_insights": {"default": True, "client": False, "description": _LLM_SWITCH.format("portfolio insights, morning briefing, red flags, macro impact, trade journal and PDF reports")},
    "llm_research_prose": {"default": True, "client": False, "description": _LLM_SWITCH.format("Research Engine prose")},
    "llm_harvest": {
        "default": True,
        "client": False,
        "description": _LLM_SWITCH.format("scheduler and harvester jobs with no bound feature, including the harvester reformatter"),
    },
    "forum": {
        "default": False,
        "client": True,
        "description": "Community forum. Off: /api/forum returns 404 FEATURE_DISABLED and iOS hides the card. Enable only with moderation staffing and a grievance officer.",
    },
    "ipo_hub": {"default": False, "client": True, "description": "IPO hub. Off until a real IPO data source exists."},
}

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_warned: set[str] = set()  # unregistered keys already warned about


def _env_value(key: str):
    raw = os.environ.get(f"NIVESH_FLAG_{key.upper()}")
    token = (raw or "").strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    return None  # unset or unparseable: ignored


def is_enabled(key: str) -> bool:
    """Current value of `key`; fails closed for an unregistered key."""
    if key in _core.FLAGS:
        return _core.is_enabled(key)
    # ponytail: no DB layer yet; platform-flags adds the feature_flags table lookup
    # (with its 30 s cache) in front of the env read.
    env = _env_value(key)
    if env is not None:
        return env
    spec = FLAG_DEFAULTS.get(key)
    if spec is None:
        if key not in _warned:
            _warned.add(key)
            logger.warning("unregistered feature flag %r resolves to off", key)
        return False
    return bool(spec["default"])


def client_flags() -> dict[str, bool]:
    """Client-visible flags only (client=True), for the public flags endpoint."""
    return {key: is_enabled(key) for key, spec in FLAG_DEFAULTS.items() if spec["client"]}


def _reset_cache() -> None:
    """Drop cached resolutions (tests call this between cases)."""
    _warned.clear()


def require_flag(key: str):
    """FastAPI dependency: 404 {"code": "FEATURE_DISABLED", "feature": key} while `key` is off.

    An unregistered key raises KeyError at route definition, so a typo fails app
    import instead of shipping an ungated route.
    """
    if key in _core.FLAGS:
        return _core.require_flag(key)
    if key not in FLAG_DEFAULTS:
        raise KeyError(f"unknown feature flag: {key!r}")

    def _dependency() -> None:
        if not is_enabled(key):
            raise HTTPException(status_code=404, detail={"code": "FEATURE_DISABLED", "feature": key})

    return _dependency
