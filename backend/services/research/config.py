"""Research Engine flags (spec 9.3, decision D27/D36).

``load()`` runs at import and never raises. Any invalid value or combination is
logged at CRITICAL and makes research fail closed: effective mode ``off``,
``tier_only`` outlooks and a private track record, with the causes listed in
``degraded_reasons`` (shown in ``/healthz``). Nothing outside research is
affected, and ``RESEARCH_LEGACY_RETIRED`` keeps its own value (D24: rolling
research back never revives the old pipeline).

Read flags at call time through ``CONFIG`` (or the upper-case aliases, e.g.
``config.LEGACY_RETIRED``), never copy them at import: tests and ``/healthz``
reload with ``load()``.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional

from .templates import RA_DISCLAIMER_TEXT

logger = logging.getLogger(__name__)

MODES = ("off", "shadow", "on")
OUTLOOK_DISPLAYS = ("tier_only", "cohort_frequency")
REG_NO_RE = re.compile(r"^INH\d{9}$")
DEFAULT_ML_ENGINE_URL = "http://localhost:8001"

_TRUE = ("true", "1")
_FALSE = ("false", "0")


@dataclass(frozen=True)
class ResearchConfig:
    """Effective research flags (after fail-closed validation)."""

    mode: str = "off"
    outlook_display: str = "tier_only"
    track_record_public: bool = False
    sebi_ra_reg_no: Optional[str] = None  # effective only: None unless valid and a registered disclaimer exists
    legacy_retired: bool = False
    llm_prose: bool = True
    llm_max_calls_per_day: int = 800
    compute_daily_quota: int = 10
    ml_engine_url: str = DEFAULT_ML_ENGINE_URL
    ml_engine_api_key: Optional[str] = field(default=None, repr=False)
    degraded_reasons: tuple[str, ...] = ()

    @property
    def enabled(self) -> bool:
        """True when research runs at all (shadow or on)."""
        return self.mode != "off"

    @property
    def degraded(self) -> bool:
        return bool(self.degraded_reasons)


def load(environ: Optional[Mapping[str, str]] = None) -> ResearchConfig:
    """Read and validate the flags, set the module ``CONFIG`` and return it."""
    global CONFIG
    try:
        CONFIG = _parse(os.environ if environ is None else environ)
    except Exception as exc:  # never raise at import (D36)
        logger.critical("research config could not be read (%s); research is off", type(exc).__name__)
        CONFIG = ResearchConfig(degraded_reasons=("config_invalid:unreadable",))
    return CONFIG


def _parse(env: Mapping[str, str]) -> ResearchConfig:
    reasons: list[str] = []

    def raw(name: str) -> Optional[str]:
        value = env.get(name)
        if value is None:
            return None
        value = value.strip()
        return value or None

    def choice(name: str, allowed: tuple[str, ...], default: str) -> str:
        value = raw(name)
        if value is None:
            return default
        if value.lower() in allowed:
            return value.lower()
        reasons.append(f"config_invalid:{name}")
        return default

    def boolean(name: str, default: bool) -> bool:
        value = raw(name)
        if value is None:
            return default
        if value.lower() in _TRUE:
            return True
        if value.lower() in _FALSE:
            return False
        reasons.append(f"config_invalid:{name}")
        return default

    def count(name: str, default: int) -> int:
        value = raw(name)
        if value is None:
            return default
        try:
            n = int(value)
        except ValueError:
            n = -1
        if n < 0:
            reasons.append(f"config_invalid:{name}")
            return default
        return n

    mode = choice("RESEARCH_ENGINE_MODE", MODES, "off")
    outlook_display = choice("RESEARCH_OUTLOOK_DISPLAY", OUTLOOK_DISPLAYS, "tier_only")
    track_record_public = boolean("RESEARCH_TRACK_RECORD_PUBLIC", False)
    legacy_retired = boolean("RESEARCH_LEGACY_RETIRED", False)
    llm_prose = boolean("RESEARCH_LLM_PROSE", True)
    llm_max_calls = count("RESEARCH_LLM_MAX_CALLS_PER_DAY", 800)
    compute_quota = count("RESEARCH_COMPUTE_DAILY_QUOTA", 10)

    ml_engine_url = (raw("ML_ENGINE_URL") or DEFAULT_ML_ENGINE_URL).rstrip("/")
    if not ml_engine_url.startswith(("http://", "https://")):
        reasons.append("config_invalid:ML_ENGINE_URL")
        ml_engine_url = DEFAULT_ML_ENGINE_URL

    api_key = raw("ML_ENGINE_API_KEY")
    if mode != "off" and api_key is None:
        reasons.append("config_invalid:ML_ENGINE_API_KEY")

    # Any registration number is invalid while no registered-entity disclaimer
    # exists (spec 6.4), so in v1 the effective number is always None.
    reg_no = raw("RESEARCH_SEBI_RA_REG_NO")
    reg_no_valid = False
    if reg_no is not None:
        if not REG_NO_RE.match(reg_no):
            reasons.append("config_invalid:RESEARCH_SEBI_RA_REG_NO")
        elif RA_DISCLAIMER_TEXT is None:
            reasons.append("config_invalid:RESEARCH_SEBI_RA_REG_NO_without_disclaimer")
        else:
            reg_no_valid = True
    if outlook_display == "cohort_frequency" and not reg_no_valid:
        reasons.append("config_invalid:RESEARCH_OUTLOOK_DISPLAY_needs_registration")
    if track_record_public and not reg_no_valid:
        reasons.append("config_invalid:RESEARCH_TRACK_RECORD_PUBLIC_needs_registration")

    if reasons:
        # Values are never logged: only flag names.
        logger.critical("research config invalid (%s); research is off", ", ".join(reasons))
        mode, outlook_display, track_record_public, reg_no_valid = "off", "tier_only", False, False

    return ResearchConfig(
        mode=mode,
        outlook_display=outlook_display,
        track_record_public=track_record_public,
        sebi_ra_reg_no=reg_no if reg_no_valid else None,
        legacy_retired=legacy_retired,
        llm_prose=llm_prose,
        llm_max_calls_per_day=llm_max_calls,
        compute_daily_quota=compute_quota,
        ml_engine_url=ml_engine_url,
        ml_engine_api_key=api_key,
        degraded_reasons=tuple(reasons),
    )


CONFIG: ResearchConfig = ResearchConfig()
load()

# Upper-case aliases read the current CONFIG (one source of truth).
_ALIASES = {
    "MODE": "mode",
    "OUTLOOK_DISPLAY": "outlook_display",
    "TRACK_RECORD_PUBLIC": "track_record_public",
    "SEBI_RA_REG_NO": "sebi_ra_reg_no",
    "LEGACY_RETIRED": "legacy_retired",
    "LLM_PROSE": "llm_prose",
    "LLM_MAX_CALLS_PER_DAY": "llm_max_calls_per_day",
    "COMPUTE_DAILY_QUOTA": "compute_daily_quota",
    "ML_ENGINE_URL": "ml_engine_url",
    "DEGRADED_REASONS": "degraded_reasons",
}


def __getattr__(name: str) -> Any:
    if name in _ALIASES:
        return getattr(CONFIG, _ALIASES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
