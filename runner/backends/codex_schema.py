"""Codex output schema conversion and validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ValidationError


class CodexSchemaError(ValueError):
    """The requested result model cannot be represented by the Codex contract."""


class CodexResponseValidationError(ValueError):
    """The final Codex response does not satisfy the declared result model."""


_ANNOTATION_KEYS = frozenset({"default", "description", "title"})
_SCHEMA_KEYS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "anyOf",
        "enum",
        "items",
        "properties",
        "required",
        "type",
    }
)
_SCALAR_TYPES = frozenset({"boolean", "integer", "null", "number", "string"})


def build_codex_output_schema(result_type: object) -> dict[str, Any]:
    """Return the strict JSON Schema accepted by the Codex CLI backend.

    The contract intentionally accepts a small subset of Pydantic models. Every
    object is fixed, every declared field is required on the wire, and defaults
    remain a Python-side concern.
    """

    _require_fixed_base_model(result_type)
    assert isinstance(result_type, type) and issubclass(result_type, BaseModel)

    try:
        generated = result_type.model_json_schema(by_alias=True, mode="validation")
    except Exception as exc:  # pragma: no cover - defensive around Pydantic internals
        raise CodexSchemaError(
            f"$.result_type: failed to generate a JSON schema for {result_type.__name__}"
        ) from exc

    schema = deepcopy(generated)
    _normalize_schema(schema, "$", schema.get("$defs", {}))
    _reject_reference_cycles(schema)
    return schema


def validate_codex_output(
    result_type: object, raw_json: str | bytes
) -> BaseModel:
    """Strictly validate a final-message file against the original model."""

    schema = build_codex_output_schema(result_type)
    assert isinstance(result_type, type) and issubclass(result_type, BaseModel)

    if isinstance(raw_json, bytes):
        try:
            raw_json = raw_json.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CodexResponseValidationError(
                "Codex final response is not valid UTF-8"
            ) from exc
    elif not isinstance(raw_json, str):
        raise CodexResponseValidationError(
            "Codex final response must be UTF-8 JSON text"
        )

    try:
        result = result_type.model_validate_json(raw_json, strict=True)
    except ValidationError as exc:
        raise CodexResponseValidationError(_validation_message(exc)) from exc

    decoded = json.loads(raw_json)
    _require_wire_fields(decoded, schema, schema.get("$defs", {}), "$")
    return result


def _require_fixed_base_model(result_type: object) -> None:
    if not isinstance(result_type, type) or not issubclass(result_type, BaseModel):
        raise CodexSchemaError(
            "$.result_type: expected a Pydantic BaseModel subclass with a fixed object shape"
        )
    if getattr(result_type, "__pydantic_root_model__", False):
        raise CodexSchemaError("$.result_type: Pydantic RootModel is not supported")


def _normalize_schema(
    schema: object, location: str, definitions: Mapping[str, object]
) -> None:
    if not isinstance(schema, dict):
        raise CodexSchemaError(f"{location}: expected a JSON Schema object")

    for key in _ANNOTATION_KEYS:
        schema.pop(key, None)

    if "const" in schema:
        schema["enum"] = [schema.pop("const")]

    unknown = sorted(set(schema) - _SCHEMA_KEYS)
    if unknown:
        raise CodexSchemaError(
            f"{location}: unsupported schema constraint or keyword {unknown[0]!r}"
        )

    nested_definitions = schema.get("$defs")
    if nested_definitions is not None:
        if location != "$" or not isinstance(nested_definitions, dict):
            raise CodexSchemaError(f"{location}.$defs: unsupported definition container")
        for name, definition in nested_definitions.items():
            _normalize_schema(definition, f"{location}.$defs.{name}", nested_definitions)

    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            raise CodexSchemaError(f"{location}: only local $defs references are supported")
        target = reference.removeprefix("#/$defs/")
        if not target or "/" in target or target not in definitions:
            raise CodexSchemaError(f"{location}: unresolved local reference {reference!r}")
        remaining = set(schema) - {"$ref", "$defs"}
        if remaining:
            raise CodexSchemaError(
                f"{location}: a local reference cannot contain {sorted(remaining)[0]!r}"
            )
        return

    if "anyOf" in schema:
        variants = schema["anyOf"]
        if not isinstance(variants, list) or len(variants) != 2:
            raise CodexSchemaError(
                f"{location}: only a nullable union of one type and null is supported"
            )
        null_variants = [item for item in variants if item == {"type": "null"}]
        if len(null_variants) != 1:
            raise CodexSchemaError(
                f"{location}: only a nullable union of one type and null is supported"
            )
        remaining = set(schema) - {"anyOf", "$defs"}
        if remaining:
            raise CodexSchemaError(
                f"{location}: nullable unions cannot contain {sorted(remaining)[0]!r}"
            )
        for index, variant in enumerate(variants):
            _normalize_schema(variant, f"{location}.anyOf[{index}]", definitions)
        return

    schema_type = schema.get("type")
    if schema_type == "object":
        _normalize_object(schema, location, definitions)
        return
    if schema_type == "array":
        remaining = set(schema) - {"type", "items", "$defs"}
        if remaining:
            raise CodexSchemaError(
                f"{location}: arrays do not support {sorted(remaining)[0]!r}"
            )
        if "items" not in schema:
            raise CodexSchemaError(f"{location}: arrays require one item schema")
        _normalize_schema(schema["items"], f"{location}.items", definitions)
        return
    if schema_type in _SCALAR_TYPES:
        _normalize_scalar(schema, location)
        return

    raise CodexSchemaError(f"{location}: unsupported or missing schema type")


def _normalize_object(
    schema: dict[str, Any], location: str, definitions: Mapping[str, object]
) -> None:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise CodexSchemaError(f"{location}: fixed objects require properties")
    if schema.get("additionalProperties") is not False:
        raise CodexSchemaError(
            f"{location}: model must set extra='forbid'; arbitrary properties are unsupported"
        )

    remaining = set(schema) - {
        "$defs",
        "additionalProperties",
        "properties",
        "required",
        "type",
    }
    if remaining:
        raise CodexSchemaError(
            f"{location}: objects do not support {sorted(remaining)[0]!r}"
        )

    schema["required"] = list(properties)
    for name, field_schema in properties.items():
        _normalize_schema(field_schema, f"{location}.properties.{name}", definitions)


def _normalize_scalar(schema: dict[str, Any], location: str) -> None:
    remaining = set(schema) - {"type", "enum", "$defs"}
    if remaining:
        raise CodexSchemaError(
            f"{location}: scalar fields do not support {sorted(remaining)[0]!r}"
        )
    if "enum" in schema:
        values = schema["enum"]
        if not isinstance(values, list) or not values:
            raise CodexSchemaError(f"{location}: enums require at least one value")
        if not all(_enum_value_matches(schema["type"], value) for value in values):
            raise CodexSchemaError(
                f"{location}: enum values must all match the declared scalar type"
            )


def _enum_value_matches(schema_type: str, value: object) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return value is None


def _reject_reference_cycles(schema: dict[str, Any]) -> None:
    definitions = schema.get("$defs", {})
    if not isinstance(definitions, dict):
        return

    edges = {
        name: _definition_references(definition)
        for name, definition in definitions.items()
    }
    visited: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        if name in active:
            raise CodexSchemaError(
                f"$.$defs.{name}: recursive local references are not supported"
            )
        if name in visited:
            return
        active.add(name)
        for target in edges.get(name, set()):
            visit(target)
        active.remove(name)
        visited.add(name)

    for definition_name in definitions:
        visit(definition_name)


def _definition_references(value: object) -> set[str]:
    references: set[str] = set()
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            references.add(reference.removeprefix("#/$defs/"))
        for child in value.values():
            references.update(_definition_references(child))
    elif isinstance(value, list):
        for child in value:
            references.update(_definition_references(child))
    return references


def _validation_message(exc: ValidationError) -> str:
    errors = exc.errors(include_input=False, include_url=False)
    if errors and errors[0].get("type") == "json_invalid":
        return "Codex final response is not valid JSON"

    details: list[str] = []
    for error in errors:
        location_parts = error.get("loc", ())
        location = "$" + "".join(f".{part}" for part in location_parts)
        details.append(f"{location}: {error.get('msg', 'invalid value')}")
    suffix = "; ".join(details) if details else "invalid value"
    return f"Codex final response failed strict validation at {suffix}"


def _require_wire_fields(
    value: object,
    schema: Mapping[str, Any],
    definitions: Mapping[str, object],
    location: str,
) -> None:
    reference = schema.get("$ref")
    if isinstance(reference, str):
        target = reference.removeprefix("#/$defs/")
        target_schema = definitions[target]
        assert isinstance(target_schema, Mapping)
        _require_wire_fields(value, target_schema, definitions, location)
        return

    variants = schema.get("anyOf")
    if isinstance(variants, list):
        if value is None:
            return
        non_null = next(item for item in variants if item != {"type": "null"})
        assert isinstance(non_null, Mapping)
        _require_wire_fields(value, non_null, definitions, location)
        return

    if schema.get("type") == "object":
        assert isinstance(value, dict)
        properties = schema["properties"]
        assert isinstance(properties, Mapping)
        for name, field_schema in properties.items():
            field_location = f"{location}.{name}"
            if name not in value:
                raise CodexResponseValidationError(
                    f"{field_location}: field is required on the wire"
                )
            assert isinstance(field_schema, Mapping)
            _require_wire_fields(
                value[name], field_schema, definitions, field_location
            )
        return

    if schema.get("type") == "array":
        assert isinstance(value, list)
        item_schema = schema["items"]
        assert isinstance(item_schema, Mapping)
        for index, item in enumerate(value):
            _require_wire_fields(
                item, item_schema, definitions, f"{location}[{index}]"
            )
