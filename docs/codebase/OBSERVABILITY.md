# Observability

The baseline is `job_runs` (per-run job history) plus a daily model canary. See also `MONITORING.md` for uptime checks and log rotation.

## What `job_runs` records

Every scheduled job, sync or async, writes one row per run (`services/job_runs.tracked`): name, status (`running`, `ok`, `failed`), start and finish time (naive UTC, served with a trailing `Z`), duration, rows written, the scrubbed error (2,000 characters at most) and a small `meta` JSON.

- A coroutine job keeps running on the scheduler's event loop. Only the bookkeeping, including the alert POST, runs in a worker thread. There is no `asyncio.run` path.
- Bookkeeping failures are logged and never stop the job.
- Errors are scrubbed before storage: emails, PAN, Bearer tokens, URL credentials and runs of 10 or more digits are masked.
- A `running` row left by a restart becomes `failed` ("abandoned: scheduler restarted") when the scheduler leader starts. No alert.

## Alerts

Alerts go to `OPS_ALERT_WEBHOOK_URL` (ntfy-compatible plain text, `Title` header).

- "Nivesh job failed: X" is sent only for the first failure in a streak. The body is the scrubbed error, capped at 300 characters.
- "Nivesh job recovered: X" is sent on the next `ok` run.
- The daily digest has a "Scheduled jobs (last 24h)" block. If its query fails it prints `UNKNOWN - query failed`.

Use a self-hosted ntfy server or an access-controlled topic. Anyone who knows a public ntfy.sh topic name can read it. The relay is listed as a processor ("Operations alert relay (owner-chosen): scrubbed error text only") in `docs/compliance/DPDP_RUNBOOK.md` and in the data export.

## Model canary

`services/model_canary.py` runs daily at 08:30 IST and sends a one-token request to each configured model id. It is registered by the scheduler package and is switched off with `CANARY_ENABLED=0` (an ops job, not a server flag). A retired model id fails the run, and the failure alert above fires.

## Retention and volume

`run_retention` deletes `job_runs` rows older than 90 days (03:15 IST). Expect about 2,000 rows a week and about 25,000 at the 90-day cap.

## Where to look

- Admin console, Jobs page.
- `journalctl -u nivesh`.
- SQL:

```sql
-- latest run per job
SELECT j.* FROM job_runs j
JOIN (SELECT job_name, MAX(id) AS id FROM job_runs GROUP BY job_name) m ON m.id = j.id
ORDER BY j.job_name;

-- failures in the last 7 days
SELECT job_name, COUNT(*) FROM job_runs
WHERE status = 'failed' AND started_at > now() - interval '7 days'
GROUP BY job_name ORDER BY 2 DESC;
```

## Deferred

- `/api/v1/data-status` and user-facing "as of" footers. Engine reports already carry staleness; read `job_runs.latest_by_job()` when a screen needs it.
- Merging the four `*_error_logs` tables.
- GlitchTip or consented crash upload (needs consent and a new dependency).
- Missed-run detection. The backup heartbeat already catches a dead scheduler.
- Thread-pool size knob. If `/health` latency rises while the CPU is idle, set `anyio.to_thread.current_default_thread_limiter().total_tokens` at startup. Not built until measured.
