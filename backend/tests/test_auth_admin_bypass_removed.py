"""AUTH-02: no ADMIN_TOKEN bypass. A static bearer authenticates as nobody, whatever the env says;
admin routes need the JWT of a users.is_admin account."""
import os
import re
from pathlib import Path

import pytest

import core.security
import helpers

_BACKEND = Path(__file__).resolve().parent.parent
_SKIP_DIRS = {"tests", "tests_suite", "venv", ".venv", "__pycache__", "node_modules", "cache", "charts", "logs", "data"}
# A bearer token written out as a string literal ('Bearer admin'); built headers ('Bearer '+t) do not match.
_LITERAL_BEARER = re.compile(r"Bearer [A-Za-z0-9_.-]{3,}['\"`]")


@pytest.mark.parametrize("environment", ["production", "development"])
@pytest.mark.parametrize("token", ["admin", "x" * 40])
def test_admin_token_env_grants_nothing(client, monkeypatch, environment, token):
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("ADMIN_TOKEN", token)
    headers = {"Authorization": f"Bearer {token}"}
    # require_admin called inline, core.security Depends, helpers Depends
    for path in ("/dashboard-data", "/users", "/api/v1/subscription", "/api/v1/predictions/calibration"):
        assert client.get(path, headers=headers).status_code == 401, path


def test_helpers_reexports_the_single_auth_implementation():
    for name in ("get_current_user_id", "require_auth", "require_admin"):
        assert getattr(helpers, name) is getattr(core.security, name), name


def test_no_hardcoded_bearer_or_admin_token_in_backend_source():
    offenders = []
    for root, dirs, files in os.walk(_BACKEND):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith((".py", ".html")) and not name.startswith("test_"):
                text = Path(root, name).read_text(encoding="utf-8", errors="ignore")
                if _LITERAL_BEARER.search(text) or "ADMIN_TOKEN" in text:
                    offenders.append(os.path.relpath(os.path.join(root, name), _BACKEND))
    assert offenders == []


def test_admin_routes_need_an_admin_jwt(client, admin_headers, auth_headers):
    assert client.get("/users", headers=admin_headers).status_code == 200
    assert client.get("/users", headers=auth_headers).status_code == 403
