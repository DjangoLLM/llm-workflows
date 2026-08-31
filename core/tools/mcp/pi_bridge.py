"""Bridge between the agents MCP server and the pi-worker (`piInference`).

The pi-worker (`services/pi-worker/src/activities.ts`) accepts tools as
plain JSON schemas (`PiInferenceTool = {name, description?, parameters?}`)
and returns `toolCalls: [{name, arguments}]`. This module is what a Python
caller (typically a Temporal workflow) uses to:

  1. Spawn an MCP STDIO server (`run_tools_mcp --toolset X --transport stdio`)
     for a toolset registered with `expose_mcp=True`.
  2. Discover its tools and translate them into the `PiInferenceTool`
     shape the pi-worker expects.
  3. Dispatch returned `toolCalls` back through the same MCP client and
     return their results in a form suitable for the next user message.

Two flavours are provided:

  * `discover_pi_tools(...)` / `invoke_pi_tool(...)`  — one-shot helpers
    that spawn the subprocess, do one operation, and tear down. Cheap to
    reason about; fine inside Temporal activities.
  * `PiMcpBridge(...)`                                — async context
    manager that keeps a single subprocess + client alive across many
    operations. Use inside a single workflow turn that lists tools and
    calls several of them in sequence.

This module never imports pi-ai or temporalio; it is pure Python + fastmcp.
The conversion choices live entirely on the Python side so the pi-worker
stays a generic JSON-schema tool consumer.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Sequence


__all__ = [
    "PiInferenceTool",
    "PiToolResult",
    "default_stdio_command",
    "discover_pi_tools",
    "invoke_pi_tool",
    "PiMcpBridge",
]


@dataclass(slots=True, frozen=True)
class PiInferenceTool:
    """One tool descriptor in the shape pi-worker's `PiInferenceInput.tools` expects."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass(slots=True, frozen=True)
class PiToolResult:
    """Outcome of invoking a tool through the MCP bridge."""

    name: str
    arguments: dict[str, Any]
    output: Any
    is_error: bool
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "output": self.output,
            "is_error": self.is_error,
            "error_message": self.error_message,
        }


def default_stdio_command(
    toolset_name: str,
    *,
    python_bin: str | None = None,
    manage_py: str | os.PathLike[str] = "manage.py",
) -> list[str]:
    """Return the argv that launches `run_tools_mcp` over STDIO.

    The caller is responsible for the working directory: `manage.py` must
    resolve against the host Django project (e.g. the feedback demo).
    """

    return [
        python_bin or sys.executable,
        str(manage_py),
        "run_tools_mcp",
        "--toolset",
        toolset_name,
        "--transport",
        "stdio",
    ]


def _build_transport(command: Sequence[str], cwd: str | os.PathLike[str] | None, env: dict[str, str] | None):
    from fastmcp.client.transports import StdioTransport

    return StdioTransport(
        command=command[0],
        args=list(command[1:]),
        env=env or os.environ.copy(),
        cwd=str(cwd) if cwd is not None else None,
    )


def _normalize_schema(schema: Any) -> dict[str, Any]:
    """Coerce an MCP tool inputSchema into a plain JSON-Schema dict.

    FastMCP returns these as `dict` already, but be defensive in case a
    future version surfaces a pydantic model.
    """

    if schema is None:
        return {"type": "object", "properties": {}}
    if hasattr(schema, "model_dump"):
        return schema.model_dump(mode="json")
    if isinstance(schema, dict):
        return schema
    return dict(schema)


def _coerce_call_result(result: Any) -> Any:
    """Extract the structured payload from a FastMCP CallToolResult.

    Our adapters return `BaseModel.model_dump(mode="json")` (a `dict`),
    which FastMCP exposes via `result.data`. Fall back to the structured
    content list when `data` is unavailable.
    """

    data = getattr(result, "data", None)
    if data is not None:
        return data

    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None)
    if content is None:
        return None

    # Concatenate text blocks if that's all we have.
    text_blocks: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            text_blocks.append(text)
    return "".join(text_blocks) if text_blocks else None


# ---------------------------------------------------------------------------
# Long-lived bridge: one subprocess, many ops.
# ---------------------------------------------------------------------------


class PiMcpBridge:
    """Async context manager that holds one MCP STDIO subprocess open.

    Use when a workflow turn needs to (a) discover tools and then (b) call
    several of them back-to-back. Spawning per call is fine but slower; use
    the one-shot helpers below if you only need a single op.

    Example::

        async with PiMcpBridge.for_toolset("echo", cwd=DEMO_DIR) as bridge:
            tools = await bridge.list_tools()
            result = await bridge.call_tool("echo", {"text": "hi"})
    """

    def __init__(self, command: Sequence[str], *, cwd: str | os.PathLike[str] | None = None, env: dict[str, str] | None = None) -> None:
        self._command = list(command)
        self._cwd = cwd
        self._env = env
        self._client = None  # type: ignore[assignment]
        self._client_cm = None  # type: ignore[assignment]

    @classmethod
    def for_toolset(
        cls,
        toolset_name: str,
        *,
        cwd: str | os.PathLike[str] | None = None,
        env: dict[str, str] | None = None,
        python_bin: str | None = None,
        manage_py: str | os.PathLike[str] = "manage.py",
    ) -> "PiMcpBridge":
        command = default_stdio_command(toolset_name, python_bin=python_bin, manage_py=manage_py)
        return cls(command, cwd=cwd, env=env)

    async def __aenter__(self) -> "PiMcpBridge":
        from fastmcp import Client

        transport = _build_transport(self._command, self._cwd, self._env)
        self._client_cm = Client(transport)
        self._client = await self._client_cm.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        cm = self._client_cm
        self._client = None
        self._client_cm = None
        if cm is not None:
            await cm.__aexit__(exc_type, exc, tb)

    async def list_tools(self) -> list[PiInferenceTool]:
        if self._client is None:
            raise RuntimeError("PiMcpBridge must be entered with `async with` before use.")
        raw = await self._client.list_tools()
        return [
            PiInferenceTool(
                name=t.name,
                description=getattr(t, "description", None) or "",
                parameters=_normalize_schema(getattr(t, "inputSchema", None)),
            )
            for t in raw
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> PiToolResult:
        if self._client is None:
            raise RuntimeError("PiMcpBridge must be entered with `async with` before use.")

        from fastmcp.exceptions import ToolError

        try:
            result = await self._client.call_tool(name, arguments)
        except ToolError as exc:
            return PiToolResult(
                name=name,
                arguments=arguments,
                output=None,
                is_error=True,
                error_message=str(exc),
            )

        return PiToolResult(
            name=name,
            arguments=arguments,
            output=_coerce_call_result(result),
            is_error=False,
            error_message=None,
        )


# ---------------------------------------------------------------------------
# One-shot helpers: spawn-run-teardown per call.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _bridge(toolset_name: str, **kwargs: Any) -> AsyncIterator[PiMcpBridge]:
    bridge = PiMcpBridge.for_toolset(toolset_name, **kwargs)
    async with bridge:
        yield bridge


async def discover_pi_tools(
    toolset_name: str,
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    python_bin: str | None = None,
    manage_py: str | os.PathLike[str] = "manage.py",
) -> list[PiInferenceTool]:
    """Spawn the MCP server, list its tools, return them in pi-worker shape."""

    async with _bridge(
        toolset_name,
        cwd=cwd,
        env=env,
        python_bin=python_bin,
        manage_py=manage_py,
    ) as bridge:
        return await bridge.list_tools()


async def invoke_pi_tool(
    toolset_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
    python_bin: str | None = None,
    manage_py: str | os.PathLike[str] = "manage.py",
) -> PiToolResult:
    """Spawn the MCP server, invoke one tool, return its structured result."""

    async with _bridge(
        toolset_name,
        cwd=cwd,
        env=env,
        python_bin=python_bin,
        manage_py=manage_py,
    ) as bridge:
        return await bridge.call_tool(tool_name, arguments)
