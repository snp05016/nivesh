# Backup & Restore

> Added 2026-10-11 (OPS-03). Code: `backend/services/backup_service.py`, `backend/scripts/backup_db.py`, scheduler job `db_backup` in `backend/services/harvest_worker.py`.

## What is backed up, and when

| Datastore | When it is included | Method | File |
|---|---|---|---|
| Main DB, SQLite | `DATABASE_URL` is `sqlite:...` (or unset) | SQLite online backup API, then `PRAGMA quick_check` on the copy | `stockapp-<UTC stamp>.db` |
| Main DB, PostgreSQL | `DATABASE_URL` is `postgresql...` | `pg_dump --format=custom` | `stockapp-<UTC stamp>.dump` |
| `backend/harvester.db` | the file exists | SQLite online backup API | `harvester-<UTC stamp>.db` |
| RAG pgvector DB | `RAG_DB_PASS` is set | `pg_dump --format=custom` (`RAG_DB_HOST/USER/NAME`) | `rag-<UTC stamp>.dump` |

- **Nightly** at 21:00 UTC (02:30 IST) from the APScheduler, which runs in one uvicorn worker only. **RPO is 24 hours.**
- **Before every server migration**, by hand, through the backup gate (see below).
- Copies go to `BACKUP_DIR` (default `~/nivesh-backups`), outside the git checkout, so `git reset --hard` or `git clean` cannot delete them. The newest `BACKUP_KEEP` copies (default 14) of each datastore are kept.
- A target that fails does not stop the others, but the run reports failure: the scheduler job logs `[db_backup] Error`, the CLI exits 1, and the heartbeat gets a `/fail` ping.

Settings (`backend/.env`): `BACKUP_DIR`, `BACKUP_KEEP`, `BACKUP_HEARTBEAT_URL`. Postgres targets need `pg_dump` (package `postgresql-client`) at the server's major version.

## Pre-migration backup gate

Run every server migration (`upgrade`, `downgrade`, `stamp`) like this:

```bash
cd /home/saumyapatel/Desktop/nivesh/backend
../venv/bin/python scripts/backup_db.py && ../venv/bin/alembic upgrade head
```

`backup_db.py` prints one line per datastore with the file it wrote. If it prints `BACKUP FAILED`, do not migrate; fix the backup first. It loads `backend/.env` without overriding variables already exported in the shell, so a `DATABASE_URL` exported for alembic is the one that gets backed up.

## Monitoring (dead-man switch)

Create a check on healthchecks.io (period 1 day, grace 2 hours) and set its ping URL as `BACKUP_HEARTBEAT_URL`. Every successful run pings the URL; a failed run pings `<url>/fail`. A night with no ping at all (API down, scheduler not running) also alerts, so the check doubles as a scheduler liveness signal.

## Off-host copy

The code only writes to the local disk; a disk failure takes the backups with it unless they are copied elsewhere. Add a crontab entry for the service user on the server (`crontab -e`), for example:

```cron
30 4 * * * rclone copy /home/saumyapatel/nivesh-backups remote:nivesh-backups && rclone delete --min-age 60d remote:nivesh-backups
```

Use `copy`, not `sync`: if the local folder is wiped, `sync` would wipe the off-host copy too. `rsync -a` (without `--delete`) to another machine works the same way.

## Restore

### SQLite main DB (or harvester.db)

```bash
cd /home/saumyapatel/Desktop/nivesh/backend
sudo systemctl stop nivesh                         # stop every writer first (systemd only, no pkill)
pgrep -fa "uvicorn|job_worker"                     # must print nothing
mkdir -p ~/nivesh-pre-restore
mv stockapp.db stockapp.db-wal stockapp.db-shm ~/nivesh-pre-restore/ 2>/dev/null   # keep the old files, and never leave a stale -wal beside the restored DB
cp ~/nivesh-backups/stockapp-<STAMP>.db stockapp.db
../venv/bin/python -c "import sqlite3; print(sqlite3.connect('stockapp.db').execute('PRAGMA integrity_check').fetchone()[0])"   # expect: ok
sudo systemctl start nivesh && systemctl is-active nivesh   # systemd is the only production supervisor (AGENTS.md section 6.5)
curl -fsS http://127.0.0.1:8000/health
```

Use the path from `DATABASE_URL` if it is not `backend/stockapp.db`. For `harvester.db`, do the same with `harvester-<STAMP>.db`. If the restored DB is older than the code's Alembic head, run the backup gate and `alembic upgrade head` before starting the service.

### PostgreSQL main DB or RAG DB

Stop the backend first, then:

```bash
PGPASSWORD='<password>' pg_restore --clean --if-exists --no-owner \
  --dbname 'postgresql://<user>@<host>:5432/<db>' ~/nivesh-backups/stockapp-<STAMP>.dump
PGPASSWORD='<RAG_DB_PASS>' pg_restore --clean --if-exists --no-owner \
  --host 127.0.0.1 --username saumyapatel --dbname nivesh ~/nivesh-backups/rag-<STAMP>.dump
```

If the RAG restore fails on the `vector` extension, create it first as a superuser (`CREATE EXTENSION IF NOT EXISTS vector;`). Start the backend and check `/health`.

## Quarterly restore drill

Never drill against the live files, and never start a second backend on a restored copy (its price-alert poller would push real notifications).

1. Run `../venv/bin/python scripts/backup_db.py` and note the file it printed for `stockapp`.
2. Copy that file to a scratch folder: `mkdir -p /tmp/nivesh-drill && cp <file> /tmp/nivesh-drill/stockapp.db`.
3. Check it: `PRAGMA integrity_check` returns `ok`, and row counts for `users`, `portfolio`, `portfolio_transactions` and `analysis_history` match the live DB (allow for writes since the backup).
4. Fetch one file back from the off-host copy (`rclone copy remote:nivesh-backups/<file> /tmp/nivesh-drill/`) and repeat step 3 on it.
5. Confirm the healthchecks.io check shows a ping from the last night.
6. Delete `/tmp/nivesh-drill` and record the date, file and result in the ops log.

## Monthly restore drill

`services/restore_drill.py` runs on day 1 of every month at 04:00 IST (scheduler job `restore_drill`) and by hand with `../venv/bin/python scripts/restore_drill.py [--backup PATH]`. It takes the newest `stockapp-*` backup in `BACKUP_DIR` and:

- SQLite: copies it to a temp directory, requires `PRAGMA integrity_check` to return `ok`, and counts rows.
- PostgreSQL: always runs `pg_restore --list`. When `RESTORE_DRILL_PG_URL` is set, it also restores into that scratch database and counts rows. When it is unset the result is `listed_only`.
- Compares counts with the live database for `users`, `portfolio`, `portfolio_transactions`, `kyc_consents`, `audit_log_entries`, `research_predictions` and `job_runs`. It fails when a live table with at least 100 rows has under 50% of them in the backup, or when `users` or `portfolio_transactions` is empty in the backup but not live.

**Setting up `RESTORE_DRILL_PG_URL`.** Point it only at an empty scratch database, for example `createdb nivesh_restore_drill`, owned by a role that can restore into it. The database name must contain `drill` or `scratch`, and it must not be any database named in `DATABASE_URL` or another `*_DATABASE_URL` (harvester, RAG). The code refuses both cases before it runs any subprocess, and the restore uses `--clean`, so it would overwrite whatever it is pointed at. Install a `postgresql-client` that matches the server's major version.

**Where results appear.** Each run is a `restore_drill` row on the admin Jobs page, and a failure sends an alert through `OPS_ALERT_WEBHOOK_URL`. The quarterly manual drill above still covers fetching a file back from the off-host copy.

