# Git and GitHub Agent Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one documented and enforced Git and GitHub workflow for every repository agent.

**Architecture:** Keep the three runtime guidance files identical and enforce synchronization in GitHub Actions. Use GitHub issue forms, a pull-request template, CODEOWNERS, labels, repository settings, and branch protection to turn the policy into an executable workflow.

**Tech Stack:** Markdown, GitHub issue forms, GitHub Actions YAML, Git, GitHub CLI, GitNexus, Graphify

## Global Constraints

- Do not modify or stage unrelated user changes.
- Never run local backend Python tests or `xcodebuild`.
- Run GitNexus change detection before every commit.
- Run `graphify update .` after repository files change.
- Never merge into `main` without explicit user approval.
- Use issue #2 for this implementation.

---

### Task 1: Record the approved workflow

**Files:**
- Create: `docs/superpowers/specs/2026-06-22-git-github-agent-workflow-design.md`
- Create: `docs/superpowers/plans/2026-06-22-git-github-agent-workflow.md`

**Interfaces:**
- Consumes: Approved workflow stated in the conversation and issue #2.
- Produces: Stable design and execution record for later tasks.

- [ ] **Step 1:** Write the approved design and implementation plan.
- [ ] **Step 2:** Run `git diff --check` and confirm no whitespace errors.
- [ ] **Step 3:** Run GitNexus change detection and inspect `git diff --stat`.
- [ ] **Step 4:** Commit with `docs(repository): document GitHub agent workflow`.

### Task 2: Synchronize agent guidance

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `GEMINI.md`

**Interfaces:**
- Consumes: The approved design.
- Produces: One identical policy consumed by Codex, Claude, and Gemini.

- [ ] **Step 1:** Replace the narrow commit workflow with issue intake, branching, commit, PR, review, merge, deployment, release, and completion rules.
- [ ] **Step 2:** Copy the complete authoritative `AGENTS.md` to the other two guidance files through an `apply_patch` edit.
- [ ] **Step 3:** Run `cmp` across all three files; expect no differences.
- [ ] **Step 4:** Run policy scans and `git diff --check`.
- [ ] **Step 5:** Run GitNexus change detection and inspect the staged scope.
- [ ] **Step 6:** Commit with `docs(repository): standardize agent Git workflow`.

### Task 3: Add GitHub workflow artifacts

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/technical_work.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/pull_request_template.md`
- Create: `.github/CODEOWNERS`
- Create: `.github/workflows/agent-guidance-sync.yml`

**Interfaces:**
- Consumes: The issue and PR requirements in the synchronized policy.
- Produces: Structured GitHub intake, review metadata, ownership, and a required synchronization check.

- [ ] **Step 1:** Add required issue forms with scope, acceptance criteria, verification, risk, and dependency fields.
- [ ] **Step 2:** Add a PR template with issue linkage, summary, testing, risk, deployment, migration, UI evidence, and checklist sections.
- [ ] **Step 3:** Add CODEOWNERS for `@snp05016`.
- [ ] **Step 4:** Add a pull-request workflow that compares all three guidance files.
- [ ] **Step 5:** Parse every YAML file and run `git diff --check`.
- [ ] **Step 6:** Run GitNexus change detection and inspect the staged scope.
- [ ] **Step 7:** Commit with `chore(repository): add GitHub workflow templates`.

### Task 4: Publish and configure GitHub

**Files:**
- Modify through GitHub API: repository merge settings and `main` branch protection.

**Interfaces:**
- Consumes: Published synchronization workflow and repository labels.
- Produces: A draft PR linked to issue #2 and enforceable repository governance.

- [ ] **Step 1:** Run `graphify update .` and commit generated graph changes separately if Graphify changes tracked files.
- [ ] **Step 2:** Push `codex/docs/2-git-github-workflow` and open a draft PR with `Closes #2`.
- [ ] **Step 3:** Use `gh api` to enable squash-only merging and automatic branch deletion.
- [ ] **Step 4:** Use `gh api` to protect `main`, require pull requests, require conversation resolution, and require the guidance synchronization check while leaving administrator enforcement disabled.
- [ ] **Step 5:** Query repository settings, branch protection, PR checks, and issue metadata; compare each value with the approved policy.
- [ ] **Step 6:** Report the draft PR and leave merging to the user.
