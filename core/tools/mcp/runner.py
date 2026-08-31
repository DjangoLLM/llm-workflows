from __future__ import annotations

import sys

from agents.core.tools.mcp.server import build_mcp_server
from agents.core.tools.registry import ToolRegistry, default_registry

# NOTE: coverage of this module's `server.run(...)` call is intentionally low —
# the real transport loop is exercised by manual verification (LLD §14) rather
# than by unit tests, which use FastMCP's in-process client instead.


def run(
    toolset_name: str,
    *,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
    name: str | None = None,
    registry: ToolRegistry = default_registry,
) -> None:
    """Build and start a FastMCP server for `toolset_name` on `transport`.

    `--port` is required for `http` / `sse`. Boot-time logging goes to stderr;
    stdout is reserved for the STDIO transport.
    """

    if transport in ("http", "sse") and port is None:
        print(
            f"mcp.runner.refused transport={transport} reason=port-required",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if transport not in ("stdio", "http", "sse"):
        print(
            f"mcp.runner.refused transport={transport} reason=unknown-transport",
            file=sys.stderr,
        )
        raise SystemExit(2)

    server = build_mcp_server(toolset_name, registry=registry)

    transport_kwargs: dict[str, object] = {}
    if transport in ("http", "sse"):
        transport_kwargs["host"] = host
        transport_kwargs["port"] = port

    server.run(transport=transport, **transport_kwargs)
