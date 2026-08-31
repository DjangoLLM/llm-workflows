"""Adapt registry Tool descriptors into pydantic-ai-compatible callables.

pydantic-ai infers a tool's JSON schema from the function's type annotations
and signature. This adapter creates a wrapper function whose signature mirrors
the tool's `input_model.model_fields`, so pydantic-ai sees the correct schema
without any changes to the underlying tool implementation.

The return value is the output model instance; pydantic-ai serialises it fine.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from pydantic_core import PydanticUndefined

from agents.core.tools.contracts import Tool


def build_pydantic_ai_tool(tool: Tool) -> Callable[..., Any]:
    """Return a callable pydantic-ai can use as a tool.

    The wrapper:
      - Has a signature and annotations that mirror `tool.input_model.model_fields`.
      - Constructs `tool.input_model(**kwargs)` so Pydantic validates the args.
      - Calls `tool.bound_method` with the validated model.
      - Returns the output model instance (pydantic-ai handles serialisation).
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

    def wrapper(**kwargs: Any) -> Any:
        input_obj = tool.input_model(**kwargs)
        return tool.bound_method(input_obj)

    wrapper.__name__ = tool.name
    wrapper.__qualname__ = tool.name
    wrapper.__doc__ = getattr(tool.bound_method, "__doc__", None) or tool.name
    wrapper.__signature__ = inspect.Signature(params)
    wrapper.__annotations__ = {
        field_name: field_info.annotation
        for field_name, field_info in tool.input_model.model_fields.items()
    }
    return wrapper
