"""Provider-independent inference execution delegation."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from agents.core.inference.adapter import InferenceAdapter

ResultT = TypeVar("ResultT")


class InferenceRunner(Generic[ResultT]):
    """Run an adapter without persistence or provider-specific conversion."""

    def __init__(self, adapter: InferenceAdapter[ResultT]) -> None:
        self._runner = adapter

    @property
    def adapter(self) -> InferenceAdapter[ResultT]:
        return self._runner

    @property
    def name(self) -> str | None:
        return getattr(self._runner, "name", None)

    async def run(self, input_payload: Any = None) -> ResultT:
        return await self._runner.run(input_payload)

    def run_sync(self, input_payload: Any = None) -> ResultT:
        return self._runner.run_sync(input_payload)


__all__ = ("InferenceRunner",)
