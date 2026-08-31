"""Temporal activities that bridge the agents MCP server to the pi-worker.

These activities wrap `agents.core.tools.mcp.pi_bridge` so a workflow can:

  - Discover the tool schemas a registered toolset exposes, in the JSON
    shape the TypeScript pi-worker accepts as `PiInferenceInput.tools`.
  - Dispatch a tool call returned by the pi-worker through the same MCP
    server and collect its structured output.

Both activities spawn a fresh STDIO MCP subprocess per call (simple, no
shared state). For multi-call hot paths, a longer-lived bridge can be
introduced later; nothing in the workflow API would change.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from temporalio import activity

from agents.core.tools.mcp.pi_bridge import discover_pi_tools, invoke_pi_tool

logger = logging.getLogger(__name__)


@activity.defn(name="agents.mcp.list_pi_tools")
async def list_pi_tools_activity(
    toolset_name: str,
    cwd: Optional[str] = None,
    python_bin: Optional[str] = None,
    manage_py: str = "manage.py",
) -> list[dict[str, Any]]:
    """Return the toolset's tool descriptors in pi-worker JSON shape.

    Output items are `{name, description, parameters}` and can be passed
    directly to `PiInferenceInput.tools` over the polyglot Temporal boundary.
    """

    tools = await discover_pi_tools(
        toolset_name,
        cwd=cwd,
        python_bin=python_bin,
        manage_py=manage_py,
        env=os.environ.copy(),
    )
    payload = [t.to_dict() for t in tools]
    logger.info(
        "agents.mcp.list_pi_tools toolset=%s count=%d", toolset_name, len(payload)
    )
    return payload


@activity.defn(name="agents.mcp.call_pi_tool")
async def call_pi_tool_activity(
    toolset_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    cwd: Optional[str] = None,
    python_bin: Optional[str] = None,
    manage_py: str = "manage.py",
) -> dict[str, Any]:
    """Invoke `tool_name` on the toolset's MCP server and return its result.

    The return shape is `PiToolResult.to_dict()`. Failures are surfaced
    as `{is_error: True, error_message: ...}` so the workflow can decide
    whether to feed the error back to the LLM or abort.
    """

    result = await invoke_pi_tool(
        toolset_name,
        tool_name,
        arguments,
        cwd=cwd,
        python_bin=python_bin,
        manage_py=manage_py,
        env=os.environ.copy(),
    )
    logger.info(
        "agents.mcp.call_pi_tool toolset=%s tool=%s is_error=%s",
        toolset_name,
        tool_name,
        result.is_error,
    )
    return result.to_dict()
