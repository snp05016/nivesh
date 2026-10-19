"""REG-11: accuracy / hit-rate figures about the app's own BUY/SELL calls are
internal QA metrics (no PaRRVA verification), so only admins can read them."""
import pytest

ROUTES = ["/signal-accuracy", "/api/v1/predictions/performance"]


@pytest.mark.parametrize("path", ROUTES)
def test_anonymous_is_rejected(client, path):
    assert client.get(path).status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_regular_user_is_forbidden(client, auth_headers, path):
    assert client.get(path, headers=auth_headers).status_code == 403


@pytest.mark.parametrize("path", ROUTES)
def test_admin_can_read(client, admin_headers, path):
    resp = client.get(path, headers=admin_headers)
    assert resp.status_code == 200, resp.text


QUANTLAB_ROUTES = [
    "/api/v1/predictions/calibration",
    "/api/v1/predictions/pillar-attribution",
    "/api/v1/predictions/model-versions",
    "/api/v1/predictions/calibration/health",
    "/api/v1/predictions/fusion-weight-recommendations",
]


@pytest.mark.parametrize("billing", [None, "true"])
@pytest.mark.parametrize("path", QUANTLAB_ROUTES)
def test_quantlab_dashboards_admin_only(client, auth_headers, admin_headers, monkeypatch, path, billing):
    """Calibration dashboards are never sold and never user-facing (growth cluster, 41 I44 delta 1)."""
    if billing is None:
        monkeypatch.delenv("BILLING_ENABLED", raising=False)
    else:
        monkeypatch.setenv("BILLING_ENABLED", billing)
    assert client.get(path).status_code == 401
    resp = client.get(path, headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"
    assert client.get(path, headers=admin_headers).status_code == 200
