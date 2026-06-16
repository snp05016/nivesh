# Backend Test Audit Plan

## Objective
Implement `prompts/TEST_BACKEND_PROMPT.md`: remove the looping legacy API test, inventory the backend, add deterministic offline tests for database/API/service/migration risk, run adversarial review loops, and produce `backend_test_audit_report.md`.

## Constraints
- Do not call live LLMs or market APIs.
- Do not rewrite production code unless a testability blocker makes valid tests impossible.
- Use existing `backend/tests/conftest.py` heavy-module mocks unless a narrower fixture is needed.
- Do not run Xcode.

## Steps
1. Inventory FastAPI routes, ORM metadata, migrations, services, and existing tests.
2. Delete `backend/tests/test_api.py`.
3. Add deterministic tests for:
   - route inventory and schema contracts,
   - database constraints/relationships/precision,
   - migration chain sanity and destructive-operation detection,
   - auth/watchlist/portfolio/trade-journal ownership and invalid input,
   - financial helper/service math that can run offline,
   - concurrency/idempotency around uniqueness and job state.
4. Run four adversarial review loops:
   - Loop 1: route coverage gaps,
   - Loop 2: database and migration invariants,
   - Loop 3: financial correctness and service contracts,
   - Loop 4: failure modes, auth isolation, and report completeness.
5. Run pytest on the new/affected backend tests; fix test infrastructure only where needed.
6. Write `backend_test_audit_report.md` with inventory, results, defects, and documented untestable areas.

## Verification
- `cd backend && .venv/bin/python3 -m pytest ...`
- `git status --short`
- If production symbols are edited, run GitNexus impact first and detect changes before any commit.
