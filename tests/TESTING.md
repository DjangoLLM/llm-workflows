# Agents Test Harness

## Commands

Local (includes live tests):

```bash
PYTHONPATH=/Users/karthik/Desktop/merge_conflicts/freedom /Users/karthik/Desktop/merge_conflicts/freedom/agents/tests/scripts/run_agents_tests.sh
```

CI (mocked-only, excludes `live` marker):

```bash
PYTHONPATH=/Users/karthik/Desktop/merge_conflicts/freedom /Users/karthik/Desktop/merge_conflicts/freedom/agents/tests/scripts/run_agents_tests.sh --ci
```

## What The Harness Does

1. Creates an ephemeral Postgres container (`pgvector/pgvector:pg15`).
2. Mounts database files into a temporary host directory from `mktemp -d`.
3. Waits for database health and enables `vector` extension.
4. Exports `DATABASE_URL` for the agents test settings.
5. Runs pytest with coverage.
6. Enforces line and branch coverage gates (`90/80`).
7. Always tears down container/volume and removes temporary data directory.

## Live Test Prerequisites

Live tests are strict and fail hard when prerequisites are missing:

- `codex` and `gemini` binaries in `PATH`.
- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CODEX_API_KEY` set.
- Reachable Temporal endpoint from `TEMPORAL_SERVER_URL`.

## Troubleshooting

- If Docker startup fails, verify Docker Desktop/daemon is running.
- If DB connection fails, ensure no local firewall/network policy blocks loopback ports.
- If live tests fail immediately, check missing prerequisite names in the failure message.
