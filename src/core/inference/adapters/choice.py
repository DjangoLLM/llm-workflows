"""Execution contract for choice inference providers."""

from typing import TypeVar

from agents.core.inference.adapter import InferenceAdapter

ResultT = TypeVar("ResultT", covariant=True)


class ChoiceAdapter(InferenceAdapter[ResultT]):
    """Execute choice inference and return the provider's result wrapper."""


__all__ = ("ChoiceAdapter",)
