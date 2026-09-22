"""Common execution contract for inference adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

ResultT = TypeVar("ResultT", covariant=True)


class InferenceAdapter(ABC, Generic[ResultT]):
    """Execute inference with synchronous and asynchronous entry points.

    Concrete adapters translate payloads for their provider and return the
    provider's result wrapper. Adapters used by ManagedAgent must return a
    result with an ``output`` attribute.
    """

    @abstractmethod
    async def run(self, input_payload: Any = None) -> ResultT:
        """Execute one inference asynchronously."""

    @abstractmethod
    def run_sync(self, input_payload: Any = None) -> ResultT:
        """Execute one inference synchronously."""


__all__ = ("InferenceAdapter",)
