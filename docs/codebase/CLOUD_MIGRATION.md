# Cloud migration (I48)

**Status: deferred.** The council called a managed cloud the right destination at the wrong time. The home server stays until a trigger below is hit.

## Triggers (any one starts the move)

- Before billing goes live (roadmap Step 5).
- Partner due diligence asks for hosted infrastructure.
- Two home-server outages longer than 4 hours in one month.
- A need for more than one API process or host.

## Already portable

- `DATABASE_URL` and `REDIS_URL` come from the environment.
- systemd is the only supervisor, with exact-SHA checkouts.
- `/health/ready` is a DB-backed readiness probe.
- Nightly backups (`BACKUP_RESTORE.md`) and the monthly restore drill, which can verify a new database.
- The ml-engine container is bound to 127.0.0.1.

## Target

- Managed Postgres with point-in-time recovery, and managed Redis, in an Indian region.
- One or two API VMs behind TLS.
- One worker VM running the scheduler and ml-engine.
- A staging copy of the stack, and an iOS staging base URL through `ServerURLPolicy`.

## Code needed at move time

- Split the scheduler out of the API process with an env switch and a worker entrypoint. The fcntl leader lock in `harvest_worker.start_scheduler` works on one host only.
- Redis-backed rate limits (FIX:ARCH-07).
- Connection-pool sizing (FIX:PERF-21).

## Cutover outline

1. Freeze writes (maintenance mode) and take a final backup (`scripts/backup_db.py`).
2. Restore it into the new managed database.
3. Run `scripts/restore_drill.py` against the new database to compare row counts.
4. Switch DNS for `api.nivesh.qzz.io` to the new API VMs.
5. Monitor `/health/ready`, the admin Jobs page and the alert webhook for a day.
6. Roll back by pointing DNS at the home server, which stays untouched and warm until the new stack has run a week.
