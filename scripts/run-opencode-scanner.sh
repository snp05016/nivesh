#!/usr/bin/env bash
set -o nounset
set -o pipefail

# ──────────────────────────────────────────────────────────────
# Nivesh OpenCode Scanner — cron wrapper
# Invoked by crontab every 2 hours.
# Uses flock(1) to prevent overlapping executions.
# ──────────────────────────────────────────────────────────────

REPO_DIR="/home/saumyapatel/Desktop/nivesh"
OPENCODE_BIN="/home/saumyapatel/.opencode/bin/opencode"
LOCKFILE="/tmp/nivesh-scanner.lock"
LOGDIR="${REPO_DIR}/logs"
RUNNER_FILE="${REPO_DIR}/opencoderunner.txt"

# Bail early if run outside the repo (safety check)
if [ ! -d "${REPO_DIR}" ]; then
    echo "FATAL: Repository directory ${REPO_DIR} not found." >&2
    exit 1
fi

if [ ! -x "${OPENCODE_BIN}" ]; then
    echo "FATAL: OpenCode binary ${OPENCODE_BIN} not found or not executable." >&2
    exit 1
fi

if [ ! -f "${RUNNER_FILE}" ]; then
    echo "FATAL: Runner file ${RUNNER_FILE} not found." >&2
    exit 1
fi

mkdir -p "${LOGDIR}"

# Lock — exit immediately if another instance holds the lock
exec 200>"${LOCKFILE}"
if ! flock --nonblock 200; then
    echo "[$(date --iso-8601=seconds)] Another scanner instance is already running. Exiting." \
        >> "${LOGDIR}/scanner-error.log"
    exit 1
fi

TIMESTAMP=$(date --iso-8601=seconds)
LOGFILE="${LOGDIR}/scanner-${TIMESTAMP}.log"

cd "${REPO_DIR}"

# Write header
{
    echo "=== Nivesh OpenCode Scanner ==="
    echo "Started at: ${TIMESTAMP}"
    echo "PID:         $$"
    echo "Repository:  ${REPO_DIR}"
    echo "Log file:    ${LOGFILE}"
    echo ""
} >> "${LOGFILE}"

# Execute the scanner. Ignore its exit code so we always log completion.
set +o errexit
${OPENCODE_BIN} --yolo  run "# GitHub Issue Scanner (Research-Grade Multi-Agent Council)

Your task is to perform a **research-grade audit** of the entire codebase using the **`gh-issue-scanner`** skill.

The objective is **not** to maximize the number of GitHub issues. The objective is to maximize the **accuracy and usefulness** of the issues created.

---

# Overall Goal

Search the entire repository for:

* Bugs
* Logic errors
* Edge cases
* Race conditions
* Thread safety issues
* Async issues
* SwiftUI state bugs
* Memory leaks
* Resource leaks
* Security vulnerabilities
* Authentication problems
* Authorization flaws
* Input validation issues
* API contract mismatches
* Database inconsistencies
* Migration issues
* Dead code
* Code smells
* Performance bottlenecks
* Architecture problems
* Technical debt
* UX defects
* Accessibility issues
* Error handling gaps
* Missing tests
* Flaky tests
* Documentation inconsistencies
* Build problems
* CI/CD issues
* Dependency issues
* Reliability concerns
* Maintainability issues
* Scalability limitations

Treat this as if you are reviewing a production codebase before shipping to millions of users.

---

# Multi-Agent Council

Create **three independent agents**.

Each agent must work **without seeing the conclusions of the others**.

The agents should actively disagree whenever appropriate.

## Agent 1 — The Skeptic

Assume every issue is probably real.

Aggressively search for:

* hidden bugs
* unsafe assumptions
* crashes
* edge cases
* missing validation
* undefined behaviour

Goal:
Find everything that *could* realistically break.

---

## Agent 2 — The Defender

Assume the code is correct.

Attempt to disprove every issue discovered.

For every candidate issue ask:

* Is this actually reachable?
* Can this happen in production?
* Is this intentional?
* Is this already handled elsewhere?
* Is it merely stylistic?
* Is there evidence?

Reject weak reports.

---

## Agent 3 — The Senior Staff Engineer

Ignore both previous agents.

Perform an architectural review.

Focus on:

* maintainability
* future scalability
* design quality
* coupling
* abstractions
* modularity
* API design
* technical debt
* long-term engineering risk

Prioritize issues that will matter 1–3 years from now.

---

# Three Iteration Process

Perform **three complete passes**.

---

## Pass 1

Each agent independently audits the repository.

Produce candidate issues only.

Do **not** create GitHub issues yet.

---

## Pass 2

Cross-review.

Every candidate issue must be challenged.

Each issue should receive arguments:

* supporting the issue
* arguing against the issue
* confidence score
* evidence
* affected files
* reproduction steps (if applicable)

Remove:

* duplicates
* speculative findings
* false positives
* cosmetic-only observations

---

## Pass 3

Re-audit the repository focusing on:

* areas surrounding accepted issues
* related modules
* neighbouring code
* recent commits
* similar implementations

Determine whether:

* the issue exists elsewhere
* multiple issues can be merged
* the issue is actually a symptom of a larger architectural problem

Only after Pass 3 is complete should an issue be considered final.

---

# False Positive Policy

Never create an issue unless there is strong evidence.

Reject issues that are:

* hypothetical
* speculative
* preference-based
* style-only
* unsupported
* intentional behaviour
* impossible to reproduce

Quality is vastly more important than quantity.

---

# GitHub Issue Creation

For every accepted issue, use the **GitHub CLI (`gh`)** to create a GitHub issue.

Do **not** generate markdown files.

Do **not** generate reports for manual upload.

Create the issue directly on GitHub.

Each issue must include:

* clear title
* concise summary
* problem description
* affected files
* why it matters
* severity
* confidence level
* reproduction steps (when applicable)
* suggested direction for fixing (not full implementation)

---

# Labels

Apply appropriate labels.

Examples include:

* bug
* critical
* high-priority
* medium-priority
* low-priority
* security
* performance
* architecture
* technical-debt
* enhancement
* documentation
* testing
* ui
* ux
* backend
* frontend
* ios
* android
* api
* database
* ci
* devops
* refactor
* reliability

Create missing labels if necessary.

Never misuse labels.

---

# Duplicate Detection

Before creating a GitHub issue:

* search all existing GitHub issues
* search closed issues
* search pull requests
* search discussions (if available)

If the issue already exists:

* do not recreate it
* instead update the existing issue with additional evidence if appropriate

---

# Priority Framework

Every issue must be assigned exactly one priority.

## Critical

Production crash

Security vulnerability

Data corruption

Authentication failure

Severe financial loss

Major reliability issue

---

## High

Incorrect behaviour

Performance bottleneck

Major UX problem

Scalability blocker

Concurrency bug

Memory leak

---

## Medium

Technical debt

Architecture improvement

Refactoring

Maintainability

Moderate UX issue

Missing tests

---

## Low

Documentation

Minor cleanup

Small optimizations

Nice-to-have improvements

---

# Required Evidence

Every issue must cite concrete evidence, such as:

* source files
* functions
* line numbers (where practical)
* execution path
* logs
* compiler diagnostics
* tests
* stack traces
* screenshots (if available)

Never rely on assumptions alone.

---

# Issue Quality Checklist

Before creating an issue verify:

* reproducible
* actionable
* sufficiently scoped
* non-duplicate
* supported by evidence
* correctly prioritized
* correctly labeled
* clearly written

---

# Final Output

After all GitHub issues have been created, output only:

## Audit Summary

* Total candidate issues
* False positives rejected
* Duplicates skipped
* Existing issues updated
* New GitHub issues created

## Breakdown

Critical: X

High: X

Medium: X

Low: X

## Confidence

Average confidence score

## Repository Health Score

Score the repository from **0–10** based on:

* correctness
* architecture
* maintainability
* reliability
* scalability
* testing
* security
* documentation

Then provide a concise explanation of the score and identify the highest-impact engineering investments for improving it.
" >> "${LOGFILE}" 2>&1
SCANNER_EXIT=$?
set -o errexit

{
    echo ""
    echo "Scanner exit code: ${SCANNER_EXIT}"
    echo "=== Finished at: $(date --iso-8601=seconds) ==="
} >> "${LOGFILE}" 2>&1
