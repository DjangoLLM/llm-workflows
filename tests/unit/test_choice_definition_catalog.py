from __future__ import annotations

import pytest

from agents.inferences.choices import ChoiceDefinition
from agents.catalog.choice_definition_catalog import ChoiceDefinitionCatalog


def choice_definition(question: str = "Which project?") -> ChoiceDefinition:
    return ChoiceDefinition(
        question=question,
        criteria="Closest topic",
        input_type=dict,
        result_type=dict,
        candidates={"project": "Project"},
    )


def test_choice_definition_registers_itself() -> None:
    definition = choice_definition()

    definition.register("project.selection")

    assert ChoiceDefinitionCatalog.resolve_choice_definition("project.selection") is definition


def test_catalog_registers_and_resolves_factory() -> None:
    ChoiceDefinitionCatalog.register_choice_definition(
        "project.selection",
        lambda: choice_definition("Which project should run?"),
    )

    resolved = ChoiceDefinitionCatalog.resolve_choice_definition("project.selection")

    assert resolved.question == "Which project should run?"


def test_catalog_rejects_duplicate_key() -> None:
    choice_definition().register("duplicate")

    with pytest.raises(ValueError, match="Duplicate choice definition key 'duplicate'."):
        choice_definition().register("duplicate")


def test_catalog_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown choice definition key 'missing'."):
        ChoiceDefinitionCatalog.resolve_choice_definition("missing")


def test_catalog_rejects_invalid_resolver_output() -> None:
    ChoiceDefinitionCatalog.register_choice_definition("bad", lambda: "oops")

    with pytest.raises(TypeError, match="expected ChoiceDefinition"):
        ChoiceDefinitionCatalog.resolve_choice_definition("bad")


def test_catalog_lists_and_validates_resolvers() -> None:
    choice_definition("A").register("a")
    choice_definition("B").register("b")

    ChoiceDefinitionCatalog.validate_registry()

    assert ChoiceDefinitionCatalog.list_choice_definition_keys() == ["a", "b"]
