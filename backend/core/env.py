"""Single loader for backend/.env.

Production keeps the old semantics (override=True: .env wins over the process
environment). Under pytest, backend/conftest.py sets NIVESH_TESTING=1 and this
becomes a no-op, so the forced test DATABASE_URL and dummy API keys can never be
replaced by the host's real values (DB-30).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_backend_env(path: Path = BACKEND_ENV_PATH) -> bool:
    """Load `path` over os.environ. Returns False, touching nothing, when NIVESH_TESTING=1."""
    if os.getenv("NIVESH_TESTING") == "1":
        return False
    load_dotenv(dotenv_path=path, override=True)
    return True
