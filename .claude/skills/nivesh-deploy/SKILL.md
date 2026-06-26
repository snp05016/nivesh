---
name: nivesh-deploy
description: "Full server deploy + health check + endpoint audit + test suite. Use when user says 'deploy', 'redeploy', 'check server', 'verify everything', 'is everything working', 'nivesh deploy'. Runs pull, process kill, uvicorn restart, API health checks, endpoint audit, and pytest on the remote server. Returns ALL GOOD or FAILED with specifics."
---

# Nivesh Deploy & Verify Skill

Complete remote server deployment and verification pipeline. Executes in strict order — each step must pass before the next begins. Any failure stops the pipeline and reports the failing step.

---

## Pipeline

### Step 0 — Pre-flight
- Verify local main is synced: `git checkout main && git pull --ff-only origin main`
- Verify no uncommitted changes: `git diff-index --quiet HEAD`
- Record SHA: `SHA=$(git rev-parse --short HEAD)`

### Step 1 — Server Sync
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  cd /home/saumyapatel/Desktop/nivesh &&
  git fetch origin &&
  git checkout main &&
  git reset --hard origin/main &&
  git rev-parse --short HEAD
"
```
- Verify returned SHA matches local SHA
- If SHA mismatch → ABORT "Server SHA mismatch"

### Step 2 — Kill & Restart
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  sudo fuser -k 8000/tcp 2>/dev/null
  sleep 2
  cd /home/saumyapatel/Desktop/nivesh/backend &&
  nohup /home/saumyapatel/Desktop/nivesh/venv/bin/uvicorn main:app \
    --host 0.0.0.0 --port 8000 --reload \
    > /tmp/uvicorn.log 2>&1 &
  sleep 5
  curl -s http://localhost:8000/ping
"
```
- Must return `{"pong":true}`
- If not → ABORT "Server failed to start"

### Step 3 — Health Checks
```bash
curl -s --max-time 5 https://api.nivesh.qzz.io/ping     # expect {"pong":true}
curl -s --max-time 5 https://api.nivesh.qzz.io/health    # expect {"status":"ok"}
curl -s --max-time 10 https://api.nivesh.qzz.io/health/live  # expect 200
```
- All 3 must return 200
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
| `GET /api/v1/backtests/strategy-sweep` | No | Valid JSON |
| `POST /api/v1/screener/natural-language` | No | Has results array |
| `POST /api/v1/options/payoff` | No | Valid JSON |
| `GET /fundamentals/RELIANCE.NS/financials` | No | Valid JSON |
| `GET /api/v1/earnings/surprises` | No | Valid JSON |
| `GET /api/v1/dashboard/ai-engine?limit=5` | Admin | Valid JSON |
| `GET /api/v1/market/anomalies` | No | Valid JSON |
| `GET /api/v1/market/sector-rotation` | No | Valid JSON |

- Any 500 → ABORT "Endpoint 5xx: /path"
- Auth endpoints: use `Authorization: Bearer admin`

### Step 5 — Run Tests on Server
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  cd /home/saumyapatel/Desktop/nivesh/backend &&
  /home/saumyapatel/Desktop/nivesh/venv/bin/python3 -m pytest \
    tests/test_quantlab_api.py \
    tests/test_prediction_calibration_api.py \
    tests/test_predictions_performance.py \
    tests/test_prediction_logging.py \
    -v --tb=short
"
```
- All tests must pass
- If any fail → ABORT "Tests failed: N failures"

### Step 6 — Check for 5xx in Logs
```bash
ssh -o ConnectTimeout=5 saumyapatel@192.168.1.122 "
  tail -50 /tmp/uvicorn.log | grep -c '500\|Error\|Traceback'
"
```
- If > 0 recent errors → ABORT "Server logs show errors"

---

## Success Output
```
✅ ALL GOOD — Server: <SHA>, Health: ok, Endpoints: 17/17, Tests: PASSED
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
| Admin Token | ADMIN_TOKEN=admin (in server .env) |
