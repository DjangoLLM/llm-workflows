# Agents test harness

## Commands

Local (includes live tests):

```bash
./tests/scripts/run_agents_tests.sh
```

CI and routine development runs are credential-free and exclude the `live`
marker:

```bash
./tests/scripts/run_agents_tests.sh --ci
```

Run the required live Codex acceptance test without Docker or other live
providers:

```bash
CODEX_LIVE_MODEL=gpt-6-astra ./tests/scripts/run_codex_live.sh -vv
```

The live test exercises `Agent.run`, `Agent.run_sync`, and `ManagedAgent` with
the real authenticated CLI. It validates a fixed nested Pydantic result,
managed JSON output and `SUCCEEDED` state, and temporary-file cleanup. This
test must pass for a Codex CLI release. A skipped test or mocked response is not
acceptance evidence.

## What the harness does

1. Creates an ephemeral Postgres container (`pgvector/pgvector:pg15`).
2. Mounts database files into a temporary host directory from `mktemp -d`.
3. Waits for database health and enables `vector` extension.
4. Exports `DATABASE_URL` for the agents test settings.
5. Runs pytest with coverage.
6. Enforces line and branch coverage gates (`90/80`).
7. Always tears down container/volume and removes temporary data directory.

## Live test prerequisites

The focused Codex test requires:

- The supported `codex` binary in `PATH`, already authenticated through its
  normal CLI login flow. The framework does not accept or store a Codex API
  key.
- `uv` in `PATH`. The runner creates an isolated environment, installs the
  package with its pinned driver revision, and uses an in-memory SQLite test
  database.
- An optional `CODEX_LIVE_MODEL` value. Set it to record an explicit model in
  delivery evidence. When unset, Codex uses its configured default model.

The broader live suite also requires:

- Docker with Compose support.
- `OPENAI_API_KEY` for the separate Pydantic AI live test.
- A reachable endpoint at `TEMPORAL_SERVER_URL` for the separate Temporal live
  test.

The Codex test runs from the repository working directory and uses a
180-second timeout.
Production calls can set `codex_working_dir` and `codex_timeout_seconds` in
`AgentConfig.extra_kwargs`; their defaults are the current directory and 300
seconds.

The runner requests the `read-only` Codex sandbox. This does not isolate the
process from local reads or tools supplied by trusted Codex configuration.
The framework does not pass its own tools or toolsets to the Codex process.

## Troubleshooting

- If Docker startup fails, verify Docker Desktop/daemon is running.
- If DB connection fails, ensure no local firewall/network policy blocks loopback ports.
- If Codex fails before inference, run `codex --version` and confirm the CLI is
  installed, supported, and authenticated.
- If the requested model is unavailable, unset `CODEX_LIVE_MODEL` to use the
  configured default or select a model available to the signed-in account.
- A timeout, nonzero exit, terminal failure event, missing response file, or
  invalid response schema is a hard live-test failure.
