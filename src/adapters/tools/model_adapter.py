"""Shared Pydantic-model conversion for tool adapters."""

from __future__ import annotations

from typing import Any, Callable

from agents.core.tools.contracts import Tool


def build_model_callable(
    tool: Tool,
    *,
    serialize_output: bool,
) -> Callable[..., Any]:
    """Build a keyword callable that validates with the source Pydantic model."""

    def call(**kwargs: Any) -> Any:
        input_obj = tool.input_model.model_validate(
            kwargs,
            by_alias=True,
            by_name=True,
        )
        output = tool.bound_method(input_obj)
        return output.model_dump(mode="json") if serialize_output else output

    call.__name__ = tool.name
    call.__qualname__ = tool.name
    call.__doc__ = getattr(tool.bound_method, "__doc__", None)
    return call


def input_json_schema(tool: Tool) -> dict[str, Any]:
    """Return the authoritative schema advertised by every tool adapter."""

    return tool.input_model.model_json_schema()
