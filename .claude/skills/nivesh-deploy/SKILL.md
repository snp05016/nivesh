---
name: nivesh-deploy
description: "Full server deploy + health check + endpoint audit + test suite. Use when user says 'deploy', 'redeploy', 'check server', 'verify everything', 'is everything working', 'nivesh deploy'. Runs the pinned deploy script (scripts/deploy_server.py: worktree rehearsal, backup gate, exact-SHA checkout, systemd restart, readiness wait), endpoint audit, and pytest on the remote server. Returns ALL GOOD or FAILED with specifics."
---

# Nivesh Deploy & Verify Skill

Complete remote server deployment and verification pipeline. Executes in strict order — each step must pass before the next begins. Any failure stops the pipeline and reports the failing step.

---

## Pipeline

### Step 0 — Pre-flight
- Verify no uncommitted or untracked changes FIRST, before touching the branch: `git diff-index --quiet HEAD && test -z "$(git ls-files --others --exclude-standard)"`
- If dirty → ABORT "Local tree dirty" (never checkout over uncommitted work)
- Only then sync local main: `git fetch origin && git checkout main && git pull --ff-only origin main`
- Record full SHA: `SHA=$(git rev-parse HEAD)`

### Step 1 — Deploy the exact SHA
- `$SHA` must be on origin: if local main is ahead of `origin/main`, push it first (`git push origin main`).
- Then run the server's deploy script. It does the whole switch: tracked-files check, fetch, staged worktree, backup gate, migration rehearsal, checkout, `pip install -r requirements.txt`, `alembic upgrade head`, `sudo systemctl restart nivesh` and the wait for `/health/ready`. Do not run any of those steps by hand.
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && ../venv/bin/python scripts/deploy_server.py --sha $SHA"
```
- Exit 0 → continue. Any other exit → ABORT "Deploy script exit N" with its stderr, and never retry automatically:

| Exit | Report |
|------|--------|
| 2 | Precondition failed (server tracked files changed, fetch, unknown SHA). Nothing changed. |
| 3 | Backup failed. Nothing changed. |
| 4 | Migration rehearsal failed. Nothing changed. |
| 5 | Checkout or pip failed. The script went back to the previous commit. |
| 6 | Live migration failed. The script went back to the previous commit without restarting; report the backup file it printed. |
| 7 | Not ready within 60 s. Report the rollback command it printed and `journalctl -u nivesh -n 50 --no-pager`. The owner runs the rollback. |

- `--skip-rehearsal` only on the owner's explicit instruction, after exit 4 for a migration that needs a new dependency (docs/codebase/BACKUP_RESTORE.md, Deploying).
- systemd (`nivesh.service`) is the only supervisor of the production API: never kill port 8000 or start uvicorn by hand.

### Step 2 — Critical Endpoint Audit
Test these endpoints and verify 200 responses:

| Endpoint | Auth | Check |
|----------|------|-------|
| `GET /market-indices` | No | Len > 0 |
| `GET /search?q=RELIANCE` | No | Result array |
| `GET /api/v1/market/pulse` | No | Valid JSON |
| `GET /quick-info?ticker=RELIANCE` | No | Has ticker field |
| `GET /api/v1/stocks/RELIANCE.NS/financials` | Admin | Has line_items |
| `GET /api/v1/stocks/RELIANCE.NS/ml-signal` | Admin | Has ml_engine_mode |
| `GET /dividends/RELIANCE.NS` | No | Has dividends array |
| `GET /api/v1/predictions/performance` | Admin | Has total_predictions |
| `GET /api/v1/predictions/calibration?horizon=30d` | Admin | Has buckets |
| `POST /api/v1/options/payoff` | No | Valid JSON |
| `GET /fundamentals/RELIANCE.NS/financials` | No | Valid JSON |
| `GET /api/v1/earnings/surprises` | No | Valid JSON |
| `GET /api/v1/dashboard/ai-engine?limit=5` | Admin | Valid JSON |
| `GET /api/v1/market/anomalies` | No | Valid JSON |
| `GET /api/v1/market/sector-rotation` | No | Valid JSON |

- Any 500 → ABORT "Endpoint 5xx: /path"
- Admin rows: send `Authorization: Bearer $ADMIN_JWT`, the `access_token` from `POST /login` for an `is_admin` account (grant with `backend/scripts/manage_users.py set-admin <username>`; `/api/v1/predictions/performance` also needs that account on the pro tier). There is no static admin token: without a JWT from the owner, skip the Admin rows and report them as skipped.
- Verification must never call LLM-backed or CPU-heavy routes (analysis, multi-agent debate, assistant chat, NL screener, strategy sweep, stress test, portfolio PDF). Add such a check only behind `ALLOW_PAID_ENDPOINTS=1`, and only for an explicit, owner-approved run.

### Step 3 — Run Tests on Server
Run pytest from a throwaway worktree, never from the production checkout: the worktree has no `backend/.env`, so `load_dotenv(override=True)` in main.py cannot point the tests at the production database or keys.
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  cd /home/saumyapatel/Desktop/nivesh &&
  git worktree add --detach /tmp/nivesh-test-$SHA $SHA &&
  cd /tmp/nivesh-test-$SHA/backend &&
  test ! -e .env &&
  ENVIRONMENT=test DATABASE_URL=sqlite:////tmp/nivesh-test-$SHA/backend/stockapp_test.db \
  /home/saumyapatel/Desktop/nivesh/venv/bin/python3 -m pytest \
    tests/test_quantlab_api.py \
    tests/test_prediction_calibration_api.py \
    tests/test_predictions_performance.py \
    tests/test_prediction_logging.py \
    -v --tb=short
  rc=\$?
  cd / && git -C /home/saumyapatel/Desktop/nivesh worktree remove --force /tmp/nivesh-test-$SHA
  exit \$rc
"
```
- All tests must pass
- If any fail → ABORT "Tests failed: N failures"

### Step 4 — Check for 5xx in Logs
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  journalctl -u nivesh --since '-10 min' --no-pager | grep -cE 'Traceback| 500 '
"
```
- If > 0 recent errors → ABORT "Server logs show errors"

---

## Success Output
```
✅ ALL GOOD — Server: <SHA>, Deploy: exit 0, Endpoints: 15/15, Tests: PASSED
```

## Failure Output
```
❌ FAILED at <STEP> — <DETAIL>
```

---

## Configuration
| Config | Value |
|--------|-------|
| Server | 192.168.1.122 |
| User | saumyapatel |
| Path | /home/saumyapatel/Desktop/nivesh |
| Port | 8000 |
| Venv | /home/saumyapatel/Desktop/nivesh/venv |
| API | https://api.nivesh.qzz.io |
| Admin auth | JWT from `POST /login` for an `is_admin` account; no `ADMIN_TOKEN` (must not be set in server .env) |
