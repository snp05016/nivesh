"""DB-30: the suite must never bind to the host's real database or API keys.

backend/conftest.py forces DATABASE_URL to a per-session temp SQLite file and
sets NIVESH_TESTING=1, which makes core.env.load_backend_env() a no-op, so a
backend/.env with a Postgres DATABASE_URL (the production server's setup) cannot
take over when main.py is imported.
"""
import os

from sqlalchemy.engine import make_url

import database
from core.env import load_backend_env


def test_engine_bound_to_test_db():
    url = database.ENGINE.url
    assert os.environ["NIVESH_TESTING"] == "1"
    if os.environ.get("TEST_DATABASE_URL"):
        assert url == make_url(os.environ["TEST_DATABASE_URL"])
    else:
        assert url.get_backend_name() == "sqlite"
        assert (url.database or "").endswith("stockapp_test.db")
        assert "nivesh-test-" in (url.database or "")


def test_load_backend_env_noop_under_tests(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://prod/nivesh\nDEEPSEEK_API_KEY=real\n")
    before = {key: os.environ[key] for key in ("DATABASE_URL", "DEEPSEEK_API_KEY")}
    for key, value in before.items():  # registered so monkeypatch restores them even if the call leaks
        monkeypatch.setenv(key, value)

    assert load_backend_env(env_file) is False
    assert {key: os.environ[key] for key in before} == before


def test_load_backend_env_loads_when_not_testing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("NIVESH_ENV_PROBE=loaded\n")
    monkeypatch.delenv("NIVESH_TESTING")
    monkeypatch.setenv("NIVESH_ENV_PROBE", "before")  # registered so monkeypatch removes it afterwards

    assert load_backend_env(env_file) is True
    assert os.environ["NIVESH_ENV_PROBE"] == "loaded"  # override=True, as in production
