# Feature package ai-surveillance-data: CONDITIONAL: NSE REG_IND loader, 6-hourly refresh and ASM/GSM flags (build only after the OPS spike and legal sign-off)

Cluster: ai (AI cost architecture and research surfaces); area: backend
Features covered: 40. I33 Risk flags card

## Files (create or modify)
- backend/services/surveillance_service.py
- backend/services/risk_flags_service.py
- backend/services/harvest_worker.py
- backend/tests/test_surveillance_service.py
- backend/tests/test_risk_flags_surveillance.py
- backend/tests/fixtures/reg_ind_sample.csv

## Dependencies
- Feature packages (integrated before you start): ai-flags, ai-riskflags-be
- Declared in the plan: ai-riskflags-be, ai-flags, FIX:REG-10, FIX:REL-03, FIX:ARCH-07, FIX:OPS-18, FIX:TEST-13. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
CONDITIONAL. Build only after human step 2 (REG_IND spike plus legal sign-off as part of the I07 data-licence decision) is recorded as passed, together with the URL template and code meanings it confirmed. If the spike got 401/403 or legal said no, drop this package and keep FEATURE_RISK_FLAGS_SURVEILLANCE=false.

1. New backend/services/surveillance_service.py (stdlib csv, io, re, time, datetime and zoneinfo, plus requests; no new dependency)
Constants:
- URL template from os.getenv('SURVEILLANCE_REG_IND_URL', 'https://nsearchives.nseindia.com/content/equities/REG_IND{ddmmyy}.csv'), read at call time;
- LOOKBACK_DAYS = 7; OK_TTL = 36 * 3600; NOT_APPLICABLE = 100;
- cache namespace 'surveillance', key 'reg_ind'.
class SurveillanceSchemaError(ValueError).
parse_reg_ind(text: str) -> dict[str, dict]
- csv.DictReader; normalise each header with re.sub('[^a-z]', '', h.lower()).
- Columns: symbol is the header equal to 'symbol'; gsm contains 'gsm'; asm_long contains 'asm' and either contains 'long' or starts with 'lt'; asm_short contains 'asm' and either contains 'short' or starts with 'st'. asm_short is optional: NSE's file may not carry short-term ASM.
- A missing symbol column, or neither gsm nor asm_long, raises SurveillanceSchemaError listing the headers.
- Cell: int(float(v)) when non-blank and numeric, else None; NOT_APPLICABLE becomes None. Keep every other raw code, including 0.
- Output only symbols (upper-cased, stripped) with at least one non-None code: {SYMBOL: {'gsm': int|None, 'asm_long': int|None, 'asm_short': int|None}}.
fetch_snapshot(today: date | None = None, *, http_get=requests.get, sleep=time.sleep) -> dict | None
- ua = config.settings.get_user_agent(). If not ua.startswith('NiveshBot'): error_telemetry.log_diagnostic_error(subsystem='SURVEILLANCE', classification='blocked_precondition', context={'reason': 'user_agent_not_honest'}) and return None without any request. Until FIX:REG-10 lands, get_user_agent() returns a random fake browser UA (config/settings.py:154); this guard stops the module from ever disguising the client.
- today defaults to the IST date. For d in today, today-1, ... (LOOKBACK_DAYS dates):
  - url = template.format(ddmmyy=d.strftime('%d%m%y')); resp = http_get(url, headers={'User-Agent': ua}, timeout=(3, 5));
  - 404: try the next date;
  - 401 or 403: log_diagnostic_error(subsystem='SURVEILLANCE', classification='blocked', context={'status': code}) and return None. Never retry with another identity, and never bootstrap cookies.
  - 200 whose body does not start with '<': parse_reg_ind. On SurveillanceSchemaError, log classification='schema' and return None. On success return {'as_of': d.isoformat(), 'source_url': url, 'by_symbol': parsed}.
  - other statuses or exceptions: try the next date.
- sleep(1.0) between requests. Return None when nothing is found.
refresh_snapshot() -> bool
- Return False immediately, with no network call, unless is_enabled('risk_flags_surveillance').
- snap = fetch_snapshot(); on success disk_cache.set('surveillance', 'reg_ind', snap, ttl=OK_TTL) and return True; on failure return False and leave any previous snapshot in place until its TTL lapses.
get_snapshot() -> dict | None
- Cache read only: disk_cache.get('surveillance', 'reg_ind'); a dict with 'as_of' is returned, anything else gives None. It never fetches, so request handlers never wait on NSE.
Use `from services import disk_cache` and call disk_cache.get/set, so tests can replace the module attribute. Module docstring: NSE's public daily regulatory-indicators file, fetched with the honest NiveshBot User-Agent (FIX:REG-10), one small file per scheduled refresh; ASM/GSM was cut from the research engine (D32); the private nseindia.com/api endpoints are deliberately not used; display is allowed per the legal sign-off recorded in human step 2.

2. backend/services/harvest_worker.py, inside start_scheduler(): add a sync callable (FIX:REL-03 registers only sync jobs) `def _run_surveillance_refresh(): from services import surveillance_service; surveillance_service.refresh_snapshot()` and `_scheduler.add_job(_run_surveillance_refresh, 'interval', hours=6, id='surveillance_refresh', replace_existing=True)`. The job does nothing while the flag is off. With FIX:ARCH-07 the scheduler and the API share one process, and FIX:OPS-18's cache works with or without Redis.

3. backend/services/risk_flags_service.py: in risk_flags(), before the concentration step:
- if is_enabled('risk_flags_surveillance'): checks.insert(0, 'surveillance'); snap = surveillance_service.get_snapshot();
- snap None: unavailable.append({'check': 'surveillance', 'reason': 'source_unavailable'});
- otherwise entry = snap['by_symbol'].get(sym); no entry gives no flag and no unavailable entry; else prepend surveillance_flags(sym, entry, snap).
- Order: gsm, asm, then the concentration flags; MAX_FLAGS stays 3.
Code rules, as module constants. OPS confirms them against NSE's REG_IND file-structure PDF during the spike and edits them if NSE's codes differ.
- GSM_STAGES = {1, 2, 3, 4, 6}. gsm == 0: 'NSE lists {SYM} under its Graded Surveillance Measure in its regulatory indicators file dated {D}. Stocks in this framework trade under extra conditions set by the exchange.' gsm in GSM_STAGES: the same text with 'Graded Surveillance Measure (stage {n})'. Any other code: no flag, and log_diagnostic_error(subsystem='SURVEILLANCE', classification='schema', context={'field': 'gsm', 'code': n}).
- ASM_LONG_STAGES = {1, 2, 3, 4}; ASM_SHORT_STAGES = {1, 2}. Parts 'long-term stage {a}' and 'short-term stage {b}' are added only for known codes and joined by '; '; an unknown code is logged the same way and adds no part. One asm flag when at least one part exists: title 'Under exchange surveillance (ASM)', text 'NSE lists {SYM} under its Additional Surveillance Measure ({parts}) in its regulatory indicators file dated {D}. Stocks in this framework trade under extra conditions set by the exchange.'
- gsm flag title: 'Under exchange surveillance (GSM)'. Both flags: source 'NSE regulatory indicators file', source_url 'https://www.nseindia.com/regulations/exchange-market-surveillance-actions', as_of = snap['as_of'].

4. Fixture backend/tests/fixtures/reg_ind_sample.csv
- Header: 'ScripCode,Symbol,NSE Exclusive,Status,Series,GSM,Long_Term_Additional_Surveillance_Measure (Long Term ASM),Short_Term_Additional_Surveillance_Measure (Short Term ASM),ESM,Pledge'.
- Rows: ABC (GSM 2, LT 100, ST 100); DEF (100, 1, 100); GHI (100, 100, 2); JKL (all 100); MNO (GSM blank, LT 3, ST blank); PQR (GSM 0, 100, 100); STU (GSM 5, 100, 100).

5. Tests, backend/tests/test_surveillance_service.py
No network: a fake http_get; a dict-backed fake disk_cache via monkeypatch.setattr(surveillance_service, 'disk_cache', fake); monkeypatch config.settings.get_user_agent.
- parse gives ABC gsm 2, DEF asm_long 1, GHI asm_short 2, MNO asm_long 3, PQR gsm 0 and STU gsm 5, and no JKL entry;
- a header variant without the short-term column still parses; a missing Symbol column raises SurveillanceSchemaError;
- with UA 'NiveshBot/1.0 (+https://example.test/bot)': lookback with 404, 404, 200 gives as_of = today-2 after three requests, and every request's headers['User-Agent'].startswith('NiveshBot');
- with UA 'Mozilla/5.0 (Macintosh)': fetch_snapshot returns None, http_get is never called, and log_diagnostic_error is called with classification 'blocked_precondition';
- 403 returns None after one request with a 'blocked' log; an HTML body with status 200 is skipped;
- refresh_snapshot with the flag off makes no request and returns False; flag on plus success sets the cache with ttl OK_TTL; flag on plus failure leaves an existing snapshot that get_snapshot still returns;
- get_snapshot never calls http_get, and an empty cache gives None.
backend/tests/test_risk_flags_surveillance.py (FEATURE_RISK_FLAGS_SURVEILLANCE=true; monkeypatch surveillance_service.get_snapshot):
- gsm 2 gives a text containing 'stage 2' and the date; gsm 0 gives a text without 'stage'; gsm 5 gives no flag and a 'schema' log;
- asm_long 1 plus asm_short 2 gives one asm flag with both parts; gsm plus asm gives the order gsm, asm;
- snapshot None gives unavailable [{'check': 'surveillance', 'reason': 'source_unavailable'}] and checks[0] == 'surveillance';
- concentration off and surveillance on: the endpoint returns 200 with checks == ['surveillance'];
- surveillance off: 'surveillance' is absent from checks and there is no unavailable entry.

## Acceptance checks
0. Human step 2 is recorded as passed before work starts; otherwise the package is dropped.
1. PYPARSE and PYRIGHT are clean.
2. Both test files pass in CI with the TEST-13 network guard active.
3. grep 'nseindia.com/api', 'fake_useragent' and 'cookies' each return 0 in surveillance_service.py, and get_snapshot contains no HTTP call.
4. harvest_worker.py registers exactly one 'surveillance_refresh' job.
5. No new requirement is added.

## Cluster spec
docs/feature-specs/spec_ai.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
