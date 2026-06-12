# Analysis Engine v2 (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the runaway, connection-tied "extreme" AI analysis into a bounded, observable, cancellable server-side background job whose extreme output is a richer superset (longer narrative + 4 graph bundles) of normal analysis.

**Architecture:** A DB-backed `AnalysisJob` row is the single source of truth. `POST /analyze` returns `202` immediately and spawns a detached `multiprocessing.Process` worker that writes status/checkpoints/result to the DB and self-enforces a 600 s wall-clock + 400K-token kill-switch. The engine config is bounded (Approach A). Extreme output adds deterministic graph data (computed in Python) plus LLM narrative blocks, guaranteed by an extended normalizer.

**Tech Stack:** Python, FastAPI, SQLAlchemy (DeclarativeBase), multiprocessing, threading, OpenAI-compatible DeepSeek client, Anthropic (Haiku/Sonnet), LangGraph (tradingagents-core).

**Spec:** `docs/superpowers/specs/2026-06-12-analysis-engine-v2-design.md`

**Working dir for all commands:** `/Users/saumya/Desktop/nivesh/backend`

**Project rule (AGENTS.md/CLAUDE.md):** Before editing any function/class/method, run `gitnexus_impact({target, direction:"upstream"})`; before each commit run `gitnexus_detect_changes()`. NEVER run `xcodebuild`. Commit after each task.

---

## File Map

- Modify `backend/database.py` — add `AnalysisJob` table + job DAO functions.
- Modify `backend/services/orchestrator.py` — `build_ta_config` bounds; reformat budget; extreme normalizer; checkpoint hooks; `run_trading_agents` job-scoped progress.
- Modify `backend/services/llm_utils.py` — cap reasoner `effective_max`; token accounting hook.
- Create `backend/services/job_manager.py` — registry, spawn, cancel, watchdog, crash sweep.
- Create `backend/services/checkpoints.py` — `CheckpointEmitter` (job-scoped, DB-backed).
- Create `backend/services/extreme_enrichers.py` — deterministic graph bundles.
- Modify `backend/prompts.py` — `EXTREME_ADDENDUM` (additive; base prompt untouched).
- Modify `backend/routers/analysis.py` — `POST /analyze` → 202; new job endpoints; worker refactor.
- Modify `backend/main.py` — startup crash-sweep hook.
- Modify `backend/routers/dashboard.py` — read job rows.
- Tests under `backend/tests/`.

---

## Task 1: `AnalysisJob` model + DAO

**Files:**
- Modify: `backend/database.py` (add after `AnalysisHistory`, ~line 147)
- Test: `backend/tests/test_analysis_job.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_analysis_job.py
import os, tempfile, importlib
import pytest

@pytest.fixture
def db(monkeypatch):
    import database
    importlib.reload(database)
    database.Base.metadata.create_all(database.engine)
    return database

def test_job_lifecycle(db):
    job = db.create_job(user_id=1, ticker="RELIANCE", exchange="NSE", scan_type="extreme")
    assert job["status"] == "QUEUED"
    assert len(job["job_id"]) == 12
    db.update_job(job["job_id"], status="RUNNING", pid=4242, progress_pct=10, stage="market")
    db.append_checkpoint(job["job_id"], stage="market", agent="Market Analyst",
                         message="reading indicators", state="running", pct=15)
    got = db.get_job(job["job_id"])
    assert got["status"] == "RUNNING"
    assert got["pid"] == 4242
    assert got["checkpoints"][-1]["agent"] == "Market Analyst"
    assert got["progress_pct"] == 15

def test_one_active_per_user(db):
    j1 = db.create_job(user_id=2, ticker="TCS", exchange="NSE", scan_type="extreme")
    db.update_job(j1["job_id"], status="RUNNING")
    assert db.get_active_job_for_user(2)["job_id"] == j1["job_id"]
    db.update_job(j1["job_id"], status="SUCCEEDED")
    assert db.get_active_job_for_user(2) is None

def test_sweep_stale_running_marks_failed(db):
    from datetime import datetime, timedelta
    j = db.create_job(user_id=3, ticker="INFY", exchange="NSE", scan_type="standard")
    db.update_job(j["job_id"], status="RUNNING",
                  heartbeat_at=datetime.utcnow() - timedelta(seconds=200))
    n = db.sweep_stale_jobs(max_heartbeat_age_sec=90)
    assert n == 1
    assert db.get_job(j["job_id"])["status"] == "FAILED"
```

- [ ] **Step 2: Run test, expect FAIL** — `pytest tests/test_analysis_job.py -v` → fails (`create_job` undefined).

- [ ] **Step 3: Add model + DAO to `database.py`**

```python
# ── after AnalysisHistory ────────────────────────────────────────────────
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    job_id       = Column(String(12), primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticker       = Column(String(30), nullable=False)
    exchange     = Column(String(10), nullable=False, default="NSE")
    scan_type    = Column(String(20), nullable=False, default="standard")
    status       = Column(String(20), nullable=False, default="QUEUED")
    stage        = Column(String(60), nullable=True)
    progress_pct = Column(Integer, nullable=False, default=0)
    checkpoints  = Column(Text, nullable=False, default="[]")   # JSON list
    pid          = Column(Integer, nullable=True)
    heartbeat_at = Column(DateTime, nullable=True)
    tokens_used  = Column(Integer, nullable=False, default=0)
    error        = Column(Text, nullable=True)
    result_id    = Column(Integer, ForeignKey("analysis_history.id"), nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    started_at   = Column(DateTime, nullable=True)
    finished_at  = Column(DateTime, nullable=True)

_TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMEOUT"}

def _job_to_dict(j: "AnalysisJob") -> dict:
    return {
        "job_id": j.job_id, "user_id": j.user_id, "ticker": j.ticker,
        "exchange": j.exchange, "scan_type": j.scan_type, "status": j.status,
        "stage": j.stage, "progress_pct": j.progress_pct,
        "checkpoints": json.loads(j.checkpoints or "[]"),
        "pid": j.pid, "tokens_used": j.tokens_used, "error": j.error,
        "result_id": j.result_id,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }

def create_job(user_id, ticker, exchange, scan_type) -> dict:
    jid = str(uuid.uuid4())[:12]
    with get_session() as s:
        j = AnalysisJob(job_id=jid, user_id=user_id, ticker=ticker.upper(),
                        exchange=exchange, scan_type=scan_type, status="QUEUED",
                        heartbeat_at=datetime.utcnow())
        s.add(j); s.flush()
        return _job_to_dict(j)

def get_job(job_id) -> dict | None:
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        return _job_to_dict(j) if j else None

def update_job(job_id, **fields) -> None:
    if fields.get("status") in _TERMINAL:
        fields.setdefault("finished_at", datetime.utcnow())
    if fields.get("status") == "RUNNING":
        fields.setdefault("started_at", datetime.utcnow())
    fields.setdefault("heartbeat_at", datetime.utcnow())
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j: return
        for k, v in fields.items():
            setattr(j, k, v)

def append_checkpoint(job_id, *, stage, agent, message, state, pct) -> None:
    from datetime import datetime as _dt
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j: return
        cps = json.loads(j.checkpoints or "[]")
        cps.append({"ts": _dt.utcnow().isoformat(), "stage": stage,
                    "agent": agent, "message": message, "state": state})
        j.checkpoints = json.dumps(cps, ensure_ascii=False)
        j.stage = stage; j.progress_pct = max(j.progress_pct, int(pct))
        j.heartbeat_at = _dt.utcnow()

def add_job_tokens(job_id, n) -> int:
    with get_session() as s:
        j = s.get(AnalysisJob, job_id)
        if not j: return 0
        j.tokens_used = (j.tokens_used or 0) + int(n)
        j.heartbeat_at = datetime.utcnow()
        return j.tokens_used

def get_active_job_for_user(user_id) -> dict | None:
    if user_id is None: return None
    with get_session() as s:
        j = (s.query(AnalysisJob)
               .filter(AnalysisJob.user_id == user_id,
                       AnalysisJob.status.in_(["QUEUED", "RUNNING"]))
               .order_by(AnalysisJob.created_at.desc()).first())
        return _job_to_dict(j) if j else None

def sweep_stale_jobs(max_heartbeat_age_sec: int = 90) -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=max_heartbeat_age_sec)
    with get_session() as s:
        stale = (s.query(AnalysisJob)
                   .filter(AnalysisJob.status.in_(["QUEUED", "RUNNING"]),
                           AnalysisJob.heartbeat_at < cutoff).all())
        for j in stale:
            j.status = "FAILED"; j.error = "Worker died (stale heartbeat / restart)"
            j.finished_at = datetime.utcnow()
        return len(stale)
```

Ensure imports at top of `database.py`: `import json, uuid` and `from datetime import datetime, timedelta` (timedelta may need adding). Verify `get_session` + `engine` already exist.

- [ ] **Step 4: Run tests, expect PASS** — `pytest tests/test_analysis_job.py -v`.

- [ ] **Step 5: Commit** — `git add backend/database.py backend/tests/test_analysis_job.py && git commit -m "Add AnalysisJob model: DB-backed job state + DAO"`

---

## Task 2: Bound the engine (the runaway fix)

**Files:**
- Modify: `backend/services/orchestrator.py:401-421` (`build_ta_config`)
- Modify: `backend/services/llm_utils.py:73` (`effective_max`)
- Test: `backend/tests/test_engine_bounds.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_engine_bounds.py
def test_extreme_config_is_bounded():
    from services.orchestrator import build_ta_config
    c = build_ta_config("extreme")
    assert c["max_debate_rounds"] == 2
    assert c["max_risk_discuss_rounds"] == 1
    assert c["max_tokens"] == 8000
    assert c["quick_think_llm"] == "deepseek-reasoner"
    assert c.get("recursion_limit") and c["recursion_limit"] <= 40
    assert c.get("analyst_tool_loop_cap") == 3

def test_reasoner_effective_max_capped(monkeypatch):
    import services.llm_utils as lu
    captured = {}
    class _Resp:
        class _C:  # minimal stub
            class message: content = "ok"; reasoning_content = ""
        choices = [_C()]; usage = None
    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw): captured.update(kw); return _Resp()
    monkeypatch.setattr(lu, "get_deepseek_client", lambda: _Client())
    lu.deepseek_chat([{"role":"user","content":"hi"}], max_tokens=8000, model="deepseek-reasoner")
    assert captured["max_tokens"] <= 16000  # not 8000*8=64000
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Edit `build_ta_config` extreme branch**

```python
    if scan_type == "extreme":
        config["quick_think_llm"] = "deepseek-reasoner"
        config["quick_think_provider"] = "deepseek"
        config["max_debate_rounds"] = 2          # was 3
        config["max_risk_discuss_rounds"] = 1    # was 2
        config["max_tokens"] = 8000              # was 16000
        config["recursion_limit"] = 40           # explicit LangGraph bound
        config["analyst_tool_loop_cap"] = 3      # cap agent↔tool loop
```

Edit `llm_utils.deepseek_chat` line 73:

```python
    # Reasoner needs headroom for reasoning_content, but never inflate to absurd sizes.
    if is_pro:
        effective_max = min(max_tokens + 8000, 16000)
    else:
        effective_max = max(max_tokens, 512)
```

- [ ] **Step 4: Run, expect PASS.** Also grep that `recursion_limit` is consumed where the graph compiles/invokes (`OptimizedTradingAgentsGraph` / `propagate`); if the library invoke accepts a config, pass `{"recursion_limit": config["recursion_limit"]}`. If tradingagents `propagate` doesn't accept it, note for Task 5 to pass at `graph.invoke(..., config={"recursion_limit": N})`.

- [ ] **Step 5: Commit** — `git commit -m "Fix extreme runaway: bound rounds/tokens, cap reasoner effective_max, recursion limit"`

---

## Task 3: `CheckpointEmitter` (job-scoped, DB-backed)

**Files:**
- Create: `backend/services/checkpoints.py`
- Test: `backend/tests/test_checkpoints.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_checkpoints.py
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

def test_emitter_noop_without_job():
    from services.checkpoints import CheckpointEmitter
    CheckpointEmitter(None).emit("x","y","z",pct=1)  # must not raise
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
# backend/services/checkpoints.py
"""Job-scoped checkpoint emitter. Single channel for per-agent progress.
Safe no-op when job_id is None (e.g. standard scans not tracked as jobs)."""
from __future__ import annotations

class CheckpointEmitter:
    def __init__(self, job_id: str | None):
        self.job_id = job_id

    def emit(self, stage: str, agent: str, message: str, *,
             pct: int, state: str = "running") -> None:
        if not self.job_id:
            return
        try:
            import database
            database.append_checkpoint(self.job_id, stage=stage, agent=agent,
                                       message=message, state=state, pct=pct)
        except Exception as e:
            print(f"[checkpoint] emit failed: {e}")
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "Add CheckpointEmitter: job-scoped per-agent progress"`

---

## Task 4: Deterministic extreme enrichers (graph bundles)

**Files:**
- Create: `backend/services/extreme_enrichers.py`
- Test: `backend/tests/test_extreme_enrichers.py`

Each function returns a JSON-serializable dict/list and **degrades gracefully** (returns `None`/`[]` on missing data, never raises). Reuses existing services: `factor_engine`, `piotroski`, `nse_data_provider`.

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_extreme_enrichers.py
import services.extreme_enrichers as ex

def test_all_enrichers_graceful_on_missing(monkeypatch):
    monkeypatch.setattr(ex, "_safe_fundamentals", lambda t: {})
    out = ex.build_extreme_bundles("ZZZZ", "NSE")
    assert set(out) >= {"factor_scores","piotroski","financial_trends",
                        "ownership_trends","peer_comparison"}
    # missing data → empty/None, not crash
    assert out["peer_comparison"] == [] or out["peer_comparison"] is None

def test_factor_scores_shape(monkeypatch):
    monkeypatch.setattr(ex, "_compute_factor_scores",
        lambda t,e: {"value":60,"quality":72,"momentum":40,"growth":55,"low_volatility":63})
    out = ex.build_extreme_bundles("RELIANCE","NSE")
    fs = out["factor_scores"]
    assert set(fs) == {"value","quality","momentum","growth","low_volatility"}
    assert all(0 <= v <= 100 for v in fs.values())
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** (wire to real services; wrap each in try/except)

```python
# backend/services/extreme_enrichers.py
"""Deterministic, code-computed graph bundles for extreme analysis.
Real numbers for charts; the LLM only adds narrative. All best-effort."""
from __future__ import annotations

def _safe_fundamentals(ticker: str) -> dict:
    try:
        from services.nse_data_provider import get_fundamentals
        return get_fundamentals(ticker) or {}
    except Exception:
        return {}

def _compute_factor_scores(ticker: str, exchange: str) -> dict | None:
    try:
        from services.factor_engine import compute_factor_scores  # adapt to real API
        return compute_factor_scores(ticker, exchange)
    except Exception:
        return None

def _compute_piotroski(ticker: str) -> dict | None:
    try:
        from services.piotroski import compute_piotroski  # adapt to real API
        return compute_piotroski(ticker)
    except Exception:
        return None

def _financial_trends(ticker: str) -> dict | None:
    try:
        f = _safe_fundamentals(ticker)
        # adapt key names to nse_data_provider output; omit missing series
        return f.get("financial_trends") or None
    except Exception:
        return None

def _ownership_trends(ticker: str) -> dict | None:
    try:
        f = _safe_fundamentals(ticker)
        return f.get("ownership_trends") or None
    except Exception:
        return None

def _peer_comparison(ticker: str, exchange: str) -> list:
    try:
        from services.nse_data_provider import get_sector_peers  # adapt/skip if absent
        return get_sector_peers(ticker, exchange) or []
    except Exception:
        return []

def build_extreme_bundles(ticker: str, exchange: str = "NSE") -> dict:
    return {
        "factor_scores":    _compute_factor_scores(ticker, exchange),
        "piotroski":        _compute_piotroski(ticker),
        "financial_trends": _financial_trends(ticker),
        "ownership_trends": _ownership_trends(ticker),
        "peer_comparison":  _peer_comparison(ticker, exchange),
    }
```

> NOTE for implementer: open `services/factor_engine.py`, `services/piotroski.py`, `services/nse_data_provider.py` and replace the adapter calls (`compute_factor_scores`, `compute_piotroski`, `get_sector_peers`, fundamentals key names) with the real function names/shapes. Run `gitnexus_context({name:"..."})` on each.

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "Add extreme_enrichers: deterministic graph bundles (factor/piotroski/trends/ownership/peers)"`

---

## Task 5: Extreme LLM narrative + extended normalizer

**Files:**
- Modify: `backend/prompts.py` (add `EXTREME_ADDENDUM`, do NOT touch `INDIAN_MARKET_SYSTEM_PROMPT`)
- Modify: `backend/services/orchestrator.py` — `reformat_with_claude` (raise extreme budget + append addendum), `_normalize_response` (extend for extreme), `analyze` (attach bundles)
- Test: `backend/tests/test_extreme_output.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_extreme_output.py
def test_extreme_normalizer_guarantees_blocks():
    from services.orchestrator import _normalize_response
    base = {"signal":"BUY","confidence_pct":70}
    out = _normalize_response(base, scan_type="extreme")
    for k in ("scenarios","valuation_bands","extended_thesis",
              "niche_insights","governance_flags","analysis_tier"):
        assert k in out
    assert out["analysis_tier"] == "extreme"
    assert isinstance(out["niche_insights"], list)

def test_normal_normalizer_unchanged():
    from services.orchestrator import _normalize_response
    out = _normalize_response({"signal":"HOLD"}, scan_type="standard")
    assert "scenarios" not in out  # additive only for extreme
```

- [ ] **Step 2: Run, expect FAIL** (signature `scan_type` not yet supported).

- [ ] **Step 3a: `prompts.py` — add addendum**

```python
EXTREME_ADDENDUM = """
EXTREME MODE — produce a markedly deeper, longer report than standard analysis.
In addition to all standard fields, you MUST output these extra JSON fields:
- "scenarios": {"bull":{"price_3m","price_12m","price_36m","probability_pct","narrative"},
                "base":{...},"bear":{...}}
- "valuation_bands": {"current_price","fair_value","bull_value","bear_value",
                      "method","pe_band":{"low","mid","high"}}
- "extended_thesis": {"bull_deep_dive","bear_deep_dive","management_quality",
                      "competitive_moat","sector_positioning"}  (each 120-250 words)
- "niche_insights": [ non-obvious, decision-useful findings ]
- "governance_flags": [ {"flag","severity","detail"} ]
Maintain dialectical asymmetry: the bear analysis must be more thorough than the bull.
All monetary values in Lakhs/Crores. No emojis.
"""
```

- [ ] **Step 3b: `_normalize_response` — add `scan_type` param + extreme guarantees** (additive; keep all existing behavior for standard)

```python
def _normalize_response(result: dict, scan_type: str = "standard") -> dict:
    # ... existing normalization unchanged ...
    if scan_type == "extreme":
        result["analysis_tier"] = "extreme"
        result.setdefault("scenarios", {})
        result.setdefault("valuation_bands", {})
        result.setdefault("extended_thesis", {})
        result.setdefault("niche_insights", [])
        result.setdefault("governance_flags", [])
    return result
```

Update all `_normalize_response(x)` call sites that handle extreme to pass `scan_type`. Find them: `grep -n "_normalize_response(" services/orchestrator.py`.

- [ ] **Step 3c: `reformat_with_claude`** — accept `scan_type`; when extreme, append `EXTREME_ADDENDUM` to the prompt and raise `max_tokens` 4000→8000 for the Sonnet/Haiku and DeepSeek-fallback calls (lines ~535, ~576).

- [ ] **Step 3d: `analyze`** — after reformat, when `scan_type=="extreme"` attach deterministic bundles:

```python
    if scan_type == "extreme":
        from services.extreme_enrichers import build_extreme_bundles
        result.update({k: v for k, v in build_extreme_bundles(ticker, exchange).items()})
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "Add extreme superset output: addendum prompt, extended normalizer, graph bundles, larger budget"`

---

## Task 6: Worker refactor (DB-driven, kill-switches, checkpoints)

**Files:**
- Modify: `backend/routers/analysis.py` — `_run_analysis_worker` (line 186)
- Modify: `backend/services/orchestrator.py` — thread `job_id`/`CheckpointEmitter` + token accounting through `run_trading_agents`/`analyze`
- Test: `backend/tests/test_worker.py`

- [ ] **Step 1: Failing test** (no real LLM — patch `analyze`)

```python
# backend/tests/test_worker.py
def test_worker_marks_succeeded(monkeypatch):
    import database, importlib; importlib.reload(database)
    database.Base.metadata.create_all(database.engine)
    job = database.create_job(1, "RELIANCE", "NSE", "standard")
    import services.job_worker as jw
    # run_job imports analyze at call-time from services.orchestrator → patch the source
    monkeypatch.setattr("services.orchestrator.analyze", lambda *a, **k: {"signal":"BUY"})
    monkeypatch.setattr("database.save_analysis", lambda *a, **k: 7)  # returns result_id
    jw.run_job(job["job_id"], "RELIANCE", "NSE", 1, False, "standard")
    g = database.get_job(job["job_id"])
    assert g["status"] == "SUCCEEDED"
    assert g["result_id"] is not None
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Create `services/job_worker.py`** (the function the subprocess runs)

```python
# backend/services/job_worker.py
"""Subprocess entry point for a single analysis job. Writes all state to DB."""
from __future__ import annotations
import threading, time, os

def _start_wallclock_watchdog(job_id: str, limit_sec: int = 600):
    def _kill():
        time.sleep(limit_sec)
        import database
        j = database.get_job(job_id)
        if j and j["status"] == "RUNNING":
            database.update_job(job_id, status="TIMEOUT",
                                error=f"Exceeded {limit_sec}s wall-clock budget")
            os._exit(1)  # hard stop the subprocess
    t = threading.Thread(target=_kill, daemon=True); t.start()

def run_job(job_id, ticker, exchange, user_id, deep_scan, scan_type):
    from dotenv import load_dotenv; load_dotenv(override=True)
    import database
    from services.orchestrator import analyze
    database.update_job(job_id, status="RUNNING", pid=os.getpid(),
                        stage="starting", progress_pct=1)
    if scan_type == "extreme":
        _start_wallclock_watchdog(job_id, 600)
    try:
        result = analyze(ticker, exchange, user_id, deep_scan=deep_scan,
                         scan_type=scan_type, job_id=job_id)
        # persist result to AnalysisHistory, link result_id
        rid = database.save_analysis(user_id, ticker, result)  # reuse existing saver
        database.update_job(job_id, status="SUCCEEDED", progress_pct=100,
                            stage="done", result_id=rid)
    except Exception as e:
        database.update_job(job_id, status="FAILED", error=str(e))
        raise
```

> Implementer: confirm `database.save_analysis` exists and returns the row id (grep `def save_analysis` in `database.py`); if it returns nothing, add a thin `save_analysis_returning_id`. Thread `job_id` + token accounting (`database.add_job_tokens` + 400K guard) into `analyze`/`run_trading_agents` and have agent nodes call `CheckpointEmitter(job_id).emit(...)` at each stage. The token guard: after each LLM call, `if database.add_job_tokens(job_id, n) > 400_000: raise RuntimeError("token budget exceeded")`.

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "Add job_worker: DB-driven subprocess with wall-clock + token kill-switches"`

---

## Task 7: `job_manager` (spawn, registry, cancel)

**Files:**
- Create: `backend/services/job_manager.py`
- Test: `backend/tests/test_job_manager.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_job_manager.py
def test_spawn_and_cancel(monkeypatch):
    import database, importlib; importlib.reload(database)
    database.Base.metadata.create_all(database.engine)
    job = database.create_job(1, "TCS", "NSE", "standard")
    import services.job_manager as jm
    class _FakeProc:
        def __init__(self,*a,**k): self.pid=999; self._alive=True
        def start(self): pass
        def is_alive(self): return self._alive
        def terminate(self): self._alive=False
        def join(self,*a,**k): pass
    monkeypatch.setattr(jm.multiprocessing, "Process", _FakeProc)
    jm.spawn_job(job["job_id"], "TCS", "NSE", 1, False, "standard")
    assert job["job_id"] in jm._job_registry
    jm.cancel_job(job["job_id"])
    assert database.get_job(job["job_id"])["status"] == "CANCELLED"
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

```python
# backend/services/job_manager.py
"""Owns running job subprocesses: spawn, registry, cancel. Locked global state."""
from __future__ import annotations
import multiprocessing, threading

_job_registry: dict[str, "multiprocessing.Process"] = {}
_registry_lock = threading.Lock()

def spawn_job(job_id, ticker, exchange, user_id, deep_scan, scan_type):
    from services.job_worker import run_job
    p = multiprocessing.Process(
        target=run_job,
        args=(job_id, ticker, exchange, user_id, deep_scan, scan_type),
        daemon=True,
    )
    p.start()
    with _registry_lock:
        _job_registry[job_id] = p

def cancel_job(job_id) -> bool:
    import database
    database.update_job(job_id, status="CANCELLED", error="Cancelled by user")
    with _registry_lock:
        p = _job_registry.pop(job_id, None)
    if p and p.is_alive():
        p.terminate(); p.join(timeout=5)
    return True

def reap_finished():
    with _registry_lock:
        for jid in [j for j, p in _job_registry.items() if not p.is_alive()]:
            _job_registry.pop(jid, None)
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "Add job_manager: subprocess registry, spawn, cancel (locked global state)"`

---

## Task 8: API surface (202 + job endpoints + startup sweep)

**Files:**
- Modify: `backend/routers/analysis.py` — replace `POST /analyze` body (474-625) with non-blocking 202; add 3 endpoints
- Modify: `backend/main.py` — startup sweep
- Test: `backend/tests/test_analyze_api.py` (use FastAPI `TestClient`, patch `job_manager.spawn_job`)

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_analyze_api.py
from fastapi.testclient import TestClient
def _client(monkeypatch):
    import database, importlib; importlib.reload(database)
    database.Base.metadata.create_all(database.engine)
    import services.job_manager as jm
    monkeypatch.setattr(jm, "spawn_job", lambda *a, **k: None)
    from main import app
    return TestClient(app), database

def test_analyze_returns_202_immediately(monkeypatch):
    c, db = _client(monkeypatch)
    r = c.post("/analyze", json={"ticker":"RELIANCE","exchange":"NSE","user_id":1,"scan_type":"extreme"})
    assert r.status_code == 202
    jid = r.json()["job_id"]
    assert db.get_job(jid)["status"] in ("QUEUED","RUNNING")

def test_second_job_blocked(monkeypatch):
    c, db = _client(monkeypatch)
    c.post("/analyze", json={"ticker":"A","exchange":"NSE","user_id":2,"scan_type":"standard"})
    r2 = c.post("/analyze", json={"ticker":"B","exchange":"NSE","user_id":2,"scan_type":"standard"})
    assert r2.status_code == 409
    assert "job_id" in r2.json()

def test_job_poll_and_cancel(monkeypatch):
    c, db = _client(monkeypatch)
    jid = c.post("/analyze", json={"ticker":"A","exchange":"NSE","user_id":3,"scan_type":"standard"}).json()["job_id"]
    assert c.get(f"/analyze/job/{jid}").json()["status"] in ("QUEUED","RUNNING")
    assert c.post(f"/analyze/{jid}/cancel").status_code == 200
    assert db.get_job(jid)["status"] == "CANCELLED"
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Replace `POST /analyze` and add endpoints**

```python
@router.post("/analyze", status_code=202)
async def analyze_endpoint(req: AnalyzeRequest):
    import database
    from services.job_manager import spawn_job
    ticker = req.ticker.upper()
    if req.user_id is not None:
        active = database.get_active_job_for_user(req.user_id)
        if active:
            return JSONResponse(status_code=409, content={
                "error_code": "ALREADY_RUNNING",
                "error_title": "Analysis Already Running",
                "job_id": active["job_id"], "ticker": active["ticker"],
                "suggested_action": "ATTACH_OR_CANCEL"})
    job = database.create_job(req.user_id, ticker, req.exchange, req.scan_type)
    spawn_job(job["job_id"], ticker, req.exchange, req.user_id, req.deep_scan, req.scan_type)
    return {"job_id": job["job_id"], "status": "QUEUED", "ticker": ticker}

@router.get("/analyze/job/{job_id}")
async def get_job_status(job_id: str):
    import database
    job = database.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error":"job not found"})
    if job["status"] == "SUCCEEDED" and job["result_id"]:
        job["result"] = database.get_analysis_by_id(job["result_id"])  # full_json
    return job

@router.get("/analyze/active")
async def get_active_job(user_id: int):
    import database
    return database.get_active_job_for_user(user_id) or {"status": "NONE"}

@router.post("/analyze/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    import database
    from services.job_manager import cancel_job
    if not database.get_job(job_id):
        return JSONResponse(status_code=404, content={"error":"job not found"})
    cancel_job(job_id)
    return {"job_id": job_id, "status": "CANCELLED"}
```

> Implementer: ensure `JSONResponse` imported; add `database.get_analysis_by_id(rid)` (returns parsed `full_json`) if missing. Delete the old blocking loop (474-625) and the now-unused `multiprocessing.Queue` path in this router (keep `_run_analysis_worker` only if still referenced elsewhere; otherwise remove). Keep `_build_analysis_error` for other endpoints.

- [ ] **Step 3b: `main.py` startup sweep**

```python
@app.on_event("startup")
def _sweep_stale_analysis_jobs():
    try:
        import database
        n = database.sweep_stale_jobs(90)
        if n: print(f"[startup] swept {n} stale analysis jobs → FAILED")
    except Exception as e:
        print(f"[startup] job sweep failed: {e}")
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git commit -m "Rework /analyze: 202 background job, job/active/cancel endpoints, startup sweep"`

---

## Task 9: Dashboard reads job rows + end-to-end smoke

**Files:**
- Modify: `backend/routers/dashboard.py` — `get_dashboard_snapshot` reads active jobs from DB
- Test: `backend/tests/test_dashboard_jobs.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_dashboard_jobs.py
def test_snapshot_includes_db_active_jobs(monkeypatch):
    import database, importlib; importlib.reload(database)
    database.Base.metadata.create_all(database.engine)
    j = database.create_job(1, "RELIANCE", "NSE", "extreme")
    database.update_job(j["job_id"], status="RUNNING", progress_pct=42, stage="debate")
    from routers.dashboard import get_dashboard_snapshot
    snap = get_dashboard_snapshot()
    jobs = snap["active_analyses"]
    assert any(v.get("progress_pct") == 42 for v in jobs.values()) or \
           any(x.get("progress_pct") == 42 for x in jobs)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — in `get_dashboard_snapshot`, query DB for `status in (QUEUED,RUNNING)` jobs and merge into `active_analyses` (keyed by `job_id`, with `ticker/stage/progress_pct/tokens_used`). Keep token_stats/recent.

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Full-suite run + commit**

```bash
cd backend && python -m pytest tests/test_analysis_job.py tests/test_engine_bounds.py \
  tests/test_checkpoints.py tests/test_extreme_enrichers.py tests/test_extreme_output.py \
  tests/test_worker.py tests/test_job_manager.py tests/test_analyze_api.py \
  tests/test_dashboard_jobs.py -v
git commit -m "Dashboard reads AnalysisJob rows; v2 backend engine complete"
```

---

## Done / Verification

- [ ] Manual smoke (real keys, one cheap standard ticker): `POST /analyze` returns `202` instantly; `GET /analyze/job/{id}` shows progressing checkpoints; disconnecting client does **not** kill the job; `cancel` stops it; backend restart mid-run → job becomes `FAILED`.
- [ ] One extreme run completes in ≤ 10 min and returns the 4 graph bundles + extended thesis.
- [ ] `gitnexus_detect_changes()` shows only expected symbols touched.
- [ ] Phase 2 (iOS) tracked separately.
