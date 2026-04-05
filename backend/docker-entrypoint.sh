#!/bin/sh
set -e

echo "Waiting for database at ${DB_HOST:-db}:${DB_PORT:-5432}..."
python - <<'PY'
import os
import socket
import time

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))
deadline = time.time() + int(os.getenv("DB_WAIT_TIMEOUT", "60"))

while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"Database {host}:{port} was not reachable before timeout")
PY

echo "Running Alembic migrations..."
alembic upgrade head

if [ "${RUN_SEED_DATA:-false}" = "true" ]; then
    echo "Seeding sample data..."
    python seed_data.py
fi

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
