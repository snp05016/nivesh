# Data feeds

The data foundation: an instrument master, stored end-of-day prices, the AMFI mutual-fund universe,
corporate-action proposals and a results digest. Everything here is behind a server-side flag
(`core/feature_flags.py`, `GET /api/v1/features`) and degrades to the existing behaviour when off.

## Sources, licences and legal items

| Data | Source | Cadence | Code |
|---|---|---|---|
| EQ end-of-day rows, Nifty 50 close | ml-engine `GET /research/v1/eod/{date}` (read-only, from the engine's NSE bhavcopy store) | nightly, re-pulls 15 calendar days | `services/eod_prices.py` |
| Missing bhavcopies while research mode is off | ml-engine `POST /research/v1/marketdata/sync` (the engine's own gap-fill under its run lock) | each mirror run | `services/eod_prices.py`, `ml-engine/research/marketdata/eod.py` |
| Equity names, series, ISINs | NSE `nsearchives.nseindia.com/content/equities/EQUITY_L.csv` | weekly | `services/instruments.py` |
| Mutual-fund universe and NAV | AMFI `www.amfiindia.com/spages/NAVAll.txt` | 23:30 and 08:10 IST | `services/amfi.py` |
| Results link and quarter | NSE `nsearchives.nseindia.com/content/RSS/Financial_Results.xml` | :05 and :35, 08-23h IST | `services/results_digest.py` |
| Results figures | yfinance `quarterly_income_stmt` (labelled Yahoo) | 22:15 IST, at most 150 calls | `services/results_digest.py` |
| Splits and bonuses | yfinance (`fetch_split_events`), cross-checked with mirrored NSE rows | daily (MATH-07) | `services/ledger_service.py` |

Legal items (record the outcome here when cleared):

| Item | Gates | Outcome |
|---|---|---|
| (a) Display rights for NSE end-of-day prices and NSE Indices (Nifty 50) closes | `data_eod_display` (and engine Stage 3) | open |
| (b) Automated download of EQUITY_L.csv, of bhavcopies outside research runs (the gap-fill) and of the Financial Results RSS, plus linking to filings | `data_instruments`, `data_eod_prices` gap-fill, `data_results_digest`; until cleared `data_eod_prices` may be turned off | open |
| (c) AMFI NAV attribution | MF screen copy ("NAVs are published by AMFI") | open |
| (d) Use of Yahoo Finance split events and quarterly figures | `data_corp_actions_confirm`, `data_results_digest` | open |

## Honest User-Agent policy

Every fetch uses `config.settings.get_user_agent()` (`NiveshBot/1.0 (+BOT_CONTACT_URL)`); the engine uses
`NiveshResearch/1.0 (+RESEARCH_HTTP_CONTACT)`. The contact is https://github.com/snp05016/nivesh or an
ops address. Never disguise the client, rotate agents or call `www.nseindia.com/api/`. On a 403 or 429, wait
for the next scheduled run. If NSE or AMFI blocks the honest agent, drop that feed or buy a licensed
vendor feed. Set `BOT_CONTACT_URL` in `backend/.env` and `RESEARCH_HTTP_CONTACT` in the ml-engine
environment before the jobs run; the EOD mirror also needs `ML_ENGINE_API_KEY`.

## Jobs (Asia/Kolkata)

`services/data_jobs.py` registers these from `harvest_worker.start_scheduler` (guarded: a failure to
register logs CRITICAL and does not stop other jobs). Each has `max_instances=1`, `coalesce=True`,
`misfire_grace_time=3600`; a failing run is logged and recorded as a `DATA_FEEDS` diagnostic, never raised.

| Job id | When (IST) | Target |
|---|---|---|
| `data_eod_mirror_evening` | Mon-Fri 21:40 | `eod_prices.mirror_recent` |
| `data_eod_mirror_morning` | Tue-Sat 07:40 | `eod_prices.mirror_recent` |
| `data_amfi_nav_night` | 23:30 | `amfi.harvest` |
| `data_amfi_nav_morning` | 08:10 | `amfi.harvest` |
| `data_equity_master` | Sat 08:30 | `instruments.refresh_equity_master` |
| `data_results_feed` | hourly 08-23 at :05 and :35 | `results_digest.poll_feed_job` |
| `data_results_numbers` | 22:15 | `results_digest.fill_pending_numbers` |
| `corporate_actions` (MATH-07, scheduler UTC 02:00) | 07:30 | `ledger_service.sync_corporate_actions_all_users` |

With research mode off, each mirror run first asks the engine to gap-fill, so an evening's data lands by the
07:40 run. In shadow or on, the nightly research runs fill the engine's store.

The legacy `download_bhavcopy` job (13:30 UTC cache that nothing read) is deleted.

### Corporate-action guard (applies with the flag on or off)

For each (user, group, event), with the effective instant 23:59:59 UTC on the day before the ex-date, the job
skips when an application exists in any status, a SPLIT already sits at the effective instant, nothing was
held before it, or every BUY is a statement (CAS) import. Otherwise:

- **Unambiguous** (every earlier non-corporate row was created, by IST date, before the ex-date): the SPLIT is auto-applied.
- **Ambiguous** (any earlier row created on or after the ex-date, or with no `created_at`): never auto-applied. With `data_corp_actions_confirm` on for the user a pending application is recorded; otherwise the event is only recorded.

Trade-off with the flag off: a back-dated pre-split quantity stays unsplit until the user edits it. That is the safer error than doubling.

Known gap: the holdings replay still spans groups (the per-group replay, C4/DB-09, is not on this line), so a
SPLIT written for one group also multiplies other groups' earlier shares. Keep `data_corp_actions_confirm` off
for everyone until C4 is deployed.

#### Review query for SPLIT rows written before the guard

Run on Postgres if MATH-07's job ran in production before this guard shipped. It lists auto SPLIT rows where
the same user, group and ticker has an earlier-dated row created on or after the ex-date (the SPLIT date plus one day);
correct those holdings with the users before enabling the confirm flag.

```sql
SELECT s.id, s.user_id, s.group_id, s.ticker, s.date AS split_effective_at, s.notes
FROM portfolio_transactions s
WHERE s.transaction_type = 'SPLIT'
  AND s.notes LIKE 'auto: corporate action%'
  AND EXISTS (
    SELECT 1 FROM portfolio_transactions b
    WHERE b.user_id = s.user_id
      AND b.ticker = s.ticker
      AND b.group_id IS NOT DISTINCT FROM s.group_id
      AND b.id <> s.id
      AND b.transaction_type NOT IN ('SPLIT', 'BONUS', 'DIVIDEND')
      AND b.date < s.date
      AND ((b.created_at AT TIME ZONE 'UTC') AT TIME ZONE 'Asia/Kolkata')::date >= s.date::date + 1
  )
ORDER BY s.user_id, s.ticker, s.date;
```

## Flags

All keys are registered in `core/feature_flags.py` (env `FEATURE_<KEY>`, read at startup; change the value in
`backend/.env` and restart). Cohorts: `FEATURE_<KEY>_USERS` is a comma-separated list of user ids who get a
feature while its flag is off (`services/data_flags.py`); the data jobs run while the flag is on or a cohort exists.

| Key | Default | Gates | Who may flip it |
|---|---|---|---|
| `data_instruments` | on | weekly EQUITY_L refresh; new-listing search results | owner |
| `data_eod_prices` | on | EOD mirror; gap-fill request while research mode is off | owner (off until legal item (b) if needed) |
| `data_eod_display` | **off** | EQ and INDEX closes returned to user-facing callers | owner, only after legal item (a) |
| `data_mf_universe` | on | AMFI harvest and NAV history | owner |
| `data_corp_actions_confirm` | **off** (Defer) | proposals for ambiguous events and the corporate-actions API | owner, after the conditions below |
| `data_results_digest` | **off** (Defer) | RSS poll, numbers and the results-digest API | owner, after the conditions below |

Cohort variables: `FEATURE_DATA_CORP_ACTIONS_CONFIRM_USERS`, `FEATURE_DATA_RESULTS_DIGEST_USERS`.

### Deferral conditions

`data_corp_actions_confirm` (all four): (1) the per-group replay (C4) is deployed; (2) the iOS build with the
Holdings review sheet is live in the App Store; (3) the I06 data export includes `corporate_action_applications`;
(4) an internal cohort's pending proposals have been reviewed over a few nights and spot-checked against NSE
corporate announcements.

`data_results_digest` (all three): (a) the feed is verified on the server (fetch the RSS once by hand with the
honest agent and confirm items carry a filing link, a period-end date and a symbol parameter or company name; the
parser's symbol-from-link rule is unverified); (b) legal approves the RSS, filing links and Yahoo figures;
(c) in a 4-week cohort, at least 90% of a weekly sample of digests match the filings. The guidance ledger is
decided afterwards, using I47 data.

`data_eod_display`: legal item (a) cleared (the same prerequisite as engine Stage 3).

## Tables, growth and retention

Migration `ecac0bc9105a` adds `instruments`, `instrument_aliases`, `daily_prices`,
`corporate_action_applications` and `results_digests`, plus columns on `mutual_funds` and `corporate_actions`.
Take a backup (OPS-03) before `alembic upgrade head` and confirm `alembic heads` shows one head.

- `daily_prices` grows by about 1.5 million rows a year (EQ closes, the Nifty 50 close and recorded AMFI NAVs).
  Include it in backups and watch disk use; revisit the history scope if storage becomes a constraint. No automatic retention.
- AMFI NAV history is recorded from the first harvest for open Growth plans and tracked schemes; there is no backfill and no computed return.
- `instruments` is bounded by listed securities and schemes (tens of thousands of rows).
- `results_digests` holds one row per held or watched symbol and quarter.
- After the engine's historical backfill (`python -m research.marketdata.store backfill --start 2018-01-01` on the engine host), run
  `python -m scripts.backfill_daily_prices --start 2018-01-29 --end 2018-02-02` (plus any XIRR span the money cluster requests).

## Contracts for other clusters

- `instruments.resolve(symbol=None, isin=None)` and `instruments.resolve_isin(isin)` (the CAS import entry point).
- `eod_prices.get_close(symbol=None, *, isin=None, on=None, max_age_days=7, for_display=True) -> PriceFact | None`,
  `get_closes(identifiers)` and `index_close(...)`.
  **EQ and INDEX closes are not returned to user-facing callers until `data_eod_display` is on; mutual-fund NAVs always are.
  Callers must handle `None` by keeping their existing source (today yfinance) and labelling what they show.**
- `mutual_fund_service.mark_tracked(scheme_codes)`.
- `money_mf_meta` reads MutualFund rows: category is Equity, Debt, Hybrid, Solution Oriented or Other; sub_category is AMFI's
  (`Equity Scheme - ELSS` gives Equity / ELSS); ISINs come from the MF instrument row (`isin` growth/payout, `isin_alt` reinvestment).
- `results_digests` and `corporate_actions` are inputs for I31 Event Radar.

## DPDP

`corporate_action_applications` is the only per-user table here. It cascades on user delete, is mapped `delete` in
`ERASURE_POLICY` (`compliance_service`), and must be in the I06 export before `data_corp_actions_confirm` is turned on.

## I17: shareholding patterns (deferred, no code)

No free source respects the terms (NSE's website terms bar automated collection; licensed feeds cost roughly Rs 5-10 lakh a year).
The follow-on design, once a licence exists:

- `shareholding_patterns` gains `period_end` (DATE), `source`, `source_url`, `filed_on`, `updated_at` and a unique `(ticker, period_end)`;
- Indian financial-year labels derived from `period_end` (2026-09-30 is Q2 FY27);
- FII, DII, public and pledge percentages optional and never invented; results ordered by `period_end`;
- a `data_shareholding` flag, default off.

Prerequisite: a licensed vendor or written exchange permission, plus legal sign-off. Do not load hand-copied exchange tables.

## C15: incremental RAG ingestion (covered by the fix track)

REL-21 schedules watermark-based `ingest_new` in the scheduler leader. End state: at engine Stage 3, unschedule `ingest_new`
(nothing reads the chunks once `/analyze` returns 410); at Stage 4, delete `services/rag_ingestion.py`, `rag_tools.py`
and `vector_store.py` (and their `backup_service` reference) and drop the `nivesh_filings` table. No retention job is built.

## Rollout order

1. Flags, then the schema migration (backup first).
2. Instruments, the engine EOD export, AMFI.
3. EOD mirror, corporate actions (with MATH-07), results digest.
4. Wiring (jobs and routers).
5. iOS packages, then ship the build.
6. Defer flags go to a cohort first, then everyone; `data_eod_display` waits for legal.

After the first deploy, watch the 23:30 IST AMFI run (more than 10,000 parsed rows and no "AMFI file too short" telemetry),
open the MF screen to confirm real funds with NAV dates, and keep `DEMO_MODE=false` in production. Optionally run the equity
master refresh once from an admin shell instead of waiting for Saturday 08:30 IST.
