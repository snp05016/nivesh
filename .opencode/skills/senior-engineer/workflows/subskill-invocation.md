# Subskill Invocation

Delegate complex or specialized tasks to subskills. Don't invoke them blindly.

## Available Subskills

| Subskill | When to Use |
|----------|-------------|
| `/nivesh-deploy` | Full server deploy + health check + endpoint audit + test suite |
| `/gh-issue-fixer` | Triage and close/fix batches of GitHub issues |
| `/superpowers` | Brainstorming, multi-step planning, deep codebase reasoning |

## Decision Tree

```
Need to deploy?                    → /nivesh-deploy
Need to fix GitHub issues?         → /gh-issue-fixer
Need to plan a complex feature?    → /superpowers (brainstorming)
Need deep codebase investigation?  → /superpowers (explore)
Need design/architecture help?     → /superpowers (brainstorming)
Need parallel independent work?    → /superpowers (dispatching-parallel-agents)

Simple single-file fix?            → Don't invoke subskills. Just fix it.
Read-only question?                → Don't invoke subskills. Just answer.
```

## Rules

- **Never** invoke a subskill just to read a file or answer a question.
- **Never** invoke multiple subskills for a single-file fix.
- **Only** invoke when the task genuinely requires the subskill's special workflow.
- If the subskill returns an error, handle the error yourself before re-invoking.
