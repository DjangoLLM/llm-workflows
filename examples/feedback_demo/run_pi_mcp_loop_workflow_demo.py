"""End-to-end: PiMcpLoopWorkflow driving real MCP tool calls.

We stub the `piInference` activity in Python (with a canned tool-call
script) so this test doesn't need the TypeScript worker or LLM keys.
The MCP server, bridge activities, and workflow loop are all real:

  Workflow
    -> activity agents.mcp.list_pi_tools  (spawns real STDIO MCP server, lists `echo`)
    -> activity piInference (stub: emit a tool_call for `echo`)
    -> activity agents.mcp.call_pi_tool   (spawns real STDIO MCP server, runs `echo`)
    -> activity piInference (stub: emit final text, no tool_calls)
    -> return.

Prereqs: Temporal server on localhost:7233 (or TEMPORAL_SERVER_URL).
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "feedback_demo.settings")
os.environ.setdefault(
    "DATABASE_URL",
    "postgres://postgres:postgrespassword@127.0.0.1:5433/agents_unit_test",
)
sys.path.insert(0, str(DEMO_DIR))

import django  # noqa: E402

django.setup()

from temporalio import activity  # noqa: E402
from temporalio.client import Client  # noqa: E402
from temporalio.worker import UnsandboxedWorkflowRunner, Worker  # noqa: E402

from agents.core.temporal.mcp_pi_activities import (  # noqa: E402
    call_pi_tool_activity,
    list_pi_tools_activity,
)
from feedback.pi_mcp_workflow import (  # noqa: E402
    PiMcpLoopInput,
    PiMcpLoopWorkflow,
)


# Canned conversation: first turn picks `echo`, second turn answers.
_PI_SCRIPT = iter(
    [
        {
            "finalText": "",
            "toolCalls": [{"name": "echo", "arguments": {"text": "pi-mcp-loop"}}],
            "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
        },
        {
            "finalText": "Echo result confirmed.",
            "toolCalls": [],
            "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
        },
    ]
)


@activity.defn(name="piInference")
async def fake_pi_inference(input: dict) -> dict:
    """Stand-in for the TypeScript piInference activity."""

    print(f"[fake-pi] iteration messages={len(input['messages'])} tools={len(input.get('tools', []))}")
    return next(_PI_SCRIPT)


async def main() -> int:
    temporal_url = os.environ.get("TEMPORAL_SERVER_URL", "localhost:7233")
    task_queue = f"pi-mcp-loop-e2e-{uuid.uuid4().hex[:8]}"

    client = await Client.connect(temporal_url)

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[PiMcpLoopWorkflow],
        activities=[
            fake_pi_inference,
            list_pi_tools_activity,
            call_pi_tool_activity,
        ],
        workflow_runner=UnsandboxedWorkflowRunner(),
    )

    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    workflow_input = PiMcpLoopInput(
        provider="stub",
        model="stub",
        system_prompt="You can call tools.",
        user_message="Echo the phrase 'pi-mcp-loop'.",
        toolset_name="echo",
        mcp_cwd=str(DEMO_DIR),
        mcp_python_bin=python_bin,
        max_iterations=4,
        activity_timeout_seconds=30,
    )

    print(f"Running PiMcpLoopWorkflow on task_queue={task_queue}")

    worker_task = asyncio.create_task(worker.run())
    try:
        # PiInference must route to the same task_queue here since we're
        # registering the fake locally; override the workflow's default by
        # patching TS_ACTIVITY_QUEUE for this run.
        from feedback import pi_mcp_workflow

        pi_mcp_workflow.TS_ACTIVITY_QUEUE = task_queue

        result = await client.execute_workflow(
            PiMcpLoopWorkflow.run,
            workflow_input,
            id=f"pi-mcp-loop-e2e-{uuid.uuid4().hex[:8]}",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=120),
        )
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    print(f"\nWorkflow result:")
    print(f"  iterations:   {result.iterations}")
    print(f"  final_text:   {result.final_text!r}")
    print(f"  tool_results: {result.tool_results}")

    assert result.iterations == 2, result
    assert result.final_text == "Echo result confirmed.", result
    assert len(result.tool_results) == 1
    tool_result = result.tool_results[0]
    assert tool_result["is_error"] is False
    assert tool_result["output"] == {"echoed": "pi-mcp-loop", "char_count": 11}

    print("\nPASS — pi-agent loop drove the MCP server end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
