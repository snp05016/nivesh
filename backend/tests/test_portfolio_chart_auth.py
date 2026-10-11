"""AUTH-04: portfolio chart PNGs must only be reachable by their owner.

The old public `/charts` StaticFiles mount served chart_<uid>_<n>.png to anyone.
"""

import base64
import os

import database

_CHART_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "charts"))
# 1x1 transparent PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_chart_images_require_owner(client, auth_token, test_user_id):
    uid = test_user_id
    fname = f"chart_{uid}_0.png"
    path = os.path.join(_CHART_DIR, fname)
    os.makedirs(_CHART_DIR, exist_ok=True)
    with open(path, "wb") as f:
        f.write(_PNG)
    owner = {"Authorization": f"Bearer {auth_token}"}
    # Seeded stub user (conftest): tokens need a real user (AUTH-13).
    other = {"Authorization": f"Bearer {database.create_access_token(990001)}"}
    route = f"/api/v1/portfolio/charts/{uid}/image"
    try:
        # Public static mount is gone. The global OPTIONS catch-all in main.py
        # turns unmatched GETs into 405, so accept either 404 or 405.
        r = client.get(f"/charts/{fname}")
        assert r.status_code in (404, 405) and r.content != _PNG

        ok = client.get(f"{route}/{fname}", headers=owner)
        assert ok.status_code == 200
        assert ok.headers["content-type"] == "image/png"
        assert ok.content == _PNG

        assert client.get(f"{route}/{fname}", headers=other).status_code == 404
        assert client.get(f"{route}/{fname}").status_code == 401

        # Only chart PNGs of the owner, no metadata, no traversal.
        assert client.get(f"{route}/meta_{uid}.json", headers=owner).status_code == 404
        assert client.get(f"{route}/..%2F.env", headers=owner).status_code in (404, 405)
        assert client.get(f"{route}/chart_{uid}_99.png", headers=owner).status_code == 404
    finally:
        os.remove(path)
