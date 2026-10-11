"""Root pytest config: force an isolated test environment (DB-30).

pytest imports this file before tests/, tests_suite/ and their conftests, i.e.
before any backend module, so these values are what database.py binds to.
NIVESH_TESTING=1 turns core.env.load_backend_env() into a no-op, so main.py, the
orchestrator and the job workers can no longer swap in backend/.env's real
DATABASE_URL or API keys. Every session gets a fresh temp SQLite file unless
TEST_DATABASE_URL names another test database.
"""
import atexit
import os
import shutil
import tempfile

import pytest
from sqlalchemy.engine import make_url

os.environ["NIVESH_TESTING"] = "1"

_db_url = os.environ.get("TEST_DATABASE_URL")
if not _db_url:
    _tmp_dir = tempfile.mkdtemp(prefix="nivesh-test-")
    atexit.register(shutil.rmtree, _tmp_dir, True)
    _db_url = f"sqlite:///{_tmp_dir}/stockapp_test.db"

_parsed = make_url(_db_url)
if _parsed.get_backend_name() != "sqlite" and "test" not in (_parsed.database or ""):
    raise pytest.UsageError(
        "TEST_DATABASE_URL must be SQLite or a database whose name contains 'test'; refusing to run."
    )

os.environ.update({
    "DATABASE_URL": _db_url,
    "JWT_SECRET": "test_secret_key_for_pytest_only_0123456789",  # >=32 chars (SILENT-09)
    "ANTHROPIC_API_KEY": "test_key",
    # "placeholder" is the sentinel tradingagents-core's live-API skipif gate recognises.
    "DEEPSEEK_API_KEY": "placeholder",
    "ENABLE_SCHEDULER": "false",
    "ENVIRONMENT": "test",  # unset now means production (OPS-13)
})
