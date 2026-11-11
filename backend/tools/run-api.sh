#!/usr/bin/env bash
# Start the API for local development. Reads backend/.env (python -m app.cli init-env).
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port "${PORT:-8000}" \
  --reload --reload-dir app \
  --ws-max-size 65536
