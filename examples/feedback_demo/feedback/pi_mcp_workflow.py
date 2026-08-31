"""Sample workflow demonstrating: pi-worker (LLM) + agents MCP toolset.

The shape of the loop:

  1. Activity `agents.mcp.list_pi_tools` opens the STDIO MCP server for
     the requested toolset and returns its tool schemas in pi-worker
     JSON form.
  2. Activity `piInference` (TypeScript, on `pi-inference-queue`) is
     called with those tools attached. It returns final text and zero or
     more `toolCalls`.
  3. For each tool call, activity `agents.mcp.call_pi_tool` invokes the
     tool through the MCP server and we append the result as a synthetic
     "user" turn so the next `piInference` round has the data.
  4. Repeat until `toolCalls` is empty or `max_iterations` reached.

This module is deliberately a workflow definition only — no worker
registration here. The host project's Temporal worker should pick up the
`piInference` activity stub plus the agents MCP activities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from temporalio import workflow

# Re-export the canonical pi-worker routing stub from the agents core. The
# stub lives in core so non-demo agent paths can use it without depending on
# this example module.
from agents.core.temporal.activities import (  # noqa: F401
    PI_INFERENCE_TASK_QUEUE as TS_ACTIVITY_QUEUE,
    pi_inference_stub,
)


# ---------------------------------------------------------------------------
# Workflow input.
# ---------------------------------------------------------------------------


@dataclass
class PiMcpLoopInput:
    provider: str
    model: str
    system_prompt: str
    user_message: str
    toolset_name: str
    # Filesystem context for the MCP subprocess. Defaults assume the host
    # Django project's CWD already contains `manage.py`.
    mcp_cwd: Optional[str] = None
    mcp_python_bin: Optional[str] = None
    mcp_manage_py: str = "manage.py"
    max_iterations: int = 4
    activity_timeout_seconds: int = 60


@dataclass
class PiMcpLoopOutput:
    final_text: str
    iterations: int
    tool_results: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Workflow.
# ---------------------------------------------------------------------------


@workflow.defn(name="agents.examples.PiMcpLoopWorkflow")
class PiMcpLoopWorkflow:
    """Drive a pi-worker conversation that can call agents MCP tools.

    The workflow is the source of truth for the message history; the
    pi-worker activity is stateless. Tool results are folded back as
    user-role messages because the current `PiInferenceMessage` schema in
    `services/pi-worker/src/activities.ts` only supports plain text
    content. Switching to a richer message schema later only requires
    updating the message append step here.
    """

    @workflow.run
    async def run(self, input: PiMcpLoopInput) -> PiMcpLoopOutput:
        timeout = timedelta(seconds=input.activity_timeout_seconds)

        tools = await workflow.execute_activity(
            "agents.mcp.list_pi_tools",
            args=[
                input.toolset_name,
                input.mcp_cwd,
                input.mcp_python_bin,
                input.mcp_manage_py,
            ],
            start_to_close_timeout=timeout,
        )

        messages: list[dict[str, str]] = [
            {"role": "user", "content": input.user_message}
        ]

        tool_results: list[dict[str, Any]] = []
        final_text = ""

        for iteration in range(1, input.max_iterations + 1):
            pi_payload = {
                "provider": input.provider,
                "model": input.model,
                "systemPrompt": input.system_prompt,
                "messages": messages,
                "tools": tools,
            }

            pi_output: dict = await workflow.execute_activity(
                pi_inference_stub,
                pi_payload,
                task_queue=TS_ACTIVITY_QUEUE,
                start_to_close_timeout=timeout,
            )

            final_text = pi_output.get("finalText", "")
            calls = pi_output.get("toolCalls", []) or []

            if not calls:
                return PiMcpLoopOutput(
                    final_text=final_text,
                    iterations=iteration,
                    tool_results=tool_results,
                )

            # Record the assistant's tool-picking turn so the next round
            # has it in history.
            if final_text:
                messages.append({"role": "assistant", "content": final_text})

            for call in calls:
                result = await workflow.execute_activity(
                    "agents.mcp.call_pi_tool",
                    args=[
                        input.toolset_name,
                        call["name"],
                        call.get("arguments", {}),
                        input.mcp_cwd,
                        input.mcp_python_bin,
                        input.mcp_manage_py,
                    ],
                    start_to_close_timeout=timeout,
                )
                tool_results.append(result)

                # Stitch the tool result into the next user turn. Pi-worker
                # only consumes plain text today; JSON-encode the payload.
                import json

                feedback = json.dumps(
                    {
                        "tool": call["name"],
                        "arguments": call.get("arguments", {}),
                        "result": result["output"]
                        if not result["is_error"]
                        else {"error": result["error_message"]},
                    }
                )
                messages.append({"role": "user", "content": f"<tool_result>{feedback}</tool_result>"})

        return PiMcpLoopOutput(
            final_text=final_text,
            iterations=input.max_iterations,
            tool_results=tool_results,
        )
