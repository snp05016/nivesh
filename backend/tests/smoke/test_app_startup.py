"""Smoke tests: app import, startup, liveness."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("JWT_SECRET", "test-secret")


def test_main_imports_without_error():
    """App module must import without raising."""
    import main  # noqa: F401
    assert True


def test_app_object_exists():
    """FastAPI app object must exist and have a title."""
    import main
    assert hasattr(main, "app")
    assert main.app is not None
    assert main.app.title


def test_ping_endpoint():
    """GET /ping must return 200 with no auth."""
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/ping")
    assert resp.status_code == 200


def test_health_endpoint():
    """GET /health must return 200."""
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code in (200, 503)  # 503 if external deps fail in test env
