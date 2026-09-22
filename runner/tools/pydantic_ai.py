"""Adapt registry Tool descriptors into pydantic-ai tools."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Tool as PydanticAITool

from agents.core.tools.contracts import Tool
from agents.runner.tools.model_adapter import build_model_callable, input_json_schema


def build_pydantic_ai_tool(tool: Tool) -> PydanticAITool[Any]:
    """Return a Pydantic AI tool with the input model's authoritative schema."""

    function = build_model_callable(tool, serialize_output=False)
    adapted = PydanticAITool.from_schema(
        function,
        name=tool.name,
        description=function.__doc__ or tool.name,
        json_schema=input_json_schema(tool),
    )
    adapted.__name__ = tool.name
    return adapted
