# Use slim variant with pinned patch version for reproducibility
FROM python:3.12.9-slim AS builder

WORKDIR /app

# Install system dependencies
# - No recommends = skip suggested packages
# - Clean apt cache in same layer to minimize layer size
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy ONLY requirements first — Docker cache skips reinstall
# if requirements.txt hasn't changed (fastest build optimization)
COPY requirements.txt .

# Install with Asian mirror fallback + aggressive retry for Vietnam network
# Try Aliyun mirror first (fast in Asia), fallback to default PyPI if it fails
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    --default-timeout=300 \
    --retries=10 \
    --no-compile \
    -r requirements.txt || \
    pip install --no-cache-dir \
    --default-timeout=300 \
    --retries=10 \
    --no-compile \
    -r requirements.txt

# Install pandas-ta separately with extended timeout and retry
# This URL is often slow, so we give it extra resilience
RUN pip install --no-cache-dir \
    --default-timeout=300 \
    --retries=15 \
    --no-compile \
    https://www.pandas-ta.dev/assets/zip/pandas_ta-0.4.71b0.tar.gz || \
    (echo "pandas-ta download failed, retrying..." && sleep 5 && \
     pip install --no-cache-dir \
     --default-timeout=300 \
     --retries=15 \
     --no-compile \
     https://www.pandas-ta.dev/assets/zip/pandas_ta-0.4.71b0.tar.gz)

# Purge pip cache to reduce final image size
RUN pip cache purge

# Multi-stage build: production stage
FROM python:3.12.9-slim

WORKDIR /app

# Install only runtime dependencies (no gcc needed in production).
# Added curl to support the healthcheck command used in docker-compose.yml.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy installed Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ .

# Performance: unbuffered logs + disable .pyc writes to disk
# PYTHONDONTWRITEBYTECODE saves disk from .pyc files in container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=1

# Non-root user for security best practice
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check for container orchestration
# Switched to curl to avoid the overhead of starting a Python interpreter for health checks.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Expose Streamlit default port
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]