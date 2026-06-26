# Query Router

Route ambiguous or multi-type requests to the correct workflow.

## Decision Tree

```
User request
├── Contains "build"/"add"/"feature"/"implement" + size > 50 lines?
│   └── → feature-implementation.md
├── Contains "fix"/"bug"/"crash"/"broken"/"500"/"not working"?
│   └── → bug-fix.md
├── Contains "deploy"/"redeploy"/"server"/"is everything working"?
│   └── → /nivesh-deploy skill
├── Contains "issue"/"gh issue"/"triage"/"fix issues"?
│   └── → gh-issue-workflow.md
├── Contains "test"/"add test"/"coverage"/"pytest"?
│   └── → testing-verification.md
├── Contains "refactor"/"architecture"/"design"/"review"/"structure"?
│   └── → architecture-review.md
├── Contains "commit"/"cleanup"/"summarize"/"what did we do"?
│   └── → cleanup-and-commit.md
├── Ambiguous, multi-file, multi-step, complex planning needed?
│   └── → /superpowers skill (brainstorming + planning)
└── Simple question, read-only, explanation?
    └── Answer directly from docs or codebase
```

## Implementation

When the main SKILL.md loads:
1. Scan the user query for keywords
2. Load the matching workflow
3. Execute the workflow's checklist
4. Report results

If the query matches multiple categories (e.g., "fix the bug and deploy"), execute them sequentially: fix first, verify, then deploy.
