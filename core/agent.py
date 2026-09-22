"""Author-facing agent configuration."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pydantic_ai.models.openai import (
        OpenAIChatModel,
        OpenAIResponsesModel,
        OpenAIResponsesModelSettings,
    )


@dataclass(slots=True)
class AgentConfig:
    """Describe an agent-backed step without executing it."""

    instructions: str
    execution_backend: Literal["pydantic_ai", "codex_cli", "jev"] = "pydantic_ai"
    model: OpenAIChatModel | OpenAIResponsesModel | str | None = None
    settings: OpenAIResponsesModelSettings | None = None
    result_type: type[Any] | None = None
    tools: Iterable[Callable[..., Any]] | None = None
    toolsets: Iterable[str] | None = None
    extra_kwargs: Mapping[str, Any] | None = None
    questions: Mapping[str, Mapping[str, Any]] | None = None

    def __post_init__(self) -> None:
        valid_backends = frozenset({"pydantic_ai", "codex_cli", "jev"})
        if self.execution_backend not in valid_backends:
            raise ValueError(
                f"execution_backend must be one of {sorted(valid_backends)!r}; "
                f"got {self.execution_backend!r}"
            )
        if self.execution_backend == "jev":
            if not self.questions or any(
                "criteria" not in question for question in self.questions.values()
            ):
                raise ValueError(
                    "jev backend requires `questions` with a `criteria` mapping per head"
                )
            if self.model is not None and not isinstance(self.model, str):
                raise ValueError(
                    "jev backend takes `model` as a string, e.g. 'jev-latest'"
                )


def __getattr__(name: str) -> Any:
    """Keep legacy execution imports working while callers move to runner."""

    if name in {"Agent", "ManagedAgent", "agent_run_finished", "run_agent"}:
        from agents.runner import agent as runner_agent

        return getattr(runner_agent, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ("AgentConfig",)
