"""Separate agent and choice inference adapter contracts."""

from agents.core.inference.adapters.agent import AgentAdapter
from agents.core.inference.adapters.choice import ChoiceAdapter

__all__ = ("AgentAdapter", "ChoiceAdapter")
