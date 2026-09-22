"""Execution interface for registered workflow definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.runner.agent import Agent, ManagedAgent, agent_run_finished, run_agent
    from agents.runner.workflow import (
        create_workflow_run,
        execute_workflow_step,
        mark_workflow_failure,
        mark_workflow_success,
    )

__all__ = (
    "Agent",
    "ManagedAgent",
    "agent_run_finished",
    "create_workflow_run",
    "execute_workflow_step",
    "mark_workflow_failure",
    "mark_workflow_success",
    "run_agent",
)


def __getattr__(name: str) -> Any:
    if name in {"Agent", "ManagedAgent", "agent_run_finished", "run_agent"}:
        from agents.runner import agent

        return getattr(agent, name)
    if name in {
        "create_workflow_run",
        "execute_workflow_step",
        "mark_workflow_failure",
        "mark_workflow_success",
    }:
        from agents.runner import workflow

        return getattr(workflow, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
