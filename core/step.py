"""Author-facing workflow step contract."""

from __future__ import annotations

from abc import ABC
from typing import Any

from agents.core.agent import AgentConfig


class Step(ABC):
    """A unit of workflow work defined by the target application."""

    @property
    def agent_config(self) -> AgentConfig | None:
        """Return agent configuration when this is an agent-backed step."""

        return None

    def pre_execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        """Transform input before the step runs."""

        return payload, context or {}

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a code step. Agent-backed steps may use the default implementation."""

        if self.agent_config is not None:
            raise RuntimeError("Agent-backed steps are executed by agents.runner")
        raise NotImplementedError("Code steps must override execute(payload)")

    def post_execute(
        self,
        result: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | dict[str, Any]:
        """Transform output after the step runs."""

        return result, context or {}


__all__ = ("Step",)
