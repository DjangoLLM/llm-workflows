# CODING-2058 acceptance evidence

Run date: 2026-09-21

## Package source and clean installation

`freedom-agents` declares this immutable dependency in `pyproject.toml` and
`uv.lock`:

```text
coding-agent-drivers @ git+https://github.com/charleeagni/django-agent.git@a9e1911dbe5ad4c53b659b80d995fb57339e0f0d#subdirectory=DjangoAgent/coding-agent-drivers
```

The driver commit was published on branch
`wt/CODIN-2056-typed-codex-inference`. A clean installation used these
commands from the `freedom-agents` checkout:

```bash
uv build --out-dir /tmp/coding2058-install-proof/dist
uv venv /tmp/coding2058-install-proof/venv
uv pip install \
  --python /tmp/coding2058-install-proof/venv/bin/python \
  /tmp/coding2058-install-proof/dist/freedom_agents-0.1.3-py3-none-any.whl
```

The fresh environment installed `freedom-agents==0.1.3` and
`coding-agent-drivers==0.1.0`. Its driver `direct_url.json` recorded repository
`https://github.com/charleeagni/django-agent.git`, commit
`a9e1911dbe5ad4c53b659b80d995fb57339e0f0d`, and subdirectory
`DjangoAgent/coding-agent-drivers`. Both imports resolved under the fresh
environment's `site-packages`; no sibling editable checkout was used.

## Live Codex inference

Environment facts:

- CLI: `codex-cli 0.155.1`
- Authentication check: `codex login status` reported `Logged in using ChatGPT`
- Explicit model: `gpt-6-astra`
- Driver: `coding-agent-drivers==0.1.0` at commit
  `a9e1911dbe5ad4c53b659b80d995fb57339e0f0d`

Executed command:

```bash
CODEX_LIVE_MODEL=gpt-6-astra ./tests/scripts/run_codex_live.sh -vv
```

Result: `1 passed` in 23.87 seconds. The test made three actual authenticated
CLI calls through `Agent.run`, `Agent.run_sync`, and `ManagedAgent.run_sync`.
The two direct calls returned the concrete `_LiveResult` model. The managed
call returned and persisted JSON, and its `AgentRun` reached `SUCCEEDED`.

The nonsensitive validated value was:

```json
{
  "marker": "codex-live-ok",
  "count": 7,
  "details": {
    "values": ["direct", "managed"],
    "note": null
  }
}
```

The test redirected Python temporary files to its pytest directory and found
no `freedom-agents-codex-*` directory after the calls. This checks cleanup of
the generated schema and final-response files.

## Regression results

Focused `freedom-agents` tests covered the schema builder, Codex runner,
direct calls, managed persistence, Temporal activity result shape, MCP cleanup,
and removal of the pi-worker path. Result: `98 passed` in 7.17 seconds.

The full deterministic suite then passed with live tests excluded:
`225 passed, 3 deselected` in 5.35 seconds. The deselected tests were the
explicit live checks.

The exact published driver commit passed its own deterministic suite:
`45 passed, 2 deselected` in 0.38 seconds. The two deselected tests were its
explicit live tests.

A repository search found no active `pi_worker`, `pi-worker`, `PiInference`, or
`piInference` implementation outside specifications. The only remaining match
is a negative unit-test case that asserts `pi_worker` is rejected as an
unsupported backend. This reconciles the #2042 removal without restoring that
backend.

No credentials, tokens, sensitive prompts, or raw model transcripts are stored
in this evidence.
