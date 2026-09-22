from agents.core.tools.contracts import Tool, ToolExecutionError
from agents.core.tools.toolset import ToolSet, tool

__all__ = (
    "ToolSet",
    "tool",
    "Tool",
    "ToolExecutionError",
    "ToolRegistry",
    "default_registry",
    "register_toolset",
)


def __getattr__(name: str):
    if name in {"ToolRegistry", "default_registry", "register_toolset"}:
        from agents.catalog import tool_catalog

        return getattr(tool_catalog, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
