#!/bin/sh
set -eu

mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
find "${PROMETHEUS_MULTIPROC_DIR}" -maxdepth 1 -type f -delete

exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2 \
    --limit-concurrency 200 --backlog 512 --timeout-keep-alive 5 \
    --timeout-graceful-shutdown 30 --no-access-log
