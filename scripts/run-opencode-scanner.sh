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
${OPENCODE_BIN} run "using the gh-issue scanner please run $(cat "${RUNNER_FILE}")" >> "${LOGFILE}" 2>&1
SCANNER_EXIT=$?
set -o errexit

{
    echo ""
    echo "Scanner exit code: ${SCANNER_EXIT}"
    echo "=== Finished at: $(date --iso-8601=seconds) ==="
} >> "${LOGFILE}" 2>&1
