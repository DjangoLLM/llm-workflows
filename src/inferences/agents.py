"""Public Codex agent definition and catalog binding."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from agents.core.inference.definition import Definition

if TYPE_CHECKING:
    from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog


@dataclass(slots=True)
class AgentDefinition(Definition):
    """Define an agent executed by the supported Codex backend."""

    instructions: str
    execution_backend: Literal["codex_cli"] = "codex_cli"
    model: Any = None
    settings: Mapping[str, Any] | None = None
    result_type: type[Any] | None = None
    tools: Iterable[Callable[..., Any]] | None = None
    toolsets: Iterable[str] | None = None
    extra_kwargs: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        valid_backends = frozenset({"codex_cli"})
        if self.execution_backend not in valid_backends:
            raise ValueError(
                f"execution_backend must be one of {sorted(valid_backends)!r}; "
                f"got {self.execution_backend!r}"
            )

    @classmethod
    def _get_catalog(cls) -> type[AgentDefinitionCatalog]:
        from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog

        return AgentDefinitionCatalog


__all__ = ("AgentDefinition",)
