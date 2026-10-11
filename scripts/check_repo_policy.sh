#!/usr/bin/env bash
# Repo policy gate (OPS-20): grep-based regression checks for deploy, CI and
# repo-hygiene rules. Prints every offending line and exits 1 on any violation.
# Run from anywhere inside the repo: bash scripts/check_repo_policy.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

fail=0

# forbid <description> <git grep args...>: fail if git grep finds anything.
forbid() {
  local desc=$1; shift
  local hits rc=0
  hits=$(git grep -nE "$@") || rc=$?
  # git grep: 0 = match, 1 = no match, >1 = error (bad regex/pathspec): fail closed.
  if [ "$rc" -gt 1 ]; then
    echo "POLICY: git grep error ($rc) in check: $desc"; fail=1
  elif [ -n "$hits" ]; then
    echo "POLICY: $desc"
    printf '%s\n' "$hits"
    fail=1
  fi
}

# Audit records, inventories, tests and this script quote the forbidden strings on purpose.
SELF=':!scripts/check_repo_policy.sh'
QUOTES=(':!docs/investigations' ':!docs/superpowers' ':!ios/docs' ':!.gh-issue-fixer' ':!backend/tests' "$SELF")

# (a) systemd is the only supervisor of the production API.
forbid "unsupervised uvicorn (nohup / fuser -k 8000 / /tmp/uvicorn.log)" \
  'nohup[^#]*uvicorn|fuser -k 8000|/tmp/uvicorn\.log' -- . "${QUOTES[@]}"

# (b) --reload only for local development (backend/run.sh, README dev block).
forbid "uvicorn --reload outside local dev" \
  'uvicorn [A-Za-z_.]+:app[^#]*--reload' -- . "${QUOTES[@]}" ':!backend/run.sh' ':!README.md'

# (c) ML deploy scripts must not touch the API process.
forbid "ML deploy script kills or starts the API" \
  'pkill -f|uvicorn main:app' -- 'scripts/deploy_ml_*.sh'

# (d) Actions pinned to a version; no workflow_dispatch input interpolated into run steps.
forbid "workflow action on a moving branch or raw event input" \
  'uses: .*@(master|main)$|\$\{\{ *github\.event\.inputs' -- .github/workflows

# (e) CI gates must fail closed (TEST-14).
forbid "fail-open CI step (|| echo / || true / || exit 0)" \
  '\|\|[[:space:]]*(echo|true|exit 0)' -- .github/workflows

# (f) Agent/readme entry points exist; the old scratch folder does not.
for f in README.md AGENTS.md CLAUDE.md; do
  [ -f "$f" ] || { echo "POLICY: missing $f"; fail=1; }
done
[ ! -e .TextFiles ] || { echo "POLICY: .TextFiles must not exist"; fail=1; }

# (g) No tracked symlinks; removed helper scripts stay removed.
links=$(git ls-files -s | awk '$1 == "120000" {print $4}')
if [ -n "$links" ]; then
  echo "POLICY: tracked symlinks"; printf '%s\n' "$links"; fail=1
fi
for f in scripts/commit.sh backend/deploy_update.sh; do
  [ ! -e "$f" ] || { echo "POLICY: $f must not exist"; fail=1; }
done

# (h) Deploy verification never calls LLM-backed or heavy routes.
forbid "deploy skill verifies an LLM-backed route" \
  '(GET|POST) /api/v1/[^ |`]*(screener|analy[sz]e|brainstorm|copilot)' -- .claude/skills/nivesh-deploy/SKILL.md

# (i) Secrets and databases stay out of the Docker build context.
for pat in '^\.env$' '\*\.db$'; do
  grep -qE "$pat" backend/.dockerignore || { echo "POLICY: backend/.dockerignore lacks $pat"; fail=1; }
done

# (j) No hard-coded developer checkout path in scripts.
forbid "hard-coded REPO_DIR" 'REPO_DIR="/home/saumyapatel/Desktop/nivesh"' -- scripts "$SELF"

if [ "$fail" -eq 0 ]; then
  echo "Repo policy: OK"
fi
exit "$fail"
