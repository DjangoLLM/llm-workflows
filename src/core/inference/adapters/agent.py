"""Execution contract for agent inference providers."""

from typing import TypeVar

from agents.core.inference.adapter import InferenceAdapter

ResultT = TypeVar("ResultT", covariant=True)


class AgentAdapter(InferenceAdapter[ResultT]):
    """Execute agent inference and return the provider's result wrapper."""


__all__ = ("AgentAdapter",)
