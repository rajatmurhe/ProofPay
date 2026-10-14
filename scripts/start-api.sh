#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
.venv/bin/alembic -c services/api/alembic.ini upgrade head
exec .venv/bin/uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8017 --no-access-log
