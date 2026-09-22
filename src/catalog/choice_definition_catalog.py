"""Default catalog for public choice definitions."""

from collections.abc import Callable

from agents.core.inference.definition_catalog import DefinitionCatalog
from agents.inferences.choices import ChoiceDefinition


class ChoiceDefinitionCatalog(DefinitionCatalog[ChoiceDefinition]):
    """Store reusable choice definitions in this catalog's own registry."""

    definition_type = ChoiceDefinition
    definition_label = "choice definition"

    @classmethod
    def register_choice_definition(
        cls,
        key: str,
        resolver: Callable[[], ChoiceDefinition],
    ) -> None:
        """Register a choice definition factory under a stable key."""

        cls.register(key, resolver)

    @classmethod
    def resolve_choice_definition(cls, key: str) -> ChoiceDefinition:
        """Build the choice definition registered under ``key``."""

        return cls.resolve(key)

    @classmethod
    def list_choice_definition_keys(cls) -> list[str]:
        """Return registered keys in sorted order."""

        return cls.list_keys()


__all__ = ("ChoiceDefinitionCatalog",)
