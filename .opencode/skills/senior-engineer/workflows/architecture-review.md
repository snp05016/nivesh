# Architecture Review Workflow

Evaluate architecture decisions. Propose minimal safe changes. Avoid purity refactors.

## Checklist

### 1. Read Architecture Docs
- `CodebaseInformation/ARCHITECTURE_MAP.md` — file map
- `CodebaseInformation/API_REFERENCE.md` — endpoint reference
- `AGENTS.md` §3 (Backend Architecture), §4 (AI Pipeline), §5 (Data Formats)

### 2. Identify Drift
- Does any code violate Controller-Service-Repository?
- Are there business logic leaks in routers?
- Are ORM models duplicated outside `models/db_models.py`?
- Are there circular imports?
- Are there unapplied Alembic migrations?

### 3. Propose Changes
- State the current problem.
- Propose the minimal change.
- Separate "must fix now" from "future cleanup."

### 4. Evaluate Impact
- How many files change? (<5 = safe, 5-15 = moderate, >15 = risky)
- What breaks if this goes wrong?
- What existing tests cover this area?

### 5. Recommend
- If the change is safe and necessary → implement.
- If the change is cosmetic → defer, create a tech debt issue.
- If the change is risky → ask user before proceeding.

## Anti-Patterns

- ❌ "Let's rewrite this entire module"
- ❌ "This pattern is wrong, let me change all 20 files to match"
- ❌ Refactoring code that isn't causing bugs
- ❌ Adding abstractions "just in case"
- ❌ Moving code between files without a concrete benefit

## Areas to Watch

| Pattern | Check |
|---------|-------|
| Router business logic | `backend/routers/*.py` — any yfinance/LLM calls? |
| ORM model leaks | Any `class Foo(Base)` outside `models/db_models.py`? |
| Circular imports | `from main import ...` in any service file |
| Migration drift | `alembic current` vs `alembic heads` |
| Duplicate auth | Both `require_auth` and `verify_access_token` patterns |
