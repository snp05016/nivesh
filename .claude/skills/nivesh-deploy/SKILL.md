---
name: nivesh-deploy
description: "Full server deploy + health check + endpoint audit + test suite. Use when user says 'deploy', 'redeploy', 'check server', 'verify everything', 'is everything working', 'nivesh deploy'. Runs exact-SHA checkout, systemd restart (nivesh.service), API health checks, endpoint audit, and pytest on the remote server. Returns ALL GOOD or FAILED with specifics."
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

### Step 1 — Server Sync (exact SHA)
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  cd /home/saumyapatel/Desktop/nivesh &&
  test -z \"\$(git status --porcelain)\" &&
  git fetch origin &&
  git checkout --detach $SHA &&
  git rev-parse HEAD
"
```
- `$SHA` is the full SHA recorded in Step 0. Never `git reset --hard origin/main`: it deploys whatever main points to now and wipes server-side changes.
- If the server tree is dirty (the `test -z` fails) → ABORT "Server tree dirty" and report `git status` to the owner
- Verify returned SHA matches local SHA
- If SHA mismatch → ABORT "Server SHA mismatch"

### Step 2 — Restart under systemd
systemd (`nivesh.service`) is the only supervisor of the production API. Never kill port 8000 (`fuser`/`pkill`) or start uvicorn with `nohup` or `--reload`: systemd would race the stray process for the port, and that process neither survives a reboot nor keeps its logs.
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  sudo systemctl restart nivesh &&
  sleep 5 &&
  systemctl is-active --quiet nivesh &&
  curl -fsS --max-time 5 http://localhost:8000/ping
"
```
- Must exit 0 and return `{"pong":true}`
- If not → ABORT "Server failed to start" and include `journalctl -u nivesh -n 50 --no-pager`

### Step 3 — Health Checks
```bash
curl -fsS --max-time 5 https://api.nivesh.qzz.io/ping         # expect {"pong":true}
curl -fsS --max-time 5 https://api.nivesh.qzz.io/health       # expect 200
curl -fsS --max-time 10 https://api.nivesh.qzz.io/health/live # expect 200
```
- All 3 must return 200 (`-f` makes curl exit non-zero on any 4xx/5xx)
- If not → ABORT "Health check failed"

### Step 4 — Critical Endpoint Audit
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

### Step 5 — Run Tests on Server
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

### Step 6 — Check for 5xx in Logs
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  journalctl -u nivesh --since '-10 min' --no-pager | grep -cE 'Traceback| 500 '
"
```
- If > 0 recent errors → ABORT "Server logs show errors"

---

## Success Output
```
✅ ALL GOOD — Server: <SHA>, Health: ok, Endpoints: 15/15, Tests: PASSED
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
