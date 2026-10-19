# Feature package platform-restore-drill: Monthly automated restore drill with scratch-database guards, plus cloud-move readiness doc

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 56 I48 Leave the home server

## Files (create or modify)
- backend/services/restore_drill.py
- backend/scripts/restore_drill.py
- backend/tests/test_restore_drill.py
- docs/codebase/BACKUP_RESTORE.md
- docs/codebase/CLOUD_MIGRATION.md
- backend/.env.example

## Dependencies
- Feature packages (integrated before you start): platform-jobruns
- Declared in the plan: platform-jobruns, FIX:OPS-03, FIX:DB-14, FIX:OPS-06, FIX:REL-18, FIX:OPS-18, FIX:AUTH-20. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I48: automates the only C5 piece the fix track leaves manual. No other cluster plan in this run builds a drill.

1. services/restore_drill.py: run_restore_drill(backup_path=None) -> dict.
   - Find the backup. Use the newest main-database backup written by FIX:OPS-03's backup_service. Files live in BACKUP_DIR and are named '<target>-<UTC %Y%m%dT%H%M%SZ>.*'. Use backup_service's main-DB target name, not the harvester or RAG targets. If there is none, raise RestoreDrillFailed('no backup found').
   - SQLite backup (.db):
     - Copy it into a tempfile.TemporaryDirectory.
     - Require PRAGMA integrity_check == 'ok'.
     - Count rows.
   - Any other backup file is a Postgres custom dump:
     - Always run ['pg_restore', '--list', path] with a 300 s timeout. If shutil.which('pg_restore') is None, raise RestoreDrillFailed('pg_restore not installed').
     - If RESTORE_DRILL_PG_URL is unset, return status 'listed_only'.
     - If it is set, first call _check_scratch_target(url). This happens before any subprocess call. Every refusal raises ValueError, and the message names the env var involved, never the URL:
       a. sqlalchemy.engine.make_url(url).database must contain 'drill' or 'scratch', case-insensitive; otherwise ValueError('RESTORE_DRILL_PG_URL database name must contain drill or scratch').
       b. Compare (host, port, database) with every env var named DATABASE_URL or ending in '_DATABASE_URL' (for example harvester or RAG Postgres). Normalise 'localhost', '127.0.0.1' and '::1' to one host, and a missing port to 5432. Skip values that do not parse. On a match, raise ValueError('scratch URL points at the database in <ENV NAME>').
     - Then run ['pg_restore', '--clean', '--if-exists', '--no-owner', '--dbname', url, path] with a 3600 s timeout.
     - Count rows through sqlalchemy.create_engine(url).
     - Never log URLs or passwords.
   - Counts:
     - DRILL_TABLES = users, portfolio, portfolio_transactions, kyc_consents, audit_log_entries, research_predictions, job_runs. Skip any table missing from either database.
     - Get live counts via get_session.
     - Fail when live >= 100 and backup < 50% of live.
     - Fail when live > 0 and backup == 0 for users or portfolio_transactions.
   - Return {'status': 'ok' or 'listed_only', 'backup': file name only, 'age_hours': float, 'tables': {name: {'backup': n, 'live': m}}}.
   - Raise RestoreDrillFailed with a one-line summary on any failed check.

2. scripts/restore_drill.py: a CLI using the same sys.path insert and dotenv(override=False) pattern as the other scripts.
   - It runs job_runs.tracked('restore_drill', run_restore_drill)(), so a manual run also records a job_runs row and alerts via notify_ops on failure.
   - Optional --backup PATH.
   - Prints the result dict; exits 1 on any exception.

3. Scheduling is platform-scheduler-ist's job: monthly, day 1, 04:00 IST, id 'restore_drill'.

4. docs/codebase/BACKUP_RESTORE.md (from FIX:OPS-03): add a 'Monthly restore drill' section covering:
   - what it checks;
   - RESTORE_DRILL_PG_URL setup: an empty scratch database only. Its name must contain 'drill' or 'scratch', and it must not be any database named in DATABASE_URL or another *_DATABASE_URL; the code refuses both;
   - where results appear (admin Jobs page, OPS webhook);
   - how to run it by hand.

5. docs/codebase/CLOUD_MIGRATION.md (new):
   - Status: deferred. The council called it the right destination at the wrong time.
   - Trigger conditions:
     - before billing goes live (roadmap Step 5);
     - partner due diligence;
     - two home-server outages longer than 4 h in one month;
     - a need for more than one API process or host.
   - Already portable: env DATABASE_URL and REDIS_URL, the systemd unit, the readiness probe, backups and this drill, and the ml-engine container bound to 127.0.0.1.
   - Target:
     - managed Postgres with point-in-time recovery, and managed Redis, in an Indian region;
     - 1-2 API VMs behind TLS;
     - one worker VM running the scheduler and ml-engine;
     - a staging copy;
     - an iOS staging base URL through ServerURLPolicy.
   - Code needed at move time:
     - split the scheduler out of the API process with an env switch and a worker entrypoint, because the fcntl leader lock only works on one host;
     - Redis-backed rate limits (FIX:ARCH-07);
     - pool sizing (FIX:PERF-21).
   - Cutover outline: freeze, final backup, restore, run restore_drill against the new database, switch DNS for api.nivesh.qzz.io, monitor, and roll back if needed.

6. .env.example: add RESTORE_DRILL_PG_URL, with a comment that it must point at an empty scratch database whose name contains 'drill' or 'scratch'.

## Acceptance checks
- AST parse and pyright are clean.
- tests/test_restore_drill.py (tmp_path, SQLite, hermetic) passes in CI with these cases:
  - A healthy backup returns status ok with counts.
  - A backup with users emptied raises RestoreDrillFailed.
  - A corrupt file raises RestoreDrillFailed.
  - No backup raises RestoreDrillFailed.
  - Each of these raises ValueError while a monkeypatched subprocess.run fails the test if it is ever called:
    - a RESTORE_DRILL_PG_URL whose database name lacks drill and scratch;
    - a drill-named URL equal to DATABASE_URL;
    - a drill-named URL equal to a monkeypatched HARVESTER_DATABASE_URL, given as 'localhost' versus '127.0.0.1' with the port omitted.
  - shutil.which monkeypatched to None on the Postgres path raises RestoreDrillFailed.
  - The CLI path writes a failed job_runs row, with notify_ops monkeypatched.
- Both docs exist. CLOUD_MIGRATION.md contains the trigger list, and BACKUP_RESTORE.md contains the naming rule.

## Cluster spec
docs/feature-specs/spec_platform.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
