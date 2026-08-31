"""End-to-end: Agent pi_worker backend driving the real MCP toolset.

This runs the full Python-side pi_worker path without mocks:

  1. Build `AgentConfig(execution_backend="pi_worker", toolsets=["echo"])`.
  2. Route through `ManagedAgent`, which picks up the pi-worker dispatch hook.
  3. Spawn the real `manage.py run_tools_mcp --toolset echo --transport stdio`
     subprocess via `PiMcpBridge`.
  4. Call the actual `EchoToolSet.echo` tool exposed by the feedback demo app.
  5. Persist the resulting `AgentRun` row and verify the stored output.

Run from the `examples/feedback_demo` directory:

    .venv/bin/python run_agent_pi_worker_e2e.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "feedback_demo.settings")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402

from agents.core.agent import Agent, AgentConfig, ManagedAgent  # noqa: E402
from agents.models import AgentRun, AgentRunStatus  # noqa: E402


def main() -> int:
    os.chdir(DEMO_DIR)

    # The demo uses SQLite and disables migrations for the reusable agents app.
    # Ensure the schema exists before the bridge subprocess starts.
    call_command("migrate", interactive=False, run_syncdb=True, verbosity=0)

    agent = Agent(
        config=AgentConfig(
            instructions="Use the echo tool and return its output.",
            execution_backend="pi_worker",
            toolsets=["echo"],
        )
    )

    managed = ManagedAgent(agent=agent, agent_label="pi-worker-e2e")
    output = managed.run_sync(input_payload={"text": "hello from pi-worker e2e"})

    run = AgentRun.objects.get(pk=managed.run_id)
    expected_output = {
        "name": "echo",
        "arguments": {"text": "hello from pi-worker e2e"},
        "output": {
            "echoed": "hello from pi-worker e2e",
            "char_count": len("hello from pi-worker e2e"),
        },
        "is_error": False,
        "error_message": None,
    }

    assert run.status == AgentRunStatus.SUCCEEDED, run.status
    assert run.output == expected_output, run.output
    assert output == expected_output, output

    print("pi-worker Agent e2e success.")
    print(f"run_id: {run.id}")
    print(f"output: {run.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
