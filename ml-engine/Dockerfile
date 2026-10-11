# ml-engine runs in its own container, so it keeps its own Python minor (3.12,
# chosen with the research pins) instead of the backend's /.python-version.
FROM python:3.12-slim

WORKDIR /app

# System deps for LightGBM, Torch, and Celery
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security (default USER when run without --user).
RUN useradd --create-home --shell /bin/bash mluser && \
    chown mluser:mluser /app

# requirements.lock: exact pins frozen from the running image (OPS-16);
# requirements.txt is only the fallback until that lock is committed.
COPY requirements.txt requirements.lock* ./
RUN if [ -f requirements.lock ]; then pip install --no-cache-dir -r requirements.lock; \
    else pip install --no-cache-dir -r requirements.txt; fi

COPY --chown=mluser:mluser . .

# config.py runs os.makedirs(/app/data, /app/cache) at import time, and
# .dockerignore keeps both out of the image. The deploy script runs the
# container as the host user (--user "$(id -u):$(id -g)"), whose uid need not
# match mluser's, so pre-create them world-writable (sticky) for any uid.
# Nothing else under /app is writable by a non-mluser uid.
RUN mkdir -p /app/data /app/cache && chmod 1777 /app/data /app/cache

# Research data (raw bhavcopies, curated panel, models, runs): a host volume
# mounted at /data by scripts/deploy_ml_microservice.sh.
ENV RESEARCH_DATA_DIR=/data

EXPOSE 8001

USER mluser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
