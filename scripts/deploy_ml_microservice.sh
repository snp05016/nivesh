#!/usr/bin/env bash
# ===========================================================================
# ML Microservice Deployment Script (Milestone 3)
# Runs on the server. Builds the new image first, swaps the container, and
# rolls back to the previous image if the health check fails. It never stops
# or restarts the backend API.
# ===========================================================================
set -euo pipefail

# Configurations
CONTAINER_NAME="ml-engine"
IMAGE_NAME="ml-engine"
PORT="8001"
BACKEND_PORT="8000"
ML_MEMORY="${ML_MEMORY:-4g}"
ML_CPUS="${ML_CPUS:-3}"
# Research engine state (spec 2.7): a host directory only this user can read,
# mounted at /data, and an env file (mode 600) holding ML_ENGINE_API_KEY and
# RESEARCH_HTTP_CONTACT. The backend reads the same key from backend/.env.
RESEARCH_DATA_HOST_DIR="${HOME}/nivesh-data/research"
ML_ENV_FILE="${HOME}/nivesh-data/ml-engine.env"

# Dynamically determine project root relative to the script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🚀 Starting deployment of Nivesh ML Engine..."
echo "📂 Project root: ${PROJECT_ROOT}"

# 1. Verify Docker Availability & Permissions
if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        DOCKER_CMD=(docker)
    elif sudo -n docker info &> /dev/null; then
        DOCKER_CMD=(sudo -n docker)
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

echo "✅ Docker command verified: Using '${DOCKER_CMD[*]}'"

# Data directory and env file, before anything is built or stopped.
mkdir -p "${RESEARCH_DATA_HOST_DIR}" && chmod 700 "${RESEARCH_DATA_HOST_DIR}"
if [ ! -f "${ML_ENV_FILE}" ]; then
    echo "❌ Error: ${ML_ENV_FILE} is missing (needs ML_ENGINE_API_KEY and RESEARCH_HTTP_CONTACT, mode 600)." >&2
    exit 1
fi
chmod 600 "${ML_ENV_FILE}"

# AUTH-21: hand the shared secret from backend/.env to the container through a
# private env file (never on the command line, never echoed). The backend sends
# it as X-ML-Engine-Key. It is passed after ML_ENV_FILE so the engine always
# uses the backend's key; without it the key in ML_ENV_FILE applies.
ML_KEY_ENV_FILE="$(mktemp)"
trap 'rm -f "${ML_KEY_ENV_FILE}"' EXIT
chmod 600 "${ML_KEY_ENV_FILE}"
ML_KEY_LINE="$(grep -E '^ML_ENGINE_API_KEY=' "${PROJECT_ROOT}/backend/.env" 2>/dev/null | tail -n 1 || true)"
if [ -n "${ML_KEY_LINE#ML_ENGINE_API_KEY=}" ]; then
    printf '%s\n' "${ML_KEY_LINE}" | sed -E "s/^(ML_ENGINE_API_KEY=)[\"'](.*)[\"']\$/\1\2/" > "${ML_KEY_ENV_FILE}"
else
    echo "⚠️ WARN: ML_ENGINE_API_KEY not set in backend/.env; the backend cannot authenticate to ml-engine." >&2
fi

run_container() {
    # Runs as the deploying user (owner of the 700 data dir), loopback only.
    "${DOCKER_CMD[@]}" run -d \
        --name "${CONTAINER_NAME}" \
        --restart unless-stopped \
        --cpus="${ML_CPUS}" \
        --memory="${ML_MEMORY}" \
        --user "$(id -u):$(id -g)" \
        -p "127.0.0.1:${PORT}:${PORT}" \
        -v "${RESEARCH_DATA_HOST_DIR}:/data" \
        --env-file "${ML_ENV_FILE}" \
        --env-file "${ML_KEY_ENV_FILE}" \
        -e RESEARCH_DATA_DIR=/data \
        -e HOME=/data \
        "$1"
}

wait_healthy() {
    for _ in {1..30}; do
        if curl -fsS --max-time 2 "http://localhost:${PORT}/health" 2>/dev/null \
            | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# 2. Remember the image the running container uses, for rollback
if PREV_IMAGE_ID=$("${DOCKER_CMD[@]}" container inspect --format '{{.Image}}' "${CONTAINER_NAME}" 2>/dev/null); then
    "${DOCKER_CMD[@]}" tag "${PREV_IMAGE_ID}" "${IMAGE_NAME}:previous"
    echo "📌 Tagged current image as ${IMAGE_NAME}:previous for rollback"
fi

# 3. Build the new image BEFORE stopping anything: a failed build (set -e)
#    leaves the old container serving.
echo "🔨 Building Docker image: ${IMAGE_NAME}:latest..."
"${DOCKER_CMD[@]}" build -t "${IMAGE_NAME}:latest" -f "${PROJECT_ROOT}/ml-engine/Dockerfile" "${PROJECT_ROOT}/ml-engine"

# 4. Stop and remove existing container named ml-engine
if "${DOCKER_CMD[@]}" ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "🛑 Stopping existing container: ${CONTAINER_NAME}..."
    "${DOCKER_CMD[@]}" stop "${CONTAINER_NAME}" || true
    echo "🗑️ Removing existing container: ${CONTAINER_NAME}..."
    "${DOCKER_CMD[@]}" rm "${CONTAINER_NAME}" || true
fi

# 5. Stop and remove any conflicting container using port 8001
CONFLICTING_CONTAINERS=$("${DOCKER_CMD[@]}" ps -a --filter "publish=${PORT}" --format '{{.ID}}')
if [ -n "${CONFLICTING_CONTAINERS}" ]; then
    # shellcheck disable=SC2086
    for container in ${CONFLICTING_CONTAINERS}; do
        echo "🛑 Stopping conflicting container on port ${PORT}: ${container}..."
        "${DOCKER_CMD[@]}" stop "${container}" || true
        echo "🗑️ Removing conflicting container on port ${PORT}: ${container}..."
        "${DOCKER_CMD[@]}" rm "${container}" || true
    done
fi

# 6. Run the new container (loopback only: the backend reaches it on localhost)
#    and wait for its health check. A failed `docker run` (bad ML_CPUS/ML_MEMORY,
#    port held by a non-docker process) takes the same rollback path as a failed
#    health check, since the old container is already gone at this point.
echo "🚀 Starting new container ${CONTAINER_NAME} on 127.0.0.1:${PORT} (memory ${ML_MEMORY}, cpus ${ML_CPUS})..."
echo "⏳ Waiting for health check to pass..."
if ! run_container "${IMAGE_NAME}:latest" || ! wait_healthy; then
    echo "❌ Error: ml-engine start or health check failed." >&2
    echo "📋 Showing last 20 lines of container logs:"
    "${DOCKER_CMD[@]}" logs --tail 20 "${CONTAINER_NAME}" 2>&1 || true
    "${DOCKER_CMD[@]}" rm -f "${CONTAINER_NAME}" || true
    if "${DOCKER_CMD[@]}" image inspect "${IMAGE_NAME}:previous" > /dev/null 2>&1; then
        if run_container "${IMAGE_NAME}:previous" && wait_healthy; then
            echo "↩️ Rolled back to previous image (${IMAGE_NAME}:previous)." >&2
        else
            echo "❌ Rolled back to previous image, but it is not healthy either." >&2
        fi
    fi
    exit 1
fi
echo "✅ ml-engine is healthy and running!"

# The backend is deliberately not touched: it calls ml-engine over HTTP and
# keeps serving during the rollout. This is only an informational check.
if ! curl -fsS --max-time 5 "http://localhost:${BACKEND_PORT}/ping" > /dev/null 2>&1; then
    echo "⚠️ WARN: backend not responding on :${BACKEND_PORT} (not touched by this script)." >&2
fi

echo "🎉 Deployment successfully completed!"
