# Quant Lab -- Backend Files Changed

## New Endpoint

### routers/analysis.py (modified)
Added `GET /api/v1/stocks/{symbol}/ml-signal` endpoint. Proxies to the ML engine's prediction endpoint, transforms the response into the typed `MLSignalResponse` schema, and returns it to the iOS client. Includes timeout handling (5s to ML engine) and proper error responses (404 if symbol not found, 504 if ML engine timeout).

## Modified Files

### schemas/backtest_schemas.py (modified)
Added `CostSensitivityResponse` Pydantic model to provide typed response serialization for the existing `GET /api/v1/backtests/cost-sensitivity` endpoint. Previously returned raw dict.

### schemas/__init__.py (modified)
Exported `MLSignalResponse` and `CostSensitivityResponse` from the schemas package.

## Unchanged but Referenced

The following existing endpoints are consumed by the Quant Lab iOS feature but were not modified:

- `GET /api/v1/predictions/calibration` -- routers/predictions.py
- `GET /api/v1/predictions/pillar-attribution` -- routers/predictions.py
- `GET /api/v1/predictions/model-versions` -- routers/predictions.py
- `POST /api/v1/backtests/alpha-validation` -- routers/backtests.py
- `GET /api/v1/backtests/strategy-sweep` -- routers/backtests.py
- `POST /api/v1/backtests/regime-breakdown` -- routers/backtests.py
- `GET /api/v1/backtests/cost-sensitivity` -- routers/backtests.py
