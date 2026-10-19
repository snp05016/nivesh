"""I11: the 426 gate for iOS builds below ios_min_build() (core/version_gate.py).

Hermetic: a throwaway FastAPI app with only the middleware; ios_min_build is
monkeypatched on config.feature_flags. Paths go through variables (TEST-20).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ios_config = pytest.importorskip("config.feature_flags", reason="ios-flags-be (config/feature_flags.py) not merged yet")

from core.version_gate import UPDATE_TEXT, version_gate  # noqa: E402

P = "/x"
APP_CONFIG = "/api/v1/app-config"
HEALTH_READY = "/health/ready"
UA_OLD = "stockme/3 CFNetwork/1494.0.7 Darwin/23.4.0"
UA_NEW = "stockme/9 CFNetwork/1494.0.7 Darwin/23.4.0"

BACKEND = Path(__file__).resolve().parents[1]


def _client() -> TestClient:
    app = FastAPI()
    for path in (P, APP_CONFIG, HEALTH_READY):
        app.add_api_route(path, lambda: {"ok": True}, methods=["GET"])
    app.middleware("http")(version_gate)
    return TestClient(app)


@pytest.fixture
def min_build(monkeypatch):
    def _set(n: int) -> TestClient:
        monkeypatch.setattr(ios_config, "ios_min_build", lambda: n)
        return _client()
    return _set


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-App-Build": "1"}, {"User-Agent": UA_OLD}, {"User-Agent": "curl/8.4.0"}],
)
def test_gate_off_when_min_build_zero(min_build, headers):
    assert min_build(0).get(P, headers=headers).status_code == 200


def test_old_build_gets_426_plain_text(min_build):
    r = min_build(5).get(P, headers={"X-App-Build": "4"})
    assert r.status_code == 426
    assert r.headers["content-type"].startswith("text/plain")
    assert r.headers["cache-control"] == "no-store"
    assert r.text == UPDATE_TEXT


@pytest.mark.parametrize(
    ("minimum", "build", "status"),
    [(5, "5", 200), (2, "1", 426), (2, "100", 200)],
)
def test_x_app_build_header(min_build, minimum, build, status):
    assert min_build(minimum).get(P, headers={"X-App-Build": build}).status_code == status


@pytest.mark.parametrize(("ua", "status"), [(UA_OLD, 426), (UA_NEW, 200), ("curl/8.4.0", 200)])
def test_user_agent_fallback(min_build, ua, status):
    assert min_build(5).get(P, headers={"User-Agent": ua}).status_code == status


@pytest.mark.parametrize("path", [APP_CONFIG, HEALTH_READY])
def test_exempt_paths(min_build, path):
    assert min_build(5).get(path, headers={"X-App-Build": "1"}).status_code == 200


def test_options_never_gated(min_build):
    assert min_build(5).options(P, headers={"X-App-Build": "1"}).status_code != 426


def test_main_registers_gate_once():
    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
    hits = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and any(isinstance(a, ast.Name) and a.id == "version_gate" for a in n.args)
    ]
    assert len(hits) == 1
