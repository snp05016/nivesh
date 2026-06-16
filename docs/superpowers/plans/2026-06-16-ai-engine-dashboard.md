# AI Engine Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a live terminal-style AI engine dashboard that mirrors `scripts/check_stock.sh`/`backend/scripts/check_jobs.py` in the backend API, SSE snapshot, CLI scripts, and iOS engine activity sheet.

**Architecture:** Keep database queries in `backend/repositories/job_repo.py`, display formatting in `backend/services/ai_engine_monitor.py`, HTTP wiring in `backend/routers/dashboard.py`, and SwiftUI rendering in small separate view structs. The CLI scripts should call the same backend monitor service so the terminal and app stay aligned.

**Tech Stack:** FastAPI, SQLAlchemy via `get_session()`, pytest, SwiftUI, Codable models, existing Nivesh `Theme.*`/Banknote components.

---

## File Structure

- Create `backend/services/ai_engine_monitor.py`: monitor formatting, mode normalization, time labels, summary counts, detail payload.
- Modify `backend/repositories/job_repo.py`: add job query helpers and latest successful result lookup.
- Modify `backend/routers/dashboard.py`: add authenticated JSON routes and include `ai_engine` in snapshots.
- Modify `backend/scripts/check_jobs.py`: render CLI table from shared monitor service.
- Modify `backend/scripts/show_result.py`: render latest successful report from shared monitor detail.
- Create `backend/tests/test_ai_engine_monitor.py`: TDD coverage for modes, labels, detail, snapshot, and route contract.
- Modify `ios/StockApp/stockme/stockme/Models/AnalysisModels.swift`: add `AIEngineMonitorResponse`, `AIEngineJob`, and summary/detail Codable models.
- Modify `ios/StockApp/stockme/stockme/NetworkManager.swift`: add fetch methods.
- Modify `ios/StockApp/stockme/stockme/AnalysisEngineManager.swift`: add monitor polling state while preserving existing active-job fields.
- Modify `ios/StockApp/stockme/stockme/Views/EngineActivityView.swift`: render terminal-style console using separate `View` structs.

## Task 1: Backend Monitor Contract

**Files:**
- Create: `backend/services/ai_engine_monitor.py`
- Modify: `backend/repositories/job_repo.py`
- Test: `backend/tests/test_ai_engine_monitor.py`

- [ ] **Step 1: Write failing tests**

Add tests for mode semantics and labels:

```python
def test_ai_engine_monitor_running_all_stuck_and_ticker_modes():
    import database
    from services.ai_engine_monitor import build_ai_engine_monitor

    uid = _create_user()
    running = database.create_job(uid, "RELIANCE", "NSE", "deep")
    database.update_job(running["job_id"], status="RUNNING", stage="research", progress_pct=42)
    done = database.create_job(uid, "TCS", "NSE", "standard")
    database.update_job(done["job_id"], status="SUCCEEDED", stage="done", progress_pct=100)
    stuck = database.create_job(uid, "INFY", "NSE", "extreme")
    _age_job(stuck["job_id"], minutes=20, status="RUNNING", stage="debate")

    running_payload = build_ai_engine_monitor(mode="running")
    assert running["job_id"] in {job["job_id"] for job in running_payload["jobs"]}
    assert done["job_id"] not in {job["job_id"] for job in running_payload["jobs"]}

    all_payload = build_ai_engine_monitor(mode="all")
    assert done["job_id"] in {job["job_id"] for job in all_payload["jobs"]}

    stuck_payload = build_ai_engine_monitor(mode="stuck")
    assert stuck_payload["jobs"][0]["is_stuck"] is True

    ticker_payload = build_ai_engine_monitor(mode="running", ticker="TCS")
    assert ticker_payload["jobs"][0]["ticker"] == "TCS"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend && python3 -m pytest tests/test_ai_engine_monitor.py -q
```

Expected: fail because `services.ai_engine_monitor` does not exist.

- [ ] **Step 3: Implement repository helpers and monitor service**

Add repository functions with `get_session()` only:

```python
def list_jobs_for_monitor(*, mode: str = "running", ticker: str | None = None,
                          limit: int = 20, stuck_minutes: int = 15) -> list[dict]:
    ...

def get_latest_successful_job_for_ticker(ticker: str) -> Optional[dict]:
    ...
```

Add service functions:

```python
def build_ai_engine_monitor(*, mode: str = "running", ticker: str | None = None,
                            limit: int = 20, now: datetime | None = None) -> dict:
    ...

def build_ai_engine_job_detail(job_id: str, *, now: datetime | None = None) -> dict | None:
    ...
```

The output must include `type`, `mode`, `generated_at`, `summary`, and `jobs`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
cd backend && python3 -m pytest tests/test_ai_engine_monitor.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/repositories/job_repo.py backend/services/ai_engine_monitor.py backend/tests/test_ai_engine_monitor.py
git commit -m "feat(backend): add ai engine monitor service"
```

## Task 2: Dashboard API, SSE, and Scripts

**Files:**
- Modify: `backend/routers/dashboard.py`
- Modify: `backend/scripts/check_jobs.py`
- Modify: `backend/scripts/show_result.py`
- Test: `backend/tests/test_ai_engine_monitor.py`

- [ ] **Step 1: Write failing route and snapshot tests**

Add tests:

```python
def test_dashboard_snapshot_includes_ai_engine_payload():
    from routers.dashboard import get_dashboard_snapshot
    snap = get_dashboard_snapshot()
    assert "ai_engine" in snap
    assert snap["ai_engine"]["type"] == "ai_engine_monitor"


def test_ai_engine_route_returns_monitor_payload(monkeypatch):
    from fastapi.testclient import TestClient
    import main

    monkeypatch.setattr("routers.dashboard.require_auth", lambda authorization: {"id": 1})
    client = TestClient(main.app)
    response = client.get("/api/v1/dashboard/ai-engine?mode=all", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert response.json()["type"] == "ai_engine_monitor"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
cd backend && python3 -m pytest tests/test_ai_engine_monitor.py -q
```

Expected: fail because the route and snapshot field are missing.

- [ ] **Step 3: Implement thin dashboard routes**

Add:

```python
@router.get("/api/v1/dashboard/ai-engine")
async def ai_engine_dashboard(mode: str = "running", ticker: str | None = None,
                              limit: int = 20, authorization: str = Header(None)):
    require_auth(authorization)
    return build_ai_engine_monitor(mode=mode, ticker=ticker, limit=limit)
```

Add the detail route and include `ai_engine` in `get_dashboard_snapshot()`.

- [ ] **Step 4: Update scripts**

Make `backend/scripts/check_jobs.py` call `build_ai_engine_monitor()` and print the same columns plus `TOOK`. Make `backend/scripts/show_result.py` call `build_ai_engine_job_detail()`.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
cd backend && python3 -m pytest tests/test_ai_engine_monitor.py tests/test_dashboard_jobs.py -q
bash scripts/check_stock.sh --all
```

Expected: tests pass; script prints a table or `No jobs found.`

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/routers/dashboard.py backend/scripts/check_jobs.py backend/scripts/show_result.py backend/tests/test_ai_engine_monitor.py
git commit -m "feat(backend): expose ai engine dashboard feed"
```

## Task 3: iOS Monitor Models and Networking

**Files:**
- Modify: `ios/StockApp/stockme/stockme/Models/AnalysisModels.swift`
- Modify: `ios/StockApp/stockme/stockme/NetworkManager.swift`
- Modify: `ios/StockApp/stockme/stockme/AnalysisEngineManager.swift`

- [ ] **Step 1: Run GitNexus impact before symbol edits**

Run impact on `NetworkManager`, `AnalysisEngineManager`, and `JobStatus`. Warn before proceeding only if risk is HIGH or CRITICAL.

- [ ] **Step 2: Add Codable models**

Add Codable structs for the backend contract with explicit `CodingKeys`.

- [ ] **Step 3: Add network methods**

Add:

```swift
func fetchAIEngineMonitor(mode: String, ticker: String?, limit: Int) async throws -> AIEngineMonitorResponse
func fetchAIEngineJobDetail(jobId: String) async throws -> AIEngineJobDetail
```

Use `authRequest(_:)` and the existing `session`.

- [ ] **Step 4: Extend manager state**

Add published fields:

```swift
@Published var monitorJobs: [AIEngineJob] = []
@Published var monitorSummary: AIEngineSummary?
@Published var selectedMonitorJobId: String? = nil
@Published var monitorError: String? = nil
```

Poll the monitor while preserving existing single active-job fields for compatibility.

- [ ] **Step 5: Static verify**

Run:

```bash
rg -n "Color\\(hex|\\.font\\(\\.system\\(size:|Divider\\(\\)|\\.padding\\([0-9]" ios/StockApp/stockme/stockme/Models/AnalysisModels.swift ios/StockApp/stockme/stockme/NetworkManager.swift ios/StockApp/stockme/stockme/AnalysisEngineManager.swift || true
```

Expected: no new violations from these edits.

- [ ] **Step 6: Commit**

Run:

```bash
git add ios/StockApp/stockme/stockme/Models/AnalysisModels.swift ios/StockApp/stockme/stockme/NetworkManager.swift ios/StockApp/stockme/stockme/AnalysisEngineManager.swift
git commit -m "feat(ios): add ai engine monitor client"
```

## Task 4: iOS Terminal Console UI

**Files:**
- Modify: `ios/StockApp/stockme/stockme/Views/EngineActivityView.swift`

- [ ] **Step 1: Run GitNexus impact before symbol edits**

Run impact on `EngineActivityView` and `CheckpointRow`. Warn before proceeding only if risk is HIGH or CRITICAL.

- [ ] **Step 2: Replace single-job body with console layout**

Use separate structs:

```swift
struct AIEngineCommandStrip: View { ... }
struct AIEngineJobTable: View { ... }
struct AIEngineJobRow: View { ... }
struct AIEngineDetailPanel: View { ... }
struct AIEngineCheckpointTimeline: View { ... }
```

All buttons must call `HapticManager.selection()` and use `.buttonStyle(EKPressStyle())`.

- [ ] **Step 3: Preserve cancel behavior**

Show the existing stop action when the selected job matches `engineManager.activeJobId` and is running.

- [ ] **Step 4: Static verify**

Run:

```bash
rg -n "Color\\(hex|\\.font\\(\\.system\\(size:|Divider\\(\\)|GeometryReader|\\.padding\\([0-9]|\\.frame\\(width:" ios/StockApp/stockme/stockme/Views/EngineActivityView.swift || true
```

Expected: no new violations. Do not run `xcodebuild`.

- [ ] **Step 5: Commit**

Run:

```bash
git add ios/StockApp/stockme/stockme/Views/EngineActivityView.swift
git commit -m "feat(ios): render ai engine terminal console"
```

## Task 5: Final Verification, Review, and Deployment

**Files:**
- All changed files from tasks 1-4.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend && python3 -m pytest tests/test_ai_engine_monitor.py tests/test_dashboard_jobs.py -q
```

Expected: pass.

- [ ] **Step 2: Run broader backend tests if focused tests pass**

Run:

```bash
cd backend && python3 -m pytest -q
```

Expected: pass or only documented skips.

- [ ] **Step 3: Run Graphify update**

Run:

```bash
graphify update .
```

- [ ] **Step 4: Run GitNexus detect changes**

Run `gitnexus_detect_changes()` over all uncommitted changes and review affected processes.

- [ ] **Step 5: Final code review agent**

Dispatch a reviewer agent to check spec compliance, AGENTS.md rules, route thinness, repository/service separation, SwiftUI theming, script parity, and missing tests.

- [ ] **Step 6: Commit any review fixes**

Commit review fixes with a focused conventional commit.

- [ ] **Step 7: Push and remote verify**

Run:

```bash
git push
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && git pull"
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && pytest"
```

Expected: remote tests pass. Then verify server health with:

```bash
curl -fsS http://192.168.1.122:8000/healthz
```
