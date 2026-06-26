# Testing & Verification Workflow

Run tests safely, respecting AGENTS.md constraints.

## Rules (from AGENTS.md)

| Rule | Source |
|------|--------|
| Never `xcodebuild` | §6.2 |
| Backend tests: remote server ONLY | §6.5 |
| Local pytest forbidden for backend | §6.5 |

## What You CAN Do

### iOS
- Read Swift source for syntax/compile errors.
- Check for AGENTS.md compliance (Theme tokens, spacing, fonts).
- Verify NavigationStack patterns, GeometryReader usage.

### Backend (Remote)
```bash
ssh saumyapatel@192.168.1.122 "cd /home/saumyapatel/Desktop/nivesh/backend && \
  /home/saumyapatel/Desktop/nivesh/venv/bin/python3 -m pytest \
  tests/<test_file>.py -v --tb=short"
```

### API Endpoint Verification
```bash
# Public endpoints
curl -s --max-time 10 https://api.nivesh.qzz.io/<path>

# Auth-protected endpoints  
curl -s --max-time 10 https://api.nivesh.qzz.io/<path> \
  -H "Authorization: Bearer admin"
```

## Test Categories to Run

| Category | Test Files |
|----------|-----------|
| QuantLab API | test_quantlab_api.py |
| Prediction calibration | test_prediction_calibration_api.py |
| Prediction performance | test_predictions_performance.py |
| Stress test engine | test_stress_test_engine.py |
| NL Screener | test_nl_screener_fix.py |
| Morning brief | tests/morning_briefing/*.py |

## Adding Tests

1. Follow existing test patterns (conftest.py, fixtures, auth headers).
2. Backend tests MUST NOT run locally.
3. Run on server: `ssh saumyapatel@192.168.1.122 ".../venv/bin/python3 -m pytest ..."`
4. Verify all pass before committing.

## Verification Checklist

```
- [ ] All tests pass on server
- [ ] Critical endpoints return 200 
- [ ] No 5xx errors in uvicorn logs
- [ ] New code follows existing patterns
- [ ] No AGENTS.md violations introduced
```
