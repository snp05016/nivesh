FROM python:3.10-slim

WORKDIR /app

# System deps for LightGBM, Torch, and Celery
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mluser && \
    chown -R mluser:mluser /app

USER mluser

CMD ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"]
