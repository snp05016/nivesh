"""Single loader for backend/.env.

override=False: the real process environment (systemd EnvironmentFile, docker -e,
an exported shell variable) wins over backend/.env, which only fills gaps
(ARCH-12). Under pytest, backend/conftest.py sets NIVESH_TESTING=1 and this
becomes a no-op, so the forced test DATABASE_URL and dummy API keys can never be
replaced by the host's real values (DB-30).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_backend_env(path: Path = BACKEND_ENV_PATH) -> bool:
    """Fill unset os.environ keys from `path`. Returns False, touching nothing, when NIVESH_TESTING=1."""
    if os.getenv("NIVESH_TESTING") == "1":
        return False
    load_dotenv(dotenv_path=path, override=False)
    return True
