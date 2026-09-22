from __future__ import annotations

from typing import TYPE_CHECKING

from agents.core.tools.contracts import Tool
from agents.runner.tools.model_adapter import build_model_callable, input_json_schema

if TYPE_CHECKING:
    from fastmcp.tools import FunctionTool


def build_tool_adapter(tool: Tool) -> FunctionTool:
    """Return a FastMCP tool with the input model's authoritative schema."""

    from fastmcp.tools import FunctionTool

    function = build_model_callable(tool, serialize_output=True)
    return FunctionTool(
        name=tool.name,
        description=function.__doc__,
        parameters=input_json_schema(tool),
        output_schema=None,
        fn=function,
    )
