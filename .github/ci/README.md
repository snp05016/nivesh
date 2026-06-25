# Nivesh CI/CD

This directory documents the GitHub Actions workflows and their no-paid-API posture.

## Workflows

- `pr-static.yml` runs PR-only static checks: whitespace, secret scan, dependency scan, Python syntax/static imports, FastAPI route extraction, Swift source scan, and Dockerfile validation.
- `backend-remote-tests.yml` runs selected mocked backend tests on the configured remote host. It does not run local backend pytest.
- `api-contract-drift.yml` statically compares backend FastAPI route decorators with Swift URL call sites.
- `db-migration-check.yml` checks Alembic migration presence and can run remote temporary-DB migration validation on manual dispatch.
- `ml-engine-ci.yml` builds the ML Engine Docker image, runs local/mock ML tests, and checks `/health` plus `/model/status`.
- `deploy-backend.yml` deploys an exact branch/SHA by SSH and only calls free health endpoints.
- `nightly-regression.yml` runs safe mocked regression coverage for health, schema, scheduler duplication, DB integrity, and cached/static behavior.
- `release-artifacts.yml` creates route, OpenAPI, migration, test-summary, deployment-log, health-check, and changelog artifacts.

## Required Remote Configuration

Remote workflows expect these repository secrets:

- `NIVESH_REMOTE_HOST`
- `NIVESH_REMOTE_USER`
- `NIVESH_REMOTE_SSH_KEY`

Optional repository variables:

- `NIVESH_REMOTE_PORT`, default `22`
- `NIVESH_REMOTE_PATH`, default `/home/saumyapatel/Desktop/nivesh`

## Forbidden In Default CI

Default CI must not call DeepSeek, Claude, OpenAI, Anthropic, Google AI, embedding APIs, Copilot chat, `/analyze`, advisor reformatting, RAG ingestion, or any live LLM-backed endpoint.

Backend pytest is remote-only. iOS compilation is not part of CI because `xcodebuild` is prohibited for this repository.
