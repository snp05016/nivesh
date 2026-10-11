FROM python:3.10-slim

WORKDIR /app

# System deps for LightGBM, Torch, and Celery
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security. /app itself must be writable:
# config.py creates data/ and cache/ under it at import time.
RUN useradd --create-home --shell /bin/bash mluser && \
    chown mluser:mluser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=mluser:mluser . .

EXPOSE 8001

USER mluser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
