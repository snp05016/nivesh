# AI Engine Dashboard Design

## Goal

Replace the current single-job engine activity surface with a live terminal-style AI engine dashboard that shows every active and recent AI call: ticker, status, phase, progress, age, elapsed time, scan type, job ID, tokens, heartbeat, and checkpoint tail. The dashboard should match the operational usefulness of `scripts/check_stock.sh` while staying inside the app and backend API.

## User-Approved Direction

The approved visual direction is terminal-first. The main view is a dense monospaced console with command filters that mirror the scripts:

- `running`: current running AI calls.
- `--all`: recent jobs.
- `--stuck`: running jobs older than the stale threshold.
- ticker search: recent jobs for a specific stock.

The selected row opens a detail panel with job metadata, phase timeline, last checkpoint, error snippet when present, and the latest successful report summary when the job finished.

## Architecture

The backend will not shell out to the scripts from web requests. Instead, the script logic becomes shared repository/service logic that both the dashboard API and CLI scripts can call. This keeps controller code thin, uses `get_session()` for database access, and avoids duplicate query rules.

Planned backend units:

- `backend/repositories/job_repo.py`: add query functions for `running`, `all`, `stuck`, and ticker-filtered job lists, plus latest successful result lookup.
- `backend/services/ai_engine_monitor.py`: convert raw `AnalysisJob` rows into display-ready monitor records: relative age, elapsed/took labels, stuck flag, last heartbeat, current phase, last message, and checkpoint timeline.
- `backend/routers/dashboard.py`: add authenticated JSON routes and include the same monitor payload in the existing SSE snapshot.
- `backend/scripts/check_jobs.py` and `backend/scripts/show_result.py`: use the shared monitor functions so terminal output and dashboard output stay aligned.

Planned iOS units:

- `AnalysisEngineManager.swift`: fetch the new AI-engine payload on a polling cadence and expose a list of monitor records, not only one active job.
- `NetworkManager.swift`: add typed API calls for `/api/v1/dashboard/ai-engine` and `/api/v1/dashboard/ai-engine/{job_id}`.
- `EngineActivityView.swift`: refactor from a single active-job sheet into a terminal-style console with filter controls, ticker search, row selection, and phase timeline. Large sections must be separate `View` structs to avoid SwiftUI stack growth.

## Backend Data Contract

`GET /api/v1/dashboard/ai-engine?mode=running|all|stuck&ticker=RELIANCE&limit=20` returns:

```json
{
  "type": "ai_engine_monitor",
  "mode": "running",
  "generated_at": "2026-06-16T12:00:00Z",
  "summary": {
    "running": 2,
    "queued": 1,
    "stuck": 0,
    "terminal_recent": 10
  },
  "jobs": [
    {
      "job_id": "abc123",
      "ticker": "RELIANCE",
      "status": "RUNNING",
      "stage": "research",
      "current_phase": "research",
      "progress_pct": 42,
      "age_seconds": 122,
      "age_label": "2m2s",
      "elapsed_seconds": 98,
      "elapsed_label": "1m38s",
      "took_label": null,
      "scan_type": "deep",
      "tokens_used": 8112,
      "pid": 12345,
      "last_heartbeat_label": "4s ago",
      "is_stuck": false,
      "last_message": "Bear researcher complete"
    }
  ]
}
```

`GET /api/v1/dashboard/ai-engine/{job_id}` returns the same job record plus:

- full checkpoint timeline, newest last.
- terminal error snippet when present.
- latest successful report summary when available for that ticker.

The existing `/api/v1/dashboard/stream` event payload adds an `ai_engine` field with the same shape as the running monitor response. Existing `active_analyses`, `recent_analyses`, harvester, and token fields remain for compatibility.

## UI Behavior

The console must prioritize visibility over decoration:

- Top command strip: `running`, `all`, `stuck`, ticker input, and refresh.
- Main table columns: ticker, status, phase, progress, age, took/elapsed, scan, job ID.
- Rows use status color accents through `Theme.*` tokens only.
- Detail panel shows selected job metadata, last heartbeat, last message, token count, process ID, error snippet, and phase timeline.
- The view must use Banknote Aesthetic rules: `Theme.*` colors, Theme font helpers, `GuillocheDivider`, `EKPressStyle`, haptics on taps, and no raw hex values.
- Large SwiftUI sections must be separate structs. Inline `-> some View` helpers over five lines are out of scope for new code.

## Error Handling

Backend route failures return HTTP exceptions with actionable messages. Monitor formatting must tolerate missing timestamps, malformed checkpoint JSON, missing result JSON, and naive datetimes. Router functions should not query the database directly.

iOS displays a specific inline error if monitor fetch fails, keeps the last successful job list on screen, and shows a small retry control. A failed detail fetch does not blank the console.

## Testing

Use TDD. Required backend tests:

- repository/service returns the same mode semantics as `check_jobs.py`: running, `--all`, `--stuck`, and ticker lookup.
- time labels handle naive and timezone-aware timestamps.
- stuck detection uses the 15-minute script threshold.
- detail response includes checkpoint timeline and error snippet.
- dashboard snapshot includes `ai_engine` without removing existing fields.
- authenticated route returns the expected JSON contract.

Required iOS verification:

- static source scan for AGENTS.md violations: raw hex colors, `.font(.system(size:))`, plain `Divider()`, hardcoded arbitrary spacing, missing button style for new buttons.
- no `xcodebuild` runs.

## Deployment

After implementation, run backend tests locally, update graphify with `graphify update .`, commit, push, then pull and test on the remote server using the non-interactive commands from `AGENTS.md`.
