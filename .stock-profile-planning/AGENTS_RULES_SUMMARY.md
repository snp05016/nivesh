# AGENTS.md Rules Summary

## Branch Naming & Git Rules
- Format: `<agent-prefix>/<type>/<issue-number>-<short-slug>` (e.g., `codex/feat/101-financials-ui`).
- Commits: Conventional Commits `type(scope): description`.
- PR Rules: Small, independently reviewable phases. Issue tracking required for all features.

## Backend Conventions
- **Architecture**: Controller-Service-Repository separation.
- **Routers**: No business logic, no `session.query()`. Validation and process spawning only.
- **Services**: All business logic. DB interactions MUST use `get_session()` context manager.
- **Migrations**: Alembic is mandatory (`alembic revision --autogenerate`). Never use `Base.metadata.create_all()`.
- **Formatting**: JSON columns use `default="{}"`.

## iOS / SwiftUI Conventions
- **Aesthetic**: Banknote Aesthetic ONLY. Raw hex codes and system fonts (`.font(.system(...))`) are FORBIDDEN.
- **Numbering**: Indian format ONLY (Lakhs/Crores). "Million/Billion" are FORBIDDEN.
- **Sizing**: Relative sizing. Magic numbers / hardcoded pixel widths are FORBIDDEN. `GeometryReader` forbidden inside `ScrollView`/`HStack`. Use 8pt grid (`Theme.Spacing.*`).
- **Haptics**: `HapticManager.selection()` required on all interactive elements.
- **Architecture**: Unidirectional data flow. ViewModels must NOT be passed 4+ levels deep. Max 3 levels deep in `NavigationStack`. No nesting of `NavigationStack`.

## Testing & Execution Rules
- **Incremental Verification**: Verify output locally before relying on AI.
- **Process Boundaries**: Heavy tasks must use `multiprocessing.Process` with queues.
- **Validation**: Every LLM output must pass through `_normalize_response()` and `_ban_western_scale()`.
