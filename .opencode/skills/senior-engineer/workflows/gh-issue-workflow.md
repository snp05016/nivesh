# GitHub Issue Workflow

Triage and fix GitHub issues methodically. One issue at a time.

## Prerequisites
- Use `gh` CLI for all GitHub operations.
- Admin token (`Authorization: Bearer admin`) for protected endpoints.
- Read AGENTS.md §8 for GitHub DevOps Hub rules.

## Checklist

### 1. Survey
```bash
gh issue list --state open --limit 50 --json number,title,labels
```
- Count: how many open?
- Categorize: real bugs vs. code violations vs. tech debt vs. stale/false-positive.

### 2. Read Each Issue
```bash
gh issue view <number> --json title,body,labels,comments
```
- Is it a real functional bug? → fix it.
- Is it a code scanner violation (hardcoded spacing, default font)? → close as "not planned" with note.
- Is it tech debt? → acknowledge, close if low priority.
- Is it a duplicate? → close as duplicate with link.
- Is it already fixed? → close as completed with evidence.
- Is it stale/irrelevant? → close as "not planned."

### 3. Fix One at a Time
- Read the issue.
- Reproduce or confirm the issue.
- Apply the fix.
- Verify.
- Close the issue with a comment explaining the fix and verification.

### 4. Never
- ❌ Close issues just to reduce count.
- ❌ Close without reading the body.
- ❌ Close as "completed" without evidence of the fix.
- ❌ Mark multiple unrelated issues as duplicate of one.
- ❌ Skip issues because they're "too small."

## Issue Triage Categories

| Category | Action |
|----------|--------|
| Real functional bug | Reproduce → fix → verify → close as completed |
| iOS code violation (AGENTS.md) | Close as "not planned" — noted for next iOS sweep |
| Tech debt / chore | Close as "not planned" with acknowledgment |
| Already fixed in code | Close as completed with commit SHA evidence |
| Stale / false positive | Close as "not planned" |
| Duplicate | Close as duplicate, link to canonical issue |
| External dependency | Close as "not planned" (YouTube quota, NSE scraper) |
