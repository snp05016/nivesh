# Feature package data-results-backend: Results digest: NSE RSS link plus three yfinance numbers, no LLM, cohort-aware flag

Cluster: data (Data foundation); area: backend
Features covered: I25

## Files (create or modify)
- backend/services/results_digest.py
- backend/routers/results_digest.py
- backend/tests/test_results_digest.py
- backend/tests/fixtures/nse_financial_results_rss.xml

## Dependencies
- Feature packages (integrated before you start): data-flags, data-instruments, data-schema
- Declared in the plan: data-flags, data-schema, data-instruments, FIX:ARCH-11, FIX:REG-10, FIX:FAKE-04, ENG:be-db-ledger. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Defer: 'three numbers and a link', with no LLM.

services/results_digest.py:
- FIN_RESULTS_RSS = 'https://nsearchives.nseindia.com/content/RSS/Financial_Results.xml'.
- fetch_feed(): conditional GET (ETag and Last-Modified kept in module state), honest UA (stop if REG-10 has not landed), 20 s timeout, 2 MB cap. 304 returns None.
- parse_feed(xml): ElementTree over channel/item (title, link, description, pubDate via email.utils); skip malformed items.
- item_symbol(item, session):
  - a 'symbol' query parameter in the link [verify on the first live fetch];
  - else a normalised company name (upper case, & becomes AND, punctuation stripped, trailing LIMITED/LTD dropped) that equals exactly one active EQ instrument name;
  - else None.
- item_period_end(item): the latest dd-Mon-yyyy quarter-end in the description that is not after the publish date; fallback is the last quarter end before the publish date.
- poll_feed_job():
  - if not data_flags.any_enabled('data_results_digest'), return skipped (any_enabled is true while a cohort is allowlisted);
  - keep research_repo.extra_symbols(session, cap=500);
  - insert a pending ResultsDigest when (symbol, period_end) is new (first item wins);
  - return counts.
- fill_pending_numbers(today=None, max_calls=150):
  - same flag rule;
  - pending for more than 10 days after the announcement becomes 'unavailable';
  - otherwise yf_acquire() (ARCH-11), then yf.Ticker(symbol + '.NS').quarterly_income_stmt;
  - pick the column within 5 days of period_end and the year-ago column within 10 days of period_end - 365;
  - labels: revenue 'Total Revenue' or 'Operating Revenue'; profit 'Net Income', 'Net Income Common Stockholders' or 'Net Income From Continuing Operation Net Minority Interest'; EPS 'Diluted EPS' or 'Basic EPS';
  - store rupees; YoY = (cur - prev)/prev*100, rounded to 1, only when prev > 0;
  - 'ok' when revenue and profit exist, with numbers_source 'yahoo_finance' and fetched_at;
  - a per-symbol exception leaves the row pending.
- digest_payload(row):
  - period_label 'Quarter ended {d Mon yyyy}';
  - numbers_source_text: 'Figures from Yahoo Finance quarterly statements, fetched {d Mon yyyy}. The company's exchange filing is the official source.', or for unavailable 'Figures aren't available from our data source. See the company's filing.'

routers/results_digest.py:
- GET /api/v1/stocks/{symbol}/results-digest with user_id = Depends(require_auth), then data_flags.require('data_results_digest', user_id).
- Upper-case the symbol and strip .NS/.BO. If it does not match ^[A-Z0-9&-]{1,20}$, raise HTTPException(422, detail={'code':'INVALID_SYMBOL'}).
- The latest digest by period_end gives 200 {symbol, period_end, period_label, filing_url, filing_title, announced_at, numbers_status, revenue_inr, revenue_yoy_pct, net_profit_inr, net_profit_yoy_pct, eps, eps_yoy_pct, numbers_source_text}. None gives HTTPException(404, detail={'code':'NO_DIGEST'}).
- Mounted by data-wiring.

No llm_utils or LLM client import. Numbers and YoY only: no adjectives, rating or target.

## Acceptance checks
PYPARSE and PYRIGHT clean.

test_results_digest.py (2-item RSS fixture) covers:
- the source scan finds no llm, anthropic, openai or deepseek import and no nseindia.com/api
- parse reads both items
- the period comes from the description, with the fallback working
- the symbol is found via the link and via a unique name; an ambiguous name is skipped
- the poll keeps only held or watched symbols and is idempotent; it runs with only an allowlist and skips with neither flag nor allowlist
- a fake DataFrame gives rupees and YoY
- prev <= 0 gives None; a missing period stays pending; 11 days pending becomes unavailable
- the endpoint gives 200, 404 NO_DIGEST and 422 INVALID_SYMBOL; with the flag off, 200 for an allowlisted user and 404 FEATURE_DISABLED for others
- error bodies are {'detail': {'code': ...}}

## Cluster spec
docs/feature-specs/spec_data.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
