"""End-to-end smoke: launch `run_tools_mcp --toolset echo` as a STDIO subprocess
and call its `echo` tool via FastMCP's client.

Run from the freedom-agents repo root:

    .venv/bin/python examples/feedback_demo/run_mcp_e2e.py

Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


GREEN = "\033[0;32m"
RED = "\033[0;31m"
BOLD = "\033[1m"
NC = "\033[0m"


async def main() -> int:
    demo_dir = Path(__file__).resolve().parent
    venv_python = Path(__file__).resolve().parents[2] / ".venv" / "bin" / "python"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "feedback_demo.settings"
    # The demo settings expect a DATABASE_URL even though the echo tool itself
    # doesn't touch the DB. Use the meml postgres if not already set.
    env.setdefault(
        "DATABASE_URL",
        "postgres://postgres:postgrespassword@127.0.0.1:5433/agents_unit_test",
    )

    transport = StdioTransport(
        command=python_bin,
        args=["manage.py", "run_tools_mcp", "--toolset", "echo", "--transport", "stdio"],
        env=env,
        cwd=str(demo_dir),
    )

    print(f"{BOLD}Spawning STDIO MCP subprocess via run_tools_mcp...{NC}")
    print(f"  cmd: {python_bin} manage.py run_tools_mcp --toolset echo --transport stdio")
    print(f"  cwd: {demo_dir}")

    async with Client(transport) as client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        print(f"\n{BOLD}Tools advertised by the server:{NC} {tool_names}")
        assert tool_names == ["echo"], f"expected ['echo'], got {tool_names}"

        echo_tool = tools[0]
        print(f"  echo input schema: {echo_tool.inputSchema}")

        result = await client.call_tool("echo", {"text": "hello from e2e"})
        print(f"\n{BOLD}Result of echo(text='hello from e2e'):{NC}")
        print(f"  {result.data}")
        assert result.data == {"echoed": "hello from e2e", "char_count": 14}, result.data

        # Verify error mapping: ValidationError on missing field should come back
        # as a tool-call error, not crash the server.
        from fastmcp.exceptions import ToolError

        try:
            await client.call_tool("echo", {})
        except ToolError as exc:
            print(f"\n{BOLD}Missing-field error surfaces as ToolError:{NC} {exc}")
        else:
            print(f"{RED}Expected ToolError for empty input, got none{NC}")
            return 1

        # Server should still be alive after the error.
        again = await client.call_tool("echo", {"text": "still up"})
        print(f"\n{BOLD}Server still alive after error:{NC} {again.data}")
        assert again.data == {"echoed": "still up", "char_count": 8}

    print(f"\n{GREEN}{BOLD}E2E success.{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
