---
name: gh-issue-fixer
description: >
  Performs end-to-end GitHub issue triage, validation, implementation, verification, update, and
  closure for the Nivesh repository. Use when asked to fix, triage, or close GitHub issues.
  Adversarially validates every claim before touching code. Respects AGENTS.md, CLAUDE.md,
  and all project constraints. Never creates a PR without explicit user approval.
trigger: /gh-issue-fixer
---

# gh-issue-fixer

Full-lifecycle GitHub issue triage → validation → fix → verify → close for the Nivesh repository.

---

## Design Principles

1. **Adversarial first** — do not assume issues are correct. Challenge every claim.
2. **Surgical scope** — fix only the minimum. No opportunistic cleanup.
3. **Evidence-gated closure** — never close without posting a final comment with commit hash,
   files changed, verification performed, and remaining risk.
4. **No API-credit burns** — never run LLM-powered commands (analysis pipelines, AI endpoints)
   unless the user explicitly confirms it is safe.
5. **AGENTS.md is law** — read it first. Obey every constraint it defines.
6. **One issue = one commit** — never batch unrelated fixes.
7. **Branch-first** — always work on a feature branch, never on `main`.
8. **No unsolicited PRs** — push the branch; open a PR only if the user explicitly says so.

---

## Phase 0 — Worktree Enforcement

Never use `git checkout`. Always create a detached worktree.

```bash
WORKTREE_PATH="/Users/saumya/Desktop/nivesh-agy-fix-gh-issues"
git -C /Users/saumya/Desktop/nivesh worktree add --detach "$WORKTREE_PATH"
cd "$WORKTREE_PATH"
```

All work happens inside this detached worktree.

---

## Phase 1 — Repository Rule Loading

Read in this order (stop and report if any file is missing):

1. `AGENTS.md` — supreme authority
2. `CLAUDE.md` — if present
3. `GEMINI.md` — if present
4. `README.md` — project overview
5. `docs/00_STATE.md` or any root doc map

Extract and record:
- **Forbidden commands** (e.g., `xcodebuild`, bare `pytest`, production server start)
- **API-credit-sensitive paths** (LLM calls, analysis endpoints)
- **Test rules** (remote-only? local allowed? which venv?)
- **DB migration rules** (Alembic required for schema changes)
- **iOS build rules** (`xcodebuild` is prohibited)
- **Branch and PR rules** (branch-first, no unsolicited PR)

---

## Phase 2 — Issue Inventory

Create the tracking directory:

```
.gh-issue-fixer/
  TASK.md
  ISSUE_INVENTORY.md
  TRIAGE_LOG.md
  FALSE_POSITIVES.md
  FIX_PLAN.md
  FIX_LOG.md
  VERIFICATION_LOG.md
  CLOSED_ISSUES.md
  HANDOFF.md
```

Fetch all open issues:

```bash
gh issue list --state open --limit 200 \
  --json number,title,labels,assignees,createdAt,updatedAt,url,body
```

Write every issue to `.gh-issue-fixer/ISSUE_INVENTORY.md` with:
- Issue number
- Title
- Labels
- Body summary (first 300 chars)
- Claimed problem
- Suspected files/symbols
- Priority (from labels or inferred)
- Needs validation: YES/NO
- Status: `PENDING`

---

## Phase 3 — Per-Issue Triage (adversarial validation)

For each issue:

### Step 3a — Fetch full issue detail

```bash
gh issue view <ISSUE_NUMBER> --json number,title,body,comments,labels,state,url
```

### Step 3b — Inspect codebase

Search for the claimed symbol, file, or pattern:
- Use grep / ripgrep to verify the claim exists in code
- Read the specific file + line range mentioned
- Check git log for recent changes that may have already fixed it

### Step 3c — Delegate skeptical review

Spawn or mentally adopt the role of a **skeptical reviewer subagent** with this prompt:

> You are a skeptical reviewer. Do NOT assume this GitHub issue is correct.
> Inspect the issue claim against the current codebase.
> Determine whether it is a real bug, false positive, duplicate, already fixed,
> obsolete, or unclear.
> Provide evidence with file paths, symbols, and exact reasoning.
> Do NOT propose broad refactors.
> Return one of: REAL_BUG | REAL_MISSING_FEATURE | FALSE_POSITIVE | DUPLICATE | ALREADY_FIXED | OBSOLETE | NEEDS_HUMAN_DECISION

Record classification + evidence in `.gh-issue-fixer/TRIAGE_LOG.md`.

### Step 3d — Classification

```
REAL_BUG             → proceed to Phase 4
REAL_MISSING_FEATURE → proceed to Phase 4
FALSE_POSITIVE       → proceed to Phase 6 (close, no code change)
DUPLICATE            → proceed to Phase 6 (close, no code change)
ALREADY_FIXED        → proceed to Phase 6 (close, no code change)
OBSOLETE             → proceed to Phase 6 (close, no code change)
NEEDS_HUMAN_DECISION → stop, post comment, leave open
```

---

## Phase 4 — Fixing Real Issues

For each `REAL_BUG` or `REAL_MISSING_FEATURE`:

### Step 4a — Write a narrow fix plan

In `.gh-issue-fixer/FIX_PLAN.md`:
- Files to change (by name and line range)
- What exactly changes
- What must NOT change
- Any migration or config impact

Rules:
- Modify ONLY files required for the issue
- Preserve existing architecture (Controller-Service-Repository pattern)
- Use `Theme.*` tokens only in iOS (no raw hex, no raw spacing)
- Use `IndianFormatter` / `format_indian_currency()` for all financial numbers
- Do not touch secrets, `.env`, local DBs, generated artifacts, or logs
- Do not run `xcodebuild` under any circumstances
- Backend schema changes → Alembic migration required

### Step 4b — Implement the fix

Apply the minimum necessary change. No opportunistic cleanup.

### Step 4c — Inspect your own changes

```bash
git diff --check
git diff --stat
git diff
```

Fix any whitespace errors or obvious problems before committing.

---

## Phase 5 — Verification

Run the safest valid verification for the change type.

| Change type | Allowed verification |
|---|---|
| Backend Python | `cd backend && .venv/bin/pytest tests/<specific_test_file>.py -v` (only if AGENTS.md permits local tests) |
| iOS Swift | Source-level inspection only. Document manual validation needed. **Never run xcodebuild.** |
| Docs only | `git diff --check -- docs/` |
| DB migration | `alembic check` after `alembic revision --autogenerate` |
| Static changes | Source inspection, grep for affected symbol usage |

Write all commands and their output to `.gh-issue-fixer/VERIFICATION_LOG.md`.

**Hard stop conditions** — stop and request human decision if:
- Fix requires API-credit-consuming validation
- Fix requires credentials or secrets
- Fix requires destructive DB migration
- Fix would require broad architectural rewrite
- Working directory is dirty in unrelated files and cannot be safely isolated

---

## Phase 5b — Surgical Commit

After verification passes:

```bash
git status --short
git diff --check
git diff --stat
git add <ONLY_FILES_CHANGED_FOR_THIS_ISSUE>
```

Commit message format:
```
fix: resolve gh-<ISSUE_NUMBER> <short issue slug>

Issue: #<ISSUE_NUMBER>
Classification: REAL_BUG
Verification:
- <command>: <result>
```

For non-bug closures:
```
chore: close gh-<ISSUE_NUMBER> <short issue slug>
docs: resolve gh-<ISSUE_NUMBER> <short issue slug>
test: cover gh-<ISSUE_NUMBER> <short issue slug>
```

**Never commit unrelated dirty files.** Leave them untouched and record in final summary.

---

## Phase 6 — GitHub Issue Update and Closure

### For REAL_BUG / REAL_MISSING_FEATURE (after commit exists):

```bash
gh issue comment <ISSUE_NUMBER> --body "$(cat <<'EOF'
## Resolution

**Classification:** REAL_BUG

## Fix Summary

- <one-line per change>

## Files Changed

- `path/to/file.py` — description of change

## Verification

- Command: `<command>`
- Result: PASSED

## Commit

`<commit-hash>`

## Remaining Risk

- <any residual risk, or "None identified">

Closing — issue fixed and verified.
EOF
)"
gh issue close <ISSUE_NUMBER>
```

### For FALSE_POSITIVE / DUPLICATE / ALREADY_FIXED / OBSOLETE:

```bash
gh issue comment <ISSUE_NUMBER> --body "$(cat <<'EOF'
## Triage Result

**Classification:** FALSE_POSITIVE

## Evidence

- File inspected: `<path>`
- Actual code: `<snippet or description>`
- Why the claim is incorrect: <reasoning>

No code change required. Closing as not planned.
EOF
)"
gh issue close <ISSUE_NUMBER> --reason "not planned"
```

### For NEEDS_HUMAN_DECISION:

```bash
gh issue comment <ISSUE_NUMBER> --body "$(cat <<'EOF'
## Triage Result

**Classification:** NEEDS_HUMAN_DECISION

## Reason

<why this cannot be resolved automatically>

## Options

1. <option A>
2. <option B>

Leaving open for human review.
EOF
)"
```

Do NOT close. Leave open.

---

## Phase 7 — Handoff and Cleanup

### Keep these files:
```
.gh-issue-fixer/SUMMARY.md
.gh-issue-fixer/CLOSED_ISSUES.md
.gh-issue-fixer/HANDOFF.md
```

### Delete these intermediate files:
```bash
rm -f .gh-issue-fixer/FIX_PLAN.md
rm -f .gh-issue-fixer/TRIAGE_LOG.md
rm -f .gh-issue-fixer/FIX_LOG.md
rm -f .gh-issue-fixer/VERIFICATION_LOG.md
```

If the project does not want `.gh-issue-fixer/` committed:
```bash
# Either add to .gitignore or delete entirely after printing summary
echo ".gh-issue-fixer/" >> .gitignore
```

---

## Final Summary Output

At the end, output a complete summary in this format:

```md
# GH Issue Fixer Final Summary

## Issues inspected

- Total: N

## Issues fixed and closed

| Issue | Classification | Commit | Files changed | Verification |
|---|---|---|---|---|
| #N | REAL_BUG | abc1234 | file.py | pytest: PASSED |

## Issues closed without code changes

| Issue | Reason | Evidence |
|---|---|---|
| #N | FALSE_POSITIVE | Symbol does not exist in codebase |

## Issues left open

| Issue | Reason | Required human decision |
|---|---|---|
| #N | NEEDS_HUMAN_DECISION | Requires product judgment on X |

## Code changes made

### #<N> — <TITLE>

Changed files:
- ...

What changed:
- ...

Why:
- ...

Verification:
- ...

Commit:
- ...

## Files intentionally not committed

- (list any unrelated dirty files that were left untouched)

## Temporary artifacts removed

- `.gh-issue-fixer/FIX_PLAN.md`
- `.gh-issue-fixer/TRIAGE_LOG.md`
- `.gh-issue-fixer/FIX_LOG.md`
- `.gh-issue-fixer/VERIFICATION_LOG.md`

## Commands not run and why

- `xcodebuild` — forbidden by AGENTS.md §6.2
- `pytest` (full suite) — API-credit-sensitive; ran only targeted test files
- <any other skipped command>

## Remaining risk

- (list any known risks from partial verification or skipped checks)
```

---

## Quick Reference Card

```bash
# Fetch all open issues
gh issue list --state open --limit 200 --json number,title,labels,assignees,createdAt,updatedAt,url,body

# View single issue with comments
gh issue view <N> --json number,title,body,comments,labels,state,url

# Post a comment
gh issue comment <N> --body "<TEXT>"

# Close with reason
gh issue close <N>
gh issue close <N> --reason "not planned"
gh issue close <N> --reason "completed"

# Setup Worktree
WORKTREE_PATH="/Users/saumya/Desktop/nivesh-agy-fix-gh-issues"
git -C /Users/saumya/Desktop/nivesh worktree add --detach "$WORKTREE_PATH"
cd "$WORKTREE_PATH"

# Surgical add + commit
git add <specific-files>
git commit -m "fix: resolve gh-<N> <slug>"

# Ask user for approval to merge, then merge
COMMIT_HASH=$(git rev-parse HEAD)
git -C /Users/saumya/Desktop/nivesh merge --ff-only $COMMIT_HASH
git -C /Users/saumya/Desktop/nivesh push origin main
git -C /Users/saumya/Desktop/nivesh worktree remove "$WORKTREE_PATH" --force
```

---

## Nivesh-Specific Constraints (from AGENTS.md)

| Constraint | Rule |
|---|---|
| iOS build | Never run `xcodebuild`. iOS is reference-only. |
| Colors | Only `Theme.*` tokens. No raw hex. |
| Fonts | No `.system(size:...)`. Use `Theme.engravedSerif()` etc. |
| Numbers | All financial values in Lakhs/Crores. No Million/Billion/Trillion. |
| DB changes | Always Alembic. Never manual `ALTER TABLE`. |
| DB sessions | Always `get_session()`. Never global session. |
| Business logic | Only in `services/`. Never in `routers/`. |
| Tests | Backend: `.venv/bin/pytest` for targeted files only. |
| Global state | Requires `threading.Lock`. |
| Prompt integrity | Never shorten `INDIAN_MARKET_SYSTEM_PROMPT`. |
| Branching | Never work on `main`. |
| Pull requests | Never open unless user explicitly requests. |
