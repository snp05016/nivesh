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


def test_child_forked_mid_budget_refresh_can_check_budget(monkeypatch):
    """LLM-02: a job process forked while a thread is refreshing the global LLM budget memo
    must still be able to check the budget (no lock inherited in the locked state)."""
    import select
    import signal
    import threading

    from services import llm_budget

    parent = os.getpid()
    in_refresh, release = threading.Event(), threading.Event()

    def slow_spend_today(user_id=None):
        if os.getpid() == parent:  # the parent's refresh blocks mid-"DB read"
            in_refresh.set()
            release.wait(10)
        return 0.0

    monkeypatch.setattr(llm_budget, "_spend_today", slow_spend_today)
    monkeypatch.setattr(llm_budget, "_global_cache", None)
    refresher = threading.Thread(target=llm_budget.assert_global_budget)
    refresher.start()
    assert in_refresh.wait(5)
    try:
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:  # child
            try:
                os.close(r)
                llm_budget.assert_global_budget()
                os.write(w, b"ok")
            finally:
                os._exit(0)
        os.close(w)
        ready, _, _ = select.select([r], [], [], 5)
        if not ready:
            os.kill(pid, signal.SIGKILL)
        result = os.read(r, 2) if ready else b"deadlocked"
        os.close(r)
        os.waitpid(pid, 0)
    finally:
        release.set()
        refresher.join(5)

    assert result == b"ok"
