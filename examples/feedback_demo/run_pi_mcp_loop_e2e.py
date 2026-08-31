"""End-to-end: Agent(pi_worker) driving pydantic_ai with PiWorkerModel.

The agent loop is owned by pydantic_ai. Inference round-trips through a
Temporal workflow (`PiInferenceTurnWorkflow`) which dispatches to the
TypeScript `piInference` activity. Here we register a Python fake of
`piInference` with a 2-turn script so the test does not need the TS
worker or any LLM keys.

Pipeline of one run:
  pydantic_ai.Agent.run
    -> PiWorkerModel.request (turn 1: client.execute_workflow)
    -> PiInferenceTurnWorkflow -> fake piInference (returns echo tool_call)
    -> pydantic_ai invokes the registry-backed `echo` tool in-process
    -> PiWorkerModel.request (turn 2: client.execute_workflow)
    -> PiInferenceTurnWorkflow -> fake piInference (returns final_result tool call)
    -> pydantic_ai parses + validates the structured output
    -> agent_run.output is an EchoSummary instance.

Prereqs: Temporal server on localhost:7233 (or TEMPORAL_SERVER_URL).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
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

from pydantic import BaseModel  # noqa: E402
from temporalio import activity  # noqa: E402
from temporalio.client import Client  # noqa: E402
from temporalio.worker import UnsandboxedWorkflowRunner, Worker  # noqa: E402

from agents.core.agent import Agent, AgentConfig  # noqa: E402
from agents.core.temporal.workflows import PiInferenceTurnWorkflow  # noqa: E402


class EchoSummary(BaseModel):
    summary: str


_PI_SCRIPT: list[dict] = [
    {
        "finalText": "",
        "toolCalls": [
            {
                "name": "echo",
                "arguments": {"text": "pi-mcp-loop"},
                "id": "call-1",
            }
        ],
        "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
    },
    {
        "finalText": "",
        "toolCalls": [
            {
                "name": "final_result",
                "arguments": {"summary": "echo confirmed"},
                "id": "call-2",
            }
        ],
        "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
    },
]

_PI_CALL_INDEX = {"i": 0}


@activity.defn(name="piInference")
async def fake_pi_inference(payload: dict) -> dict:
    idx = _PI_CALL_INDEX["i"]
    _PI_CALL_INDEX["i"] = idx + 1
    print(
        f"[fake-pi turn={idx}] messages={len(payload.get('messages', []))} "
        f"tools={[t['name'] for t in payload.get('tools', [])]} "
        f"outputObject={'yes' if payload.get('outputObject') else 'no'}"
    )
    return _PI_SCRIPT[idx]


async def main() -> int:
    temporal_url = os.environ.get("TEMPORAL_SERVER_URL", "localhost:7233")
    host_queue = f"agents-pi-e2e-{uuid.uuid4().hex[:8]}"
    pi_queue = f"pi-inference-e2e-{uuid.uuid4().hex[:8]}"

    # Re-route the workflow to dispatch the inner activity on our local
    # fake queue, since we are not connecting to the real TS worker.
    from agents.core.temporal import workflows as core_workflows

    core_workflows.PI_INFERENCE_TASK_QUEUE = pi_queue

    client = await Client.connect(temporal_url)

    host_worker = Worker(
        client,
        task_queue=host_queue,
        workflows=[PiInferenceTurnWorkflow],
        activities=[],
        workflow_runner=UnsandboxedWorkflowRunner(),
    )
    pi_worker = Worker(
        client,
        task_queue=pi_queue,
        workflows=[],
        activities=[fake_pi_inference],
    )

    async def _client_factory():
        return client

    agent = Agent(
        config=AgentConfig(
            instructions="Echo and summarize.",
            execution_backend="pi_worker",
            model="gpt-4o-mini",
            toolsets=["echo"],
            result_type=EchoSummary,
            extra_kwargs={
                "pi_worker_task_queue": host_queue,
                "pi_worker_temporal_client_factory": _client_factory,
            },
        )
    )

    host_task = asyncio.create_task(host_worker.run())
    pi_task = asyncio.create_task(pi_worker.run())
    try:
        run_result = await agent.run({"user_message": "Echo and summarize."})
    finally:
        for t in (host_task, pi_task):
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    output = run_result.output
    print(f"\nAgent output: {output!r}")
    assert isinstance(output, EchoSummary), output
    assert output.summary == "echo confirmed", output
    assert _PI_CALL_INDEX["i"] == 2, "Expected exactly 2 inference turns (tool_call + final_result)."

    print(
        "\nPASS — Agent(pi_worker) drove pydantic_ai + PiWorkerModel + "
        "registry-backed `echo` tool call + typed EchoSummary output."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
