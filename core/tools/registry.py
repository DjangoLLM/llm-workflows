from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from pydantic import BaseModel

from agents.core.tools.contracts import Tool
from agents.core.tools.toolset import _TOOL_MARKER, ToolSet


@dataclass
class _ToolsetMeta:
    module: str
    expose_mcp: bool
    instance: ToolSet
    tools: list[Tool] = field(default_factory=list)


class ToolRegistry:
    def __init__(self) -> None:
        self._toolsets: dict[str, type[ToolSet]] = {}
        self._toolset_meta: dict[str, _ToolsetMeta] = {}
        self._tools: dict[str, Tool] = {}

    def register_toolset(
        self,
        toolset_cls: type[ToolSet],
        *,
        module: str,
        expose_mcp: bool = False,
    ) -> None:
        name = getattr(toolset_cls, "name", None)
        if not isinstance(name, str) or not name:
            raise TypeError(
                f"{toolset_cls.__qualname__} must set class attribute 'name'"
            )
        if name in self._toolsets:
            raise ValueError(f"Toolset '{name}' is already registered.")

        instance = toolset_cls()

        collected = self._collect_tools(toolset_cls, instance, name)
        if not collected:
            raise ValueError(
                f"Toolset '{name}' has no @tool-decorated methods."
            )

        if expose_mcp:
            for t in collected:
                if not t.mcp_safe:
                    raise ValueError(
                        f"Toolset '{name}' is expose_mcp=True but tool "
                        f"'{t.name}' is not mcp_safe."
                    )

        for t in collected:
            if t.name in self._tools:
                owner = self._tools[t.name].toolset_name
                raise ValueError(
                    f"Tool '{t.name}' is already registered by toolset '{owner}'."
                )

        meta = _ToolsetMeta(
            module=module, expose_mcp=expose_mcp, instance=instance, tools=collected
        )
        self._toolsets[name] = toolset_cls
        self._toolset_meta[name] = meta
        for t in collected:
            self._tools[t.name] = t

    @staticmethod
    def _collect_tools(
        toolset_cls: type[ToolSet], instance: ToolSet, toolset_name: str
    ) -> list[Tool]:
        seen: set[str] = set()
        tools: list[Tool] = []
        for cls in toolset_cls.__mro__:
            if cls in (object, ToolSet):
                continue
            for attr_name, attr in vars(cls).items():
                if attr_name in seen:
                    continue
                meta = getattr(attr, _TOOL_MARKER, None)
                if meta is None:
                    continue
                seen.add(attr_name)
                tool_name = meta.name_override or attr_name
                bound = getattr(instance, attr_name)
                tools.append(
                    Tool(
                        name=tool_name,
                        input_model=meta.input_model,
                        output_model=meta.output_model,
                        mcp_safe=meta.mcp_safe,
                        toolset_name=toolset_name,
                        bound_method=bound,
                    )
                )
        return tools

    # Toolset reads
    def get_toolset(self, name: str) -> type[ToolSet]:
        if name not in self._toolsets:
            raise KeyError(name)
        return self._toolsets[name]

    def toolset_names(
        self,
        *,
        modules: Iterable[str] | None = None,
        exposed_only: bool = False,
    ) -> list[str]:
        module_filter = frozenset(modules) if modules is not None else None
        result = []
        for name, meta in self._toolset_meta.items():
            if module_filter is not None and meta.module not in module_filter:
                continue
            if exposed_only and not meta.expose_mcp:
                continue
            result.append(name)
        return sorted(result)

    def resolve_toolset(self, name: str) -> list[Tool]:
        if name not in self._toolset_meta:
            raise KeyError(name)
        return list(self._toolset_meta[name].tools)

    def toolset_module(self, name: str) -> str:
        if name not in self._toolset_meta:
            raise KeyError(name)
        return self._toolset_meta[name].module

    def toolset_exposed(self, name: str) -> bool:
        if name not in self._toolset_meta:
            raise KeyError(name)
        return self._toolset_meta[name].expose_mcp

    # Flat tool surface
    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(name)
        return self._tools[name]

    def run(self, name: str, input: dict | BaseModel) -> BaseModel:
        tool = self.get(name)
        if isinstance(input, dict):
            validated = tool.input_model(**input)
        else:
            validated = input
        return tool.bound_method(validated)

    def names(self, *, modules: Iterable[str] | None = None) -> list[str]:
        if modules is None:
            return sorted(self._tools)
        module_filter = frozenset(modules)
        allowed_toolsets = {
            ts for ts, meta in self._toolset_meta.items() if meta.module in module_filter
        }
        return sorted(
            tn for tn, t in self._tools.items() if t.toolset_name in allowed_toolsets
        )


default_registry = ToolRegistry()
