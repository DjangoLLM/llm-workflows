#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if ! command -v codex >/dev/null 2>&1; then
  printf "codex is required to run the Codex live acceptance test.\n" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  printf "uv is required to install and run the Codex live acceptance test.\n" >&2
  exit 1
fi

unset PYTHONPATH
export DJANGO_SETTINGS_MODULE="tests.live_settings"

printf "Running the real Codex typed acceptance test with a temporary SQLite database\n"
cd "$AGENTS_DIR"
uv run \
  --isolated \
  --no-project \
  --with-editable "$AGENTS_DIR" \
  --with pytest \
  --with pytest-django \
  python -m pytest \
  -c pytest.ini \
  -o 'addopts=-ra --strict-markers --strict-config --tb=short' \
  -m codex_live \
  tests/live/test_codex_live.py \
  "$@"

printf "Codex live acceptance passed.\n"
