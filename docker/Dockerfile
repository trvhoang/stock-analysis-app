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
COPY app/requirements.txt .

# Combine both pip installs into one RUN layer — fewer layers = smaller image
# --no-compile skips .pyc generation at install time (done at runtime instead)
RUN pip install --no-cache-dir --no-compile -r requirements.txt \
    && pip install --no-cache-dir --no-compile \
       https://www.pandas-ta.dev/assets/zip/pandas_ta-0.4.71b0.tar.gz \
    && pip cache purge

# Copy application code LAST — preserves cache for all layers above
# when only app code changes, no reinstall triggered
COPY app/ .

# Performance: unbuffered logs + disable .pyc writes to disk
# PYTHONDONTWRITEBYTECODE saves disk from .pyc files in container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONOPTIMIZE=1

# Non-root user for security best practice
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run Streamlit app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]