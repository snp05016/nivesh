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
