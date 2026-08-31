"""End-to-end: pi-worker bridge against the `echo` MCP toolset.

This proves the full pi-agent → MCP pathway from the Python side without
needing the TypeScript pi-worker or any LLM API key. The bridge:

  1. Spawns `manage.py run_tools_mcp --toolset echo --transport stdio`.
  2. Calls `list_tools()` and converts each result into the JSON shape
     the pi-worker activity (`PiInferenceInput.tools`) expects.
  3. Simulates the pi-worker handing back a `toolCalls` array (this is
     what `complete()` returns when the LLM picks a tool).
  4. Dispatches each tool call through the same MCP bridge and prints the
     `toolResult` that would be threaded back into the next LLM message.

Run from the freedom-agents repo root:

    .venv/bin/python examples/feedback_demo/run_pi_bridge_e2e.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agents.core.tools.mcp.pi_bridge import PiMcpBridge  # noqa: E402


GREEN = "\033[0;32m"
RED = "\033[0;31m"
BOLD = "\033[1m"
NC = "\033[0m"


# What the pi-worker would return when the model picks our echo tool.
# Real call: `result = await complete(model, ctx)` → `result.content` contains
# `toolCall` blocks that get mapped into `PiInferenceOutput.toolCalls`.
SIMULATED_PI_TOOL_CALLS = [
    {"name": "echo", "arguments": {"text": "hello via pi-bridge"}},
    {"name": "echo", "arguments": {"text": "second call, same subprocess"}},
    # Intentionally malformed to show error mapping:
    {"name": "echo", "arguments": {}},
]


async def main() -> int:
    demo_dir = Path(__file__).resolve().parent
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "feedback_demo.settings"
    env.setdefault(
        "DATABASE_URL",
        "postgres://postgres:postgrespassword@127.0.0.1:5433/agents_unit_test",
    )

    print(f"{BOLD}=== Step 1: spawn MCP server and list tools ==={NC}")
    print(f"  toolset: echo")
    print(f"  cwd:     {demo_dir}")

    bridge = PiMcpBridge.for_toolset(
        "echo",
        cwd=demo_dir,
        env=env,
        python_bin=python_bin,
    )

    async with bridge:
        pi_tools = await bridge.list_tools()
        print(f"\n  Discovered {len(pi_tools)} tool(s) in pi-worker format:")
        for tool in pi_tools:
            print(f"    - {tool.name}")
            print(f"      description: {tool.description!r}")
            print(f"      parameters:  {tool.parameters}")

        assert pi_tools, "Expected at least one tool from echo toolset."
        assert pi_tools[0].name == "echo"
        assert "text" in pi_tools[0].parameters.get("properties", {})

        # The list above is what you'd pass straight to the pi-worker via
        # PiInferenceInput.tools — each tool serialises to {name, description, parameters}.
        pi_inference_tools_payload = [tool.to_dict() for tool in pi_tools]
        print(f"\n  Payload ready for piInference activity:")
        print(f"    tools = {pi_inference_tools_payload}")

        print(f"\n{BOLD}=== Step 2: dispatch simulated pi-worker toolCalls ==={NC}")
        print(f"  (in a real flow these come back from `piInference` after the LLM picks a tool)")

        for call in SIMULATED_PI_TOOL_CALLS:
            print(f"\n  -> call_tool name={call['name']!r} arguments={call['arguments']}")
            result = await bridge.call_tool(call["name"], call["arguments"])
            if result.is_error:
                print(f"     {RED}tool error{NC}: {result.error_message}")
            else:
                print(f"     output: {result.output}")
                print(f"     (this is what the workflow appends as the next user message)")

        # Verify subprocess survived the failing call.
        post_error = await bridge.call_tool("echo", {"text": "alive after error"})
        assert not post_error.is_error
        assert post_error.output == {"echoed": "alive after error", "char_count": 17}, post_error.output
        print(f"\n  Server survived the error case: {post_error.output}")

    print(f"\n{GREEN}{BOLD}pi-bridge e2e success.{NC}")
    print()
    print(f"{BOLD}How this slots into the pi agent:{NC}")
    print("  - workflow activity 'agents.mcp.list_pi_tools' (thin wrapper around")
    print("    `discover_pi_tools`) hands the list to PiInferenceInput.tools.")
    print("  - workflow activity 'piInference' (TypeScript, on pi-inference-queue)")
    print("    returns PiInferenceOutput.toolCalls.")
    print("  - workflow loops: for each toolCall, run an activity wrapping")
    print("    `invoke_pi_tool`, append result as a user message, re-call piInference.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
