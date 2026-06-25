# ─────────────────────────────────────────────────────────────────────────────
# Nivesh Backend — Multi-stage Dockerfile
# Stage 1: builder  — installs Python deps into a venv
# Stage 2: runtime  — slim image, copies venv, exposes :8000
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps needed to compile some packages (psycopg2, bcrypt, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create isolated venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip first
RUN pip install --upgrade pip setuptools wheel

# Copy requirements and install — separate layer so cache reuse is maximal
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install tradingagents-core as an editable local package if present
COPY tradingagents-core ./tradingagents-core
RUN if [ -f tradingagents-core/setup.py ] || [ -f tradingagents-core/pyproject.toml ]; then \
        pip install --no-cache-dir -e ./tradingagents-core; \
    fi


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Minimal runtime system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd -m -u 1000 nivesh
USER nivesh

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --chown=nivesh:nivesh . .

# ── Environment — override at runtime via docker run -e / --env-file ─────────
# Credentials are NEVER baked into the image.
# Required runtime env vars (provide via .env or secret manager):
#   ANTHROPIC_API_KEY
#   DEEPSEEK_API_KEY
#   FIRECRAWL_API_KEY
#   YOUTUBE_API_KEY
#   JWT_SECRET
#   DATABASE_URL          (defaults to SQLite if absent)
#   ALLOWED_ORIGINS       (comma-separated CORS origins)

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# ── Liveness / readiness probe (used by Kubernetes / Docker health check) ────
# Fixes #88: Use /health/live (DB check) instead of unconditional /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/live || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Fixes #84: --workers 1 avoids in-memory state inconsistency across worker processes
# (admin_users, caches, analysis tracking). Increase when shared state (Redis) is added.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
