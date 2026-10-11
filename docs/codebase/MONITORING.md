# Monitoring and Alerting

Single home server, no paid tooling. Four pieces, each owned by the operator.

## 1. External uptime check

Create a free HTTP monitor (UptimeRobot or healthchecks.io), 5 minute interval, alerting
the owner's phone:

- URL: `https://api.nivesh.qzz.io/healthz` (runs `SELECT 1`; 503 when the DB is down).
  Once `/health` checks the DB (REL-18), point the monitor at `/health` instead.
- Alert when the status is not 200 or the request times out.

`/ping` and `/health/live` only prove the process answers HTTP; never use them as the
uptime signal.

## 2. Backup dead-man switch

`BACKUP_HEARTBEAT_URL` (see `BACKUP_RESTORE.md`) is pinged after every nightly backup and
`<url>/fail` on failure. Configure the healthchecks.io check with a 1 day period so a
missed backup alerts too.

## 3. Daily error digest delivery

At 07:00 IST the scheduler runs `services/error_telemetry.generate_daily_digest()`, which
writes `backend/logs/nightly_digest_<date>.txt` and, when `OPS_ALERT_WEBHOOK_URL` is set
in `backend/.env`, POSTs the digest (plain text, first 4000 chars, header `Title`) to it.

- ntfy.sh: `OPS_ALERT_WEBHOOK_URL=https://ntfy.sh/<long-random-private-topic>` and
  subscribe to that topic in the ntfy phone app.
- Slack/Discord need JSON; put a small relay in front or use ntfy.

Delivery failures are logged as a warning and never break the digest job. The digest
covers the `*ErrorLog` tables only; 5xx tracebacks live in journald.

## 4. Logs

- Process stdout/stderr: journald via `nivesh.service`.
  - `journalctl -u nivesh -f` (follow)
  - `journalctl -u nivesh --since "1 hour ago" -p err`
  - `journalctl -u nivesh --since today | grep -c Traceback`
- `logs/advisor_harvester.log`: rotates itself (5 MB x 5 files).
- `token_log.jsonl` and `logs/advisor_harvest.log`: rotated daily, 30 kept, by logrotate:

  ```bash
  sudo cp backend/deploy/logrotate-nivesh.conf /etc/logrotate.d/nivesh
  sudo logrotate -d /etc/logrotate.d/nivesh   # dry run
  ```

## Startup configuration checks

`core/config_guard.validate_startup_config()` runs before `main.py` imports anything else.
Unset `ENVIRONMENT` counts as production. In production it refuses to start on a weak
`JWT_SECRET`, wildcard CORS or an unknown `ENVIRONMENT` value, and logs CRITICAL when APNs
credentials are missing (unless `ALERTS_PUSH_DISABLED=true`) or `APNS_ENVIRONMENT` is not
`production`. These run before logging is configured, so they reach journald as plain
stderr lines at info priority (`-p crit` will not show them). After every deploy run:

```bash
journalctl -u nivesh -b | grep -E "APNs not configured|APNS_ENVIRONMENT is not|ENVIRONMENT is unset"
```

## Optional follow-up

Sentry (`sentry-sdk`, free tier) would capture 5xx tracebacks with context. It is a new
dependency, so it is deferred until the owner decides.
