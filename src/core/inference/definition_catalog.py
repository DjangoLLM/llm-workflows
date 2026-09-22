"""Shared registration and validation for definition factories."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

DefinitionT = TypeVar("DefinitionT")


class DefinitionCatalog(Generic[DefinitionT]):
    """Base for typed factory catalogs, with separate storage per subclass."""

    definition_type: type[DefinitionT]
    definition_label: str
    _resolvers: dict[str, Callable[[], DefinitionT]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._resolvers = {}

    @classmethod
    def register(cls, key: str, resolver: Callable[[], DefinitionT]) -> None:
        """Store a factory under a unique, nonempty key."""

        if not key:
            raise ValueError(f"{cls.definition_label.capitalize()} key cannot be empty.")
        if key in cls._resolvers:
            raise ValueError(f"Duplicate {cls.definition_label} key '{key}'.")
        cls._resolvers[key] = resolver

    @classmethod
    def resolve(cls, key: str) -> DefinitionT:
        """Call the registered factory and validate its result type."""

        if key not in cls._resolvers:
            raise ValueError(f"Unknown {cls.definition_label} key '{key}'.")
        definition = cls._resolvers[key]()
        if not isinstance(definition, cls.definition_type):
            raise TypeError(
                f"Resolver for '{key}' returned {type(definition).__name__}, "
                f"expected {cls.definition_type.__name__}."
            )
        return definition

    @classmethod
    def list_keys(cls) -> list[str]:
        """Return registered keys in sorted order."""

        return sorted(cls._resolvers)

    @classmethod
    def validate_registry(cls) -> None:
        """Resolve every registered definition to validate the catalog."""

        for key in cls.list_keys():
            cls.resolve(key)


__all__ = ("DefinitionCatalog",)
