"""DB-02: a forked worker must not reuse the parent's DB pool or pgvector connection."""
import json
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.pool import QueuePool

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="needs os.fork")


def _checkedin(engine) -> int:
    pool = engine.pool
    if not isinstance(pool, QueuePool):
        pytest.skip(f"needs a QueuePool, got {type(pool).__name__}")
    return pool.checkedin()


def test_child_gets_fresh_pool_and_vector_conn():
    import database
    vector_store = pytest.importorskip("services.vector_store")

    with database.ENGINE.connect() as c:
        c.execute(text("select 1"))
    assert _checkedin(database.ENGINE) >= 1

    saved_conn = vector_store._conn
    sentinel = SimpleNamespace(closed=False)  # never a real psycopg2 connection
    vector_store._conn = sentinel
    try:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:  # child
            try:
                os.close(r)
                payload = {
                    "checkedin": _checkedin(database.ENGINE),
                    "vs_conn_none": vector_store._conn is None,
                }
                os.write(w, json.dumps(payload).encode())
            finally:
                os._exit(0)
        os.close(w)
        with os.fdopen(r) as fh:
            result = json.loads(fh.read())
        os.waitpid(pid, 0)
    finally:
        vector_store._conn = saved_conn

    assert result == {"checkedin": 0, "vs_conn_none": True}
    # The parent keeps its own pooled connection.
    assert _checkedin(database.ENGINE) >= 1
