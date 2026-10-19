# Scheduler

One APScheduler instance, built in `services/harvest_worker.start_scheduler` and run only by the worker that holds the fcntl lock `/tmp/nivesh_scheduler.lock` (the leader). It runs in `Asia/Kolkata`: cron fields are IST wall clock. There is no separate worker process yet; `CLOUD_MIGRATION.md` records when that changes.

Every job is added through `_track_all_jobs`, so each run writes a `job_runs` row (sync and async jobs alike, including the research jobs and any job added later). See `OBSERVABILITY.md`. At start the leader marks leftover `running` rows as abandoned.

## Jobs

| id | Schedule (IST) | Notes |
|---|---|---|
| advisor_harvest | 07:00 | |
| morning_brief_pregen | 06:30 | |
| error_digest | 07:00 | daily digest to the ops webhook |
| corporate_actions | 07:30 | |
| model_canary | 08:30 | `CANARY_ENABLED=0` makes it a no-op |
| price_alerts | Mon-Fri 09:00-15:55, every 5 min | runs only while the market is open |
| anomaly_scan | Mon-Fri 09:30-16:30, hourly at :30 | |
| portfolio_snapshot | 16:30 | |
| nightly_screen | 16:45 | |
| portfolio_snapshot_retry | 17:30 | fills users skipped for a missing price |
| bhavcopy | 19:00 | |
| piotroski_weekly | Sun 23:00 | |
| legacy_outcome_eval | 02:00 | until the research engine retires legacy analyses |
| db_backup | 02:30 | |
| prediction_outcomes | 02:40 | |
| notification_cleanup | 03:00 | |
| preferences_backfill | 03:05 | |
| rag_ingest | 03:15 | also runs 5 minutes after boot |
| retention | 03:20 | news, job payloads, alerts, token log, job_runs, user_events |
| process_deletion_requests | 03:30 | account erasure after the grace period |
| restore_drill | day 1 of the month, 04:00 | `restore_drill.py`; see `BACKUP_RESTORE.md` |
| news_harvest, youtube_metadata, youtube_portfolio, expert_harvest, sebi_harvest, youtube_expert_harvest | every 2 h, staggered | interval jobs |
| job_sweep | every 2 min | stale analysis jobs |

## Research jobs (UTC)

`services/research/jobs.register_research_jobs` pins its 7 cron jobs to `timezone="UTC"` because the windows start at :30 IST. Their IST equivalents: kick Mon-Fri 19:45 and 21:00 and Tue-Sat 07:15; poll every 5 min 06:30-09:25 and 19:30-00:25; score Mon-Fri 22:30; live metrics Sun 10:00; cleanup 02:30.

## Rules for new jobs

- Use IST wall clock. Use `timezone="UTC"` only for windows defined in UTC.
- Always pass `id=`.
- Write jobs as plain `def` that raise on failure (do not swallow the exception; a bare `raise` after logging is enough). Async jobs also work and stay on the event loop.
- Tracking is automatic.
