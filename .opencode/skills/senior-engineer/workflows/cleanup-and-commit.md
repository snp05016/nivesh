# Cleanup & Commit Workflow

Clean up after a task. Commit surgically. Never stage junk.

## Cleanup

### Delete
- Temporary scratch files created during the task (e.g., `temp_body.md`, `scratch_*.py`).
- Debug `print()` statements added during investigation (unless user wants them).
- Generated files that aren't part of the deliverable.

### Keep
- Test files created for the task.
- Architecture docs updated during the task.
- Skills created during the task (e.g., `.opencode/skills/`).

### Don't Touch
- Pre-existing dead code.
- Pre-existing debug prints.
- Pre-existing temp files.
- Files the user modified in parallel.

## Commit (AGENTS.md §6.4.4)

### Before Committing
```bash
git status --short          # review ALL modified files
git diff --check            # check for whitespace errors
git diff --stat             # review scope
git diff                    # review actual changes
```

### Stage
- Stage ONLY files relevant to the task.
- Use explicit paths: `git add backend/routers/market.py`.
- NEVER `git add .` or `git add -A` unless the entire diff is reviewed and intentional.

### Commit Message
Format: `type(scope): description`

Valid types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `style`, `perf`, `ci`, `build`, `revert`.

Valid scopes: `ios`, `backend`, `copilot`, `earnings`, `correlation`, `stress-test`, `nl-screener`, `anomalies`, `sector-rotation`, `settings`, `home`, `portfolio`, `markets`, `analysis`, `repository`.

Examples:
```
fix(backend): handle yfinance calendar returning dict instead of DataFrame
feat(backend): add /api/v1/predictions/performance analytics endpoint
fix(ios): remove nested NavigationStack from NLScreenerScreen
chore(repository): remove agent work directories from git
```

### Push
```bash
git push origin main
```

## Summarize

After any task, update the anchored summary with:
- What was done
- Key decisions made
- Relevant files changed
