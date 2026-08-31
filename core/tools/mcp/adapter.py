from __future__ import annotations

import inspect
from typing import Any, Callable

from pydantic_core import PydanticUndefined

from agents.core.tools.contracts import Tool


def build_tool_adapter(tool: Tool) -> Callable[..., dict[str, Any]]:
    """Return a callable whose signature mirrors `tool.input_model.model_fields`.

    The adapter:
      - Constructs `tool.input_model(**kwargs)` (Pydantic ValidationError propagates).
      - Calls `tool.bound_method` with the validated model (ToolExecutionError
        propagates unchanged).
      - Returns `output.model_dump(mode="json")` for deterministic MCP serialisation.

    No exceptions are caught: FastMCP turns ValidationError / ToolExecutionError
    into tool-call error responses and keeps the server up.
    """

    params = [
        inspect.Parameter(
            field_name,
            inspect.Parameter.KEYWORD_ONLY,
            default=(
                field_info.default
                if field_info.default is not PydanticUndefined
                else inspect.Parameter.empty
            ),
            annotation=field_info.annotation,
        )
        for field_name, field_info in tool.input_model.model_fields.items()
    ]

    def adapter(**kwargs: Any) -> dict[str, Any]:
        input_obj = tool.input_model(**kwargs)
        output = tool.bound_method(input_obj)
        return output.model_dump(mode="json")

    adapter.__name__ = tool.name
    adapter.__qualname__ = tool.name
    adapter.__doc__ = getattr(tool.bound_method, "__doc__", None)
    adapter.__signature__ = inspect.Signature(params, return_annotation=dict)
    adapter.__annotations__ = {
        field_name: field_info.annotation
        for field_name, field_info in tool.input_model.model_fields.items()
    }
    adapter.__annotations__["return"] = dict
    return adapter
