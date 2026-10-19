# Feature package platform-events-api: Consent-gated POST /api/v1/events, erasure on consent withdrawal, per-caller flag fields and SQL docs

Cluster: platform (Platform, operations and privacy); area: backend
Features covered: 36 I47 First-party product analytics, 28 I06 Privacy center: erasure, export, consent

## Files (create or modify)
- backend/services/events_service.py
- backend/routers/events.py
- backend/routers/flags.py
- backend/services/disclosure_service.py
- backend/services/kyc_consent_service.py
- backend/services/compliance_service.py
- backend/core/rate_limiter.py
- backend/main.py
- backend/tests/test_events_api.py
- docs/analytics/QUERIES.md

## Dependencies
- Feature packages (integrated before you start): platform-events-db, platform-flags
- Declared in the plan: platform-events-db, platform-flags, FIX:FINSEC-04, FIX:FINSEC-09, FIX:DB-10, FIX:AUTH-01, FIX:FINSEC-22, FIX:FINSEC-03. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
I47 event ingestion, plus the immediate erase on consent withdrawal and the per-caller flag fields.

Contract, shared with platform-ios-flags-events:
- POST /api/v1/events requires Authorization: Bearer and returns 401 without it.
- Body: {'events': [{'name': 'app_open', 'props': {'launch': 'cold'}, 'ts': '2026-10-11T03:12:00Z'}], 'app_version': '1.4.0', 'platform': 'ios'}. Send 1-50 events; anything else is a 422.
- Response: 202 {'accepted': int, 'rejected': int, 'reason': null | 'disabled' | 'no_consent'}.
- Identity comes only from the token. Any user_id in the body is ignored.
- GET /api/v1/flags gains two fields:
  - flags['analytics_consented']: true only when the caller sends a valid token, 'analytics' is enabled, and the caller has an active 'product_analytics' consent; otherwise false;
  - the top-level int 'analytics_retention_days' = services.retention.USER_EVENTS_RETENTION_DAYS.
  The response keeps platform-flags' Cache-Control: no-store, private and Vary: Authorization headers.

1. services/events_service.py
- EVENT_SCHEMA:
  - app_open: launch in {cold, warm}
  - search: results in {0, 1-5, 6+}
  - stock_view: no props
  - report_view: state in {fresh, stale, expired, not_covered, unavailable}
  - report_compute: result in {ok, quota, unavailable, error}
  - alert_create: direction in {above, below}
  - import_start: kind in {cas, csv, manual}
  - import_done: kind in {cas, csv, manual}; outcome in {ok, partial, failed}
  - paywall_view: no props
  - purchase: outcome in {success, cancelled, failed, pending}
- validate(name, props) -> bool. True only when:
  - name is in the schema;
  - props is a dict of at most 4 str->str pairs;
  - every key is allowed for that event and every value is in its allowed set.
  This means tickers, amounts and free text can never be stored.
- ingest(user_id, events, app_version, platform) -> dict:
  - If feature_flags.is_enabled('analytics') is false, return accepted 0, rejected = number of events, reason 'disabled', without touching the DB.
  - If kyc_consent_service.has_active_consent(user_id, 'product_analytics') (FIX:FINSEC-04) is false, return reason 'no_consent'.
  - Otherwise insert the valid events in one session (add_all, one commit):
    - created_at = ts converted to naive UTC and clamped to [now - 7 days, now + 5 minutes]; a missing or out-of-range ts becomes now;
    - app_version cut to 20 characters.
  - Count invalid events as rejected.
- erase_user_events(user_id) -> int: in one get_session(), execute delete(UserEvent).where(UserEvent.user_id == user_id), commit, and return the row count.
- daily_counts(days=14) -> {'days': d, 'active_users': distinct users with an event in the window, 'rows': [{'date': 'YYYY-MM-DD' in IST, 'event_name', 'events', 'users'}]}. Only users with analytics on can have events.
  - Clamp days to 1..31.
  - Aggregate in Python over one bounded query. Add the comment 'ponytail: move to SQL date_trunc past ~1M rows a month'.

2. routers/events.py
- APIRouter(prefix='/api/v1/events', tags=['Events']).
- Pydantic models:
  - EventIn: name str of 1..40 chars; props dict[str, str] = {}; ts datetime | None = None.
  - EventsBatch: events list[EventIn] of 1..50; app_version str | None with max 20; platform Literal['ios'] = 'ios'.
- POST '': status_code 202, plain def, user_id = Depends(require_auth).
  - Call _check_rate_limit(f'user:{user_id}', 'events') first.
  - Then return events_service.ingest(...).

3. core/rate_limiter.py: add _RATE_LIMITS['events'] = {'window': 3600, 'max_requests': 120}.
- It is keyed per user.
- The key has no leading slash, so the per-IP middleware never matches it.

4. services/disclosure_service.py: add CONSENT_PURPOSES['product_analytics'] = f'Share app usage events (screens opened and features used; never holdings, stock names or amounts) to improve Nivesh. Kept {USER_EVENTS_RETENTION_DAYS} days. You can turn this off at any time; turning it off deletes the events already recorded.'
- Import USER_EVENTS_RETENTION_DAYS from services.retention.
- FIX:FINSEC-09 makes record_consent reject unknown types, so this entry is required.

5. services/kyc_consent_service.py: add on_consent_withdrawn(user_id, consent_type) -> None.
- If consent_type == 'product_analytics', call events_service.erase_user_events(user_id). Use a local import to avoid an import cycle.
- Wrap it in try/except that calls logger.exception and never raises. The daily retention backstop (platform-events-db) cleans up any failed erase.
- Call it only after the withdrawing transaction has committed and its session has closed. On SQLite, an open write transaction would block the erase's own session.
  - record_consent: when granted is False, assign the result inside the 'with get_session()' block, then call on_consent_withdrawn after the block exits, then return.
  - revoke_consent, own-session path: do the same on both returns (revoked, and nothing-to-revoke). The erase is idempotent and also clears leftovers of an earlier failed erase.
  - If FIX:DB-10 added a session= parameter, the caller-owned-session path does not call it; that caller calls it after its own commit (item 6).

6. services/compliance_service.py: in withdraw_consent, if it passes its own session to revoke_consent (FIX:DB-10's session= path), call kyc_consent_service.on_consent_withdrawn(user_id, consent_type) after its audit commit. If it calls revoke_consent without a session, the hook already ran, so add nothing. grep for any other revoke_consent(..., session=...) caller and apply the same rule.

7. routers/flags.py:
- GET takes user_id: Optional[int] = Depends(core.security.get_current_user_id), which returns None instead of raising.
- It adds flags['analytics_consented'] and the top-level 'analytics_retention_days' as described in the contract.
- Keep the JSONResponse headers from platform-flags.

8. main.py: include events.router.

9. docs/analytics/QUERIES.md: Postgres SQL for:
- daily and weekly active users (analytics on);
- D1/D7/D30 cohort retention from first app_open;
- the search -> stock_view -> report_view funnel;
- paywall_view -> purchase;
- the report_compute outcome mix.
State that only consented users are counted, that withdrawn users' events are deleted, and that App Store Connect analytics is the unbiased baseline.

## Acceptance checks
- AST parse and pyright are clean.
- tests/test_events_api.py passes in CI with these cases:
  - 401 without a token.
  - Flag off: 202 with reason 'disabled' and no rows.
  - Flag on, no consent: reason 'no_consent' and no rows.
  - With consent: rows are stored under the token's user_id, even when the body carries a different user_id field.
  - An unknown event, an unknown prop key and a bad value are each counted as rejected.
  - 51 events gives 422.
  - A ts 30 days old is stored as now.
  - With _RATE_LIMITS['events'] monkeypatched to 2 requests, the third request gets 429.
  - analytics_consented is true only with a token, the flag on and consent granted.
  - daily_counts puts an event at 2026-10-10 19:00 UTC on 2026-10-11, and reports active_users.
  - Withdrawal: grant product_analytics, ingest 3 events, call revoke_consent, and 0 user_events rows remain for the user and daily_counts excludes them. The same holds through record_consent(granted=False) and through compliance_service.withdraw_consent.
  - With events_service.erase_user_events monkeypatched to raise, the withdrawal still returns success and the consent is revoked.
  - GET /api/v1/flags returns analytics_retention_days equal to retention.USER_EVENTS_RETENTION_DAYS, and still sends Cache-Control no-store and Vary Authorization.
  - CONSENT_PURPOSES['product_analytics'] contains the retention number.
- The FINSEC-09 consent test still passes with the new purpose.

## Cluster spec
docs/feature-specs/spec_platform.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

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
