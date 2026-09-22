from __future__ import annotations

import sys

from agents.runner.tools.mcp.adapter import build_tool_adapter
from agents.core.tools.registry import ToolRegistry, default_registry


def build_mcp_server(
    toolset_name: str,
    *,
    name: str | None = None,
    registry: ToolRegistry = default_registry,
):
    """Build a FastMCP server exposing every member tool of `toolset_name`.

    Refuses (SystemExit) if the toolset is missing or not registered with
    `expose_mcp=True`. Imports fastmcp lazily so that this module is importable
    in environments where fastmcp isn't installed (e.g. list_toolsets path).
    """

    registered = registry.toolset_names()
    exposed = registry.toolset_names(exposed_only=True)
    if toolset_name not in exposed:
        reason = "not-registered" if toolset_name not in registered else "not-exposed"
        print(
            f"mcp.server.refused toolset={toolset_name} reason={reason}",
            file=sys.stderr,
        )
        raise SystemExit(2)

    try:
        from fastmcp import FastMCP  # type: ignore
    except ImportError:
        print(
            f"mcp.server.refused toolset={toolset_name} reason=fastmcp-missing",
            file=sys.stderr,
        )
        raise SystemExit(3)

    server = FastMCP(name=name or toolset_name)
    tools = registry.resolve_toolset(toolset_name)
    for tool in tools:
        server.add_tool(build_tool_adapter(tool))

    bound = ",".join(sorted(t.name for t in tools))
    print(
        f"mcp.server.bound toolset={toolset_name} tools={bound}",
        file=sys.stderr,
    )
    return server
