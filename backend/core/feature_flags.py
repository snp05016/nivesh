"""Server-side feature flags: the one choke point for every new surface.

Each flag is an env var read on every call, so changing one needs a backend
restart (systemd reloads backend/.env), never an App Store release. iOS reads
the same values from GET /api/v1/features and treats unknown keys as off.

Register a flag here, document it in backend/.env.example, and gate its routes
with Depends(require_flag("key")).
"""
import logging
import os

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
    # Data foundation cluster (docs: spec_data 0.1). Cohort access: services/data_flags.py.
    "data_instruments": ("FEATURE_DATA_INSTRUMENTS", True),
    "data_eod_prices": ("FEATURE_DATA_EOD_PRICES", True),
    "data_eod_display": ("FEATURE_DATA_EOD_DISPLAY", False),
    "data_mf_universe": ("FEATURE_DATA_MF_UNIVERSE", True),
    "data_corp_actions_confirm": ("FEATURE_DATA_CORP_ACTIONS_CONFIRM", False),
    "data_results_digest": ("FEATURE_DATA_RESULTS_DIGEST", False),
}

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})
_warned: set[str] = set()  # keys already warned about an unparseable value


def is_enabled(key: str) -> bool:
    """Current value of flag `key`. Unknown key -> KeyError (a typo must not ungate a route)."""
    env_name, default = FLAGS[key]
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    token = raw.strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    if key not in _warned:
        _warned.add(key)
        logger.warning("%s has an unrecognised value; using the default (%s)", env_name, default)
    return default


def client_flags() -> dict[str, bool]:
    """Every registered flag with its current value, for GET /api/v1/features."""
    return {key: is_enabled(key) for key in FLAGS}


def require_flag(key: str):
    """FastAPI dependency: 404 FEATURE_DISABLED while `key` is off.

    Raises KeyError at route definition for an unregistered key, so a typo fails
    app import instead of silently shipping an ungated route.
    """
    if key not in FLAGS:
        raise KeyError(f"unknown feature flag: {key!r}")

    def _dependency() -> None:
        if not is_enabled(key):
            raise HTTPException(
                status_code=404,
                detail={"code": "FEATURE_DISABLED", "message": "This feature isn't available."},
            )

    return _dependency
