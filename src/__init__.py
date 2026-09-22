from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .inferences.agents import AgentDefinition
    from .models import AgentRun, AgentRunStatus
    from .runner.agent import Agent, ManagedAgent, run_agent

__all__ = ("Agent", "AgentDefinition", "ManagedAgent", "AgentRun", "AgentRunStatus", "run_agent")


def __getattr__(name: str) -> Any:
    if name == "AgentRun":
        from .models import AgentRun as _AgentRun

        return _AgentRun
    if name == "AgentRunStatus":
        from .models import AgentRunStatus as _AgentRunStatus

        return _AgentRunStatus
    if name == "Agent":
        from .runner.agent import Agent as _Agent

        return _Agent
    if name == "ManagedAgent":
        from .runner.agent import ManagedAgent as _ManagedAgent

        return _ManagedAgent
    if name == "AgentDefinition":
        from .inferences.agents import AgentDefinition as _AgentDefinition

        return _AgentDefinition
    if name == "run_agent":
        from .runner.agent import run_agent as _run_agent

        return _run_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
