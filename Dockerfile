FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Application code
COPY api/ ./api/
COPY scripts/run_api.sh ./run_api.sh
RUN chmod +x ./run_api.sh

ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus


# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')" || exit 1

# Run with uvicorn
CMD ["./run_api.sh"]
