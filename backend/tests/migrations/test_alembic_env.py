"""DB-14: migrations resolve the database like the app and refuse to guess in production."""
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent.parent


def _alembic(env, *args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, env=env,
    )


def _env_without_url(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "ENVIRONMENT")}
    env["NIVESH_TESTING"] = "1"  # load_backend_env() must not pull in backend/.env
    env.update(extra)
    return env


def test_env_requires_url_in_production():
    result = _alembic(_env_without_url(ENVIRONMENT="production"), "current")

    assert result.returncode != 0
    assert "DATABASE_URL must be set for migrations in production" in result.stderr


def test_explicit_url_is_used(tmp_path):
    db = tmp_path / "explicit.db"
    env = _env_without_url(DATABASE_URL=f"sqlite:///{db}", ENVIRONMENT="production")

    result = _alembic(env, "current")

    assert result.returncode == 0, result.stderr
    assert db.exists()
