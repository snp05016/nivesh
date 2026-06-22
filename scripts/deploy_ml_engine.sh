#!/usr/bin/env bash
# =============================================================================
# deploy_ml_engine.sh — Production Deployment: Nivesh ML Engine
# =============================================================================
# Deploys the ml-engine Docker container and restarts the Uvicorn backend
# on the remote server saumyapatel@192.168.1.122 non-interactively.
#
# Usage:
#   chmod +x scripts/deploy_ml_engine.sh
#   ./scripts/deploy_ml_engine.sh
#
# Prerequisites (local machine):
#   • SSH key-based auth configured for saumyapatel@192.168.1.122
#   • Git remote 'origin' points to the canonical repository
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REMOTE_USER="saumyapatel"
REMOTE_HOST="192.168.1.122"
REMOTE="$REMOTE_USER@$REMOTE_HOST"
REMOTE_PROJECT="/home/$REMOTE_USER/Desktop/nivesh"
REMOTE_BACKEND="$REMOTE_PROJECT/backend"
REMOTE_VENV="$REMOTE_PROJECT/venv"

IMAGE_NAME="ml-engine"
CONTAINER_NAME="ml-engine"
ML_PORT="8001"
BACKEND_PORT="8000"

SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no)

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
# Step 2 — Pull latest code on the remote server
# ---------------------------------------------------------------------------
log_info "Pulling latest code on $REMOTE ..."
remote "
    set -euo pipefail
    cd '$REMOTE_PROJECT'
    git fetch --all
    git pull
"
log_info "Code updated."

# ---------------------------------------------------------------------------
# Step 3 — Kill stale uvicorn / python main processes (AGENTS.md §6.5)
# ---------------------------------------------------------------------------
log_info "Killing stale uvicorn and python-main processes on $REMOTE ..."
remote "
    pkill -f 'uvicorn' || true
    pkill -f 'python.*main' || true
    sleep 2
    echo 'Stale processes cleared.'
"

# ---------------------------------------------------------------------------
# Step 4 — Stop and remove any existing ml-engine container
# ---------------------------------------------------------------------------
log_info "Removing any existing '$CONTAINER_NAME' container on $REMOTE ..."
remote "
    set -euo pipefail
    if docker ps -a --format '{{.Names}}' | grep -Eq '^${CONTAINER_NAME}$'; then
        docker stop '$CONTAINER_NAME'  || true
        docker rm   '$CONTAINER_NAME'  || true
        echo 'Old container removed.'
    else
        echo 'No existing container found — skipping removal.'
    fi
"

# Stop any container already occupying port 8001
remote "
    CONFLICT=\$(docker ps -a --filter 'publish=$ML_PORT' --format '{{.ID}}')
    if [ -n \"\$CONFLICT\" ]; then
        echo \"Stopping conflicting container on port $ML_PORT: \$CONFLICT\"
        docker stop \"\$CONFLICT\" || true
        docker rm   \"\$CONFLICT\" || true
    fi
"

# ---------------------------------------------------------------------------
# Step 5 — Build the ml-engine Docker image on the remote server
# ---------------------------------------------------------------------------
log_info "Building Docker image '$IMAGE_NAME:latest' on $REMOTE ..."
remote "
    set -euo pipefail
    cd '$REMOTE_PROJECT'
    docker build \
        -t '$IMAGE_NAME:latest' \
        -f ml-engine/Dockerfile \
        ml-engine/
"
log_info "Image built successfully."

# ---------------------------------------------------------------------------
# Step 6 — Run the ml-engine container (detached, restart=unless-stopped)
# ---------------------------------------------------------------------------
log_info "Starting '$CONTAINER_NAME' on port $ML_PORT ..."
remote "
    set -euo pipefail
    docker run -d \
        --name '$CONTAINER_NAME' \
        -p '$ML_PORT:$ML_PORT' \
        --restart unless-stopped \
        '$IMAGE_NAME:latest'
"
log_info "Container '$CONTAINER_NAME' started."

# ---------------------------------------------------------------------------
# Step 7 — Health-check the ml-engine container (up to 30 s)
# ---------------------------------------------------------------------------
log_info "Waiting for ml-engine health check on $REMOTE:$ML_PORT ..."
ML_HEALTHY=false
for i in $(seq 1 30); do
    RESPONSE=$(remote "curl -s http://localhost:$ML_PORT/health || true")
    if echo "$RESPONSE" | grep -q '"status"'; then
        ML_HEALTHY=true
        log_info "ml-engine is healthy (attempt $i/30)."
        break
    fi
    log_info "  attempt $i/30 — not ready yet, retrying in 1 s ..."
    sleep 1
done

if [ "$ML_HEALTHY" = false ]; then
    log_error "ml-engine health check failed after 30 s. Showing container logs:"
    remote "docker logs --tail 30 '$CONTAINER_NAME'" || true
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 8 — Restart Uvicorn backend in background (AGENTS.md §6.5)
# ---------------------------------------------------------------------------
log_info "Restarting Uvicorn backend on $REMOTE:$BACKEND_PORT ..."
remote "
    set -euo pipefail
    cd '$REMOTE_BACKEND'
    nohup '$REMOTE_VENV/bin/uvicorn' main:app \
        --host 0.0.0.0 \
        --port '$BACKEND_PORT' \
        --reload \
        > /tmp/uvicorn.log 2>&1 &
    echo \"Uvicorn started (PID: \$!)\"
"

# Brief pause then confirm uvicorn is alive
sleep 3
if remote "pgrep -f uvicorn > /dev/null 2>&1"; then
    log_info "Uvicorn backend running on $REMOTE:$BACKEND_PORT."
else
    log_warn "Uvicorn may not have started. Check /tmp/uvicorn.log on $REMOTE."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log_info "============================================================"
log_info " Deployment complete!"
log_info "  ML engine  → http://$REMOTE_HOST:$ML_PORT"
log_info "  Backend    → http://$REMOTE_HOST:$BACKEND_PORT"
log_info "  Uvicorn log: ssh $REMOTE 'tail -f /tmp/uvicorn.log'"
log_info "============================================================"
