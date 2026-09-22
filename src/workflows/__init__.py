"""Author-facing workflow definition."""

from __future__ import annotations

from typing import ClassVar

from agents.steps import Step


class Workflow:
    """A named composition of registered step definitions."""

    name: ClassVar[str] = ""
    steps: ClassVar[dict[str, type[Step]]] = {}


__all__ = ("Workflow",)
