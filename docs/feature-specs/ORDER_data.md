# Build order for cluster data

Build in this order; each package lists the packages it builds on (all earlier in this list).

- data-flags: Register data flags in the project flag module plus a cohort-aware wrapper (deps: none)
- data-schema: Data-foundation models, one idempotent Alembic migration and the erasure mapping (deps: none)
- data-instruments: Instrument master: EQUITY_L refresh, monotonic identity upserts, ISIN resolution, EQ-only new-listing search (deps: data-flags, data-schema)
- data-ml-eod-api: ml-engine read-only EOD export and marketdata-only gap-fill route (deps: none)
- data-eod-mirror: Postgres daily_prices mirror, gap-fill request, display-gated accessors and backfill CLI (deps: data-flags, data-instruments, data-ml-eod-api, data-schema)
- data-amfi-backend: AMFI harvester, real MF universe, paged MF API and NAV history from daily_prices (deps: data-flags, data-instruments, data-schema)
- data-amfi-ios: iOS MF discovery and detail on the real AMFI universe (paging, Direct default, no best sort) (deps: data-amfi-backend)
- data-corpactions-backend: Typed corporate actions, created_at guard on auto-apply, per-group proposals with apply/dismiss/undo (deps: data-flags, data-instruments, data-schema)
- data-corpactions-ios: iOS corporate-action banner and review sheet on Holdings (deps: data-corpactions-backend)
- data-results-backend: Results digest: NSE RSS link plus three yfinance numbers, no LLM, cohort-aware flag (deps: data-flags, data-instruments, data-schema)
- data-stockpage-ios: iOS Latest results card in the Financials tab (deps: data-results-backend)
- data-wiring: Register IST data jobs, mount routers before portfolio/stocks, delete legacy bhavcopy job, document feeds (deps: data-amfi-backend, data-corpactions-backend, data-eod-mirror, data-instruments, data-results-backend)
