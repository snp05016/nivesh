FROM python:3.10-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libgomp1 \
    graphviz \
    curl \
    iputils-ping \
    dnsutils \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# Add non-root user rduser
RUN useradd -m -s /bin/bash rduser

# Set up static historic data mount point
RUN mkdir -p /data/static_historic && chown -R rduser:rduser /data/static_historic

# Install Python packages
# Install numpy and pandas first to satisfy potential setup dependencies for qlib
RUN pip install --no-cache-dir numpy pandas
RUN pip install --no-cache-dir qlib rdagent

# Declare mount point volume
VOLUME ["/data/static_historic"]

# Switch to non-root user
USER rduser
WORKDIR /home/rduser

# Default command to keep the container running for verification
CMD ["tail", "-f", "/dev/null"]
