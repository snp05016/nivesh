# Deployment Map

> Last generated: 2026-06-24. Source: repository deployment files, AGENTS.md remote-verification rules, backend service files, Docker files, and scripts.

## Runtime Topology

```mermaid
flowchart TB
  iPhone[iOS app] -->|HTTPS| Backend[FastAPI/Uvicorn backend :8000]
  Backend --> DB[(SQLite dev / PostgreSQL prod)]
  Backend --> ML[Docker ML engine :8001]
  Backend --> External[NSE, yfinance, SEBI, YouTube, LLM APIs]
  Backend --> Disk[charts/, cache/, token_log.jsonl]
  Backend --> Scheduler[APScheduler jobs]
  Worker[Celery worker] --> DB
  Worker --> External
  Ops[SSH deploy scripts] --> Server[saumyapatel@192.168.1.122]
```

## Deployment Artifacts

| File | Purpose | Failure modes |
|---|---|---|
| `backend/nivesh.service` | systemd unit: the only production supervisor of the backend (journald logs, restart on failure). | Unit not enabled (no reboot survival), installed copy drifts from the repo file, stray non-systemd uvicorn holding :8000. |
| `backend/Dockerfile` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |
| `backend/run.sh` | Local development only (`--reload`, binds 127.0.0.1). Never run on the server. | Port conflict with another local process. |
| `docker/rd-agent/Dockerfile` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |
| `docker/rd-agent/docker-compose.yml` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |
| `ml-engine/Dockerfile` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |
| `scripts/deploy_ml_engine.sh` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |
| `scripts/deploy_ml_microservice.sh` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |
| `scripts/health_check.sh` | Deployment/runtime helper discovered in repository. | Env mismatch, missing dependencies, port conflict, stale checkout, failed health check. |

## Required Backend Deployment Flow

AGENTS.md requires backend verification on `saumyapatel@192.168.1.122`, not by running backend tests locally. The deployment record must include branch, exact full SHA, commands, and health/test results. Required sequence:

1. Push current branch and record `git rev-parse HEAD`.
2. Non-interactive SSH clean-check on `/home/saumyapatel/Desktop/nivesh`; stop if dirty.
3. Never kill :8000 or uvicorn (`fuser`, `pkill`) and never start uvicorn with `nohup` or `--reload` on the server; systemd (`nivesh.service`) owns the process.
4. Fetch/switch/pull `--ff-only` on intended branch (or `git checkout --detach <SHA>`) and verify remote `HEAD` equals local SHA.
5. Restart with `sudo systemctl restart nivesh`, then `systemctl is-active --quiet nivesh && curl -fsS http://localhost:8000/ping`.
6. Run relevant `python3 -m pytest` remotely.
7. Health-check `/ping`, `/health`, `/health/live` or feature-specific endpoints and inspect `journalctl -u nivesh --since '-10 min'`.

## Environment and Secrets

- `backend/main.py` loads `backend/.env` at import time with `load_dotenv(..., override=True)`.
- Important env vars include `DATABASE_URL`, `JWT_SECRET`, `ALLOWED_ORIGINS`, `ENABLE_SCHEDULER`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, and ML-service URL settings used by qlib client.
- `.env` files, local DBs, logs, and generated binary artifacts must not be staged.

## Health Checks and Rollback Signals

| Check | Meaning | Failure implication |
|---|---|---|
| `GET /ping` | Zero-dependency backend process check. | Uvicorn/app not reachable. |
| `GET /health` | Lightweight iOS health endpoint. | App route/middleware failure. |
| `GET /health/live` | DB-backed liveness check. | DB unreachable or session failure. |
| `GET /healthz` | Router health endpoint. | Router registration or DB-backed health issue depending implementation. |
| Feature endpoint smoke | Confirms route + service + data path. | Deployment incomplete even if process is alive. |

Rollback after failed deployment should restore the last verified commit and record the rollback in the issue/PR/deployment record.

## Deployment Drift and Open Questions

- Current iOS default base URL is `https://api.nivesh.qzz.io`; `ServerURLPolicy.swift` rewrites legacy `http://192.168.1.122:8000` values to the default.
- `backend/nivesh.service` runs as `saumyapatel` from `/home/saumyapatel/Desktop/nivesh/backend`, matching AGENTS.md. Confirm the installed copy in `/etc/systemd/system/` matches the repo file and that the unit is enabled.
- The `--workers` count in `backend/nivesh.service` is the deployed value; the multi-worker decision is tracked separately (ARCH-07).
- `scripts/health_check.sh` defaults to `https://api.nivesh.app`, while the app and current docs use `https://api.nivesh.qzz.io`.
- `ml-engine` runs separately on port 8001; `scripts/deploy_ml_engine.sh` builds/runs the container on `saumyapatel@192.168.1.122` and restarts backend Uvicorn.
