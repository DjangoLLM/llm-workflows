#!/usr/bin/env bash
set -euo pipefail

CI_MODE=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ci)
      CI_MODE=1
      shift
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        EXTRA_ARGS+=("$1")
        shift
      done
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$AGENTS_DIR/.." && pwd)"
COMPOSE_FILE="$AGENTS_DIR/tests/docker-compose.test.yml"
ARTIFACTS_DIR="$AGENTS_DIR/tests/artifacts"

mkdir -p "$ARTIFACTS_DIR"

POSTGRES_USER="postgres"
POSTGRES_PASSWORD="postgrespassword"
POSTGRES_DB="agents_test"
POSTGRES_PORT="$(python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
)"
POSTGRES_DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/agents-test-pgdata.XXXXXX")"
COMPOSE_PROJECT="agents-test-$(date +%s)-$RANDOM"

cleanup() {
  local exit_code=$?
  docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$POSTGRES_DATA_DIR" || true
  exit "$exit_code"
}

trap cleanup EXIT INT TERM

export POSTGRES_USER
export POSTGRES_PASSWORD
export POSTGRES_DB
export POSTGRES_PORT
export POSTGRES_DATA_DIR

export PYTHONPATH="$AGENTS_DIR${PYTHONPATH:+:$PYTHONPATH}"

printf "Starting ephemeral Postgres test container on port %s\n" "$POSTGRES_PORT"
docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" up -d --wait

printf "Enabling pgvector extension in %s\n" "$POSTGRES_DB"
docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" exec -T postgres_test \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"

export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"

PYTEST_CMD=(
  uv run
  --with .
  --with pytest
  --with pytest-django
  --with pytest-asyncio
  --with pytest-cov
  --with coverage[toml]
  --with dj-database-url
  --with psycopg2-binary
  python -m pytest
  -c "pytest.ini"
  "tests"
)

if [[ "$CI_MODE" -eq 1 ]]; then
  PYTEST_CMD+=(-m "not live")
fi

if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  PYTEST_CMD+=("${EXTRA_ARGS[@]}")
fi

printf "Running pytest (%s mode)\n" "$( [[ "$CI_MODE" -eq 1 ]] && echo ci || echo local )"
# Enter the actual project directory so uv uses the correct pyproject.toml
cd "$AGENTS_DIR"

"${PYTEST_CMD[@]}"

uv run python tests/verify_coverage.py \
  tests/artifacts/coverage.json \
  --line 90 \
  --branch 80

printf "Agents test harness completed successfully.\n"
