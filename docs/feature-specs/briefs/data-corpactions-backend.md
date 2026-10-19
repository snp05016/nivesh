# Feature package data-corpactions-backend: Typed corporate actions, created_at guard on auto-apply, per-group proposals with apply/dismiss/undo

Cluster: data (Data foundation); area: backend
Features covered: I18

## Files (create or modify)
- backend/services/corporate_actions.py
- backend/services/ledger_service.py
- backend/routers/corporate_actions.py
- backend/tests/test_corporate_action_confirm.py
- backend/tests/test_corporate_actions.py

## Dependencies
- Feature packages (integrated before you start): data-flags, data-instruments, data-schema
- Declared in the plan: data-flags, data-schema, data-instruments, FIX:MATH-07, FIX:MATH-11, FIX:CMON-V1, FIX:DB-01, FIX:DB-09, FIX:DB-08, FIX:DB-24, ENG:be-db-ledger. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Builds on MATH-07 (fetch_split_events, apply_split_events, sync_corporate_actions_all_users and the 07:30 IST job), MATH-11, CMON-V1/DB-01, DB-09 and DB-24. ledger_service stays the only writer. Adapt to C4's signatures if they have changed. Ship in the same release as MATH-07.

ledger_service.py:
- effective_for(ex_on) = datetime.combine(ex_on - 1 day, time(23,59,59), tzinfo=UTC).
- shares_held_before(session, user_id, ticker, effective, group_id): the existing _replay over _ledger_rows(session, user_id, group_id, ticker) with date < effective. Extract it from apply_split_events and use it in both places.
- is_ambiguous(rows, ex_on): rows = that group's rows with date < effective and type not in (SPLIT, BONUS, DIVIDEND). True if any created_at is None or its IST date (created_at is naive UTC; use core.timeutil.IST) is >= ex_on.
- is_cas_only(rows): Transaction has a 'source' attribute and every BUY has source == 'cas'.
- apply_split_events(user_id, ticker, events, action_ids=None): keep MATH-07's loop over groups and events. For each (group, event), with ca_id = action_ids.get(ex_on):
  1. skip if an application exists for (user, group, ca_id) in any status (group None compares with IS NULL);
  2. skip if a SPLIT exists at effective in that group;
  3. skip if held <= 0;
  4. skip if is_cas_only;
  5. not ambiguous: insert the SPLIT as MATH-07 does (quantity = ratio, price 0, date = effective, notes 'auto: corporate action (yfinance)') and replay;
  6. ambiguous, with ca_id set and data_flags.enabled_for('data_corp_actions_confirm', user_id): insert a pending application with shares_before = held;
  7. otherwise do nothing; the event is only recorded.
- sync_corporate_actions_all_users(): MATH-07's flow (fetch outside sessions, per-ticker try/except). For each ticker, ids = corporate_actions.record_events(ticker, events), then apply_split_events(..., action_ids=ids) per holder.
- apply_corporate_action(user_id, app_id):
  - LookupError when missing or another user's; ValueError('INVALID_STATE') unless pending.
  - Insert a SPLIT in the application's group_id (notes 'confirmed: corporate action #{id}'), replay, set status 'applied', transaction_id and decided_at.
  - Return {'item','holding'}.
- dismiss_corporate_action: pending becomes dismissed, with decided_at.
- undo_corporate_action:
  - Allowed for applied or dismissed within 30 days of decided_at; otherwise INVALID_STATE.
  - applied: delete the linked SPLIT and replay.
  - Both: status 'pending', transaction_id None, decided_at None. The job never re-applies, because the application still exists.

corporate_actions.py:
- ratio_text(r): the smallest b in 1..10 with r*b an integer within 1e-6 gives '{b} share(s) became {n}' (2.0 gives '1 share became 2'; 1.5 gives '2 shares became 3'). Otherwise '1 share became ' + format(r, '.4g').
- record_events(ticker, events) -> {ex_on: id}:
  - Normalise the ticker. Upsert by (ticker, 'SPLIT_OR_BONUS', ex_on) with ex_date ISO, ratio, purpose 'Share split or bonus: ' + ratio_text, and source 'yfinance'.
  - nse_confirmed (review): inst = instruments.resolve(ticker); row = its 'nse_bhavcopy' DailyPrice on ex_on; prev = the latest row in [ex_on - 10 days, ex_on).
  - None when inst, row, prev or row.prev_close is missing. Otherwise row.event in ('split','override') and abs(prev_close/prev.close*ratio - 1) <= 0.02.
  - These are internal reads, so the display gate does not apply.
- list_for_user(user_id): pending items plus applied or dismissed items decided in the last 30 days, newest ex_on first. group_name comes from PortfolioGroup.

routers/corporate_actions.py:
- APIRouter(prefix='/api/v1/portfolio/corporate-actions'). Each handler takes user_id = Depends(require_auth) (core.security), then data_flags.require('data_corp_actions_confirm', user_id).
- GET '' returns {'items'}. POST '/{id}/apply', '/dismiss' and '/undo' return {'item','holding'|null}.
- Errors via HTTPException(detail=...): 404 {'code':'NOT_FOUND'}; 409 {'code':'INVALID_STATE','status'}; 409 {'code':'LEDGER_CONFLICT'}.
- Item: {'id','ticker','group_id','group_name','action_label':'Share split or bonus','ratio','ratio_text','ex_date','status','shares_before','shares_after','nse_confirmed','source':'Yahoo Finance corporate actions','decided_at','undo_until'} (decided date + 30 days for applied or dismissed, else null).

tests/test_corporate_actions.py (MATH-07's): set created_at before the ex-date wherever a test expects auto-apply.

## Acceptance checks
PYPARSE and PYRIGHT clean.

test_corporate_action_confirm.py (SQLite get_session patch from test_portfolio_ledger.py; router on a fresh FastAPI(); data_flags monkeypatched) covers:
- ratio_text cases
- record_events upserts once; nse_confirmed is True for 'split' rows (2900, then prev_close 1450, ratio 2), False for 'ca_unverified', None with no rows
- guard with the flag off: a BUY dated 2026-01-10 and created 2026-01-10, with an event on 2026-03-02, auto-applies (200 shares, no application); the same BUY created 2026-03-05 gets no SPLIT and no application; NULL created_at counts as ambiguous
- flag on: the back-dated BUY gets one pending application (shares_before 100, no SPLIT); the unambiguous BUY still auto-applies
- two groups give two pending applications; apply inserts a SPLIT only in its own group
- an allowlisted user gets a proposal while the flag is off; another user does not
- apply gives 200 shares and half the average price; a second apply gives 409
- dismiss then undo gives pending; apply then undo deletes only the linked row, restores 100 shares and gives pending; the next sync neither re-applies nor duplicates
- undo after 31 days gives 409
- another user's id gives 404 NOT_FOUND; flag off for that user gives 404 FEATURE_DISABLED
- every error body is {'detail': {'code': ...}}

The adapted MATH-07 tests pass.

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
