# Build order for cluster platform

Build in this order; each package lists the packages it builds on (all earlier in this list).

- platform-flags: Server-side feature flags: table, resolver and cache-safe public client endpoint (deps: none)
- platform-jobruns: job_runs history, sync/async tracked() wrapper, failure alerts and retention (deps: platform-flags)
- platform-restore-drill: Monthly automated restore drill with scratch-database guards, plus cloud-move readiness doc (deps: platform-jobruns)
- platform-events-db: user_events table with erasure registration, configurable retention and a consent backstop (deps: platform-jobruns)
- platform-scheduler-ist: One IST scheduler: explicit ids, job_runs tracking, market-hours alerts, canary and drill registration (deps: platform-jobruns, platform-restore-drill)
- platform-events-api: Consent-gated POST /api/v1/events, erasure on consent withdrawal, per-caller flag fields and SQL docs (deps: platform-events-db, platform-flags)
- platform-privacy-export: GET /api/v1/compliance/my-data JSON export with owner-column filtering, stored-data groups, non-FK user columns in erasure, DPDP runbook (deps: platform-events-api, platform-events-db)
- platform-admin-api: Admin API for flags, job runs, audit and usage, plus audit rows on every user-level admin read (deps: platform-events-api, platform-flags, platform-jobruns)
- platform-admin-ui: Admin console Flags, Jobs, Audit and Usage pages (deps: platform-admin-api)
- platform-async-guard: Ruff flake8-async gate with baseline, plus AST test for project blocking calls and awaits on sync functions (deps: platform-admin-api, platform-events-api, platform-privacy-export, platform-scheduler-ist)
- platform-ios-flags-events: iOS RemoteFlags, EventLogger and platform network calls (flags, events, data export) (deps: platform-events-api, platform-flags, platform-privacy-export)
- platform-ios-privacy-center: iOS Your Data screen and the one-time Home analytics ask (deps: platform-events-api, platform-ios-flags-events, platform-privacy-export)
- platform-ios-event-callsites: Instrument the ten events on existing screens and rewrite tutorial step 8 (deps: platform-ios-flags-events, platform-scheduler-ist)
