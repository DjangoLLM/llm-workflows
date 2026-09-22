# Feedback pipeline demo

This Django project demonstrates a feedback workflow with Temporal and Codex.
It cleans text, calls an echo tool, and asks Codex for a typed feedback analysis.

## Run end to end on the host

Install the project dependencies in the repo virtual environment. The
`coding-agent-drivers` sibling checkout configured in `pyproject.toml` must exist.
The `temporal` and `codex` CLIs must be on PATH, and Codex must be signed in.

```bash
cd examples/feedback_demo
../../.venv/bin/python run_e2e.py
```

This starts a Temporal dev server, a worker, and the Django server. It submits
feedback through the HTTP form, waits for the workflow, and prints the analysis.
It exits with status 0 on success and tears down the processes afterward.

Set `CODEX_MODEL` to override the model configured in Codex. The analysis step
makes a real Codex call. Step activities retry at most three times.

## Run the services separately

The Compose file provides Temporal only. Run the worker on the host so it can
use the installed Codex CLI and its existing sign-in.

```bash
docker compose -f examples/feedback_demo/docker-compose.yml up -d
cd examples/feedback_demo
../../.venv/bin/python manage.py migrate --run-syncdb --noinput
../../.venv/bin/python manage.py run_temporal_worker
```

In another terminal, start the web server from the same directory:

```bash
../../.venv/bin/python manage.py runserver
```

Open the demo at http://localhost:8000 and Temporal at http://localhost:8233.
