et -uo pipefail

###############################################################################
# Resolve repository root
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

###############################################################################
# Configuration
###############################################################################

PROMPT_FILE="${PROMPT_FILE:-$REPO_DIR/.agent-runs/codex-issue-engine/PROMPT.md}"
LOG_DIR="${LOG_DIR:-$REPO_DIR/.agent-runs/codex-issue-engine/logs}"

# Restart Codex before Plus' 5 hour window.
RUN_SECONDS="${RUN_SECONDS:-17100}"     # 4h45m

# Wait before restarting.
SLEEP_SECONDS="${SLEEP_SECONDS:-120}"

###############################################################################
# CHANGE THIS IF YOUR CODEX COMMAND IS DIFFERENT
###############################################################################

CODEX_CMD="${CODEX_CMD:-codex exec --dangerously-bypass-approvals-and-sandbox}"

###############################################################################
# Setup
###############################################################################

mkdir -p "$LOG_DIR"

cd "$REPO_DIR" || {
    echo "Failed to locate repository."
    exit 1
}

###############################################################################
# Checks
###############################################################################

if ! command -v codex >/dev/null 2>&1; then
    echo "ERROR: codex CLI not installed."
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: GitHub CLI not installed."
    exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Prompt file not found:"
    echo "$PROMPT_FILE"
    exit 1
fi

###############################################################################
# Main Loop
###############################################################################

RUN=1

while true; do

    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    LOGFILE="$LOG_DIR/run_${RUN}_${TIMESTAMP}.log"

    echo ""
    echo "======================================================" | tee -a "$LOGFILE"
    echo "Run #$RUN" | tee -a "$LOGFILE"
    echo "$(date)" | tee -a "$LOGFILE"
    echo "======================================================" | tee -a "$LOGFILE"

    ###########################################################################
    # Update git metadata
    ###########################################################################

    git fetch --all --prune 2>&1 | tee -a "$LOGFILE"

    ###########################################################################
    # Run Codex
    ###########################################################################

    timeout "$RUN_SECONDS" \
        bash -lc "$CODEX_CMD \"\$(cat '$PROMPT_FILE')\"" \
        2>&1 | tee -a "$LOGFILE"

    EXIT_CODE=${PIPESTATUS[0]}

    echo "" | tee -a "$LOGFILE"
    echo "Finished with exit code: $EXIT_CODE" | tee -a "$LOGFILE"
    echo "$(date)" | tee -a "$LOGFILE"

    RUN=$((RUN+1))

    echo ""
    echo "Sleeping ${SLEEP_SECONDS}s before restarting..."
    sleep "$SLEEP_SECONDS"

done
