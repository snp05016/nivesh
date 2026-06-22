# Git and GitHub Agent Workflow Design

## Goal

Give every coding agent one enforceable workflow for issues, branches, commits, pull requests, reviews, merging, releases, and deployment.

## Approved direction

Keep the policy identical in `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`. Treat `AGENTS.md` as the authority, but require byte-for-byte synchronization so each agent runtime receives the same rules.

Back the written policy with GitHub-native controls: structured issue forms, a pull-request template, CODEOWNERS, repository labels, squash merging, automatic branch deletion, and `main` branch protection. Use `gh` and `gh api` for GitHub state. Preserve administrator recovery access.

## Workflow

Agents start by inspecting the repository and searching for duplicate issues. Non-trivial work receives an issue with acceptance criteria and verification requirements. Work proceeds on an issue-linked branch through small conventional commits and an early draft pull request. Checks, review threads, deployment evidence, and follow-up issues determine completion.

Agents must preserve unrelated work, stage explicit paths, avoid destructive Git commands, and obtain user approval before merging. Backend verification remains remote-only and must identify the deployed commit.

## Repository artifacts

- `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`: identical agent policy.
- `.github/ISSUE_TEMPLATE/*.yml`: bug, feature, and technical-work intake.
- `.github/pull_request_template.md`: review and verification contract.
- `.github/CODEOWNERS`: default ownership.
- `.github/workflows/agent-guidance-sync.yml`: synchronization check.
- GitHub repository settings: squash-only merge, automatic branch deletion, and protected `main`.

## Verification

Validate YAML syntax, compare the three guidance files, inspect the staged scope, run GitNexus change detection, update Graphify, and query GitHub settings after applying them. Do not run local backend Python or `xcodebuild`.

## Safety

Apply changes in an isolated worktree. Do not stage or modify the user's unrelated working-tree changes. Keep `enforce_admins` disabled in branch protection so the owner can recover from a misconfigured required check.
