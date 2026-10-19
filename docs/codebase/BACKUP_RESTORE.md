# Backup & Restore

> Added 2026-10-11 (OPS-03). Code: `backend/services/backup_service.py`, `backend/scripts/backup_db.py`, scheduler job `db_backup` in `backend/services/harvest_worker.py`, deploys through `backend/scripts/deploy_server.py` (C5).

## What is backed up, and when

| Datastore | When it is included | Method | File |
|---|---|---|---|
| Main DB, SQLite | `DATABASE_URL` is `sqlite:...` (or unset) | SQLite online backup API, then `PRAGMA quick_check` on the copy | `stockapp-<UTC stamp>.db` |
| Main DB, PostgreSQL | `DATABASE_URL` is `postgresql...` | `pg_dump --format=custom` | `stockapp-<UTC stamp>.dump` |
| `backend/harvester.db` | the file exists | SQLite online backup API | `harvester-<UTC stamp>.db` |
| RAG pgvector DB | `RAG_DB_PASS` is set | `pg_dump --format=custom` (`RAG_DB_HOST/USER/NAME`) | `rag-<UTC stamp>.dump` |

- **Nightly** at 21:00 UTC (02:30 IST) from the APScheduler, which runs in one uvicorn worker only. **RPO is 24 hours.**
- **Before every server migration**, by hand, through the backup gate (see below).
- Copies go to `BACKUP_DIR` (default `~/nivesh-backups`), outside the git checkout, so `git reset --hard` or `git clean` cannot delete them. Backups hold PII: the directory is mode 0700 and every file 0600. The newest `BACKUP_KEEP` copies (default 14) of each datastore are kept.
- A target that fails does not stop the others, but the run reports failure: the scheduler job logs `[db_backup] Error`, the CLI exits 1, and the heartbeat gets a `/fail` ping.

Settings (`backend/.env`): `BACKUP_DIR`, `BACKUP_KEEP`, `BACKUP_HEARTBEAT_URL`. Postgres targets need `pg_dump` (package `postgresql-client`) at the server's major version.

## Pre-migration backup gate

`scripts/deploy_server.py` (see Deploying) runs this gate itself. Run every manual server migration (`upgrade`, `downgrade`, `stamp`) like this:

```bash
cd /home/saumyapatel/Desktop/nivesh/backend
../venv/bin/python scripts/backup_db.py && ../venv/bin/alembic upgrade head
```

`backup_db.py` prints one line per datastore with the file it wrote. If it prints `BACKUP FAILED`, do not migrate; fix the backup first. It loads `backend/.env` without overriding variables already exported in the shell, so a `DATABASE_URL` exported for alembic is the one that gets backed up.

## Monitoring (dead-man switch)

Create a check on healthchecks.io (period 1 day, grace 2 hours) and set its ping URL as `BACKUP_HEARTBEAT_URL`. Every successful run pings the URL; a failed run pings `<url>/fail`. A night with no ping at all (API down, scheduler not running) also alerts, so the check doubles as a scheduler liveness signal.

## Encrypted off-host copy

The code only writes to the local disk; a disk failure takes the backups with it unless they are copied elsewhere. The copies hold users' PII, so they leave the server only through an rclone **crypt** remote, never a plain one:

1. `rclone config`: create the storage remote (for example `nivesh-store`, any provider), then a `crypt` remote named `nivesh-crypt` whose `remote` is `nivesh-store:nivesh-backups`, with filename encryption on and a generated password and salt. Keep both in the password manager: without them the off-host copy cannot be read.
2. Add a crontab entry for the service user (`crontab -e`) that runs after the 02:30 IST backup. Cron uses the server's clock; this line is 03:00 IST on an IST clock (use `30 21 * * *` on a UTC clock):

```cron
0 3 * * * find /home/saumyapatel/nivesh-backups -name 'stockapp-*' -mmin -120 | grep -q . && rclone sync /home/saumyapatel/nivesh-backups nivesh-crypt:backups
```

`sync` mirrors `BACKUP_KEEP` pruning to the remote. The `find` guard skips the run unless tonight's backup exists, so an emptied or stale local folder never wipes the off-host copy.

3. Enable full-disk encryption on the server (LUKS) so a stolen or discarded disk does not leak the local copies.

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
4. Fetch one file back from the off-host copy (`rclone copy nivesh-crypt:backups/<file> /tmp/nivesh-drill/`) and repeat step 3 on it.
5. Confirm the healthchecks.io check shows a ping from the last night.
6. Delete `/tmp/nivesh-drill` and record the date, file and result in the ops log.

## Deploying

Every server deploy is one exact commit. Push it, then on the server:

```bash
cd /home/saumyapatel/Desktop/nivesh/backend
../venv/bin/python scripts/deploy_server.py --sha <full 40-character sha>
```

The script stages the commit in a temporary `git worktree` outside the repo first. The pending-migration check and the rehearsal run against that staged copy, so a bad commit or a failing migration is found while the live tree, the running service and the live database are all untouched. Only then does it check the commit out in the live tree, install its requirements, migrate the live database (taking a backup first) and restart `nivesh` under systemd, waiting up to 60 s for `/health/ready`.

When the commit has pending migrations, the rehearsal migrates a copy of the backup the script just took with the commit's own migrations, then runs `alembic check`. A SQLite backup is copied to a temp folder. A Postgres backup is restored into the scratch database named by `RESTORE_DRILL_PG_URL` (in `backend/.env`), which must differ from `DATABASE_URL` in host, port or database.

| Exit | Meaning | State and rollback |
|---|---|---|
| 0 | Deployed and ready | - |
| 2 | Precondition failed: tracked files changed on the server, fetch failed, unknown commit, or the staged worktree / alembic could not run | Nothing changed. Untracked files (logs, local DBs) never block. |
| 3 | Backup failed | Nothing changed. Fix the backup (see above) and re-run. |
| 4 | Rehearsal failed, no fresh backup, or `RESTORE_DRILL_PG_URL` missing or equal to the live DB | Nothing changed. Fix the migration in a new commit. |
| 5 | `git checkout` or `pip install` failed in the live tree | The script checked out the previous commit and reinstalled its requirements. The service never restarted. |
| 6 | Live `alembic upgrade head` failed | The script checked out the previous commit and reinstalled its requirements, and did not restart. It prints the backup file: restore it (see Restore) only if `alembic current` no longer shows the previous revision. Postgres rolls back failed DDL; SQLite may not. |
| 7 | The service did not become ready within 60 s | The script prints `git checkout --detach <prev> && ../venv/bin/pip install -r requirements.txt && sudo systemctl restart nivesh`, preceded by "restore <backup> first" when it migrated. Run it by hand. |

- The script never restores a database automatically and never hard-resets the checkout.
- `--skip-rehearsal` skips step 5 (the backup still runs). The rehearsal uses the live venv, so a migration that needs a dependency added in the same commit fails the rehearsal. That failure is safe: read the migration, then re-run with `--skip-rehearsal`.
- Every run appends one JSON line to `~/nivesh-deploys.log`: `ts_utc`, `sha`, `prev_sha`, `migrated`, `rehearsal` (`sqlite`, `postgres`, `skipped` or `none`) and `exit_code`.
- The service user needs a sudoers rule for `systemctl restart nivesh` only, with no password.
- The commit that introduces `deploy_server.py` is deployed once with the old manual steps (`git checkout --detach <sha>`, `pip install -r requirements.txt`, the backup gate and `alembic upgrade head`, `sudo systemctl restart nivesh`), because the script is not on the server yet.

## Destructive migrations

Before a migration that drops a table or column, or deletes rows, archive the data it removes, separately from the nightly backups, which rotate out after `BACKUP_KEEP` days:

```bash
pg_dump -Fc -t <table> [-t <table> ...] --dbname '<libpq DSN>' > archive.dump   # each affected table, PGPASSWORD in the env
gpg --symmetric --cipher-algo AES256 archive.dump    # or: age -p -o archive.dump.age archive.dump
shred -u archive.dump                                # never keep the plain dump
rclone copy archive.dump.gpg nivesh-crypt:archives/<migration id>/
```

For SQLite, copy the fresh `stockapp-*.db` backup instead and encrypt it the same way. Record the archive in the ops log and delete it, locally and off-host, after 30 days.
