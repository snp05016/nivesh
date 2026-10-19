# Feature package data-instruments: Instrument master: EQUITY_L refresh, monotonic identity upserts, ISIN resolution, EQ-only new-listing search

Cluster: data (Data foundation); area: backend
Features covered: I14

## Files (create or modify)
- backend/services/instruments.py
- backend/routers/search.py
- backend/scripts/refresh_nse_symbols.py
- backend/tests/test_instruments.py
- backend/tests/fixtures/equity_l_sample.csv

## Dependencies
- Feature packages (integrated before you start): data-flags, data-schema
- Declared in the plan: data-flags, data-schema, FIX:CMKT-15, FIX:GH-639, FIX:ARCH-10, FIX:REG-10, FIX:DB-24, ENG:be-db-ledger. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
New backend/services/instruments.py. Import get_session and the models inside the functions, so scripts can import the fetch and parse helpers. EQUITY_L_URL = 'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'; MIN_EQUITY_ROWS = 1500.

fetch_equity_list(timeout=30):
- requests.get with {'User-Agent': config.settings.get_user_agent()}; first confirm REG-10 has landed (no fake_useragent), else stop;
- raise_for_status; reject bodies over 5 MB; on 403, log once and raise;
- never change the UA or call www.nseindia.com/api.

parse_equity_list(text):
- csv.DictReader with stripped, upper-cased keys (the real header has leading spaces);
- keep SERIES in {'EQ','BE','BZ'} with an ISIN matching ^IN[A-Z0-9]{10}$;
- output {'symbol','name','series','isin','listing_date' (%d-%b-%Y or None)}; skip malformed rows.

_add_alias(session, instrument_id, kind, value, valid_to):
- if (kind, value, instrument_id) exists, set valid_to = max(existing, new), with None treated as oldest; otherwise insert;
- every alias write goes through it, so a re-run never violates the unique key.

upsert_eq_identity(session, *, symbol, isin, seen_on, source, name=None, series=None, listing_date=None, entity_id=None) -> Instrument
Match in order:
- (1) entity_id owned by a row;
- (2) an EQ row whose isin or isin_alt == isin;
- (3) an 'isin' alias pointing at an EQ row;
- (4) an ACTIVE EQ row with this symbol (face-value split);
- (5) otherwise insert: name defaults to the symbol, status 'active', last_seen_on = seen_on.
Monotonic rule (review critical): if matched.last_seen_on is set and seen_on < last_seen_on, return the row unchanged. Older data never touches symbol, isin, name, series, listing_date, status, entity_id or aliases.
Otherwise:
- Freeing a symbol held by another EQ row (on insert or rename): if the holder is inactive or a different identity, and seen_on >= holder.last_seen_on (or None), then _add_alias(holder, 'symbol', symbol, seen_on), holder.symbol = None, status 'inactive'. If the holder is newer, keep the incoming symbol None and log a warning.
- A changed symbol or isin: _add_alias for the old value (valid_to = seen_on), then update.
- Fill entity_id if it is null and unused. Update name, series and listing_date when given. Set status 'active' and last_seen_on = seen_on.
- No commit inside.

upsert_mf(session, *, scheme_code, name, isin, isin_alt, seen_on, active=True): keyed by amfi_scheme_code; asset_class 'MF', symbol None, source 'amfi'; ISIN change goes through _add_alias.

get_or_create_index(session, code='NIFTY50', name='Nifty 50 (price index)'): asset_class 'INDEX', source 'seed'.

refresh_equity_master(today=None):
- data_flags.enabled('data_instruments') is off: return {'skipped':'flag_off'};
- fewer than MIN_EQUITY_ROWS: raise RuntimeError and change nothing;
- in one get_session(), upsert all rows with source 'nse_equity_l' and seen_on = core.timeutil.ist_today();
- deactivate EQ rows absent from the file and with last_seen_on < today - 10 days;
- commit and return {inserted, updated, renamed, isin_changed, deactivated}.

resolve(symbol=None, isin=None):
- isin wins: isin or isin_alt in any class, then 'isin' aliases;
- a symbol goes through research_repo.normalize_symbol, then active EQ/INDEX rows, then 'symbol' aliases (latest valid_to);
- return the row detached (session.expunge).

resolve_isin(isin) -> {'asset_class','symbol','amfi_scheme_code','name','status','instrument_id'} | None.

search_new_listings(q, limit):
- active EQ rows with series == 'EQ' (review) and a symbol; upper(symbol) LIKE 'Q%' or upper(name) LIKE '%Q%', with % and _ escaped;
- prefix matches first, then by symbol; fetch limit*3; drop tickers that stock_universe.by_ticker knows;
- return at most limit dicts {'ticker','company_name','sector':'','exchange':'NSE'}.

routers/search.py:
- after results = search_endpoint(q=query, limit=limit), if the flag is on and the list is short, extend with search_new_listings(query, limit - len(results)), skipping duplicates;
- wrap that in try/except that logs, so search never returns 500;
- keep auth and the bare list.

scripts/refresh_nse_symbols.py: replace fetch_nse()'s HTTP and CSV code with instruments.fetch_equity_list() (add backend to sys.path); filter EQ; map to {'ticker','name','sector': guess_sector(name),'exchange':'NSE'}; delete the browser UA headers.

## Acceptance checks
PYPARSE and PYRIGHT clean; no 'nseindia.com/api' and no fake_useragent in the touched files.

tests/test_instruments.py (fixture with leading-space headers, an SM row, a bad ISIN, a BZ row and a listing date) covers:
- parsing keeps valid EQ/BE/BZ rows
- insert; rename keeps the id and writes one symbol alias; ISIN change keeps the id and writes one isin alias
- monotonic rule: after seen_on 2026-10-09, an upsert dated 2026-10-01 carrying the old symbol changes nothing and adds no alias
- the same rename applied twice leaves one alias row
- a reused symbol on an inactive row is freed; a newer holder is not
- a 10-row file raises and changes nothing; deactivation skips rows seen within 10 days
- resolve('zomato.ns') works via the alias, and resolve(isin=<old>) works
- search excludes the BZ row and stock_universe tickers, and treats '%' literally
- GET /api/v1/search?query=NEWCO appends the new listing when the flag is on and omits it when off

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
