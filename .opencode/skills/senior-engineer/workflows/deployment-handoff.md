# Deployment Handoff

Deploy backend to server: `192.168.1.122`. Use `/nivesh-deploy` skill for the full pipeline.

## Pre-Flight
```bash
git checkout main
git pull --ff-only origin main
SHA=$(git rev-parse --short HEAD)
git diff-index --quiet HEAD  # verify clean
```

## Deploy Steps (AGENTS.md §6.5)

```bash
# 1. Record
echo "Deploying $SHA to 192.168.1.122"

# 2. Verify remote clean
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && \
  test -z \"\$(git status --porcelain)\""

# 3. Kill stale processes
ssh saumyapatel@192.168.1.122 "sudo fuser -k 8000/tcp 2>/dev/null; sleep 2"

# 4. Fetch + fast-forward
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && \
  git fetch origin && git checkout main && git reset --hard origin/main"

# 5. Verify SHA
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh && \
  git rev-parse --short HEAD"

# 6. Restart
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && \
  nohup /home/saumyapatel/Desktop/nivesh/venv/bin/uvicorn main:app \
  --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 & sleep 5 && \
  curl -s http://localhost:8000/ping"

# 7. Health checks
curl -s --max-time 5 https://api.nivesh.qzz.io/ping
curl -s --max-time 5 https://api.nivesh.qzz.io/health
```

## Post-Deploy Verification

```bash
# Critical endpoints
curl -s https://api.nivesh.qzz.io/api/v1/predictions/performance -H "Auth: Bearer admin"
curl -s https://api.nivesh.qzz.io/api/v1/stocks/RELIANCE.NS/financials -H "Auth: Bearer admin"
curl -s https://api.nivesh.qzz.io/dividends/RELIANCE.NS

# Run tests on server
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && \
  /home/saumyapatel/Desktop/nivesh/venv/bin/python3 -m pytest \
  tests/test_quantlab_api.py tests/test_prediction_calibration_api.py \
  tests/test_predictions_performance.py -q"
```

## Don't Deploy If
- Working tree is dirty
- Tests fail
- Server is unreachable (host down on 192.168.1.122:22)
- New migration wasn't applied

## Report
```
**Deployed**: <SHA>
**Health**: ok/degraded
**Tests**: N passed
**Endpoints**: all 200
**Rollback**: <previous SHA>
```
