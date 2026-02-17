from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .agent import Agent, AgentConfig, ManagedAgent, run_agent
    from .models import AgentRun, AgentRunStatus

__all__ = ("Agent", "AgentConfig", "ManagedAgent", "AgentRun", "AgentRunStatus", "run_agent")


def __getattr__(name: str) -> Any:
    if name == "AgentRun":
        from .models import AgentRun as _AgentRun

        return _AgentRun
    if name == "AgentRunStatus":
        from .models import AgentRunStatus as _AgentRunStatus

        return _AgentRunStatus
    if name == "Agent":
        from .agent import Agent as _Agent

        return _Agent
    if name == "ManagedAgent":
        from .agent import ManagedAgent as _ManagedAgent

        return _ManagedAgent
    if name == "AgentConfig":
        from .agent import AgentConfig as _AgentConfig

        return _AgentConfig
    if name == "run_agent":
        from .agent import run_agent as _run_agent

        return _run_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
