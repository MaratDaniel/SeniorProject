#!/usr/bin/env bash
# Disposable local PostgreSQL for development and tests, for machines without Docker.
# Listens on 127.0.0.1 only. Data lives in backend/.pgdata (git-ignored).
#   tools/devdb.sh start|stop|status|reset
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${ADAL_DEVDB_PORT:-54329}"
DATA=".pgdata"
TOOLS_PY="tools/.venv/bin/python"

if [ ! -x "$TOOLS_PY" ]; then
  echo "Missing $TOOLS_PY. Create it with:" >&2
  echo "  uv venv --python 3.12 tools/.venv && uv pip install --python tools/.venv/bin/python --require-hashes -r tools/devdb-requirements.txt" >&2
  exit 1
fi
BIN="$("$TOOLS_PY" -c 'import os, pgserver; print(os.path.join(os.path.dirname(pgserver.__file__), "pginstall", "bin"))')"

start() {
  if [ ! -d "$DATA" ]; then
    "$BIN/initdb" -D "$DATA" -U adal -A trust --encoding=UTF8 --locale=C >/dev/null
  fi
  if ! "$BIN/pg_ctl" -D "$DATA" status >/dev/null 2>&1; then
    "$BIN/pg_ctl" -D "$DATA" -l "$DATA/server.log" -w \
      -o "-c listen_addresses=127.0.0.1 -c port=$PORT -c unix_socket_directories=''" start >/dev/null
  fi
  for db in adal adal_test; do
    if ! "$BIN/psql" -h 127.0.0.1 -p "$PORT" -U adal -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1; then
      "$BIN/createdb" -h 127.0.0.1 -p "$PORT" -U adal "$db"
    fi
  done
  echo "PostgreSQL on 127.0.0.1:$PORT (databases: adal, adal_test)"
}

case "${1:-}" in
  start) start ;;
  stop) "$BIN/pg_ctl" -D "$DATA" -m fast -w stop ;;
  status) "$BIN/pg_ctl" -D "$DATA" status ;;
  reset) "$BIN/pg_ctl" -D "$DATA" -m fast -w stop 2>/dev/null || true; rm -rf "$DATA"; start ;;
  *) echo "usage: tools/devdb.sh start|stop|status|reset" >&2; exit 2 ;;
esac
