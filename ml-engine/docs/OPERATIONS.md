# ml-engine operations

How to tell whether the served model is healthy, what to alert on, and how to roll back.

## Liveness and readiness

| Probe | Meaning | Used by |
|---|---|---|
| `GET /health` | The process is up. Always `{"status": "ok"}`. | Manual checks only |
| `GET /ready` | 200 `{"status": "ready", "model_version", "model_validated", "model_integrity_ok", "manifest_version"}` only when the LightGBM booster loaded and, if `models/MANIFEST.json` exists, matches it (sha256, feature list, objective); `model_version` is `"unregistered"` without a manifest. Otherwise 503 `{"status": "degraded", "reason": "model_not_loaded" or "model_integrity"}`. | Docker `HEALTHCHECK`, `scripts/deploy_ml_microservice.sh` |

A missing or misplaced `models/lgb_model.txt` keeps `/health` green while every
prediction comes from the heuristic fallback. `/ready` turns that into a failed
deploy, which rolls back to the previous image. The first deploy after `/ready`
was added rolls back to an image that has no `/ready`, so the script reports the
rollback as unhealthy even though the old container is serving. Check
`curl -fsS http://127.0.0.1:8001/health` by hand in that case.

`model_validated: false` means no passed promotion gate was found in
`models/MANIFEST.json`. The engine then serves every prediction as `no_edge`.
`/ready` stays 200 in that state because it is a deliberate serving mode, not a
broken deploy. Watch for it on the status endpoint (below).

## Prediction monitor

`GET /model/status` (needs the `X-ML-Engine-Key` header when `ML_ENGINE_API_KEY`
is set) includes `recent_predictions`, computed over the last 500 predictions of
this process:

| Field | Meaning |
|---|---|
| `n` | Predictions in the window |
| `n_ok` | Predictions in the window with `signal_state: ok` (served by a validated model) |
| `no_edge_rate` | Share of the window served as `no_edge` (`1 - n_ok / n`) |
| `class_share` | Share of `-1`, `0`, `1` directions among the `ok` predictions only |
| `fallback_rate` | Share served without the booster |
| `degenerate` | `n_ok >= 50` and one class holds more than 90% of the `ok` predictions |

The window resets on restart. A model without a passed gate serves every
prediction as `no_edge` direction 0 by design. Those predictions count towards
`no_edge_rate`, not `class_share`, so that state shows `no_edge_rate: 1.0` and
`degenerate: false`. When `degenerate` flips to true, the engine logs one
WARNING: `Prediction distribution degenerate over last N ok-state calls`.

### Alert on

- `/ready` not 200 for more than 2 minutes.
- `recent_predictions.degenerate` is true: a validated model has collapsed to one class.
- `recent_predictions.fallback_rate` above 0: the booster is not being used.
- `model_validated` false, or `no_edge_rate` above 0, when a validated model
  was expected. Both are normal while no `MANIFEST.json` gate has passed, so
  the cron check below does not alert on them.
- Any `Inference failed` / HTTP 500 lines in the logs.

The repository has no alerting stack. Until one exists, run the checks from cron
on the server, for example every 5 minutes:

```bash
curl -fsS http://127.0.0.1:8001/ready >/dev/null || echo "ml-engine not ready"
curl -fsS -H "X-ML-Engine-Key: $ML_ENGINE_API_KEY" http://127.0.0.1:8001/model/status \
  | python3 -c 'import json,sys; r=json.load(sys.stdin)["recent_predictions"]; sys.exit(1 if r["degenerate"] or r["fallback_rate"] > 0 else 0)' \
  || echo "ml-engine predictions degenerate or in fallback"
```

Pipe each `echo` to whatever notification channel is configured.

## Prediction logs

Each prediction writes one JSON log line with `event`, `ticker`, `model_version`,
`mode`, `direction`, `signal_state`, `raw_score`, `latency_ms` and `fallback_used`:

```bash
docker logs ml-engine 2>&1 | grep '"event": "prediction"' | tail -50
# class mix over the last 1000 ok-state predictions
docker logs ml-engine 2>&1 | grep '"event": "prediction"' | grep '"signal_state": "ok"' | tail -1000 \
  | grep -o '"direction": -\?[0-9]' | sort | uniq -c
```

## Backend cache

The backend caches ml-signal responses for an hour under a key that includes the
deployed `model_version` (read from `/model/status`, refreshed every 60 s). A new
model therefore stops old signals from being served within about a minute of the
deploy, without a manual cache flush.

## Rollback

`scripts/deploy_ml_microservice.sh` tags the running image as
`ml-engine:previous` (image id also in `.ml-engine.previous` at the repo root)
before every swap, and restarts it automatically when the new container fails
`/ready`. A new `ml-engine:<sha>` image must first pass `/ready` as
`ml-engine-candidate` on 127.0.0.1:8011, reporting the `MANIFEST.json` model
version, or the running container is left untouched. The script prints the
exact rollback command at the end.

To roll back a model that passed `/ready` but behaves badly (degenerate, worse
hit rate):

1. Redeploy the previous model version: check out the commit whose
   `ml-engine/models/` holds the previous `lgb_model.txt` and
   `MANIFEST.json`, and run `scripts/deploy_ml_engine.sh`. Use the registry
   promotion step instead once it exists.
2. Or restore the previous image directly on the server:
   `docker rm -f ml-engine`, then start `ml-engine:previous` with the same
   `run_container` arguments as the deploy script.
3. Confirm `/ready` reports the expected `model_version`, then watch
   `recent_predictions` until `n_ok >= 50` (or `n >= 50` with
   `no_edge_rate: 1.0` for an unvalidated model).
