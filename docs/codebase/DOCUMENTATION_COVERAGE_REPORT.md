# Documentation Coverage Report

> Last generated: 2026-06-24.

## Covered Components

- iOS SwiftUI client: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- FastAPI application shell: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Authentication and authorization: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Analysis engine and AI jobs: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Portfolio and user finance workflows: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Market data, earnings, ideas, and screeners: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Harvesting, content, and RAG: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Background jobs and schedulers: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- ML microservice and Qlib integration: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- Observability, admin, and error telemetry: purpose, responsibilities, dependencies, inputs, outputs, failure modes, files, tables, and endpoints documented.
- API inventory: 140 FastAPI route decorators extracted.
- Database inventory: 32 ORM tables/classes extracted.
- Service inventory: 88 backend service modules extracted.
- Migration inventory: 11 Alembic migration files extracted.
- Swift bridge inventory: initial AST pass under-counted dynamic Swift URLs; explorer-backed bridge table now covers the main NetworkManager, sidebar, home feed, and direct view call sites.

## Missing Documentation

- Per-field Pydantic schema documentation is not fully expanded for every request/response model; API contracts identify route handlers and major bodies but do not inline every schema class.
- Per-function service internals are summarized by module and key function/class rather than line-by-line commentary for every helper.
- `nivesh-harvester/` is mapped as a related code area but not deeply documented at the same level as mounted FastAPI backend.
- Graphify interactive output and GitNexus execution-flow resources are not embedded directly; the docs cite source maps and generated diagrams instead.

## Unclear Architecture Areas

- Controller-service-repository drift: multiple routers contain DB queries and business logic despite the intended rule.
- Scheduler ownership: startup scheduler, optional `ENABLE_SCHEDULER` jobs, Celery tasks, and `nivesh-harvester` scheduler coexist.
- API versioning: active endpoints are split across unprefixed legacy paths and `/api/v1` paths.
- Deployment target details such as process manager status and production DB engine must be verified on the remote server before operational changes.
- Current worktree has pre-existing modified/untracked files outside this documentation task; those were preserved.

## Recommended Documentation Improvements

- Generate OpenAPI JSON from the running server and commit a sanitized endpoint/schema snapshot.
- Add per-router ownership notes and gradually move router DB/business logic into services/repositories.
- Add a canonical endpoint naming policy and stale-route deprecation table.
- Add a scheduler runbook showing exactly which jobs run in prod and which env flag controls each one.
- Add schema examples for the top 10 Swift-facing response models.
- Add a remote verification log template under `docs/deployments/`.

## Confidence Scores

| Document | Confidence | Basis |
|---|---:|---|
| `ARCHITECTURE_MAP.md` | 0.86 | Broad source inventory plus known drift documented. |
| `SERVICE_MAP.md` | 0.82 | AST service inventory and grouped responsibilities; deeper per-helper behavior still requires source reading. |
| `DATABASE_MAP.md` | 0.90 | Direct ORM/migration/session extraction. |
| `API_CONTRACT_MAP.md` | 0.91 | Direct FastAPI decorator and Swift URL extraction. |
| `DATA_FLOW_MAP.md` | 0.84 | Major flows traced from current call sites and handlers; not every minor endpoint expanded end-to-end. |
| `DEPLOYMENT_MAP.md` | 0.78 | Repo files and AGENTS remote flow documented; live remote state not checked in this turn. |
| `TESTING_MAP.md` | 0.86 | Test inventory and constraints extracted; tests not executed locally by rule. |

## Evidence Passes Used

- Local AST extraction for FastAPI decorators, ORM models, migrations, services, and tests.
- Direct source inspection of `backend/main.py`, routers, repositories, database/session code, and current docs.
- Explorer pass for backend/API/service inventory.
- Explorer pass for database/migration/repository inventory.
- Explorer pass for iOS client paths, background jobs, deployment files, and testing constraints.

