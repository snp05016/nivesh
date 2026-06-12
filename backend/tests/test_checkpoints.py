"""Task 3 — CheckpointEmitter writes job-scoped progress; no-ops without a job."""


def test_emitter_writes_to_db(monkeypatch):
    from services.checkpoints import CheckpointEmitter
    calls = []
    import database
    monkeypatch.setattr(database, "append_checkpoint",
                        lambda job_id, **kw: calls.append((job_id, kw)))
    em = CheckpointEmitter("abc123")
    em.emit("market", "Market Analyst", "reading RSI/MACD", pct=15)
    assert calls[0][0] == "abc123"
    assert calls[0][1]["agent"] == "Market Analyst"
    assert calls[0][1]["state"] == "running"
    assert calls[0][1]["pct"] == 15


def test_emitter_noop_without_job():
    from services.checkpoints import CheckpointEmitter
    # must not raise and must not touch the DB
    CheckpointEmitter(None).emit("x", "y", "z", pct=1)


def test_emitter_swallows_db_errors(monkeypatch):
    from services.checkpoints import CheckpointEmitter
    import database

    def _boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(database, "append_checkpoint", _boom)
    # an emit failure must never propagate into the analysis pipeline
    CheckpointEmitter("abc123").emit("market", "Market Analyst", "x", pct=1)
