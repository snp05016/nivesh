#!/usr/bin/env bash
# ===========================================================================
# ML Microservice Deployment Script (Milestone 3)
# Runs on the server. Builds ml-engine:<git sha> while the old container keeps
# serving, proves it as ml-engine-candidate on 127.0.0.1:8011 (/ready with
# model_integrity_ok and the MANIFEST.json model version), then swaps the
# container and rolls back to the previous image if readiness fails. It never
# stops or restarts the backend API.
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

# ML-07: every image is tagged with the commit it was built from, and the
# container must report the model version recorded in models/MANIFEST.json
# ("unregistered" when there is none) with model_integrity_ok before it serves.
DEPLOY_SHA="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)"
NEW_IMAGE="${IMAGE_NAME}:${DEPLOY_SHA}"
MANIFEST="${PROJECT_ROOT}/ml-engine/models/MANIFEST.json"
EXPECTED_VERSION="unregistered"
if [ -f "${MANIFEST}" ]; then
    EXPECTED_VERSION="$(sed -n 's/^ *"model_version": *"\([^"]*\)".*/\1/p' "${MANIFEST}" | head -n 1)"
fi
CANDIDATE_NAME="${CONTAINER_NAME}-candidate"
CANDIDATE_PORT="8011"
PREVIOUS_FILE="${PROJECT_ROOT}/.ml-engine.previous"
echo "📦 Image ${NEW_IMAGE}, expected model version: ${EXPECTED_VERSION}"

run_container() {
    # $1 container name, $2 host port, $3 image, then extra docker run flags.
    # Runs as the deploying user (owner of the 700 data dir), loopback only.
    local name="$1" host_port="$2" image="$3"
    shift 3
    "${DOCKER_CMD[@]}" run -d \
        --name "${name}" \
        "$@" \
        --cpus="${ML_CPUS}" \
        --memory="${ML_MEMORY}" \
        --user "$(id -u):$(id -g)" \
        -p "127.0.0.1:${host_port}:${PORT}" \
        -v "${RESEARCH_DATA_HOST_DIR}:/data" \
        --env-file "${ML_ENV_FILE}" \
        --env-file "${ML_KEY_ENV_FILE}" \
        -e RESEARCH_DATA_DIR=/data \
        -e HOME=/data \
        "${image}"
}

# Readiness, not liveness: /ready is 503 unless the booster loaded and matched
# its manifest (ML-24, ML-07). With $2 set, the reported model_version must
# equal it. /ready is JSON with compact separators (Starlette JSONResponse).
wait_ready() {
    local port="$1" expected="${2:-}" body
    for _ in {1..60}; do
        if body="$(curl -fsS --max-time 2 "http://127.0.0.1:${port}/ready" 2>/dev/null)" \
            && grep -qF '"model_integrity_ok":true' <<< "${body}" \
            && { [ -z "${expected}" ] || grep -qF "\"model_version\":\"${expected}\"" <<< "${body}"; }; then
            return 0
        fi
        sleep 1
    done
    echo "Last /ready response on :${port}: ${body:-none}" >&2
    return 1
}

# 2. Build the new image while the old container keeps serving: a failed build
#    (set -e) changes nothing.
echo "🔨 Building Docker image: ${NEW_IMAGE}..."
"${DOCKER_CMD[@]}" build -t "${NEW_IMAGE}" -f "${PROJECT_ROOT}/ml-engine/Dockerfile" "${PROJECT_ROOT}/ml-engine"

# 3. Prove the new image next to the old one on 127.0.0.1:${CANDIDATE_PORT}.
"${DOCKER_CMD[@]}" rm -f "${CANDIDATE_NAME}" > /dev/null 2>&1 || true
echo "🧪 Starting ${CANDIDATE_NAME} on 127.0.0.1:${CANDIDATE_PORT}..."
if ! run_container "${CANDIDATE_NAME}" "${CANDIDATE_PORT}" "${NEW_IMAGE}" \
    || ! wait_ready "${CANDIDATE_PORT}" "${EXPECTED_VERSION}"; then
    echo "❌ Error: ${NEW_IMAGE} did not become ready with model ${EXPECTED_VERSION}; the running ml-engine is untouched." >&2
    "${DOCKER_CMD[@]}" logs --tail 40 "${CANDIDATE_NAME}" 2>&1 || true
    "${DOCKER_CMD[@]}" rm -f "${CANDIDATE_NAME}" > /dev/null 2>&1 || true
    exit 1
fi
"${DOCKER_CMD[@]}" rm -f "${CANDIDATE_NAME}" > /dev/null
echo "✅ ${NEW_IMAGE} passed readiness as a candidate."

# 4. Remember the image the running container uses, for rollback
if PREV_IMAGE_ID=$("${DOCKER_CMD[@]}" container inspect --format '{{.Image}}' "${CONTAINER_NAME}" 2>/dev/null); then
    "${DOCKER_CMD[@]}" tag "${PREV_IMAGE_ID}" "${IMAGE_NAME}:previous"
    printf '%s\n' "${PREV_IMAGE_ID}" > "${PREVIOUS_FILE}"
    echo "📌 Previous image ${PREV_IMAGE_ID} tagged ${IMAGE_NAME}:previous and recorded in ${PREVIOUS_FILE}"
fi

# 5. Stop and remove the existing ml-engine container and anything else on port 8001
if "${DOCKER_CMD[@]}" ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "🛑 Replacing existing container: ${CONTAINER_NAME}..."
    "${DOCKER_CMD[@]}" stop "${CONTAINER_NAME}" || true
    "${DOCKER_CMD[@]}" rm "${CONTAINER_NAME}" || true
fi
CONFLICTING_CONTAINERS=$("${DOCKER_CMD[@]}" ps -a --filter "publish=${PORT}" --format '{{.ID}}')
if [ -n "${CONFLICTING_CONTAINERS}" ]; then
    # shellcheck disable=SC2086
    for container in ${CONFLICTING_CONTAINERS}; do
        echo "🛑 Removing conflicting container on port ${PORT}: ${container}..."
        "${DOCKER_CMD[@]}" stop "${container}" || true
        "${DOCKER_CMD[@]}" rm "${container}" || true
    done
fi

# 6. Run the new image as ml-engine and re-check readiness. A failed start
#    takes the rollback path, since the old container is already gone here.
echo "🚀 Starting ${CONTAINER_NAME} from ${NEW_IMAGE} on 127.0.0.1:${PORT} (memory ${ML_MEMORY}, cpus ${ML_CPUS})..."
if ! run_container "${CONTAINER_NAME}" "${PORT}" "${NEW_IMAGE}" --restart unless-stopped \
    || ! wait_ready "${PORT}" "${EXPECTED_VERSION}"; then
    echo "❌ Error: ml-engine start or readiness check failed." >&2
    "${DOCKER_CMD[@]}" logs --tail 20 "${CONTAINER_NAME}" 2>&1 || true
    "${DOCKER_CMD[@]}" rm -f "${CONTAINER_NAME}" || true
    if "${DOCKER_CMD[@]}" image inspect "${IMAGE_NAME}:previous" > /dev/null 2>&1; then
        if run_container "${CONTAINER_NAME}" "${PORT}" "${IMAGE_NAME}:previous" --restart unless-stopped \
            && wait_ready "${PORT}"; then
            echo "↩️ Rolled back to previous image (${IMAGE_NAME}:previous)." >&2
        else
            echo "❌ Rolled back to previous image, but it is not ready either." >&2
        fi
    fi
    exit 1
fi
echo "✅ ml-engine ${NEW_IMAGE} is ready (model ${EXPECTED_VERSION})."

# The backend is deliberately not touched: it calls ml-engine over HTTP and
# keeps serving during the rollout. This is only an informational check.
if ! curl -fsS --max-time 5 "http://localhost:${BACKEND_PORT}/ping" > /dev/null 2>&1; then
    echo "⚠️ WARN: backend not responding on :${BACKEND_PORT} (not touched by this script)." >&2
fi

if [ -s "${PREVIOUS_FILE}" ]; then
    # ML_ENV_FILE also holds ML_ENGINE_API_KEY; it must match backend/.env.
    echo "↩️ Rollback command:"
    echo "  ${DOCKER_CMD[*]} rm -f ${CONTAINER_NAME} && ${DOCKER_CMD[*]} run -d --name ${CONTAINER_NAME} --restart unless-stopped --cpus=${ML_CPUS} --memory=${ML_MEMORY} --user $(id -u):$(id -g) -p 127.0.0.1:${PORT}:${PORT} -v ${RESEARCH_DATA_HOST_DIR}:/data --env-file ${ML_ENV_FILE} -e RESEARCH_DATA_DIR=/data -e HOME=/data $(cat "${PREVIOUS_FILE}")"
fi
echo "🎉 Deployment successfully completed!"
