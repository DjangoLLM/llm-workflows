"""Shared behavior for reusable definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.core.inference.definition_catalog import DefinitionCatalog


class Definition(ABC):
    """A definition that can register itself in its default catalog."""

    __slots__ = ()

    @classmethod
    @abstractmethod
    def _get_catalog(cls) -> type[DefinitionCatalog[Any]]:
        """Return the catalog responsible for this definition type."""

    def register(self, key: str) -> None:
        """Register this definition under a stable key."""

        self._get_catalog().register(key, lambda: self)


__all__ = ("Definition",)
