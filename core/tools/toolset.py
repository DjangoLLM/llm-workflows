from __future__ import annotations

from typing import Any, Callable, ClassVar, NamedTuple

from pydantic import BaseModel

_TOOL_MARKER = "__agent_tool__"


class _ToolMeta(NamedTuple):
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    mcp_safe: bool
    name_override: str | None


class ToolSet:
    """Base class for tool collections. Subclasses set `name` and define
    `@tool`-decorated methods. One subclass = one toolset."""

    name: ClassVar[str]

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass


def tool(
    *,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    mcp_safe: bool = False,
    name: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a `ToolSet` method to mark it as a tool.

    The function is returned unchanged so it can still be called normally
    in-process; `register_toolset` discovers it by the attached marker."""

    if not (isinstance(input_model, type) and issubclass(input_model, BaseModel)):
        raise TypeError("@tool input_model must be a BaseModel subclass")
    if not (isinstance(output_model, type) and issubclass(output_model, BaseModel)):
        raise TypeError("@tool output_model must be a BaseModel subclass")

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        if not callable(fn):
            raise TypeError("@tool must wrap a callable")
        setattr(
            fn,
            _TOOL_MARKER,
            _ToolMeta(
                input_model=input_model,
                output_model=output_model,
                mcp_safe=mcp_safe,
                name_override=name,
            ),
        )
        return fn

    return decorate
