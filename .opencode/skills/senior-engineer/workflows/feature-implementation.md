# Feature Implementation Workflow

Build features in small vertical slices. Plan first, then implement, then verify.

## Checklist

### 1. Read Architecture
- Read `CodebaseInformation/ARCHITECTURE_MAP.md` for the relevant area.
- Read `CodebaseInformation/API_REFERENCE.md` for related endpoints.
- Identify which layers are affected: router, service, repository, model, schema, migration, test.

### 2. Write Implementation Plan
- 3-5 bullet points max.
- State: "I'll add X in router, Y in service, Z in model."
- Estimate files to touch: ~3-7.
- Confirm with user if the feature is large (5+ files) or risky.

### 3. Implement in Vertical Slices
- Backend: model → migration → repository → service → router → test.
- iOS: model → API method → view model → view.
- Each slice should be independently testable.
- Commit after each slice if the user requested autonomous commits.

### 4. Add/Update Tests
- Backend: add pytest test (run on server per AGENTS.md §6.5).
- iOS: verify source compiles (no xcodebuild per AGENTS.md §6.2).

### 5. Update Docs
- If new endpoint: update CodebaseInformation/API_REFERENCE.md.
- If new file: note in ARCHITECTURE_MAP.md.
- Update README.md only if the change is user-visible.

### 6. Verify & Deploy
- Run `nivesh-deploy` skill if backend changed.
- Run all related tests.

### 7. Report
```
**What was built**: <description>
**Files created**: <list>
**Files modified**: <list with line counts>
**API changes**: <new endpoints or modified schemas>
**Tests**: <count passed/failed>
**Deployment**: <SHA, health status>
**Skipped**: <iOS build, local backend tests — per AGENTS.md §6.2, §6.5>
```

## Anti-Patterns

- ❌ Building the entire feature before testing any part
- ❌ Adding "future-proof" abstractions
- ❌ Creating a framework for one use case
- ❌ Writing 500 lines when 100 would work
- ❌ Adding new dependencies without asking
