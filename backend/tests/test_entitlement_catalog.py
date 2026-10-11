"""WIP-07: FEATURE_MIN_TIER lists exactly the feature keys that routers enforce
with require_entitlement(), and the entitlements endpoint returns exactly those."""
import re
from pathlib import Path

from services.entitlement_service import FEATURE_MIN_TIER

ROUTERS_DIR = Path(__file__).resolve().parent.parent / "routers"
_GATE_RE = re.compile(r"""require_entitlement\(\s*["']([a-z_]+)["']\s*\)""")


def _enforced_keys() -> set:
    keys = set()
    for path in ROUTERS_DIR.glob("*.py"):
        keys.update(_GATE_RE.findall(path.read_text(encoding="utf-8")))
    return keys


def test_every_feature_key_is_enforced():
    unenforced = set(FEATURE_MIN_TIER) - _enforced_keys()
    assert not unenforced, f"FEATURE_MIN_TIER keys with no require_entitlement() call site: {unenforced}"


def test_no_unenforced_keys():
    assert _enforced_keys() == set(FEATURE_MIN_TIER)


def test_removed_marketing_keys_stay_gone():
    for key in ("alpha_generators", "whatsapp_alerts", "forum_premium_board"):
        assert key not in FEATURE_MIN_TIER


def test_entitlements_endpoint_shape(client, auth_headers):
    resp = client.get("/api/v1/subscription/entitlements", headers=auth_headers)
    assert resp.status_code == 200
    assert set(resp.json()["features"]) == set(FEATURE_MIN_TIER)
