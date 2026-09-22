"""Shared definition registration supports custom definition types."""

from dataclasses import dataclass

import pytest

from agents.core import Definition, DefinitionCatalog


def test_custom_definition_registers_itself_in_its_catalog():
    @dataclass(frozen=True, slots=True)
    class ExampleDefinition(Definition):
        instruction: str

        @classmethod
        def _get_catalog(cls):
            return ExampleCatalog

    class ExampleCatalog(DefinitionCatalog[ExampleDefinition]):
        definition_type = ExampleDefinition
        definition_label = "example definition"

    definition = ExampleDefinition("Select one")
    definition.register("example")

    assert ExampleCatalog.resolve("example") is definition
    assert not hasattr(definition, "__dict__")
    with pytest.raises(ValueError, match="Duplicate example definition key"):
        definition.register("example")


def test_definition_requires_a_catalog_implementation():
    with pytest.raises(TypeError, match="abstract"):
        Definition()
