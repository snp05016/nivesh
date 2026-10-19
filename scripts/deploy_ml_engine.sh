#!/usr/bin/env bash
# =============================================================================
# deploy_ml_engine.sh — Production Deployment: Nivesh ML Engine
# =============================================================================
# Deploys the ml-engine Docker container on the remote server
# saumyapatel@192.168.1.122 non-interactively. The server checkout is
# fast-forwarded to exactly DEPLOY_SHA (default: local HEAD, which must already
# be pushed to origin), then scripts/deploy_ml_microservice.sh runs there:
# it builds ml-engine:<short sha>, proves it as a candidate container on
# 127.0.0.1:8011 (ready, model_integrity_ok, model_version from
# ml-engine/models/MANIFEST.json or "unregistered"), then swaps the container
# and rolls back on a failed readiness check. The backend API is never stopped
# or restarted.
#
# Usage:
#   chmod +x scripts/deploy_ml_engine.sh
#   ./scripts/deploy_ml_engine.sh
#   DEPLOY_SHA=<commit> ML_MEMORY=4g ML_CPUS=3 ./scripts/deploy_ml_engine.sh
#
# Container (research engine, spec 2.7). deploy_ml_microservice.sh starts it as
#   docker run -d --name ml-engine --restart unless-stopped --cpus=3 --memory=4g \
#     --user "$(id -u):$(id -g)" -p 127.0.0.1:8001:8001 \
#     -v ~/nivesh-data/research:/data --env-file ~/nivesh-data/ml-engine.env \
#     -e RESEARCH_DATA_DIR=/data -e HOME=/data ml-engine:<short sha>
# ~/nivesh-data/research is mode 700. ~/nivesh-data/ml-engine.env is mode 600
# and holds ML_ENGINE_API_KEY and RESEARCH_HTTP_CONTACT (create it once by hand
# on the server; never commit it). The backend reads the same key from backend/.env.
#
# Prerequisites (local machine):
#   • SSH key-based auth configured for saumyapatel@192.168.1.122
#   • Git remote 'origin' points to the canonical repository
#   • The server's host key in ~/.ssh/known_hosts has been verified once
#     (StrictHostKeyChecking=accept-new refuses a changed key)
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REMOTE_USER="saumyapatel"
REMOTE_HOST="192.168.1.122"
REMOTE="$REMOTE_USER@$REMOTE_HOST"
REMOTE_PROJECT="/home/$REMOTE_USER/Desktop/nivesh"
DEPLOY_SHA="${DEPLOY_SHA:-$(git rev-parse HEAD)}"
ML_MEMORY="${ML_MEMORY:-4g}"
ML_CPUS="${ML_CPUS:-3}"

ML_PORT="8001"
BACKEND_PORT="8000"

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

# ---------------------------------------------------------------------------
# Helper — run a command on the remote server non-interactively
# ---------------------------------------------------------------------------
remote() {
    # shellcheck disable=SC2029  # "$@" expansion on client side is intentional:
    # callers pass literal shell strings meant to be interpreted by the remote shell.
    ssh "${SSH_OPTS[@]}" "$REMOTE" "$@"
}

# ---------------------------------------------------------------------------
# Helper — print coloured status lines (gracefully degrade if no tty)
# ---------------------------------------------------------------------------
log_info()    { printf '\033[0;32m[INFO]\033[0m  %s\n' "$*"; }
log_warn()    { printf '\033[0;33m[WARN]\033[0m  %s\n' "$*"; }
log_error()   { printf '\033[0;31m[ERROR]\033[0m %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# Pre-flight — the commit to deploy must exist on origin
# ---------------------------------------------------------------------------
DEPLOY_SHA="$(git rev-parse --verify "${DEPLOY_SHA}^{commit}")"
git fetch origin --quiet
if [ -z "$(git branch -r --contains "$DEPLOY_SHA")" ]; then
    log_error "$DEPLOY_SHA is not on any origin branch; push it first."
    exit 1
fi
log_info "Deploying commit $DEPLOY_SHA"

# ---------------------------------------------------------------------------
# Step 0 — Verify SSH connectivity
# ---------------------------------------------------------------------------
log_info "Verifying SSH connectivity to $REMOTE ..."
if ! remote "exit 0"; then
    log_error "Cannot reach $REMOTE via SSH. Check network, key auth, and known_hosts."
    exit 1
fi
log_info "SSH connection OK."

# ---------------------------------------------------------------------------
# Step 1 — Ensure Docker is installed on the remote server
# ---------------------------------------------------------------------------
log_info "Checking Docker availability on $REMOTE ..."
if ! remote "command -v docker > /dev/null 2>&1"; then
    log_warn "Docker not found on $REMOTE. Installing via apt-get ..."
    remote "
        set -euo pipefail
        export DEBIAN_FRONTEND=noninteractive
        sudo apt-get update -qq
        sudo apt-get install -y --no-install-recommends \
            ca-certificates \
            curl \
            gnupg \
            lsb-release
        sudo install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        sudo chmod a+r /etc/apt/keyrings/docker.gpg
        echo \
            \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
            https://download.docker.com/linux/ubuntu \
            \$(. /etc/os-release && echo \"\$VERSION_CODENAME\") stable\" \
            | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update -qq
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
            docker-buildx-plugin docker-compose-plugin
        sudo systemctl enable --now docker
        sudo usermod -aG docker \"\$USER\"
        newgrp docker || true
    "
    log_info "Docker installed on $REMOTE."
else
    log_info "Docker already installed on $REMOTE."
fi

# ---------------------------------------------------------------------------
# Step 2 — Fast-forward the server checkout to exactly DEPLOY_SHA
# ---------------------------------------------------------------------------
# --ff-only plus the SHA check aborts on a diverged or wrong checkout instead
# of deploying something else.
log_info "Updating code on $REMOTE to $DEPLOY_SHA ..."
remote "
    set -euo pipefail
    cd '$REMOTE_PROJECT'
    git fetch origin
    git merge --ff-only '$DEPLOY_SHA'
    test \"\$(git rev-parse HEAD)\" = '$DEPLOY_SHA' || { echo 'server HEAD != $DEPLOY_SHA (older commit or diverged checkout; only descendants of the server HEAD can be deployed)' >&2; exit 1; }
"
log_info "Code updated to $DEPLOY_SHA."

# ---------------------------------------------------------------------------
# Step 3 — Research data directory (700) and env file (600), before docker run
# ---------------------------------------------------------------------------
log_info "Preparing ~/nivesh-data on $REMOTE ..."
if ! remote "
    set -euo pipefail
    mkdir -p ~/nivesh-data/research && chmod 700 ~/nivesh-data/research
    test -f ~/nivesh-data/ml-engine.env
    chmod 600 ~/nivesh-data/ml-engine.env
"; then
    log_error "~/nivesh-data/ml-engine.env is missing on $REMOTE (ML_ENGINE_API_KEY, RESEARCH_HTTP_CONTACT; mode 600)."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 4 — Build, swap and health-check the ml-engine container on the server
# ---------------------------------------------------------------------------
log_info "Running deploy_ml_microservice.sh on $REMOTE ..."
remote "ML_MEMORY='$ML_MEMORY' ML_CPUS='$ML_CPUS' bash '$REMOTE_PROJECT/scripts/deploy_ml_microservice.sh'"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log_info "============================================================"
log_info " Deployment complete!"
log_info "  Commit     → $DEPLOY_SHA"
log_info "  ML engine  → http://127.0.0.1:$ML_PORT (loopback on $REMOTE_HOST)"
log_info "  Backend    → http://127.0.0.1:$BACKEND_PORT (loopback on $REMOTE_HOST, not restarted)"
log_info "============================================================"
