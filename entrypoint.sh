#!/bin/sh
# Wait for RabbitMQ to be reachable before starting uvicorn.
# This avoids the DNS / startup race where the Python container boots
# before RabbitMQ's hostname is resolvable in the compose network.

set -e

RABBIT_HOST="${RABBIT_HOST:-rabbitmq}"
RABBIT_PORT="${RABBIT_PORT:-5672}"

echo "[entrypoint] waiting for ${RABBIT_HOST}:${RABBIT_PORT}..."

# Use Python to check TCP connectivity (more portable than nc which may be missing)
until python -c "
import socket, os, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect((os.environ.get('RABBIT_HOST', 'rabbitmq'), int(os.environ.get('RABBIT_PORT', '5672'))))
    s.close()
except Exception as e:
    sys.exit(1)
sys.exit(0)
" > /dev/null 2>&1; do
    echo "[entrypoint] ${RABBIT_HOST}:${RABBIT_PORT} not ready yet, retrying..."
    sleep 2
done

echo "[entrypoint] ${RABBIT_HOST}:${RABBIT_PORT} is reachable, running migrations"

# Apply Alembic migrations before serving traffic. `alembic upgrade head`
# is idempotent — it will detect an up-to-date schema and exit 0.
alembic upgrade head

echo "[entrypoint] migrations applied, starting uvicorn"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
