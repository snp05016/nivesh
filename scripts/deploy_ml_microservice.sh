#!/usr/bin/env bash
# ===========================================================================
# ML Microservice & Backend Deployment Script (Milestone 3)
# ===========================================================================
set -euo pipefail

# Configurations
CONTAINER_NAME="ml-engine"
IMAGE_NAME="ml-engine"
PORT="8001"
BACKEND_PORT="8000"

# Dynamically determine project root relative to the script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Starting deployment of Nivesh ML Engine..."
echo "📂 Project root: ${PROJECT_ROOT}"

# 1. Verify Docker Availability & Permissions
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        DOCKER_CMD="docker"
    elif sudo docker info &> /dev/null; then
        DOCKER_CMD="sudo docker"
    else
        echo "❌ Error: Docker daemon is not running or accessible." >&2
        exit 1
    fi
else
    echo "❌ Error: Docker is not installed." >&2
    echo "To install Docker on Fedora, please run:"
    echo "  sudo dnf install -y dnf-plugins-core"
    echo "  sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo"
    echo "  sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
    echo "  sudo systemctl enable --now docker"
    echo "  sudo usermod -aG docker \$USER"
    exit 1
fi

echo "✅ Docker command verified: Using '${DOCKER_CMD}'"

# 2. Stop and remove existing container named ml-engine
if "${DOCKER_CMD}" ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "🛑 Stopping existing container: ${CONTAINER_NAME}..."
    "${DOCKER_CMD}" stop "${CONTAINER_NAME}" || true
    echo "🗑️ Removing existing container: ${CONTAINER_NAME}..."
    "${DOCKER_CMD}" rm "${CONTAINER_NAME}" || true
fi

# 3. Stop and remove any conflicting container using port 8001
CONFLICTING_CONTAINERS=$("${DOCKER_CMD}" ps -a --filter "publish=${PORT}" --format '{{.ID}}')
if [ -n "${CONFLICTING_CONTAINERS}" ]; then
    # shellcheck disable=SC2086
    for container in ${CONFLICTING_CONTAINERS}; do
        echo "🛑 Stopping conflicting container on port ${PORT}: ${container}..."
        "${DOCKER_CMD}" stop "${container}" || true
        echo "🗑️ Removing conflicting container on port ${PORT}: ${container}..."
        "${DOCKER_CMD}" rm "${container}" || true
    done
fi

# 4. Build the ML Engine Docker Image
echo "🔨 Building Docker image: ${IMAGE_NAME}:latest..."
"${DOCKER_CMD}" build -t "${IMAGE_NAME}:latest" -f "${PROJECT_ROOT}/ml-engine/Dockerfile" "${PROJECT_ROOT}/ml-engine"

# 5. Run the new container
echo "🚀 Starting new container ${CONTAINER_NAME} on port ${PORT}..."
"${DOCKER_CMD}" run -d \
    --name "${CONTAINER_NAME}" \
    -p "${PORT}:${PORT}" \
    --restart unless-stopped \
    "${IMAGE_NAME}:latest"

# 6. Verify health check
echo "⏳ Waiting for health check to pass..."
HEALTHY=false
for _ in {1..30}; do
    if RESPONSE=$(curl -s "http://localhost:${PORT}/health"); then
        # Check if the response contains status: ok or "status":"ok"
        if echo "${RESPONSE}" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
            echo "✅ ml-engine is healthy and running!"
            HEALTHY=true
            break
        fi
    fi
    sleep 1
done

if [ "${HEALTHY}" = false ]; then
    echo "❌ Error: ml-engine health check failed or timed out." >&2
    echo "📋 Showing last 20 lines of container logs:"
    "${DOCKER_CMD}" logs "${CONTAINER_NAME}" | tail -n 20
    exit 1
fi

# 7. Restart Nivesh Uvicorn Backend Processes
echo "🔄 Restarting main Nivesh Uvicorn processes manually (AGENTS.md §6.5)..."

echo "  Killing stale uvicorn/python main processes..."
pkill -f 'uvicorn' || true
pkill -f 'python.*main' || true
sleep 2

echo "  Starting backend server on port ${BACKEND_PORT}..."
cd "${PROJECT_ROOT}/backend"
nohup ../venv/bin/uvicorn main:app --host 0.0.0.0 --port "${BACKEND_PORT}" --reload > /tmp/uvicorn.log 2>&1 &

sleep 2
if pgrep -f 'uvicorn' > /dev/null; then
    echo "✅ Nivesh backend restarted successfully (PID: $(pgrep -f 'uvicorn' | tr '\n' ' '))"
else
    echo "❌ Error: Failed to restart Nivesh backend server. Check /tmp/uvicorn.log" >&2
    exit 1
fi

echo "🎉 Deployment successfully completed!"
